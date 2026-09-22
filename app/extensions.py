"""extensions.py — Khởi tạo các extension dùng chung (db, migrate, csrf).
"""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData

# Đặt tên constraint có quy tắc để migration ổn định và dễ downgrade/sửa về sau
# (nếu không, PostgreSQL tự sinh tên ngẫu nhiên).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
migrate = Migrate()
csrf = CSRFProtect()  # chặn CSRF cho mọi request POST/PUT/DELETE dùng session cookie
