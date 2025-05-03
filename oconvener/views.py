# oconvener/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from werkzeug.utils import secure_filename
import requests
import sqlite3
import uuid
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Service, CourseInformation, BankAccount

import json

# Database connection function for legacy code
# Add payment service check function
def check_payment_service(organization_id):
    # Query for organization's payment service
    payment_service = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.service_type == 'M')
        .filter(Service.status == 2)
    ).scalar_one_or_none()
    
    return payment_service is not None

def process_payment(from_org_id, to_org_id, amount):
    try:
        # Get payment service for sending organization
        payment_service = db.session.execute(
            db.select(Service)
            .filter(Service.organization_id == from_org_id)
            .filter(Service.service_type == 'M')
            .filter(Service.status == 2)
        ).scalar_one_or_none()
        
        if not payment_service:
            return False, "No transfer service available"
        
        # Get bank account info for both parties
        from_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == from_org_id)
        ).scalar_one_or_none()
        
        to_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == to_org_id)
        ).scalar_one_or_none()
        
        if not from_account or not to_account:
            return False, "Bank account information not found"
        
        # Prepare payment request data
        payment_data = {
            "from_bank": from_account.bank,
            "from_name": from_account.name,
            "from_account": from_account.number,
            "password": from_account.password,
            "to_bank": to_account.bank,
            "to_name": to_account.name,
            "to_account": to_account.number,
            "amount": amount
        }
        
        # Send payment request
        url = payment_service.url + payment_service.path
        response = requests.post(url, json=payment_data)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, "Payment failed"
            
    except Exception as e:
        return False, str(e)

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

@oconvener_bp.route('/manage-services/<int:organization_id>')
def manage_services(organization_id):
    """Service management interface for O-Convener"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can manage services', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    # Get all services for the organization
    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .order_by(Service.service_type)
    ).scalars().all()
    
    return render_template('service_management.html',
                         services=services,
                         user=user)

@oconvener_bp.route('/update-service-status/<int:service_id>', methods=['POST'])
def update_service_status(service_id):
    """Update service status by O-Convener"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'}), 401
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    service = db.session.get(Service, service_id)
    if not service:
        return jsonify({'status': 'error', 'message': 'Service not found'}), 404
    
    try:
        new_status = int(request.form.get('status', 0))
        is_paid = request.form.get('is_paid') is not None
        cost = 0

        # Only allow setting status to 0 or 1
        if new_status not in [0, 1]:
            flash('Invalid status value', 'error')
            return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))

        if is_paid:
            try:
                cost = int(request.form.get('cost', 0))
                if cost <= 0:
                    flash('Price must be a positive number', 'error')
                    return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))
            except ValueError:
                flash('Invalid price value', 'error')
                return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))
        
        service.status = new_status
        service.cost = cost
        db.session.commit()
        flash('Service status and price updated successfully', 'success')
            
    except ValueError:
        flash('Invalid input values', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service status: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))

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

@oconvener_bp.route('/check_payment_service/<int:organization_id>')
def check_payment_service_route(organization_id):
    """Check if an organization has payment service available"""
    has_service = check_payment_service(organization_id)
    return jsonify({'hasPaymentService': has_service})

@oconvener_bp.route('/configuration/<int:organization_id>')
def configuration_interface(organization_id):
    """Configuration interface for services"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Verify user has permission (must be PP of this organization)
    if user.user_type != 'PP' or user.organization_id != organization_id:
        flash('You do not have permission to configure services for this organization', 'error')
        return redirect(url_for('user.dashboard', user_type=user.user_type))
    
    # For providers, only show status 1 services from their organization
    # For others, show both status 1 and 2 services
    if user.user_type == 'PP':
        services = db.session.execute(
            db.select(Service)
            .filter(Service.organization_id == organization_id)
            .filter(Service.status == 1)
            .order_by(Service.service_type)
        ).scalars().all()
    else:
        services = db.session.execute(
            db.select(Service)
            .filter(Service.organization_id == organization_id)
            .filter(Service.status.in_([1, 2]))
            .order_by(Service.service_type)
        ).scalars().all()
    
    return render_template('configuration_interface.html',
                         services=services,
                         user=user)

@oconvener_bp.route('/submit_configuration/<int:service_id>', methods=['POST'])
def submit_configuration(service_id):
    """Submit service configuration"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
        
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP' or user.organization_id != service.organization_id:
        flash('You do not have permission to configure this service', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    try:
        import json
        # Update service configuration
        service.url = request.form.get('url', '')
        service.path = request.form.get('path', '')
        service.method = request.form.get('method', 'POST')
        
        # Parse and validate JSON input
        try:
            input_json = json.loads(request.form.get('input_json', '{}'))
            output_json = json.loads(request.form.get('output_json', '{}'))
            service.input_json = input_json
            service.output_json = output_json
            
            # When configuration is complete, update status to 2 (Active)
            if service.status == 1:
                service.status = 2
        except json.JSONDecodeError:
            flash('Invalid JSON format in inputs or outputs', 'error')
            return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))
        
        db.session.commit()
        flash('Service configuration updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service configuration: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

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
