import os

from flask import Flask, abort, redirect, render_template, request, url_for

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


@app.route("/students/<int:student_id>")
def student_profile(student_id):
    database = db.get_db()

    student = database.execute(
        """
        SELECT
            id,
            name,
            grade,
            subjects,
            school,
            learning_goal,
            current_level,
            strengths,
            areas_to_improve,
            tutor_notes,
            status,
            created_at
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    upcoming_sessions = database.execute(
        """
        SELECT
            id,
            subject,
            session_date,
            start_time,
            duration_minutes
        FROM sessions
        WHERE student_id = ?
          AND status = 'scheduled'
          AND session_date >= DATE('now')
        ORDER BY session_date ASC, start_time ASC
        LIMIT 3
        """,
        (student_id,),
    ).fetchall()

    return render_template(
        "student_profile.html",
        student=student,
        upcoming_sessions=upcoming_sessions,
    )


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    database = db.get_db()

    student = database.execute(
        """
        SELECT
            id,
            name,
            grade,
            subjects,
            school,
            learning_goal,
            current_level,
            strengths,
            areas_to_improve,
            tutor_notes,
            status,
            created_at
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    if request.method == "POST":
        student_name = request.form.get("name", "").strip()
        grade = request.form.get("grade", "").strip()
        subjects = request.form.get("subjects", "").strip()
        school = request.form.get("school", "").strip()
        learning_goal = request.form.get("learning_goal", "").strip()
        current_level = request.form.get("current_level", "").strip()
        strengths = request.form.get("strengths", "").strip()
        areas_to_improve = request.form.get(
            "areas_to_improve",
            "",
        ).strip()
        tutor_notes = request.form.get("tutor_notes", "").strip()

        if not student_name or not grade or not subjects or not school:
            return render_template(
                "student_editpage.html",
                student=student,
                error="Please complete name, grade, subjects, and school.",
            )

        database.execute(
            """
            UPDATE students
            SET
                name = ?,
                grade = ?,
                subjects = ?,
                school = ?,
                learning_goal = ?,
                current_level = ?,
                strengths = ?,
                areas_to_improve = ?,
                tutor_notes = ?
            WHERE id = ?
            """,
            (
                student_name,
                grade,
                subjects,
                school,
                learning_goal,
                current_level,
                strengths,
                areas_to_improve,
                tutor_notes,
                student_id,
            ),
        )

        database.commit()

        return redirect(
            url_for("student_profile", student_id=student_id)
        )

    return render_template(
        "student_editpage.html",
        student=student,
    )


@app.route("/students/<int:student_id>/archive", methods=["POST"])
def archive_student(student_id):
    database = db.get_db()

    student = database.execute(
        """
        SELECT id, status
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    database.execute(
        """
        UPDATE students
        SET status = 'archived'
        WHERE id = ?
        """,
        (student_id,),
    )

    database.commit()

    return redirect(
        url_for("student_profile", student_id=student_id)
    )


@app.route("/students/<int:student_id>/restore", methods=["POST"])
def restore_student(student_id):
    database = db.get_db()

    student = database.execute(
        """
        SELECT id, status
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    database.execute(
        """
        UPDATE students
        SET status = 'active'
        WHERE id = ?
        """,
        (student_id,),
    )

    database.commit()

    return redirect(
        url_for("student_profile", student_id=student_id)
    )


@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        student_name = request.form.get("name", "").strip()
        grade = request.form.get("grade", "").strip()
        subjects = request.form.get("subjects", "").strip()
        school = request.form.get("school", "").strip()
        learning_goal = request.form.get("learning_goal", "").strip()
        current_level = request.form.get("current_level", "").strip()
        strengths = request.form.get("strengths", "").strip()
        areas_to_improve = request.form.get(
            "areas_to_improve",
            "",
        ).strip()
        tutor_notes = request.form.get("tutor_notes", "").strip()

        if not student_name or not grade or not subjects or not school:
            return render_template(
                "add_student.html",
                error="Please complete name, grade, subjects, and school.",
            )

        database = db.get_db()

        database.execute(
            """
            INSERT INTO students (
                name,
                grade,
                subjects,
                school,
                learning_goal,
                current_level,
                strengths,
                areas_to_improve,
                tutor_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_name,
                grade,
                subjects,
                school,
                learning_goal,
                current_level,
                strengths,
                areas_to_improve,
                tutor_notes,
            ),
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