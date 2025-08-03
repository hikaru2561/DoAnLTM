# sockets/events.py

from flask_socketio import emit,SocketIO
from utils.db import SessionLocal
from models.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import request
from utils.auth import create_jwt

from ssi_fc_data import model
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import config
import json

# Khởi tạo client và stream
client = MarketDataClient(config)
mm = MarketDataStream(config, client)
data1 = []
symbols = []
user_sessions = {}
latest_data = {}
VN30 = []
HNX30 = []
HoSE = []
HNX = []



# Emit dữ liệu mới nhất cho symbol
def get_data(message):
    # Bỏ qua mọi message không phải dict hoặc không có trường 'Content'
    if not isinstance(message, dict) or "Content" not in message:
        return

    content_str = message.get("Content")
    if not isinstance(content_str, str):
        return

    try:
        content = json.loads(content_str)

        symbol = content.get("Symbol")
        if symbol not in symbols:
            # Nếu symbol không nằm trong danh sách, bỏ qua
            return

        # Nếu hợp lệ thì emit về client
        json_data = json.dumps(content, ensure_ascii=False)
        print(f"📤 Gửi tới client: {json_data}")
        socketio_instance.emit('server_data', json_data)

    except Exception as e:
        print("❌ Lỗi xử lý Content:", e)

def init_app(app):
    mm.start(get_data, get_error, "X:ALL")

# Callback lỗi
def get_error(error):
    print("❌ Streaming Error:", error)

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

# Đăng ký các sự kiện socket
def register_socket_events(socketio):
    global socketio_instance
    socketio_instance = socketio

    @socketio.on('register')
    def handle_register(data):
        session = SessionLocal()
        try:
            username = data.get('username')
            if session.query(User).filter_by(username=username).first():
                emit('register_failed', {'message': 'Tên đăng nhập đã tồn tại'})
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
            emit('register_success', {'message': 'Đăng ký thành công'})
        except Exception as e:
            session.rollback()
            emit('register_failed', {'message': f'Lỗi đăng ký: {str(e)}'})
        finally:
            session.close()

    @socketio.on('login')
    def handle_login(data):
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(username=data.get('username')).first()
            if user and check_password_hash(user.hash_pass, data.get('password')):
                token = create_jwt(user.ID, user.username)
                user_sessions[request.sid] = user.ID
                emit('login_success', {'message': 'Đăng nhập thành công!', 'token': token, 'username': user.username})
            else:
                emit('login_failed', {'message': 'Sai tài khoản hoặc mật khẩu!'})
        finally:
            session.close()

    @socketio.on('disconnect')
    def handle_disconnect():
        user_sessions.pop(request.sid, None)

    @socketio.on('button_click')
    def handle_button_click(data):
        global  symbols
        name = data.get('exchange')
        print(f"🔘 Button clicked: {name}")

        try:
            
            if name in ['HOSE', 'HNX', 'UPCOM']:
                res = md_get_securities_list(name)
                symbols = [item.get('Symbol') or item.get('symbol') for item in res['data']]
            elif name in ['VN30', 'VN100', 'HNX30']:
                res = md_get_index_components(name.lower())
                index_data = res['data'][0]
                symbols = [item.get('StockSymbol') for item in index_data['IndexComponent']]

            print(symbols)
            mm.start(get_data, get_error, "X:ALL")

        except Exception as e:
            print("❌ Lỗi khi xử lý sự kiện button_click:", e)
            socketio.emit('server_response', {'error': str(e)})

   


    