"""
Network Manager using the working broadcast method
"""

import socket
import threading
import json
import time
import uuid

class NetworkManager:
    def __init__(self, database):
        self.database = database
        self.running = False
        self.broadcast_thread = None
        self.listen_thread = None
        self.tcp_thread = None
        self.online_users = {}
        self.message_callbacks = []
        
        # Configuration
        self.port = 6667
        self.broadcast_interval = 3
        
        # User info
        self.user_id = str(uuid.uuid4())[:8]
        self.username = None
        self.local_ip = self._get_local_ip()
        
        print(f"[NETWORK] Initialized: {self.local_ip}")
    
    def _get_local_ip(self):
        """Get local IP"""
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
        print(f"[NETWORK] Username: {username}")
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        
        # Start UDP broadcast (like their working code)
        self.broadcast_thread = threading.Thread(
            target=self._broadcast_presence,
            daemon=True
        )
        self.broadcast_thread.start()
        
        # Start UDP listener (like their working code)
        self.listen_thread = threading.Thread(
            target=self._listen_for_peers,
            daemon=True
        )
        self.listen_thread.start()
        
        # Start TCP server for messages
        self.tcp_thread = threading.Thread(
            target=self._tcp_server,
            daemon=True
        )
        self.tcp_thread.start()
        
        print(f"[NETWORK] Started on port {self.port}")
    
    def stop(self):
        self.running = False
    
    def get_online_users(self):
        """Get online users list"""
        current_time = time.time()
        stale_users = []
        
        for user_id, data in self.online_users.items():
            if current_time - data['last_seen'] > 10:
                stale_users.append(user_id)
        
        for user_id in stale_users:
            del self.online_users[user_id]
        
        return [
            {
                'username': data['username'],
                'ip': data['ip'],
                'last_seen': data['last_seen']
            }
            for user_id, data in self.online_users.items()
            if user_id != self.user_id
        ]
    
    def send_message(self, sender, recipient_ip, message):
        """Send message via TCP"""
        try:
            print(f"[NETWORK] Connecting to {recipient_ip}:{self.port}")
            
            # Create TCP socket
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(5)
            
            # Connect
            c.connect((recipient_ip, self.port))
            
            # Prepare message
            packet = {
                'type': 'message',
                'sender': sender,
                'message': message,
                'timestamp': time.time()
            }
            
            # Send
            c.send(json.dumps(packet).encode('utf-8'))
            
            # Get response
            response = c.recv(1024).decode()
            c.close()
            
            if response == "OK":
                print(f"[NETWORK] Message sent to {recipient_ip}")
                return True
            else:
                print(f"[NETWORK] Bad response: {response}")
                return False
                
        except socket.timeout:
            print(f"[NETWORK] Timeout connecting to {recipient_ip}")
            return False
        except ConnectionRefusedError:
            print(f"[NETWORK] Connection refused by {recipient_ip}")
            return False
        except Exception as e:
            print(f"[NETWORK] Error: {e}")
            return False
    
    def register_message_callback(self, callback):
        self.message_callbacks.append(callback)
    
    def _broadcast_presence(self):
        """Broadcast our presence (like their working code)"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        print(f"[BROADCAST] Started on port {self.port}")
        
        while self.running:
            if self.username:
                try:
                    # Create discovery message
                    discovery_msg = {
                        'type': 'discovery',
                        'user_id': self.user_id,
                        'username': self.username,
                        'ip': self.local_ip,
                        'timestamp': time.time()
                    }
                    
                    # Convert to JSON string
                    message = json.dumps(discovery_msg)
                    
                    # Broadcast using their method
                    sock.sendto(
                        message.encode('utf-8'),
                        ('<broadcast>', self.port)  # Their working method
                    )
                    
                    print(f"[BROADCAST] Sent: {self.username}")
                    
                except Exception as e:
                    print(f"[BROADCAST] Error: {e}")
            
            time.sleep(self.broadcast_interval)
        
        sock.close()
        print("[BROADCAST] Stopped")
    
    def _listen_for_peers(self):
        """Listen for peer broadcasts (like their working code)"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', self.port))  # Bind to all interfaces
        
        print(f"[LISTEN] Listening on port {self.port}")
        
        while self.running:
            try:
                # Receive data (blocking)
                data, addr = sock.recvfrom(1024)
                
                try:
                    # Try to parse as JSON
                    packet = json.loads(data.decode('utf-8'))
                    
                    if packet.get('type') == 'discovery':
                        user_id = packet.get('user_id')
                        username = packet.get('username')
                        ip = packet.get('ip', addr[0])
                        
                        if user_id != self.user_id:
                            self.online_users[user_id] = {
                                'username': username,
                                'ip': ip,
                                'last_seen': time.time()
                            }
                            print(f"[LISTEN] Discovered {username} at {ip}")
                    
                except json.JSONDecodeError:
                    # Not JSON, check if it's a simple discovery message
                    if data == b'SECURE_FILE_SHARE_DISCOVERY':
                        print(f"[LISTEN] Simple discovery from {addr[0]}")
                except:
                    pass
                    
            except Exception as e:
                print(f"[LISTEN] Error: {e}")
                break
        
        sock.close()
        print("[LISTEN] Stopped")
    
    def _tcp_server(self):
        """TCP server for messages"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(('0.0.0.0', self.port))
            sock.listen(5)
            sock.settimeout(1)
            
            print(f"[TCP] Server listening on port {self.port}")
            
            while self.running:
                try:
                    # Accept connection
                    c, addr = sock.accept()
                    c.settimeout(5)
                    
                    print(f"[TCP] Connection from {addr}")
                    
                    # Handle in thread
                    threading.Thread(
                        target=self._handle_tcp_client,
                        args=(c, addr),
                        daemon=True
                    ).start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[TCP] Accept error: {e}")
                    continue
                    
        except Exception as e:
            print(f"[TCP] Server error: {e}")
        finally:
            sock.close()
            print("[TCP] Server stopped")
    
    def _handle_tcp_client(self, c, addr):
        try:
            # Receive data
            data = b''
            while True:
                chunk = c.recv(4096)
                if not chunk:
                    break
                data += chunk
                
                # Try to parse JSON
                try:
                    json.loads(data.decode('utf-8'))
                    break
                except:
                    continue
            
            if data:
                packet = json.loads(data.decode('utf-8'))
                
                if packet.get('type') == 'message':
                    sender = packet.get('sender', 'Unknown')
                    message = packet.get('message', '')
                    timestamp = packet.get('timestamp', time.time())

                    print(f"[TCP] Message from {sender}: {message}")

                     # 🔥 SAVE MESSAGE LOCALLY 🔥
                    self.database.save_message(
                        sender,
                        self.username,
                        message,
                        is_encrypted=False
                    )
                    
                    # Call callbacks
                    for callback in self.message_callbacks:
                        try:
                            callback(packet)
                        except:
                            pass
                
                # Send response
                c.send(b"OK")
            
        except Exception as e:
            print(f"[TCP] Client error: {e}")
        finally:
            try:
                c.close()
            except:
                pass