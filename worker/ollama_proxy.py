import socket
import threading

def forward(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        src.close()
        dst.close()

def handle_client(client_socket):
    try:
        target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target.connect(("127.0.0.1", 11434))
        t1 = threading.Thread(target=forward, args=(client_socket, target), daemon=True)
        t2 = threading.Thread(target=forward, args=(target, client_socket), daemon=True)
        t1.start()
        t2.start()
    except Exception as e:
        client_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 11435))
    server.listen(100)
    print("Ollama proxy listening on 0.0.0.0:11435 -> 127.0.0.1:11434", flush=True)
    while True:
        client, addr = server.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()

if __name__ == "__main__":
    main()
