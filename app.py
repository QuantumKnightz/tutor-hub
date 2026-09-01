import os

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "development-only-change-this-secret-key",
)

app.config["DATABASE"] = os.path.join(
    app.instance_path,
    "tutor_hub.sqlite3",
)

os.makedirs(app.instance_path, exist_ok=True)

db.init_app(app)


@app.route("/")
def home():
    database = db.get_db()

    upcoming_sessions = database.execute(
        """
        SELECT
            sessions.id,
            sessions.session_date,
            sessions.start_time,
            sessions.subject,
            sessions.duration_minutes,
            students.name AS student_name
        FROM sessions
        JOIN students
            ON sessions.student_id = students.id
        WHERE sessions.status = 'scheduled'
          AND sessions.session_date >= DATE('now')
        ORDER BY sessions.session_date ASC, sessions.start_time ASC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "home.html",
        upcoming_sessions=upcoming_sessions,
    )


@app.route("/students")
def students():
    database = db.get_db()

    student_list = database.execute(
        """
        SELECT
            id,
            name,
            grade,
            subjects,
            status,
            created_at
        FROM students
        ORDER BY name ASC
        """
    ).fetchall()

    return render_template(
        "students.html",
        students=student_list,
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

        flash(f"{student_name} was added as a student.", "success")

        return redirect(url_for("students"))

    return render_template("add_student.html")


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

        flash(f"{student_name}'s profile was updated.", "success")

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
        SELECT id, name
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

    flash(
        f"{student['name']} was archived. Their profile and history were kept.",
        "success",
    )

    return redirect(
        url_for("student_profile", student_id=student_id)
    )


@app.route("/students/<int:student_id>/restore", methods=["POST"])
def restore_student(student_id):
    database = db.get_db()

    student = database.execute(
        """
        SELECT id, name
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

    flash(
        f"{student['name']} was restored and is available for scheduling.",
        "success",
    )

    return redirect(
        url_for("student_profile", student_id=student_id)
    )


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
        JOIN students
            ON sessions.student_id = students.id
        WHERE sessions.status = 'scheduled'
          AND sessions.session_date >= DATE('now')
        ORDER BY sessions.session_date ASC, sessions.start_time ASC
        """
    ).fetchall()

    return render_template(
        "sessions.html",
        sessions=upcoming_sessions,
    )


@app.route("/sessions/add", methods=["GET", "POST"])
def add_session():
    database = db.get_db()

    active_students = database.execute(
        """
        SELECT
            id,
            name,
            grade,
            subjects
        FROM students
        WHERE status = 'active'
        ORDER BY name ASC
        """
    ).fetchall()

    selected_student_id = request.args.get("student_id", type=int)

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        subject = request.form.get("subject", "").strip()
        session_date = request.form.get("session_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        duration_minutes = request.form.get(
            "duration_minutes",
            "",
        ).strip()
        notes = request.form.get("notes", "").strip()

        if (
            not student_id
            or not subject
            or not session_date
            or not start_time
            or not duration_minutes
        ):
            return render_template(
                "add_session.html",
                students=active_students,
                selected_student_id=selected_student_id,
                error=(
                    "Please complete student, subject, date, time, "
                    "and duration."
                ),
            )

        try:
            student_id = int(student_id)
            duration_minutes = int(duration_minutes)
        except ValueError:
            return render_template(
                "add_session.html",
                students=active_students,
                selected_student_id=selected_student_id,
                error="Please choose a student and enter a valid duration.",
            )

        selected_student_id = student_id

        student = database.execute(
            """
            SELECT id, name
            FROM students
            WHERE id = ?
              AND status = 'active'
            """,
            (student_id,),
        ).fetchone()

        if student is None:
            return render_template(
                "add_session.html",
                students=active_students,
                selected_student_id=selected_student_id,
                error="Please choose an active student.",
            )

        if duration_minutes <= 0:
            return render_template(
                "add_session.html",
                students=active_students,
                selected_student_id=selected_student_id,
                error="Duration must be greater than zero.",
            )

        database.execute(
            """
            INSERT INTO sessions (
                student_id,
                subject,
                session_date,
                start_time,
                duration_minutes,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                subject,
                session_date,
                start_time,
                duration_minutes,
                notes,
            ),
        )

        database.commit()

        flash(
            f"Session for {student['name']} was scheduled successfully.",
            "success",
        )

        return redirect(url_for("sessions"))

    return render_template(
        "add_session.html",
        students=active_students,
        selected_student_id=selected_student_id,
    )


if __name__ == "__main__":
    app.run(debug=True)