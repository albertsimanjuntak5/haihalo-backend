import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 21021)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME", "defaultdb"),
        ssl_mode="REQUIRED"
    )

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Username sudah terdaftar"}), 400

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password)
        )
        conn.commit()
        return jsonify({"status": "success", "message": "Registrasi berhasil, silakan login"}), 201
    except Exception as e:
        print("Error Register:", e)
        return jsonify({"status": "error", "message": "Gagal meregistrasi akun"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({"status": "error", "message": "Username atau password salah"}), 401

        return jsonify({"status": "success", "message": "Login berhasil", "username": username}), 200
    except Exception as e:
        print("Error Login:", e)
        return jsonify({"status": "error", "message": "Gagal melakukan login"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users ORDER BY username ASC")
        users = [row[0] for row in cursor.fetchall()]
        return jsonify(users), 200
    except Exception as e:
        print("Error Fetch Users:", e)
        return jsonify([]), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/messages', methods=['GET'])
def get_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')

    if not user1 or not user2:
        return jsonify([]), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT sender, target, message, created_at 
            FROM messages 
            WHERE (sender = %s AND target = %s) OR (sender = %s AND target = %s)
            ORDER BY created_at ASC
        """
        cursor.execute(query, (user1, user2, user2, user1))
        messages = cursor.fetchall()

        for msg in messages:
            if msg.get('created_at'):
                msg['created_at'] = msg['created_at'].isoformat()

        return jsonify(messages), 200
    except Exception as e:
        print("Error Fetch Messages:", e)
        return jsonify([]), 500
    finally:
        cursor.close()
        conn.close()

# ---------------- SOCKET.IO REAL-TIME CHAT ----------------
@socketio.on('register_user')
def handle_register_user(username):
    if username:
        join_room(username)
        print(f"[Socket] User '{username}' berhasil masuk ke room socket.")

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    target = data.get('target')
    message = data.get('message')

    if sender and target and message:
        payload = {'sender': sender, 'target': target, 'message': message}
        
        # Kirim ke penerima dan ke pengirim
        emit('private_message', payload, room=target)
        emit('private_message', payload, room=sender)

        # Simpan ke Database MySQL
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO messages (sender, target, message) VALUES (%s, %s, %s)",
                (sender, target, message)
            )
            conn.commit()
        except Exception as e:
            print("Error Save Message DB:", e)
        finally:
            cursor.close()
            conn.close()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)