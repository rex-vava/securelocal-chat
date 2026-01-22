"""
Check network configuration
"""

import socket
# import netifaces  # Optional, install with: pip install netifaces

def check_network():
    print("="*60)
    print("NETWORK CONFIGURATION CHECK")
    print("="*60)
    
    # Get hostname
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    
    # Get IP addresses
    print("\nIP Addresses:")
    try:
        # Method 1: Standard socket
        _, _, ips = socket.gethostbyname_ex(hostname)
        for ip in ips:
            print(f"  - {ip}")
    except:
        pass
    
    # Method 2: UDP method
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"  - {local_ip} (via UDP method)")
    except:
        pass
    
    # Check UDP broadcasting
    print("\nTesting UDP broadcast...")
    test_udp_broadcast()
    
    print("\n" + "="*60)

def test_udp_broadcast():
    """Test if UDP broadcasting works"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    # Test broadcast addresses
    test_addresses = [
        ('255.255.255.255', 6667),
        ('192.168.1.255', 6667),
        ('192.168.0.255', 6667),
        ('10.255.255.255', 6667),
    ]
    
    for addr, port in test_addresses:
        try:
            sock.sendto(b"TEST", (addr, port))
            print(f"  ✓ Broadcast to {addr}:{port} sent")
        except Exception as e:
            print(f"  ✗ Failed to broadcast to {addr}:{port}: {e}")
    
    sock.close()

if __name__ == "__main__":
    check_network()