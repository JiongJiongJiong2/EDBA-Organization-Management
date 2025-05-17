# app.py
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
#!=!============================================================================================================================================================
#from models import db, Member, Organization, Service, Application, Question, CourseInformation, ApplicationDocument # Import ApplicationDocument
from models import db, Member, Organization, Service, Application, Question, CourseInformation, ApplicationDocument, BankAccount
#=============================================================================================================================================================
import random
import string
import os
from werkzeug.utils import secure_filename # Import secure_filename

UPLOAD_FOLDER = 'instance/proof_documents' # Define upload folder
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['SECRET_KEY'] = '155178Hr'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB文件大小限制

# 确保 instance 文件夹存在
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# 使用绝对路径配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "EDBA.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.qiye.aliyun.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False  # 禁用TLS
app.config['MAIL_USE_SSL'] = True   # 启用SSL
app.config['MAIL_USERNAME'] = 'sdw@wbo4.top'
app.config['MAIL_PASSWORD'] = 'j4lQqgUdUslOg5aDGElR'

# 初始化扩展
db.init_app(app)
mail = Mail(app)

def init_demo_data():
    """初始化演示数据"""
    # 检查是否已经有数据
    if Organization.query.first() is not None:
        return

    # 创建一个组织
    org1 = Organization(name="Demo Organization1")
    db.session.add(org1)
    db.session.commit()
    org2 = Organization(name="Demo Organization2")
    db.session.add(org2)
    db.session.commit()

    # 创建测试用户
    testmember1 = Member(
        email="r130026229@mail.uic.edu.cn",
        user_type="PP",  # Senior E-admin
        organization_id=org1.organization_id,
        fund=100
    )
    db.session.add(testmember1)
    db.session.commit()

    testmember2 = Member(
        email="s230026048@mail.uic.edu.cn",
        user_type="PP",  # Senior E-admin
        organization_id=org2.organization_id,
        fund=100
    )
    db.session.add(testmember2)
    db.session.commit()



    # 添加服务数据
    s1 = Service(
        organization_id=org1.organization_id,
        service_type='A',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/student/authenticate',
        method='POST',
        cost=1  # 添加 cost 参数
    )
    s1.input_json = {"name": "string", "id": "string", "photo": "file"}
    s1.output_json = {"status": "string"}

    s2 = Service(
        organization_id=org1.organization_id,
        service_type='R',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/student/record',
        method='POST',
        cost=1  # 添加 cost 参数
    )
    s2.input_json = {"name": "string", "id": "string"}
    s2.output_json = {"name": "string", "enroll_year": "string", "graduation_year": "string", "gpa": "number"}

    s3 = Service(
        organization_id=org1.organization_id,
        service_type='S',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/thesis/search',
        method='POST',
        cost=0  # 添加 cost 参数
    )
    s3.input_json = {"keywords": "string"}
    s3.output_json = {"title": "string", "abstract": "string"}

    s4 = Service(
        organization_id=org1.organization_id,
        service_type='P',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/thesis/pdf',
        method='POST',
        cost=1  # 添加 cost 参数
    )
    s4.input_json = {"title": "string"}
    s4.output_json = ["file"]

    s5 = Service(
        organization_id=org2.organization_id,
        service_type='A',
        status=2,
        cost=10  # 添加 cost 参数
    )

#new!=!=================================================================================================================================================
    s6 = Service(
        organization_id=org2.organization_id,
        service_type='M',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/bank/transfer',
        method='POST',
        cost=0  # 添加 cost 参数
    )
    s6.input_json = { 
        "from_bank": "string",
        "from_name": "string",
        "from_account": "string",
        "password": "string",
        "to_bank": "string",
        "to_name": "string",
        "to_account": "string",
        "amount": "int"
    }
    s6.output_json = {"feedback": "string"}
    s7 = Service(
        organization_id=org1.organization_id,
        service_type='M',
        status=2,
        url='http://172.16.160.88:8001',
        path='/hw/bank/transfer',
        method='POST',
        cost=0  # 添加 cost 参数
    )
    s7.input_json = { 
        "from_bank": "string",
        "from_name": "string",
        "from_account": "string",
        "password": "string",
        "to_bank": "string",
        "to_name": "string",
        "to_account": "string",
        "amount": "int"
    }
    s7.output_json = {"feedback": "string"}
