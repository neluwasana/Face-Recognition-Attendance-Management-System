from flask import render_template, request, redirect, flash, session, url_for
from db import get_db

def register_auth_routes(app):

    @app.route("/")
    def home():
        return render_template("login.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":

            username = request.form.get("username")
            password = request.form.get("password")

            if not username or not password:
                flash("Please fill username and password!", "error")
                return redirect(url_for("home"))

            # ADMIN LOGIN
            if username == "admin" and password == "1234":
                session.clear()
                session["user"] = username
                session["role"] = "admin"
                return redirect(url_for("dashboard"))

            db = get_db()
            cursor = db.cursor(dictionary=True)

            # STUDENT LOGIN
            cursor.execute(
                "SELECT * FROM students WHERE username=%s AND password=%s",
                (username, password)
            )
            student = cursor.fetchone()

            if student:
                session.clear()
                session["student_id"] = student["id"]
                session["student_name"] = student["full_name"]
                session["role"] = "student"
                cursor.close()
                db.close()
                return redirect(url_for("student_dashboard"))

            # LECTURER LOGIN
            cursor.execute(
                "SELECT * FROM lecturers WHERE username=%s AND password=%s",
                (username, password)
            )
            lecturer = cursor.fetchone()
            cursor.close()
            db.close()

            if lecturer:
                session.clear()
                session["lecturer_id"] = lecturer["id"]
                session["lecturer_name"] = lecturer["lecturer_name"]
                session["user"] = lecturer["username"]
                session["role"] = "lecturer"
                return redirect(url_for("lecturer_dashboard"))

            flash("Invalid username or password!", "error")
            return redirect(url_for("home"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out successfully!", "success")
        return redirect(url_for("home"))