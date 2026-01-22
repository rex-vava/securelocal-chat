"""
Network Manager using the working broadcast method + E2EE
"""

from e2e_encryption import (
    generate_rsa_keys, load_rsa_keys,
    generate_session_key, encrypt_session_key, decrypt_session_key,
    encrypt_message, decrypt_message
)

import socket
import threading
import json
import time
import uuid
import os


class NetworkManager:
    def __init__(self, database):
        self.database = database
        self.running = False

        self.online_users = {}
        self.message_callbacks = []

        # E2EE
        self.public_key = None
        self.private_key = None
        self.session_keys = {}  # user_id -> AES key

        self.port = 6667
        self.broadcast_interval = 3

        self.user_id = str(uuid.uuid4())[:8]
        self.username = None
        self.local_ip = self._get_local_ip()

        print(f"[NETWORK] Initialized: {self.local_ip}")

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def set_username(self, username):
        self.username = username

        key_dir = f"keys/{self.user_id}"
        if not os.path.exists(key_dir):
            self.public_key, self.private_key = generate_rsa_keys(self.user_id)
        else:
            self.public_key, self.private_key = load_rsa_keys(self.user_id)

        print(f"[KEYS] Loaded for {username}")

    def start(self):
        if not self.username or not self.public_key:
            print("[NETWORK] Cannot start before set_username()")
            return
        self.running = True

        threading.Thread(target=self._broadcast_presence, daemon=True).start()
        threading.Thread(target=self._listen_for_peers, daemon=True).start()
        threading.Thread(target=self._tcp_server, daemon=True).start()

    # ------------------------------------------------------------------
    # UDP DISCOVERY
    # ------------------------------------------------------------------

    def _broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                packet = {
                    "type": "discovery",
                    "user_id": self.user_id,
                    "username": self.username,
                    "ip": self.local_ip,
                    "public_key": self.public_key.decode()
                }
                sock.sendto(json.dumps(packet).encode(), ("<broadcast>", self.port))
            except Exception as e:
                print("[BROADCAST ERROR]", e)

            time.sleep(self.broadcast_interval)

    def _listen_for_peers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.port))

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                packet = json.loads(data.decode())

                if packet["type"] == "discovery":
                    uid = packet["user_id"]
                    if uid == self.user_id:
                        continue

                    self.online_users[uid] = {
                        "username": packet["username"],
                        "ip": packet["ip"],
                        "public_key": packet["public_key"],
                        "last_seen": time.time()
                    }

            except:
                pass

    # ------------------------------------------------------------------
    # TCP
    # ------------------------------------------------------------------

    def _tcp_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))
        sock.listen(5)

        while self.running:
            try:
                c, addr = sock.accept()
                threading.Thread(
                    target=self._handle_tcp_client,
                    args=(c,),
                    daemon=True
                ).start()
            except:
                pass

    def _handle_tcp_client(self, c):
        try:
            packet = json.loads(c.recv(8192).decode())

            if packet["type"] == "session_key":
                self.session_keys[packet["sender_id"]] = decrypt_session_key(
                    packet["data"],
                    self.private_key
                )
                c.send(b"OK")
                return

            if packet["type"] == "secure_message":
                plaintext = decrypt_message(
                    packet["payload"],
                    self.session_keys[packet["sender_id"]]
                )

                self.database.save_message(
                    packet["sender"],
                    self.username,
                    plaintext,
                    is_encrypted=True
                )

                for cb in self.message_callbacks:
                    cb(plaintext)

                c.send(b"OK")

        except Exception as e:
            print("[TCP ERROR]", e)
        finally:
            c.close()

    # ------------------------------------------------------------------
    # SEND MESSAGE
    # ------------------------------------------------------------------

    def send_message(self, recipient_id, plaintext):
        user = self.online_users[recipient_id]

        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect((user["ip"], self.port))

        if recipient_id not in self.session_keys:
            sk = generate_session_key()
            self.session_keys[recipient_id] = sk

            encrypted_sk = encrypt_session_key(
                sk,
                user["public_key"]
            )

            c.send(json.dumps({
                "type": "session_key",
                "sender_id": self.user_id,
                "data": encrypted_sk
            }).encode())
            c.recv(1024)

        encrypted_msg = encrypt_message(
            plaintext,
            self.session_keys[recipient_id]
        )

        c.send(json.dumps({
            "type": "secure_message",
            "sender": self.username,
            "sender_id": self.user_id,
            "payload": encrypted_msg,
            "timestamp": time.time()
        }).encode())

        c.recv(1024)
        c.close()
