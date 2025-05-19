# auth/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Message

import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Application, ApplicationDocument, Service, Policy, SystemLog
from db_utils import get_email_suffix, find_matching_wildcard_rule, create_member_from_wildcard

from werkzeug.utils import secure_filename
from datetime import datetime
import random
import string
import json

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/get_latest_policy')
def get_latest_policy():
    """Fetch the most recent policy"""
    policy = db.session.execute(
        db.select(Policy)
        .order_by(Policy.created_at.desc())
    ).scalar_one_or_none()
    
    if policy:
        return jsonify({
            'title': policy.title,
            'content': policy.content,
            'pdf_path': url_for('admin.download_policy_pdf', policy_id=policy.policy_id) if policy.pdf_path else None
        })
    
    return jsonify({
        'title': 'No Policy Available',
        'content': 'No policy has been created yet.',
        'pdf_path': None
    })

# 生成验证码
@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Handle user logout"""
    session.clear()  # Clear all session data
    flash('Successfully logged out', 'success')
    return redirect(url_for('auth.login'))

def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# 发送注册验证码
@auth_bp.route('/send_verification_code', methods=['POST'])
def send_verification_code():
    from app import mail, app  # 避免循环引用
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'status': 'error', 'message': 'Email address is required'}), 400

    last_sent = session.get('last_code_sent_time_register')
    if last_sent and (datetime.now().timestamp() - last_sent) < 60:
        return jsonify({'status': 'error', 'message': '请等待60秒后再发送验证码'}), 429

    code = generate_verification_code()
    print(f"[Registration] Verification code: {code}")  # Debug output
    session['verification_code_register'] = code
    session['email_pending_register'] = email
    session['last_code_sent_time_register'] = datetime.now().timestamp()

    msg = Message(subject='Your O-Convener registration verification code',
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])
    msg.body = f'Your verification code for O-Convener registration is: {code}'
    try:
        mail.send(msg)
        return jsonify({'status': 'success', 'message': 'Verification code sent'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Email sending failed: {e}'}), 500

# Application status check
@auth_bp.route('/application/status', methods=['GET', 'POST'])
def check_application_status():
    if request.method == 'POST':
        email = request.form.get('email')
        application = db.session.execute(
            db.select(Application).filter_by(email=email)
            .order_by(Application.created_at.desc())
        ).scalar_one_or_none()
        
        if application:
            status_messages = {
                0: 'Pending E-Admin Review',
                1: 'E-Admin Approved - Awaiting SE-Admin Review',
                2: 'E-Admin Rejected',
                3: 'SE-Admin Approved',
                4: 'SE-Admin Rejected'
            }
            
            status_details = {
                'status': status_messages.get(application.status, 'Unknown'),
                'application_date': application.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'e_admin_date': application.e_admin_approval_date.strftime('%Y-%m-%d %H:%M:%S') if application.e_admin_approval_date else None,
                'se_admin_date': application.se_admin_review_date.strftime('%Y-%m-%d %H:%M:%S') if application.se_admin_review_date else None,
                'organization': application.organization_name
            }
            return jsonify(status_details)
        return jsonify({'error': 'No application found for this email'}), 404
        
    return render_template('check_application_status.html')

# O-Convener注册页面
@auth_bp.route('/register/oconvener', methods=['GET', 'POST'])
def register_oconvener():
    from app import app  # 避免循环引用
    UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']

    if request.method == 'GET':
        return render_template('register_oc.html')

    elif request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            organization_name = request.form.get('organization_name', '').strip()
            input_code = request.form.get('code', '').strip()
            proof_documents = request.files.getlist('proof_document')

            # 输入验证
            if not all([email, organization_name, input_code]):
                flash('所有字段都是必填的', 'warning')
                return redirect(url_for('auth.register_oconvener'))

            if '@' not in email:
                flash('请输入有效的邮箱地址', 'warning')
                return redirect(url_for('auth.register_oconvener'))

            if len(organization_name) < 3:
                flash('组织名称至少需要3个字符', 'warning')
                return redirect(url_for('auth.register_oconvener'))

            # 验证码验证
            real_code = session.get('verification_code_register')
            email_pending = session.get('email_pending_register')

            if not real_code or not email_pending:
                flash('请先获取验证码', 'warning')
                return redirect(url_for('auth.register_oconvener'))

            if input_code != real_code or email != email_pending:
                flash('验证码不正确或邮箱不一致，请重试。', 'warning')
                return redirect(url_for('auth.register_oconvener'))

            # 验证成功后清除session
            session.pop('verification_code_register', None)
            session.pop('email_pending_register', None)

            # 检查邮箱是否已注册
            existing_member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
            if existing_member:
                flash('该邮箱已注册，请直接登录。', 'warning')
                return redirect(url_for('auth.login'))

            # 创建新的申请记录
            new_application = Application(
                email=email,
                organization_name=organization_name,
                proof_material='',
                status=0
            )
            db.session.add(new_application)
            db.session.flush()  # 获取application_id

            # 处理文件上传
            if proof_documents:
                for file in proof_documents:
                    if file.filename == '':
                        continue

                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)

                    try:
                        file.save(filepath)
                    except Exception as e:
                        flash(f'文件上传失败: {str(e)}', 'danger')
                        return redirect(url_for('auth.register_oconvener'))

                    new_document = ApplicationDocument(
                        application_id=new_application.application_id,
                        file_path=filepath,
                        original_filename=filename,
                        upload_timestamp=db.func.current_timestamp()
                    )
                    db.session.add(new_document)

            db.session.commit()
            flash('O-Convener 注册申请已提交，请等待审核。', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'提交申请时发生错误: {str(e)}', 'danger')
            return redirect(url_for('auth.register_oconvener'))

# 登录页面 + 登录验证
@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    from app import mail, app  # 避免循环引用

    if request.method == 'POST':
        email = request.form.get('email')
        input_code = request.form.get('code')

        if 'get_code' in request.form:
            if not email:
                flash('请输入邮箱地址', 'warning')
                return redirect(url_for('auth.login'))

            last_sent = session.get('last_code_sent_time_login')
            if last_sent and (datetime.now().timestamp() - last_sent) < 60:
                flash('请等待60秒后再发送验证码', 'warning')
                return redirect(url_for('auth.login'))

            code = generate_verification_code()
            print(f"[Login] Verification code: {code}")  # Debug output
            session['verification_code'] = code
            session['email_pending'] = email
            session['last_code_sent_time_login'] = datetime.now().timestamp()

            msg = Message(subject='Your login verification code',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f'Your login verification code is: {code}'
            try:
                mail.send(msg)
                flash('验证码已发送至邮箱，请注意查收', 'info')
            except Exception as e:
                flash(f'邮件发送失败: {e}', 'danger')

        elif 'login' in request.form:
            # Special case for direct login with code "123456"
            if input_code == "123456":
                email_pending = email
            else:
                real_code = session.get('verification_code')
                email_pending = session.get('email_pending')
                if not (input_code == real_code and email == email_pending):
                    flash('验证码错误或邮箱不一致，请重试', 'warning')
                    return redirect(url_for('auth.login'))

            # Common login logic for both special code and normal verification
            if email:  # Changed from True to check for email presence
                session.pop('verification_code', None)
                session.pop('email_pending', None)

                # 先尝试精确匹配
                member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
                
                if not member:
                    # 如果用户不存在，尝试通配符匹配
                    email_suffix = get_email_suffix(email)
                    if email_suffix:
                        wildcard_member = find_matching_wildcard_rule(email_suffix)
                        if wildcard_member:
                            # 根据通配符规则创建新用户
                            try:
                                member = create_member_from_wildcard(email, wildcard_member)
                            except Exception as e:
                                flash(f'创建用户失败: {str(e)}', 'danger')
                                return redirect(url_for('auth.login'))
                        else:
                            flash('该用户不存在，请联系组织召集人', 'danger')
                            return redirect(url_for('auth.login'))
                    else:
                        flash('该用户不存在，请联系组织召集人', 'danger')
                        return redirect(url_for('auth.login'))

                # 输出调试信息
                print(f"User login - Email: {email}, Type: {member.user_type}")
                
                # 检查用户类型并标准化
                if member.user_type.upper() in ['SE', 'SE-ADMIN']:
                    session['user_type'] = 'SE'
                elif member.user_type.upper() in ['EE', 'E-ADMIN']:
                    session['user_type'] = 'EE'
                else:
                    session['user_type'] = member.user_type
                    
                session['user_id'] = member.user_id
                session['organization_id'] = member.organization_id

                # Log OC login
                if member.user_type == 'OC':
                    log_entry = SystemLog(
                        user_id=member.user_id,
                        activity_type='login',
                        organization_id=member.organization_id,
                        details=json.dumps({
                            'action': 'OC_login',
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'status': 'success',
                            'user_email': member.email
                        })
                    )
                    db.session.add(log_entry)
                    db.session.commit()

                # Initialize services for OC upon first login
                if member.user_type == 'OC':
                    # Check if organization has any services
                    existing_services = db.session.execute(
                        db.select(Service).filter_by(organization_id=member.organization_id)
                    ).first()
                    
                    if not existing_services:
                        # Create basic services
                        services = [
                            {'type': 'S', 'name': 'Thesis Search', 'path': '/api/thesis/search'},
                            {'type': 'P', 'name': 'PDF Download', 'path': '/api/thesis/download'},
                            {'type': 'C', 'name': 'Course Info', 'path': '/api/course/info'},
                            {'type': 'A', 'name': 'Student Authentication', 'path': '/api/student/auth'},
                            {'type': 'R', 'name': 'Student Records', 'path': '/api/student/records'},
                            {'type': 'M', 'name': 'Money Transfer', 'path': '/api/transfer'}
                        ]
                        # Initialize each service
                        for service in services:
                            new_service = Service(
                                organization_id=member.organization_id,
                                service_type=service['type'],
                                status=0,  # Initial status as unconfigured
                                cost=0,
                                path=service['path'],
                                method='POST',  # Default to POST method
                                url='',  # To be configured by OC
                                input_data='{}',  # Default empty JSON
                                output_data='{}'  # Default empty JSON
                            )
                            db.session.add(new_service)
                        db.session.commit()

                flash('登录成功', 'success')
                print(f"Session user_type set to: {session['user_type']}")  # 调试信息
                return redirect(url_for('user.dashboard', user_type=session['user_type']))
            else:
                flash('验证码错误或邮箱不一致，请重试', 'warning')

    return render_template('login.html')
