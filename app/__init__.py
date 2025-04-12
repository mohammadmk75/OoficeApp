from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_apscheduler import APScheduler
from flask_limiter.util import get_remote_address
from flask_mail import Mail
import os
import datetime
import pytz

scheduler = APScheduler()
db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)
mail = Mail()

iran_tz = pytz.timezone('Asia/Tehran')

# Override Flask-SQLAlchemy's default UTC behavior
def iran_now():
    return datetime.now(iran_tz)

# Patch SQLAlchemy to use Iran time by default
# db.Model.metadata.bind = db.engine
# db.Model.metadata.info['timezone'] = iran_tz

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.configs.Config')
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    scheduler.init_app(app)
    scheduler.start()

    from app.utils.decorators import user_name_filter
    app.add_template_filter(user_name_filter, name='user_name')

    
    from .views import main_blueprint
    app.register_blueprint(main_blueprint)
    print("MAIL_USERNAME:", app.config["MAIL_USERNAME"])
    print("MAIL_PASSWORD:", app.config["MAIL_PASSWORD"])  # Should print App Password
    print("UPLOAD_FOLDER:", app.config["UPLOAD_FOLDER"])
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


    return app
