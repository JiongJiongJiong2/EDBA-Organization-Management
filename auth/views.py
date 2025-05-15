# auth/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Message

import sys  
import os  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Application, ApplicationDocument

from werkzeug.utils import secure_filename
from datetime import datetime
import random
import string

auth_bp = Blueprint('auth', __name__)

# 生成验证码
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
            real_code = session.get('verification_code')
            email_pending = session.get('email_pending')

            if input_code == real_code and email == email_pending:
                session.pop('verification_code', None)
                session.pop('email_pending', None)

                member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
                if not member:
                    flash('该用户不存在，请联系组织召集人', 'danger')
                    return redirect(url_for('auth.login'))

                session['user_id'] = member.user_id
                session['user_type'] = member.user_type
                session['organization_id'] = member.organization_id
                flash('登录成功', 'success')
                return redirect(url_for('user.dashboard', user_type=member.user_type))
            else:
                flash('验证码错误或邮箱不一致，请重试', 'warning')

    return render_template('login.html')
