import base64
import os
import cv2
import numpy as np
from flask import (
    render_template,
    request,
    redirect,
    flash,
    session,
    url_for,
    jsonify,
    send_from_directory,
)
from db import get_db
from PIL import Image

# Absolute paths — works regardless of which directory Flask is launched from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAINER_DIR = os.path.join(BASE_DIR, "trainer")
TRAINER_FILE = os.path.join(TRAINER_DIR, "trainer.yml")



def preprocess_face(gray_img, x, y, w, h):
    """Crop only the face region correctly using standard bounding box to maintain compatibility."""
    h_img, w_img = gray_img.shape[:2]
    # Ensure coordinates are within image boundaries
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w_img, x + w)
    y2 = min(h_img, y + h)
    
    face_crop = gray_img[y1:y2, x1:x2]
    face_resized = cv2.resize(face_crop, (200, 200))
    
    # Apply CLAHE for lighting normalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    face_preprocessed = clahe.apply(face_resized)
    return face_preprocessed


def auto_train_model():
    """
    Train LBPH model from dataset with augmentation.
    Each registered face_*.jpg is expanded into multiple augmented variants
    (horizontal flip + brightness shifts) so LBPH has enough per-student
    variance to reliably distinguish between registered students.
    Pre-cropped 200x200 grayscale CLAHE images are loaded directly —
    no re-detection needed. This ensures parity with the recognition pipeline.
    """
    try:
        cleanup_deleted_student_folders()
        if not os.path.exists(DATASET_DIR):
            return False, "Dataset folder does not exist."

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
        faces = []
        ids   = []

        for idx, student_folder in enumerate(folders):
            student_path = os.path.join(DATASET_DIR, student_folder)
            for image_name in sorted(os.listdir(student_path)):
                # Only load pre-cropped face images (prefixed face_)
                if image_name.startswith("face_") and image_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    image_path = os.path.join(student_path, image_name)
                    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                    if img is None:
                        continue
                    img = cv2.resize(img, (200, 200))

                    # ── Rich Augmentation for live-camera robustness 
                    # 1. Original
                    faces.append(img)
                    ids.append(idx)

                    # 2. Horizontal flip
                    flipped = cv2.flip(img, 1)
                    faces.append(flipped)
                    ids.append(idx)

                    # 3–8. Brightness shifts
                    for delta in (-50, -25, -10, 10, 25, 50):
                        shifted = np.clip(img.astype(np.int16) + delta, 0, 255).astype(np.uint8)
                        faces.append(shifted)
                        ids.append(idx)

                    # 9–12. Rotations (±5°, ±10° — simulate head tilt)
                    h_i, w_i = img.shape
                    cx, cy = w_i // 2, h_i // 2
                    for angle in (-10, -5, 5, 10):
                        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
                        rotated = cv2.warpAffine(img, M, (w_i, h_i),
                                                  borderMode=cv2.BORDER_REPLICATE)
                        faces.append(rotated)
                        ids.append(idx)

                    # 13. Slight Gaussian blur (camera focus)
                    faces.append(cv2.GaussianBlur(img, (3, 3), 0))
                    ids.append(idx)

                    # 14. Stronger blur
                    faces.append(cv2.GaussianBlur(img, (5, 5), 0))
                    ids.append(idx)

                    # 15–16. Contrast scaling
                    for alpha in (0.75, 1.3):
                        contrasted = np.clip(img.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
                        faces.append(contrasted)
                        ids.append(idx)

                    # 17–18. Gamma correction (simulate over/under exposure)
                    for gamma in (0.6, 1.6):
                        inv_gamma = 1.0 / gamma
                        table = np.array([(v / 255.0) ** inv_gamma * 255 for v in range(256)], dtype=np.uint8)
                        faces.append(cv2.LUT(img, table))
                        ids.append(idx)

                    # 19. Gaussian noise
                    noise = np.random.normal(0, 12, img.shape).astype(np.int16)
                    noisy = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
                    faces.append(noisy)
                    ids.append(idx)

                    # 20. Erosion (thinner features — simulate distance)
                    kernel = np.ones((2, 2), np.uint8)
                    faces.append(cv2.erode(img, kernel, iterations=1))
                    ids.append(idx)

                    # 21. Dilation
                    faces.append(cv2.dilate(img, kernel, iterations=1))
                    ids.append(idx)

                    # 22. Flip + brightness shift combined
                    flipped_bright = np.clip(flipped.astype(np.int16) + 20, 0, 255).astype(np.uint8)
                    faces.append(flipped_bright)
                    ids.append(idx)

        if len(faces) == 0:
            if os.path.exists(TRAINER_FILE):
                try:
                    os.remove(TRAINER_FILE)
                except Exception:
                    pass
            return False, "No student face images found in dataset."

        recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=2, neighbors=8, grid_x=8, grid_y=8
        )
        recognizer.train(faces, np.array(ids))
        os.makedirs(TRAINER_DIR, exist_ok=True)
        recognizer.save(TRAINER_FILE)
        num_students = len(folders)
        raw_images   = len(faces) // 7  # approx original count
        print(f"[AUTO-TRAIN] Trained with {len(faces)} samples ({raw_images} raw + augmented) "
              f"from {num_students} student(s).")
        return True, f"Model trained with {len(faces)} samples from {num_students} student(s)."
    except Exception as e:
        return False, str(e)


