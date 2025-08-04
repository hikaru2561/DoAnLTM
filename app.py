import eventlet
eventlet.monkey_patch()
from flask import Flask, request,jsonify,render_template,session
from flask_socketio import SocketIO
from config import Config
from utils.db import init_db
from flask_socketio import emit,SocketIO
from utils.db import SessionLocal
from models.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from utils.auth import create_jwt
import time
from ssi_fc_data import model
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import config
import json
import threading
import queue
from datetime import date,timedelta
from models.models import GiaoDich, QuyNguoiDung,DatLenh,DanhMucDauTu,MarketData  
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps


# Khởi tạo client và stream
client = MarketDataClient(config)
mm = MarketDataStream(config, client)
data1 = []
symbols = []
user_sessions = {}
latest_data = {}
VN30 = []
HNX30 = []
HOSE = []
HNX = []
UPCOM = []
VN100 = []
connected_clients = {}
task_queue = queue.Queue()
NUM_WORKERS = 3


app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.secret_key = 'chungkhoanrealtime' 
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 
init_db()

socketio = SocketIO(app)

# Register routes

def init_app():
    global mm,VN100,VN30,HNX30,HOSE,HNX,UPCOM
    mm.start(get_data, get_error, "X:ALL")

    HOSE = get_symbols_from_exchange('HOSE')
    time.sleep(0.1)

    HNX = get_symbols_from_exchange('HNX')
    time.sleep(0.1)

    UPCOM = get_symbols_from_exchange('UPCOM')
    time.sleep(0.1)

    VN30 = get_symbols_from_index('vn30')
    time.sleep(0.1)

    VN100 = get_symbols_from_index('vn100')
    time.sleep(0.1)

    HNX30 = get_symbols_from_index('hnx30')
    threading.Thread(target=broadcast_market_data_loop, daemon=True).start()

def get_user_id(sid):
    return user_sessions.get(sid)

def broadcast_market_data_loop():
    global connected_clients
    while True:
        if connected_clients:
            session = SessionLocal()
            try:
                for sid, symbol_list in connected_clients.items():
                    if not symbol_list:
                        continue
                    # Truy vấn dữ liệu phù hợp với symbol_list của client này
                    results = session.query(MarketData).filter(MarketData.Symbol.in_(symbol_list)).all()
                    for row in results:
                        data = {
                            'Symbol': row.Symbol,
                            'BidPrice1': row.BidPrice1, 'BidVol1': row.BidVol1,
                            'BidPrice2': row.BidPrice2, 'BidVol2': row.BidVol2,
                            'BidPrice3': row.BidPrice3, 'BidVol3': row.BidVol3,
                            'AskPrice1': row.AskPrice1, 'AskVol1': row.AskVol1,
                            'AskPrice2': row.AskPrice2, 'AskVol2': row.AskVol2,
                            'AskPrice3': row.AskPrice3, 'AskVol3': row.AskVol3,
                            'LastPrice': row.LastPrice, 'LastVol': row.LastVol,
                            'Change': row.Change, 'RatioChange': row.RatioChange,
                            'Ceiling': row.Ceiling, 'Floor': row.Floor, 'RefPrice': row.RefPrice,
                            'High': row.High, 'Low': row.Low, 'TotalVol': row.TotalVol
                        }
                        socketio.emit('server_data', json.dumps(data, ensure_ascii=False), room=sid)
            except Exception as e:
                print(f"❌ Lỗi khi gửi dữ liệu: {e}")
            finally:
                session.close()
        time.sleep(0.1)


def insert_or_update_market_data(content: dict):
    session = SessionLocal()
    try:
        symbol = content.get("Symbol")
        if not symbol:
            return

        existing = session.query(MarketData).filter_by(Symbol=symbol).first()
        if not existing:
            existing = MarketData(Symbol=symbol)

        # Cập nhật tất cả các trường
        for field in [
            "BidPrice1", "BidVol1", "BidPrice2", "BidVol2", "BidPrice3", "BidVol3",
            "AskPrice1", "AskVol1", "AskPrice2", "AskVol2", "AskPrice3", "AskVol3",
            "LastPrice", "LastVol", "Change", "RatioChange",
            "Ceiling", "Floor", "RefPrice",
            "High", "Low", "TotalVol"  # <--- thêm vào đây
        ]:
            if field in content:
                setattr(existing, field, content[field])

        session.merge(existing)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"❌ DB insert/update error: {e}")
    finally:
        session.close()


