# user/views.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Organization, Service, Question, CourseInformation

import requests
import io
from flask import send_file

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
        return render_template('se_admin_main_page.html', user=member)
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
    return render_template('ask_for_help.html')

@user_bp.route('/submit-question', methods=['POST'])
def submit_question():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'})

    description = request.form.get('description')
    if not description:
        return jsonify({'status': 'error', 'message': 'Question description is required'})

    try:
        new_question = Question(
            description=description,
            sender_id=session['user_id'],
            status=0,
            answer=None
        )
        db.session.add(new_question)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Question has been sent',
            'redirect_url': url_for('user.dashboard', user_type=session.get('user_type'))
        })
    except Exception:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Failed to submit question'})

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
    
    if request.method == 'POST':
        organization_id = request.form.get('organization_id')
        if organization_id:
            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == 2)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('user.student_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    organizations = db.session.execute(
        db.select(Organization)
        .join(Service)
        .filter(Service.service_type == service_type)
        .filter(Service.status == 2)
        .distinct()
    ).scalars().all()
    
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
    
    return render_template('student_inquiry.html', 
                           service=service,
                           result=session.pop('inquiry_result', None))

@user_bp.route('/submit-inquiry/<int:service_id>', methods=['POST'])
def submit_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    try:
        data = {}
        files = {}
        for field_name, field_type in service.input_json.items():
            if field_type == 'file':
                if field_name in request.files:
                    files[field_name] = request.files[field_name]
            else:
                data[field_name] = request.form.get(field_name, '')
        
        url = service.url + service.path
        
        if files:
            response = requests.post(url, data=data, files=files)
        else:
            response = requests.post(url, json=data)
        
        session['inquiry_result'] = response.json()
        return redirect(url_for('user.student_inquiry', service_id=service_id))
        
    except Exception as e:
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('user.student_inquiry', service_id=service_id))

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
            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == 2)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('user.thesis_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    organizations = db.session.execute(
        db.select(Organization)
        .join(Service)
        .filter(Service.service_type == service_type)
        .filter(Service.status == 2)
        .distinct()
    ).scalars().all()
    
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
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    try:
        data = {}
        if 'search' in request.form:
            for field_name, field_type in service.input_json.items():
                data[field_name] = request.form.get(field_name, '')
            url = service.url + service.path
            response = requests.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                if result:
                    session['inquiry_result'] = result
                else:
                    session['inquiry_result'] = "No matching thesis found."
            else:
                session['inquiry_result'] = f"Error: {response.status_code} - {response.text}"
            return redirect(url_for('user.thesis_inquiry', service_id=service_id))

        elif 'download' in request.form:
            for field_name, field_type in service.input_json.items():
                data[field_name] = request.form.get(field_name, '')
            url = service.url + service.path
            response = requests.post(url, json=data)

            if response.status_code == 200:
                filename = 'thesis.pdf'
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    import re
                    filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1).strip('"\'')
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'

                file_obj = io.BytesIO(response.content)
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
            return redirect(url_for('user.dashboard', user_type=user.user_type))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add course information: {str(e)}', 'error')
            return redirect(url_for('user.provide_course_info'))
    
    return render_template('provide_course_info.html')
