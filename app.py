from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymysql
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Izinkan CORS penuh dari domain frontend mana pun
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")

# Konfigurasi Koneksi Database Aiven
def get_db_connection():
    # Menyesuaikan nama variabel dengan file .env kamu (DB_HOST, DB_USER, dst)
    host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST")
    user = os.getenv("DB_USER") or os.getenv("MYSQLUSER")
    password = os.getenv("DB_PASS") or os.getenv("MYSQLPASSWORD")
    database = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE")
    port = int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT", 21021))

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        cursorclass=pymysql.cursors.DictCursor,
        ssl={'ssl': {}} # Aiven mewajibkan SSL
    )

# --- ENDPOINT REGISTER ---
@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Cek apakah username sudah ada
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"status": "error", "message": "Username sudah terdaftar!"}), 400

            # Hash password lalu simpan
            hashed_pwd = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pwd))
            conn.commit()
            conn.close()
            
            return jsonify({"status": "success", "message": "Registrasi berhasil! Silakan masuk."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

# --- ENDPOINT LOGIN ---
@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            conn.close()

            # Verifikasi password yang di-hash
            if user and check_password_hash(user['password'], password):
                return jsonify({"status": "success", "message": "Login berhasil!", "username": username})
            else:
                return jsonify({"status": "error", "message": "Username atau password tidak sesuai"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

# WebSocket Event
@socketio.on('message')
def handle_message(msg):
    emit('message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)