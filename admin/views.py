# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file
import sqlite3
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member, Workspace, Policy, BankAccount, Question, SystemLog
from flask import current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/e_admin/logs')
def view_logs():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get filter parameters
    activity_type = request.args.get('activity_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    organization_id = request.args.get('organization_id')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Build query
    query = db.select(SystemLog).join(Member).join(Organization)

    # Apply filters
    if activity_type:
        query = query.filter(SystemLog.activity_type == activity_type)
    if start_date:
        query = query.filter(SystemLog.timestamp >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(SystemLog.timestamp < end)
    if organization_id:
        query = query.filter(SystemLog.organization_id == organization_id)

    # Order by timestamp descending
    query = query.order_by(SystemLog.timestamp.desc())

    # Execute query with pagination
    pagination = db.paginate(query, page=page, per_page=per_page)
    logs = pagination.items

    # Get all organizations for the filter dropdown
    organizations = db.session.execute(db.select(Organization)).scalars().all()

    return render_template('e_admin_logs.html', 
                         user=user,
                         logs=logs,
                         pagination=pagination,
                         organizations=organizations)

def send_email(to, subject, body):
    """发送邮件的辅助函数"""
    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config['MAIL_USERNAME']
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Error sending email: {str(e)}")

# T-Admin Routes
@admin_bp.route('/t_admin/questions/a')
def t_admin_question_a():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    search_query = request.args.get('search', '')
    
    if search_query:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(
                Question.status == 1,
                db.or_(
                    Question.title.ilike(f'%{search_query}%'),
                    Question.description.ilike(f'%{search_query}%'),
                    Member.email.ilike(f'%{search_query}%')
                )
            )
            .order_by(Question.submit_time.desc())
        ).scalars().all()
    else:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(Question.status == 1)
            .order_by(Question.submit_time.desc())
        ).scalars().all()
    
    return render_template('t-admin_question_a.html', 
                         user=user,
                         questions=questions, 
                         search_query=search_query)

@admin_bp.route('/t_admin/questions/b')
def t_admin_question_b():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    search_query = request.args.get('search', '')
    
    if search_query:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(
                Question.status == 0,
                db.or_(
                    Question.title.ilike(f'%{search_query}%'),
                    Question.description.ilike(f'%{search_query}%'),
                    Member.email.ilike(f'%{search_query}%')
                )
            )
            .order_by(Question.submit_time.desc())
        ).scalars().all()
    else:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(Question.status == 0)
            .order_by(Question.submit_time.desc())
        ).scalars().all()
    
    return render_template('t-admin_question_b.html', 
                         user=user,
                         questions=questions, 
                         search_query=search_query)

@admin_bp.route('/t_admin/submit_answer/<question_id>', methods=['POST'])
def t_admin_submit_answer(question_id):
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    new_answer = request.form.get('answer', '')
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        question.status = 1
        question.response_time = datetime.now()  # Track response time
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.t_admin_question_b'))

@admin_bp.route('/t_admin/update_answer/<question_id>', methods=['POST'])
def t_admin_update_answer(question_id):
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    new_answer = request.form.get('answer', '').strip()
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        if not new_answer:
            question.status = 0
            question.response_time = None
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.t_admin_question_a'))

@admin_bp.route('/t_admin/main')
def t_admin_main_page():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user information
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get counts for unanswered and answered questions
    unanswered_count = db.session.execute(
        db.select(db.func.count(Question.question_id))
        .filter_by(status=0)
    ).scalar()
    
    answered_count = db.session.execute(
        db.select(db.func.count(Question.question_id))
        .filter_by(status=1)
    ).scalar()
    
    return render_template('t-admin_main_page.html', 
                         user=user,
                         unanswered_count=unanswered_count,
                         answered_count=answered_count)

