# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file
import sqlite3
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member, Workspace, Policy, EDBankAccount, Question
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

# SE Admin Routes
@admin_bp.route('/se_admin/main')
def se_admin_main():
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"Current user type: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        print(f"Access denied for user type: {user_type}")  # Debug log
        return redirect(url_for('auth.login'))
    return render_template('se_admin_user_management.html')

@admin_bp.route('/se_admin/dashboard')
def se_admin_dashboard():
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"Current user type: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        print(f"Access denied for user type: {user_type}")  # Debug log
        return redirect(url_for('auth.login'))
    
    # Get count of pending applications for display
    pending_count = db.session.execute(
        db.select(db.func.count(Application.application_id))
        .filter_by(status=1)  # e_admin_approved
    ).scalar()
    
    return render_template('se_admin_main_page.html', pending_count=pending_count)

@admin_bp.route('/se_admin/applications')
def se_admin_applications():
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"Current user type for applications: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        flash('没有权限访问此页面', 'error')
        print(f"Access denied for user type: {user_type}")  # Debug log
        return redirect(url_for('auth.login'))
    
    search_query = request.args.get('search', '')
    query = db.select(Application).filter_by(status=1)  # Only show e_admin_approved applications
    
    if search_query:
        query = query.filter(
            db.or_(
                Application.organization_name.ilike(f'%{search_query}%'),
                Application.email.ilike(f'%{search_query}%')
            )
        )
    
    applications = db.session.execute(
        query.order_by(Application.e_admin_approval_date.desc())
    ).scalars().all()
    
    return render_template('se_admin_applications.html', 
                         applications=applications,
                         search_query=search_query)

@admin_bp.route('/se_admin/document/<int:doc_id>')
def download_document(doc_id):
    print(f"Attempting to download document {doc_id}")  # Debug log
    
    if 'user_id' not in session:
        print("No user session")  # Debug log
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"User type attempting document download: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        print(f"Access denied for user type: {user_type}")  # Debug log
        flash('没有权限下载文件', 'error')
        return redirect(url_for('auth.login'))
    
    document = db.session.get(ApplicationDocument, doc_id)
    if not document:
        print(f"Document {doc_id} not found")  # Debug log
        flash('Document not found', 'error')
        return redirect(url_for('admin.se_admin_applications'))

    try:
        print(f"Sending file: {document.file_path}")  # Debug log
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            os.path.basename(document.file_path),  # 使用文件路径的基本名称
            as_attachment=True,
            download_name=document.original_filename
        )
    except Exception as e:
        print(f"Error sending file: {str(e)}")  # Debug log
        flash('Error downloading document', 'error')
        return redirect(url_for('admin.se_admin_applications'))

