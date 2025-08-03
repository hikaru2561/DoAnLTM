from flask import Blueprint, render_template, request, redirect, url_for, session
from models.models import User
from utils.db import db
from utils.auth import hash_password, check_password
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        user = User(
            Name=data['name'],
            username=data['username'],
            email=data['email'],
            phone=data['phone'],
            birthday=datetime.strptime(data['birthday'], "%Y-%m-%d"),
            country=data['country'],
            sex=bool(int(data['sex'])),
            hash_pass=hash_password(data['password'])
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password(password, user.hash_pass):
            session['user_id'] = user.ID
            session['username'] = user.username
            return redirect(url_for('views.dashboard'))
        else:
            return "Đăng nhập thất bại", 401
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
