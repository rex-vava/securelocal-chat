"""
Network Manager - UDP discovery + TCP messaging with E2EE + status sync
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

        self.online_users = {}      # user_id -> {username, ip, public_key, last_seen}
        self.session_keys = {}      # user_id -> AES key
        self.message_callbacks = [] # UI / Flask listeners

        self.public_key = None
        self.private_key = None

        print(f"[NETWORK] Initialized at {self.local_ip}")

    # ------------------ Helpers ------------------
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

    # ------------------ Start / Stop ------------------
    def start(self):
        if not self.username or not self.public_key:
            raise RuntimeError("set_username() first")

        if self.running:
            return

        self.running = True
        threading.Thread(target=self._broadcast_presence, daemon=True).start()
        threading.Thread(target=self._listen_for_peers, daemon=True).start()
        threading.Thread(target=self._tcp_server, daemon=True).start()

        print("[NETWORK] Running")

    def stop(self):
        self.running = False

    # ------------------ UDP Discovery ------------------
    def _broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            packet = {
                "type": "discovery",
                "user_id": self.user_id,
                "username": self.username,
                "public_key": self.public_key.decode()
            }
            sock.sendto(json.dumps(packet).encode(), ("<broadcast>", self.DISCOVERY_PORT))
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
                pkt = json.loads(data.decode())

                if pkt.get("type") != "discovery":
                    continue
                if pkt["user_id"] == self.user_id:
                    continue

                self.online_users[pkt["user_id"]] = {
                    "username": pkt["username"],
                    "ip": addr[0],
                    "public_key": pkt["public_key"],
                    "last_seen": time.time()
                }

            except socket.timeout:
                pass

        sock.close()

    def get_online_users(self):
        now = time.time()
        self.online_users = {
            uid: u for uid, u in self.online_users.items()
            if now - u["last_seen"] <= 10
        }
        return [{"user_id": uid, **u} for uid, u in self.online_users.items()]

    # ------------------ TCP Server ------------------
    def _tcp_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.TCP_PORT))
        sock.listen(5)
        sock.settimeout(1)

        while self.running:
            try:
                conn, _ = sock.accept()
                threading.Thread(
                    target=self._handle_tcp_client,
                    args=(conn,),
                    daemon=True
                ).start()
            except socket.timeout:
                pass

        sock.close()

    def _handle_tcp_client(self, c):
        try:
            packet = json.loads(c.recv(8192).decode())
            ptype = packet.get("type")

            # ---- Session key exchange ----
            if ptype == "session_key":
                self.session_keys[packet["sender_id"]] = decrypt_session_key(
                    packet["data"], self.private_key
                )
                c.send(b"OK")

            # ---- Secure message ----
            elif ptype == "secure_message":
                sender_id = packet["sender_id"]
                plaintext = decrypt_message(
                    packet["payload"],
                    self.session_keys[sender_id]
                )

                msg_id = self.database.save_message(
                    packet["sender"],
                    self.username,
                    plaintext,
                    is_encrypted=True,
                    status="delivered"
                )

                # notify sender (✔✔)
                self.send_status_update(sender_id, msg_id, "delivered")

                for cb in self.message_callbacks:
                    cb({
                        "type": "message",
                        "sender": packet["sender"],
                        "message": plaintext,
                        "id": msg_id
                    })

                c.send(b"OK")

            # ---- Status update ----
            elif ptype == "status_update":
                self.database.update_message_status(
                    packet["message_id"],
                    packet["status"]
                )

                for cb in self.message_callbacks:
                    cb({
                        "type": "status",
                        "message_id": packet["message_id"],
                        "status": packet["status"]
                    })

                c.send(b"OK")

        except Exception as e:
            print("[TCP ERROR]", e)
        finally:
            c.close()

    # ------------------ Send message ------------------
    def send_message(self, recipient_id, plaintext):
        user = self.online_users[recipient_id]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((user["ip"], self.TCP_PORT))

        if recipient_id not in self.session_keys:
            sk = generate_session_key()
            self.session_keys[recipient_id] = sk
            sock.send(json.dumps({
                "type": "session_key",
                "sender_id": self.user_id,
                "data": encrypt_session_key(sk, user["public_key"])
            }).encode())
            sock.recv(1024)

        sock.send(json.dumps({
            "type": "secure_message",
            "sender": self.username,
            "sender_id": self.user_id,
            "payload": encrypt_message(plaintext, self.session_keys[recipient_id]),
            "timestamp": time.time()
        }).encode())

        sock.recv(1024)
        sock.close()

    # ------------------ Status sender ------------------
    def send_status_update(self, recipient_id, message_id, status):
        if recipient_id not in self.online_users:
            return

        user = self.online_users[recipient_id]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((user["ip"], self.TCP_PORT))

        sock.send(json.dumps({
            "type": "status_update",
            "message_id": message_id,
            "status": status
        }).encode())

        sock.recv(1024)
        sock.close()
