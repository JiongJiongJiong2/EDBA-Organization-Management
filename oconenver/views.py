# oconvener/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Service, CourseInformation

import json

oconvener_bp = Blueprint('oconvener', __name__)

# 服务配置界面（列出当前组织所有服务）
@oconvener_bp.route('/configuration-interface/<int:organization_id>')
def configuration_interface(organization_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('auth.login'))

    if user.organization_id != organization_id:
        flash('You do not have permission to access this organization', 'error')
        return redirect(url_for('user.dashboard', user_type=user.user_type))

    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.status.in_([1, 2]))
        .order_by(Service.service_type)
    ).scalars().all()

    return render_template('configuration_interface.html',
                           services=services,
                           user=user)

# 提交服务配置
@oconvener_bp.route('/submit-configuration/<int:service_id>', methods=['POST'])
def submit_configuration(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    try:
        # 更新服务配置
        service.url = request.form.get('url', '')
        service.path = request.form.get('path', '')
        service.method = request.form.get('method', 'POST')

        try:
            input_json = json.loads(request.form.get('input_json', '{}'))
            output_json = json.loads(request.form.get('output_json', '{}'))
            service.input_json = input_json
            service.output_json = output_json
        except json.JSONDecodeError:
            flash('Invalid JSON format in inputs or outputs', 'error')
            return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

        db.session.commit()
        flash('Service configuration updated successfully', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service configuration: {str(e)}', 'error')

    return redirect(url_for('oconvener.configuration_interface', organization_id=service.organization_id))

# O-Convener添加课程信息
@oconvener_bp.route('/provide-course-info', methods=['GET', 'POST'])
def provide_course_info():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Unauthorized access', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))

    if request.method == 'POST':
        course_name = request.form.get('course_name')
        course_description = request.form.get('course_description')

        if not course_name:
            flash('Course name is required', 'error')
            return redirect(url_for('oconvener.provide_course_info'))

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
            return redirect(url_for('oconvener.provide_course_info'))

    return render_template('provide_course_info.html')
