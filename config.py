# config.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 上传文件设置
    UPLOAD_FOLDER = os.path.join(basedir, 'instance', 'proof_documents')
    POLICIES_FOLDER = os.path.join(basedir, 'instance', 'policies')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB上传限制

    # 数据库设置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "EDBA.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 邮件服务器配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.example.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

    # 其他可以扩展，比如DEBUG模式
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'