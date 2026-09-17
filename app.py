import os
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-haihalo-key'

CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 21021)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "Backend HaiHalo Server Running!"})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi!"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO users (username, password) VALUES (%s, %s)"
        cursor.execute(query, (username, password))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "User berhasil terdaftar!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": str(err)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM users WHERE username = %s AND password = %s"
    cursor.execute(query, (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return jsonify({"status": "success", "user": {"id": user['id'], "username": user['username']}})
    else:
        return jsonify({"status": "error", "message": "Username atau password salah!"}), 401

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = data.get('sender_id')
    message_text = data.get('message_text')

    if sender_id and message_text:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO messages (sender_id, message_text) VALUES (%s, %s)"
        cursor.execute(query, (sender_id, message_text))
        conn.commit()
        cursor.close()
        conn.close()

        emit('receive_message', {
            'sender_id': sender_id,
            'message_text': message_text
        }, broadcast=True)

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)