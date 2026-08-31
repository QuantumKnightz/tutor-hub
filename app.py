import os

from flask import Flask, redirect, render_template, request, url_for
import db


app = Flask(__name__)

app.config["DATABASE"] = os.path.join(
    app.instance_path,
    "tutor_hub.sqlite3",
)

os.makedirs(app.instance_path, exist_ok=True)

db.init_app(app)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/students")
def students():
    database = db.get_db()

    student_list = database.execute(
        """
        SELECT id, name, grade, subjects, status, created_at
        FROM students
        ORDER BY name
        """
    ).fetchall()

    return render_template("students.html", students=student_list)

@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        student_name = request.form.get("name", "").strip()
        grade = request.form.get("grade", "").strip()
        subjects = request.form.get("subjects", "").strip()

        if not student_name or not grade or not subjects:
            return render_template(
                "add_student.html",
                error="Please complete name, grade, and subjects.",
            )

        database = db.get_db()

        database.execute(
            """
            INSERT INTO students (name, grade, subjects)
            VALUES (?, ?, ?)
            """,
            (student_name, grade, subjects),
        )

        database.commit()

        return redirect(url_for("students"))

    return render_template("add_student.html")

@app.route("/sessions")
def sessions():
    database = db.get_db()

    upcoming_sessions = database.execute(
        """
        SELECT
            sessions.id,
            sessions.subject,
            sessions.session_date,
            sessions.start_time,
            sessions.duration_minutes,
            students.name AS student_name
        FROM sessions
        JOIN students ON sessions.student_id = students.id
        WHERE sessions.status = 'scheduled'
          AND sessions.session_date >= DATE('now')
        ORDER BY sessions.session_date ASC, sessions.start_time ASC
        """
    ).fetchall()

    return render_template(
        "sessions.html",
        sessions=upcoming_sessions,
    )

if __name__ == "__main__":
    app.run(debug=True)