#=======================================================================================================================================================
#!=!====================================================================================================================================================
    #db.session.add_all([s1, s2, s3, s4, s5])
    db.session.add_all([s1, s2, s3, s4, s5, s6, s7])
#=======================================================================================================================================================
    db.session.commit()

#new!=!================================================================================================================================================
    a1 = BankAccount(
        organization_id=org1.organization_id,
        bank = 'Bank of Utopia',
        name = 'EdGrow Finance Co.',
        number = '393077718917153',
        password = '9217'
    )
    
    a2 = BankAccount(
        organization_id=org2.organization_id,
        bank = 'Global Education Bank',
        name = 'BrightMind Capital',
        number = '265254690447221',
        password = '4664'
    )

    db.session.add_all([a1, a2])
    db.session.commit()
    
#====================================================================================================================================================

# 只在直接运行此文件时创建数据库和初始数据
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_demo_data()


def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@app.route('/send_verification_code', methods=['POST'])
def send_verification_code():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'status': 'error', 'message': 'Email address is required'}), 400

    # 检查时间间隔
    last_sent = session.get('last_code_sent_time_register')
    if last_sent and (datetime.now().timestamp() - last_sent) < 60:
        return jsonify({'status': 'error', 'message': '请等待60秒后再发送验证码'}), 429

    code = generate_verification_code()
    # 存储验证码、邮箱和时间戳
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


