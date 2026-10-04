from flask import Flask
from routes_auth import register_auth_routes
from routes_dashboard import register_dashboard_routes
from routes_student import register_student_routes
from routes_academic import register_academic_routes
from routes_timetabel import register_timetabel_routes

from routes_attendance import register_attendance_routes
from routes_lecturer import register_lecturer_routes
from student_view import register_student_view_routes


app = Flask(__name__)
app.secret_key = "Nelu"
# Allow up to 16 MB per request so base64 face images don't hit the 413 limit
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

@app.errorhandler(413)
def request_entity_too_large(error):
    from flask import jsonify
    return jsonify({
        "success": False,
        "message": "Image is too large. Please upload an image smaller than 16 MB or use the camera capture instead."
    }), 413

# Register all routes directly on the app instance
register_auth_routes(app)
register_dashboard_routes(app)
register_student_routes(app)
register_academic_routes(app)
register_timetabel_routes(app)

register_student_view_routes(app)
register_attendance_routes(app)
register_lecturer_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
