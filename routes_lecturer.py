import datetime
from flask import render_template, redirect, flash, session, url_for, request
from db import get_db


#  SHARED HELPER 
def _get_lecturer_or_redirect():
    """Fetch and enrich lecturer from session. Returns lecturer dict or None."""
    if "lecturer_id" not in session or session.get("role") != "lecturer":
        return None

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM lecturers WHERE id = %s", (session["lecturer_id"],))
    lecturer = cursor.fetchone()
    cursor.close()
    db.close()

    if lecturer:
        raw_name = lecturer["lecturer_name"]
        normalized_name = raw_name.replace(".", " ")
        name_parts = normalized_name.split()
        
        clean_parts = []
        for part in name_parts:
            p_lower = part.lower()
            if p_lower in ('mr', 'mrs', 'miss', 'ms'):
                continue
            clean_parts.append(part)
        
        full_words = [p for p in clean_parts if len(p) > 1]
        
        initials = "L"
        if len(full_words) >= 2:
            first_name = full_words[0]
            last_name = full_words[-1]
            initials = first_name[0].upper() + last_name[0].upper()
        elif len(full_words) == 1:
            surname = full_words[0]
            prev_initials = []
            for p in clean_parts:
                if p == surname:
                    break
                if len(p) == 1:
                    prev_initials.append(p)
            if prev_initials:
                initials = prev_initials[-1][0].upper() + surname[0].upper()
            else:
                initials = surname[0].upper()
        elif len(clean_parts) >= 2:
            initials = clean_parts[0][0].upper() + clean_parts[-1][0].upper()
        elif len(clean_parts) == 1:
            initials = clean_parts[0][0].upper()
            
        lecturer["initials"] = initials

    return lecturer


