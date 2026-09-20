from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymysql
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Konfigurasi Database Aiven dari Environment Variables
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )

# --- ENDPOINT REGISTER ---
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Cek apakah username sudah dipakai
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Username sudah terdaftar!"}), 400

            # Hash password dan simpan ke database
            hashed_pwd = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pwd))
            conn.commit()
            
            return jsonify({"status": "success", "message": "Registrasi berhasil! Silakan login."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- ENDPOINT LOGIN ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Cari user berdasarkan username
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            # Verifikasi user & password
            if user and check_password_hash(user['password'], password):
                return jsonify({"status": "success", "message": "Login berhasil!", "username": username})
            else:
                return jsonify({"status": "error", "message": "Username atau password tidak sesuai"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# WebSocket Event
@socketio.on('message')
def handle_message(msg):
    emit('message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)