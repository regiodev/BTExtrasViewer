# session_manager.py
import os
import sys
import socket
import subprocess
import threading
import json
import base64
from PIL import Image
import pystray
import keyboard

# Adăugăm calea rădăcină
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from common.app_constants import (
    GLOBAL_HOTKEY_CHAT, CHAT_COMMAND_PORT, 
    VIEWER_COMMAND_PORT, GLOBAL_HOTKEY_VIEWER,
    SESSION_COMMAND_PORT
)

class SessionManager:
    def __init__(self):
        self.tray_icon = None
        # Vom stoca PID-urile, nu obiectele Popen
        self.chat_pid = None
        self.viewer_pid = None
        self.current_session_user = None

        hotkey_thread = threading.Thread(target=self._listen_for_hotkey, daemon=True)
        hotkey_thread.start()
        
        session_thread = threading.Thread(target=self._listen_for_session_commands, daemon=True)
        session_thread.start()

    def run(self):
        print("INFO: Managerul de Sesiune a pornit. Se creează iconița în tray.")
        self._create_and_run_tray_icon()

    def _create_and_run_tray_icon(self):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        image_path = os.path.join(base_path, "assets", "BT_logo.ico")
        
        try:
            image = Image.open(image_path)
        except FileNotFoundError:
            image = Image.new('RGB', (64, 64), color='red')

        menu = (
            pystray.MenuItem('Deschide BTExtrasViewer', self._handle_show_viewer),
            pystray.MenuItem('Deschide Chat', self._handle_show_chat),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Ieșire', self.quit_all)
        )
        self.tray_icon = pystray.Icon("SessionManager", image, "BTExtras Suite", menu)
        self.tray_icon.run()

    def _listen_for_hotkey(self):
        try:
            keyboard.add_hotkey(GLOBAL_HOTKEY_CHAT, self._handle_show_chat)
            keyboard.add_hotkey(GLOBAL_HOTKEY_VIEWER, self._handle_show_viewer)
            keyboard.wait()
        except Exception as e:
            print(f"EROARE la înregistrarea hotkey-ului: {e}")

    def _listen_for_session_commands(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('127.0.0.1', SESSION_COMMAND_PORT))
                server_socket.listen()
                print(f"INFO (SM): Serverul de comenzi de sesiune ascultă pe portul {SESSION_COMMAND_PORT}.")
                while True:
                    conn, addr = server_socket.accept()
                    with conn:
                        data_bytes = conn.recv(4096)
                        if data_bytes:
                            command, *payload = data_bytes.decode('utf-8').split(' ', 1)
                            if command == 'SET_USER' and payload:
                                self.current_session_user = json.loads(payload[0])
                                print(f"INFO (SM): Sesiune setată pentru: {self.current_session_user.get('username')}")
        except Exception as e:
            print(f"EROARE CRITICĂ: Serverul de comenzi de sesiune NU a putut porni: {e}")

    def _handle_show_chat(self):
        print("INFO: Comandă primită pentru Chat.")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                s.connect(('127.0.0.1', CHAT_COMMAND_PORT))
                s.sendall(b'SHOW_WINDOW')
            print("INFO (SM): Chat-ul rulează. Comanda SHOW a fost trimisă.")
        except (ConnectionRefusedError, socket.timeout):
            print("INFO (SM): Chat-ul nu rulează. Se lansează.")
            self._launch_app('chat')

    def _handle_show_viewer(self):
        print("INFO: Comandă primită pentru Viewer.")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                s.connect(('127.0.0.1', VIEWER_COMMAND_PORT))
                s.sendall(b'SHOW_WINDOW')
            print("INFO (SM): Viewer-ul rulează. Comanda SHOW a fost trimisă.")
        except (ConnectionRefusedError, socket.timeout):
            print("INFO (SM): Viewer-ul nu rulează. Se lansează.")
            self._launch_app('viewer')

    def _launch_app(self, app_type):
        try:
            is_frozen = getattr(sys, 'frozen', False)
            flags = 0
            if os.name == 'nt':
                flags = subprocess.DETACHED_PROCESS

            command = []
            if app_type == 'chat':
                if is_frozen:
                    app_path = os.path.join(os.path.dirname(sys.executable), 'BTExtrasChat', 'BTExtrasChat.exe')
                    command = [app_path]
                else:
                    command = [sys.executable, '-m', 'BTExtrasChat.chat_main']
                
                if self.current_session_user:
                    user_data_json = json.dumps(self.current_session_user)
                    user_data_b64 = base64.b64encode(user_data_json.encode('utf-8')).decode('utf-8')
                    command.append(f'--user-data={user_data_b64}')
                
                process = subprocess.Popen(command, creationflags=flags)
                self.chat_pid = process.pid # Stocăm PID-ul
                print(f"INFO: Chat lansat cu PID: {self.chat_pid}")

            elif app_type == 'viewer':
                if is_frozen:
                    app_path = os.path.join(os.path.dirname(sys.executable), 'BTExtrasViewer', 'btextrasviewer.exe')
                    command = [app_path]
                else:
                    command = [sys.executable, '-m', 'BTExtrasViewer.btextrasviewer_main']
                
                process = subprocess.Popen(command, creationflags=flags)
                self.viewer_pid = process.pid # Stocăm PID-ul
                print(f"INFO: Viewer lansat cu PID: {self.viewer_pid}")

        except Exception as e:
            print(f"EROARE la lansarea '{app_type}': {e}")

    def quit_all(self, icon=None, item=None):
        print("INFO: Se inițiază procedura de închidere...")
        
        # Folosim PID-urile stocate pentru a ucide procesele
        pids_to_kill = {'Chat': self.chat_pid, 'Viewer': self.viewer_pid}
        for name, pid in pids_to_kill.items():
            if pid:
                try:
                    print(f"INFO: Se încearcă terminarea procesului {name} (PID: {pid})...")
                    if os.name == 'nt':
                        os.system(f"taskkill /F /PID {pid}")
                    else:
                        os.kill(pid, 9) # SIGKILL
                    print(f"INFO: Comanda de terminare pentru {name} a fost trimisă.")
                except Exception as e:
                    print(f"AVERTISMENT: Nu s-a putut termina procesul {name}: {e}")
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        keyboard.unhook_all()
        print("INFO: Session Manager s-a închis complet.")
        sys.exit(0)

if __name__ == '__main__':
    # Logica pentru single-instance a Session Manager-ului însuși
    try:
        lock_socket = socket.socket()
        lock_socket.bind(("127.0.0.1", 54321)) # Port arbitrar pentru lock
        manager = SessionManager()
        manager.run()
    except OSError:
        print("EROARE: O instanță a Session Manager rulează deja.")
        sys.exit(1)