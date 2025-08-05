import eventlet
eventlet.monkey_patch()
from flask import Flask, request,jsonify,render_template,session,Response
from flask_socketio import SocketIO
from config import Config
from utils.db import init_db
from flask_socketio import emit,SocketIO
from utils.db import SessionLocal
from models.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import time
from ssi_fc_data import model
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import config
import json
import threading
import queue
from datetime import date,timedelta
from models.models import GiaoDich, QuyNguoiDung,DatLenh,DanhMucDauTu,MarketData ,ThongBao ,LichSuKhopLenh
from functools import wraps
from sqlalchemy import func 
from decimal import Decimal
from sqlalchemy.orm import joinedload
from zoneinfo import ZoneInfo


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
    api_data = threading.Thread(target=broadcast_market_data_loop, daemon=True)
    api_data.start()
    matching_thread = threading.Thread(target=xu_ly_khop_lenh_lien_tuc, daemon=True)
    matching_thread.start()
    

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
        time.sleep(0.25)

def xu_ly_khop_lenh_lien_tuc():
    while True:
        session = SessionLocal()
        try:
            lenh_chua_khop = session.query(DatLenh)\
                .filter(DatLenh.trang_thai == 'Đang xử lý')\
                .options(joinedload(DatLenh.stock), joinedload(DatLenh.user))\
                .all()

            for lenh in lenh_chua_khop:
                market: MarketData = lenh.stock
                if not market:
                    continue

                matched = False
                matched_qty = 0
                matched_price = 0

                if lenh.loai_lenh == "Mua":
                    if lenh.gia_lenh >= market.AskPrice1:
                        matched_price = market.AskPrice1
                        matched_qty = min(lenh.so_luong_co_phieu, int(market.AskVol1 or 0))
                        matched = True

                elif lenh.loai_lenh == 'Bán':
                    if lenh.gia_lenh <= market.BidPrice1:
                        matched_price = market.BidPrice1
                        matched_qty = min(lenh.so_luong_co_phieu, int(market.BidVol1 or 0))
                        matched = True

                if matched and matched_qty > 0:
                    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

                    # ✅ Cập nhật danh mục đầu tư
                    try:
                        dmdt = session.query(DanhMucDauTu)\
                            .filter_by(ID_user=lenh.ID_user, ID_stock=lenh.ID_stock)\
                            .first()

                        if lenh.loai_lenh == 'Mua':
                            if dmdt:
                                tong_gia = dmdt.gia_mua_trung_binh * dmdt.so_luong_co_phieu_nam + matched_price * matched_qty
                                dmdt.so_luong_co_phieu_nam += matched_qty
                                dmdt.gia_mua_trung_binh = tong_gia / dmdt.so_luong_co_phieu_nam
                            else:
                                dmdt = DanhMucDauTu(
                                    ID_user=lenh.ID_user,
                                    ID_stock=lenh.ID_stock,
                                    so_luong_co_phieu_nam=matched_qty,
                                    gia_mua_trung_binh=matched_price
                                )
                                session.add(dmdt)

                        elif lenh.loai_lenh == 'Bán':
                            if dmdt:
                                if matched_qty >= dmdt.so_luong_co_phieu_nam:
                                    session.delete(dmdt)
                                else:
                                    dmdt.so_luong_co_phieu_nam -= matched_qty

                        session.commit()
                    except Exception as e:
                        session.rollback()
                        print("❌ Lỗi cập nhật danh mục đầu tư:", e)

                    # ✅ Cộng tiền (nếu là lệnh bán)
                    if lenh.loai_lenh == 'Bán':
                        try:
                            tien = matched_price * matched_qty
                            session.add(QuyNguoiDung(userID=lenh.ID_user, so_tien=tien))
                            session.commit()
                        except Exception as e:
                            session.rollback()
                            print("❌ Lỗi cộng tiền:", e)

                    # ✅ Ghi lịch sử khớp lệnh
                    try:
                        session.add(LichSuKhopLenh(
                            ID_user=lenh.ID_user,
                            ID_stock=lenh.ID_stock,
                            loai_lenh=lenh.loai_lenh,
                            gia_khop=matched_price,
                            so_luong=matched_qty,
                            thoi_gian=now
                        ))
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        print("❌ Lỗi ghi lịch sử khớp lệnh:", e)

                    # ✅ Gửi thông báo
                    try:
                        session.add(ThongBao(
                            ID_user=lenh.ID_user,
                            loai_thong_bao="Khớp lệnh",
                            noi_dung=f"Lệnh {lenh.loai_lenh.upper()} cổ phiếu {lenh.ID_stock} đã khớp {matched_qty} CP giá {matched_price}.",
                            trang_thai="Chưa đọc",
                            thoi_gian=now
                        ))
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        print("❌ Lỗi gửi thông báo:", e)

                    # ✅ Cập nhật trạng thái lệnh
                    try:
                        if matched_qty == lenh.so_luong_co_phieu:
                            lenh.trang_thai = "Đã khớp"
                        else:
                            lenh.so_luong_co_phieu -= matched_qty
                            lenh.trang_thai = "Khớp một phần"
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        print("❌ Lỗi cập nhật trạng thái lệnh:", e)

        except Exception as e:
            print("❌ Lỗi ngoài vòng lặp khớp lệnh:", e)
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
    req = model.securities(exchange_code, 1, 100)
    res = client.securities(config, req)
    return res

