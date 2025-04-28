# admin/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Application, ApplicationDocument, Organization, Member

from flask import send_from_directory


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