@admin_bp.route('/se_admin/applications/<int:app_id>/approve', methods=['POST'])
def se_admin_approve_application(app_id):
    print(f"Processing approval request for application {app_id}")  # Debug log
    
    if 'user_id' not in session:
        print("No user session")  # Debug log
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"User type attempting approval: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        print(f"Access denied for user type: {user_type}")  # Debug log
        flash('没有权限审批申请', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application:
        print(f"Application {app_id} not found")  # Debug log
        flash('Invalid application', 'error')
        return redirect(url_for('admin.se_admin_applications'))
        
    if application.status != 1:
        print(f"Invalid application status: {application.status}")  # Debug log
        flash('Invalid application status', 'error')
        return redirect(url_for('admin.se_admin_applications'))
        
    try:
        try:
            # Create organization with initial settings
            organization = Organization(name=application.organization_name)
            db.session.add(organization)
            db.session.flush()  # Get organization_id
            
            # Create workspace with detailed settings
            workspace = Workspace(
                organization_id=organization.organization_id,
                name=f"{application.organization_name}'s Workspace",
                status='active',
                settings=json.dumps({
                    'created_by': session.get('user_id'),
                    'created_at': datetime.now().isoformat(),
                    'initial_setup_complete': True
                })
            )
            db.session.add(workspace)
            db.session.flush()
            
            # Create O-Convener member with initial fund
            member = Member(
                email=application.email,
                user_type='OC',
                organization_id=organization.organization_id,
                fund=50  # Initial fund amount
            )
            db.session.add(member)
            
            # Update application with detailed tracking
            application.status = 3  # se_admin_approved
            application.se_admin_review_date = datetime.now()
            application.se_admin_notes = request.form.get('notes')
            application.workspace_id = workspace.workspace_id
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in approving application: {str(e)}")
            raise e  # Re-raise to be caught by outer try-except
        
        # Send detailed notification email to O-Convener
        send_email(
            to=application.email,
            subject='Your O-Convener Application Has Been Approved',
            body=f'''Congratulations! Your application to become an O-Convener has been approved.

Organization Details:
- Name: {application.organization_name}
- Workspace ID: {workspace.workspace_id}
- Initial Fund: 50 credits

You can now log in to the E-DBA system using your email address: {application.email}

Important Next Steps:
1. Log in to your account
2. Complete your organization profile
3. Review the workspace settings
4. Set up your services

Welcome to the E-DBA system!

Best regards,
The E-DBA Team'''
        )
        
        flash('Application approved successfully. Workspace created and O-Convener notified.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving application: {str(e)}', 'error')
    
    return redirect(url_for('admin.se_admin_applications'))

@admin_bp.route('/se_admin/applications/<int:app_id>/reject', methods=['POST'])
def se_admin_reject_application(app_id):
    print(f"Processing rejection request for application {app_id}")  # Debug log
    
    if 'user_id' not in session:
        print("No user session")  # Debug log
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    user_type = session.get('user_type', '').upper()
    print(f"User type attempting rejection: {user_type}")  # Debug log
    
    if user_type not in ['SE', 'SE-ADMIN']:
        print(f"Access denied for user type: {user_type}")  # Debug log
        flash('没有权限拒绝申请', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application:
        print(f"Application {app_id} not found")  # Debug log
        flash('Invalid application', 'error')
        return redirect(url_for('admin.se_admin_applications'))
        
    if application.status != 1:
        print(f"Invalid application status: {application.status}")  # Debug log
        flash('Application must be E-Admin approved first', 'error')
        return redirect(url_for('admin.se_admin_applications'))
    
    try:
        # Update application with rejection details
        application.status = 4  # se_admin_rejected
        application.se_admin_review_date = datetime.now()
        rejection_notes = request.form.get('notes')
        application.se_admin_notes = rejection_notes
        
        db.session.commit()
        
        # Send detailed rejection email to O-Convener
        send_email(
            to=application.email,
            subject='Your O-Convener Application Status',
            body=f'''We regret to inform you that your application to become an O-Convener has been rejected.

Application Details:
- Organization: {application.organization_name}
- Submitted: {application.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Reviewed by E-Admin: {application.e_admin_approval_date.strftime('%Y-%m-%d %H:%M:%S')}
- Final Review: {application.se_admin_review_date.strftime('%Y-%m-%d %H:%M:%S')}

Reason for Rejection:
{rejection_notes}

If you would like to appeal this decision or need further clarification, please contact our support team with your application ID: {application.application_id}

Best regards,
The E-DBA Team'''
        )
        
        flash('Application rejected and detailed notification sent to applicant', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')
    
    return redirect(url_for('admin.se_admin_applications'))

    # T-Admin Routes
@admin_bp.route('/t_admin/users/a')
def t_admin_users_a():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.user_type.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(db.select(Member)).scalars().all()
    
    return render_template('t-admin_users_a.html', users=users, search_query=search_query)

@admin_bp.route('/t_admin/users/b')
def t_admin_users_b():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                Member.user_type == 'E-Admin',
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(
            db.select(Member).where(Member.user_type == 'E-Admin')
        ).scalars().all()
    
    non_eadmin_users = db.session.execute(
        db.select(Member).where(Member.user_type != 'E-Admin')
    ).scalars().all()
    
    return render_template('t-admin_users_b.html', users=users, non_eadmin_users=non_eadmin_users, search_query=search_query)

@admin_bp.route('/t_admin/users/c')
def t_admin_users_c():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                Member.user_type == 'SE-Admin',
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(
            db.select(Member).where(Member.user_type == 'SE-Admin')
        ).scalars().all()
    
    eadmin_users = db.session.execute(
        db.select(Member).where(Member.user_type == 'E-Admin')
    ).scalars().all()
    
    return render_template('t-admin_users_c.html', users=users, eadmin_users=eadmin_users, search_query=search_query)

@admin_bp.route('/t_admin/users/d')
def t_admin_users_d():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                Member.user_type == 'T-Admin',
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(
            db.select(Member).where(Member.user_type == 'T-Admin')
        ).scalars().all()
    
    non_eadmin_users = db.session.execute(
        db.select(Member).where(Member.user_type != 'E-Admin')
    ).scalars().all()
    
    eadmin_users = db.session.execute(
        db.select(Member).where(Member.user_type == 'E-Admin')
    ).scalars().all()
    
    return render_template('t-admin_users_d.html', users=users, non_eadmin_users=non_eadmin_users, eadmin_users=eadmin_users, search_query=search_query)

@admin_bp.route('/t_admin/update_answer/<question_id>', methods=['POST'])
def t_admin_update_answer(question_id):
    new_answer = request.form.get('answer', '').strip()
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        if not new_answer:
            question.status = 0
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.t_admin_question_a'))

@admin_bp.route('/t_admin/questions/a')
def t_admin_question_a():
    search_query = request.args.get('search', '')
    
    if search_query:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(
                Question.status == 1,
                db.or_(
                    Question.description.ilike(f'%{search_query}%'),
                    Member.email.ilike(f'%{search_query}%'),
                    Question.answer.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(Question.status == 1)
        ).scalars().all()
    
    return render_template('t-admin_question_a.html', questions=questions, search_query=search_query)

@admin_bp.route('/t_admin/submit_answer/<question_id>', methods=['POST'])
def t_admin_submit_answer(question_id):
    new_answer = request.form.get('answer', '')
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        question.status = 1
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.t_admin_question_b'))

@admin_bp.route('/t_admin/questions/b')
def t_admin_question_b():
    search_query = request.args.get('search', '')
    
    if search_query:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(
                Question.status == 0,
                db.or_(
                    Question.description.ilike(f'%{search_query}%'),
                    Member.email.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        questions = db.session.execute(
            db.select(Question)
            .join(Member)
            .where(Question.status == 0)
        ).scalars().all()
    
    return render_template('t-admin_question_b.html', questions=questions, search_query=search_query)

@admin_bp.route('/t_admin/main')
def t_admin_main_page():
    return render_template('t-admin_main_page.html')

@admin_bp.route('/t_admin')
def t_admin_index():
    return redirect(url_for('admin.t_admin_user_management'))

@admin_bp.route('/t_admin/users')
def t_admin_user_management():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.user_type.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(db.select(Member)).scalars().all()
    
    return render_template('t-admin_user_management.html', users=users, search_query=search_query)

@admin_bp.route('/t_admin/grant_eadmin/<user_id>', methods=['POST'])
def t_admin_grant_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'E-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.t_admin_user_management'))

@admin_bp.route('/t_admin/revoke_eadmin/<user_id>', methods=['POST'])
def t_admin_revoke_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'User'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.t_admin_user_management'))

@admin_bp.route('/t_admin/grant_seadmin/<user_id>', methods=['POST'])
def t_admin_grant_seadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'SE-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.t_admin_user_management'))

@admin_bp.route('/t_admin/revoke_seadmin/<user_id>', methods=['POST'])
def t_admin_revoke_seadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'E-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.t_admin_user_management'))

