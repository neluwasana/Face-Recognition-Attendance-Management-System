import datetime
import json
from flask import render_template, jsonify, request, redirect
from db import get_db

def save_semester_and_weeks(db, department, year, semester, start_date, end_date):
    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    
    # Generate 15 weeks
    weeks_list = []
    for w in range(1, 16):
        w_start = start_dt + datetime.timedelta(days=(w - 1) * 7)
        w_end = w_start + datetime.timedelta(days=6)
        weeks_list.append({
            "week_number": w,
            "start_date": w_start.strftime("%Y-%m-%d"),
            "end_date": w_end.strftime("%Y-%m-%d")
        })
    weeks_json = json.dumps(weeks_list)
    
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO semesters (department, year, semester, start_date, end_date, weeks)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            start_date = VALUES(start_date),
            end_date = VALUES(end_date),
            weeks = VALUES(weeks)
    """, (department, year, semester, start_date, end_date, weeks_json))
    cursor.close()

def register_timetabel_routes(app):

  
    # TIME TABLE PAGE
  
    @app.route("/time_tabel")
    def time_tabel():
        course = request.args.get("course", "").strip()
        year = request.args.get("year", "").strip()
        semester = request.args.get("semester", "").strip()
        study_mode = request.args.get("study_mode", "").strip()
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

        # subjects
        cursor.execute("SELECT id, subject_name FROM subjects")
        subjects = cursor.fetchall()

        # lecturers
        cursor.execute("SELECT id, lecturer_name FROM lecturers")
        lecturers = cursor.fetchall()

        timetable_entries = []
        if course and year and semester:
            # Build optional study_mode filter
            sm_clause = "AND t.part_time_full_time = %s" if study_mode else ""
            params = [course, year, semester, selected_date, day_name, selected_date, selected_date]
            if study_mode:
                params.insert(3, study_mode)   # inject after semester in WHERE order

            cursor.execute(f"""
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
                    t.attendance_mark_time,
                    t.is_cancelled,
                    t.cancel_reason,
                    t.day,
                    t.time_slot,
                    t.semester_start_date,
                    t.semester_end_date
                FROM timetable t
                JOIN subjects s ON t.subject_id = s.id
                JOIN lecturers l ON t.lecturer_id = l.id
                WHERE t.course = %s
                  AND t.year = %s
                  AND t.semester = %s
                  {sm_clause}
                  AND (
                      (t.lecture_date = %s)
                      OR
                      (LOWER(TRIM(t.day)) = LOWER(%s) AND t.semester_start_date <= %s AND t.semester_end_date >= %s)
                  )
                ORDER BY t.start_time ASC
            """, tuple(params))
            timetable_entries = cursor.fetchall()

        db.close()

        # Format dates/times for rendering in the admin table
        import datetime as dt_module
        for entry in timetable_entries:
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

        return render_template(
            "time_tabel.html",
            subjects=subjects,
            lecturers=lecturers,
            timetable_entries=timetable_entries,
            selected_course=course,
            selected_year=year,
            selected_semester=semester,
            selected_study_mode=study_mode,
            selected_date=selected_date.strftime("%Y-%m-%d")
        )

   
    # ADD TIMETABLE
    
    @app.route("/add_timetable", methods=["POST"])
    def add_timetable():

        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        semester = request.form.get("semester", "").strip()
        part_time_full_time = request.form.get("part_time_full_time", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        lecturer_id = request.form.get("lecturer_id", "").strip()
        location = request.form.get("location", "").strip()
        lecture_date = request.form.get("lecture_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        attendance_mark_time = request.form.get("attendance_mark_time", "0").strip()

        # Validation
        if not course:
            return jsonify({"success": False, "message": "Course/Department is required!"})
        if not year:
            return jsonify({"success": False, "message": "Year is required!"})
        if not semester:
            return jsonify({"success": False, "message": "Semester is required!"})
        if not part_time_full_time:
            return jsonify({"success": False, "message": "Study Mode (Part-Time/Full-Time) is required!"})
        if not subject_id:
            return jsonify({"success": False, "message": "Subject is required!"})
        if not lecturer_id:
            return jsonify({"success": False, "message": "Lecturer is required!"})
        if not location:
            return jsonify({"success": False, "message": "Location is required!"})
        if not start_time or not end_time:
            return jsonify({"success": False, "message": "Start and End times are required!"})

        # New fields
        day = request.form.get("day", "").strip() or None
        time_slot = request.form.get("time_slot", "").strip() or None
        semester_start_date = request.form.get("semester_start_date", "").strip() or None
        semester_end_date = request.form.get("semester_end_date", "").strip() or None

        db = get_db()

        # Weekly Schedule Automation
        if day and semester_start_date and semester_end_date:
            try:
                start_dt = datetime.datetime.strptime(semester_start_date, "%Y-%m-%d").date()
                end_dt = datetime.datetime.strptime(semester_end_date, "%Y-%m-%d").date()
            except ValueError:
                db.close()
                return jsonify({"success": False, "message": "Invalid date format for Semester Start/End Date."})

            if start_dt > end_dt:
                db.close()
                return jsonify({"success": False, "message": "Semester Start Date cannot be after End Date."})

            # Map day name to weekday integer
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_wday = day_map.get(day.lower())
            if target_wday is None:
                db.close()
                return jsonify({"success": False, "message": f"Invalid day of week selected: {day}"})

            # Find all target dates matching the selected weekday between start_dt and end_dt
            # Calculate the number of weeks based on start and end dates
            import math
            diff_days = (end_dt - start_dt).days
            num_weeks = int(math.ceil((diff_days + 1) / 7.0))
            num_weeks = max(1, min(15, num_weeks))

            # Find the first occurrence of target_wday on or after start_dt
            first_lecture_date = start_dt
            while first_lecture_date.weekday() != target_wday:
                first_lecture_date += datetime.timedelta(days=1)

            # Generate exactly num_weeks weekly dates
            dates = []
            for w in range(num_weeks):
                dates.append(first_lecture_date + datetime.timedelta(weeks=w))

            if not dates:
                db.close()
                return jsonify({
                    "success": False,
                    "message": f"No {day}s found between {semester_start_date} and {semester_end_date}."
                })

            # Conflict check for each target date
            conflict_cursor = db.cursor(dictionary=True)
            has_conflict = False
            conflict_msg = ""
            for dt in dates:
                dt_str = dt.strftime("%Y-%m-%d")
                wday_name = dt.strftime("%A")
                conflict_cursor.execute("""
                    SELECT id FROM timetable
                    WHERE course = %s
                      AND part_time_full_time = %s
                      AND year = %s
                      AND semester = %s
                      AND (is_cancelled IS NULL OR is_cancelled = 0)
                      AND (
                          (lecture_date = %s AND time_slot = %s)
                          OR
                          (LOWER(TRIM(day)) = LOWER(%s) AND semester_start_date <= %s AND semester_end_date >= %s AND time_slot = %s)
                      )
                """, (
                    course, part_time_full_time, year, semester,
                    dt_str, time_slot,
                    wday_name, dt_str, dt_str, time_slot
                ))
                conflict = conflict_cursor.fetchone()
                if conflict:
                    has_conflict = True
                    conflict_msg = f"Conflict detected on {dt_str}: A lecture for the same class already exists at this time slot ({time_slot})."
                    break
            conflict_cursor.close()

            if has_conflict:
                db.close()
                return jsonify({"success": False, "message": conflict_msg})

            # Save semester and weeks if start/end dates are provided
            try:
                save_semester_and_weeks(db, course, year, semester, semester_start_date, semester_end_date)
            except Exception as e:
                db.close()
                return jsonify({
                    "success": False,
                    "message": f"Error generating/saving semester weeks: {str(e)}"
                })

            # Insert individual weekly session entries into timetable
            cursor = db.cursor()
            for dt in dates:
                dt_str = dt.strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO timetable
                    (course, year, semester, part_time_full_time, subject_id, lecturer_id, location,
                     lecture_date, start_time, end_time, attendance_mark_time, day, time_slot, semester_start_date, semester_end_date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    course, year, semester, part_time_full_time, subject_id, lecturer_id, location,
                    dt_str, start_time, end_time, attendance_mark_time, None, time_slot, None, None
                ))
            db.commit()
            db.close()

            return jsonify({
                "success": True,
                "message": f"Successfully generated and added {len(dates)} weekly timetable entries!"
            })

        else:
            # One-time (Additional Lecture)
            if not lecture_date:
                db.close()
                return jsonify({"success": False, "message": "Lecture Date is required for one-time lectures."})

            # Conflict check for one-time lecture
            conflict_cursor = db.cursor(dictionary=True)
            wday_name = datetime.datetime.strptime(lecture_date, "%Y-%m-%d").strftime("%A")
            conflict_cursor.execute("""
                SELECT id FROM timetable
                WHERE course = %s
                  AND part_time_full_time = %s
                  AND year = %s
                  AND semester = %s
                  AND (is_cancelled IS NULL OR is_cancelled = 0)
                  AND (
                      (lecture_date = %s AND time_slot = %s)
                      OR
                      (LOWER(TRIM(day)) = LOWER(%s) AND semester_start_date <= %s AND semester_end_date >= %s AND time_slot = %s)
                  )
            """, (
                course, part_time_full_time, year, semester,
                lecture_date, time_slot,
                wday_name, lecture_date, lecture_date, time_slot
            ))
            conflict = conflict_cursor.fetchone()
            conflict_cursor.close()

            if conflict:
                db.close()
                return jsonify({
                    "success": False,
                    "message": f"Conflict detected: A lecture for the same class already exists at this time slot ({time_slot}) on {lecture_date}."
                })

            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO timetable
                (course, year, semester, part_time_full_time, subject_id, lecturer_id, location,
                 lecture_date, start_time, end_time, attendance_mark_time, day, time_slot, semester_start_date, semester_end_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                course, year, semester, part_time_full_time, subject_id, lecturer_id, location,
                lecture_date, start_time, end_time, attendance_mark_time, None, time_slot, None, None
            ))
            db.commit()
            db.close()

            return jsonify({
                "success": True,
                "message": "New lecture added successfully!"
            })
    

    
    # AJAX - GET SUBJECTS
    
    @app.route("/get_subjects")
    def get_subjects():

      course = request.args.get("department")
      year = request.args.get("year")
      semester = request.args.get("semester")

      db = get_db()
      cursor = db.cursor(dictionary=True)

      cursor.execute("""
        SELECT s.id, s.subject_name, s.lecturer_id
        FROM subjects s
        JOIN courses c ON s.course_id = c.id
        WHERE c.course_code = %s
        AND s.year = %s
        AND s.semester = %s
      """, (course, year, semester))

      subjects = cursor.fetchall()

      cursor.close()
      db.close()

      return jsonify(subjects)

# edit time
    @app.route("/edit_timetable/<int:id>")
    def edit_timetable(id):
        import datetime

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM timetable
            WHERE id = %s
        """, (id,))

        timetable = cursor.fetchone()

        cursor.close()
        db.close()

        if not timetable:
            return jsonify({"error": "Timetable not found"}), 404

        # Convert date and timedelta to string so JSON serialization works
        if isinstance(timetable.get("lecture_date"), datetime.date):
            timetable["lecture_date"] = timetable["lecture_date"].isoformat()
        if isinstance(timetable.get("semester_start_date"), datetime.date):
            timetable["semester_start_date"] = timetable["semester_start_date"].isoformat()
        if isinstance(timetable.get("semester_end_date"), datetime.date):
            timetable["semester_end_date"] = timetable["semester_end_date"].isoformat()

        if isinstance(timetable.get("start_time"), datetime.timedelta):
            total_seconds = int(timetable["start_time"].total_seconds())
            h, m = divmod(total_seconds // 60, 60)
            timetable["start_time"] = f"{h:02d}:{m:02d}"

        if isinstance(timetable.get("end_time"), datetime.timedelta):
            total_seconds = int(timetable["end_time"].total_seconds())
            h, m = divmod(total_seconds // 60, 60)
            timetable["end_time"] = f"{h:02d}:{m:02d}"

        if isinstance(timetable.get("attendance_mark_time"), datetime.timedelta):
            total_seconds = int(timetable["attendance_mark_time"].total_seconds())
            h, m = divmod(total_seconds // 60, 60)
            timetable["attendance_mark_time"] = f"{h:02d}:{m:02d}"

        return jsonify(timetable)
    

    @app.route("/update_timetable", methods=["POST"])
    def update_timetable():

        id = request.form.get("id")
        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        semester = request.form.get("semester", "").strip()
        part_time_full_time = request.form.get("part_time_full_time", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        lecturer_id = request.form.get("lecturer_id", "").strip()
        location = request.form.get("location", "").strip()
        lecture_date = request.form.get("lecture_date", "").strip() or None
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        attendance_mark_time = request.form.get("attendance_mark_time", "0").strip()

        # Validation
        if not id:
            return jsonify({"success": False, "message": "ID is required!"})
        if not course:
            return jsonify({"success": False, "message": "Course/Department is required!"})
        if not year:
            return jsonify({"success": False, "message": "Year is required!"})
        if not semester:
            return jsonify({"success": False, "message": "Semester is required!"})
        if not part_time_full_time:
            return jsonify({"success": False, "message": "Study Mode (Part-Time/Full-Time) is required!"})
        if not subject_id:
            return jsonify({"success": False, "message": "Subject is required!"})
        if not lecturer_id:
            return jsonify({"success": False, "message": "Lecturer is required!"})
        if not location:
            return jsonify({"success": False, "message": "Location is required!"})
        if not start_time or not end_time:
            return jsonify({"success": False, "message": "Start and End times are required!"})

        # New fields
        day = request.form.get("day", "").strip() or None
        time_slot = request.form.get("time_slot", "").strip() or None
        semester_start_date = request.form.get("semester_start_date", "").strip() or None
        semester_end_date = request.form.get("semester_end_date", "").strip() or None

        # Use semester_start_date as lecture_date if no explicit lecture_date
        if not lecture_date and semester_start_date:
            lecture_date = semester_start_date

        db = get_db()

        # Conflict Check
        conflict_cursor = db.cursor(dictionary=True)
        if day and semester_start_date and semester_end_date:
            try:
                start_dt = datetime.datetime.strptime(semester_start_date, "%Y-%m-%d").date()
                end_dt = datetime.datetime.strptime(semester_end_date, "%Y-%m-%d").date()
            except ValueError:
                db.close()
                return jsonify({"success": False, "message": "Invalid date format for Semester Start/End Date."})

            conflict_cursor.execute("""
                SELECT id FROM timetable
                WHERE course = %s
                  AND part_time_full_time = %s
                  AND year = %s
                  AND semester = %s
                  AND id != %s
                  AND (is_cancelled IS NULL OR is_cancelled = 0)
                  AND (
                      (LOWER(TRIM(day)) = LOWER(%s) AND semester_start_date <= %s AND semester_end_date >= %s AND time_slot = %s)
                      OR
                      (lecture_date BETWEEN %s AND %s AND time_slot = %s)
                  )
            """, (
                course, part_time_full_time, year, semester, id,
                day, semester_end_date, semester_start_date, time_slot,
                semester_start_date, semester_end_date, time_slot
            ))
            conflict = conflict_cursor.fetchone()
        else:
            if not lecture_date:
                db.close()
                return jsonify({"success": False, "message": "Lecture Date is required."})

            wday_name = datetime.datetime.strptime(lecture_date, "%Y-%m-%d").strftime("%A")
            conflict_cursor.execute("""
                SELECT id FROM timetable
                WHERE course = %s
                  AND part_time_full_time = %s
                  AND year = %s
                  AND semester = %s
                  AND id != %s
                  AND (is_cancelled IS NULL OR is_cancelled = 0)
                  AND (
                      (lecture_date = %s AND time_slot = %s)
                      OR
                      (LOWER(TRIM(day)) = LOWER(%s) AND semester_start_date <= %s AND semester_end_date >= %s AND time_slot = %s)
                  )
            """, (
                course, part_time_full_time, year, semester, id,
                lecture_date, time_slot,
                wday_name, lecture_date, lecture_date, time_slot
            ))
            conflict = conflict_cursor.fetchone()

        conflict_cursor.close()
        if conflict:
            db.close()
            return jsonify({
                "success": False,
                "message": f"Conflict detected: A lecture for the same class already exists at this time slot ({time_slot})."
            })

        # Save semester and weeks if start/end dates are provided
        if semester_start_date and semester_end_date:
            try:
                save_semester_and_weeks(db, course, year, semester, semester_start_date, semester_end_date)
            except Exception as e:
                db.close()
                return jsonify({
                    "success": False,
                    "message": f"Error generating/saving semester weeks: {str(e)}"
                })

        cursor = db.cursor()
        cursor.execute("""
            UPDATE timetable
            SET
                course=%s,
                year=%s,
                semester=%s,
                part_time_full_time=%s,
                subject_id=%s,
                lecturer_id=%s,
                location=%s,
                lecture_date=%s,
                start_time=%s,
                end_time=%s,
                attendance_mark_time=%s,
                day=%s,
                time_slot=%s,
                semester_start_date=%s,
                semester_end_date=%s
            WHERE id=%s
        """, (
            course,
            year,
            semester,
            part_time_full_time,
            subject_id,
            lecturer_id,
            location,
            lecture_date,
            start_time,
            end_time,
            attendance_mark_time,
            day,
            time_slot,
            semester_start_date,
            semester_end_date,
            id
        ))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Timetable updated successfully!"
        })
    


    @app.route("/delete_timetable/<string:id_list>", methods=["POST"])
    def delete_timetable(id_list):
        try:
            ids = [int(x) for x in id_list.split(",") if x.strip().isdigit()]
        except ValueError:
            return jsonify({"success": False, "message": "Invalid timetable ID list!"})

        if not ids:
            return jsonify({"success": False, "message": "No timetable IDs provided!"})

        db = get_db()
        cursor = db.cursor()

        format_strings = ','.join(['%s'] * len(ids))
        cursor.execute(
            f"DELETE FROM timetable WHERE id IN ({format_strings})",
            tuple(ids)
        )

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Timetable(s) deleted successfully!"
        })


   
    # CANCEL LECTURE
    
    @app.route("/cancel_timetable/<int:id>", methods=["POST"])
    def cancel_timetable(id):
        reason = request.form.get("reason", "")

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Fetch lecture details for notification
        cursor.execute("""
            SELECT t.id, t.course, t.year, t.semester,
                   s.subject_name, l.lecturer_name,
                   t.lecture_date, t.start_time, t.end_time, t.location
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            JOIN lecturers l ON t.lecturer_id = l.id
            WHERE t.id = %s
        """, (id,))
        lecture = cursor.fetchone()

        if not lecture:
            cursor.close()
            db.close()
            return jsonify({"success": False, "message": "Lecture not found!"})

        # Mark as cancelled in the DB
        cursor2 = db.cursor()
        cursor2.execute(
            "UPDATE timetable SET is_cancelled = 1, cancel_reason = %s WHERE id = %s",
            (reason, id)
        )
        db.commit()
        cursor2.close()
        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": f"Lecture '{lecture['subject_name']}' on {lecture['lecture_date']} has been cancelled. Students notified.",
            "lecture": {
                "subject":   lecture["subject_name"],
                "lecturer":  lecture["lecturer_name"],
                "date":      str(lecture["lecture_date"]),
                "start":     str(lecture["start_time"]),
                "end":       str(lecture["end_time"]),
                "location":  lecture["location"],
                "course":    lecture["course"],
            }
        })


    # API: CANCELLED LECTURES (for student dashboard notifications)
   
    @app.route("/api/cancelled-lectures")
    def api_cancelled_lectures():
        import datetime

        course   = request.args.get("course", "")
        year     = request.args.get("year", "")
        semester = request.args.get("semester", "")

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                t.id,
                s.subject_name,
                l.lecturer_name,
                t.location,
                t.lecture_date,
                t.start_time,
                t.end_time,
                t.cancel_reason
            FROM timetable t
            JOIN subjects s ON t.subject_id = s.id
            JOIN lecturers l ON t.lecturer_id = l.id
            WHERE t.is_cancelled = 1
              AND t.course   = %s
              AND t.year     = %s
              AND t.semester = %s
            ORDER BY t.lecture_date DESC
        """, (course, year, semester))

        rows = cursor.fetchall()
        cursor.close()
        db.close()

        # Convert date/timedelta to strings
        result = []
        for row in rows:
            if isinstance(row.get("lecture_date"), datetime.date):
                row["lecture_date"] = row["lecture_date"].isoformat()
            if isinstance(row.get("start_time"), datetime.timedelta):
                total = int(row["start_time"].total_seconds())
                h, m = divmod(total // 60, 60)
                row["start_time"] = f"{h:02d}:{m:02d}"
            if isinstance(row.get("end_time"), datetime.timedelta):
                total = int(row["end_time"].total_seconds())
                h, m = divmod(total // 60, 60)
                row["end_time"] = f"{h:02d}:{m:02d}"
            result.append(row)

        return jsonify(result)

