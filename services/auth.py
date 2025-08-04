from models.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import db


def register_user(username, password, email):
    if User.query.filter_by(username=username).first():
        return False, "Tài khoản đã tồn tại"
    hashed = generate_password_hash(password)
    new_user = User(username=username, hash_pass=hashed, email=email)
    db.session.add(new_user)
    db.session.commit()
    return True, "Đăng ký thành công"

def verify_login(username, password):
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.hash_pass, password):
        return False, "Tài khoản hoặc mật khẩu không đúng"
    return True, user