def robust_rmtree(path, max_retries=5, delay=0.2):
    """
    Robustly removes a directory, handling read-only files and retrying on Windows lock issues.
    """
    import shutil
    import stat
    import time

    if not os.path.exists(path):
        return True

    def remove_readonly(func, file_path, excinfo):
        try:
            os.chmod(file_path, stat.S_IWRITE)
            func(file_path)
        except Exception:
            pass

    for i in range(max_retries):
        try:
            # Change permissions of all files to writable first
            for root, dirs, files in os.walk(path):
                for file in files:
                    try:
                        os.chmod(os.path.join(root, file), stat.S_IWRITE)
                    except Exception:
                        pass
                for dir in dirs:
                    try:
                        os.chmod(os.path.join(root, dir), stat.S_IWRITE)
                    except Exception:
                        pass
            shutil.rmtree(path, onerror=remove_readonly)
            if not os.path.exists(path):
                return True
        except Exception as e:
            print(f"[ROBUST RM] Attempt {i+1} failed to delete {path}: {e}")
            time.sleep(delay)

    # Final force attempt using file-by-file deletion if still exists
    if os.path.exists(path):
        try:
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.chmod(file_path, stat.S_IWRITE)
                        os.remove(file_path)
                    except Exception:
                        pass
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    try:
                        shutil.rmtree(dir_path, onerror=remove_readonly)
                    except Exception:
                        pass
            shutil.rmtree(path, onerror=remove_readonly)
        except Exception as e:
            print(f"[ROBUST RM] Force delete fallback failed for {path}: {e}")

    return not os.path.exists(path)


def cleanup_deleted_student_folders():
    """
    Scans the DATASET_DIR and removes any folders that do not belong to active students in the database.
    This prevents orphan/deleted face records from remaining in the dataset or causing false duplicate matches.
    """
    try:
        if not os.path.exists(DATASET_DIR):
            return
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT student_id, department FROM students")
        students = cursor.fetchall()
        cursor.close()
        db.close()
        
        active_folders = set()
        for s in students:
            sid = s["student_id"]
            dept = s["department"]
            v1 = sid.replace("/", "_")
            v2 = f"{sid}_{dept}".replace("/", "_").replace(" ", "_")
            active_folders.add(v1.lower())
            active_folders.add(v2.lower())
            
        for folder in os.listdir(DATASET_DIR):
            folder_path = os.path.join(DATASET_DIR, folder)
            if os.path.isdir(folder_path):
                if folder.lower() not in active_folders:
                    print(f"[CLEANUP] Removing deleted student folder: {folder}")
                    robust_rmtree(folder_path)
    except Exception as e:
        print(f"[CLEANUP] Error during orphan folders cleanup: {e}")


