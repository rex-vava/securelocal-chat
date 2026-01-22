"""
Debug script to test UDP discovery
"""

import socket
import json
import threading
import time

def debug_discovery():
    """Test UDP discovery between devices"""
    
    def broadcaster(name, ip):
        """Broadcast presence"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        print(f"[{name}] Broadcasting from {ip}")
        
        while True:
            data = {
                'type': 'discovery',
                'name': name,
                'ip': ip,
                'time': time.time()
            }
            
            # Try different broadcast addresses
            for target in ['255.255.255.255', '192.168.1.255', '192.168.0.255']:
                try:
                    sock.sendto(json.dumps(data).encode(), (target, 6667))
                except:
                    pass
            
            print(f"[{name}] Broadcast sent")
            time.sleep(3)
    
    def listener(name):
        """Listen for broadcasts"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', 6667))
        sock.settimeout(1)
        
        print(f"[{name}] Listening on port 6667...")
        
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                packet = json.loads(data.decode())
                
                if packet.get('type') == 'discovery':
                    print(f"[{name}] Received from {packet.get('name')} at {addr[0]}")
            except socket.timeout:
                continue
            except:
                continue
    
    print("="*60)
    print("UDP DISCOVERY DEBUG")
    print("="*60)
    
    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    print(f"Your IP: {local_ip}")
    
    choice = input("\n1. Run both broadcast and listen\n2. Run broadcast only\n3. Run listen only\nChoose (1-3): ").strip()
    
    name = input("Enter your device name: ").strip() or "Device"
    
    if choice in ['1', '2']:
        # Start broadcaster
        broadcast_thread = threading.Thread(
            target=broadcaster, 
            args=(name, local_ip),
            daemon=True
        )
        broadcast_thread.start()
        print(f"Broadcaster started as '{name}'")
    
    if choice in ['1', '3']:
        # Start listener
        listen_thread = threading.Thread(
            target=listener,
            args=(name,),
            daemon=True
        )
        listen_thread.start()
        print("Listener started")
    
    print("\n" + "="*60)
    print("Press Ctrl+C to stop")
    print("="*60)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    debug_discovery()