"""
NRDS Configuration Module.
Improvement #3:  Secure session cookie settings.
Improvement #20: Logging configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "mysql+pymysql://root:@localhost/nrds_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "noreply@nrds.gov.ng")

    # CSRF (#1)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # Session cookie security (#3)
    SESSION_COOKIE_HTTPONLY = True      # JS cannot read session cookie
    SESSION_COOKIE_SAMESITE = "Lax"    # CSRF protection
    SESSION_COOKIE_SECURE = False       # Set True in production (requires HTTPS)
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours

    # Application metadata
    APP_NAME = "National Relief Distribution System"
    APP_VERSION = "1.0.0"
    APP_ACRONYM = "NRDS"
    ORGANIZATION = "NEMA"

    # NIN length
    NIN_LENGTH = 11

    # Logging (#20)
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
    LOG_BACKUP_COUNT = 5


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_SECURE = True   # Enforce HTTPS in production


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
