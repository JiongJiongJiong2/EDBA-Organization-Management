# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member, Question

from flask import send_from_directory

# Database connection function for legacy code
def get_db_connection():
    conn = sqlite3.connect('EDBA.db')
    conn.row_factory = sqlite3.Row
    return conn



admin_bp = Blueprint('admin', __name__)

# 查看所有注册申请列表
@admin_bp.route('/applications')
def admin_applications():
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    applications = db.session.execute(
        db.select(Application)
        .order_by(Application.status, Application.application_id)
    ).scalars().all()

    return render_template('admin_applications.html', applications=applications)

# 查看某一个申请的详情
@admin_bp.route('/application/<int:app_id>')
def admin_view_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin.admin_applications'))

    documents = db.session.execute(
        db.select(ApplicationDocument)
        .filter(ApplicationDocument.application_id == app_id)
        .order_by(ApplicationDocument.upload_timestamp)
    ).scalars().all()

    current_user_can_approve = (
        (application.status == 0 and session.get('user_type') in ['EE', 'SE']) or
        (application.status == 1 and session.get('user_type') == 'SE')
    )

    return render_template('admin_application_detail.html',
                            application=application,
                            documents=documents,
                            current_user_can_approve=current_user_can_approve)

# 下载申请者上传的文件
@admin_bp.route('/download/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    document = db.session.get(ApplicationDocument, doc_id)
    if not document:
        flash('Document not found', 'error')
        return redirect(url_for('admin.admin_applications'))

    try:
        directory = os.path.dirname(document.file_path)
        filename = os.path.basename(document.file_path)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('admin.admin_view_application', app_id=document.application_id))

# 审核通过申请
@admin_bp.route('/approve/<int:app_id>', methods=['POST'])
def admin_approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin.admin_applications'))

    try:
        # E-Admin can approve status 0 (pending), Senior E-Admin can approve status 1 (E-Admin approved)
        if (application.status == 0 and session.get('user_type') in ['EE', 'SE']) or \
           (application.status == 1 and session.get('user_type') == 'SE'):
            
            if application.status == 0:
                # First approval by E-Admin
                application.status = 1
                flash('Application approved by E-Admin, waiting for Senior E-Admin approval', 'success')
            elif application.status == 1:
                # Final approval by Senior E-Admin
                application.status = 3
                
                # Create new organization
                new_org = Organization(name=application.organization_name)
                db.session.add(new_org)
                db.session.flush()  # Get the new organization_id
                
                # Create O-Convener user
                new_member = Member(
                    email=application.email,
                    user_type='OC',
                    organization_id=new_org.organization_id,
                    fund=0  # Initial fund for O-Convener
                )
                db.session.add(new_member)
                
                flash('Application fully approved and organization created', 'success')

            db.session.commit()
        else:
            flash('You cannot approve this application at its current status', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Error approving application: {str(e)}', 'error')

    return redirect(url_for('admin_view_application', app_id=app_id))

# 拒绝申请
@admin_bp.route('/reject/<int:app_id>', methods=['POST'])
def admin_reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('auth.login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin.admin_applications'))

    try:
        if application.status in [0, 1]:
            application.status = 2  # 设置为拒绝状态
            db.session.commit()
            flash('Application rejected', 'success')
        else:
            flash('Cannot reject an application that is already finalized', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')

    return redirect(url_for('admin.admin_view_application', app_id=app_id))

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
@admin_bp.route('/e_admin/users/b')
def e_admin_users_b():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member)
            .where(
                Member.user_type == 'E-Admin',
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(
            db.select(Member)
            .where(Member.user_type == 'E-Admin')
        ).scalars().all()
    
    non_eadmin_users = db.session.execute(
        db.select(Member)
        .where(Member.user_type != 'E-Admin')
    ).scalars().all()
    
    return render_template('e_admin_user_b.html', users=users, non_eadmin_users=non_eadmin_users, search_query=search_query)

@admin_bp.route('/e_admin/questions/a', methods=['GET'])
def e_admin_question_a():
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
    
    return render_template('e_admin_question_a.html', questions=questions, search_query=search_query)

@admin_bp.route('/e_admin/questions/b', methods=['GET'])
def e_admin_question_b():
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
    
    return render_template('e_admin_question_b.html', questions=questions, search_query=search_query)

@admin_bp.route('/e_admin/update_answer/<question_id>', methods=['POST'])
def e_admin_update_answer(question_id):
    new_answer = request.form.get('answer', '')
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        if not new_answer:
            question.status = 0
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.e_admin_question_a'))

@admin_bp.route('/e_admin/submit_answer/<question_id>', methods=['POST'])
def e_admin_submit_answer(question_id):
    new_answer = request.form.get('answer', '')
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        question.status = 1
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.e_admin_question_b'))

@admin_bp.route('/e_admin/main')
def e_admin_main_page():
    return render_template('e_admin_main.html')

@admin_bp.route('/e_admin')
def e_admin_index():
    return render_template('e_admin_user_management.html')

@admin_bp.route('/e_admin/grant_eadmin/<user_id>', methods=['POST'])
def e_admin_grant_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'E-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.e_admin_user_management'))

