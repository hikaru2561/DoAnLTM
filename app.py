import eventlet
eventlet.monkey_patch()
from flask import Flask, request
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

init_db()

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


@socketio.on('register')
def handle_register(data):
    task_queue.put({'event': 'register', 'data': data, 'sid': request.sid})
    session = SessionLocal()
    try:
        username = data.get('username')
        if session.query(User).filter_by(username=username).first():
            emit('register_failed', {'message': 'Tên đăng nhập đã tồn tại'},room=request.sid)
            return

        new_user = User(
            username=username,
            hash_pass=generate_password_hash(data.get('password')),
            Name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone'),
            birthday=datetime.strptime(data.get('birthday'), "%Y-%m-%d"),
            country=data.get('country'),
            sex=data.get('sex')
        )
        session.add(new_user)
        session.commit()
        emit('register_success', {'message': 'Đăng ký thành công'},room=request.sid)
    except Exception as e:
        session.rollback()
        emit('register_failed', {'message': f'Lỗi đăng ký: {str(e)}'},room=request.sid)
    finally:
        session.close()

@socketio.on('login')
def handle_login(data):
    task_queue.put({'event': 'login', 'data': data, 'sid': request.sid})
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=data.get('username')).first()
        if user and check_password_hash(user.hash_pass, data.get('password')):
            token = create_jwt(user.ID, user.username)
            user_sessions[request.sid] = user.ID
            emit('login_success', {'message': 'Đăng nhập thành công!', 'token': token, 'username': user.username},room=request.sid)
        else:
            emit('login_failed', {'message': 'Sai tài khoản hoặc mật khẩu!'},room=request.sid)
    finally:
        session.close()

@socketio.on('button_click')
def handle_button_click(data):
    task_queue.put({'event': 'button_click', 'data': data, 'sid': request.sid})
    global clients, symbols
    global VN100, VN30, HNX30, HOSE, HNX, UPCOM

    clients = request.sid
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

        # Gửi dữ liệu hiện tại từ DB cho client
        session = SessionLocal()
        try:
            from models.models import MarketData  # đảm bảo đã import
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
                }
                socketio.emit('server_data', json.dumps(data, ensure_ascii=False), room=clients)
        finally:
            session.close()

    except Exception as e:
        print("❌ Lỗi khi xử lý sự kiện button_click:", e)
        socketio.emit('server_response', {'error': str(e)}, room=request.sid)

# Nạp tiền vào ví
@socketio.on('deposit')
def handle_deposit(data):
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        emit('deposit_failed', {'message': 'Số tiền không hợp lệ'}, room=request.sid)
        return

    session = SessionLocal()
    try:
        today = date.today()
        # Lưu vào bảng GiaoDich
        gd = GiaoDich(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Nạp tiền',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        session.add(gd)

        # Lưu vào bảng QuyNguoiDung (thêm tiền)
        quy = QuyNguoiDung(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Nạp',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        session.add(quy)

        session.commit()
        emit('deposit_success', {'message': f'Nạp {amount} thành công'}, room=request.sid)
    except Exception as e:
        session.rollback()
        emit('deposit_failed', {'message': str(e)}, room=request.sid)
    finally:
        session.close()

# Rút tiền
@socketio.on('withdraw')
def handle_withdraw(data):
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        emit('withdraw_failed', {'message': 'Số tiền không hợp lệ'}, room=request.sid)
        return

    session = SessionLocal()
    try:
        today = date.today()

        # TODO: có thể kiểm tra tổng nạp - tổng rút nếu cần

        gd = GiaoDich(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Rút tiền',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        session.add(gd)

        quy = QuyNguoiDung(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Rút',
            so_tien_giao_dich=-amount,
            ngay_giao_dich=today
        )
        session.add(quy)

        session.commit()
        emit('withdraw_success', {'message': f'Rút {amount} thành công'}, room=request.sid)
    except Exception as e:
        session.rollback()
        emit('withdraw_failed', {'message': str(e)}, room=request.sid)
    finally:
        session.close()

# Lấy lịch sử giao dịch
@socketio.on('transaction_history')
def handle_transaction_history():
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

    session = SessionLocal()
    try:
        result = session.query(GiaoDich).filter_by(userID=user_id).order_by(GiaoDich.ngay_giao_dich.desc()).all()
        history = [{
            'loai': gd.loai_giao_dich,
            'so_tien': float(gd.so_tien_giao_dich),
            'ngay': gd.ngay_giao_dich.strftime('%Y-%m-%d')
        } for gd in result]

        emit('transaction_history_result', {'data': history}, room=request.sid)
    finally:
        session.close()

# Lấy danh mục đầu tư
@socketio.on('portfolio')
def handle_portfolio():
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

    session = SessionLocal()
    try:
        holdings = session.query(DanhMucDauTu).filter_by(ID_user=user_id).all()
        results = [{
            'stock_id': h.ID_stock,
            'so_luong': h.so_luong_co_phieu_nam,
            'gia_mua_trung_binh': float(h.gia_mua_trung_binh)
        } for h in holdings]

        emit('portfolio_data', {'assets': results}, room=request.sid)
    finally:
        session.close()

#Lịch sử lệnh giao dịch
@socketio.on('order_history')
def handle_order_history():
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

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

        emit('order_history_result', {'orders': results}, room=request.sid)
    finally:
        session.close()

#Đặt lệnh giao dịch
@socketio.on('place_order')
def handle_place_order(data):
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

    session = SessionLocal()
    try:
        loai_lenh = data.get('loai_lenh')  # "Mua" hoặc "Bán"
        stock_id = data.get('stock_id')
        gia_lenh = float(data.get('gia_lenh'))
        so_luong = int(data.get('so_luong'))
        tong_gia_tri = gia_lenh * so_luong

        if loai_lenh not in ['Mua', 'Bán']:
            emit('order_failed', {'message': 'Loại lệnh không hợp lệ'}, room=request.sid)
            return

        if loai_lenh == 'Mua':
            # 👉 Tính tổng số dư hiện tại
            total_balance = session.query(QuyNguoiDung).filter_by(userID=user_id).with_entities(
                QuyNguoiDung.so_tien_giao_dich
            ).all()
            so_du = sum([float(t[0]) for t in total_balance])

            if so_du < tong_gia_tri:
                emit('order_failed', {'message': 'Số dư không đủ để mua'}, room=request.sid)
                return

        elif loai_lenh == 'Bán':
            # 👉 Kiểm tra số lượng cổ phiếu đang nắm giữ
            holding = session.query(DanhMucDauTu).filter_by(ID_user=user_id, ID_stock=stock_id).first()
            if not holding or holding.so_luong_co_phieu_nam < so_luong:
                emit('order_failed', {'message': 'Không đủ cổ phiếu để bán'}, room=request.sid)
                return

        # 👉 Nếu đủ điều kiện thì đặt lệnh
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

        emit('order_success', {'message': 'Đặt lệnh thành công'}, room=request.sid)

    except Exception as e:
        session.rollback()
        emit('order_failed', {'message': str(e)}, room=request.sid)
    finally:
        session.close()

#Sổ lênh giao dịch
@socketio.on('order_book')
def handle_order_book():
    user_id = user_sessions.get(request.sid)
    if not user_id:
        emit('unauthorized', {'message': 'Bạn cần đăng nhập trước.'}, room=request.sid)
        return

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

        emit('order_book_result', {'orders': results}, room=request.sid)
    finally:
        session.close()


@socketio.on('connect')
def handle_connect(data):
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