def extract_and_save_face(image_b64, student_folder_name, current_student_folder=None, registering_student_id=None):
    """
    Decode base64 image, detect exactly one face, apply CLAHE, save:
      - face_1.jpg  : pre-cropped 200x200 grayscale face (used for training)
      - preview.jpg : original color image for UI preview
    Returns (face_roi_gray, saved_face_path, saved_preview_path, error_message)
    On error: (None, None, None, error_string)
    """
    try:
        image_data = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes  = base64.b64decode(image_data)
        np_arr     = np.frombuffer(img_bytes, np.uint8)
        frame      = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, None, None, "Corrupted image or unsupported format."

        gray         = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        # More lenient detection for uploaded images
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))

        # Filter out small false positive detections (e.g. background details)
        if len(faces) > 0:
            largest_w = max(f[2] for f in faces)
            faces = [f for f in faces if f[2] >= largest_w * 0.6]

        if len(faces) == 0:
            return None, None, None, "No face detected. Please use a clear, front-facing photo."
        if len(faces) > 1:
            return None, None, None, "Multiple faces detected. Please ensure only one person is in the photo."

        x, y, w, h   = faces[0]
        face_gray    = preprocess_face(gray, x, y, w, h)

        # Duplicate check against existing dataset
        is_dup, dup_msg = check_duplicate_face(face_gray, registering_student_id=registering_student_id)
        if is_dup:
            return None, None, None, dup_msg

        # Save files
        student_path = os.path.join(DATASET_DIR, student_folder_name)
        os.makedirs(student_path, exist_ok=True)

        face_path    = os.path.join(student_path, "face_1.jpg")
        preview_path = os.path.join(student_path, "preview.jpg")

        cv2.imwrite(face_path,    face_gray)          # grayscale cropped — for training
        cv2.imwrite(preview_path, frame)              # original color — for UI preview

        return face_gray, face_path, preview_path, None
    except Exception as e:
        return None, None, None, str(e)


def check_duplicate_face(new_face_image, registering_student_id=None, threshold=45.0):
    """
    Checks if new_face_image matches any existing face in DATASET_DIR.
    If registering_student_id is provided, matching against that student's own face
    is allowed (i.e. it will not be flagged as a duplicate).
    """
    cleanup_deleted_student_folders()

    if not os.path.exists(DATASET_DIR):
        return False, None
        
    folders = sorted([f for f in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, f))])
    
    faces_list = []
    labels_list = []
    folder_mapping = {}
    
    current_label_id = 0
    for folder in folders:
        folder_path = os.path.join(DATASET_DIR, folder)
        has_images = False
        for img_name in sorted(os.listdir(folder_path)):
            # Only compare against pre-cropped face images, not color preview
            if not img_name.startswith("face_"):
                continue
            if not img_name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            img_path = os.path.join(folder_path, img_name)
            try:
                existing_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if existing_img is None:
                    continue
                existing_img = cv2.resize(existing_img, (200, 200))
                faces_list.append(existing_img)
                labels_list.append(current_label_id)
                has_images = True
            except Exception as e:
                print(f"Error loading image {img_name}: {e}")
        if has_images:
            folder_mapping[current_label_id] = folder
            current_label_id += 1

    if len(faces_list) > 0:
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=2, neighbors=8, grid_x=8, grid_y=8
            )
            recognizer.train(faces_list, np.array(labels_list))
            label, confidence = recognizer.predict(new_face_image)
            print(f"[DUPLICATE CHECK] Match confidence: {confidence:.2f} for folder: {folder_mapping.get(label)}")
            if confidence < threshold:
                matched_folder = folder_mapping.get(label)
                if matched_folder:
                    # --- Fast self-match check via folder name (no DB needed) ---
                    # Build all expected folder name variants for the registering student
                    if registering_student_id:
                        sid_clean = registering_student_id.replace("/", "_").replace(" ", "_")
                        # Fetch department from DB to build the v2 folder name
                        try:
                            db_tmp = get_db()
                            cur_tmp = db_tmp.cursor(dictionary=True)
                            cur_tmp.execute("SELECT department FROM students WHERE LOWER(student_id) = LOWER(%s) LIMIT 1", (registering_student_id,))
                            tmp_row = cur_tmp.fetchone()
                            cur_tmp.close()
                            db_tmp.close()
                            if tmp_row:
                                dept_clean = tmp_row['department'].replace("/", "_").replace(" ", "_")
                                sid_v2 = f"{sid_clean}_{dept_clean}"
                            else:
                                sid_v2 = sid_clean
                        except Exception:
                            sid_v2 = sid_clean
                        own_folders = {sid_clean.lower(), sid_v2.lower()}
                        if matched_folder.lower() in own_folders:
                            print(f"[DUPLICATE CHECK] Same student folder match. Allowing for {registering_student_id}.")
                            return False, None

                    # --- DB lookup to identify whose face matched ---
                    db = get_db()
                    cursor = db.cursor(dictionary=True)
                    clean_folder = matched_folder.replace("_", "/")
                    cursor.execute(
                        "SELECT student_id, full_name FROM students WHERE student_id = %s OR REPLACE(student_id, '/', '_') = %s OR CONCAT(REPLACE(student_id, '/', '_'), '_', REPLACE(department, ' ', '_')) = %s LIMIT 1",
                        (clean_folder, matched_folder, matched_folder)
                    )
                    row = cursor.fetchone()
                    cursor.close()
                    db.close()
                    if row:
                        matched_sid = row['student_id']
                        matched_name = row['full_name']
                        if registering_student_id and matched_sid.strip().lower() == registering_student_id.strip().lower():
                            print(f"[DUPLICATE CHECK] Same student face match. Allowing registration for {registering_student_id}.")
                            return False, None
                        return True, f"This face is already registered under student {matched_name} ({matched_sid})!"
                    return False, None
        except Exception as e:
            print(f"Error in duplicate face recognition: {e}")
            
    return False, None


