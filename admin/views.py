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

# T-Admin Routes
@admin_bp.route('/t_admin/questions/a')
def t_admin_question_a():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
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
    
    return render_template('t-admin_question_a.html', questions=questions, search_query=search_query)

@admin_bp.route('/t_admin/questions/b')
def t_admin_question_b():
    if 'user_id' not in session or session.get('user_type') != 'TT':
        flash('Unauthorized access', 'error')
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
    
    return render_template('t-admin_question_b.html', questions=questions, search_query=search_query)

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
    
    return render_template('t-admin_user_management.html', admins=admins, search_query=search_query)

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

# E-Admin Routes
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
