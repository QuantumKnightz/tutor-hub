import os
import sqlite3
from datetime import date, datetime

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


def ensure_homework_table():
    database = db.get_db()
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            resource_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned',
            assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            submitted_at TEXT,
            teacher_feedback TEXT,
            reviewed_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
        """
    )
    database.commit()


def homework_display_status(homework):
    stored_status = homework["status"]
    if stored_status == "reviewed":
        return "Reviewed"
    if stored_status == "submitted":
        if homework["submitted_at"] and homework["due_date"]:
            submitted_date = homework["submitted_at"][:10]
            if submitted_date > homework["due_date"]:
                days_late = (
                    date.fromisoformat(submitted_date)
                    - date.fromisoformat(homework["due_date"])
                ).days
                return f"Submitted {days_late} day{'s' if days_late != 1 else ''} late"
        return "Submitted"

    days_overdue = (
        date.today() - date.fromisoformat(homework["due_date"])
    ).days
    if days_overdue > 0:
        return f"Overdue by {days_overdue} day{'s' if days_overdue != 1 else ''}"
    return "Assigned"


def homework_context(rows):
    items = []
    for row in rows:
        item = dict(row)
        item["display_status"] = homework_display_status(row)
        item["status_key"] = row["status"]
        if row["status"] == "assigned" and date.fromisoformat(row["due_date"]) < date.today():
            item["status_key"] = "overdue"
        elif row["status"] == "submitted":
            submitted_date = row["submitted_at"][:10] if row["submitted_at"] else ""
            item["status_key"] = "late" if submitted_date > row["due_date"] else "submitted"
        items.append(item)
    return items


@app.before_request
def prepare_homework_table():
    if request.endpoint != "static":
        ensure_homework_table()


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

    return render_template("students.html", students=student_list)


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
        areas_to_improve = request.form.get("areas_to_improve", "").strip()
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
                name, grade, subjects, school, learning_goal,
                current_level, strengths, areas_to_improve, tutor_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_name, grade, subjects, school, learning_goal,
                current_level, strengths, areas_to_improve, tutor_notes,
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
        SELECT id, name, grade, subjects, school, learning_goal,
               current_level, strengths, areas_to_improve, tutor_notes,
               status, created_at
        FROM students WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    upcoming_sessions = database.execute(
        """
        SELECT id, subject, session_date, start_time, duration_minutes
        FROM sessions
        WHERE student_id = ? AND status = 'scheduled'
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
        SELECT id, name, grade, subjects, school, learning_goal,
               current_level, strengths, areas_to_improve, tutor_notes,
               status, created_at
        FROM students WHERE id = ?
        """,
        (student_id,),
    ).fetchone()

    if student is None:
        abort(404)

    if request.method == "POST":
        values = {
            "name": request.form.get("name", "").strip(),
            "grade": request.form.get("grade", "").strip(),
            "subjects": request.form.get("subjects", "").strip(),
            "school": request.form.get("school", "").strip(),
            "learning_goal": request.form.get("learning_goal", "").strip(),
            "current_level": request.form.get("current_level", "").strip(),
            "strengths": request.form.get("strengths", "").strip(),
            "areas_to_improve": request.form.get("areas_to_improve", "").strip(),
            "tutor_notes": request.form.get("tutor_notes", "").strip(),
        }

        if not values["name"] or not values["grade"] or not values["subjects"] or not values["school"]:
            return render_template(
                "student_editpage.html",
                student=student,
                error="Please complete name, grade, subjects, and school.",
            )

        database.execute(
            """
            UPDATE students SET name = ?, grade = ?, subjects = ?, school = ?,
                learning_goal = ?, current_level = ?, strengths = ?,
                areas_to_improve = ?, tutor_notes = ?
            WHERE id = ?
            """,
            (
                values["name"], values["grade"], values["subjects"], values["school"],
                values["learning_goal"], values["current_level"], values["strengths"],
                values["areas_to_improve"], values["tutor_notes"], student_id,
            ),
        )
        database.commit()
        flash(f"{values['name']}'s profile was updated.", "success")
        return redirect(url_for("student_profile", student_id=student_id))

    return render_template("student_editpage.html", student=student)


@app.route("/students/<int:student_id>/archive", methods=["POST"])
def archive_student(student_id):
    database = db.get_db()
    student = database.execute("SELECT id, name FROM students WHERE id = ?", (student_id,)).fetchone()
    if student is None:
        abort(404)
    database.execute("UPDATE students SET status = 'archived' WHERE id = ?", (student_id,))
    database.commit()
    flash(f"{student['name']} was archived. Their profile and history were kept.", "success")
    return redirect(url_for("student_profile", student_id=student_id))


@app.route("/students/<int:student_id>/restore", methods=["POST"])
def restore_student(student_id):
    database = db.get_db()
    student = database.execute("SELECT id, name FROM students WHERE id = ?", (student_id,)).fetchone()
    if student is None:
        abort(404)
    database.execute("UPDATE students SET status = 'active' WHERE id = ?", (student_id,))
    database.commit()
    flash(f"{student['name']} was restored and is available for scheduling.", "success")
    return redirect(url_for("student_profile", student_id=student_id))


@app.route("/sessions")
def sessions():
    database = db.get_db()
    upcoming_sessions = database.execute(
        """
        SELECT sessions.id, sessions.subject, sessions.session_date,
               sessions.start_time, sessions.duration_minutes,
               students.name AS student_name
        FROM sessions JOIN students ON sessions.student_id = students.id
        WHERE sessions.status = 'scheduled'
          AND sessions.session_date >= DATE('now')
        ORDER BY sessions.session_date ASC, sessions.start_time ASC
        """
    ).fetchall()
    return render_template("sessions.html", sessions=upcoming_sessions)


@app.route("/sessions/add", methods=["GET", "POST"])
def add_session():
    database = db.get_db()
    active_students = database.execute(
        "SELECT id, name, grade, subjects FROM students WHERE status = 'active' ORDER BY name ASC"
    ).fetchall()
    selected_student_id = request.args.get("student_id", type=int)

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        subject = request.form.get("subject", "").strip()
        session_date = request.form.get("session_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        duration_minutes = request.form.get("duration_minutes", "").strip()
        notes = request.form.get("notes", "").strip()

        if not student_id or not subject or not session_date or not start_time or not duration_minutes:
            return render_template(
                "add_session.html", students=active_students,
                selected_student_id=selected_student_id,
                error="Please complete student, subject, date, time, and duration.",
            )

        try:
            student_id = int(student_id)
            duration_minutes = int(duration_minutes)
        except ValueError:
            return render_template(
                "add_session.html", students=active_students,
                selected_student_id=selected_student_id,
                error="Please choose a student and enter a valid duration.",
            )

        selected_student_id = student_id
        student = database.execute(
            "SELECT id, name FROM students WHERE id = ? AND status = 'active'",
            (student_id,),
        ).fetchone()

        if student is None:
            return render_template(
                "add_session.html", students=active_students,
                selected_student_id=selected_student_id,
                error="Please choose an active student.",
            )

        if duration_minutes <= 0:
            return render_template(
                "add_session.html", students=active_students,
                selected_student_id=selected_student_id,
                error="Duration must be greater than zero.",
            )

        database.execute(
            """
            INSERT INTO sessions (student_id, subject, session_date,
                                  start_time, duration_minutes, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, subject, session_date, start_time, duration_minutes, notes),
        )
        database.commit()
        flash(f"Session for {student['name']} was scheduled successfully.", "success")
        return redirect(url_for("sessions"))

    return render_template(
        "add_session.html", students=active_students,
        selected_student_id=selected_student_id,
    )


