"""
Simplified Security Manager - Just handles authentication
"""

import os
import json
import base64
import hashlib
import secrets
from pathlib import Path

class SecurityManager:
    def __init__(self, data_path):
        self.data_path = Path(data_path)
        self.users_file = self.data_path / 'users.json'
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    def create_user(self, username, password, security_mode=1):
        """Create new user with password"""
        users = self._load_users()
        
        # Generate salt
        salt = secrets.token_bytes(16)
        
        # Hash password with salt using PBKDF2
        password_hash = self._hash_password(password, salt)
        
        users[username] = {
            'password_hash': password_hash,
            'salt': base64.b64encode(salt).decode('utf-8'),
            'security_mode': security_mode,
            'created': secrets.token_hex(8)  # Simple timestamp
        }
        
        return self._save_users(users)
    
    def _hash_password(self, password, salt):
        """Hash password with salt using PBKDF2"""
        # Use built-in hashlib.pbkdf2_hmac
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000  # Number of iterations
        )
        return base64.b64encode(dk).decode('utf-8')
    
    def verify_user(self, username, password):
        """Verify user credentials"""
        users = self._load_users()
        
        if username not in users:
            return False
        
        user_data = users[username]
        salt = base64.b64decode(user_data['salt'])
        stored_hash = user_data['password_hash']
        
        calculated_hash = self._hash_password(password, salt)
        
        # Constant-time comparison
        return secrets.compare_digest(stored_hash, calculated_hash)
    
    def get_user_mode(self, username):
        users = self._load_users()
        return users.get(username, {}).get('security_mode', 1)
    
    def user_exists(self, username):
        users = self._load_users()
        return username in users
    
    def set_mode(self, mode):
        """Set security mode (compatibility method)"""
        pass
    
    def encrypt_message(self, message, recipient=None):
        """Simple encryption placeholder"""
        return message
    
    def decrypt_message(self, encrypted_data, sender=None):
        """Simple decryption placeholder"""
        return encrypted_data
    
    def _load_users(self):
        if not self.users_file.exists():
            return {}
        
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_users(self, users):
        try:
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            return True
        except:
            return False