# E-Admin Routes
@admin_bp.route('/e_admin/applications')
def e_admin_applications():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get pending applications
    applications = db.session.execute(
        db.select(Application)
        .filter_by(status=0)  # pending
        .order_by(Application.created_at.desc())
    ).scalars().all()
    
    # Check for applications nearing 3-day deadline
    current_time = datetime.now()
    for app in applications:
        time_diff = current_time - app.created_at
        if time_diff > timedelta(days=2):  # Warning after 2 days
            flash(f'Application {app.application_id} needs immediate attention! Processing deadline approaching.', 'warning')
    
    return render_template('e_admin_applications.html', 
                         applications=applications,
                         now=datetime.now(),
                         timedelta=timedelta)

@admin_bp.route('/e_admin/applications/<int:app_id>/approve', methods=['POST'])
def approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application or application.status != 0:
        flash('Invalid application', 'error')
        return redirect(url_for('admin.e_admin_applications'))
    
    try:
        # Update application status with timing information
        application.status = 1  # e_admin_approved
        application.e_admin_approval_date = datetime.now()
        
        # Calculate time taken for E-Admin review
        review_time = application.e_admin_approval_date - application.created_at
        
        db.session.commit()
        
        # Prepare detailed notification for Senior E-Admin
        senior_admins = db.session.execute(
            db.select(Member).filter_by(user_type='SE')
        ).scalars().all()
        
        for admin in senior_admins:
            send_email(
                to=admin.email,
                subject='New O-Convener Application Requires Your Review',
                body=f'''An O-Convener application has been approved and requires your review.

Application Details:
- Organization: {application.organization_name}
- Applicant Email: {application.email}
- Submission Date: {application.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- E-Admin Approval Date: {application.e_admin_approval_date.strftime('%Y-%m-%d %H:%M:%S')}
- Review Time: {review_time.days} days, {review_time.seconds//3600} hours
- Application ID: {application.application_id}

Supporting Documents:
{chr(10).join(f"- {doc.original_filename}" for doc in application.documents)}

Please review this application through your SE-Admin dashboard.
A workspace will be created upon your approval.

Action Required:
1. Review application details
2. Check supporting documents
3. Make final approval decision

Access the application at: {request.host_url}se_admin/applications
'''
            )
        
        flash('Application approved and detailed notification sent to Senior E-Admin', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving application: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/e_admin/applications/<int:app_id>/reject', methods=['POST'])
def reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application or application.status != 0:
        flash('Invalid application', 'error')
        return redirect(url_for('admin.e_admin_applications'))
    
    try:
        # Update application status
        application.status = 2  # e_admin_rejected
        application.e_admin_approval_date = datetime.now()
        db.session.commit()
        
        # Send rejection email to applicant
        send_email(
            to=application.email,
            subject='Your O-Convener Application Status',
            body=f'We regret to inform you that your application to become an O-Convener has been rejected.\n\n'
                 f'Organization: {application.organization_name}\n\n'
                 f'If you have any questions, please contact our support team.'
        )
        
        flash('Application rejected and applicant notified', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_applications'))

@admin_bp.route('/e_admin/policies')
def e_admin_policies():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policies = db.session.execute(
        db.select(Policy).order_by(Policy.created_at.desc())
    ).scalars().all()
    
    return render_template('e_admin_policies.html', policies=policies)

@admin_bp.route('/e_admin/policies/add', methods=['POST'])
def add_policy():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        pdf_file = request.files.get('pdf_file')
        
        policy = Policy(title=title, content=content)
        
        if pdf_file and pdf_file.filename:
            # Save PDF file
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf_file.filename}")
            pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'policies', filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            pdf_file.save(pdf_path)
            policy.pdf_path = f'policies/{filename}'
        
        db.session.add(policy)
        db.session.commit()
        
        flash('Policy added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding policy: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/e_admin/policies/<int:policy_id>/update', methods=['POST'])
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
            # Remove old PDF if exists
            if policy.pdf_path:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], policy.pdf_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            # Save new PDF
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf_file.filename}")
            pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'policies', filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            pdf_file.save(pdf_path)
            policy.pdf_path = f'policies/{filename}'
        
        policy.updated_at = datetime.now()
        db.session.commit()
        
        flash('Policy updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating policy: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/e_admin/policies/<int:policy_id>/delete', methods=['POST'])
