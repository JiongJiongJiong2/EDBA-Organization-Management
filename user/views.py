# user/views.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Organization, Service, Question, CourseInformation, Application, BankAccount

import requests
import io
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import send_file, Response
from functools import wraps

def validate_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_service_or_404(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return None
    return service

def process_payment(user_id, service_id, query_count=1):
    """Process payment for a service"""
    try:
        # Debug logging
        print(f"Processing payment for user {user_id}, service {service_id}, query count {query_count}")
        
        user = db.session.get(Member, user_id)
        service = db.session.get(Service, service_id)
        
        if not user or not service:
            print("Error: User or service not found")
            return False, "Invalid user or service"
        
        # Calculate total cost
        total_cost = service.cost * query_count
        print(f"Total cost: {total_cost}, User's fund: {user.fund}")
        
        # Check user's fund
        if user.fund < total_cost:
            print("Error: Insufficient funds")
            return False, "Your fund is not enough! Please connect with your O-convener."
            
        # Get payment service for both organizations
        payment_service_from = db.session.execute(
            db.select(Service)
            .filter_by(organization_id=user.organization_id)
            .filter_by(service_type='M')
            .filter_by(status=2)
        ).scalar_one_or_none()
        
        payment_service_to = db.session.execute(
            db.select(Service)
            .filter_by(organization_id=service.organization_id)
            .filter_by(service_type='M')
            .filter_by(status=2)
        ).scalar_one_or_none()
        
        print(f"Payment services - From: {payment_service_from}, To: {payment_service_to}")
        
        if not payment_service_from or not payment_service_to:
            print("Error: Payment service not configured")
            return False, "Payment service configuration not completed! Please connect with your O-convener."
            
        # Get bank accounts
        from_bank = db.session.execute(
            db.select(BankAccount)
            .filter_by(organization_id=user.organization_id)
        ).scalar_one_or_none()
        
        to_bank = db.session.execute(
            db.select(BankAccount)
            .filter_by(organization_id=service.organization_id)
        ).scalar_one_or_none()
        
        print(f"Bank accounts - From: {from_bank}, To: {to_bank}")
        
        if not from_bank or not to_bank:
            print("Error: Bank accounts not configured")
            return False, "Payment service configuration not completed! Please connect with your O-convener."
            
        # Prepare payment data
        payment_data = {
            "from_bank": from_bank.bank,
            "from_name": from_bank.name,
            "from_account": from_bank.number,
            "password": from_bank.password,
            "to_bank": to_bank.bank,
            "to_name": to_bank.name,
            "to_account": to_bank.number,
            "amount": total_cost
        }
        
        # Construct payment URL
        payment_url = payment_service_from.url.rstrip('/') + '/' + payment_service_from.path.lstrip('/')
        print(f"Sending payment request to: {payment_url}")
        
        # Send payment request
        response = requests.post(payment_url, json=payment_data)
        print(f"Payment response: {response.text}")
        
        try:
            response_data = response.json()
            if response_data.get("status") != "success":
                print(f"Payment failed: {response_data}")
                return False, "Payment failure! Please connect with your O-convener."
        except Exception as e:
            print(f"Error parsing payment response: {e}")
            return False, "Payment system error! Please connect with your O-convener."
            
        # Update user's fund
        user.fund -= total_cost
        db.session.commit()
        print(f"Payment successful, updated user fund to: {user.fund}")
        
        return True, None
        
    except Exception as e:
        db.session.rollback()
        return False, f"Payment error: {str(e)}"

user_bp = Blueprint('user', __name__)

# 用户的dashboard
@user_bp.route('/dashboard/<user_type>')
def dashboard(user_type):
    valid_types = ['OC', 'PP', 'PC', 'CC', 'EE', 'TT', 'SE']
    user_id = session.get('user_id')

    # First check if user_type is valid
    if user_type not in valid_types:
        flash('Invalid user type', 'danger')
        return redirect(url_for('auth.login'))

    # Then get the member information
    member = db.session.get(Member, user_id)
    if not member:
        flash('User information retrieval failed, please log in again', 'danger')
        return redirect(url_for('auth.login'))

    # Handle different user types
    if user_type == 'TT':
        return render_template('t-admin_main_page.html', user=member)
    elif user_type == 'EE':
        return render_template('e_admin_main.html', user=member)
    elif user_type == 'SE':
        return render_template('se_admin_user_management.html', user=member)
    elif user_type == 'OC':
        return render_template('oc_workspace_oc-workspace.html', user=member)
    else:
        return render_template('dashboard_data_user.html', user=member)

# 提交问题（寻求帮助）
@user_bp.route('/ask-for-help')
def ask_for_help():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    # Get all questions for the current user, ordered by newest first
    questions = db.session.execute(
        db.select(Question)
        .filter_by(sender_id=session['user_id'])
        .order_by(Question.question_id.desc())
    ).scalars().all()
    
    return render_template('ask_for_help.html', questions=questions)

@user_bp.route('/submit-question', methods=['POST'])
def submit_question():
    # Debug logging
    print("Received question submission request")
    print("Session data:", dict(session))
    print("Form data:", dict(request.form))

    if 'user_id' not in session:
        print("Error: No user_id in session")
        return jsonify({'status': 'error', 'message': 'Please login first'})

    title = request.form.get('title')
    description = request.form.get('description')
    
    # Validate input data
    if not title:
        print("Error: Missing title")
        return jsonify({'status': 'error', 'message': 'Question title is required'})
    if not description:
        print("Error: Missing description")
        return jsonify({'status': 'error', 'message': 'Question description is required'})
        
    # Check field lengths
    if len(title) > 100:
        print(f"Error: Title too long ({len(title)} chars)")
        return jsonify({'status': 'error', 'message': 'Question title cannot exceed 100 characters'})
    if len(description) > 255:
        print(f"Error: Description too long ({len(description)} chars)")
        return jsonify({'status': 'error', 'message': 'Question description cannot exceed 255 characters'})

    try:
        # Debug logging
        print(f"Creating new question for user {session['user_id']}")
        print(f"Title: {title}")
        print(f"Description: {description}")

        new_question = Question(
            title=title,
            description=description,
            sender_id=session['user_id'],
            status=0,
            answer=None,
            submit_time=db.func.current_timestamp()
        )
        db.session.add(new_question)
        db.session.commit()
        
        print("Question successfully added to database")
        
        return jsonify({
            'status': 'success',
            'message': 'Question has been sent successfully',
            'redirect_url': url_for('user.dashboard', user_type=session.get('user_type'))
        })
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Database error: {error_msg}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to submit question: {error_msg}'
        })

