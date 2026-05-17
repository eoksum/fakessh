import socket
import threading
import paramiko
import datetime
import sys
import ctypes         

# Global IP deneme takip sözlüğü ve Thread kilidi
ip_attempts = {}
tracker_lock = threading.Lock()

HOST_KEY = paramiko.RSAKey.generate(2048)

def enforce_single_instance():
    """
    Windows üzerinde scriptin sadece tek bir kopyasının çalışmasını sağlar.
    Eğer başka bir kopya varsa, bu scripti anında sonlandırır.
    """
    mutex_name = "Global\\FakeSSHHoneypot_Mutex_2026"
    kernel32 = ctypes.windll.kernel32
    
    # Mutex oluşturuluyor
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    
    # 183 = ERROR_ALREADY_EXISTS (Zaten böyle bir mutex var demek)
    if last_error == 183:
        print("[-] Uyarı: Honeypot scripti zaten arka planda çalışıyor!")
        print("[-] Bu yeni instance hiçbir işlem yapmadan sonlandırılıyor...")
        sys.exit(0)
        
    return mutex # Script kapanana kadar çöp toplayıcı (GC) silmesin diye referansı tutuyoruz

class SSHHoneypot(paramiko.ServerInterface):
    def __init__(self, client_ip, client_port):
        self.client_ip = client_ip
        self.client_port = client_port
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        with tracker_lock:
            if self.client_ip not in ip_attempts:
                ip_attempts[self.client_ip] = 0
            
            ip_attempts[self.client_ip] += 1
            current_attempts = ip_attempts[self.client_ip]

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp}|{self.client_ip}|{self.client_port}|{current_attempts}|{username}|{password}|\n"
        
        print(log_message.strip())
        
        with open("ssh_bruteforce_logs.txt", "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

def handle_connection(client, addr):
    try:
        transport = paramiko.Transport(client)
        transport.add_server_key(HOST_KEY)
        
        server = SSHHoneypot(client_ip=addr[0], client_port=addr[1])
        try:
            transport.start_server(server=server)
        except paramiko.SSHException:
            return
        
        channel = transport.accept(20)
        if channel is None:
            pass
            
    except Exception:
        pass
    finally:
        try:
            transport.close()
        except:
            pass

def start_server(ip='0.0.0.0', port=22):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((ip, port))
        sock.listen(100)
        
        print(f"[*] Sahte SSH Sunucusu dinleniyor: {ip}:{port}")
        print("[*] Loglar 'ssh_bruteforce_logs.txt' dosyasına kaydediliyor...\n")
        
        while True:
            client, addr = sock.accept()
            threading.Thread(target=handle_connection, args=(client, addr)).start()
            
    except Exception as e:
        print(f"[-] Sunucu başlatılamadı: {e}")

if __name__ == "__main__":
    # 1. Önce single instance kontrolü yapılıyor
    app_mutex = enforce_single_instance()
    
    # 2. Eğer buradan geçebildiyse demek ki çalışan başka instance yok, sunucuyu başlatıyoruz
    start_server(port=22)