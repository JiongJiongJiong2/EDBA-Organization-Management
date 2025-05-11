# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file
import sqlite3
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member, Workspace
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
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    return render_template('se_admin_user_management.html')

@admin_bp.route('/se_admin/dashboard')
def se_admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    # Get count of pending applications for display
    pending_count = db.session.execute(
        db.select(db.func.count(Application.application_id))
        .filter_by(status=1)  # e_admin_approved
    ).scalar()
    
    return render_template('se_admin_main_page.html', pending_count=pending_count)

@admin_bp.route('/se_admin/applications')
def se_admin_applications():
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
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
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    document = db.session.get(ApplicationDocument, doc_id)
    if not document:
        flash('Document not found', 'error')
        return redirect(url_for('admin.se_admin_applications'))

    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        document.filename,
        as_attachment=True,
        download_name=document.original_filename
    )

@admin_bp.route('/se_admin/applications/<int:app_id>/approve', methods=['POST'])
def se_admin_approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application or application.status != 1:  # Must be e_admin_approved
        flash('Invalid application', 'error')
        return redirect(url_for('admin.se_admin_applications'))
        
    try:
        # Create organization
        organization = Organization(name=application.organization_name)
        db.session.add(organization)
        db.session.flush()  # Get organization_id
        
        # Create workspace
        workspace = Workspace(
            organization_id=organization.organization_id,
            name=f"{application.organization_name}'s Workspace"
        )
        db.session.add(workspace)
        db.session.flush()
        
        # Create O-Convener member
        member = Member(
            email=application.email,
            user_type='OC',
            organization_id=organization.organization_id
        )
        db.session.add(member)
        
        # Update application
        application.status = 3  # se_admin_approved
        application.se_admin_review_date = datetime.now()
        application.se_admin_notes = request.form.get('notes')
        application.workspace_id = workspace.workspace_id
        
        db.session.commit()
        
        # Send notification email to O-Convener
        send_email(
            to=application.email,
            subject='Your O-Convener Application Has Been Approved',
            body=f'Congratulations! Your application to become an O-Convener has been approved.\n\n'
                 f'Organization: {application.organization_name}\n'
                 f'You can now log in to the E-DBA system using your email address.\n\n'
                 f'Welcome to the E-DBA system!'
        )
        
        flash('Application approved successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving application: {str(e)}', 'error')
    
    return redirect(url_for('admin.se_admin_applications'))

@admin_bp.route('/se_admin/applications/<int:app_id>/reject', methods=['POST'])
def se_admin_reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') != 'SE':
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))
    
    application = db.session.get(Application, app_id)
    if not application or application.status != 1:  # Must be e_admin_approved
        flash('Invalid application', 'error')
        return redirect(url_for('admin.se_admin_applications'))
    
    try:
        # Update application
        application.status = 4  # se_admin_rejected
        application.se_admin_review_date = datetime.now()
        application.se_admin_notes = request.form.get('notes')
        
        db.session.commit()
        
        # Send notification email to O-Convener
        send_email(
            to=application.email,
            subject='Your O-Convener Application Status',
            body=f'We regret to inform you that your application to become an O-Convener has been rejected.\n\n'
                 f'Organization: {application.organization_name}\n'
                 f'Notes: {application.se_admin_notes}\n\n'
                 f'If you have any questions, please contact support.'
        )
        
        flash('Application rejected successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')
    
    return redirect(url_for('admin.se_admin_applications'))
