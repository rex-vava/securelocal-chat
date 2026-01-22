"""
DatabaseManager with read receipts & typing indicators
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.connection = None
        self.lock = Lock()  # Thread-safe for Flask
        self.typing_users = set()  # In-memory: (username, recipient)
        self.connect()
        self.initialize_database()

    def connect(self):
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def initialize_database(self):
        """Create tables if they do not exist and ensure 'status' column exists."""
        with self.lock:
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

            # Ensure 'status' column exists
            cursor.execute("PRAGMA table_info(messages)")
            columns = [c[1] for c in cursor.fetchall()]
            if "status" not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN status TEXT DEFAULT "sent"')

            # Indexes for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(sender, recipient)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')

            self.connection.commit()

    # ---------------- User Methods ----------------
    def add_user(self, username, security_mode=1):
        with self.lock:
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
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                'UPDATE users SET security_mode = ? WHERE username = ?',
                (security_mode, username)
            )
            self.connection.commit()

    # ---------------- Message Methods ----------------
    def save_message(self, sender, recipient, message, is_encrypted=False):
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO messages (sender, recipient, message, is_encrypted, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (sender, recipient, message, is_encrypted, "sent"))
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
            utc_dt = datetime.fromisoformat(msg['timestamp'])
            local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(gmt_plus_2)
            msg['timestamp'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            messages.append(msg)

        return messages

    def update_message_status(self, message_id, status):
        """Update a single message's status: sent, delivered, read"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                'UPDATE messages SET status = ? WHERE id = ?',
                (status, message_id)
            )
            self.connection.commit()

    def get_unread_messages(self, recipient):
        cursor = self.connection.cursor()
        cursor.execute(
            'SELECT * FROM messages WHERE recipient = ? AND status != "read"',
            (recipient,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def clear_old_messages(self, days=30):
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                'DELETE FROM messages WHERE timestamp < datetime("now", ?)',
                (f"-{days} days",)
            )
            self.connection.commit()
            return cursor.rowcount

    # ---------------- Typing Indicator Methods ----------------
    def user_started_typing(self, username, recipient):
        """Call when user starts typing"""
        self.typing_users.add((username, recipient))

    def user_stopped_typing(self, username, recipient):
        """Call when user stops typing"""
        self.typing_users.discard((username, recipient))

    def get_typing_users(self, recipient):
        """Returns list of users typing to `recipient`"""
        return [u for u, r in self.typing_users if r == recipient]