@app.route('/register/oconvener', methods=['GET', 'POST'])
def register_oconvener():
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
                return redirect(url_for('register_oconvener'))

            if not '@' in email:
                flash('请输入有效的邮箱地址', 'warning')
                return redirect(url_for('register_oconvener'))

            if len(organization_name) < 3:
                flash('组织名称至少需要3个字符', 'warning')
                return redirect(url_for('register_oconvener'))

            # 验证码验证
            real_code = session.get('verification_code_register')
            email_pending = session.get('email_pending_register')

            if not real_code or not email_pending:
                flash('请先获取验证码', 'warning')
                return redirect(url_for('register_oconvener'))

            if input_code != real_code or email != email_pending:
                flash('验证码不正确或邮箱不一致，请重试。', 'warning')
                return redirect(url_for('register_oconvener'))

            # 验证成功后清除 session 中的验证码信息
            session.pop('verification_code_register', None)
            session.pop('email_pending_register', None)

            # 验证邮箱是否已注册
            existing_member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
            if existing_member:
                flash('该邮箱已注册，请直接登录。', 'warning')
                return redirect(url_for('login'))

            # 创建新的申请记录
            new_application = Application(
                email=email,
                organization_name=organization_name,
                proof_material='', # 暂时留空或存储主文件信息，具体取决于需求
                status=0 # 0: 待 E-Admin 审核
            )
            db.session.add(new_application)
            db.session.flush() # 获取 application_id

            # 处理文件上传并记录到 application_documents 表
            if proof_documents:
                for file in proof_documents:
                    if file.filename == '':
                        continue # Skip empty file inputs

                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    try:
                        file.save(filepath)
                        print(f"文件保存成功: {filepath}")  # 调试信息
                    except Exception as e:
                        print(f"文件保存失败: {str(e)}")  # 调试信息
                        flash(f'文件上传失败: {str(e)}', 'danger')
                        return redirect(url_for('register_oconvener'))

                    new_document = ApplicationDocument(
                        application_id=new_application.application_id,
                        file_path=filepath,
                        original_filename=filename,
                        upload_timestamp=db.func.current_timestamp() # 使用数据库函数获取当前时间
                    )
                    db.session.add(new_document)

            db.session.commit()
            flash('O-Convener 注册申请已提交，请等待审核。', 'success')
            return redirect(url_for('login')) # 或者重定向到申请成功页面

        except Exception as e:
            db.session.rollback()
            flash(f'提交申请时发生错误: {str(e)}', 'danger')
            return redirect(url_for('register_oconvener'))

        # 验证成功后清除 session 中的验证码信息
        session.pop('verification_code_register', None)
        session.pop('email_pending_register', None)

        # 2. 验证邮箱是否已注册
        existing_member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
        if existing_member:
            flash('该邮箱已注册，请直接登录。', 'warning')
            return redirect(url_for('login'))

        # 3. 创建新的申请记录
        try:
            new_application = Application(
                email=email,
                organization_name=organization_name,
                proof_material='', # 暂时留空或存储主文件信息，具体取决于需求
                status=0 # 0: 待 E-Admin 审核
            )
            db.session.add(new_application)
            db.session.flush() # 获取 application_id

            # 4. 处理文件上传并记录到 application_documents 表
            if proof_documents:
                for file in proof_documents:
                    if file.filename == '':
                        continue # Skip empty file inputs

                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    new_document = ApplicationDocument(
                        application_id=new_application.application_id,
                        file_path=filepath,
                        original_filename=filename,
                        upload_timestamp=db.func.current_timestamp() # 使用数据库函数获取当前时间
                    )
                    db.session.add(new_document)

            db.session.commit()
            flash('O-Convener 注册申请已提交，请等待审核。', 'success')
            return redirect(url_for('login')) # 或者重定向到申请成功页面

        except Exception as e:
            db.session.rollback()
            flash(f'提交申请时发生错误: {str(e)}', 'danger')
            return redirect(url_for('register_oconvener'))

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        input_code = request.form.get('code')

        if 'get_code' in request.form:
            if not email:
                flash('Please provide a valid email address', 'warning')
                return redirect(url_for('login'))

            # 检查时间间隔
            last_sent = session.get('last_code_sent_time_login')
            if last_sent and (datetime.now().timestamp() - last_sent) < 60:
                flash('请等待60秒后再发送验证码', 'warning')
                return redirect(url_for('login'))

            code = generate_verification_code()
            session['verification_code'] = code
            session['email_pending'] = email
            session['last_code_sent_time_login'] = datetime.now().timestamp()

            msg = Message(subject='Your login verification code',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f'Your login verification code is: {code}'
            try:
                mail.send(msg)
                flash('The verification code has been sent to your email, please check it carefully', 'info')
            except Exception as e:
                flash(f'Email sending failed: {e}', 'danger')

        elif 'login' in request.form:
            real_code = session.get('verification_code')
            email_pending = session.get('email_pending')

            if input_code == real_code and email == email_pending:
                session.pop('verification_code', None)
                session.pop('email_pending', None)

                member = db.session.execute(db.select(Member).filter_by(email=email)).scalar_one_or_none()
                if not member:
                    flash('The user does not exist, please contact your organization converter', 'danger')
                    return redirect(url_for('login'))

                session['user_id'] = member.user_id
                session['user_type'] = member.user_type
                session['organization_id'] = member.organization_id
                flash('Login succeeded', 'success')
                return redirect(url_for('dashboard', user_type=member.user_type))
            else:
                flash('The verification code is incorrect or the email address is inconsistent. Please try again', 'warning')

    return render_template('login.html') # No changes needed here, the link will be added in login.html

@app.route('/dashboard/<user_type>')
def dashboard(user_type):
    valid_types = ['OC', 'PP', 'PC', 'CC', 'EE', 'TT', 'SE']  # 所有有效的用户类型
    user_id = session.get('user_id')

    if user_type not in valid_types:
        flash('Invalid user type', 'danger')
        return redirect(url_for('login'))
    
    member = db.session.get(Member, user_id)
    if not member:
        flash('User information retrieval failed, please log in again', 'danger')
        return redirect(url_for('login'))

    return render_template('dashboard_data_user.html', user=member)

@app.route('/ask-for-help')
def ask_for_help():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    return render_template('ask_for_help.html')

@app.route('/submit-question', methods=['POST'])
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
            'redirect_url': url_for('dashboard', user_type=session.get('user_type'))
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to submit question'
        })