# 学生信息组织列表
@user_bp.route('/organization-list-student/<service_type>', methods=['GET', 'POST'])
def organization_list_student(service_type):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    # For OC users, show member management interface
    if user.user_type == 'OC':
        members = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=user.organization_id)
            .order_by(Member.user_type)
        ).scalars().all()
        return render_template('organization_list_student.html',
                             user=user,
                             members=members,
                             service_type='S')
    
    # For other users, show organization list
    if request.method == 'POST':
        organization_id = request.form.get('organization_id')
        if organization_id:
            # For PC and CC users, only show released services
            if user.user_type in ['PC', 'CC']:
                status_filter = 3
            else:
                status_filter = 2

            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == status_filter)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('user.student_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    # Filter services based on user type
    query = db.select(Organization).join(Service).filter(Service.service_type == service_type)
    
    # PC and CC users can only see released services
    if user.user_type in ['PC', 'CC']:
        query = query.filter(Service.status == 3)
    else:
        query = query.filter(Service.status == 2)

    organizations = db.session.execute(query.distinct()).scalars().all()
    
    return render_template('organization_list_student.html', 
                           organizations=organizations, 
                           service_type=service_type,
                           user=user,
                           user_id=session['user_id'])

# 查询学生信息
@user_bp.route('/student-inquiry/<int:service_id>', methods=['GET', 'POST'])
def student_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('student_inquiry.html', 
                           service=service,
                           user=user,
                           result=session.pop('inquiry_result', None))

@user_bp.route('/download_gpa_template/<int:service_id>')
@validate_session
def download_gpa_template(service_id):
    """Provide an Excel template for batch student inquiries"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    # Create DataFrame with column headers based on service.input_json
    columns = list(service.input_json.keys())
    df = pd.DataFrame(columns=columns)

    # Add a comment row for file type fields
    comments = {field_name: 'Place file in "files" folder and enter filename here' 
               for field_name, field_type in service.input_json.items() 
               if field_type == 'file'}
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Batch Query', index=False)
        worksheet = writer.sheets['Batch Query']
        
        # Add column width and format
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, max(len(col) + 2, 15))

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'student_inquiry_template_{service_id}.xlsx'
    )

@user_bp.route('/submit-inquiry/<int:service_id>', methods=['POST'])
def submit_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    print(f"Processing inquiry for service {service_id}")
    print(f"Form data: {request.form}")
    print(f"Files: {request.files}")
    print(f"Request method: {request.method}")
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    try:
        # Process payment first
        print("Processing payment...")
        success, error_message = process_payment(session['user_id'], service_id)
        if not success:
            flash(error_message, 'error')
            return redirect(url_for('user.student_inquiry', service_id=service_id))

        # Prepare inquiry data
        data = {}
        files = {}
        for field_name, field_type in service.input_json.items():
            if field_type == 'file':
                if field_name in request.files:
                    files[field_name] = request.files[field_name]
            else:
                data[field_name] = request.form.get(field_name, '')
        
        print(f"Prepared data: {data}")
        print(f"Files to upload: {list(files.keys())}")
        
        # Construct query URL
        service_url = service.url.rstrip('/')
        service_path = service.path.lstrip('/')
        url = f"{service_url}/{service_path}"
        print(f"Sending request to: {url}")
        
        if files:
            print("Sending request with files...")
            response = requests.post(url, data=data, files=files)
        else:
            print("Sending request with JSON data...")
            response = requests.post(url, json=data)
        
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        try:
            response_data = response.json()
            session['inquiry_result'] = response_data
        except Exception as e:
            print(f"Error parsing response: {e}")
            session['inquiry_result'] = {'error': 'Invalid response from service'}
        
        return redirect(url_for('user.student_inquiry', service_id=service_id))
        
    except Exception as e:
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

@user_bp.route('/download_template/<int:service_id>')
@validate_session
def download_template(service_id):
    """Provide an Excel template for batch student inquiries"""
    service = get_service_or_404(service_id)
    if not service:
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    if service.service_type == 'GPA':
        return redirect(url_for('user.download_gpa_template', service_id=service_id))

    # Create DataFrame with column headers based on service.input_json
    columns = list(service.input_json.keys())
    df = pd.DataFrame(columns=columns)

    # Add comment row to help users with file fields
    comments = {field_name: 'Place file in "files" folder and enter filename here' 
               for field_name, field_type in service.input_json.items() 
               if field_type == 'file'}
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Batch Query', index=False)
        worksheet = writer.sheets['Batch Query']
        
        # Add column width and format
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, max(len(col) + 2, 15))

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'student_inquiry_template_{service_id}.xlsx'
    )

@user_bp.route('/submit-batch-gpa/<int:service_id>', methods=['POST'])
@validate_session
def submit_batch_gpa(service_id):
    """Handle batch GPA inquiries via Excel file"""
    service = get_service_or_404(service_id)
    if not service:
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    # Ensure files directory exists
    if not os.path.exists('files'):
        os.makedirs('files')

    if 'batch_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    file = request.files['batch_file']
    if not file or not file.filename.endswith('.xlsx'):
        flash('Please upload a valid Excel file (.xlsx)', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    try:
        # Read Excel file
        df = pd.read_excel(file)
        query_count = len(df)

        # Process payment first
        success, error_message = process_payment(session['user_id'], service_id, query_count)
        if not success:
            flash(error_message, 'error')
            return redirect(url_for('user.student_inquiry', service_id=service_id))
        required_fields = list(service.input_json.keys())
        file_fields = {field_name: field_type for field_name, field_type in service.input_json.items() 
                      if field_type == 'file'}
        
        # Validate columns
        missing_cols = set(required_fields) - set(df.columns)
        if missing_cols:
            flash(f'Missing required columns: {", ".join(missing_cols)}', 'error')
            return redirect(url_for('user.student_inquiry', service_id=service_id))

        # Construct query URL properly
        service_url = service.url.rstrip('/')
        service_path = service.path.lstrip('/')
        url = f"{service_url}/{service_path}"
        
        print(f"Sending batch requests to: {url}")
        results = []

        # Process each row
        for idx, row in df.iterrows():
            try:
                data = {}
                files = {}
                
                for field_name in required_fields:
                    if pd.notna(row[field_name]):
                        if field_name in file_fields:
                            file_path = os.path.join('files', str(row[field_name]))
                            if os.path.exists(file_path):
                                files[field_name] = open(file_path, 'rb')
                            else:
                                raise Exception(f"File not found: {file_path}")
                        else:
                            data[field_name] = str(row[field_name])
                
                if files:
                    response = requests.post(url, data=data, files=files)
                else:
                    response = requests.post(url, json=data)
                
                # Close file handlers
                for file_obj in files.values():
                    file_obj.close()
                
                results.append({
                    'row_number': idx + 2,
                    'status': 'Success',
                    'result': response.json()
                })
            except Exception as e:
                results.append({
                    'row_number': idx + 2,
                    'status': 'Error',
                    'result': str(e)
                })

        session['inquiry_result'] = results
        session['gpa_batch_results'] = results  # Store for potential download
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

@user_bp.route('/submit-batch-inquiry/<int:service_id>', methods=['POST'])
@validate_session
def submit_batch_inquiry(service_id):
    """Handle batch student inquiries via Excel file"""
    service = get_service_or_404(service_id)
    if not service:
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    # Ensure files directory exists
    if not os.path.exists('files'):
        os.makedirs('files')

    if 'batch_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    file = request.files['batch_file']
    if not file or not file.filename.endswith('.xlsx'):
        flash('Please upload a valid Excel file (.xlsx)', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    try:
        # Read Excel file
        df = pd.read_excel(file)
        query_count = len(df)

        # Process payment first
        success, error_message = process_payment(session['user_id'], service_id, query_count)
        if not success:
            flash(error_message, 'error')
            return redirect(url_for('user.student_inquiry', service_id=service_id))
        required_fields = list(service.input_json.keys())
        file_fields = {field_name: field_type for field_name, field_type in service.input_json.items() 
                      if field_type == 'file'}
        
        # Validate columns
        missing_cols = set(required_fields) - set(df.columns)
        if missing_cols:
            flash(f'Missing required columns: {", ".join(missing_cols)}', 'error')
            return redirect(url_for('user.student_inquiry', service_id=service_id))

        # Construct query URL properly
        service_url = service.url.rstrip('/')
        service_path = service.path.lstrip('/')
        url = f"{service_url}/{service_path}"
        
        print(f"Sending batch requests to: {url}")
        results = []
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                data = {}
                files = {}
                
                for field_name in required_fields:
                    if pd.notna(row[field_name]):
                        if field_name in file_fields:
                            file_path = os.path.join('files', str(row[field_name]))
                            if os.path.exists(file_path):
                                files[field_name] = open(file_path, 'rb')
                            else:
                                raise Exception(f"File not found: {file_path}")
                        else:
                            data[field_name] = str(row[field_name])
                
                if files:
                    response = requests.post(url, data=data, files=files)
                else:
                    response = requests.post(url, json=data)
                
                # Close file handlers
                for file_obj in files.values():
                    file_obj.close()
                
                results.append({
                    'row_number': idx + 2,  # +2 because Excel rows start at 1 and we skip header
                    'status': 'Success',
                    'result': response.json()
                })
            except Exception as e:
                results.append({
                    'row_number': idx + 2,
                    'status': 'Error',
                    'result': str(e)
                })

        session['inquiry_result'] = results
        session['batch_results'] = results  # Store for potential download
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

@user_bp.route('/download_gpa_results/<int:service_id>')
@validate_session
def download_gpa_results(service_id):
    """Download batch GPA query results as Excel file"""
    if 'gpa_batch_results' not in session:
        flash('No GPA results available for download', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    results = session['gpa_batch_results']
    
    # Create DataFrame from results
    rows = []
    for result in results:
        row = {
            'Row': result['row_number'],
            'Status': result['status'],
            'Result': str(result['result'])
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='GPA Query Results', index=False)
        worksheet = writer.sheets['GPA Query Results']
        
        # Format columns
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, min(max_length, 50))

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'student_gpa_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

@user_bp.route('/download_results/<int:service_id>')
@validate_session
def download_results(service_id):
    """Download batch query results as Excel file"""
    if 'user_id' not in session or 'batch_results' not in session:
        flash('No results available for download', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

    results = session['batch_results']
    
    # Create DataFrame from results
    rows = []
    for result in results:
        row = {
            'Row': result['row_number'],
            'Status': result['status'],
            'Result': str(result['result'])
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Query Results', index=False)
        worksheet = writer.sheets['Query Results']
        
        # Format columns
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, min(max_length, 50))

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'student_inquiry_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

# 查询论文信息
@user_bp.route('/organization-list-thesis/<service_type>', methods=['GET', 'POST'])
def organization_list_thesis(service_type):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        organization_id = request.form.get('organization_id')
        if organization_id:
            # For PC and CC users, only show released services
            if user.user_type in ['PC', 'CC']:
                status_filter = 3
            else:
                status_filter = 2

            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == status_filter)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('user.thesis_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    # Filter services based on user type
    query = db.select(Organization).join(Service).filter(Service.service_type == service_type)
    
    # PC and CC users can only see released services
    if user.user_type in ['PC', 'CC']:
        query = query.filter(Service.status == 3)
    else:
        query = query.filter(Service.status == 2)

    organizations = db.session.execute(query.distinct()).scalars().all()
    
    return render_template('organization_list_thesis.html', 
                           organizations=organizations, 
                           service_type=service_type,
                           user=user,
                           user_id=session['user_id'])

@user_bp.route('/thesis-inquiry/<int:service_id>', methods=['GET'])
def thesis_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    user = db.session.get(Member, session['user_id'])
    
    return render_template('thesis_inquiry.html', 
                           service=service,
                           user=user,
                           result=session.pop('inquiry_result', None))

@user_bp.route('/submit-thesis-inquiry/<int:service_id>', methods=['POST'])
def submit_thesis_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    # Get search service (the one passed in service_id)
    search_service = db.session.get(Service, service_id)
    if not search_service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    try:
        # Process payment for search if needed
        if 'search' in request.form:
            success, error_message = process_payment(session['user_id'], service_id)
            if not success:
                flash(error_message, 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))

        data = {}
        if 'search' in request.form:
            for field_name, field_type in search_service.input_json.items():
                value = request.form.get(field_name, '')
                data[field_name] = value
                
                # Store keywords for potential use in download
                if field_name == 'keywords':
                    session['search_keywords'] = value
            
            # Construct query URL properly
            service_url = search_service.url.rstrip('/')
            service_path = search_service.path.lstrip('/')
            url = f"{service_url}/{service_path}"
            print(f"Search data: {data}")
            print(f"Sending search request to: {url}")
            
            response = requests.post(url, json=data)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
            if response.status_code == 200:
                result = response.json()
                if result:
                    # Store thesis ID and metadata in session
                    if isinstance(result, dict):
                        # Store thesis title for download
                        session['thesis_title'] = result.get('title')
                        print(f"Stored thesis title: {session['thesis_title']}")
                        
                        # Get download service schema
                        download_service = db.session.execute(
                            db.select(Service)
                            .filter_by(organization_id=search_service.organization_id)
                            .filter_by(service_type='P')
                            .filter(Service.status.in_([2, 3]))
                        ).scalar_one_or_none()
                        
                        if download_service:
                            # Store download service info
                            session['download_service_id'] = download_service.service_id
                            if download_service.input_json:
                                print(f"Download service input schema: {download_service.input_json}")
                                result['_download_params'] = download_service.input_json
                    
                    print(f"Search result with metadata: {result}")
                    session['inquiry_result'] = result
                else:
                    session['inquiry_result'] = "No matching thesis found."
            else:
                session['inquiry_result'] = f"Error: {response.status_code} - {response.text}"
            return redirect(url_for('user.thesis_inquiry', service_id=service_id))

        elif 'download' in request.form:
            # Get the download service for the same organization
            download_service = db.session.execute(
                db.select(Service)
                .filter_by(organization_id=search_service.organization_id)
                .filter_by(service_type='P')
                .filter(Service.status.in_([2, 3]))
            ).scalar_one_or_none()

            if not download_service:
                flash('Download service not available', 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))

            # Process payment for download
            success, error_message = process_payment(session['user_id'], download_service.service_id)
            if not success:
                flash(error_message, 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))

            # Initialize download data
            data = {}
            
            # Try to get title from session first
            title = session.get('thesis_title')
            print(f"Title from session: {title}")
            
            # If not in session, try to get from form
            if not title:
                title = request.form.get('title')
                print(f"Title from form: {title}")
            
            if title:
                data['title'] = title
                print(f"Using title for download: {data['title']}")
            else:
                flash('Missing thesis title for download', 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))
                    
            # Include search keywords if available
            if session.get('search_keywords'):
                data['keywords'] = session.get('search_keywords')

            print(f"Using search parameters: {data}")
            
            # Construct query URL properly
            service_url = download_service.url.rstrip('/')
            service_path = download_service.path.lstrip('/')
            url = f"{service_url}/{service_path}"
            print(f"Sending download request to: {url}")
            print(f"Download request data: {data}")
            
            # Set appropriate headers for PDF download
            headers = {
                'Accept': 'application/pdf',
                'Content-Type': 'application/json'
            }
            
            print(f"Sending download request with headers: {headers}")
            print(f"Download URL: {url}")
            print(f"Download data: {data}")
            
            # Use GET request for downloading with URL parameters
            response = requests.get(
                url,
                params=data,  # Send data as URL parameters
                headers=headers,
                stream=True   # Keep streaming for large files
            )
            print(f"Download GET request URL: {response.url}")  # Log the full URL with parameters
            
            print(f"Download response headers: {response.headers}")
            print(f"Download response content type: {response.headers.get('Content-Type')}")
            print(f"Download response content length: {response.headers.get('Content-Length')}")
            print(f"Response status: {response.status_code}")
            print(f"Response content type: {response.headers.get('Content-Type', 'unknown')}")

            # Analyze response
            content_type = response.headers.get('Content-Type', '').lower()
            print(f"Analyzing response: content-type={content_type}")

            # Try to interpret as JSON first
            try:
                json_data = response.json()
                print("Response appears to be JSON:", json_data)
                flash('Download failed: Service returned JSON instead of PDF', 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))
            except:
                # Not JSON, proceed with PDF check
                print("Response is not JSON, checking for PDF content")

            # Check if response appears to be a PDF
            is_pdf = (
                response.status_code == 200 and
                (
                    'pdf' in content_type or 
                    response.content.startswith(b'%PDF-') or
                    len(response.content) > 1024  # PDFs are typically larger than 1KB
                )
            )
            
            print(f"PDF check result: {is_pdf}")
            print(f"Content starts with: {response.content[:20]}")

            if is_pdf:
                print("Response appears to be a valid PDF")
                
                # Get filename from Content-Disposition or use default
                filename = 'thesis.pdf'
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    import re
                    filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1).strip('"\'')
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                
                print(f"Using filename: {filename}")
                print(f"Content length: {len(response.content)} bytes")
                
                # Create file object from response content
                file_obj = io.BytesIO(response.content)
                
                # Verify file object has content
                file_size = file_obj.getbuffer().nbytes
                print(f"File object size: {file_size} bytes")
                
                if file_size == 0:
                    raise Exception("Received empty file")
                
                return send_file(
                    file_obj,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
            else:
                flash(f'Download failed: {response.status_code} - {response.text}', 'error')
                return redirect(url_for('user.thesis_inquiry', service_id=service_id))

    except Exception as e:
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('user.thesis_inquiry', service_id=service_id))

# 搜索课程信息
@user_bp.route('/course-info-check')
def course_info_check():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    course_name = request.args.get('course_name', '')
    
    if course_name:
        courses = db.session.execute(
            db.select(CourseInformation)
            .join(Organization)
            .filter(CourseInformation.name.ilike(f'%{course_name}%'))
            .order_by(CourseInformation.name)
        ).scalars().all()
    else:
        courses = []
    
    return render_template('course_info_check.html', courses=courses)

@user_bp.route('/provide-course-info', methods=['GET', 'POST'])
def provide_course_info():
    """Provide course information interface for PP users"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can provide course information', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    if request.method == 'POST':
        course_name = request.form.get('course_name')
        course_description = request.form.get('course_description')
        
        if not course_name:
            flash('Course name is required', 'error')
            return redirect(url_for('user.provide_course_info'))
        
        try:
            new_course = CourseInformation(
                organization_id=user.organization_id,
                name=course_name,
                description=course_description
            )
            db.session.add(new_course)
            db.session.commit()
            flash('Course information has been successfully added', 'success')
            return redirect(url_for('user.provide_course_info'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add course information: {str(e)}', 'error')
            return redirect(url_for('user.provide_course_info'))

    # Get all courses for the user's organization
    courses = db.session.execute(
        db.select(CourseInformation)
        .filter_by(organization_id=user.organization_id)
        .order_by(CourseInformation.name)
    ).scalars().all()
    
    return render_template('provide_course_info.html', courses=courses)

@user_bp.route('/edit-course/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    """Edit an existing course"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can edit course information', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    course = db.session.get(CourseInformation, course_id)
    if not course or course.organization_id != user.organization_id:
        flash('Course not found or you do not have permission to edit it', 'error')
        return redirect(url_for('user.provide_course_info'))
    
    course_name = request.form.get('course_name')
    course_description = request.form.get('course_description')
    
    if not course_name:
        flash('Course name is required', 'error')
        return redirect(url_for('user.provide_course_info'))
    
    try:
        course.name = course_name
        course.description = course_description
        db.session.commit()
        flash('Course information has been successfully updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to update course information: {str(e)}', 'error')
    
    return redirect(url_for('user.provide_course_info'))

@user_bp.route('/delete-course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can delete course information', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    course = db.session.get(CourseInformation, course_id)
    if not course or course.organization_id != user.organization_id:
        flash('Course not found or you do not have permission to delete it', 'error')
        return redirect(url_for('user.provide_course_info'))
    
    try:
        db.session.delete(course)
        db.session.commit()
        flash('Course has been successfully deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete course: {str(e)}', 'error')
    
    return redirect(url_for('user.provide_course_info'))
