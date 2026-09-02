import os
from datetime import date

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

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


def ensure_resources_table():
    database = db.get_db()

    database.execute(
        """
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            subject TEXT,
            url TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    database.commit()


def ensure_progress_table():
    database = db.get_db()

    database.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            progress_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            improvement TEXT NOT NULL,
            needs_work TEXT,
            confidence INTEGER NOT NULL DEFAULT 3,
            next_step TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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

                suffix = "" if days_late == 1 else "s"

                return f"Submitted {days_late} day{suffix} late"

        return "Submitted"

    days_overdue = (
        date.today() - date.fromisoformat(homework["due_date"])
    ).days

    if days_overdue > 0:
        suffix = "" if days_overdue == 1 else "s"
        return f"Overdue by {days_overdue} day{suffix}"

    return "Assigned"


def homework_context(rows):
    items = []

    for row in rows:
        item = dict(row)
        item["display_status"] = homework_display_status(row)
        item["status_key"] = row["status"]

        due_date = date.fromisoformat(row["due_date"])

        if row["status"] == "assigned" and due_date < date.today():
            item["status_key"] = "overdue"

        elif row["status"] == "submitted":
            submitted_date = (
                row["submitted_at"][:10]
                if row["submitted_at"]
                else ""
            )

            if submitted_date > row["due_date"]:
                item["status_key"] = "late"
            else:
                item["status_key"] = "submitted"

        items.append(item)

    return items


@app.before_request
def prepare_database_tables():
    if request.endpoint != "static":
        ensure_homework_table()
        ensure_resources_table()
        ensure_progress_table()


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
                error=(
                    "Please complete name, grade, subjects, and school."
                ),
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

        flash(
            f"{student_name} was added as a student.",
            "success",
        )

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
        values = {
            "name": request.form.get("name", "").strip(),
            "grade": request.form.get("grade", "").strip(),
            "subjects": request.form.get("subjects", "").strip(),
            "school": request.form.get("school", "").strip(),
            "learning_goal": request.form.get(
                "learning_goal",
                "",
            ).strip(),
            "current_level": request.form.get(
                "current_level",
                "",
            ).strip(),
            "strengths": request.form.get(
                "strengths",
                "",
            ).strip(),
            "areas_to_improve": request.form.get(
                "areas_to_improve",
                "",
            ).strip(),
            "tutor_notes": request.form.get(
                "tutor_notes",
                "",
            ).strip(),
        }

        if (
            not values["name"]
            or not values["grade"]
            or not values["subjects"]
            or not values["school"]
        ):
            return render_template(
                "student_editpage.html",
                student=student,
                error=(
                    "Please complete name, grade, subjects, and school."
                ),
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
                values["name"],
                values["grade"],
                values["subjects"],
                values["school"],
                values["learning_goal"],
                values["current_level"],
                values["strengths"],
                values["areas_to_improve"],
                values["tutor_notes"],
                student_id,
            ),
        )

        database.commit()

        flash(
            f"{values['name']}'s profile was updated.",
            "success",
        )

        return redirect(
            url_for(
                "student_profile",
                student_id=student_id,
            )
        )

    return render_template(
        "student_editpage.html",
        student=student,
    )


@app.route(
    "/students/<int:student_id>/archive",
    methods=["POST"],
)
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
        f"{student['name']} was archived. "
        "Their profile and history were kept.",
        "success",
    )

    return redirect(
        url_for(
            "student_profile",
            student_id=student_id,
        )
    )


@app.route(
    "/students/<int:student_id>/restore",
    methods=["POST"],
)
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
        url_for(
            "student_profile",
            student_id=student_id,
        )
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

    selected_student_id = request.args.get(
        "student_id",
        type=int,
    )

    if request.method == "POST":
        student_id = request.form.get(
            "student_id",
            "",
        ).strip()
        subject = request.form.get(
            "subject",
            "",
        ).strip()
        session_date = request.form.get(
            "session_date",
            "",
        ).strip()
        start_time = request.form.get(
            "start_time",
            "",
        ).strip()
        duration_minutes = request.form.get(
            "duration_minutes",
            "",
        ).strip()
        notes = request.form.get(
            "notes",
            "",
        ).strip()

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
                error=(
                    "Please choose a student and enter a valid duration."
                ),
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


@app.route("/homework")
def homework():
    database = db.get_db()

    filter_name = request.args.get(
        "status",
        "all",
    )

    rows = database.execute(
        """
        SELECT
            homework.*,
            students.name AS student_name
        FROM homework
        JOIN students
            ON homework.student_id = students.id
        ORDER BY homework.due_date ASC, homework.id DESC
        """
    ).fetchall()

    homework_items = homework_context(rows)

    allowed_filters = {
        "assigned",
        "overdue",
        "submitted",
        "reviewed",
    }

    if filter_name in allowed_filters:
        homework_items = [
            item
            for item in homework_items
            if item["status_key"] == filter_name
        ]

    return render_template(
        "homework.html",
        homework=homework_items,
        active_filter=filter_name,
    )


@app.route("/homework/add", methods=["GET", "POST"])
def add_homework():
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

    if request.method == "POST":
        student_id = request.form.get(
            "student_id",
            "",
        ).strip()
        title = request.form.get(
            "title",
            "",
        ).strip()
        description = request.form.get(
            "description",
            "",
        ).strip()
        due_date = request.form.get(
            "due_date",
            "",
        ).strip()

        if (
            not student_id
            or not title
            or not description
            or not due_date
        ):
            return render_template(
                "add_homework.html",
                students=active_students,
                error=(
                    "Please complete student, title, description, "
                    "and due date."
                ),
            )

        try:
            student_id = int(student_id)
            date.fromisoformat(due_date)
        except ValueError:
            return render_template(
                "add_homework.html",
                students=active_students,
                error="Please choose a valid student and due date.",
            )

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
                "add_homework.html",
                students=active_students,
                error="Please choose an active student.",
            )

        database.execute(
            """
            INSERT INTO homework (
                student_id,
                title,
                description,
                due_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                student_id,
                title,
                description,
                due_date,
            ),
        )

        database.commit()

        flash(
            f"Homework was assigned to {student['name']}.",
            "success",
        )

        return redirect(url_for("homework"))

    return render_template(
        "add_homework.html",
        students=active_students,
    )


