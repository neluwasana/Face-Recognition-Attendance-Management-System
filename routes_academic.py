from flask import render_template, request, redirect, flash, session, jsonify, url_for
from db import get_db

def register_academic_routes(app):

    @app.route("/academic_management")
    def academic_management():
        if "user" not in session:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
            
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Fetch courses
        cursor.execute("SELECT * FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        
        # Fetch subjects
        cursor.execute("""
            SELECT s.*, c.course_code, c.course_name, l.lecturer_name
            FROM subjects s
            JOIN courses c ON s.course_id = c.id
            JOIN lecturers l ON s.lecturer_id = l.id
            ORDER BY c.course_code, s.subject_code
        """)
        subjects = cursor.fetchall()
        
        # Fetch lecturers
        cursor.execute("SELECT * FROM lecturers ORDER BY lecturer_name")
        lecturers = cursor.fetchall()
        
        # Convert date objects to string so Jinja can render them cleanly
        for row in lecturers:
            if row.get("dob") and hasattr(row["dob"], "isoformat"):
                row["dob"] = row["dob"].isoformat()
        
        cursor.close()
        db.close()
        
        return render_template("academic_management.html", courses=courses, subjects=subjects, lecturers=lecturers)

    @app.route("/lecturer_management")
    def lecturer_management():
        if "user" not in session:
            flash("Please login first!", "error")
            return redirect(url_for("home"))
        # Lecturers are now managed inside Academic Management (Lecturers tab)
        return redirect(url_for("academic_management"))


    #  COURSES 

    @app.route("/api/courses")
    def api_courses():
        if "user" not in session and "lecturer_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(courses)


    @app.route("/api/courses/add", methods=["POST"])
    def api_add_course():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data = request.get_json() or request.form
        code = data.get("course_code", "").strip()
        name = data.get("course_name", "").strip()

        if not code or not name:
            return jsonify({"success": False, "message": "Please fill course code and name!"})

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO courses (course_code, course_name) VALUES (%s, %s)", (code, name))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Course added successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    @app.route("/api/courses/edit", methods=["POST"])
    def api_edit_course():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data = request.get_json() or request.form
        cid  = data.get("id")
        code = data.get("course_code", "").strip()
        name = data.get("course_name", "").strip()

        if not cid or not code or not name:
            return jsonify({"success": False, "message": "Missing required fields!"})

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("UPDATE courses SET course_code=%s, course_name=%s WHERE id=%s", (code, name, cid))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Course updated successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    @app.route("/api/courses/delete/<int:id>", methods=["POST"])
    def api_delete_course(id):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM courses WHERE id=%s", (id,))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Course deleted successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    #LECTURERS
    @app.route("/api/lecturers")
    def api_lecturers():
        if "user" not in session:
            return jsonify({"error": "Not logged in"}), 401
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM lecturers ORDER BY lecturer_name")
        lecturers = cursor.fetchall()
        cursor.close()
        db.close()
        # Convert date objects to string so JSON serialization works
        for row in lecturers:
            if row.get("dob") and hasattr(row["dob"], "isoformat"):
                row["dob"] = row["dob"].isoformat()
        return jsonify(lecturers)



    @app.route("/api/lecturers/add", methods=["POST"])
    def api_add_lecturer():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data          = request.get_json() or request.form
        name          = data.get("lecturer_name", "").strip()
        subjects      = data.get("subjects", "").strip()
        qualification = data.get("qualification", "").strip()
        nic           = data.get("nic", "").strip()
        tel_no        = data.get("tel_no", "").strip()
        email         = data.get("email", "").strip()
        dob           = data.get("dob", "").strip()
        username      = data.get("username", "").strip()
        password      = data.get("password", "").strip()

        if not name:
            return jsonify({"success": False, "message": "Please enter lecturer name!"})

        if not nic:
            return jsonify({"success": False, "message": "Please enter NIC number!"})

        import re
        if not re.match(r"^(\d{9}[VvXx]|\d{12})$", nic):
            return jsonify({"success": False, "message": "Please enter a valid NIC number (e.g. 123456789V or 123456789012)."})

        if not username:
            return jsonify({"success": False, "message": "Please enter a username!"})

        if not password:
            return jsonify({"success": False, "message": "Please enter a password!"})

        # Check if NIC already exists in students or lecturers
        db_check = get_db()
        cursor_check = db_check.cursor()
        cursor_check.execute("SELECT id FROM students WHERE nic = %s", (nic,))
        exists_student = cursor_check.fetchone()
        cursor_check.execute("SELECT id FROM lecturers WHERE nic = %s", (nic,))
        exists_lecturer = cursor_check.fetchone()
        cursor_check.close()
        db_check.close()
        if exists_student or exists_lecturer:
            return jsonify({"success": False, "message": "This NIC is already registered."})



        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO lecturers
                   (lecturer_name, subjects, qualification, nic, tel_no, email, dob, username, password)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, subjects or None, qualification or None, nic or None,
                 tel_no or None, email or None, dob or None, username, password)
            )
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Lecturer added successfully!"})
        except Exception as e:
            err = str(e)
            if "Duplicate entry" in err and "username" in err:
                return jsonify({"success": False, "message": "This username is already taken!"})
            return jsonify({"success": False, "message": err})


    @app.route("/api/lecturers/edit", methods=["POST"])
    def api_edit_lecturer():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data          = request.get_json() or request.form
        lid           = data.get("id")
        name          = data.get("lecturer_name", "").strip()
        subjects      = data.get("subjects", "").strip()
        qualification = data.get("qualification", "").strip()
        nic           = data.get("nic", "").strip()
        tel_no        = data.get("tel_no", "").strip()
        email         = data.get("email", "").strip()
        dob           = data.get("dob", "").strip()
        username      = data.get("username", "").strip()
        password      = data.get("password", "").strip()

        if not lid or not name:
            return jsonify({"success": False, "message": "Missing required fields!"})

        if not nic:
            return jsonify({"success": False, "message": "Please enter NIC number!"})

        import re
        if not re.match(r"^(\d{9}[VvXx]|\d{12})$", nic):
            return jsonify({"success": False, "message": "Please enter a valid NIC number (e.g. 123456789V or 123456789012)."})

        # Check if NIC already exists in students or lecturers (excluding current lecturer)
        db_check = get_db()
        cursor_check = db_check.cursor()
        cursor_check.execute("SELECT id FROM students WHERE nic = %s", (nic,))
        exists_student = cursor_check.fetchone()
        cursor_check.execute("SELECT id FROM lecturers WHERE nic = %s AND id != %s", (nic, lid))
        exists_lecturer = cursor_check.fetchone()
        cursor_check.close()
        db_check.close()
        if exists_student or exists_lecturer:
            return jsonify({"success": False, "message": "This NIC is already registered."})



        try:
            db = get_db()

            # If password is blank, keep the old one
            if not password:
                cursor_check = db.cursor(dictionary=True)
                cursor_check.execute("SELECT password FROM lecturers WHERE id=%s", (lid,))
                row = cursor_check.fetchone()
                cursor_check.close()
                password = row["password"] if row else ""

            cursor = db.cursor()
            cursor.execute(
                """UPDATE lecturers
                   SET lecturer_name=%s, subjects=%s, qualification=%s, nic=%s,
                       tel_no=%s, email=%s, dob=%s, username=%s, password=%s
                   WHERE id=%s""",
                (name, subjects or None, qualification or None, nic or None,
                 tel_no or None, email or None, dob or None, username, password, lid)
            )
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Lecturer updated successfully!"})
        except Exception as e:
            err = str(e)
            if "Duplicate entry" in err and "username" in err:
                return jsonify({"success": False, "message": "This username is already taken!"})
            return jsonify({"success": False, "message": err})


    @app.route("/api/lecturers/delete/<int:id>", methods=["POST"])
    def api_delete_lecturer(id):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM lecturers WHERE id=%s", (id,))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Lecturer deleted successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    # SUBJECTS 

    @app.route("/api/subjects")
    def api_subjects():
        if "user" not in session:
            return jsonify({"error": "Not logged in"}), 401
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, c.course_code, c.course_name, l.lecturer_name
            FROM subjects s
            JOIN courses c ON s.course_id = c.id
            JOIN lecturers l ON s.lecturer_id = l.id
            ORDER BY c.course_code, s.subject_code
        """)
        subjects = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(subjects)


    @app.route("/api/subjects/add", methods=["POST"])
    def api_add_subject():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data        = request.get_json() or request.form
        code        = data.get("subject_code", "").strip()
        name        = data.get("subject_name", "").strip()
        course_id   = data.get("course_id")
        year        = data.get("year", "").strip()
        semester    = data.get("semester", "").strip()
        lecturer_id = data.get("lecturer_id")

        if not code or not name or not course_id or not year or not semester or not lecturer_id:
            return jsonify({"success": False, "message": "Please fill all required fields!"})

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO subjects (subject_code, subject_name, course_id, year, semester, lecturer_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (code, name, course_id, year, semester, lecturer_id)
            )
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Subject added successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    @app.route("/api/subjects/edit", methods=["POST"])
    def api_edit_subject():
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401

        data        = request.get_json() or request.form
        sid         = data.get("id")
        code        = data.get("subject_code", "").strip()
        name        = data.get("subject_name", "").strip()
        course_id   = data.get("course_id")
        year        = data.get("year", "").strip()
        semester    = data.get("semester", "").strip()
        lecturer_id = data.get("lecturer_id")

        if not sid or not code or not name or not course_id or not year or not semester or not lecturer_id:
            return jsonify({"success": False, "message": "Missing required fields!"})

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE subjects SET subject_code=%s, subject_name=%s, course_id=%s, year=%s, semester=%s, lecturer_id=%s WHERE id=%s",
                (code, name, course_id, year, semester, lecturer_id, sid)
            )
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Subject updated successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    @app.route("/api/subjects/delete/<int:id>", methods=["POST"])
    def api_delete_subject(id):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM subjects WHERE id=%s", (id,))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Subject deleted successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


    @app.route("/api/courses/<int:course_id>/subjects")
    def api_course_subjects(course_id):
        if "user" not in session and "lecturer_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, l.lecturer_name
            FROM subjects s
            JOIN lecturers l ON s.lecturer_id = l.id
            WHERE s.course_id = %s
            ORDER BY s.subject_code
        """, (course_id,))
        subjects = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(subjects)
