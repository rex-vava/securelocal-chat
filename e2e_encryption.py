from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Random import get_random_bytes
import base64
import os
import json

# -------------------- RSA Key Management --------------------
def generate_rsa_keys(user_id):
    """Generate and save RSA public/private key pair."""
    key = RSA.generate(2048)
    private_key = key.export_key()
    public_key = key.publickey().export_key()

    # Save keys locally
    os.makedirs(f'keys/{user_id}', exist_ok=True)
    with open(f'keys/{user_id}/private.pem', 'wb') as f:
        f.write(private_key)
    with open(f'keys/{user_id}/public.pem', 'wb') as f:
        f.write(public_key)

    return public_key, private_key

def load_rsa_keys(user_id):
    with open(f'keys/{user_id}/private.pem', 'rb') as f:
        private_key = RSA.import_key(f.read())
    with open(f'keys/{user_id}/public.pem', 'rb') as f:
        public_key = RSA.import_key(f.read())
    return public_key, private_key

# -------------------- AES Session Key Management --------------------
def generate_session_key():
    """Generate a random AES session key."""
    return get_random_bytes(32)  # 256-bit AES key

def encrypt_session_key(session_key, friend_public_key):
    """Encrypt AES session key using friend's RSA public key."""
    cipher_rsa = PKCS1_OAEP.new(RSA.import_key(friend_public_key))
    encrypted_session_key = cipher_rsa.encrypt(session_key)
    return base64.b64encode(encrypted_session_key).decode()

def decrypt_session_key(encrypted_session_key_b64, private_key):
    encrypted_session_key = base64.b64decode(encrypted_session_key_b64)
    cipher_rsa = PKCS1_OAEP.new(private_key)
    return cipher_rsa.decrypt(encrypted_session_key)

# -------------------- AES Message Encryption --------------------
def encrypt_message(message, session_key):
    cipher_aes = AES.new(session_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(message.encode())
    data = {
        'nonce': base64.b64encode(cipher_aes.nonce).decode(),
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'tag': base64.b64encode(tag).decode()
    }
    return json.dumps(data)

def decrypt_message(encrypted_data_json, session_key):
    data = json.loads(encrypted_data_json)
    nonce = base64.b64decode(data['nonce'])
    ciphertext = base64.b64decode(data['ciphertext'])
    tag = base64.b64decode(data['tag'])
    cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce=nonce)
    return cipher_aes.decrypt_and_verify(ciphertext, tag).decode()