@app.route("/homework/<int:homework_id>")
def homework_detail(homework_id):
    database = db.get_db()

    item = database.execute(
        """
        SELECT
            homework.*,
            students.name AS student_name
        FROM homework
        JOIN students
            ON homework.student_id = students.id
        WHERE homework.id = ?
        """,
        (homework_id,),
    ).fetchone()

    if item is None:
        abort(404)

    item = dict(item)
    item["display_status"] = homework_display_status(item)

    return render_template(
        "homework_detail.html",
        homework=item,
    )


@app.route(
    "/homework/<int:homework_id>/submit",
    methods=["POST"],
)
def submit_homework(homework_id):
    database = db.get_db()

    item = database.execute(
        """
        SELECT id
        FROM homework
        WHERE id = ?
        """,
        (homework_id,),
    ).fetchone()

    if item is None:
        abort(404)

    database.execute(
        """
        UPDATE homework
        SET
            status = 'submitted',
            submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (homework_id,),
    )

    database.commit()

    flash(
        "Homework was marked as submitted.",
        "success",
    )

    return redirect(
        url_for(
            "homework_detail",
            homework_id=homework_id,
        )
    )


@app.route(
    "/homework/<int:homework_id>/review",
    methods=["POST"],
)
def review_homework(homework_id):
    feedback = request.form.get(
        "teacher_feedback",
        "",
    ).strip()

    if not feedback:
        flash(
            "Please write feedback before marking homework as reviewed.",
            "error",
        )

        return redirect(
            url_for(
                "homework_detail",
                homework_id=homework_id,
            )
        )

    database = db.get_db()

    item = database.execute(
        """
        SELECT id
        FROM homework
        WHERE id = ?
        """,
        (homework_id,),
    ).fetchone()

    if item is None:
        abort(404)

    database.execute(
        """
        UPDATE homework
        SET
            status = 'reviewed',
            teacher_feedback = ?,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            feedback,
            homework_id,
        ),
    )

    database.commit()

    flash(
        "Homework feedback was saved.",
        "success",
    )

    return redirect(
        url_for(
            "homework_detail",
            homework_id=homework_id,
        )
    )


