import eventlet
eventlet.monkey_patch()
from flask_cors import CORS
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from config import Config
from utils.db import init_db
from flask_socketio import emit,SocketIO
from utils.db import SessionLocal
from models.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from utils.auth import create_jwt, decode_jwt
import time
from ssi_fc_data import model
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import config
import json
import threading
import queue
from datetime import date
from models.models import GiaoDich, QuyNguoiDung,DatLenh,DanhMucDauTu,MarketData  

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
clients = None
task_queue = queue.Queue()
NUM_WORKERS = 3


app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
CORS(app)
app.config.from_object('config.Config')
init_db()
def get_user_id_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    return decode_jwt(token)
socketio = SocketIO(app)

# Register routes
from routes.views import views_bp
app.register_blueprint(views_bp)


def init_app():
    global mm,VN100,VN30,HNX30,HOSE,HNX,UPCOM
    mm.start(get_data, get_error, "X:ALL")

    HOSE = get_symbols_from_exchange('HOSE')
    time.sleep(1)

    HNX = get_symbols_from_exchange('HNX')
    time.sleep(1)

    UPCOM = get_symbols_from_exchange('UPCOM')
    time.sleep(1)

    VN30 = get_symbols_from_index('vn30')
    time.sleep(1)

    VN100 = get_symbols_from_index('vn100')
    time.sleep(1)

    HNX30 = get_symbols_from_index('hnx30')
    time.sleep(1)
    threading.Thread(target=broadcast_market_data_loop, daemon=True).start()

def get_user_id(sid):
    return user_sessions.get(sid)

def broadcast_market_data_loop():
    while True:
        if clients and symbols:
            try:
                session = SessionLocal()
                results = session.query(MarketData).filter(MarketData.Symbol.in_(symbols)).all()
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
                            'High': row.High,
                            'Low': row.Low,
                            'TotalVol': row.TotalVol    
                        }
                    socketio.emit('server_data', json.dumps(data, ensure_ascii=False), room=clients)
            except Exception as e:
                print(f"❌ Lỗi khi gửi dữ liệu từ DB: {e}")
            finally:
                session.close()
        time.sleep(1)  


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


