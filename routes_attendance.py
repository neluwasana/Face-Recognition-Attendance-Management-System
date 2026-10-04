import base64
import os
import datetime
import json
import re
import cv2
import numpy as np
from flask import render_template, request, jsonify, session, flash, redirect, url_for
from db import get_db
from routes_student import preprocess_face

# Absolute paths for data directories to ensure consistency regardless of CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAINER_DIR = os.path.join(BASE_DIR, "trainer")
TRAINER_FILE = os.path.join(TRAINER_DIR, "trainer.yml")

# Cache for face recognition model and label mapping to speed up processing
_cached_recognizer = None
_cached_names = None
_cached_mtime = None
_cached_hists = None
_cached_labels = None
_cached_face_cascade = None

def get_cached_recognizer_data():
    global _cached_recognizer, _cached_names, _cached_mtime, _cached_hists, _cached_labels
    if not os.path.exists(TRAINER_FILE):
        return None, None, None, None
    try:
        mtime = os.path.getmtime(TRAINER_FILE)
    except Exception:
        mtime = 0
    
    if _cached_recognizer is None or _cached_names is None or _cached_mtime != mtime:
        print("[CACHE] Loading trainer and building label mapping...")
        recognizer = cv2.face.LBPHFaceRecognizer_create(radius=2, neighbors=8, grid_x=8, grid_y=8)
        recognizer.read(TRAINER_FILE)
        
        # Build label -> folder mapping
        names = {}
        if os.path.exists(DATASET_DIR):
            folders = []
            for f in sorted(os.listdir(DATASET_DIR)):
                f_path = os.path.join(DATASET_DIR, f)
                if os.path.isdir(f_path):
                    try:
                        has_face = any(
                            img.startswith("face_") and img.lower().endswith((".png", ".jpg", ".jpeg"))
                            for img in os.listdir(f_path)
                        )
                        if has_face:
                            folders.append(f)
                    except Exception:
                        pass
            for idx, folder in enumerate(folders):
                names[idx] = folder
        
        # Pre-extract histograms/labels and convert to float32 to avoid frame-by-frame overhead
        try:
            hists = [h.astype(np.float32) for h in recognizer.getHistograms()]
            labels = recognizer.getLabels().flatten()
        except Exception as e:
            print(f"[CACHE] Error extracting histograms: {e}")
            hists = []
            labels = np.array([])
            
        _cached_recognizer = recognizer
        _cached_names = names
        _cached_mtime = mtime
        _cached_hists = hists
        _cached_labels = labels
        
    return _cached_recognizer, _cached_names, _cached_hists, _cached_labels


def get_cached_face_cascade():
    """Cache the Haar cascade classifier so it isn't reloaded every request."""
    global _cached_face_cascade
    if _cached_face_cascade is None:
        _cached_face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _cached_face_cascade



