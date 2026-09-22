"""app/__init__.py """
import os

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.config import CONFIGS
from app.extensions import csrf, db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Tạo và cấu hình app. config_name: development | production | testing."""
    config_name = config_name or os.getenv("APP_ENV", "development")
    config_class = CONFIGS[config_name]
    config_class.validate()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Import models để Alembic thấy metadata khi autogenerate migration
    from app import models  # noqa: F401

    _register_blueprints(app)
    _register_error_handlers(app)

    # from app.cli import register_cli

    # register_cli(app)
    return app


def _register_blueprints(app: Flask) -> None:
    """Đăng ký các blueprint (mỗi blueprint = một nhóm route)."""
    from app.route.admin_rooms import bp as admin_rooms_bp
    from app.route.api_rooms import bp as api_rooms_bp
    from app.route.auth import bp as auth_bp
    from app.route.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_rooms_bp)
    app.register_blueprint(api_rooms_bp)


def _register_error_handlers(app: Flask) -> None:
    """Trả JSON cho /api/*, trang HTML đơn giản cho các đường dẫn còn lại."""

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return render_template("error.html", error=error), error.code
