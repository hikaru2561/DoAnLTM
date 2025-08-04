from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)

# Trang chủ
@views_bp.route('/')
def home():
    return render_template('dashboard.html')

# Đăng nhập
@views_bp.route('/login')
def login():
    return render_template('login.html')

# Đăng ký
@views_bp.route('/register')
def register():
    return render_template('register.html')

# Dashboard chính (có thể là tổng quan)
@views_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ===== 📌 QUẢN LÝ TÀI CHÍNH =====

@views_bp.route('/wallet/deposit')
def deposit():
    return render_template('wallet/deposit.html')

@views_bp.route('/wallet/withdraw')
def withdraw():
    return render_template('wallet/withdraw.html')

@views_bp.route('/wallet/history')
def wallet_history():
    return render_template('wallet/history.html')

# ===== 📌 QUẢN LÝ LỆNH GIAO DỊCH =====

@views_bp.route('/order/place')
def place_order():
    return render_template('order_place.html')

@views_bp.route('/order/history')
def order_history():
    return render_template('order_history.html')

@views_bp.route('/order/book')
def order_book():
    return render_template('order_book.html')

# ===== 📌 DANH MỤC TÀI SẢN =====

@views_bp.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')