@app.route('/organization-list-student/<service_type>', methods=['GET', 'POST'])
def organization_list_student(service_type):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        organization_id = request.form.get('organization_id')
        if organization_id:
            # 查找该组织提供的对应服务类型的服务
            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == 2)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('student_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    # GET 请求逻辑
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

@app.route('/student-inquiry/<int:service_id>', methods=['GET'])
def student_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    service = db.session.get(Service, service_id)
    user = db.session.get(Member, session['user_id'])
    
    if not service or not user:
        flash('Service not found', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    return render_template('student_inquiry.html', 
                         service=service,
                         user=user,
                         result=session.pop('inquiry_result', None))

@app.route('/submit-inquiry/<int:service_id>', methods=['POST'])
def submit_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    service = db.session.get(Service, service_id)
    user = db.session.get(Member, session['user_id'])
    
    if not service or not user:
        flash('Service or user not found', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    # 检查用户资金是否足够
    if service.cost > 0:
        if user.fund < service.cost:
            flash('Your fund is not enough. Please contact your organization convener.', 'error')
            return redirect(url_for('student_inquiry', service_id=service_id))
    
    try:
        import requests
        
        # 准备发送的数据
        data = {}
        files = {}
        for field_name, field_type in service.input_json.items():
            if field_type == 'file':
                if field_name in request.files:
                    files[field_name] = request.files[field_name]
            else:
                data[field_name] = request.form.get(field_name, '')
        
        # 如果服务需要付费，先处理支付
        if service.cost > 0:
            success, message = process_payment(user.organization_id, service.organization_id, service.cost)
            if not success:
                flash(f'Payment failed: {message}. Please contact your organization convener.', 'error')
                return redirect(url_for('student_inquiry', service_id=service_id))
            
            # 扣除用户资金
            user.fund -= service.cost
            db.session.commit()
        
        # 构建完整的URL
        url = service.url + service.path
        
        # 发送请求
        if files:
            response = requests.post(url, data=data, files=files)
        else:
            response = requests.post(url, json=data)
        
        # 存储结果并重定向
        session['inquiry_result'] = response.json()
        return redirect(url_for('student_inquiry', service_id=service_id))
        
    except Exception as e:
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('student_inquiry', service_id=service_id))

@app.route('/organization-list-thesis/<service_type>', methods=['GET', 'POST'])
def organization_list_thesis(service_type):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        organization_id = request.form.get('organization_id')
        if organization_id:
            # 查找该组织提供的对应服务类型的服务
            service = db.session.execute(
                db.select(Service)
                .filter(Service.organization_id == organization_id)
                .filter(Service.service_type == service_type)
                .filter(Service.status == 2)
            ).scalar_one_or_none()
            
            if service:
                return redirect(url_for('thesis_inquiry', service_id=service.service_id))
            else:
                flash('Service not available', 'error')
    
    # GET 请求逻辑
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

@app.route('/thesis-inquiry/<int:service_id>', methods=['GET'])
def thesis_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    user = db.session.get(Member, session['user_id'])
    
    return render_template('thesis_inquiry.html', 
                         service=service,
                         user=user,
                         result=session.pop('inquiry_result', None))

@app.route('/submit-thesis-inquiry/<int:service_id>', methods=['POST'])
def submit_thesis_inquiry(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    try:
        import requests
        from flask import send_file
        import io
        
        # 准备发送的数据
        data = {}
        if 'search' in request.form:
            # 搜索逻辑保持不变
            for field_name, field_type in service.input_json.items():
                data[field_name] = request.form.get(field_name, '')
            # 构建完整的URL（使用搜索路径）
            url = service.url + service.path  # 使用搜索专用的路径
            
            # 发送请求
            response = requests.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    session['inquiry_result'] = result
                else:
                    session['inquiry_result'] = "No matching thesis found."
            else:
                session['inquiry_result'] = f"Error: {response.status_code} - {response.text}"
            
            return redirect(url_for('thesis_inquiry', service_id=service_id))
            
        elif 'download' in request.form:
            # 论文下载
            for field_name, field_type in service.input_json.items():
                data[field_name] = request.form.get(field_name, '')
            # 构建完整的URL
            url = service.url + service.path
            
            # 发送请求并获取文件
            response = requests.post(url, json=data)
            
            if response.status_code == 200:
                # 从响应中获取正确的文件名
                filename = 'thesis.pdf'  # 默认文件名
                
                # 1. 首先尝试从 Content-Disposition 头获取文件名
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    import re
                    try:
                        filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                        if filename_match:
                            filename = filename_match.group(1).strip('"\'')
                    except Exception:
                        pass
                
                # 2. 如果头部没有文件名，尝试从响应内容中获取
                if filename == 'thesis.pdf':
                    try:
                        # 尝试解析响应为 JSON
                        resp_data = response.json()
                        # 检查常见的文件名字段
                        for field in ['filename', 'file_name', 'name']:
                            if field in resp_data:
                                filename = resp_data[field]
                                break
                    except Exception:
                        # 如果响应不是 JSON 或解析失败，继续使用默认文件名
                        pass

                # 确保文件名以 .pdf 结尾
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                
                # 创建内存文件对象
                file_obj = io.BytesIO(response.content)
                
                # 返回下载响应
                return send_file(
                    file_obj,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
            else:
                flash(f'Download failed: {response.status_code} - {response.text}', 'error')
                return redirect(url_for('thesis_inquiry', service_id=service_id))
        
    except Exception as e:
        flash(f'Error occured: {str(e)}', 'error')
        return redirect(url_for('thesis_inquiry', service_id=service_id))
    
@app.route('/submit-configuration/<int:service_id>', methods=['POST'])
def submit_configuration(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    service = db.session.get(Service, service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    try:
        import json
        # 更新服务配置
        service.url = request.form.get('url', '')
        service.path = request.form.get('path', '')
        service.method = request.form.get('method', 'POST')
        
        # 解析并验证 JSON 输入
        try:
            input_json = json.loads(request.form.get('input_json', '{}'))
            output_json = json.loads(request.form.get('output_json', '{}'))
            service.input_json = input_json
            service.output_json = output_json
        except json.JSONDecodeError:
            flash('Invalid JSON format in inputs or outputs', 'error')
            return redirect(url_for('configuration_interface', organization_id=service.organization_id))
        
        db.session.commit()
        flash('Service configuration updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service configuration: {str(e)}', 'error')
    
    return redirect(url_for('configuration_interface', organization_id=service.organization_id))

@app.route('/configuration-interface/<int:organization_id>')
def configuration_interface(organization_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user:
        flash('User information not found', 'error')
        return redirect(url_for('login'))
    
    # 验证用户是否属于该组织
    if user.organization_id != organization_id:
        flash('You do not have permission to access this organization', 'error')
        return redirect(url_for('dashboard', user_type=user.user_type))
    
    # 获取组织的所有服务（状态为1或2）
    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.status.in_([1, 2]))
        .order_by(Service.service_type)
    ).scalars().all()
    
    return render_template('configuration_interface.html',
                         services=services,
                         user=user)

@app.route('/provide-course-info', methods=['GET', 'POST'])
def provide_course_info():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard', user_type=session.get('user_type')))
    
    if request.method == 'POST':
        course_name = request.form.get('course_name')
        course_description = request.form.get('course_description')
        
        if not course_name:
            flash('Course name is required', 'error')
            return redirect(url_for('provide_course_info'))
        
        try:
            new_course = CourseInformation(
                organization_id=user.organization_id,
                name=course_name,
                description=course_description
            )
            db.session.add(new_course)
            db.session.commit()
            flash('Course information has been successfully added', 'success')
            return redirect(url_for('dashboard', user_type=user.user_type))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add course information: {str(e)}', 'error')
            return redirect(url_for('provide_course_info'))
    
    return render_template('provide_course_info.html')

@app.route('/course-info-check')
def course_info_check():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    course_name = request.args.get('course_name', '')
    
    if course_name:
        # 使用 SQL 的 LIKE 操作符进行模糊查询
        courses = db.session.execute(
            db.select(CourseInformation)
            .join(Organization)
            .filter(CourseInformation.name.ilike(f'%{course_name}%'))
            .order_by(CourseInformation.name)
        ).scalars().all()
    else:
        courses = []
    
    return render_template('course_info_check.html', courses=courses)

# Admin application management routes
@app.route('/admin/applications')
def admin_applications():
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))

    applications = db.session.execute(
        db.select(Application)
        .order_by(Application.status, Application.application_id)
    ).scalars().all()

    return render_template('admin_applications.html', applications=applications)

@app.route('/admin/application/<int:app_id>')
def admin_view_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin_applications'))

    documents = db.session.execute(
        db.select(ApplicationDocument)
        .filter(ApplicationDocument.application_id == app_id)
        .order_by(ApplicationDocument.upload_timestamp)
    ).scalars().all()

    # Check if current user can approve (E-Admin can approve status 0, Senior E-Admin can approve status 1)
    current_user_can_approve = (
        (application.status == 0 and session.get('user_type') in ['EE', 'SE']) or
        (application.status == 1 and session.get('user_type') == 'SE')
    )

    return render_template('admin_application_detail.html',
                         application=application,
                         documents=documents,
                         current_user_can_approve=current_user_can_approve)

@app.route('/admin/download/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))

    document = db.session.get(ApplicationDocument, doc_id)
    if not document:
        flash('Document not found', 'error')
        return redirect(url_for('admin_applications'))

    try:
        from flask import send_from_directory
        import os
        directory = os.path.dirname(document.file_path)
        filename = os.path.basename(document.file_path)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('admin_view_application', app_id=document.application_id))

@app.route('/admin/approve/<int:app_id>', methods=['POST'])
def admin_approve_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin_applications'))

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

@app.route('/admin/reject/<int:app_id>', methods=['POST'])
def admin_reject_application(app_id):
    if 'user_id' not in session or session.get('user_type') not in ['EE', 'SE']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))

    application = db.session.get(Application, app_id)
    if not application:
        flash('Application not found', 'error')
        return redirect(url_for('admin_applications'))

    try:
        # Only allow rejection if status is pending (0 or 1)
        if application.status in [0, 1]:
            application.status = 2  # Rejected
            db.session.commit()
            flash('Application rejected', 'success')
        else:
            flash('Cannot reject an application that is already finalized', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting application: {str(e)}', 'error')

    return redirect(url_for('admin_view_application', app_id=app_id))

@app.route('/check_payment_service/<int:organization_id>')
def check_payment_service(organization_id):
    # 查找组织的支付服务
    payment_service = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.service_type == 'M')
        .filter(Service.status == 2)
    ).scalar_one_or_none()
    
    return jsonify({'hasPaymentService': payment_service is not None})

def process_payment(from_org_id, to_org_id, amount):
    try:
        # 获取支付方组织的支付服务
        payment_service = db.session.execute(
            db.select(Service)
            .filter(Service.organization_id == from_org_id)
            .filter(Service.service_type == 'M')
            .filter(Service.status == 2)
        ).scalar_one_or_none()
        
        if not payment_service:
            return False, "No transfer service available"
        
        # 获取支付方的银行账户信息
        from_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == from_org_id)
        ).scalar_one_or_none()
        
        # 获取接收方的银行账户信息
        to_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == to_org_id)
        ).scalar_one_or_none()
        
        if not from_account or not to_account:
            return False, "Bank account information not found"
        
        # 准备支付请求数据
        payment_data = {
            "from_bank": from_account.bank,
            "from_name": from_account.name,
            "from_account": from_account.number,
            "password": from_account.password,
            "to_bank": to_account.bank,
            "to_name": to_account.name,
            "to_account": to_account.number,
            "amount": amount
        }
        
        # 发送支付请求
        import requests
        url = payment_service.url + payment_service.path
        response = requests.post(url, json=payment_data)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, "Payment failed"
            
    except Exception as e:
        return False, str(e)

if __name__ == '__main__':
    app.run(debug=True)
