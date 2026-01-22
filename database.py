"""
Simplified Database Manager - Just stores messages
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.connection = None
        self.connect()
    
    def connect(self):
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
    
    def initialize_database(self):
        cursor = self.connection.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                security_mode INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT NOT NULL,
                is_encrypted INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(sender, recipient)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
        
        self.connection.commit()
    
    def add_user(self, username, security_mode=1):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                'INSERT OR REPLACE INTO users (username, security_mode) VALUES (?, ?)',
                (username, security_mode)
            )
            self.connection.commit()
            return True
        except:
            return False
    
    def user_exists(self, username):
        cursor = self.connection.cursor()
        cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,))
        return cursor.fetchone() is not None
    
    def update_user_mode(self, username, security_mode):
        cursor = self.connection.cursor()
        cursor.execute(
            'UPDATE users SET security_mode = ? WHERE username = ?',
            (security_mode, username)
        )
        self.connection.commit()
    
    def save_message(self, sender, recipient, message, is_encrypted=False):
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT INTO messages (sender, recipient, message, is_encrypted)
            VALUES (?, ?, ?, ?)
        ''', (sender, recipient, message, is_encrypted))
        self.connection.commit()
        return cursor.lastrowid
    
    def get_messages(self, user1, user2, limit=50):
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE (sender = ? AND recipient = ?) 
            OR (sender = ? AND recipient = ?)
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (user1, user2, user2, user1, limit))

        messages = []
        gmt_plus_2 = timezone(timedelta(hours=2))

        for row in cursor.fetchall():
            msg = dict(row)

            # SQLite gives UTC time as string
            utc_dt = datetime.fromisoformat(msg['timestamp'])

            # Convert UTC → GMT+2
            local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(gmt_plus_2)

            msg['timestamp'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            messages.append(msg)

        return messages

    
    def clear_old_messages(self, days=30):
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM messages WHERE timestamp < datetime("now", ?)', (f"-{days} days",))
        self.connection.commit()
        return cursor.rowcount