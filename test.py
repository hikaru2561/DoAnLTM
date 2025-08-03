import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template
from flask_socketio import SocketIO
import time
import threading
import random
import json
from ssi_fc_data import model
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
client = MarketDataClient(config)
symbols = []
@app.route('/')
def index():
    return render_template('dashboard.html')

import config
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient

def get_market_data(message):
    # Bỏ qua mọi message không phải dict hoặc không có trường 'Content'
    if not isinstance(message, dict) or "Content" not in message:
        return

    content_str = message.get("Content")
    if not isinstance(content_str, str):
        return
    try:
        content = json.loads(content_str)       
        json_data = json.dumps(content, ensure_ascii=False)
        print(f"📤 Gửi tới client: {json_data}")
        socketio.emit('server_data', json_data)
    except Exception as e:
        print("❌ Lỗi xử lý Content:", e)

def get_error(error):
    print("❌ Lỗi từ SSI API:", error)
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
        socketio.emit('server_data', json_data)

    except Exception as e:
        print("❌ Lỗi xử lý Content:", e)

selected_channel = "X:ALL"
# Lọc theo sàn
mm = MarketDataStream(config, MarketDataClient(config))
# Bắt đầu luồng background khi server chạy
    
mm_started = False

@socketio.on('button_click')
def handle_button_click(data):
    global  symbols
    global mm_started
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
        if not mm_started:
                mm.start(get_data, get_error, "X:ALL")
                mm_started = True
        else:
            mm.swith_channel("X:ALL")

    except Exception as e:
        print("❌ Lỗi khi xử lý sự kiện button_click:", e)
        socketio.emit('server_response', {'error': str(e)})

@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    bg_thread = threading.Thread()  # Khởi tạo thread rỗng
    socketio.run(app, debug=True)