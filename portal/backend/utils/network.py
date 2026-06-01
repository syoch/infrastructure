import socket

def get_local_ip():
    """
    Detects the local IP address of the server on the LAN by attempting
    a connection to a dummy external IP. Does not send actual packets.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 8.8.8.8 is a dummy address, no connection is actually made
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
