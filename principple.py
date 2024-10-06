from flask import Flask, request, jsonify, g
import sqlite3
from datetime import datetime
import json
import pytest

app = Flask(__name__)
DATABASE = 'school.db'

# Utility functions to interact with the database
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize the database (this would typically be handled in a separate script)
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                role TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                student_id INTEGER,
                teacher_id INTEGER,
                status TEXT,  -- "draft", "submitted", "graded"
                grade TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        db.commit()

# Route for principal to view all teachers
@app.route('/principal/teachers', methods=['GET'])
def principal_view_teachers():
    principal_header = request.headers.get('X-Principal')
    if not principal_header or 'principal_id' not in eval(principal_header):
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT id, user_id, created_at, updated_at FROM users
        WHERE role = "teacher"
    ''')
    teachers = cursor.fetchall()
    return jsonify({"data": teachers}), 200

# Route for principal to view all submitted and graded assignments
@app.route('/principal/assignments', methods=['GET'])
def principal_view_assignments():
    principal_header = request.headers.get('X-Principal')
    if not principal_header or 'principal_id' not in eval(principal_header):
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM assignments 
        WHERE status IN ("submitted", "graded")
    ''')
    assignments = cursor.fetchall()
    return jsonify({"data": assignments}), 200

# Route for principal to grade or re-grade an assignment
@app.route('/principal/assignments/grade', methods=['POST'])
def principal_grade_assignment():
    principal_header = request.headers.get('X-Principal')
    if not principal_header or 'principal_id' not in eval(principal_header):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    assignment_id = data.get('id')
    new_grade = data.get('grade')

    if not assignment_id or not new_grade:
        return jsonify({"error": "Invalid input"}), 400

    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        UPDATE assignments 
        SET grade = ?, status = "graded", updated_at = ?
        WHERE id = ?
    ''', (new_grade, datetime.now().isoformat(), assignment_id))

    if cursor.rowcount == 0:
        return jsonify({"error": "Assignment not found"}), 404

    db.commit()
    return jsonify({"message": "Assignment graded"}), 200

# Route for students to create or edit a draft assignment
@app.route('/student/assignments', methods=['POST'])
def create_or_edit_assignment():
    student_id = request.json.get('student_id')
    title = request.json.get('title')
    content = request.json.get('content')
    assignment_id = request.json.get('assignment_id')

    db = get_db()
    cursor = db.cursor()

    if assignment_id:  # Edit existing draft
        cursor.execute(''' 
            UPDATE assignments SET title = ?, content = ?, updated_at = ? 
            WHERE id = ? AND student_id = ? AND status = "draft"
        ''', (title, content, datetime.now().isoformat(), assignment_id, student_id))
    else:  # Create new draft
        cursor.execute(''' 
            INSERT INTO assignments (title, content, student_id, status, created_at, updated_at) 
            VALUES (?, ?, ?, "draft", ?, ?)
        ''', (title, content, student_id, datetime.now().isoformat(), datetime.now().isoformat()))

    db.commit()
    return jsonify({"message": "Assignment saved"}), 201

# Route for students to list their assignments
@app.route('/student/<int:student_id>/assignments', methods=['GET'])
def list_student_assignments(student_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM assignments WHERE student_id = ?', (student_id,))
    assignments = cursor.fetchall()
    return jsonify(assignments)

# Route for students to submit an assignment
@app.route('/student/assignments/submit', methods=['POST'])
def submit_assignment():
    student_id = request.json.get('student_id')
    assignment_id = request.json.get('assignment_id')
    teacher_id = request.json.get('teacher_id')

    db = get_db()
    cursor = db.cursor()
    cursor.execute(''' 
        UPDATE assignments SET status = "submitted", teacher_id = ?, updated_at = ?
        WHERE id = ? AND status = "draft"
    ''', (teacher_id, datetime.now().isoformat(), assignment_id))
    db.commit()
    return jsonify({"message": "Assignment submitted"}), 200

# Route for teachers to list assignments submitted to them
@app.route('/teacher/<int:teacher_id>/assignments', methods=['GET'])
def list_teacher_assignments(teacher_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM assignments WHERE teacher_id = ? AND status = "submitted"', (teacher_id,))
    assignments = cursor.fetchall()
    return jsonify(assignments)

# Route for teachers to grade an assignment
@app.route('/teacher/assignments/grade', methods=['POST'])
def grade_assignment():
    assignment_id = request.json.get('assignment_id')
    grade = request.json.get('grade')
    db = get_db()
    cursor = db.cursor()
    cursor.execute(''' 
        UPDATE assignments SET grade = ?, status = "graded", updated_at = ?
        WHERE id = ? AND status = "submitted"
    ''', (grade, datetime.now().isoformat(), assignment_id))
    db.commit()
    return jsonify({"message": "Assignment graded"}), 200

if __name__ == '__main__':
    init_db()  # Initialize the database with tables
    app.run(debug=True)
