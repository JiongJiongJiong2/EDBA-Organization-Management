# oconvener/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from werkzeug.utils import secure_filename
import requests
import sqlite3
import uuid
import sys  
import os  
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Service, CourseInformation, BankAccount
from db_utils import validate_email_pattern

import json

# 配置上传文件存储
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    return redirect(url_for('user.organization_list_student', service_type='S'))

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

@oconvener_bp.route('/update-member-fund/<int:member_id>', methods=['POST'])
def update_member_fund(member_id):
    """Update member fund by O-Convener"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can manage member funds', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('user.organization_list_student', service_type='S'))
    
    try:
        new_fund = int(request.form.get('fund', 0))
        if new_fund < 0:
            flash('Fund value cannot be negative', 'error')
        else:
            member.fund = new_fund
            db.session.commit()
            flash('Member fund updated successfully', 'success')
    except ValueError:
        flash('Invalid fund value', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating member fund: {str(e)}', 'error')
    
    return redirect(url_for('user.organization_list_student', service_type='S'))

@oconvener_bp.route('/add-member', methods=['POST'])
def add_member():
    """Add new member to organization by O-Convener"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can add members', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        email = request.form.get('email')
        user_type = request.form.get('user_type')
        
        # Validate user type
        if user_type not in ['PP', 'PC', 'CC']:
            flash('Invalid user type', 'error')
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        # Check if email already exists
        existing_member = db.session.execute(
            db.select(Member).filter_by(email=email)
        ).scalar_one_or_none()
        
        if existing_member:
            flash('A member with this email already exists', 'error')
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        # Create new member
        new_member = Member(
            email=email,
            user_type=user_type,
            organization_id=oc.organization_id,
            fund=0  # Initial fund value
        )
        db.session.add(new_member)
        db.session.commit()
        flash('New member added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding member: {str(e)}', 'error')
    
    return redirect(url_for('user.organization_list_student', service_type='S'))

@oconvener_bp.route('/edit-member/<int:member_id>', methods=['POST'])
def edit_member(member_id):
    """Edit member details by O-Convener"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can edit members', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('user.organization_list_student', service_type='S'))
    
    try:
        email = request.form.get('email')
        user_type = request.form.get('user_type')
        
        # Validate user type
        if user_type not in ['PP', 'PC', 'CC']:
            flash('Invalid user type', 'error')
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        # Check if email already exists for different member
        existing_member = db.session.execute(
            db.select(Member).filter_by(email=email)
        ).scalar_one_or_none()
        if existing_member and existing_member.user_id != member_id:
            flash('A member with this email already exists', 'error')
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        # Update member details
        member.email = email
        member.user_type = user_type
        db.session.commit()
        flash('Member details updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating member: {str(e)}', 'error')
    
    return redirect(url_for('user.organization_list_student', service_type='S'))

@oconvener_bp.route('/delete-member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    """Delete member by O-Convener"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can delete members', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('user.organization_list_student', service_type='S'))
    
    try:
        # Prevent OC from deleting themselves
        if member.user_id == oc.user_id:
            flash('O-Conveners cannot delete themselves', 'error')
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        # Delete the member
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting member: {str(e)}', 'error')
    
    return redirect(url_for('user.organization_list_student', service_type='S'))

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

@oconvener_bp.route('/release-service/<int:service_id>', methods=['POST'])
def release_service(service_id):
    """Release a service for PC users"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can release services', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    service = db.session.get(Service, service_id)
    if not service or service.organization_id != user.organization_id:
        flash('Service not found or you do not have permission', 'error')
        return redirect(url_for('oconvener.configuration_interface', organization_id=user.organization_id))
    
    try:
        if service.status == 2:  # 只有状态为2的服务可以发布
            service.status = 3
            db.session.commit()
            flash('Service has been released successfully', 'success')
        else:
            flash('Only configured services can be released', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error releasing service: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

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
        except json.JSONDecodeError:
            flash('Invalid JSON format in inputs or outputs', 'error')
            return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

        # Update service status
        if service.status == 3:
            service.status = 2  # If service is in status 3 and being edited, change it back to status 2
        elif service.status == 1:
            service.status = 2  # When initial configuration is complete, update status to 2
        
        db.session.commit()
        flash('Service configuration updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service configuration: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

@oconvener_bp.route('/batch-import-members', methods=['POST'])
def batch_import_members():
    """Batch import members from Excel file"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can import members', 'error')
        return redirect(url_for('user.dashboard'))
    
    if 'members_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('user.organization_list_student', service_type='S'))
    
    file = request.files['members_file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid file format. Please upload an Excel (.xlsx) file', 'error')
        return redirect(url_for('user.organization_list_student', service_type='S'))
    
    try:
        # 保存上传的文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # 读取Excel文件
        df = pd.read_excel(filepath)
        
        # 验证必需的列是否存在
        required_columns = ['email', 'user_type', 'fund']
        if not all(col in df.columns for col in required_columns):
            flash('Excel file must contain email, user_type, and fund columns', 'error')
            os.remove(filepath)
            return redirect(url_for('user.organization_list_student', service_type='S'))
        
        success_count = 0
        error_count = 0
        
        # 开始批处理
        for _, row in df.iterrows():
            try:
                # 验证数据
                if not row['email'] or not isinstance(row['email'], str):
                    error_count += 1
                    continue

                # 验证邮箱格式
                if not validate_email_pattern(row['email']):
                    error_count += 1
                    continue
                    
                if not isinstance(row['fund'], (int, float)) or row['fund'] < 0:
                    error_count += 1
                    continue
                    
                if row['user_type'] not in ['PP', 'PC', 'CC']:
                    error_count += 1
                    continue
                
                # 如果是通配符邮箱模式，直接创建/更新
                if '*@' in row['email']:
                    existing_member = db.session.execute(
                        db.select(Member).filter_by(email=row['email'])
                    ).scalar_one_or_none()
                    
                    if existing_member:
                        # 更新已存在的通配符规则
                        existing_member.user_type = row['user_type']
                        existing_member.fund = int(row['fund'])
                    else:
                        # 创建新的通配符规则
                        new_member = Member(
                            email=row['email'],
                            user_type=row['user_type'],
                            organization_id=oc.organization_id,
                            fund=int(row['fund'])
                        )
                        db.session.add(new_member)
                else:
                    # 处理普通邮箱
                    existing_member = db.session.execute(
                        db.select(Member).filter_by(email=row['email'])
                    ).scalar_one_or_none()
                    
                    if existing_member:
                        # 更新已存在的成员
                        existing_member.user_type = row['user_type']
                        existing_member.fund = int(row['fund'])
                    else:
                        # 创建新成员
                        new_member = Member(
                            email=row['email'],
                            user_type=row['user_type'],
                            organization_id=oc.organization_id,
                            fund=int(row['fund'])
                        )
                        db.session.add(new_member)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        db.session.commit()
        
        # 删除上传的文件
        os.remove(filepath)
        
        flash(f'Successfully processed {success_count} members. {error_count} errors encountered.', 
              'success' if error_count == 0 else 'warning')
        
    except Exception as e:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('user.organization_list_student', service_type='S'))

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
