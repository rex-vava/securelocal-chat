"""
Network Manager - UDP discovery + TCP messaging with E2EE
"""

import socket
import threading
import json
import time
import uuid
import os

from e2e_encryption import (
    generate_rsa_keys, load_rsa_keys,
    generate_session_key, encrypt_session_key, decrypt_session_key,
    encrypt_message, decrypt_message
)


class NetworkManager:
    DISCOVERY_PORT = 6667
    TCP_PORT = 6668
    BROADCAST_INTERVAL = 3

    def __init__(self, database):
        self.database = database
        self.running = False

        self.user_id = str(uuid.uuid4())[:8]
        self.username = None
        self.local_ip = self._get_local_ip()

        # Online users: user_id -> {username, ip, public_key, last_seen}
        self.online_users = {}

        # Message callbacks for GUI or API
        self.message_callbacks = []

        # E2EE
        self.public_key = None
        self.private_key = None
        self.session_keys = {}  # user_id -> AES key

        print(f"[NETWORK] Initialized at IP {self.local_ip}")

    # ------------------ Helper ------------------
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

    # ------------------ Start / Stop ------------------
    def start(self):
        if not self.username or not self.public_key:
            raise Exception("Call set_username() before start()")

        if self.running:
            return  # Already running

        self.running = True

        threading.Thread(target=self._broadcast_presence, daemon=True).start()
        threading.Thread(target=self._listen_for_peers, daemon=True).start()
        threading.Thread(target=self._tcp_server, daemon=True).start()

        print("[NETWORK] Started UDP discovery + TCP server")

    def stop(self):
        self.running = False

    # ------------------ UDP Discovery ------------------
    def _broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                packet = json.dumps({
                    "type": "discovery",
                    "user_id": self.user_id,
                    "username": self.username,
                    "public_key": self.public_key.decode()
                })
                sock.sendto(packet.encode(), ("<broadcast>", self.DISCOVERY_PORT))
            except Exception as e:
                print("[BROADCAST ERROR]", e)

            time.sleep(self.BROADCAST_INTERVAL)

        sock.close()

    def _listen_for_peers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.DISCOVERY_PORT))
        sock.settimeout(1)

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                packet = json.loads(data.decode())

                if packet.get("type") != "discovery":
                    continue
                uid = packet["user_id"]
                if uid == self.user_id:
                    continue

                self.online_users[uid] = {
                    "username": packet["username"],
                    "ip": addr[0],
                    "public_key": packet["public_key"],
                    "last_seen": time.time()
                }

            except socket.timeout:
                continue
            except Exception as e:
                print("[DISCOVERY ERROR]", e)

        sock.close()

    def get_online_users(self):
        now = time.time()
        # Remove stale users (last seen > 10s ago)
        stale = [uid for uid, u in self.online_users.items() if now - u["last_seen"] > 10]
        for uid in stale:
            del self.online_users[uid]

        return [
            {"user_id": uid, **u}
            for uid, u in self.online_users.items()
        ]

    # ------------------ TCP Messaging ------------------
    def _tcp_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.TCP_PORT))
        sock.listen(5)
        sock.settimeout(1)

        while self.running:
            try:
                c, addr = sock.accept()
                threading.Thread(target=self._handle_tcp_client, args=(c,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                print("[TCP SERVER ERROR]", e)

        sock.close()

    def _handle_tcp_client(self, c):
        try:
            packet = json.loads(c.recv(8192).decode())
            ptype = packet.get("type")

            if ptype == "session_key":
                sender_id = packet["sender_id"]
                self.session_keys[sender_id] = decrypt_session_key(packet["data"], self.private_key)
                c.send(b"OK")

            elif ptype == "secure_message":
                sender_id = packet["sender_id"]
                plaintext = decrypt_message(packet["payload"], self.session_keys[sender_id])

                self.database.save_message(packet["sender"], self.username, plaintext, is_encrypted=True)

                for cb in self.message_callbacks:
                    cb({"sender": packet["sender"], "message": plaintext, "timestamp": packet["timestamp"]})

                c.send(b"OK")

        except Exception as e:
            print("[TCP ERROR]", e)
        finally:
            c.close()

    # ------------------ Send Message ------------------
    def send_message(self, recipient_id, plaintext):
        if recipient_id not in self.online_users:
            raise Exception("Recipient not online")

        user = self.online_users[recipient_id]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((user["ip"], self.TCP_PORT))

        # Ensure session key
        if recipient_id not in self.session_keys:
            sk = generate_session_key()
            self.session_keys[recipient_id] = sk
            encrypted_sk = encrypt_session_key(sk, user["public_key"])
            sock.send(json.dumps({
                "type": "session_key",
                "sender_id": self.user_id,
                "data": encrypted_sk
            }).encode())
            sock.recv(1024)  # ACK

        # Send encrypted message
        encrypted_msg = encrypt_message(plaintext, self.session_keys[recipient_id])
        sock.send(json.dumps({
            "type": "secure_message",
            "sender": self.username,
            "sender_id": self.user_id,
            "payload": encrypted_msg,
            "timestamp": time.time()
        }).encode())
        sock.recv(1024)
        sock.close()
