import os

class Config:
    SECRET_KEY = 'pbbivvx9a*o$ng$*kk@$=)h9bq($jc1i9hb44r_1@bbnlhzoc'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:q-3yG_jBATn}=)UP^bZD97@localhost:5432/company-db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True  # Ensure TLS is enabled
    MAIL_USE_SSL = False  # Do NOT use SSL; TLS is required
    MAIL_USERNAME = 'keshavarzi96@gmail.com'
    MAIL_PASSWORD="ooerczcyolppglrn"
    MAIL_DEFAULT_SENDER = 'keshavarzi96@gmail.com'
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    SCHEDULER_API_ENABLED = True
