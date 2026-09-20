import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'haihalo-secret-key-123')

CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Konfigurasi Database
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
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Username sudah terdaftar"}), 400

            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            conn.commit()
        return jsonify({"status": "success", "message": "Registrasi berhasil"}), 201
    except Exception as e:
        print("Database Error (Register):", e)
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
    finally:
        if conn: conn.close()

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

            saved_pw = user['password']
            is_valid = check_password_hash(saved_pw, password) if (saved_pw.startswith('scrypt:') or saved_pw.startswith('pbkdf2:')) else (saved_pw == password)

            if is_valid:
                return jsonify({"status": "success", "message": "Login berhasil", "username": username}), 200
            else:
                return jsonify({"status": "error", "message": "Password salah"}), 401
    except Exception as e:
        print("Database Error (Login):", e)
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
    finally:
        if conn: conn.close()

# API: Ambil semua daftar user dari database
@app.route('/users', methods=['GET'])
def get_users():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM users")
            users = cursor.fetchall()
            user_list = [u['username'] for u in users]
        return jsonify(user_list), 200
    except Exception as e:
        print("Database Error (Get Users):", e)
        return jsonify([]), 500
    finally:
        if conn: conn.close()

# API: Ambil riwayat percakapan antara dua user dari database
@app.route('/messages', methods=['GET'])
def get_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')

    if not user1 or not user2:
        return jsonify([]), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT sender, target, message, created_at 
                FROM messages 
                WHERE (sender = %s AND target = %s) OR (sender = %s AND target = %s)
                ORDER BY created_at ASC
            """
            cursor.execute(sql, (user1, user2, user2, user1))
            messages = cursor.fetchall()
        return jsonify(messages), 200
    except Exception as e:
        print("Database Error (Get Messages):", e)
        return jsonify([]), 500
    finally:
        if conn: conn.close()

# ================= SOCKET.IO EVENTS =================

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('register_user')
def handle_register_user(username):
    if username:
        join_room(username)
        print(f"User '{username}' bergabung ke roomnya sendiri: {username}")

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    target = data.get('target')
    message = data.get('message')

    if sender and target and message:
        # Simpan ke Database
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO messages (sender, target, message) VALUES (%s, %s, %s)",
                    (sender, target, message)
                )
                conn.commit()
        except Exception as e:
            print("Database Error (Save Message):", e)
        finally:
            if conn: conn.close()

        # Kirimkan pesan secara realtime ke room target dan ke room sender sendiri
        payload = {'sender': sender, 'target': target, 'message': message}
        emit('private_message', payload, room=target)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)