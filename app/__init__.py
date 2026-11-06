"""
NRDS Application Factory
Initializes Flask app and all extensions using the application factory pattern.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail

from config import get_config

# Extension instances (not yet bound to an app)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()


def create_app(config_class=None):
    """Application factory function."""

    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)

    # Login manager settings
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # Register blueprints
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

    # Register error handlers
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)

    # Register custom Jinja2 filters
    @app.template_filter("format_number")
    def format_number_filter(value):
        """Format an integer with thousands separators."""
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return value

    return app
