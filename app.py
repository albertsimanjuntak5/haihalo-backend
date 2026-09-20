from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymysql
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Izinkan CORS untuk semua domain & method (POST/GET/OPTIONS)
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Username sudah terdaftar!"}), 400

            hashed_pwd = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pwd))
            conn.commit()
            
            return jsonify({"status": "success", "message": "Registrasi berhasil! Silakan masuk."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                return jsonify({"status": "success", "message": "Login berhasil!", "username": username})
            else:
                return jsonify({"status": "error", "message": "Username atau password tidak sesuai"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@socketio.on('message')
def handle_message(msg):
    emit('message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)