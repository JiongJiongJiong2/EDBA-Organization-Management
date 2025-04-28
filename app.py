# app.py

from flask import Flask, redirect, url_for
from models import db
from flask_mail import Mail

# 导入各个蓝图
from auth.views import auth_bp
from user.views import user_bp
from oconvener.views import oconvener_bp
from admin.views import admin_bp

# 导入配置文件
from config import Config

# 初始化邮件对象
mail = Mail()

def create_app():
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(Config)

    # 初始化数据库和邮件系统
    db.init_app(app)
    mail.init_app(app)

    # 注册蓝图（Blueprints）
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(oconvener_bp, url_prefix='/oconvener')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