@app.route("/resources")
def resources():
    database = db.get_db()

    resource_type = request.args.get(
        "type",
        "all",
    )

    rows = database.execute(
        """
        SELECT
            id,
            title,
            resource_type,
            subject,
            url,
            description,
            created_at
        FROM resources
        ORDER BY title ASC
        """
    ).fetchall()

    resource_list = rows

    if resource_type != "all":
        resource_list = [
            resource
            for resource in rows
            if resource["resource_type"] == resource_type
        ]

    resource_types = database.execute(
        """
        SELECT DISTINCT resource_type
        FROM resources
        WHERE resource_type IS NOT NULL
          AND resource_type != ''
        ORDER BY resource_type ASC
        """
    ).fetchall()

    return render_template(
        "resources.html",
        resources=resource_list,
        resource_types=resource_types,
        active_type=resource_type,
    )


@app.route("/resources/add", methods=["GET", "POST"])
def add_resource():
    if request.method == "POST":
        title = request.form.get(
            "title",
            "",
        ).strip()
        resource_type = request.form.get(
            "resource_type",
            "",
        ).strip()
        subject = request.form.get(
            "subject",
            "",
        ).strip()
        url = request.form.get(
            "url",
            "",
        ).strip()
        description = request.form.get(
            "description",
            "",
        ).strip()

        if not title or not resource_type:
            return render_template(
                "add_resource.html",
                error=(
                    "Please complete the title and resource type."
                ),
            )

        database = db.get_db()

        database.execute(
            """
            INSERT INTO resources (
                title,
                resource_type,
                subject,
                url,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                resource_type,
                subject,
                url,
                description,
            ),
        )

        database.commit()

        flash(
            f"{title} was added to Resources.",
            "success",
        )

        return redirect(url_for("resources"))

    return render_template("add_resource.html")


@app.route("/resources/<int:resource_id>")
def resource_detail(resource_id):
    database = db.get_db()

    resource = database.execute(
        """
        SELECT
            id,
            title,
            resource_type,
            subject,
            url,
            description,
            created_at
        FROM resources
        WHERE id = ?
        """,
        (resource_id,),
    ).fetchone()

    if resource is None:
        abort(404)

    linked_homework = database.execute(
        """
        SELECT
            id,
            title,
            due_date,
            status
        FROM homework
        WHERE resource_id = ?
        ORDER BY due_date ASC
        """,
        (resource_id,),
    ).fetchall()

    return render_template(
        "resource_detail.html",
        resource=resource,
        linked_homework=linked_homework,
    )


@app.route("/progress")
def progress():
    database = db.get_db()

    progress_rows = database.execute(
        """
        SELECT
            progress.id,
            progress.progress_date,
            progress.topic,
            progress.improvement,
            progress.needs_work,
            progress.confidence,
            progress.next_step,
            students.name AS student_name
        FROM progress
        JOIN students
            ON progress.student_id = students.id
        ORDER BY progress.progress_date DESC, progress.id DESC
        """
    ).fetchall()

    return render_template(
        "progress.html",
        progress=progress_rows,
    )


@app.route("/progress/add", methods=["GET", "POST"])
def add_progress():
    database = db.get_db()

    active_students = database.execute(
        """
        SELECT
            id,
            name,
            grade
        FROM students
        WHERE status = 'active'
        ORDER BY name ASC
        """
    ).fetchall()

    if request.method == "POST":
        student_id = request.form.get(
            "student_id",
            "",
        ).strip()
        progress_date = request.form.get(
            "progress_date",
            "",
        ).strip()
        topic = request.form.get(
            "topic",
            "",
        ).strip()
        improvement = request.form.get(
            "improvement",
            "",
        ).strip()
        needs_work = request.form.get(
            "needs_work",
            "",
        ).strip()
        confidence = request.form.get(
            "confidence",
            "",
        ).strip()
        next_step = request.form.get(
            "next_step",
            "",
        ).strip()

        if (
            not student_id
            or not progress_date
            or not topic
            or not improvement
            or not confidence
        ):
            return render_template(
                "add_progress.html",
                students=active_students,
                error=(
                    "Please complete student, date, topic, improvement, "
                    "and confidence."
                ),
            )

        try:
            student_id = int(student_id)
            date.fromisoformat(progress_date)
            confidence = int(confidence)
        except ValueError:
            return render_template(
                "add_progress.html",
                students=active_students,
                error="Please enter valid progress information.",
            )

        if confidence < 1 or confidence > 5:
            return render_template(
                "add_progress.html",
                students=active_students,
                error="Confidence must be between 1 and 5.",
            )

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
                "add_progress.html",
                students=active_students,
                error="Please choose an active student.",
            )

        database.execute(
            """
            INSERT INTO progress (
                student_id,
                progress_date,
                topic,
                improvement,
                needs_work,
                confidence,
                next_step
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                progress_date,
                topic,
                improvement,
                needs_work,
                confidence,
                next_step,
            ),
        )

        database.commit()

        flash(
            f"Progress note was added for {student['name']}.",
            "success",
        )

        return redirect(url_for("progress"))

    return render_template(
        "add_progress.html",
        students=active_students,
    )