def delete_policy(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    policy = db.session.get(Policy, policy_id)
    if not policy:
        flash('Policy not found', 'error')
        return redirect(url_for('admin.e_admin_policies'))
    
    try:
        # Remove PDF file if exists
        if policy.pdf_path:
            pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], policy.pdf_path)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        
        db.session.delete(policy)
        db.session.commit()
        
        flash('Policy deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting policy: {str(e)}', 'error')
    
    return redirect(url_for('admin.e_admin_policies'))

@admin_bp.route('/e_admin/policies/pdf/<int:policy_id>')
def download_policy_pdf(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        return jsonify({'error': 'Unauthorized'}), 401
    
    policy = db.session.get(Policy, policy_id)
    if not policy or not policy.pdf_path:
        return jsonify({'error': 'PDF not found'}), 404

    try:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            policy.pdf_path,
            as_attachment=True,
            download_name=f"policy_{policy_id}.pdf"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/e_admin/policies/<int:policy_id>')
def get_policy(policy_id):
    if 'user_id' not in session or session.get('user_type') != 'EE':
        return jsonify({'error': 'Unauthorized'}), 401
    
    policy = db.session.get(Policy, policy_id)
    if not policy:
        return jsonify({'error': 'Policy not found'}), 404
    
    return jsonify({
        'title': policy.title,
        'content': policy.content
    })

@admin_bp.route('/e_admin/bank-settings')
def bank_settings():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    bank_account = db.session.execute(
        db.select(EDBankAccount).order_by(EDBankAccount.account_id.desc()).limit(1)
    ).scalar()
    
    return render_template('e_admin_bank_settings.html', bank_account=bank_account)

@admin_bp.route('/e_admin/bank-settings/update', methods=['POST'])
def update_bank_account():
    if 'user_id' not in session or session.get('user_type') != 'EE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        account_number = request.form.get('account_number')
        membership_fee = float(request.form.get('membership_fee'))
        
        if membership_fee < 0:
            raise ValueError('Membership fee cannot be negative')
        
        # Get existing account or create new one
        bank_account = db.session.execute(
            db.select(EDBankAccount).order_by(EDBankAccount.account_id.desc()).limit(1)
        ).scalar()
        
        if bank_account:
            bank_account.account_number = account_number
            bank_account.membership_fee = membership_fee
        else:
            bank_account = EDBankAccount(
                account_number=account_number,
                membership_fee=membership_fee
            )
            db.session.add(bank_account)
        
        db.session.commit()
        flash('Bank account settings updated successfully', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating bank account settings: {str(e)}', 'error')
    
    return redirect(url_for('admin.bank_settings'))