def validate_attendance_session(student_id, lecture_name, cursor):
    """
    Shared validation for face, QR, and manual attendance.
    Returns:
        (True,  timetable_entry_id)   — OK to mark attendance
        (False, "ALREADY_MARKED")     — already recorded today (caller handles UI)
        (False, "<error message>")    — validation failed (caller shows error)
    """
    import datetime
    today = datetime.date.today()
    now = datetime.datetime.now()
    current_seconds = now.hour * 3600 + now.minute * 60 + now.second

    print(f"[VALIDATE] student={student_id}, lecture={lecture_name}, today={today}, time_secs={current_seconds}")

    # Check student exists and is active
    cursor.execute(
        "SELECT department, year, semester, part_time_full_time, status FROM students WHERE student_id = %s",
        (student_id,)
    )
    student = cursor.fetchone()
    if not student:
        return False, "Student not found."
    if student.get("status") == "Inactive":
        return False, "Inactive students cannot mark attendance."

    dept = (student["department"] or "").strip()
    year = (student["year"] or "").strip()
    sem  = (student["semester"] or "").strip()
    mode = (student["part_time_full_time"] or "Full Time").strip()

    print(f"[VALIDATE] dept={dept}, year={year}, sem={sem}, mode={mode}")

    # Check duplicate attendance for today — return special sentinel so callers can distinguish
    cursor.execute(
        "SELECT id FROM attendance WHERE student_id = %s AND lecture_name = %s AND date = %s",
        (student_id, lecture_name, today)
    )
    if cursor.fetchone():
        return False, "ALREADY_MARKED"

    # Query timetable for today
    day_name = today.strftime("%A")
    cursor.execute("""
        SELECT t.*, s.subject_code, s.subject_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        WHERE (LOWER(TRIM(t.course)) = LOWER(%s) OR LOWER(TRIM(t.course)) LIKE LOWER(CONCAT('%%', %s, '%%')) OR LOWER(%s) LIKE LOWER(CONCAT('%%', TRIM(t.course), '%%')))
          AND LOWER(TRIM(t.year)) = LOWER(%s)
          AND LOWER(TRIM(t.semester)) = LOWER(%s)
          AND LOWER(TRIM(t.part_time_full_time)) = LOWER(%s)
          AND (
              ((t.day IS NULL OR t.day = '') AND t.lecture_date = %s)
              OR
              (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
          )
    """, (dept, dept, dept, year, sem, mode, today, day_name, today, today))
    entries = cursor.fetchall()
    print(f"[VALIDATE] Timetable entries found: {len(entries)}")

    active_entry = None
    cancelled_entry = None
    time_mismatch = False
    subject_mismatch = False
    time_range_str = ""
    scheduled_subject_str = ""

    for entry in entries:
        start_td = entry["start_time"]
        end_td   = entry["end_time"]

        start_secs = int(start_td.total_seconds()) if hasattr(start_td, "total_seconds") else start_td.hour * 3600 + start_td.minute * 60
        end_secs   = int(end_td.total_seconds())   if hasattr(end_td,   "total_seconds") else end_td.hour   * 3600 + end_td.minute   * 60

        try:
            mark_mins = int(entry.get("attendance_mark_time") or 0)
        except Exception:
            mark_mins = 0

        att_end_secs = start_secs + mark_mins * 60
        if mark_mins == 0 or att_end_secs > end_secs:
            att_end_secs = end_secs

        print(f"[VALIDATE] Entry id={entry['id']} start={start_secs}s end={end_secs}s mark_window_end={att_end_secs}s current={current_seconds}s")

        if start_secs <= current_seconds <= end_secs:
            if current_seconds > att_end_secs:
                time_mismatch = True
                sh, sm = divmod(start_secs // 60, 60)
                eh, em = divmod(att_end_secs // 60, 60)
                time_range_str = f"{sh:02d}:{sm:02d} - {eh:02d}:{em:02d} (Window Expired)"
                continue
            if entry.get("is_cancelled") in ('1', 1):
                cancelled_entry = entry
            else:
                code = entry["subject_code"]
                name = entry["subject_name"]
                lname_lower = lecture_name.lower()
                code_lower  = code.lower()
                sname_lower = name.lower()
                if (code_lower in lname_lower or sname_lower in lname_lower
                        or lname_lower in code_lower or lname_lower in sname_lower):
                    active_entry = entry
                    break
                else:
                    subject_mismatch = True
                    scheduled_subject_str = f"{code} - {name}"
        else:
            time_mismatch = True
            sh, sm = divmod(start_secs // 60, 60)
            eh, em = divmod(end_secs // 60, 60)
            time_range_str = f"{sh:02d}:{sm:02d} - {eh:02d}:{em:02d}"

    if not active_entry:
        if cancelled_entry:
            reason = cancelled_entry.get("cancel_reason", "")
            return False, f"Lecture is cancelled today{' (' + reason + ')' if reason else ''}."
        if subject_mismatch:
            return False, f"Subject mismatch. Scheduled: '{scheduled_subject_str}'."
        if time_mismatch:
            return False, f"No active class at this time. Scheduled: {time_range_str}. (Check timetable AM/PM settings)"
        if len(entries) == 0:
            return False, f"No timetable entry found for today. Please check the timetable for {dept} {year} {sem} ({mode})."
        return False, "No active lecture found for your class right now."

    return True, active_entry["id"]


def register_attendance_routes(app):
    # --- Mark Attendance Page ---

    @app.route("/mark_attendance")
    def mark_attendance():
        if "user" not in session:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        return render_template("mark_attendance.html")


    # --- Mark Attendance API (face recognition) ---

    @app.route("/api/mark-attendance", methods=["POST"])
    def api_mark_attendance():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        try:
            data         = request.get_json() or {}
            image_data   = data.get("image", "")
            lecture_name = data.get("lecture_name", "")
            lecturer     = data.get("lecturer_name", "")

            if not image_data or not lecture_name:
                return jsonify({"success": False, "message": "No image or session selected. Please try again."})

            # --- Decode image ---
            try:
                img_bytes = base64.b64decode(image_data.split(",")[1])
                np_arr    = np.frombuffer(img_bytes, np.uint8)
                frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except Exception as e:
                print(f"[FACE ATT] Image decode error: {e}")
                return jsonify({"success": False, "message": "No face detected. Please try again."})

            # --- Face detection (cached cascade, looser params for better detection rate) ---
            face_cascade = get_cached_face_cascade()
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50)
            )
            if len(faces) == 0:
                session.pop("face_temp_match", None)
                return jsonify({"success": False, "message": "No face detected. Please try again."})

            # --- Load trained model (using cache to avoid reading from disk on every frame) ---
            if not os.path.exists(TRAINER_FILE):
                session.pop("face_temp_match", None)
                print("[FACE ATT] trainer.yml not found")
                return jsonify({"success": False, "message": "Face recognition is not ready. Please contact the admin."})

            recognizer, names, trained_hists, trained_labels = get_cached_recognizer_data()
            if not recognizer or not names:
                session.pop("face_temp_match", None)
                return jsonify({"success": False, "message": "Face recognition is not ready. Please contact the admin."})

            num_students = len(names)

            # --- Preprocess face ROI ---
            (x, y, w, h) = max(faces, key=lambda r: r[2] * r[3])
            face_roi = preprocess_face(gray, x, y, w, h)

            # --- Recognition thresholds ---
            CONFIDENCE_THRESHOLD = 90.0   # Chi-Square: lower = better match (raised for easier recognition)
            MARGIN_THRESHOLD     = 5.0    # Min gap between best & 2nd-best score (lowered for single-student classes)

            try:
                dummy_rec = cv2.face.LBPHFaceRecognizer_create(radius=2, neighbors=8, grid_x=8, grid_y=8)
                dummy_rec.train([face_roi], np.array([0]))
                query_hist = dummy_rec.getHistograms()[0].astype(np.float32)

                student_scores = {}
                for hist, lbl in zip(trained_hists, trained_labels):
                    lbl  = int(lbl)
                    dist = cv2.compareHist(query_hist, hist, cv2.HISTCMP_CHISQR)
                    if lbl not in student_scores or dist < student_scores[lbl]:
                        student_scores[lbl] = dist

                sorted_scores = sorted(student_scores.items(), key=lambda x: x[1])
                print(f"[FACE REC] Scores: {sorted_scores}")

                if not sorted_scores:
                    session.pop("face_temp_match", None)
                    return jsonify({"success": False, "message": "No face - face not recognized."})

                best_label, best_conf = sorted_scores[0]
                confidence = best_conf

                if best_conf > CONFIDENCE_THRESHOLD:
                    session.pop("face_temp_match", None)
                    return jsonify({"success": False, "message": "No face - face not recognized. Please look directly at the camera."})

                if num_students > 1 and len(sorted_scores) >= 2:
                    margin = sorted_scores[1][1] - best_conf
                    if margin < MARGIN_THRESHOLD:
                        session.pop("face_temp_match", None)
                        return jsonify({"success": False, "message": "No face - ambiguous match. Please reposition."})

            except Exception as e:
                print(f"[FACE REC] Recognition error: {e}")
                session.pop("face_temp_match", None)
                return jsonify({"success": False, "message": "Face recognition failed. Please try again."})

            # --- Map label to student folder ---
            student_folder = names.get(best_label, "Unknown")
            if student_folder == "Unknown":
                session.pop("face_temp_match", None)
                return jsonify({"success": False, "message": "No face - face not found in dataset. Please register first."})
            print(f"[FACE REC] Recognized '{student_folder}' conf={best_conf:.2f}")

            # --- Look up student in DB ---
            db     = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM students 
                WHERE LOWER(REPLACE(student_id, '/', '_')) = LOWER(%s)
                   OR LOWER(REPLACE(REPLACE(CONCAT(student_id, '_', department), '/', '_'), ' ', '_')) = LOWER(%s)
                   OR LOWER(REPLACE(full_name, ' ', '_')) = LOWER(%s)
                LIMIT 1
            """, (student_folder, student_folder, student_folder))
            student = cursor.fetchone()

            if not student:
                cursor.close(); db.close()
                session.pop("face_temp_match", None)
                print(f"[FACE REC] No DB row for '{student_folder}'")
                return jsonify({"success": False, "message": "Student not found. Please contact the admin."})

            if student.get("status") == "Inactive":
                cursor.close(); db.close()
                session.pop("face_temp_match", None)
                return jsonify({"success": False, "message": "Your student account is inactive. Please contact the admin."})

            # --- Consecutive frames gate ---
            face_match  = session.get("face_temp_match")
            current_sid = student["student_id"]
            count = (face_match.get("count", 0) + 1) if (face_match and face_match.get("student_id") == current_sid) else 1
            session["face_temp_match"] = {"student_id": current_sid, "count": count}

            REQUIRED = 1
            if count < REQUIRED:
                cursor.close(); db.close()
                return jsonify({"success": False, "message": f"No face - stabilizing... ({count}/{REQUIRED})"})

            session.pop("face_temp_match", None)

            # --- Validate timetable session ---
            student_id   = student["student_id"]
            student_name = student["full_name"]
            today    = datetime.date.today()
            time_now = datetime.datetime.now().strftime("%H:%M:%S")

            ok, result = validate_attendance_session(student_id, lecture_name, cursor)
            if not ok:
                cursor.close(); db.close()
                if result == "ALREADY_MARKED":
                    return jsonify({"success": False, "already_marked": True,
                                    "student_name": student_name, "student_id": student_id,
                                    "time": time_now,
                                    "message": f"Attendance already marked for {student_name} today."})
                # Map timetable errors to friendly messages
                msg = result.lower()
                if "inactive" in msg:
                    friendly = "Your student account is inactive. Please contact the admin."
                elif "cancelled" in msg:
                    friendly = "This lecture has been cancelled today."
                elif "subject mismatch" in msg:
                    friendly = "Wrong subject selected. Please check the session details."
                elif "no active class" in msg or "no timetable" in msg or "no active lecture" in msg:
                    friendly = "No active class at this time. Check your timetable."
                elif "time" in msg:
                    friendly = "Attendance window has closed for this session."
                else:
                    friendly = "Could not mark attendance. Please check the timetable."
                return jsonify({"success": False, "message": friendly})

            # --- Insert attendance ---
            cursor.execute(
                "INSERT INTO attendance (student_id, student_name, lecture_name, lecturer, date, time) VALUES (%s,%s,%s,%s,%s,%s)",
                (student_id, student_name, lecture_name, lecturer, today, time_now)
            )
            db.commit()
            cursor.close(); db.close()

            return jsonify({"success": True, "student_name": student_name,
                            "student_id": student_id, "time": time_now, "confidence": int(confidence)})

        except Exception as e:
            import traceback
            print(f"[FACE ATT] Unhandled error:\n{traceback.format_exc()}")
            return jsonify({"success": False, "message": "Could not mark attendance. Please try again."})

    @app.route('/api/mark-attendance-qr', methods=['POST'])
    def api_mark_attendance_qr():
        """Mark attendance via scanned QR code containing student_id."""
        if "user" not in session and "lecturer_id" not in session and "lecturer" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data         = request.get_json() or {}
        student_id   = data.get("student_id", "").strip()
        lecture_name = data.get("lecture_name", "").strip()
        lecturer     = data.get("lecturer_name", "").strip() or session.get("lecturer_name", "").strip() or session.get("user", "").strip()

        print(f"[API QR] student_id={student_id}, lecture_name={lecture_name}, lecturer={lecturer}, session_user={session.get('user')}, session_lecturer_id={session.get('lecturer_id')}")

        if not student_id or not lecture_name:
            return jsonify({"success": False, "message": "Missing student ID or lecture name."})

        db = get_db()
        cursor = db.cursor(dictionary=True)
        today    = datetime.date.today()
        time_now = datetime.datetime.now().strftime("%H:%M:%S")

        # Fetch student info (support raw text, URL query, JSON QR payload, slashes/underscores, and alphanumeric matching)
        clean_input = student_id.strip()
        if "data=" in clean_input or "student_id=" in clean_input or "id=" in clean_input:
            try:
                from urllib.parse import parse_qs, urlparse
                parsed_url = urlparse(clean_input)
                qs = parse_qs(parsed_url.query or clean_input)
                extracted = qs.get("data") or qs.get("student_id") or qs.get("id")
                if extracted and extracted[0]:
                    clean_input = extracted[0].strip()
            except Exception:
                pass

        if clean_input.startswith('{') and clean_input.endswith('}'):
            try:
                parsed_qr = json.loads(clean_input)
                clean_input = str(parsed_qr.get("student_id") or parsed_qr.get("index") or parsed_qr.get("id") or clean_input).strip()
            except Exception:
                pass

        cursor.execute(
            """SELECT student_id, full_name FROM students 
               WHERE LOWER(TRIM(student_id)) = LOWER(%s)
                  OR LOWER(REPLACE(student_id, '/', '_')) = LOWER(REPLACE(%s, '/', '_'))
                  OR LOWER(REPLACE(student_id, '_', '/')) = LOWER(REPLACE(%s, '_', '/'))
                  OR LOWER(REPLACE(student_id, '/', '-')) = LOWER(REPLACE(%s, '/', '-'))
               LIMIT 1""",
            (clean_input, clean_input, clean_input, clean_input)
        )
        student_row = cursor.fetchone()
        
        # Fallback: Alphanumeric stripping (e.g. NAW/IT/2324/F/0009 vs NAWIT2324F0009)
        if not student_row:
            cursor.execute("SELECT student_id, full_name FROM students")
            all_students = cursor.fetchall()
            target_norm = re.sub(r'[^a-zA-Z0-9]', '', clean_input).lower()
            if target_norm:
                for s in all_students:
                    s_norm = re.sub(r'[^a-zA-Z0-9]', '', str(s["student_id"] or '')).lower()
                    if s_norm and s_norm == target_norm:
                        student_row = s
                        break
        
        if not student_row:
            cursor.close()
            db.close()
            print(f"[API QR] Student '{clean_input}' not found in database.")
            return jsonify({"success": False, "message": f"Student ID '{clean_input}' not found in database."})
            
        canonical_student_id = student_row["student_id"]
        student_name = student_row["full_name"]

        success, result = validate_attendance_session(canonical_student_id, lecture_name, cursor)
        if not success:
            cursor.close()
            db.close()
            print(f"[API QR] Validation failed for {canonical_student_id}: {result}")
            # Special sentinel: already marked today — surface as warning, not error
            if result == "ALREADY_MARKED":
                return jsonify({
                    "success": False,
                    "already_marked": True,
                    "student_id": canonical_student_id,
                    "student_name": student_name,
                    "time": time_now,
                    "message": f"Attendance already marked for {student_name} today."
                })
            
            msg = str(result).lower()
            if "inactive" in msg:
                friendly = "Student account is inactive. Please contact the admin."
            elif "cancelled" in msg:
                friendly = "This lecture has been cancelled today."
            elif "subject mismatch" in msg:
                friendly = "Subject mismatch. Check session details."
            elif "no active class" in msg or "no timetable" in msg or "no active lecture" in msg:
                friendly = "No active class at this time. Check your timetable."
            elif "time" in msg:
                friendly = "Attendance window has closed for this session."
            else:
                friendly = str(result)
            return jsonify({"success": False, "message": friendly})

        try:
            cursor.execute(
                "INSERT INTO attendance (student_id, student_name, lecture_name, lecturer, date, time) VALUES (%s, %s, %s, %s, %s, %s)",
                (canonical_student_id, student_name, lecture_name, lecturer, today, time_now)
            )
            db.commit()
            cursor.close()
            db.close()
            print(f"[QR ATTENDANCE] Marked for {student_name} ({canonical_student_id}) — {lecture_name}")
            return jsonify({
                "success": True,
                "student_id": canonical_student_id,
                "student_name": student_name,
                "message": f"QR Attendance marked for {student_name}!"
            })
        except Exception as e:
            cursor.close()
            db.close()
            print(f"[QR ATTENDANCE] DB error: {e}")
            return jsonify({"success": False, "message": f"Database error: {str(e)}"})

    # --- Active Session Getter API ---

    @app.route("/api/get-active-session")
    def api_get_active_session():
        if "user" not in session and "lecturer_id" not in session and "lecturer" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
            
        course = request.args.get("course", "").strip()
        year = request.args.get("year", "").strip()
        semester = request.args.get("semester", "").strip()
        study_mode = request.args.get("study_mode", "").strip()
        subject_id = request.args.get("subject_id", "").strip()
        
        if not (course and year and semester and study_mode and subject_id):
            return jsonify({"success": False, "message": "Missing parameters"})
            
        db = get_db()
        cursor = db.cursor(dictionary=True)
        today = datetime.date.today()
        
        day_name = today.strftime("%A")
        cursor.execute("""
            SELECT t.*, s.subject_code, s.subject_name, l.lecturer_name
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            JOIN lecturers l ON t.lecturer_id = l.id
            WHERE LOWER(TRIM(t.course)) = LOWER(%s)
              AND LOWER(TRIM(t.year)) = LOWER(%s)
              AND LOWER(TRIM(t.semester)) = LOWER(%s)
              AND LOWER(TRIM(t.part_time_full_time)) = LOWER(%s)
              AND t.subject_id = %s
              AND (
                  ((t.day IS NULL OR t.day = '') AND t.lecture_date = %s)
                  OR
                  (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
              )
            LIMIT 1
        """, (course, year, semester, study_mode, subject_id, today, day_name, today, today))
        
        entry = cursor.fetchone()
        cursor.close()
        db.close()
        
        if entry:
            start_time = entry["start_time"]
            end_time = entry["end_time"]
            
            now = datetime.datetime.now()
            current_seconds = now.hour * 3600 + now.minute * 60 + now.second
            
            if hasattr(start_time, "total_seconds"):
                start_secs = int(start_time.total_seconds())
            else:
                start_secs = start_time.hour * 3600 + start_time.minute * 60 + start_time.second

            if hasattr(end_time, "total_seconds"):
                end_secs = int(end_time.total_seconds())
            else:
                end_secs = end_time.hour * 3600 + end_time.minute * 60 + end_time.second
            
            is_active_time = (start_secs <= current_seconds <= end_secs)
            
            start_str = str(entry["start_time"])
            end_str = str(entry["end_time"])
            if len(start_str) > 5: start_str = start_str[:5]
            if len(end_str) > 5: end_str = end_str[:5]
            
            return jsonify({
                "success": True,
                "session_info": f"{start_str} - {end_str} ({entry['location']})",
                "lecturer_id": entry["lecturer_id"],
                "lecturer_name": entry["lecturer_name"],
                "is_cancelled": entry["is_cancelled"],
                "is_active_time": is_active_time
            })
        else:
            return jsonify({
                "success": False,
                "message": "No active session found for today"
            })


    # --- Manual Attendance Marking API ---

    @app.route("/api/mark-attendance-manual", methods=["POST"])
    def api_mark_attendance_manual():
        if "user" not in session and "lecturer_id" not in session and "lecturer" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data          = request.get_json() or {}
        student_id   = data.get("student_id", "").strip()
        lecture_name = data.get("lecture_name", "").strip()
        lecturer     = data.get("lecturer_name", "").strip() or session.get("lecturer_name", "").strip() or session.get("user", "").strip()
        action       = data.get("action", "mark").strip()

        if not student_id or not lecture_name:
            return jsonify({"success": False, "message": "Missing required fields!"})

        today = datetime.date.today()
        time_now = datetime.datetime.now().strftime("%H:%M:%S")

        db = get_db()
        cursor = db.cursor(dictionary=True)

        if action == "unmark":
            cursor.execute(
                "DELETE FROM attendance WHERE (LOWER(TRIM(student_id)) = LOWER(%s) OR LOWER(REPLACE(student_id, '/', '_')) = LOWER(REPLACE(%s, '/', '_'))) AND lecture_name=%s AND date=%s",
                (student_id, student_id, lecture_name, today)
            )
            db.commit()
            cursor.close()
            db.close()
            return jsonify({
                "success": True,
                "message": "Attendance unmarked successfully",
                "student_id": student_id,
                "action": "unmark"
            })

        # Check if student exists (robust matching)
        clean_input = student_id.strip()
        cursor.execute(
            """SELECT * FROM students 
               WHERE LOWER(TRIM(student_id)) = LOWER(%s)
                  OR LOWER(REPLACE(student_id, '/', '_')) = LOWER(REPLACE(%s, '/', '_'))
                  OR LOWER(REPLACE(student_id, '_', '/')) = LOWER(REPLACE(%s, '_', '/'))
                  OR LOWER(REPLACE(student_id, '/', '-')) = LOWER(REPLACE(%s, '/', '-'))
               LIMIT 1""",
            (clean_input, clean_input, clean_input, clean_input)
        )
        student = cursor.fetchone()

        if not student:
            cursor.execute("SELECT * FROM students")
            all_students = cursor.fetchall()
            target_norm = re.sub(r'[^a-zA-Z0-9]', '', clean_input).lower()
            if target_norm:
                for s in all_students:
                    s_norm = re.sub(r'[^a-zA-Z0-9]', '', str(s["student_id"] or '')).lower()
                    if s_norm and s_norm == target_norm:
                        student = s
                        break

        if not student:
            cursor.close()
            db.close()
            return jsonify({"success": False, "message": f"Student with ID '{student_id}' not found."})

        # Check student status
        if student.get("status") == "Inactive":
            cursor.close()
            db.close()
            return jsonify({"success": False, "message": "Inactive students cannot mark attendance."})

        student_db_id = student["student_id"]
        student_name  = student["full_name"]



        # Check if already marked
        cursor.execute(
            "SELECT id FROM attendance WHERE student_id=%s AND lecture_name=%s AND date=%s",
            (student_db_id, lecture_name, today)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.close()
            db.close()
            return jsonify({
                "success": True,
                "message": "Attendance already marked",
                "student_name": student_name,
                "student_id": student_db_id,
                "time": time_now
            })

        # Insert attendance record
        cursor.execute(
            "INSERT INTO attendance (student_id, student_name, lecture_name, lecturer, date, time) VALUES (%s,%s,%s,%s,%s,%s)",
            (student_db_id, student_name, lecture_name, lecturer, today, time_now)
        )
        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Attendance marked manually",
            "student_name": student_name,
            "student_id": student_db_id,
            "time": time_now,
            "action": "mark"
        })


    #Get Students by Class API

    @app.route("/api/get-students-by-class")
    def api_get_students_by_class():
        if "user" not in session and "lecturer" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
            
        course_id = request.args.get("course_id", "").strip()
        year = request.args.get("year", "").strip()
        semester = request.args.get("semester", "").strip()
        study_mode = request.args.get("study_mode", "").strip()
        lecture_name = request.args.get("lecture_name", "").strip()
        
        if not (course_id and year and semester and study_mode):
            return jsonify({"success": False, "message": "Missing filtering parameters"})
            
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT course_code, course_name FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        if not course:
            cursor.close()
            db.close()
            return jsonify({"success": False, "message": "Course not found"})
            
        cursor.execute("""
            SELECT student_id, full_name 
            FROM students 
            WHERE (TRIM(department) = %s OR TRIM(department) = %s)
              AND TRIM(year) = %s
              AND TRIM(semester) = %s
              AND TRIM(part_time_full_time) = %s
              AND status = 'Active'
            ORDER BY student_id
        """, (course["course_code"].strip(), course["course_name"].strip(), year, semester, study_mode))
        students = cursor.fetchall()
        
        today = datetime.date.today()
        marked_ids = []
        if lecture_name:
            cursor.execute("""
                SELECT student_id 
                FROM attendance 
                WHERE lecture_name = %s AND date = %s
            """, (lecture_name, today))
            marked_ids = [row["student_id"] for row in cursor.fetchall()]
            
        cursor.close()
        db.close()
        
        for s in students:
            s["marked"] = s["student_id"] in marked_ids
            
        return jsonify({
            "success": True,
            "students": students
        })


    #  Attendance Report Page 

    @app.route("/attendance_report")
    def attendance_report():
        if "user" not in session:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        return render_template("attendance_report.html")


    # --- Print / PDF Attendance Report Page ---

    @app.route("/print_attendance_report")
    def print_attendance_report():
        if "user" not in session and "lecturer" not in session:
            return redirect(url_for("home"))
        return render_template("print_attendance_report.html")


    # --- Attendance Report API ---

    @app.route("/api/attendance-report")
    def api_attendance_report():
        if "user" not in session and "lecturer_id" not in session:
            return jsonify({"error": "Not logged in"}), 401

        date_filter       = request.args.get("date", "")
        student_filter    = request.args.get("student", "")
        lecture_filter    = request.args.get("lecture", "")
        study_mode_filter = request.args.get("study_mode", "")
        dept_filter       = request.args.get("department", "")
        year_filter       = request.args.get("year", "")
        semester_filter   = request.args.get("semester", "")

        db = get_db()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT a.*, s.year, s.semester, s.part_time_full_time, s.department
            FROM attendance a
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        """
        params = []

        if date_filter:
            sql += " AND a.date = %s"
            params.append(date_filter)

        if student_filter:
            sql += " AND (a.student_name LIKE %s OR a.student_id LIKE %s)"
            params.extend([f"%{student_filter}%", f"%{student_filter}%"])

        if lecture_filter:
            sql += " AND a.lecture_name LIKE %s"
            params.append(f"%{lecture_filter}%")

        if study_mode_filter:
            sql += " AND s.part_time_full_time = %s"
            params.append(study_mode_filter)

        if dept_filter:
            sql += " AND (TRIM(s.department) = %s OR a.lecture_name LIKE %s)"
            params.extend([dept_filter, f"%{dept_filter}%"])

        if year_filter:
            sql += " AND TRIM(s.year) = %s"
            params.append(year_filter)

        if semester_filter:
            sql += " AND TRIM(s.semester) = %s"
            params.append(semester_filter)

        sql += " ORDER BY a.date DESC, a.time DESC"

        cursor.execute(sql, params)
        records = cursor.fetchall()

        for r in records:
            r["date"] = str(r["date"])
            r["time"] = str(r["time"])

        cursor.execute("SELECT COUNT(DISTINCT student_id) AS cnt FROM attendance")
        unique_students = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT lecture_name) AS cnt FROM attendance")
        unique_lectures = cursor.fetchone()["cnt"]

        cursor.close()
        db.close()

        return jsonify({
            "records":         records,
            "total_records":   len(records),
            "unique_students": unique_students,
            "unique_lectures": unique_lectures
        })
