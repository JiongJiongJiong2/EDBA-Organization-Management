# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file
import sqlite3
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member, Question, Policy, SystemLog, EDBankAccount
from flask import current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

admin_bp = Blueprint('admin', __name__)

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

@admin_bp.route('/main')
def e_admin_main_page():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    return render_template('e_admin_main.html')

# O-Convener Application Routes
@admin_bp.route('/applications')
def e_admin_applications():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    applications = db.session.execute(
        db.select(Application)
        .order_by(Application.status, Application.created_at.desc())
    ).scalars().all()
    
    # 检查超过三天未处理的申请
    three_days_ago = datetime.now() - timedelta(days=3)
    for app in applications:
        if app.status == 0 and app.created_at < three_days_ago:
            flash(f'Warning: Application {app.application_id} has been pending for more than 3 days!', 'warning')
    
    return render_template('e_admin_applications.html', applications=applications)

@admin_bp.route('/applications/document/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    document = db.session.get(ApplicationDocument, doc_id)
    if not document or not document.file_path or not os.path.exists(document.file_path):
        flash('Document not found', 'error')
        return redirect(url_for('admin.e_admin_applications'))

    return send_file(
        document.file_path,
        as_attachment=True,
        download_name=document.original_filename
    )

@admin_bp.route('/applications/<int:app_id>/approve', methods=['POST'])
def approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin.e_admin_applications'))

    # 检查是否超过三天
    if datetime.now() - application.created_at > timedelta(days=3):
        flash('Warning: This application has exceeded the 3-day processing limit', 'warning')

    try:
        application.status = 1  # Approved
        db.session.commit()

        # 发送邮件给SE-Admin
        se_admins = db.session.execute(
            db.select(Member).filter_by(user_type='SE')
        ).scalars().all()

        for se_admin in se_admins:
            send_email(
                to=se_admin.email,
                subject='New O-Convener Application Approved',
                body=f'Application {app_id} has been approved by E-Admin.\n'
                     f'Applicant Email: {application.email}\n'
                     f'Organization: {application.organization_name}'
            )

        flash('Application approved successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving application: {str(e)}', 'error')

    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/applications/<int:app_id>/reject', methods=['POST'])
def reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin.e_admin_applications'))

    try:
        application.status = 2  # Rejected
        db.session.commit()

        # 发送邮件给申请者
        send_email(
            to=application.email,
            subject='Your O-Convener Application Status',
            body='Your application has been rejected by the E-Admin.\n'
                 'If you have any questions, please contact support.'
        )

        flash('Application rejected successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')

    return redirect(url_for('admin.e_admin_applications'))

# Policy Management Routes
@admin_bp.route('/policies')
def e_admin_policies():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policies = db.session.execute(db.select(Policy).order_by(Policy.created_at.desc())).scalars().all()
    return render_template('e_admin_policies.html', policies=policies)

@admin_bp.route('/policy/add', methods=['POST'])
def add_policy():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    content = request.form.get('content')
    pdf_file = request.files.get('pdf_file')

    if not title or not content:
        flash('Title and content are required', 'error')
        return redirect(url_for('admin.e_admin_policies'))

    try:
        new_policy = Policy(title=title, content=content)
        
        if pdf_file and pdf_file.filename:
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf_file.filename}")
            pdf_path = os.path.join(current_app.config['POLICIES_FOLDER'], filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            pdf_file.save(pdf_path)
            new_policy.pdf_path = pdf_path

        db.session.add(new_policy)
        db.session.commit()
        flash('Policy added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding policy: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/policy/get/<int:policy_id>', methods=['GET'])
def get_policy(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        return jsonify({'error': 'Unauthorized access'}), 403

    policy = db.session.get(Policy, policy_id)
    if not policy:
        return jsonify({'error': 'Policy not found'}), 404

    return jsonify({
        'title': policy.title,
        'content': policy.content
    })

@admin_bp.route('/policy/<int:policy_id>/update', methods=['POST'])
def update_policy(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    policy = db.session.get(Policy, policy_id)
    if not policy:
        flash('Policy not found', 'error')
        return redirect(url_for('admin.e_admin_policies'))

    try:
        policy.title = request.form.get('title')
        policy.content = request.form.get('content')
        
        pdf_file = request.files.get('pdf_file')
        if pdf_file and pdf_file.filename:
            # Delete old PDF if exists
            if policy.pdf_path and os.path.exists(policy.pdf_path):
                os.remove(policy.pdf_path)
            
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf_file.filename}")
            pdf_path = os.path.join(current_app.config['POLICIES_FOLDER'], filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            pdf_file.save(pdf_path)
            policy.pdf_path = pdf_path

        db.session.commit()
        flash('Policy updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating policy: {str(e)}', 'error')

    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/policy/<int:policy_id>/delete', methods=['POST'])
def delete_policy(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    policy = db.session.get(Policy, policy_id)
    if not policy:
        flash('Policy not found', 'error')
        return redirect(url_for('admin.e_admin_policies'))

    try:
        if policy.pdf_path and os.path.exists(policy.pdf_path):
            os.remove(policy.pdf_path)
        
        db.session.delete(policy)
        db.session.commit()
        flash('Policy deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting policy: {str(e)}', 'error')

    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/policy/<int:policy_id>/download')
def download_policy_pdf(policy_id):
    if 'user_id' not in session:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    policy = db.session.get(Policy, policy_id)
    if not policy or not policy.pdf_path or not os.path.exists(policy.pdf_path):
        flash('PDF not found', 'error')
        return redirect(url_for('admin.e_admin_policies'))

    return send_file(
        policy.pdf_path,
        as_attachment=True,
        download_name=os.path.basename(policy.pdf_path)
    )

# System Logs Routes
@admin_bp.route('/logs')
def e_admin_logs():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    activity_type = request.args.get('activity_type')
    user_email = request.args.get('user_email')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    organization_id = request.args.get('organization_id')

    query = db.select(SystemLog)
    if activity_type:
        query = query.filter(SystemLog.activity_type == activity_type)
    if user_email:
        query = query.join(Member).filter(Member.email.ilike(f'%{user_email}%'))
    if start_date:
        query = query.filter(SystemLog.timestamp >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(SystemLog.timestamp < datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if organization_id:
        query = query.filter(SystemLog.organization_id == organization_id)

    logs = db.session.execute(query.order_by(SystemLog.timestamp.desc())).scalars().all()
    organizations = db.session.execute(db.select(Organization)).scalars().all()

    return render_template('e_admin_logs.html',
                         logs=logs,
                         organizations=organizations)

@admin_bp.route('/logs/export', methods=['POST'])
def export_logs():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    logs = db.session.execute(
        db.select(SystemLog)
        .order_by(SystemLog.timestamp.desc())
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'User', 'Activity', 'Organization', 'Details'])

    for log in logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.email if log.user else 'N/A',
            log.activity_type,
            log.organization.name if log.organization else 'N/A',
            log.details
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'system_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

# Bank Account Routes
@admin_bp.route('/bank-settings')
def e_admin_bank_settings():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    bank_account = db.session.execute(db.select(EDBankAccount)).scalar_one_or_none()
    return render_template('e_admin_bank_settings.html', bank_account=bank_account)

@admin_bp.route('/bank-settings/update', methods=['POST'])
def update_bank_account():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    account_number = request.form.get('account_number')
    membership_fee = request.form.get('membership_fee')

    if not account_number or not membership_fee:
        flash('All fields are required', 'error')
        return redirect(url_for('admin.e_admin_bank_settings'))

    try:
        membership_fee = float(membership_fee)
        if membership_fee < 0:
            raise ValueError('Membership fee must be positive')

        bank_account = db.session.execute(db.select(EDBankAccount)).scalar_one_or_none()
        if bank_account:
            bank_account.account_number = account_number
            bank_account.membership_fee = membership_fee
        else:
            bank_account = EDBankAccount(account_number=account_number, membership_fee=membership_fee)
            db.session.add(bank_account)

        db.session.commit()
        flash('Bank settings updated successfully', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating bank settings: {str(e)}', 'error')

    return redirect(url_for('admin.e_admin_bank_settings'))