def get_user_id_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    return decode_jwt(token)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    session = SessionLocal()
    try:
        if session.query(User).filter_by(username=data['username']).first():
            return jsonify({'status': 'error', 'message': 'Tên đăng nhập đã tồn tại'}), 400

        new_user = User(
            username=data['username'],
            hash_pass=generate_password_hash(data['password']),
            Name=data['name'],
            email=data['email'],
            phone=data['phone'],
            birthday=datetime.strptime(data['birthday'], "%Y-%m-%d"),
            country=data['country'],
            sex=data['sex']
        )
        session.add(new_user)
        session.commit()
        return jsonify({'status': 'success', 'message': 'Đăng ký thành công'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=data['username']).first()
        if user and check_password_hash(user.hash_pass, data['password']):
            token = create_jwt(user.ID, user.username)
            return jsonify({'status': 'success', 'token': token, 'username': user.username})
        else:
            return jsonify({'status': 'error', 'message': 'Sai tài khoản hoặc mật khẩu'}), 401
    finally:
        session.close()

@socketio.on('button_click')
def handle_button_click(data):
    task_queue.put({'event': 'button_click', 'data': data, 'sid': request.sid})
    global clients, symbols
    global VN100, VN30, HNX30, HOSE, HNX, UPCOM

    name = data.get('exchange')
    print(f"🔘 Button clicked: {name} từ client {request.sid}")

    exchange_map = {    
        'HOSE': HOSE,
        'HNX': HNX,
        'UPCOM': UPCOM,
        'VN30': VN30,
        'VN100': VN100,
        'HNX30': HNX30
    }

    try:
        if name not in exchange_map:
            emit('server_response', {'error': f'Danh sách không tồn tại cho: {name}'}, room=request.sid)
            return

        symbols = exchange_map[name]
    except Exception as e:
        print("❌ Lỗi khi xử lý sự kiện button_click:", e)
        socketio.emit('server_response', {'error': str(e)}, room=request.sid)

# Nạp tiền vào ví
@app.route('/api/deposit', methods=['POST'])
def deposit():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'status': 'error', 'message': 'Số tiền không hợp lệ'}), 400

    session = SessionLocal()
    try:
        today = date.today()
        gd = GiaoDich(userID=user_id, loai_giao_dich='Nạp tiền', so_tien_giao_dich=amount, ngay_giao_dich=today)
        quy = QuyNguoiDung(userID=user_id, loai_giao_dich='Nạp', so_tien_giao_dich=amount, ngay_giao_dich=today)
        session.add(gd)
        session.add(quy)
        session.commit()
        return jsonify({'status': 'success', 'message': f'Nạp {amount} thành công'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()

# Rút tiền
@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'status': 'error', 'message': 'Số tiền không hợp lệ'}), 400

    session = SessionLocal()
    try:
        today = date.today()
        gd = GiaoDich(userID=user_id, loai_giao_dich='Rút tiền', so_tien_giao_dich=amount, ngay_giao_dich=today)
        quy = QuyNguoiDung(userID=user_id, loai_giao_dich='Rút', so_tien_giao_dich=-amount, ngay_giao_dich=today)
        session.add(gd)
        session.add(quy)
        session.commit()
        return jsonify({'status': 'success', 'message': f'Rút {amount} thành công'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()

# Lấy lịch sử giao dịch
@app.route('/api/transaction_history', methods=['GET'])
def transaction_history():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    session = SessionLocal()
    try:
        result = session.query(GiaoDich).filter_by(userID=user_id).order_by(GiaoDich.ngay_giao_dich.desc()).all()
        history = [{'loai': gd.loai_giao_dich, 'so_tien': float(gd.so_tien_giao_dich), 'ngay': gd.ngay_giao_dich.strftime('%Y-%m-%d')} for gd in result]
        return jsonify({'status': 'success', 'data': history})
    finally:
        session.close()


# Lấy danh mục đầu tư
@app.route('/api/portfolio', methods=['GET'])
def portfolio():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    session = SessionLocal()
    try:
        holdings = session.query(DanhMucDauTu).filter_by(ID_user=user_id).all()
        results = [{'stock_id': h.ID_stock, 'so_luong': h.so_luong_co_phieu_nam, 'gia_mua_trung_binh': float(h.gia_mua_trung_binh)} for h in holdings]
        return jsonify({'status': 'success', 'assets': results})
    finally:
        session.close()

#Lịch sử lệnh giao dịch
@app.route('/api/order_history', methods=['GET'])
def order_history():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    session = SessionLocal()
    try:
        orders = session.query(DatLenh).filter_by(ID_user=user_id).order_by(DatLenh.thoi_diem_dat.desc()).all()
        results = [{
            'symbol_id': o.ID_stock,
            'so_luong': o.so_luong_co_phieu,
            'gia': float(o.gia_lenh),
            'loai_lenh': o.loai_lenh,
            'trang_thai': o.trang_thai,
            'thoi_diem': o.thoi_diem_dat.strftime('%Y-%m-%d %H:%M:%S')
        } for o in orders]
        return jsonify({'status': 'success', 'orders': results})
    finally:
        session.close()

@app.route('/api/place_order', methods=['POST'])
def place_order():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    session = SessionLocal()
    try:
        loai_lenh = data.get('loai_lenh')
        stock_id = data.get('stock_id')
        gia_lenh = float(data.get('gia_lenh'))
        so_luong = int(data.get('so_luong'))
        tong_gia_tri = gia_lenh * so_luong

        if loai_lenh not in ['Mua', 'Bán']:
            return jsonify({'status': 'error', 'message': 'Loại lệnh không hợp lệ'}), 400

        if loai_lenh == 'Mua':
            total_balance = session.query(QuyNguoiDung).filter_by(userID=user_id).with_entities(
                QuyNguoiDung.so_tien_giao_dich).all()
            so_du = sum([float(t[0]) for t in total_balance])
            if so_du < tong_gia_tri:
                return jsonify({'status': 'error', 'message': 'Số dư không đủ để mua'}), 400

        elif loai_lenh == 'Bán':
            holding = session.query(DanhMucDauTu).filter_by(ID_user=user_id, ID_stock=stock_id).first()
            if not holding or holding.so_luong_co_phieu_nam < so_luong:
                return jsonify({'status': 'error', 'message': 'Không đủ cổ phiếu để bán'}), 400

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
        session.add(order)
        session.commit()
        return jsonify({'status': 'success', 'message': 'Đặt lệnh thành công'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()

@app.route('/api/order_book', methods=['GET'])
def order_book():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    session = SessionLocal()
    try:
        orders = session.query(DatLenh).filter_by(ID_user=user_id, trang_thai='Đang xử lý').all()
        results = [{
            'symbol_id': o.ID_stock,
            'so_luong': o.so_luong_co_phieu,
            'gia': float(o.gia_lenh),
            'loai_lenh': o.loai_lenh,
            'thoi_diem': o.thoi_diem_dat.strftime('%Y-%m-%d %H:%M:%S')
        } for o in orders]
        return jsonify({'status': 'success', 'orders': results})
    finally:
        session.close()


@socketio.on('connect')
def handle_connect(data):
    global clients
    clients = request.sid

    print(f"🔗 Client {request.sid} đã kết nối.")

@socketio.on('disconnect')
def handle_disconnect():
    user_sessions.pop(request.sid, None)
    print(f"🔗 Client {request.sid} đã ngắt kết nối.")

if __name__ == '__main__':
    try:
        init_app()
        print("🚀 Server đang chạy. Nhấn Ctrl+C để thoát.")
        socketio.run(app, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Đã nhận Ctrl+C. Đang thoát...")
        import os
        os._exit(0)  # Thoát cưỡng bức
