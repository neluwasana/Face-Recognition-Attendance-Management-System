import datetime
from flask import render_template, redirect, session, url_for, flash, request
from db import get_db

def register_student_view_routes(app):

    def get_logged_in_student():
        if "student_id" not in session:
            return None
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id = %s", (session["student_id"],))
        student = cursor.fetchone()
        cursor.close()
        db.close()
        return student

    @app.route("/student/dashboard")
    def student_dashboard():
        student = get_logged_in_student()
        if not student:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        return render_template("student_dashboard.html", student=student)

    @app.route("/student/details")
    def student_details():
        student = get_logged_in_student()
        if not student:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        return render_template("student_details.html", student=student)

    @app.route("/student/timetable")
    def student_timetable():
        student = get_logged_in_student()
        if not student:
            flash("Please login first!", "error")
            return redirect(url_for("home"))

        # Show only selected date's session for the student's own class
        selected_date_str = request.args.get("date", "").strip()
        if selected_date_str:
            try:
                selected_date = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.date.today()
        else:
            selected_date = datetime.date.today()

        day_name = selected_date.strftime("%A")
        dept  = (student.get("department") or "").strip()
        year  = (student.get("year") or "").strip()
        sem   = (student.get("semester") or "").strip()
        mode  = (student.get("part_time_full_time") or "Full Time").strip()

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Fetch only timetable rows matching course, year, semester, mode, and date
        cursor.execute("""
            SELECT
                t.id,
                t.course,
                t.year,
                t.semester,
                t.part_time_full_time,
                s.subject_name,
                l.lecturer_name,
                t.location,
                t.lecture_date,
                t.start_time,
                t.end_time,
                t.is_cancelled,
                t.cancel_reason,
                t.day,
                t.time_slot
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            JOIN lecturers l ON t.lecturer_id = l.id
            WHERE TRIM(t.course) = %s
              AND TRIM(t.year) = %s
              AND TRIM(t.semester) = %s
              AND TRIM(t.part_time_full_time) = %s
              AND (
                  (t.lecture_date = %s)
                  OR
                  (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
              )
            ORDER BY t.start_time ASC
        """, (dept, year, sem, mode, selected_date, day_name, selected_date, selected_date))
        timetable_entries = cursor.fetchall()
        cursor.close()
        db.close()

        # Convert timedelta to HH:MM strings
        for entry in timetable_entries:
            if isinstance(entry.get("lecture_date"), datetime.date):
                entry["lecture_date"] = entry["lecture_date"].strftime("%Y-%m-%d")
            for field in ("start_time", "end_time"):
                val = entry.get(field)
                if isinstance(val, datetime.timedelta):
                    total_seconds = int(val.total_seconds())
                    h, m = divmod(total_seconds // 60, 60)
                    entry[field] = f"{h:02d}:{m:02d}"

        return render_template(
            "student_timetable.html",
            student=student,
            timetable_entries=timetable_entries,
            selected_date=selected_date.strftime("%Y-%m-%d"),
            today=selected_date.strftime("%A, %d %B %Y")
        )

    @app.route("/student/attendance")
    def student_attendance():
        student = get_logged_in_student()
        if not student:
            flash("Please login first!", "error")
            return redirect(url_for("home"))

        student_mode = (student.get("part_time_full_time") or "Full Time").strip()
        dept = student["department"].strip()
        year = student["year"].strip()
        sem  = student["semester"].strip()
        today = datetime.date.today()

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # 1. Fetch attendance records for this student
        cursor.execute("""
            SELECT a.*
            FROM attendance a
            WHERE a.student_id = %s
            ORDER BY a.date DESC, a.time DESC
        """, (student["student_id"],))
        records = cursor.fetchall()

        # 2. Fetch subjects of the student's current semester
        cursor.execute("""
            SELECT s.id, s.subject_code, s.subject_name
            FROM subjects s
            JOIN courses c ON s.course_id = c.id
            WHERE TRIM(c.course_code) = %s
              AND TRIM(s.year) = %s
              AND TRIM(s.semester) = %s
        """, (dept, year, sem))
        subjects = cursor.fetchall()

        # 3. Count total lectures conducted per subject.
        #    Each timetable row has its own lecture_date (one row per week),
        #    so we simply count rows where lecture_date <= today.
        conducted_counts = {}
        for s in subjects:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM timetable t
                WHERE t.subject_id = %s
                  AND TRIM(t.course) = %s
                  AND TRIM(t.part_time_full_time) = %s
                  AND TRIM(t.year) = %s
                  AND TRIM(t.semester) = %s
                  AND (t.is_cancelled IS NULL OR t.is_cancelled = 0)
                  AND t.lecture_date <= %s
            """, (s["id"], dept, student_mode, year, sem, today))
            row = cursor.fetchone()
            conducted_counts[s["id"]] = row["cnt"] if row else 0

        cursor.close()
        db.close()

        # Format date/time strings for history display
        for r in records:
            r["date"] = str(r["date"])
            r["time"] = str(r["time"])

        # 4. Count attended lectures per subject by matching lecture_name
        attended_counts = {}
        for s in subjects:
            sub_id   = s["id"]
            sub_code = (s["subject_code"] or "").strip().lower()
            sub_name = (s["subject_name"] or "").strip().lower()
            attended_counts[sub_id] = 0
            for r in records:
                r_name = (r["lecture_name"] or "").strip().lower()
                if sub_code in r_name or sub_name in r_name:
                    attended_counts[sub_id] += 1

        # 5. Build subject stats
        subject_stats = []
        for s in subjects:
            sub_id         = s["id"]
            total_conducted = conducted_counts.get(sub_id, 0)
            attended        = attended_counts.get(sub_id, 0)
            percentage      = round((attended / total_conducted) * 100, 2) if total_conducted > 0 else 0.0
            subject_stats.append({
                "subject_name":    s["subject_name"],
                "total_conducted": total_conducted,
                "attended_count":  attended,
                "percentage":      percentage
            })

        return render_template(
            "student_attendance.html",
            student=student,
            records=records,
            subject_stats=subject_stats
        )
