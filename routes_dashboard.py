import datetime
from flask import render_template, redirect, flash, session, url_for, jsonify
from db import get_db

def register_dashboard_routes(app):
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session or session.get("role") != "admin":
            flash("Access denied! Administrators only.", "error")
            return redirect(url_for("home"))
        return render_template("dashboard.html")

    @app.route("/api/dashboard-stats")
    def dashboard_stats():
        if "user" not in session or session.get("role") != "admin":
            return jsonify({"error": "Not logged in"}), 401

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cursor.fetchone()["total"]

        today = datetime.date.today().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT COUNT(DISTINCT student_id) AS cnt FROM attendance WHERE date = %s",
            (today,)
        )
        present_today = cursor.fetchone()["cnt"]

        cursor.close()
        db.close()

        return jsonify({
            "total_students": total_students,
            "present_today":  present_today,
            "absent_today":   max(0, total_students - present_today)
        })

    @app.route("/api/attendance-trend")
    def attendance_trend():
        if "user" not in session or session.get("role") != "admin":
            return jsonify({"error": "Not logged in"}), 401

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total = cursor.fetchone()["total"] or 1

        trend = []
        for i in range(6, -1, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i))
            day_str = day.strftime("%Y-%m-%d")

            cursor.execute(
                "SELECT COUNT(DISTINCT student_id) AS cnt FROM attendance WHERE date = %s",
                (day_str,)
            )
            cnt = cursor.fetchone()["cnt"]
            percent = min(100, round((cnt / total) * 100)) if total > 0 else 0

            trend.append({"date": day_str, "present": cnt, "percent": percent})

        cursor.close()
        db.close()

        return jsonify(trend)
