import os

class Config:
    SECRET_KEY = 'Your-Secret-Key'
    SQLALCHEMY_DATABASE_URI = 'Your Db Config'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True  # Ensure TLS is enabled
    MAIL_USE_SSL = False  # Do NOT use SSL; TLS is required
    MAIL_USERNAME = 'Your Email'
    MAIL_PASSWORD="Your App Mail Password"
    MAIL_DEFAULT_SENDER = 'Your Email'
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    SCHEDULER_API_ENABLED = True
