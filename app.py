#!/usr/bin/env python3
"""
SecureLocal Chat using working broadcast method
"""

import sys
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash

from security import SecurityManager
from database import DatabaseManager
from network import NetworkManager

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global instances
security = None
database = None
network = None

def initialize_app():
    """Initialize application components"""
    global security, database, network
    
    try:
        # Create data directory
        if sys.platform == 'win32':
            data_path = Path(os.environ.get('APPDATA', '')) / 'SecureLocalChat'
        else:
            data_path = Path.home() / '.securelocalchat'
        data_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        database = DatabaseManager(data_path / 'chat.db')
        security = SecurityManager(data_path)
        network = NetworkManager(database)
        
        # Start network
        network.start()
        
        print("[APP] Initialized successfully")
        return True
    except Exception as e:
        print(f"[APP] Initialization failed: {e}")
        return False

# Initialize on import
if not initialize_app():
    print("WARNING: Failed to initialize app")

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
            
            # Set network username
            if network:
                network.set_username(username)
            
            # Ensure user in database
            if not database.user_exists(username):
                database.add_user(username, 1)
            
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
        
        # Validation
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
        
        # Create user
        if security.create_user(username, password):
            database.initialize_database()
            database.add_user(username, 1)
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

@app.route('/api/users')
def get_users():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if not network:
        return jsonify({'users': []})
    
    try:
        users = network.get_online_users()
        return jsonify({'users': users})
    except:
        return jsonify({'users': []})

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if request.method == 'POST':
        try:
            data = request.json
            recipient = data.get('recipient', '').strip()
            message = data.get('message', '').strip()
            
            if not recipient:
                return jsonify({'error': 'Recipient required'}), 400
            if not message:
                return jsonify({'error': 'Message required'}), 400
            
            print(f"[API] Sending to {recipient}")
            
            # Find recipient IP
            users = network.get_online_users()
            recipient_ip = None
            
            for user in users:
                if user['username'] == recipient:
                    recipient_ip = user['ip']
                    break
            
            if not recipient_ip:
                return jsonify({'error': 'User not online'}), 400
            
            # Send message
            success = network.send_message(
                session['username'],
                recipient_ip,
                message
            )
            
            if success:
                # Store sent message
                database.save_message(
                    session['username'],
                    recipient,
                    message,
                    is_encrypted=False
                )
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Failed to send message'}), 500
                
        except Exception as e:
            print(f"[API] Error: {e}")
            return jsonify({'error': 'Server error'}), 500
    
    else:  # GET
        recipient = request.args.get('with', '').strip()
        if not recipient:
            return jsonify({'error': 'Recipient required'}), 400
        
        try:
            messages = database.get_messages(session['username'], recipient)
            return jsonify({'messages': messages})
        except:
            return jsonify({'messages': []})

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

def main():
    print("\n" + "="*60)
    print("SECURELOCAL CHAT - WORKING BROADCAST METHOD")
    print("="*60)
    print("Port 6667: UDP Discovery + TCP Messaging")
    print("Web Interface: http://localhost:5000")
    print("="*60)
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()