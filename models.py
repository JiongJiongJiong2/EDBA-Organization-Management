import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Member(db.Model):
    __tablename__ = 'members'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    user_type = db.Column(db.String(2), nullable=False)

    '''
    用户类型  
    Admin role:
        O-Convener:     OC 
        T-admin:        TT
        E-admin:        EE 
        Senior E-admin: SE 
    
    Normal user role:
        Data provider:          PP 
        Public data consumer:   PC
        Private data consumer:  CC 
    '''

    fund = db.Column(db.Integer, nullable=False, default=50)  # 限定的钱数
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.organization_id'), nullable=False)

    organization = db.relationship('Organization', back_populates='members')

class Organization(db.Model):
    __tablename__ = 'organizations'
    organization_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    members = db.relationship('Member', back_populates='organization')
    services = db.relationship('Service', back_populates='organization')
    bank_accounts = db.relationship('BankAccount', back_populates='organization')

class Service(db.Model):
    __tablename__ = 'services'
    service_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.organization_id'), nullable=False)
    service_type = db.Column(db.String(1), nullable=False)
    # 'S': thesis search, 'P': PDF download, 'C': course info, 'A': student anthendicate, 'R': student GPA record and year info
    status = db.Column(db.Integer, nullable=False)  # 服务状态: 0, 1, 2
    cost = db.Column(db.Integer, nullable=False)

    url = db.Column(db.String(255), nullable=True)
    path = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(10), nullable=True)
    input_data = db.Column(db.String(255), nullable=True)
    output_data = db.Column(db.String(255), nullable=True)

    organization = db.relationship('Organization', back_populates='services')

    @property
    def input_json(self):
        """获取 input_data 的 JSON 对象"""
        return json.loads(self.input_data) if self.input_data else None

    @input_json.setter
    def input_json(self, value):
        """设置 input_data 的 JSON 字符串"""
        self.input_data = json.dumps(value) if value is not None else None

    @property
    def output_json(self):
        """获取 output_data 的 JSON 对象"""
        return json.loads(self.output_data) if self.output_data else None

    @output_json.setter
    def output_json(self, value):
        """设置 output_data 的 JSON 字符串"""
        self.output_data = json.dumps(value) if value is not None else None

class Application(db.Model):
    __tablename__ = 'applications'
    application_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    proof_material = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Integer, nullable=False)  #0,1,2
    organization_name = db.Column(db.String(100), nullable=False)

class Question(db.Model):
    __tablename__ = 'questions'
    question_id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('members.user_id'), nullable=False)
    status = db.Column(db.Integer, nullable=False)  # 0,1
    answer = db.Column(db.String(255), nullable=True)

    sender = db.relationship('Member', backref='questions')

class CourseInformation(db.Model):
    __tablename__ = 'course_info'
    course_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.organization_id'), nullable=False)
    description = db.Column(db.String(225), nullable=True)
    name = db.Column(db.String(255), nullable=False)

    organization = db.relationship('Organization', backref='courses')

class BankAccount(db.Model):
    __tablename__ = 'bank_accounts'
    account_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.organization_id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Integer, nullable=True)

    organization = db.relationship('Organization', back_populates='bank_accounts')

class ApplicationDocument(db.Model):
    __tablename__ = 'application_documents'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.application_id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    upload_timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())

    application = db.relationship('Application', backref='documents')