# Register WebSocket event
def get_data(message):
    if not isinstance(message, dict) or "Content" not in message:
        return

    content_str = message.get("Content")
    if not isinstance(content_str, str):
        return

    try:
        content = json.loads(content_str)
        insert_or_update_market_data(content)
    except Exception as e:
        print("❌ Lỗi xử lý Content:", e)

# Callback lỗi
def get_error(error):
    print("❌ Streaming Error:", error)


def get_symbols_from_exchange(exchange_code):
    res = md_get_securities_list(exchange_code)
    if isinstance(res, dict) and res.get('status') == 'Success' and 'data' in res:
        return [item.get('Symbol') for item in res['data'] if item.get('Symbol')]
    else:
        print(f"⚠️ Không lấy được dữ liệu cho sàn {exchange_code}: {res}")
        return []

def get_symbols_from_index(index_code):
    res = md_get_index_components(index_code)
    if (
        isinstance(res, dict)
        and res.get('status') == 'Success'
        and 'data' in res
        and isinstance(res['data'], list)
        and len(res['data']) > 0
        and 'IndexComponent' in res['data'][0]
    ):
        return [item.get('StockSymbol') for item in res['data'][0]['IndexComponent'] if item.get('StockSymbol')]
    else:
        print(f"⚠️ Không lấy được dữ liệu cho chỉ số {index_code}: {res}")
        return []
# Lấy danh sách mã theo sàn
def md_get_securities_list(exchange_code):
    req = model.securities(exchange_code, 1, 1000)
    res = client.securities(config, req)
    return res

# Lấy danh sách mã theo chỉ số
def md_get_index_components(index_code):
    req = model.index_components(index_code, 1, 1000)
    res = client.index_components(config, req)
    return res

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Chưa đăng nhập'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('dashboard.html')  

@app.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html') 

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/dashboard', methods=['GET'])
def dashboard_page():
    return render_template('dashboard.html')


@app.route('/api/register', methods=['POST'])
def handle_register():
    data = request.get_json()
    session = SessionLocal()
    try:
        username = data.get('username')
        if session.query(User).filter_by(username=username).first():
            return jsonify({'message': 'Tên đăng nhập đã tồn tại'}), 400

        new_user = User(
            username=username,
            hash_pass=generate_password_hash(data.get('password')),
            Name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone'),
            birthday=datetime.strptime(data.get('birthday'), "%Y-%m-%d"),
            country=data.get('country'),
            sex=data.get('sex') == True or data.get('sex') == 'True'
        )
        session.add(new_user)
        session.commit()
        return jsonify({'message': 'Đăng ký thành công'}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Lỗi đăng ký: {str(e)}'}), 500
    finally:
        session.close()

@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Thiếu tên đăng nhập hoặc mật khẩu'}), 400

    session_db = SessionLocal()
    try:
        user = session_db.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.hash_pass, password):
            session['user_id'] = user.ID  # Lưu session
            session['username'] = user.username
            session.permanent = True
            return jsonify({'message': 'Đăng nhập thành công!', 'username': user.username}), 200
        else:
            return jsonify({'message': 'Sai tài khoản hoặc mật khẩu!'}), 401
    finally:
        session_db.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Đăng xuất thành công'}), 200

@app.route('/api/session_info', methods=['GET'])
def session_info():
    if 'user_id' in session and 'username' in session:
        return jsonify({
            'user_id': session['user_id'],
            'username': session['username']
        }), 200
    return jsonify({'message': 'Chưa đăng nhập'}), 401


@socketio.on('button_click')
def handle_button_click(data):
    global connected_clients
    sid = request.sid
    name = data.get('exchange')

    exchange_map = {
        'HOSE': HOSE,
        'HNX': HNX,
        'UPCOM': UPCOM,
        'VN30': VN30,
        'VN100': VN100,
        'HNX30': HNX30
    }

    if name not in exchange_map:
        emit('server_response', {'error': f'Danh sách không tồn tại cho: {name}'}, room=sid)
        return

    symbols = exchange_map[name]
    connected_clients[sid] = symbols  # ✅ cập nhật lại symbol theo sid
    print(f"✅ Cập nhật symbol cho {sid}: {name} ({len(symbols)} symbols)")