@app.route("/progress/<int:progress_id>")
def progress_detail(progress_id):
    database = db.get_db()

    progress_note = database.execute(
        """
        SELECT
            progress.id,
            progress.progress_date,
            progress.topic,
            progress.improvement,
            progress.needs_work,
            progress.confidence,
            progress.next_step,
            students.name AS student_name
        FROM progress
        JOIN students
            ON progress.student_id = students.id
        WHERE progress.id = ?
        """,
        (progress_id,),
    ).fetchone()

    if progress_note is None:
        abort(404)

    return render_template(
        "progress_detail.html",
        progress=progress_note,
    )


@app.route("/reports")
def reports():
    database = db.get_db()

    student_list = database.execute(
        """
        SELECT
            id,
            name,
            grade
        FROM students
        WHERE status = 'active'
        ORDER BY name ASC
        """
    ).fetchall()

    selected_student_id = request.args.get(
        "student_id",
        type=int,
    )

    start_date = request.args.get(
        "start_date",
        "",
    )

    end_date = request.args.get(
        "end_date",
        "",
    )

    report = None

    if selected_student_id and start_date and end_date:
        try:
            date.fromisoformat(start_date)
            date.fromisoformat(end_date)
        except ValueError:
            return render_template(
                "reports.html",
                students=student_list,
                selected_student_id=selected_student_id,
                start_date=start_date,
                end_date=end_date,
                error="Please choose valid dates.",
            )

        student = database.execute(
            """
            SELECT
                id,
                name,
                grade,
                subjects,
                learning_goal
            FROM students
            WHERE id = ?
            """,
            (selected_student_id,),
        ).fetchone()

        if student is None:
            abort(404)

        sessions = database.execute(
            """
            SELECT
                subject,
                session_date,
                start_time,
                duration_minutes,
                notes
            FROM sessions
            WHERE student_id = ?
              AND session_date BETWEEN ? AND ?
            ORDER BY session_date ASC, start_time ASC
            """,
            (
                selected_student_id,
                start_date,
                end_date,
            ),
        ).fetchall()

        progress_notes = database.execute(
            """
            SELECT
                progress_date,
                topic,
                improvement,
                needs_work,
                confidence,
                next_step
            FROM progress
            WHERE student_id = ?
              AND progress_date BETWEEN ? AND ?
            ORDER BY progress_date ASC, id ASC
            """,
            (
                selected_student_id,
                start_date,
                end_date,
            ),
        ).fetchall()

        homework_items = database.execute(
            """
            SELECT
                title,
                due_date,
                status,
                submitted_at,
                teacher_feedback
            FROM homework
            WHERE student_id = ?
              AND (
                  due_date BETWEEN ? AND ?
                  OR submitted_at BETWEEN ? AND ?
              )
            ORDER BY due_date ASC
            """,
            (
                selected_student_id,
                start_date,
                end_date,
                start_date,
                end_date,
            ),
        ).fetchall()

        confidence_values = [
            item["confidence"]
            for item in progress_notes
            if item["confidence"] is not None
        ]

        average_confidence = None

        if confidence_values:
            average_confidence = round(
                sum(confidence_values) / len(confidence_values),
                1,
            )

        report = {
            "student": student,
            "sessions": sessions,
            "progress_notes": progress_notes,
            "homework": homework_items,
            "average_confidence": average_confidence,
            "start_date": start_date,
            "end_date": end_date,
        }

    return render_template(
        "reports.html",
        students=student_list,
        selected_student_id=selected_student_id,
        start_date=start_date,
        end_date=end_date,
        report=report,
    )


if __name__ == "__main__":
    app.run(debug=True)