@admin_bp.route('/e_admin/revoke_eadmin/<user_id>', methods=['POST'])
def e_admin_revoke_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'User'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.e_admin_user_management'))

# SE-Admin Routes
@admin_bp.route('/se_admin/users')
def se_admin_user_management():
    search_query = request.args.get('search', '')
    
    if search_query:
        users = db.session.execute(
            db.select(Member).where(
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        users = db.session.execute(db.select(Member)).scalars().all()
    
    return render_template('se_admin_user_management.html', users=users, search_query=search_query)

@admin_bp.route('/se_admin')
def se_admin_main_page1():
    return render_template('se_admin_user_management.html')

@admin_bp.route('/se_admin/main')
def se_admin_main_page2():
    return render_template('se_admin_main_page.html')

@admin_bp.route('/se_admin/users/c')
def se_admin_users_c():
    search_query = request.args.get('search', '')

    if search_query:
        se_admins = db.session.execute(
            db.select(Member).where(
                Member.user_type == 'SE-Admin',
                db.or_(
                    Member.email.ilike(f'%{search_query}%'),
                    Member.organization_id.ilike(f'%{search_query}%')
                )
            )
        ).scalars().all()
    else:
        se_admins = db.session.execute(
            db.select(Member).where(Member.user_type == 'SE-Admin')
        ).scalars().all()

    e_admins = db.session.execute(
        db.select(Member).where(Member.user_type == 'E-Admin')
    ).scalars().all()

    return render_template('se_admin_management.html',
                         se_admins=se_admins,
                         e_admins=e_admins,
                         search_query=search_query)

@admin_bp.route('/se_admin/questions/a')
def se_admin_question_a():
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
    
    return render_template('se_admin_answered_questions.html',
                         questions=questions,
                         search_query=search_query)

@admin_bp.route('/se_admin/questions/b')
def se_admin_question_b():
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
    
    return render_template('se_admin_unanswered_questions.html',
                         questions=questions,
                         search_query=search_query)

@admin_bp.route('/se_admin/update_answer/<question_id>', methods=['POST'])
def se_admin_update_answer(question_id):
    new_answer = request.form.get('answer', '').strip()
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        if not new_answer:
            question.status = 0
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.se_admin_question_a'))

@admin_bp.route('/se_admin/submit_answer/<question_id>', methods=['POST'])
def se_admin_submit_answer(question_id):
    new_answer = request.form.get('answer', '')
    question = db.session.get(Question, question_id)
    
    if question:
        question.answer = new_answer
        question.status = 1
        db.session.commit()
    
    return redirect(request.referrer or url_for('admin.se_admin_question_b'))

@admin_bp.route('/se_admin/grant_eadmin/<user_id>', methods=['POST'])
def se_admin_grant_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'E-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.se_admin_user_management'))

@admin_bp.route('/se_admin/revoke_eadmin/<user_id>', methods=['POST'])
def se_admin_revoke_eadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'User'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.se_admin_user_management'))

@admin_bp.route('/se_admin/grant_seadmin/<user_id>', methods=['POST'])
def se_admin_grant_seadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'SE-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.se_admin_user_management'))

@admin_bp.route('/se_admin/revoke_seadmin/<user_id>', methods=['POST'])
def se_admin_revoke_seadmin(user_id):
    user = db.session.get(Member, user_id)
    if user:
        user.user_type = 'E-Admin'
        db.session.commit()
    return redirect(request.referrer or url_for('admin.se_admin_user_management'))
