import os

from flask import Flask, render_template

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


if __name__ == "__main__":
    app.run(debug=True)