# Nạp tiền vào ví
@app.route('/wallet/deposit', methods=['GET'])
@login_required
def deposit_page():
    return render_template('wallet/deposit.html')

@app.route('/wallet/deposit', methods=['POST'])
def handle_deposit():
    user_id = session.get('user_id')  # 🔄 Lấy user_id từ session

    if not user_id:
        return jsonify({'message': 'Chưa đăng nhập'}), 401

    data = request.get_json()
    amount = data.get('amount')

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'message': 'Số tiền không hợp lệ'}), 400
    except:
        return jsonify({'message': 'Số tiền không hợp lệ'}), 400

    db_session = SessionLocal()
    try:
        today = date.today()

        gd = GiaoDich(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Nạp tiền',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        db_session.add(gd)

        quy = QuyNguoiDung(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Nạp',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        db_session.add(quy)

        db_session.commit()
        return jsonify({'message': f'Nạp {amount} thành công'}), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500
    finally:
        db_session.close()

# Rút tiền
@app.route('/wallet/withdraw', methods=['GET'])
@login_required
def withdraw_page():
    return render_template('wallet/withdraw.html')

@app.route('/wallet/withdraw', methods=['POST'])
def handle_withdraw():
    user_id = session.get('user_id')  # ✅ Dùng session thay cho JWT

    data = request.get_json()
    amount = data.get('amount')

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'message': 'Số tiền không hợp lệ'}), 400
    except:
        return jsonify({'message': 'Số tiền không hợp lệ'}), 400

    db_session = SessionLocal()
    try:
        today = date.today()

        # 🔒 TODO: kiểm tra số dư thực tế trước khi rút
        # (có thể bổ sung sau nếu bạn muốn kiểm soát kỹ hơn)

        gd = GiaoDich(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Rút tiền',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        db_session.add(gd)

        quy = QuyNguoiDung(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Rút',
            so_tien_giao_dich=-amount,
            ngay_giao_dich=today
        )
        db_session.add(quy)

        db_session.commit()
        return jsonify({'message': f'Rút {amount} thành công'}), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500
    finally:
        db_session.close()
# Lấy lịch sử giao dịch

@app.route('/wallet/history/page', methods=['GET'])
@login_required
def wallet_history_page():
    return render_template('wallet/history.html')


@app.route('/wallet/history', methods=['GET'])
@login_required
def handle_transaction_history():
    user_id = session.get('user_id')  # ✅ Lấy user ID từ session

    db_session = SessionLocal()
    try:
        result = db_session.query(GiaoDich).filter_by(userID=user_id)\
                        .order_by(GiaoDich.ngay_giao_dich.desc()).all()

        history = [{
            'loai': gd.loai_giao_dich,
            'so_tien': float(gd.so_tien_giao_dich),
            'ngay': gd.ngay_giao_dich.strftime('%Y-%m-%d')
        } for gd in result]

        return jsonify({'data': history}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500
    finally:
        db_session.close()

@app.route('/portfolio/page', methods=['GET'])
@login_required
def portfolio_page():
    return render_template('portfolio.html')


@app.route('/portfolio', methods=['GET'])
@login_required
def handle_portfolio():
    user_id = session.get('user_id')  # Lấy từ Flask session
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db_session = SessionLocal()
    try:
        holdings = db_session.query(DanhMucDauTu).filter_by(ID_user=user_id).all()
        results = [{
            'stock_id': h.ID_stock,
            'so_luong': h.so_luong_co_phieu_nam,
            'gia_mua_trung_binh': float(h.gia_mua_trung_binh)
        } for h in holdings]

        return jsonify({'assets': results}), 200
    finally:
        db_session.close()


#Lịch sử lệnh giao dịch

@app.route('/order/history/page', methods=['GET'])
@login_required
def order_history_page():
    return render_template('order/order_history.html')  # file HTML cần tạo


@app.route('/order/history', methods=['GET'])
@login_required
def handle_order_history():
    user_id = session.get('user_id')  # Hoặc từ user_sessions[request.sid] nếu bạn đang map theo WebSocket trước đó
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db_session = SessionLocal()
    try:
        orders = db_session.query(DatLenh)\
            .filter_by(ID_user=user_id)\
            .order_by(DatLenh.thoi_diem_dat.desc()).all()

        results = [{
            'symbol_id': o.ID_stock,
            'so_luong': o.so_luong_co_phieu,
            'gia': float(o.gia_lenh),
            'loai_lenh': o.loai_lenh,
            'trang_thai': o.trang_thai,
            'thoi_diem': o.thoi_diem_dat.strftime('%Y-%m-%d %H:%M:%S')
        } for o in orders]

        return jsonify({'orders': results}), 200
    finally:
        db_session.close()

#Đặt lệnh giao dịch
@app.route('/order/place', methods=['GET'])
@login_required
def place_order_page():
    return render_template('order/place_order.html')


@app.route('/order/place', methods=['POST'])
@login_required
def handle_place_order():
    user_id = session.get('user_id')  # Giả sử bạn đang dùng Flask session
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    data = request.get_json()
    loai_lenh = data.get('loai_lenh')  # "Mua" hoặc "Bán"
    stock_id = data.get('stock_id')
    gia_lenh = float(data.get('gia_lenh'))
    so_luong = int(data.get('so_luong'))
    tong_gia_tri = gia_lenh * so_luong

    db = SessionLocal()
    try:
        if loai_lenh not in ['Mua', 'Bán']:
            return jsonify({'message': 'Loại lệnh không hợp lệ'}), 400

        if loai_lenh == 'Mua':
            total_balance = db.query(QuyNguoiDung).filter_by(userID=user_id)\
                .with_entities(QuyNguoiDung.so_tien_giao_dich).all()
            so_du = sum([float(t[0]) for t in total_balance])
            if so_du < tong_gia_tri:
                return jsonify({'message': 'Số dư không đủ để mua'}), 400

        elif loai_lenh == 'Bán':
            holding = db.query(DanhMucDauTu).filter_by(ID_user=user_id, ID_stock=stock_id).first()
            if not holding or holding.so_luong_co_phieu_nam < so_luong:
                return jsonify({'message': 'Không đủ cổ phiếu để bán'}), 400

        # Đặt lệnh
        order = DatLenh(
            ID_user=user_id,
            ID_stock=stock_id,
            loai_lenh=loai_lenh,
            thoi_diem_dat=datetime.now(),
            gia_lenh=gia_lenh,
            so_luong_co_phieu=so_luong,
            trading='Chưa khớp',
            trang_thai='Đang xử lý'
        )
        db.add(order)
        db.commit()

        return jsonify({'message': 'Đặt lệnh thành công'}), 200

    except Exception as e:
        db.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        db.close()

#Sổ lênh giao dịch

@app.route('/order/book/page', methods=['GET'])
@login_required
def order_book_page():
    return render_template('order/book.html')  # file trong thư mục templates/



@app.route('/order/book', methods=['GET'])
@login_required
def handle_order_book():
    user_id = session.get('user_id')  # Hoặc dùng session['user_id'] nếu chắc chắn đã đăng nhập
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db_session = SessionLocal()
    try:
        orders = db_session.query(DatLenh)\
            .filter_by(ID_user=user_id, trang_thai='Đang xử lý')\
            .all()

        results = [{
            'symbol_id': o.ID_stock,
            'so_luong': o.so_luong_co_phieu,
            'gia': float(o.gia_lenh),
            'loai_lenh': o.loai_lenh,
            'thoi_diem': o.thoi_diem_dat.strftime('%Y-%m-%d %H:%M:%S')
        } for o in orders]

        return jsonify({'orders': results}), 200
    finally:
        db_session.close()


@socketio.on('connect')
def handle_connect():
    global connected_clients
    sid = request.sid
    connected_clients[sid] = None
    print(f'✅ Client connected: {sid}')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in connected_clients:
        del connected_clients[sid]
    print(f"❌ Client ngắt kết nối: {sid}")

if __name__ == '__main__':
    try:
        init_app()
        print("🚀 Server đang chạy. Nhấn Ctrl+C để thoát.")
        socketio.run(app, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Đã nhận Ctrl+C. Đang thoát...")
        import os
        os._exit(0)  # Thoát cưỡng bức