def register_student_routes(app):
    @app.route("/student_management")
    def student_management():
        if "user" not in session:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()
        cursor.execute("SELECT * FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template(
            "student_management.html", students=students, courses=courses
        )

    @app.route("/add-student", methods=["POST"])
    def add_student():
        db = None
        cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            duplicate_found = False

            student_id = request.form.get("student_id")
            full_name = request.form.get("full_name")
            department = request.form.get("department")
            year = request.form.get("year")
            semester = request.form.get("semester")
            email = request.form.get("email", "")
            phone = request.form.get("phone", "")
            registered_date = request.form.get("registered_date")
            username = request.form.get("username")
            password = request.form.get("password")
            dob = request.form.get("dob")
            nic = request.form.get("nic", "")
            gender = request.form.get("gender", "")
            religion = request.form.get("religion", "")
            address = request.form.get("address", "")
            status = request.form.get("status", "Active")
            part_time_full_time = request.form.get("part_time_full_time", "Full Time")
            image = request.form.get("image")
            image_path = ""

            if not password:
                cursor.close()
                db.close()
                return jsonify(
                    {
                        "success": False,
                        "message": "Password is required!",
                    }
                )

            if not registered_date:
                registered_date = None
            if not dob:
                dob = None

            # Check if NIC already exists in students or lecturers
            if nic and nic.strip():
                cursor.execute("SELECT id FROM students WHERE nic = %s", (nic.strip(),))
                if cursor.fetchone():
                    cursor.close()
                    db.close()
                    return jsonify({"success": False, "message": "This NIC is already registered."})
                cursor.execute("SELECT id FROM lecturers WHERE nic = %s", (nic.strip(),))
                if cursor.fetchone():
                    cursor.close()
                    db.close()
                    return jsonify({"success": False, "message": "This NIC is already registered."})

            # Duplicate check - only block if same student ID exists in same department (case-insensitive)
            cursor.execute(
                "SELECT id, image FROM students WHERE LOWER(student_id) = LOWER(%s) AND LOWER(department) = LOWER(%s)",
                (student_id, department),
            )
            existing = cursor.fetchone()
            if existing:
                existing_image = existing.get("image", "") or ""
                if existing_image and os.path.exists(existing_image):
                    # Student already fully registered with a face - block
                    cursor.close()
                    db.close()
                    return jsonify(
                        {
                            "success": False,
                            "message": "A student with this ID already exists in this department!",
                        }
                    )
                else:
                    # Student record exists but has no face image - delete incomplete record and allow fresh registration
                    cursor.execute("DELETE FROM students WHERE id = %s", (existing["id"],))
                    db.commit()

            # Face capture / upload processing
            if image:
                if len(image) < 100:
                    cursor.close(); db.close()
                    return jsonify({"success": False, "message": "Image is empty or corrupted."})

                clean_sid = f"{student_id}_{department}".replace("/", "_").replace(" ", "_")
                _, face_path, preview_path, err = extract_and_save_face(
                    image, clean_sid, current_student_folder=clean_sid, registering_student_id=student_id
                )
                if err:
                    cursor.close(); db.close()
                    return jsonify({"success": False, "message": err})

                # Store the preview (color) path in DB so the UI can display it
                image_path = preview_path

            # Save student record to database
            cursor.execute(
                """
                INSERT INTO students
                    (student_id, full_name, department, year, semester, username, password,
                     email, phone, image, registered_date, dob, nic, gender, religion, address, status, part_time_full_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    student_id,
                    full_name,
                    department,
                    year,
                    semester,
                    username,
                    password,
                    email,
                    phone,
                    image_path,
                    registered_date,
                    dob,
                    nic,
                    gender,
                    religion,
                    address,
                    status,
                    part_time_full_time,
                ),
            )
            db.commit()
            cursor.close()
            db.close()
            
            success, msg = auto_train_model()
            if not success:
                return jsonify({"success": False, "message": f"Student registered, but training failed: {msg}"})
            return jsonify({"success": True, "message": "Student registered successfully!"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            if cursor:
                try: cursor.close()
                except Exception: pass
            if db:
                try: db.close()
                except Exception: pass
            err_msg = str(e)
            if "Duplicate entry" in err_msg and "username" in err_msg:
                return jsonify({"success": False, "message": "Username already exists!"})
            if "Duplicate entry" in err_msg and "student_id" in err_msg:
                return jsonify({"success": False, "message": "Student ID already exists!"})
            return jsonify({"success": False, "message": f"Registration failed: {err_msg}"})

    @app.route("/api/train_model", methods=["POST"])
    def api_train_model():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        success, msg = auto_train_model()
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg})

    @app.route("/api/detect-face", methods=["POST"])
    def api_detect_face():
        data = request.get_json() or {}
        image_b64 = data.get("image")
        if not image_b64:
            return jsonify({"success": False, "message": "No image provided."})
        
        try:
            image_data = image_b64.split(",")[1]
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                return jsonify({"success": False, "message": "Invalid image data."})
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
            
            # Filter out small false positive detections (e.g. background details)
            if len(faces) > 0:
                largest_w = max(f[2] for f in faces)
                faces = [f for f in faces if f[2] >= largest_w * 0.6]

            if len(faces) == 0:
                return jsonify({
                    "success": False,
                    "faces_count": 0,
                    "message": "No face detected. Please upload a clear front-facing photo."
                })
            elif len(faces) > 1:
                return jsonify({
                    "success": False,
                    "faces_count": len(faces),
                    "message": "Multiple faces detected. Please ensure only one person is in the photo."
                })
            else:
                return jsonify({
                    "success": True,
                    "faces_count": 1,
                    "message": "Face detected successfully!"
                })
        except Exception as e:
            return jsonify({"success": False, "message": f"Error processing image: {str(e)}"})

    @app.route("/student/profile-pic")
    def student_profile_pic_logged_in():
        if "student_id" not in session:
            return send_from_directory(os.path.join(app.static_folder, "images"), "WhatsApp Image 2026-05-22 at 7.16.37 PM.jpeg")
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT image FROM students WHERE id = %s", (session["student_id"],))
        student = cursor.fetchone()
        cursor.close()
        db.close()
        if student and student.get("image"):
            img_path = student["image"]
            if os.path.exists(img_path):
                return send_from_directory(os.path.dirname(img_path), os.path.basename(img_path))
        return send_from_directory(os.path.join(app.static_folder, "images"), "WhatsApp Image 2026-05-22 at 7.16.37 PM.jpeg")

    @app.route("/edit/<int:id>")
    def edit_student(id):
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
        student = cursor.fetchone()
        cursor.close()
        db.close()

        if student:
            # Convert date/datetime objects to strings so jsonify works correctly
            for date_field in ("registered_date", "dob", "created_at"):
                if student.get(date_field) and hasattr(
                    student[date_field], "isoformat"
                ):
                    student[date_field] = student[date_field].isoformat()

            # Read the saved face image and send as base64 so preview works on all platforms
            # Prefer preview.jpg (color) over face_1.jpg (grayscale ROI used for training)
            image_path = student.get("image", "") or ""
            student["face_base64"] = None

            def resolve_path(p):
                """Resolve a path to absolute, always anchored to BASE_DIR if relative."""
                if not p:
                    return None
                if os.path.isabs(p) and os.path.exists(p):
                    return p
                # Try as-is relative to BASE_DIR
                candidate = os.path.join(BASE_DIR, p)
                if os.path.exists(candidate):
                    return candidate
                # Try just the filename inside BASE_DIR
                candidate2 = os.path.join(BASE_DIR, os.path.basename(p))
                if os.path.exists(candidate2):
                    return candidate2
                return None

            found_path = None

            if image_path:
                # 1. Try sibling preview.jpg (handles face_1.jpg stored in DB)
                dir_part = os.path.dirname(image_path)
                if dir_part:
                    preview_sibling = os.path.join(dir_part, "preview.jpg")
                    found_path = resolve_path(preview_sibling)

                # 2. Try the stored path itself
                if not found_path:
                    found_path = resolve_path(image_path)

            # 3. Last resort: scan dataset folder for this student's preview.jpg
            if not found_path and DATASET_DIR and os.path.exists(DATASET_DIR):
                sid_raw = student.get("student_id", "")
                dept_raw = student.get("department", "")
                if sid_raw:
                    sid_clean_v2 = f"{sid_raw}_{dept_raw}".replace("/", "_").replace(" ", "_")
                    sid_clean_v1 = sid_raw.replace("/", "_")
                    for variant in [sid_clean_v2, sid_clean_v1]:
                        candidate = os.path.join(DATASET_DIR, variant, "preview.jpg")
                        if os.path.exists(candidate):
                            found_path = candidate
                            break
                        candidate_face = os.path.join(DATASET_DIR, variant, "face_1.jpg")
                        if os.path.exists(candidate_face):
                            found_path = candidate_face
                            break

            if found_path:
                try:
                    with open(found_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                        ext = "jpeg" if found_path.lower().endswith(".jpg") or found_path.lower().endswith(".jpeg") else "png"
                        student["face_base64"] = f"data:image/{ext};base64,{encoded}"
                except Exception as img_err:
                    print(f"[EDIT] Could not read face image {found_path}: {img_err}")

        response = jsonify(student)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/update-student", methods=["POST"])
    def update_student():
        import shutil

        db = get_db()
        cursor = db.cursor(dictionary=True)

        id = request.form.get("id")
        student_id = request.form.get("student_id")
        full_name = request.form.get("full_name")
        department = request.form.get("department")
        year = request.form.get("year")
        semester = request.form.get("semester")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        registered_date = request.form.get("registered_date")
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        dob = request.form.get("dob")
        nic = request.form.get("nic", "")
        gender = request.form.get("gender", "")
        religion = request.form.get("religion", "")
        address = request.form.get("address", "")
        status = request.form.get("status", "Active")
        part_time_full_time = request.form.get("part_time_full_time", "Full Time")
        new_image = request.form.get("image")

        if not registered_date:
            registered_date = None
        if not dob:
            dob = None

        # Check if NIC already exists in students or lecturers (excluding current student)
        if nic and nic.strip():
            cursor.execute("SELECT id FROM students WHERE nic = %s AND id != %s", (nic.strip(), id))
            if cursor.fetchone():
                cursor.close()
                db.close()
                return jsonify({"success": False, "message": "This NIC is already registered."})
            cursor.execute("SELECT id FROM lecturers WHERE nic = %s", (nic.strip(),))
            if cursor.fetchone():
                cursor.close()
                db.close()
                return jsonify({"success": False, "message": "This NIC is already registered."})

        cursor.execute(
            "SELECT student_id, department, image, password FROM students WHERE id=%s",
            (id,),
        )
        existing = cursor.fetchone()
        old_student_id = existing["student_id"] if existing else student_id
        old_department = existing["department"] if existing else department
        old_image_path = existing["image"] if existing else ""
        old_password = existing["password"] if existing else ""


        if not password:
            password = old_password

        clean_old_sid_v1 = old_student_id.replace("/", "_")
        clean_old_sid_v2 = f"{old_student_id}_{old_department}".replace(
            "/", "_"
        ).replace(" ", "_")

        clean_new_sid = f"{student_id}_{department}".replace("/", "_").replace(" ", "_")

        image_path = old_image_path

        if new_image:
            _, face_path, preview_path, err = extract_and_save_face(
                new_image, clean_new_sid, current_student_folder=clean_old_sid_v2, registering_student_id=student_id
            )
            if err:
                cursor.close(); db.close()
                return jsonify({"success": False, "message": err})
            image_path = preview_path

        old_folder = None
        if os.path.exists(os.path.join(DATASET_DIR, clean_old_sid_v2)):
            old_folder = os.path.join(DATASET_DIR, clean_old_sid_v2)
        elif os.path.exists(os.path.join(DATASET_DIR, clean_old_sid_v1)):
            old_folder = os.path.join(DATASET_DIR, clean_old_sid_v1)

        new_folder = os.path.join(DATASET_DIR, clean_new_sid)

        if old_folder and old_folder != new_folder:
            if new_image:
                robust_rmtree(old_folder)
                print(f"Old dataset folder removed: {old_folder}")
            else:
                try:
                    shutil.move(old_folder, new_folder)
                    if image_path:
                        image_path = image_path.replace(
                            old_folder.replace("\\", "/"), new_folder.replace("\\", "/")
                        )
                        image_path = image_path.replace(old_folder, new_folder)
                    print(f"Dataset folder renamed: {old_folder} → {new_folder}")
                except Exception as e:
                    print(f"Warning: Could not rename dataset folder: {e}")

        try:
            cursor2 = db.cursor()
            sql = """
            UPDATE students
            SET student_id=%s, full_name=%s, department=%s, year=%s, semester=%s,
                email=%s, phone=%s, image=%s, registered_date=%s, username=%s, password=%s,
                dob=%s, nic=%s, gender=%s, religion=%s, address=%s, status=%s, part_time_full_time=%s
            WHERE id=%s
            """
            cursor2.execute(
                sql,
                (
                    student_id,
                    full_name,
                    department,
                    year,
                    semester,
                    email,
                    phone,
                    image_path,
                    registered_date,
                    username,
                    password,
                    dob,
                    nic,
                    gender,
                    religion,
                    address,
                    status,
                    part_time_full_time,
                    id,
                ),
            )
            db.commit()
            cursor2.close()
            cursor.close()
            db.close()
        except Exception as db_err:
            print("DB Update Error:", db_err)
            try:
                cursor.close()
                db.close()
            except Exception:
                pass
            err_msg = str(db_err)
            if "Duplicate entry" in err_msg and "username" in err_msg:
                return jsonify(
                    {
                        "success": False,
                        "message": "This username is already taken. Please choose a different username.",
                    }
                )
            elif "Duplicate entry" in err_msg:
                return jsonify(
                    {
                        "success": False,
                        "message": "Duplicate entry detected. Please check Student ID or username.",
                    }
                )
            else:
                return jsonify(
                    {"success": False, "message": f"Database error: {err_msg}"}
                )

        # Auto retrain after update
        face_warning = None
        success, msg = auto_train_model()
        if not success:
            print(f"[AUTO-TRAIN] Warning after update: {msg}")

        if "face_warning" in locals() and face_warning:
            return jsonify({"success": True, "message": face_warning})

        return jsonify(
            {
                "success": True,
                "message": "Student details updated and model retrained successfully!",
            }
        )

    @app.route("/delete-student/<string:id_list>", methods=["POST"])
    def delete_student(id_list):
        import shutil

        try:
            ids = [int(x) for x in id_list.split(",") if x.strip().isdigit()]
        except ValueError:
            return jsonify({"success": False, "message": "Invalid student ID list!"})

        if not ids:
            return jsonify({"success": False, "message": "No student IDs provided!"})

        db = get_db()
        cursor = db.cursor(dictionary=True)

        deleted_folders = []

        for id in ids:
            cursor.execute("SELECT student_id, department FROM students WHERE id=%s", (id,))
            student = cursor.fetchone()
            if student:
                student_id = student["student_id"]
                department = student["department"]
                clean_sid_v1 = student_id.replace("/", "_")
                clean_sid_v2 = f"{student_id}_{department}".replace("/", "_").replace(" ", "_")

                dataset_folder = None
                if os.path.exists(os.path.join(DATASET_DIR, clean_sid_v2)):
                    dataset_folder = os.path.join(DATASET_DIR, clean_sid_v2)
                elif os.path.exists(os.path.join(DATASET_DIR, clean_sid_v1)):
                    dataset_folder = os.path.join(DATASET_DIR, clean_sid_v1)

                if dataset_folder:
                    deleted_folders.append(dataset_folder)

                cursor.execute("DELETE FROM students WHERE id=%s", (id,))

        db.commit()
        cursor.close()
        db.close()

        for folder in deleted_folders:
            if os.path.exists(folder):
                robust_rmtree(folder)
                print(f"Deleted dataset folder: {folder}")

        # Auto retrain (or remove model if no students left)
        try:
            remaining = [f for f in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, f))]
            if remaining:
                auto_train_model()
            else:
                if os.path.exists(TRAINER_FILE):
                    os.remove(TRAINER_FILE)
                    print("[DELETE] No students remaining — trainer file removed.")
        except Exception as e:
            print(f"[DELETE] Retrain warning: {e}")

        return jsonify({"success": True})

    @app.route("/dataset/<path:filename>")
    def serve_dataset(filename):
        dataset_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dataset"
        )
        return send_from_directory(dataset_folder, filename)
