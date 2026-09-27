import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'
UPLOAD_DIR = BASE_DIR / 'static' / 'uploads'
INSTANCE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-change-this-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{INSTANCE_DIR / 'database.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_BYTES', 2 * 1024 * 1024))
    UPLOAD_FOLDER = str(UPLOAD_DIR)
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    ALLOWED_IMAGE_MIMETYPES = {'image/jpeg', 'image/png'}
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_HEADERS = ['X-CSRFToken', 'X-CSRF-Token']