# Lấy danh sách mã theo chỉ số
def md_get_index_components(index_code):
    req = model.index_components(index_code, 1, 100)
    res = client.index_components(config, req)
    return res

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return render_template("login.html"), 401  
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
@login_required
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
@login_required
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
            so_tien=amount,
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
@login_required
def handle_withdraw():
    user_id = session.get('user_id')
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

        # ✅ Tính số dư hiện tại
        current_balance = db_session.query(
            func.coalesce(func.sum(QuyNguoiDung.so_tien), 0)
        ).filter_by(userID=user_id).scalar()

        if amount > current_balance:
            return jsonify({'message': 'Số dư không đủ để rút tiền'}), 400

        # Ghi log giao dịch
        gd = GiaoDich(
            userID=user_id,
            id_lien_ket_tai_khoan=None,
            loai_giao_dich='Rút tiền',
            so_tien_giao_dich=amount,
            ngay_giao_dich=today
        )
        db_session.add(gd)

        # Cập nhật số dư âm trong bảng QuyNguoiDung
        quy = QuyNguoiDung(
            userID=user_id,
            so_tien=-amount,
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
    return render_template('user/portfolio.html')


@app.route('/portfolio', methods=['GET'])
@login_required
def handle_portfolio():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db_session = SessionLocal()
    try:
        holdings = db_session.query(DanhMucDauTu).filter_by(ID_user=user_id).all()
        results = [{
            'ID_stock': h.ID_stock,
            'so_luong_co_phieu_nam': h.so_luong_co_phieu_nam,
            'gia_mua_trung_binh': float(h.gia_mua_trung_binh)
        } for h in holdings]

        return jsonify(results), 200  # trả thẳng mảng, không bọc trong "assets"
    finally:
        db_session.close()

@app.route('/user/balance/page')
@login_required
def view_balance_page():
    return render_template('user/balance.html')

@app.route('/user/balance', methods=['GET'])
@login_required
def get_user_balance():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db = SessionLocal()
    try:
        balances = db.query(QuyNguoiDung).filter_by(userID=user_id)\
                    .with_entities(QuyNguoiDung.so_tien).all()
        tong_tien = sum(float(t[0]) for t in balances)

        return jsonify({'user_id': user_id, 'so_du': tong_tien}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        db.close()


#Lịch sử lệnh giao dịch\

@app.route("/api/order", methods=["POST"])
@login_required
def place_order():
    db = SessionLocal()
    try:
        data = request.json
        user_id = session.get("user_id")

        # Lấy dữ liệu
        symbol = data.get("symbol")
        side = data.get("side")  
        qty = int(data.get("qty", 0))
        price = float(data.get("price", 0))

        if not symbol or qty <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ"}), 400

        # Kiểm tra cổ phiếu tồn tại
        stock = db.query(MarketData).filter_by(Symbol=symbol).first()
        if not stock:
            return jsonify({"status": "error", "message": "Mã cổ phiếu không tồn tại"}), 404

        side = side.strip()

        # ===== Kiểm tra điều kiện giao dịch =====
        if side == "Mua":
            # Lấy tổng tiền trong quỹ
            tong_tien = db.query(func.sum(QuyNguoiDung.so_tien)).filter_by(userID=user_id).scalar() or 0
            tong_gia_tri_lenh = qty * price   # giá trị VND
            if tong_gia_tri_lenh > tong_tien:
                return jsonify({"status": "error", "message": "Số dư quỹ không đủ để mua"}), 400

        elif side == "Bán":
            # Lấy số lượng cổ phiếu đang nắm giữ
            danh_muc = db.query(DanhMucDauTu).filter_by(ID_user=user_id, ID_stock=symbol).first()
            so_luong_hien_tai = danh_muc.so_luong_co_phieu_nam if danh_muc else 0
            if qty > so_luong_hien_tai:
                return jsonify({"status": "error", "message": "Không đủ cổ phiếu để bán"}), 400
        else:
            return jsonify({"status": "error", "message": "Loại lệnh không hợp lệ"}), 400

        # ===== Tạo lệnh =====
        new_order = DatLenh(
            ID_user=user_id,
            ID_stock=symbol,
            loai_lenh=side,
            gia_lenh=price,
            so_luong_co_phieu=qty,
            thoi_diem_dat=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")),
            trang_thai="Đang xử lý",
            trading="Chưa khớp"
        )

        # ✅ Gửi thông báo
    
        db.add(new_order)
        session.add(ThongBao(
            ID_user=user_id,
            loai_thong_bao="Mua Bán",
            noi_dung=f"Lệnh {side.upper()} cổ phiếu {new_order.ID_stock} đã được đặt với khối lượng {qty} CP giá {price}.",
            trang_thai="Chưa đọc",
            thoi_gian=new_order.thoi_diem_dat
        ))
        db.commit()
        db.refresh(new_order)

        return jsonify({
            "status": "success",
            "message": "Lệnh đã được gửi",
        }), 200

    except Exception as e:
        db.rollback()
        print("❌ Lỗi đặt lệnh:", e)
        return jsonify({"status": "error", "message": "Có lỗi khi đặt lệnh"}), 500
    finally:
        db.close()


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
    user_id = session.get('user_id')
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
            # Tính tổng số dư
            total_balance = db.query(QuyNguoiDung).filter_by(userID=user_id)\
                .with_entities(QuyNguoiDung.so_tien).all()
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
            thoi_diem_dat=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")),
            gia_lenh=gia_lenh,
            so_luong_co_phieu=so_luong,
            trading='Chưa khớp',
            trang_thai='Đang xử lý'
        )
        db.add(order)
        db.commit()

        # ✅ Nếu là Mua thì trừ tiền khỏi bảng QuyNguoiDung
        if loai_lenh == 'Mua':
            tien_con_lai = tong_gia_tri
            danh_sach_quy = db.query(QuyNguoiDung).filter_by(userID=user_id).order_by(QuyNguoiDung.ID).all()

            for quy in danh_sach_quy:
                if quy.so_tien >= tien_con_lai:
                    quy.so_tien -= tien_con_lai
                    tien_con_lai = 0
                    break
                else:
                    tien_con_lai -= quy.so_tien
                    quy.so_tien = 0

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
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Bạn cần đăng nhập trước.'}), 401

    db_session = SessionLocal()
    try:
        orders = db_session.query(DatLenh)\
            .filter_by(ID_user=user_id, trang_thai='Đang xử lý')\
            .all()

        results = [{
            'ID': o.ID,
            'symbol_id': o.ID_stock,
            'so_luong': o.so_luong_co_phieu,
            'gia': float(o.gia_lenh),
            'loai_lenh': o.loai_lenh,
            'thoi_diem': o.thoi_diem_dat.strftime('%Y-%m-%d %H:%M:%S')
        } for o in orders]

        return jsonify({'orders': results}), 200
    finally:
        db_session.close()


@app.route("/order/cancel/<int:order_id>", methods=["DELETE"])
@login_required
def cancel_order(order_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Bạn chưa đăng nhập"}), 401

    db = SessionLocal()
    try:
        order = db.query(DatLenh).filter_by(ID=order_id, ID_user=user_id).first()
        if not order:
            return jsonify({"message": "Không tìm thấy lệnh"}), 404
        if order.trang_thai != "Đang xử lý":
            return jsonify({"message": "Không thể hủy lệnh này"}), 400

        # ✅ Nếu là lệnh Mua thì hoàn lại tiền
        if order.loai_lenh == "Mua":
            so_tien_hoan = order.so_luong_co_phieu * order.gia_lenh
            db.add(QuyNguoiDung(userID=user_id, so_tien=so_tien_hoan))

        # Nếu sau này muốn hỗ trợ lệnh Bán, có thể hoàn lại cổ phiếu ở đây

        order.trang_thai = "Hủy"
        db.commit()

        return jsonify({"message": "✅ Lệnh đã được hủy và hoàn tiền (nếu có)"}), 200

    except Exception as e:
        print(f"❌ Lỗi khi hủy lệnh: {e}")
        db.rollback()
        return jsonify({"message": "Lỗi server khi hủy lệnh"}), 500
    finally:
        db.close()



@app.route('/order/update/<int:order_id>', methods=['PUT'])
@login_required
def update_order(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Bạn chưa đăng nhập'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'message': 'Dữ liệu gửi lên không hợp lệ'}), 400

    db = SessionLocal()
    try:
        order = db.query(DatLenh).filter_by(ID=order_id, ID_user=user_id).first()
        if not order:
            return jsonify({'message': 'Không tìm thấy lệnh'}), 404

        # Cập nhật thông tin lệnh
        order.loai_lenh = data.get('loai_lenh', order.loai_lenh)
        order.ID_stock = data.get('stock_id', order.ID_stock)
        order.gia_lenh = data.get('gia_lenh', order.gia_lenh)
        order.so_luong_co_phieu = data.get('so_luong', order.so_luong_co_phieu)

        db.commit()
        return jsonify({'message': 'Cập nhật thành công'}), 200

    except Exception as e:
        print(f"❌ Lỗi khi cập nhật lệnh: {e}")
        db.rollback()
        return jsonify({'message': 'Lỗi server khi cập nhật lệnh'}), 500
    finally:
        db.close()

@app.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    user_id = session.get('user_id')
    db = SessionLocal()
    try:
        notifs = db.query(ThongBao).filter_by(ID_user=user_id).order_by(ThongBao.thoi_gian.desc()).all()
        results = [{
            "ID": n.ID,
            "loai_thong_bao": n.loai_thong_bao,
            "noi_dung": n.noi_dung,
            "trang_thai": n.trang_thai,
            "thoi_gian": n.thoi_gian.strftime('%Y-%m-%d %H:%M:%S')
        } for n in notifs]
        return jsonify(results), 200
    finally:
        db.close()


@app.route('/notifications/read/<int:notif_id>', methods=['PUT'])
@login_required
def mark_notification_read(notif_id):
    user_id = session.get('user_id')
    db = SessionLocal()
    try:
        notif = db.query(ThongBao).filter_by(ID=notif_id, ID_user=user_id).first()
        if not notif:
            return jsonify({"message": "Không tìm thấy thông báo"}), 404

        notif.trang_thai = "Đã đọc"
        db.commit()
        return jsonify({"message": "Đã cập nhật trạng thái"}), 200
    finally:
        db.close()


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