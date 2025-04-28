# config.py

import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Flask settings
    SECRET_KEY = '155178Hr'  # 你自己的密钥
    
    # 上传文件设置
    UPLOAD_FOLDER = os.path.join(basedir, 'instance', 'proof_documents')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB上传限制

    # 数据库设置
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "EDBA.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 邮件服务器配置
    MAIL_SERVER = 'smtp.qiye.aliyun.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'sdw@wbo4.top'
    MAIL_PASSWORD = 'j4lQqgUdUslOg5aDGElR'

    # 其他可以扩展，比如DEBUG模式
    DEBUG = True
