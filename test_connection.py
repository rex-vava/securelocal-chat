import socket
import threading
import time

def test_simple_tcp():
    """Simple TCP test based on your working example"""
    
    def server():
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', 6667))
        s.listen(3)
        print("[TEST] Server listening on port 6667...")
        
        c, addr = s.accept()
        print(f"[TEST] Connected with {addr}")
        
        message = c.recv(1024).decode()
        print(f"[TEST] Received: {message}")
        
        c.send(b"Welcome to the server")
        c.close()
        s.close()
        print("[TEST] Server closed")
    
    def client(target_ip):
        time.sleep(1)
        c = socket.socket()
        
        print(f"[TEST] Connecting to {target_ip}:6667...")
        try:
            c.connect((target_ip, 6667))
            c.send(b"Hello from client!")
            
            response = c.recv(1024).decode()
            print(f"[TEST] Server says: {response}")
            
            c.close()
            return True
        except Exception as e:
            print(f"[TEST] Error: {e}")
            return False
    
    print("="*50)
    print("SIMPLE TCP TEST (Your Working Example)")
    print("="*50)
    
    choice = input("1. Run server\n2. Run client\nChoose (1 or 2): ").strip()
    
    if choice == "1":
        print("\nStarting server...")
        server()
    elif choice == "2":
        target_ip = input("\nEnter server IP: ").strip()
        print(f"\nConnecting to {target_ip}...")
        client(target_ip)
    
    print("="*50)

if __name__ == "__main__":
    test_simple_tcp()