"""
NRDS Application Factory.
Improvement #1:  CSRF protection via Flask-WTF CSRFProtect.
Improvement #2:  Rate limiting via Flask-Limiter.
Improvement #20: Rotating file handler logging.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import get_config

# Extension instances
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app(config_class=None):
    """Application factory."""

    app = Flask(__name__, instance_relative_config=True)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Ensure logs directory exists (#20)
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)        # #1 CSRF
    limiter.init_app(app)     # #2 Rate limiting

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # ── Blueprints ────────────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.beneficiary import beneficiary_bp
    from app.routes.inventory import inventory_bp
    from app.routes.distribution import distribution_bp
    from app.routes.reports import reports_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(beneficiary_bp, url_prefix="/beneficiaries")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(distribution_bp, url_prefix="/distribution")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Error handlers ────────────────────────────────────────────────
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)

    # ── Custom Jinja2 filters ─────────────────────────────────────────
    @app.template_filter("format_number")
    def format_number_filter(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return value

    # ── Logging (#20) ─────────────────────────────────────────────────
    if not app.debug:
        _setup_logging(app, log_dir)

    return app


def _setup_logging(app, log_dir):
    """Configure rotating file logger for production use."""
    max_bytes = app.config.get("LOG_MAX_BYTES", 5 * 1024 * 1024)
    backup_count = app.config.get("LOG_BACKUP_COUNT", 5)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    # Application log
    app_handler = RotatingFileHandler(
        os.path.join(log_dir, "nrds.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.WARNING)

    # Error-only log
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "nrds_errors.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    app.logger.addHandler(app_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.WARNING)
