# oconvener/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
import requests
import sqlite3
import uuid
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Service, CourseInformation

import json

# Database connection function for legacy code
def get_db_connection():
    conn = sqlite3.connect('instance/EDBA.db')  # Updated path to match Flask's instance folder
    conn.row_factory = sqlite3.Row
    return conn

oconvener_bp = Blueprint('oconvener', __name__)

# Constants for external API endpoints
API_BASE_URL = "http://172.16.160.88:8001"
API_ENDPOINTS = {
    'bank_auth': f"{API_BASE_URL}/api/v1/bank/authenticate",
    'student_auth': f"{API_BASE_URL}/api/v1/student/authenticate",
    'thesis_search': f"{API_BASE_URL}/api/v1/thesis/search"
}

# Legacy routes from part1_app.py
@oconvener_bp.route('/account/a')
def account_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('oc_workspace_bank_auth.html')

@oconvener_bp.route('/bank/authenticate', methods=['POST'])
def bank_authenticate():
    try:
        data = request.json
        required_fields = ["bank", "account_name", "account_number", "password"]

        if not data or not all(field in data for field in required_fields):
            return jsonify({"status": "fail", "reason": "Missing required fields"}), 400

        response = requests.post(API_ENDPOINTS['bank_auth'], json=data)

        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@oconvener_bp.route('/list/a')
def list_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members")
        rows = cursor.fetchall()
        conn.close()

        table_html = "<h2>Member list</h2><table border='1'><tr>"
        col_names = [description[0] for description in cursor.description]
        for col in col_names:
            table_html += f"<th>{col}</th>"
        table_html += "</tr>"

        for row in rows:
            table_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        table_html += "</table>"

        return table_html

    except Exception as e:
        return f"<h2>Error reading member data: {e}</h2>"

@oconvener_bp.route('/information/a')
def information_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organizations")
        rows = cursor.fetchall()
        conn.close()

        table_html = "<h2>Organization Information</h2><table border='1'><tr>"
        col_names = [description[0] for description in cursor.description]
        for col in col_names:
            table_html += f"<th>{col}</th>"
        table_html += "</tr>"

        for row in rows:
            table_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        table_html += "</table>"

        return table_html

    except Exception as e:
        return f"<h2>Error reading organization data: {e}</h2>"

@oconvener_bp.route('/service/a')
def service_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    org_id = session.get('organization_id', 1)  # Get from session, fallback to 1
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT enabled FROM service_settings
        WHERE org_id = ? AND service_name = 'course_info'
    """, (org_id,))
    result = cursor.fetchone()
    conn.close()

    enabled = result[0] if result else False
    return render_template('course_info.html', enabled=enabled)

@oconvener_bp.route('/service/a/settings', methods=['GET', 'POST'])
def course_service_settings():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    org_id = session.get('organization_id', 1)  # Get from session, fallback to 1
    if request.method == 'POST':
        new_status = request.form.get('enabled') == 'on'
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO service_settings (org_id, service_name, enabled)
            VALUES (?, 'course_info', ?)
            ON CONFLICT(org_id, service_name) DO UPDATE SET enabled=excluded.enabled
        """, (org_id, int(new_status)))
        conn.commit()
        conn.close()
        return redirect(url_for('oconvener.course_service_settings'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT enabled FROM service_settings
        WHERE org_id = ? AND service_name = 'course_info'
    """, (org_id,))
    result = cursor.fetchone()
    current_status = bool(result[0]) if result else False
    conn.close()

    return render_template('course_settings.html', checked=current_status)

@oconvener_bp.route('/service/b')
def service_b():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('oc_workspace_student_auth.html')

@oconvener_bp.route('/student/authenticate', methods=['POST'])
def student_authenticate():
    if 'user_id' not in session:
        return jsonify({"status": "fail", "reason": "Not logged in"}), 401

    try:
        name = request.form.get('name')
        student_id = request.form.get('id')
        photo = request.files.get('photo')

        if not all([name, student_id, photo]):
            return jsonify({"status": "fail", "reason": "Missing required fields"}), 400

        files = {'photo': (secure_filename(photo.filename), photo.stream, photo.mimetype)}
        data = {'name': name, 'id': student_id}

        response = requests.post(API_ENDPOINTS['student_auth'], data=data, files=files)
        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@oconvener_bp.route('/service/c', methods=['POST', 'GET'])
def service_c():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    try:
        response = requests.post(API_ENDPOINTS['thesis_search'], json={"keywords": ""})
        thesis_results = response.json() if isinstance(response.json(), list) else [response.json()]
    except Exception as e:
        return f"<h2>Failed to get thesis data: {e}</h2>"

    return render_template('thesis_list.html', theses=thesis_results)

@oconvener_bp.route('/')
def index():
    return redirect(url_for('oconvener.workspace'))

@oconvener_bp.route('/workspace')
def workspace():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('oc_workspace_oc-workspace.html')

@oconvener_bp.route('/questions/a', methods=['GET', 'POST'])
def question_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        try:
            description = request.form.get('description', '')
            sender_id = session.get('user_id')
            
            if not description:
                return jsonify({'success': False, 'message': 'Question description is required'})
            
            conn = get_db_connection()
            question_id = str(uuid.uuid4())
            
            conn.execute("""
                INSERT INTO questions (question_id, description, sender_id, status, answer)
                VALUES (?, ?, ?, 0, '')
            """, (question_id, description, sender_id))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Question submitted successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Submission failed: {str(e)}'})
    
    return render_template('o-convener_question_a.html')

@oconvener_bp.route('/questions/b')
def question_b():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    search_query = request.args.get('search', '')
    current_user_id = session.get('user_id')
    
    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1 
        AND q.sender_id = ?
        AND (q.description LIKE ? OR m.email LIKE ? OR q.answer LIKE ?)
        """
        questions = conn.execute(query, (current_user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1 
        AND q.sender_id = ?
        """
        questions = conn.execute(query, (current_user_id,)).fetchall()
    
    conn.close()
    
    return render_template('o-convener_question_b.html', 
                         questions=questions,
                         search_query=search_query)