# Routes for setting up admins
@admin_bp.route('/t_admin/setup_admin', methods=['POST'])
def t_admin_setup_admin():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    email = request.form.get('email')
    admin_type = request.form.get('admin_type')  # 'EE' or 'SE'
    
    if not email or admin_type not in ['EE', 'SE']:
        flash('Invalid email or admin type', 'error')
        return redirect(url_for('admin.t_admin_user_management'))
    
    try:
        # Check if user already exists
        existing_user = db.session.execute(
            db.select(Member).filter_by(email=email)
        ).scalar_one_or_none()
        
        if existing_user:
            flash('User already exists', 'error')
            return redirect(url_for('admin.t_admin_user_management'))
        
        # Get or create organization 0
        org_zero = db.session.execute(
            db.select(Organization).filter_by(organization_id=0)
        ).scalar_one_or_none()
        
        if not org_zero:
            org_zero = Organization(organization_id=0, name='System Organization')
            db.session.add(org_zero)
            db.session.flush()
        
        # Create new admin user
        new_admin = Member(
            email=email,
            user_type=admin_type,
            organization_id=0,
            fund=0
        )
        db.session.add(new_admin)
        db.session.commit()
        
        flash(f'Successfully created {admin_type} admin user', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating admin: {str(e)}', 'error')
    
    return redirect(url_for('admin.t_admin_user_management'))

@admin_bp.route('/t_admin/user_management')
def t_admin_user_management():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    search_query = request.args.get('search', '')
    
    # Get existing admins
    if search_query:
        admins = db.session.execute(
            db.select(Member).where(
                Member.organization_id == 0,
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.user_type.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        admins = db.session.execute(
            db.select(Member).filter_by(organization_id=0)
        ).scalars().all()
    
    return render_template('t-admin_user_management.html', 
                         user=user,
                         admins=admins, 
                         search_query=search_query)

# SE Admin Routes
@admin_bp.route('/se_admin/main')
def se_admin_main():
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    # 获取当前用户信息
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('用户信息不存在', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        return redirect(url_for('auth.login'))

    # Get count of pending applications
    pending_count = db.session.execute(
        db.select(db.func.count(Application.application_id))
        .filter_by(status=1)  # Status 1 means approved by E-Admin
    ).scalar()
    
    return render_template('se_admin_main_page.html', 
                         user=user,
                         pending_count=pending_count)

@admin_bp.route('/se_admin/applications')
def se_admin_applications():
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    # 获取当前用户信息
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('用户信息不存在', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        return redirect(url_for('auth.login'))

    # Get all applications that have been processed by SE-Admin and those pending review
    applications = db.session.execute(
        db.select(Application)
        .filter(Application.status.in_([1, 3, 4]))  # Status 1: E-Admin approved (pending), 3: SE-Admin approved, 4: SE-Admin rejected
        .order_by(Application.se_admin_review_date.desc(), Application.created_at.desc())
    ).scalars().all()

    return render_template('se_admin_applications.html', 
                         user=user,
                         applications=applications,
                         now=datetime.now(),
                         timedelta=timedelta)

@admin_bp.route('/se_admin/applications/<int:app_id>/approve', methods=['POST'])
def se_admin_approve_application(app_id):
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        return redirect(url_for('auth.login'))

    try:
        application = db.session.get(Application, app_id)
        if not application:
            flash('Application not found', 'error')
            return redirect(url_for('admin.se_admin_applications'))

        # Verify application is in correct state
        if application.status != 1:
            flash('Cannot approve application - invalid status', 'error')
            return redirect(url_for('admin.se_admin_applications'))

        # Get notes from the form
        notes = request.form.get('notes', '').strip()

        # Create a new organization
        organization = Organization(
            name=application.organization_name
        )
        db.session.add(organization)
        db.session.flush()  # Get the organization_id

        # Create O-Convener member for the organization
        oc_member = Member(
            email=application.email,
            user_type='OC',
            organization_id=organization.organization_id,
            fund=50  # Default fund value
        )
        db.session.add(oc_member)
        db.session.flush()  # Ensure member is created before workspace

        # Create a new workspace
        workspace = Workspace(
            organization_id=organization.organization_id,
            name=f"{application.organization_name}'s Workspace",
            status='active'
        )
        db.session.add(workspace)
        db.session.flush()  # Get the workspace_id

        # Update application
        application.status = 3  # SE-Admin Approved
        application.se_admin_review_date = datetime.now()
        application.se_admin_notes = notes
        application.workspace_id = workspace.workspace_id
        
        try:
            db.session.commit()
            
            # Verify changes were saved
            db.session.refresh(application)
            if (application.status != 3 or
                not application.se_admin_review_date or
                not application.workspace_id):
                raise Exception("Changes were not saved correctly")

            # Send email notification
            email_subject = "O-Convener Application Approved"
            email_body = f"""Dear Applicant,

Your application for organization '{application.organization_name}' has been approved by the SE Administrator.

A workspace has been created for your organization. You can now log in to access your workspace.

Notes from the SE Administrator:
{notes if notes else 'No additional notes provided.'}

Best regards,
The Administration Team"""
            
            send_email(application.email, email_subject, email_body)
            
            # Return JSON response for AJAX
            return jsonify({'status': 'success', 'message': 'Application has been approved successfully'})
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving approval: {str(e)}', 'error')
            print(f"Database error during SE admin approval: {str(e)}")
    except Exception as e:
        flash(f'Error processing approval: {str(e)}', 'error')
        print(f"Error in SE admin approval route: {str(e)}")
    
    return redirect(url_for('admin.se_admin_applications'))

@admin_bp.route('/se_admin/applications/<int:app_id>/reject', methods=['POST'])
def se_admin_reject_application(app_id):
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        return redirect(url_for('auth.login'))

    try:
        application = db.session.get(Application, app_id)
        if not application:
            flash('Application not found', 'error')
            return redirect(url_for('admin.se_admin_applications'))

        # Verify application is in correct state
        if application.status != 1:
            flash('Cannot reject application - invalid status', 'error')
            return redirect(url_for('admin.se_admin_applications'))

        # Get notes from the form
        notes = request.form.get('notes', '').strip()

        # Update application
        application.status = 4  # SE-Admin Rejected
        application.se_admin_review_date = datetime.now()
        application.se_admin_notes = notes
        
        try:
            db.session.commit()
            
            # Verify changes were saved
            db.session.refresh(application)
            if application.status != 4 or not application.se_admin_review_date:
                raise Exception("Changes were not saved correctly")
                
            # Send email notification
            email_subject = "O-Convener Application Not Approved"
            email_body = f"""Dear Applicant,

Your application for organization '{application.organization_name}' has not been approved by the SE Administrator.

Feedback from the SE Administrator:
{notes if notes else 'No specific reason provided.'}

You may submit a new application addressing the feedback provided.

Best regards,
The Administration Team"""
            
            send_email(application.email, email_subject, email_body)
                
            # Return JSON response for AJAX
            return jsonify({'status': 'success', 'message': 'Application has been rejected successfully'})
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving rejection: {str(e)}', 'error')
            print(f"Database error during SE admin rejection: {str(e)}")
    except Exception as e:
        flash(f'Error processing rejection: {str(e)}', 'error')
        print(f"Error in SE admin rejection route: {str(e)}")
    
    return redirect(url_for('admin.se_admin_applications'))

# E-Admin Routes
# 修改后的 e_admin_applications 函数
@admin_bp.route('/e_admin/applications')
def e_admin_applications():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # 获取当前用户信息
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('用户信息不存在', 'error')
        return redirect(url_for('auth.login'))
    
    # Get all applications
    applications = db.session.execute(
        db.select(Application)
        .order_by(Application.created_at.desc())
    ).scalars().all()
    
    # 添加 timedelta 到模板上下文
    from datetime import datetime, timedelta
    
    return render_template('e_admin_applications.html', 
                         user=user,
                         applications=applications,
                         now=datetime.now(),
                         timedelta=timedelta)  # 将 timedelta 类传递给模板

@admin_bp.route('/e_admin/applications/<int:app_id>/approve', methods=['POST'])
def approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if application:
        application.status = 1  # Approved
        application.e_admin_approval_date = datetime.now()
        db.session.commit()
        flash('Application approved successfully', 'success')
    else:
        flash('Application not found', 'error')
    
    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/e_admin/applications/<int:app_id>/reject', methods=['POST'])
def reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if application:
        application.status = 2  # Rejected
        db.session.commit()
        flash('Application rejected', 'info')
    else:
        flash('Application not found', 'error')
    
    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/e_admin/document/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    document = db.session.get(ApplicationDocument, doc_id)
    if document and document.file_path:
        return send_file(document.file_path, as_attachment=True)
    
    flash('Document not found', 'error')
    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/e_admin/bank-settings')
def bank_settings():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get current user information
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get bank account for organization_id=0 (EDBA)
    bank_account = db.session.execute(
        db.select(BankAccount).filter_by(organization_id=0)
    ).scalar_one_or_none()
    
    return render_template('e_admin_bank_settings.html', 
                         user=user,
                         bank_account=bank_account)

@admin_bp.route('/e_admin/bank-settings/update', methods=['POST'])
def update_bank_account():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Get form data
        bank_name = request.form.get('bank')
        account_name = request.form.get('name')
        account_number = request.form.get('number')
        password = request.form.get('password')
        
        if not all([bank_name, account_name, account_number, password]):
            flash('All fields are required', 'error')
            return redirect(url_for('admin.bank_settings'))
        
        # Get or create organization 0 (EDBA)
        org_zero = db.session.execute(
            db.select(Organization).filter_by(organization_id=0)
        ).scalar_one_or_none()
        
        if not org_zero:
            org_zero = Organization(organization_id=0, name='System Organization')
            db.session.add(org_zero)
            db.session.flush()
        
        # Get existing account or create new one
        bank_account = db.session.execute(
            db.select(BankAccount).filter_by(organization_id=0)
        ).scalar_one_or_none()
        
        if bank_account:
            bank_account.bank = bank_name
            bank_account.name = account_name
            bank_account.number = account_number
            bank_account.password = password
        else:
            bank_account = BankAccount(
                organization_id=0,
                bank=bank_name,
                name=account_name,
                number=account_number,
                password=password
            )
            db.session.add(bank_account)
        
        db.session.commit()
        flash('Bank account settings updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating bank account settings: {str(e)}', 'error')
    
    return redirect(url_for('admin.bank_settings'))


#eadmin_policy
# 显示政策管理页面
@admin_bp.route('/e_admin_policies')

def e_admin_policies():
    # 确保用户是EE管理员
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # 获取当前用户信息
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('用户信息不存在', 'error')
        return redirect(url_for('auth.login'))
    
    # 获取所有政策
    policies = Policy.query.all()
    return render_template('e_admin_policies.html', 
                         user=user,
                         policies=policies)

# 添加新政策
@admin_bp.route('/policy/add', methods=['POST'])

def add_policy():
    # 权限检查
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    content = request.form.get('content')
    
    # 创建新的政策记录
    new_policy = Policy(
        title=title,
        content=content,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # 处理PDF文件上传（如果有）
    if 'pdf_file' in request.files and request.files['pdf_file'].filename:
        pdf_file = request.files['pdf_file']
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{pdf_file.filename}")
        
        # 确保政策文件目录存在
        policies_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'policies')
        if not os.path.exists(policies_dir):
            os.makedirs(policies_dir)
        
        # 保存文件
        file_path = os.path.join(policies_dir, filename)
        pdf_file.save(file_path)
        
        # 记录文件路径
        new_policy.pdf_path = os.path.join('policies', filename)
    
    # 保存到数据库
    db.session.add(new_policy)
    db.session.commit()
    
    flash('Policy added successfully.', 'success')
    return redirect(url_for('admin.e_admin_policies'))

# 删除政策
@admin_bp.route('/policy/<int:policy_id>/delete', methods=['POST'])

def delete_policy(policy_id):
    # 权限检查
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policy = Policy.query.get_or_404(policy_id)
    
    # 如果有PDF文件，删除文件
    if policy.pdf_path:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], policy.pdf_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # 从数据库删除记录
    db.session.delete(policy)
    db.session.commit()
    
    flash('Policy deleted successfully.', 'success')
    return redirect(url_for('admin.e_admin_policies'))

# 获取单个政策信息（用于编辑）
@admin_bp.route('/policy/<int:policy_id>', methods=['GET'])

def get_policy(policy_id):
    # 权限检查
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policy = Policy.query.get_or_404(policy_id)
    
    return jsonify({
        'title': policy.title,
        'content': policy.content,
        'created_at': policy.created_at.strftime('%Y-%m-%d'),
        'updated_at': policy.updated_at.strftime('%Y-%m-%d'),
        'has_pdf': bool(policy.pdf_path)
    })

# 更新政策
@admin_bp.route('/policy/<int:policy_id>/update', methods=['POST'])

def update_policy(policy_id):
    # 权限检查
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policy = Policy.query.get_or_404(policy_id)
    
    # 更新文本字段
    policy.title = request.form.get('title')
    policy.content = request.form.get('content')
    policy.updated_at = datetime.now()
    
    # 处理新PDF文件上传（如果有）
    if 'pdf_file' in request.files and request.files['pdf_file'].filename:
        # 如果存在旧文件，删除它
        if policy.pdf_path:
            old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], policy.pdf_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        # 保存新文件
        pdf_file = request.files['pdf_file']
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{pdf_file.filename}")
        
        # 确保目录存在
        policies_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'policies')
        if not os.path.exists(policies_dir):
            os.makedirs(policies_dir)
        
        # 保存文件
        file_path = os.path.join(policies_dir, filename)
        pdf_file.save(file_path)
        
        # 更新文件路径
        policy.pdf_path = os.path.join('policies', filename)
    
    # 保存更改
    db.session.commit()
    
    flash('Policy updated successfully.', 'success')
    return redirect(url_for('admin.e_admin_policies'))

# 下载政策PDF文件
@admin_bp.route('/policy/<int:policy_id>/download-pdf')

def download_policy_pdf(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    
    if not policy.pdf_path:
        flash('No PDF file available for this policy.', 'warning')
        return redirect(url_for('admin.e_admin_policies'))
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], policy.pdf_path)
    
    if not os.path.exists(file_path):
        flash('PDF file not found.', 'error')
        return redirect(url_for('admin.e_admin_policies'))
    
    # 提取文件名用于下载
    filename = os.path.basename(policy.pdf_path)
    
    return send_file(
        file_path,
        download_name=filename,
        as_attachment=True
    )