@app.route("/homework")
def homework():
    database = db.get_db()
    filter_name = request.args.get("status", "all")
    rows = database.execute(
        """
        SELECT homework.*, students.name AS student_name
        FROM homework JOIN students ON homework.student_id = students.id
        ORDER BY homework.due_date ASC, homework.id DESC
        """
    ).fetchall()
    items = homework_context(rows)
    if filter_name in {"assigned", "overdue", "submitted", "reviewed"}:
        items = [item for item in items if item["status_key"] == filter_name]
    return render_template("homework.html", homework=items, active_filter=filter_name)


@app.route("/homework/add", methods=["GET", "POST"])
def add_homework():
    database = db.get_db()
    active_students = database.execute(
        "SELECT id, name, grade, subjects FROM students WHERE status = 'active' ORDER BY name ASC"
    ).fetchall()

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()

        if not student_id or not title or not description or not due_date:
            return render_template(
                "add_homework.html", students=active_students,
                error="Please complete student, title, description, and due date.",
            )

        try:
            student_id = int(student_id)
            date.fromisoformat(due_date)
        except ValueError:
            return render_template(
                "add_homework.html", students=active_students,
                error="Please choose a valid student and due date.",
            )

        student = database.execute(
            "SELECT id, name FROM students WHERE id = ? AND status = 'active'",
            (student_id,),
        ).fetchone()
        if student is None:
            return render_template(
                "add_homework.html", students=active_students,
                error="Please choose an active student.",
            )

        database.execute(
            """
            INSERT INTO homework (student_id, title, description, due_date)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, title, description, due_date),
        )
        database.commit()
        flash(f"Homework was assigned to {student['name']}.", "success")
        return redirect(url_for("homework"))

    return render_template("add_homework.html", students=active_students)


@app.route("/homework/<int:homework_id>")
def homework_detail(homework_id):
    database = db.get_db()
    item = database.execute(
        """
        SELECT homework.*, students.name AS student_name
        FROM homework JOIN students ON homework.student_id = students.id
        WHERE homework.id = ?
        """,
        (homework_id,),
    ).fetchone()
    if item is None:
        abort(404)
    item = dict(item)
    item["display_status"] = homework_display_status(item)
    return render_template("homework_detail.html", homework=item)


@app.route("/homework/<int:homework_id>/submit", methods=["POST"])
def submit_homework(homework_id):
    database = db.get_db()
    item = database.execute("SELECT id FROM homework WHERE id = ?", (homework_id,)).fetchone()
    if item is None:
        abort(404)
    database.execute(
        "UPDATE homework SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP WHERE id = ?",
        (homework_id,),
    )
    database.commit()
    flash("Homework was marked as submitted.", "success")
    return redirect(url_for("homework_detail", homework_id=homework_id))


@app.route("/homework/<int:homework_id>/review", methods=["POST"])
def review_homework(homework_id):
    feedback = request.form.get("teacher_feedback", "").strip()
    if not feedback:
        flash("Please write feedback before marking homework as reviewed.", "error")
        return redirect(url_for("homework_detail", homework_id=homework_id))
    database = db.get_db()
    item = database.execute("SELECT id FROM homework WHERE id = ?", (homework_id,)).fetchone()
    if item is None:
        abort(404)
    database.execute(
        """
        UPDATE homework SET status = 'reviewed', teacher_feedback = ?,
                            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (feedback, homework_id),
    )
    database.commit()
    flash("Homework feedback was saved.", "success")
    return redirect(url_for("homework_detail", homework_id=homework_id))


if __name__ == "__main__":
    app.run(debug=True)
