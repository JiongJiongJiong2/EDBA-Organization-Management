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
    conn = sqlite3.connect('yourdatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

oconvener_bp = Blueprint('oconvener', __name__)

# Legacy routes from part1_app.py
@oconvener_bp.route('/account/a')
def account_a():
    return render_template('oc_workspace_bank_auth.html')

@oconvener_bp.route('/bank/authenticate', methods=['POST'])
def bank_authenticate():
    try:
        data = request.json
        required_fields = ["bank", "account_name", "account_number", "password"]

        if not data or not all(field in data for field in required_fields):
            return jsonify({"status": "fail", "reason": "Missing fields"}), 400

        external_api_url = "http://172.16.160.88:8001/hw/bank/authenticate"
        response = requests.post(external_api_url, json=data)

        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@oconvener_bp.route('/list/a')
def list_a():
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
        return f"<h2>Error reading member data: {e}</h2>"

@oconvener_bp.route('/service/a')
def service_a():
    org_id = 1  # Example, should be read from session
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT enabled FROM service_settings
        WHERE org_id = ? AND service_name = 'course_info'
    """, (org_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        return '<h2>Course information sharing service is enabled</h2>'
    else:
        return '<h2>Course information sharing service is currently disabled</h2>'

@oconvener_bp.route('/service/a/settings', methods=['GET', 'POST'])
def course_service_settings():
    org_id = 1  # Example
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

    checked_attr = 'checked' if current_status else ''
    return f"""
        <h2>Course Information Sharing Settings</h2>
        <form method="POST">
            <label>
                <input type="checkbox" name="enabled" {checked_attr}>
                Enable Course Information Sharing Service
            </label>
            <br><br>
            <button type="submit">Save Settings</button>
        </form>
    """

@oconvener_bp.route('/service/b')
def service_b():
    return render_template('oc_workspace_student_auth.html')

@oconvener_bp.route('/student/authenticate', methods=['POST'])
def student_authenticate():
    try:
        name = request.form.get('name')
        student_id = request.form.get('id')
        photo = request.files.get('photo')

        if not all([name, student_id, photo]):
            return jsonify({"status": "fail", "reason": "Missing fields"}), 400

        files = {'photo': (secure_filename(photo.filename), photo.stream, photo.mimetype)}
        data = {'name': name, 'id': student_id}
        api_url = 'http://172.16.160.88:8001/hw/student/authenticate'

        response = requests.post(api_url, data=data, files=files)
        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@oconvener_bp.route('/service/c', methods=['POST', 'GET'])
def service_c():
    try:
        response = requests.post("http://172.16.160.88:8001/hw/thesis/search", json={"keywords": ""})
        thesis_results = response.json() if isinstance(response.json(), list) else [response.json()]
    except Exception as e:
        return f"<h2>Failed to get thesis data: {e}</h2>"

    html_output = "<h2>Thesis Sharing</h2><hr>"
    for thesis in thesis_results:
        title = thesis.get('title', 'No Title')
        abstract = thesis.get('abstract', 'No Abstract')
        html_output += f"<h4>{title}</h4><p>{abstract}</p><hr>"

    return html_output

@oconvener_bp.route('/service/d', methods=['GET', 'POST'])
def service_d():
    org_id = request.args.get('org_id', type=int)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, description, is_paid, price 
        FROM thesis_services 
        WHERE visible = 1 OR org_id = ?
    """, (org_id,))

    services = cursor.fetchall()
    conn.close()

    html_output = "<h2>Thesis Download Service</h2><hr>"
    for service in services:
        service_id, title, description, is_paid, price = service
        html_output += f"<h4>{title}</h4><p>{description}</p>"
        if is_paid:
            html_output += f"<p><strong>Price：</strong>¥{price}</p>"
            html_output += f"<form action='/purchase_service' method='POST'><input type='hidden' name='service_id' value='{service_id}'><button type='submit'>Pay to Download</button></form>"
        else:
            html_output += f"<form action='/download_service' method='GET'><input type='hidden' name='service_id' value='{service_id}'><button type='submit'>Free Download</button></form>"
        html_output += "<hr>"

    return html_output

@oconvener_bp.route('/')
def index():
    return redirect(url_for('oconvener.workspace'))

@oconvener_bp.route('/workspace')
def workspace():
    return render_template('oc_workspace_oc-workspace.html')

@oconvener_bp.route('/questions/a', methods=['GET', 'POST'])
def question_a():
    if request.method == 'POST':
        try:
            description = request.form.get('description', '')
            sender_id = request.form.get('sender_id', '')
            
            if not description or not sender_id:
                return jsonify({'success': False, 'message': 'Please fill in all information'})
            
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
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    current_user_id = request.args.get('user_id', '')
    
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
                         current_user_id=current_user_id,
                         search_query=search_query)

# 服务配置界面（列出当前组织所有服务）
@oconvener_bp.route('/configuration-interface/<int:organization_id>')
def configuration_interface(organization_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    if user.organization_id != organization_id:
        flash('You do not have permission to access this organization', 'error')
        return redirect(url_for('user.dashboard', user_type=user.user_type))

    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.status.in_([1, 2]))
        .order_by(Service.service_type)
    ).scalars().all()

    return render_template('configuration_interface.html',
                           services=services,
                           user=user)

# 提交服务配置
@oconvener_bp.route('/submit-configuration/<int:service_id>', methods=['POST'])
def submit_configuration(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    try:
        # 更新服务配置
        service.url = request.form.get('url', '')
        service.path = request.form.get('path', '')
        service.method = request.form.get('method', 'POST')

        try:
            input_json = json.loads(request.form.get('input_json', '{}'))
            output_json = json.loads(request.form.get('output_json', '{}'))
            service.input_json = input_json
            service.output_json = output_json
        except json.JSONDecodeError:
            flash('Invalid JSON format in inputs or outputs', 'error')
            return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

        db.session.commit()
        flash('Service configuration updated successfully', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service configuration: {str(e)}', 'error')

    return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

# O-Convener添加课程信息
@oconvener_bp.route('/provide-course-info', methods=['GET', 'POST'])
def provide_course_info():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Unauthorized access', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    if request.method == 'POST':
        course_name = request.form.get('course_name')
        course_description = request.form.get('course_description')

        if not course_name:
            flash('Course name is required', 'error')
            return redirect(url_for('oconvener.provide_course_info'))

        try:
            new_course = CourseInformation(
                organization_id=user.organization_id,
                name=course_name,
                description=course_description
            )
            db.session.add(new_course)
            db.session.commit()
            flash('Course information has been successfully added', 'success')
            return redirect(url_for('user.dashboard', user_type=user.user_type))

        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add course information: {str(e)}', 'error')
            return redirect(url_for('oconvener.provide_course_info'))

    return render_template('provide_course_info.html')
