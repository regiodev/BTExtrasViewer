# BTExtrasChat/chat_main.py
import os
import sys
import socket
import argparse
import json
import base64
import tkinter as tk
from tkinter import messagebox
import configparser
import threading

# Linii CORECTATE și standardizate
from common import config_management
from common import db_handler
from common.app_constants import CHAT_COMMAND_PORT, CHAT_LOCK_PORT
from BTExtrasViewer.ui_dialogs import LoginDialog, ForcePasswordChangeDialog
from BTExtrasChat.chat_ui import ChatWindow

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user-data', type=str, help='Datele utilizatorului în format Base64 JSON.')
    args = parser.parse_args()
    
    pre_authenticated_user = None
    if args.user_data:
        try:
            user_data_json = base64.b64decode(args.user_data).decode('utf-8')
            pre_authenticated_user = json.loads(user_data_json)
        except Exception as e:
            print(f"EROARE (Chat): Nu s-au putut procesa datele utilizatorului: {e}")

    database = None
    temp_root = None
    
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()

        config = configparser.ConfigParser()
        if os.path.exists(config_management.CONFIG_FILE):
            config.read(config_management.CONFIG_FILE, encoding='utf-8')
        
        db_credentials = config_management.read_db_config_from_parser(config)
        database = db_handler.DatabaseHandler(db_credentials=db_credentials, app_master_ref=temp_root)

        if not database.is_connected() and not database.connect():
            dialog = db_handler.MariaDBConfigDialog(temp_root, initial_config=(db_credentials or {}))
            creds = dialog.result
            if creds and all(creds.values()):
                config_management.save_db_credentials(creds)
                database.db_credentials = creds
                if not database.connect():
                    raise ConnectionError("Eroare reconectare DB.")
            else:
                raise ConnectionError("Configurare DB anulată.")

        if not database.check_and_setup_database_schema():
            raise SystemError("Schema bazei de date nu a putut fi creată sau verificată.")

        # === AICI ESTE CORECȚIA CRITICĂ ===
        # Am înlocuit atribuirea cu un apel de funcție.
        database.conn.autocommit(True)
        # === SFÂRȘIT CORECȚIE ===
        
        user_data = pre_authenticated_user
        if not user_data:
            while True:
                login_dialog = LoginDialog(temp_root, database)
                user_data = login_dialog.result
                if not user_data: raise PermissionError("Autentificare anulată.")
                if user_data.get('force_password_change') in [True, 1]:
                    messagebox.showinfo("Schimbare Parolă", "Schimbați parola inițială.", parent=temp_root)
                    change_dialog = ForcePasswordChangeDialog(temp_root, database, user_data['id'], user_data['username'])
                    if change_dialog.result: continue 
                    else: raise PermissionError("Schimbare parolă anulată.")
                break

        if user_data:
            app_root = tk.Tk()
            app = ChatWindow(app_root, database, user_data, database.db_credentials)
            app_root.protocol("WM_DELETE_WINDOW", app.on_closing)
            if temp_root.winfo_exists(): temp_root.destroy()
            app_root.mainloop()

    except (ConnectionError, SystemError, PermissionError) as e:
        if 'temp_root' in locals() and temp_root.winfo_exists():
             messagebox.showerror("Eroare Pornire Chat", str(e), parent=temp_root)
        print(f"Pornire eșuată: {e}")
    except Exception as e:
        import traceback; traceback.print_exc()
        if 'temp_root' in locals() and temp_root.winfo_exists():
            messagebox.showerror("Eroare Critică Chat", f"Eroare neașteptată: {e}", parent=temp_root)
    finally:
        if database and database.is_connected():
            database.close_connection()

if __name__ == "__main__":
    try:
        # Încercăm să creăm un "lacăt" pe un port specific pentru Chat
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(("127.0.0.1", CHAT_LOCK_PORT))

        # Dacă am reușit, suntem prima instanță. Rulăm logica normală.
        main() # Am încapsulat logica originală într-o funcție main()

    except OSError:
        # Dacă bind() a eșuat, o altă instanță rulează. O notificăm.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', CHAT_COMMAND_PORT))
                s.sendall(b'SHOW_WINDOW')
        except ConnectionRefusedError:
            pass
        finally:
            sys.exit(0)