def _format_entries(entries):
    """Convert timedelta / date objects to display strings in-place and calculate status."""
    import datetime as dt_module
    now = dt_module.datetime.now()
    for entry in entries:
        orig_date = entry.get("lecture_date")
        orig_end = entry.get("end_time")

        if isinstance(entry.get("lecture_date"), dt_module.date):
            wday = entry["lecture_date"].strftime("%A")
            entry["lecture_date"] = f"{wday}, {entry['lecture_date'].strftime('%Y-%m-%d')}"
        if isinstance(entry.get("semester_start_date"), dt_module.date):
            entry["semester_start_date"] = entry["semester_start_date"].strftime("%Y-%m-%d")
        if isinstance(entry.get("semester_end_date"), dt_module.date):
            entry["semester_end_date"] = entry["semester_end_date"].strftime("%Y-%m-%d")
        for field in ("start_time", "end_time"):
            val = entry.get(field)
            if isinstance(val, dt_module.timedelta):
                total_seconds = int(val.total_seconds())
                h, m = divmod(total_seconds // 60, 60)
                entry[field] = f"{h:02d}:{m:02d}"

        # Status calculation
        if entry.get("is_cancelled"):
            entry["status"] = "Cancelled"
        elif entry.get("day"):
            # Weekly recurring lecture — no specific date, always show as Upcoming
            entry["status"] = "Upcoming"
        else:
            # One-time lecture — calculate based on actual date and end time
            if isinstance(orig_date, dt_module.date):
                lecture_date_val = orig_date
            elif isinstance(entry.get("lecture_date"), str):
                try:
                    lecture_date_val = dt_module.datetime.strptime(entry["lecture_date"], "%Y-%m-%d").date()
                except Exception:
                    lecture_date_val = dt_module.date.today()
            else:
                lecture_date_val = dt_module.date.today()

            if isinstance(orig_end, dt_module.timedelta):
                lecture_end_time = (dt_module.datetime.min + orig_end).time()
            elif isinstance(entry.get("end_time"), str):
                try:
                    lecture_end_time = dt_module.datetime.strptime(entry["end_time"], "%H:%M").time()
                except Exception:
                    lecture_end_time = dt_module.time(23, 59)
            else:
                lecture_end_time = dt_module.time(23, 59)

            lecture_datetime = dt_module.datetime.combine(lecture_date_val, lecture_end_time)
            entry["status"] = "Completed" if now > lecture_datetime else "Upcoming"


def _get_subjects_and_lecturers(cursor):
    """Return (courses, subjects, lecturers) lists from the DB."""
    cursor.execute("SELECT * FROM courses ORDER BY course_code")
    courses = cursor.fetchall()

    cursor.execute("""
        SELECT s.*, c.course_code, c.course_name, l.lecturer_name
        FROM subjects s
        JOIN courses c ON s.course_id = c.id
        JOIN lecturers l ON s.lecturer_id = l.id
        ORDER BY c.course_code, s.subject_code
    """)
    subjects = cursor.fetchall()

    cursor.execute("SELECT * FROM lecturers ORDER BY lecturer_name")
    lecturers = cursor.fetchall()

    return courses, subjects, lecturers


#ROUTES
def register_lecturer_routes(app):

    #1. Dashboard
    @app.route("/lecturer/dashboard")
    def lecturer_dashboard():
        lecturer = _get_lecturer_or_redirect()
        if not lecturer:
            flash("Access denied! Please log in as a lecturer.", "error")
            return redirect(url_for("home"))

        db = get_db()
        cursor = db.cursor(dictionary=True)
        today = datetime.date.today()
        day_name = today.strftime("%A")
        
        # Get all scheduled sessions for this lecturer today
        cursor.execute("""
            SELECT t.*, s.subject_code, s.subject_name
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            WHERE t.lecturer_id = %s
              AND (t.is_cancelled IS NULL OR t.is_cancelled = 0 OR t.is_cancelled = '0')
              AND (
                  ((t.day IS NULL OR t.day = '') AND t.lecture_date = %s)
                  OR
                  (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
              )
            ORDER BY t.start_time ASC
        """, (lecturer["id"], today, day_name, today, today))
        sessions = cursor.fetchall()
        cursor.close()
        db.close()

        import datetime as dt_module
        now = dt_module.datetime.now()
        current_time = now.time()
        
        today_session = None
        if sessions:
            # Check if there is a currently active session
            for s in sessions:
                start_val = s["start_time"]
                end_val = s["end_time"]
                
                if isinstance(start_val, dt_module.timedelta):
                    start_time = (dt_module.datetime.min + start_val).time()
                else:
                    start_time = start_val
                    
                if isinstance(end_val, dt_module.timedelta):
                    end_time = (dt_module.datetime.min + end_val).time()
                else:
                    end_time = end_val
                
                if start_time <= current_time <= end_time:
                    today_session = s
                    break
            
            # If no active session, find the first upcoming session today
            if not today_session:
                for s in sessions:
                    start_val = s["start_time"]
                    if isinstance(start_val, dt_module.timedelta):
                        start_time = (dt_module.datetime.min + start_val).time()
                    else:
                        start_time = start_val
                        
                    if start_time > current_time:
                        today_session = s
                        break
            
            # If still not found, just use the first session of today
            if not today_session:
                today_session = sessions[0]

        # Format today_session details
        today_session_data = None
        if today_session:
            start_val = today_session["start_time"]
            end_val = today_session["end_time"]
            if isinstance(start_val, dt_module.timedelta):
                sh, sm = divmod(int(start_val.total_seconds()) // 60, 60)
                start_str = f"{sh:02d}:{sm:02d}"
            else:
                start_str = start_val.strftime("%H:%M") if hasattr(start_val, "strftime") else str(start_val)[:5]
                
            if isinstance(end_val, dt_module.timedelta):
                eh, em = divmod(int(end_val.total_seconds()) // 60, 60)
                end_str = f"{eh:02d}:{em:02d}"
            else:
                end_str = end_val.strftime("%H:%M") if hasattr(end_val, "strftime") else str(end_val)[:5]
            
            today_session_data = {
                "date": today.strftime("%Y-%m-%d"),
                "time": f"{start_str} - {end_str}",
                "subject": f"{today_session['subject_code']} - {today_session['subject_name']}",
                "year": today_session["year"],
                "semester": today_session["semester"],
                "mode": today_session["part_time_full_time"]
            }

        return render_template("lecturer_dashboard.html", lecturer=lecturer, today_session=today_session_data)


    # 2. Profile 
    @app.route("/lecturer/profile")
    def lecturer_profile():
        lecturer = _get_lecturer_or_redirect()
        if not lecturer:
            flash("Access denied! Please log in as a lecturer.", "error")
            return redirect(url_for("home"))

        return render_template("lecturer_profile.html", lecturer=lecturer)


    #  3. Timetable (one-time additional lectures) 
    @app.route("/lecturer/timetable")
    def lecturer_timetable():
        lecturer = _get_lecturer_or_redirect()
        if not lecturer:
            flash("Access denied! Please log in as a lecturer.", "error")
            return redirect(url_for("home"))

        selected_date_str = request.args.get("date", "").strip()
        if selected_date_str:
            try:
                selected_date = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.date.today()
        else:
            selected_date = datetime.date.today()

        day_name = selected_date.strftime("%A")

        db = get_db()
        cursor = db.cursor(dictionary=True)
        courses, subjects, lecturers = _get_subjects_and_lecturers(cursor)

        # Fetch only selected date's timetable entries for this lecturer
        cursor.execute("""
            SELECT
                t.id, t.course, t.year, t.semester, t.part_time_full_time,
                t.day, t.time_slot, t.semester_start_date, t.semester_end_date,
                t.lecture_date, t.location, t.start_time, t.end_time,
                t.attendance_mark_time, t.is_cancelled, t.cancel_reason,
                t.subject_id, t.lecturer_id,
                s.subject_name, l.lecturer_name
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            JOIN lecturers l ON t.lecturer_id = l.id
            WHERE t.lecturer_id = %s
              AND (
                  (t.lecture_date = %s)
                  OR
                  (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
              )
            ORDER BY t.start_time ASC
        """, (session["lecturer_id"], selected_date, day_name, selected_date, selected_date))
        timetable_entries = cursor.fetchall()

        cursor.close()
        db.close()
        _format_entries(timetable_entries)

        return render_template(
            "lecturer_timetable.html",
            lecturer=lecturer,
            timetable_entries=timetable_entries,
            subjects=subjects,
            lecturers=lecturers,
            courses=courses,
            selected_date=selected_date.strftime("%Y-%m-%d"),
            today=selected_date.strftime("%A, %d %B %Y")
        )





    #  5. Mark Attendance
    @app.route("/lecturer/mark_attendance")
    def lecturer_mark_attendance():
        lecturer = _get_lecturer_or_redirect()
        if not lecturer:
            flash("Access denied! Please log in as a lecturer.", "error")
            return redirect(url_for("home"))

        return render_template("lecturer_mark_attendance.html", lecturer=lecturer)


    # 6. Reports 
    @app.route("/lecturer/reports")
    def lecturer_reports():
        lecturer = _get_lecturer_or_redirect()
        if not lecturer:
            flash("Access denied! Please log in as a lecturer.", "error")
            return redirect(url_for("home"))

        return render_template("lecturer_reports.html", lecturer=lecturer)
