#!/usr/bin/env python3
"""
SecureLocal Chat using working broadcast + TCP/E2EE
"""

import sys
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash

from security import SecurityManager
from database import DatabaseManager
from network import NetworkManager

# ----------------- Flask Setup -----------------
app = Flask(__name__)
app.secret_key = os.urandom(24)

# ----------------- Global Instances -----------------
security: SecurityManager = None
database: DatabaseManager = None
network: NetworkManager = None

# ----------------- App Initialization -----------------
def initialize_app():
    global security, database, network
    try:
        # Create app data directory
        data_path = Path.home() / '.securelocalchat' if sys.platform != 'win32' else Path(os.environ.get('APPDATA', '')) / 'SecureLocalChat'
        data_path.mkdir(parents=True, exist_ok=True)

        # Initialize core components
        database = DatabaseManager(data_path / 'chat.db')
        security = SecurityManager(data_path)
        network = NetworkManager(database)

        print("[APP] Initialization successful")
        return True
    except Exception as e:
        print(f"[APP] Initialization failed: {e}")
        return False

if not initialize_app():
    print("WARNING: Failed to initialize app")

# ----------------- Web Routes -----------------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter username and password', 'error')
            return render_template('login.html')

        if security.verify_user(username, password):
            session['username'] = username
            if network:
                network.set_username(username)
                network.start()
            if not database.user_exists(username):
                database.add_user(username)
            flash('Welcome back!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('Invalid username or password', 'error')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        errors = []

        if not username:
            errors.append('Username required')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters')
        elif security.user_exists(username):
            errors.append('Username already exists')

        if not password:
            errors.append('Password required')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters')
        elif password != confirm:
            errors.append('Passwords do not match')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')

        if security.create_user(username, password):
            database.initialize_database()
            database.add_user(username)
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed', 'error')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# ----------------- API Endpoints -----------------
@app.route('/api/users')
def api_get_users():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        return jsonify({'users': network.get_online_users() if network else []})
    except Exception:
        return jsonify({'users': []})

@app.route('/api/messages', methods=['GET', 'POST'])
def api_messages():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    current_user = session['username']

    if request.method == 'POST':
        data = request.json
        recipient = data.get("recipient", "").strip()
        message = data.get("message", "").strip()

        if not recipient or not message:
            return jsonify({"error": "Recipient and message required"}), 400

        msg_id = database.save_message(current_user, recipient, message, is_encrypted=False)

        # Send message via network if recipient is online
        if network:
          recipient_user = next((uid for uid, u in network.get_online_users().items() if u['username'] == recipient), None)
        if recipient_user:
            network.send_message(recipient_user, message)

        return jsonify({"success": True, "message_id": msg_id})

    else:
        other_user = request.args.get("with", "").strip()
        if not other_user:
            return jsonify({"error": "Recipient required"}), 400

        messages = database.get_messages(current_user, other_user)

        # Auto-update sent → delivered
        for msg in messages:
            if msg["recipient"] == current_user and msg["status"] == "sent":
                database.update_message_status(msg["id"], "delivered")
                msg["status"] = "delivered"

        return jsonify({"messages": messages})

@app.route('/api/update_status', methods=['POST'])
def api_update_status():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.json
    message_id = data.get('message_id')
    status = data.get('status')

    if not message_id or status not in ('sent', 'delivered', 'read'):
        return jsonify({'error': 'Invalid parameters'}), 400

    try:
        database.update_message_status(message_id, status)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------- Typing Indicators -----------------
@app.route('/api/typing', methods=['POST'])
def api_typing():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.json
    recipient = data.get("recipient", "").strip()
    action = data.get("action")

    if not recipient or action not in ("start", "stop"):
        return jsonify({"error": "Invalid parameters"}), 400

    if action == "start":
        database.user_started_typing(session['username'], recipient)
    else:
        database.user_stopped_typing(session['username'], recipient)

    return jsonify({"success": True})

@app.route('/api/get_typing', methods=['GET'])
def api_get_typing():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    typing_users = database.get_typing_users(session['username'])
    return jsonify({"typing": typing_users})

# ----------------- Main -----------------
def main():
    print("\n" + "="*60)
    print("SECURELOCAL CHAT - WORKING BROADCAST METHOD")
    print("="*60)
    print("Port 6667: UDP Discovery + TCP Messaging")
    print("Web Interface: http://localhost:5000")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
