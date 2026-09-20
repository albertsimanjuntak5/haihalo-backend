from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_haihalo_123'
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*")

# Database sederhana di memori (Penyimpanan sementara)
users_db = {}

# Pemetaan username -> Socket ID (request.sid)
user_sockets = {}


# ================= ROUTE API (LOGIN & REGISTER) =================

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username dan password wajib diisi'}), 400

    if username in users_db:
        return jsonify({'status': 'error', 'message': 'Username sudah terdaftar'}), 400

    users_db[username] = password
    return jsonify({'status': 'success', 'message': 'Registrasi berhasil'}), 200


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if username not in users_db or users_db[username] != password:
        return jsonify({'status': 'error', 'message': 'Username atau password salah'}), 401

    return jsonify({'status': 'success', 'message': 'Login berhasil'}), 200


# ================= EVENT SOCKET.IO (REALTIME) =================

@socketio.on('connect')
def handle_connect():
    print(f"[CONNECTED] Socket ID: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    # Hapus socket ID jika user terputus
    disconnected_user = None
    for username, sid in list(user_sockets.items()):
        if sid == request.sid:
            disconnected_user = username
            del user_sockets[username]
            break
    print(f"[DISCONNECTED] User: {disconnected_user} ({request.sid})")


@socketio.on('register_user')
def handle_register_user(username):
    """Mendaftarkan username ke Socket ID saat user login/konek"""
    if username:
        user_sockets[username] = request.sid
        print(f"[REGISTERED] {username} -> {request.sid}")


@socketio.on('private_message')
def handle_private_message(data):
    """Mengirim pesan khusus 1-on-1 ke penerima (target)"""
    sender = data.get('sender')
    target = data.get('target')
    message = data.get('message')

    print(f"[CHAT] Dari '{sender}' ke '{target}': {message}")

    target_sid = user_sockets.get(target)

    # Kirim ke penerima jika penerima sedang online
    if target_sid:
        emit('private_message', {
            'sender': sender,
            'message': message
        }, room=target_sid)


# ================= RUN SERVER =================

if __name__ == '__main__':
    # Jalankan menggunakan socketio.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)