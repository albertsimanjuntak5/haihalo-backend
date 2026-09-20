import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'haihalo-secret-key-123')

# Izinkan CORS untuk HTTP & WebSockets
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Konfigurasi Database Aiven MySQL
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT', 21021))
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_NAME = os.environ.get('DB_NAME')

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        ssl={'ssl': True}
    )

# Dictionary untuk menyimpan mapping username -> socket_id
user_sockets = {}

@app.route('/')
def index():
    return jsonify({"status": "online", "message": "Backend HaiHalo Running"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi"}), 400

    hashed_password = generate_password_hash(password)

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Cek apakah username sudah ada
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            existing_user = cursor.fetchone()
            if existing_user:
                return jsonify({"status": "error", "message": "Username sudah terdaftar"}), 400

            # Insert akun baru
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            conn.commit()

        return jsonify({"status": "success", "message": "Registrasi berhasil"}), 201
    except Exception as e:
        print("Database Error (Register):", e)
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            if not user:
                return jsonify({"status": "error", "message": "Username tidak ditemukan"}), 401

            # Verifikasi password hash atau plain text (fallback)
            saved_pw = user['password']
            is_valid = False

            if saved_pw.startswith('scrypt:') or saved_pw.startswith('pbkdf2:'):
                is_valid = check_password_hash(saved_pw, password)
            else:
                is_valid = (saved_pw == password)

            if is_valid:
                return jsonify({"status": "success", "message": "Login berhasil", "username": username}), 200
            else:
                return jsonify({"status": "error", "message": "Password salah"}), 401

    except Exception as e:
        print("Database Error (Login):", e)
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
    finally:
        if conn:
            conn.close()

# ================= EVENT SOCKET.IO =================

@socketio.on('connect')
def handle_connect():
    print(f"Client terhubung: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client terputus: {request.sid}")
    # Hapus user dari mapping jika terputus
    for user, sid in list(user_sockets.items()):
        if sid == request.sid:
            del user_sockets[user]
            break

@socketio.on('register_user')
def handle_register_user(username):
    if username:
        user_sockets[username] = request.sid
        join_room(username)
        print(f"User '{username}' terdaftar dengan SID: {request.sid}")

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    target = data.get('target')
    message = data.get('message')

    if sender and target and message:
        print(f"Pesan dari {sender} ke {target}: {message}")
        # Kirim pesan ke room target user
        emit('private_message', {
            'sender': sender,
            'message': message
        }, room=target)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)