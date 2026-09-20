from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import mysql.connector
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia_super_aman'
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*")

# Konfigurasi Database (Sesuaikan dengan kredensial Anda)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'haihalo_db'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# ---------------- API ENDPOINTS ----------------

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'status': 'error', 'message': 'Username wajib diisi'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Cek apakah user sudah ada
        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            # Buat user baru jika belum terdaftar
            cursor.execute("INSERT INTO users (username) VALUES (%s)", (username,))
            conn.commit()
            
        return jsonify({'status': 'success', 'username': username}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/users', methods=['GET'])
def get_users():
    current_user = request.args.get('current_user')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT username FROM users WHERE username != %s", (current_user,))
        users = cursor.fetchall()
        return jsonify({'users': [u['username'] for u in users]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/messages', methods=['GET'])
def get_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')
    
    if not user1 or not user2:
        return jsonify({'status': 'error', 'message': 'Parameter user1 & user2 diperlukan'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT sender, target, message, created_at 
            FROM messages 
            WHERE (sender = %s AND target = %s) OR (sender = %s AND target = %s)
            ORDER BY id ASC
        """, (user1, user2, user2, user1))
        messages = cursor.fetchall()
        return jsonify({'messages': messages}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---------------- SOCKET.IO EVENTS ----------------

@app.on_event('connect')
def handle_connect():
    print("[SOCKET] Client connected")

@socketio.on('register_user')
def handle_register_user(username):
    if username:
        join_room(username)
        print(f"[SOCKET] User '{username}' mendaftar room.")

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    target = data.get('target')
    message = data.get('message')

    if sender and target and message:
        payload = {
            'sender': sender,
            'target': target,
            'message': message
        }
        
        # Kirim pesan secara real-time ke room penerima DAN pengirim
        emit('private_message', payload, room=target)
        emit('private_message', payload, room=sender)

        # Simpan pesan ke MySQL Database
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO messages (sender, target, message) VALUES (%s, %s, %s)",
                (sender, target, message)
            )
            conn.commit()
        except Exception as e:
            print("[DB ERROR]", e)
        finally:
            cursor.close()
            conn.close()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)