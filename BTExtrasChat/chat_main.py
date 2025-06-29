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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import config_management, db_handler
from common.app_constants import CHAT_COMMAND_PORT
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
            print("INFO (Chat): Aplicație pornită cu utilizator pre-autentificat.")
        except Exception as e:
            print(f"EROARE (Chat): Nu s-au putut procesa datele utilizatorului: {e}")

    database = None
    temp_root = None
    
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()

        config = configparser.ConfigParser()
        db_credentials = config_management.read_db_config_from_parser(config)
        if not db_credentials:
            if os.path.exists(config_management.CONFIG_FILE):
                config.read(config_management.CONFIG_FILE, encoding='utf-8')
                db_credentials = config_management.read_db_config_from_parser(config)

        database = db_handler.DatabaseHandler(db_credentials=db_credentials, app_master_ref=temp_root)
        if not database.connect():
            dialog = db_handler.MariaDBConfigDialog(temp_root, initial_config=(db_credentials or {}))
            creds = dialog.result
            if creds and all(creds.values()):
                database.db_credentials = creds
                config_management.save_db_credentials(creds)
                if not database.connect(): raise ConnectionError("Eroare reconectare DB.")
            else: raise ConnectionError("Configurare DB anulată.")

        database.conn.autocommit = True
        
        user_data = pre_authenticated_user
        if not user_data:
            print("INFO (Chat): Se afișează dialogul de login.")
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
            app = ChatWindow(app_root, database, user_data, db_credentials)
            app_root.protocol("WM_DELETE_WINDOW", app.on_closing)
            if temp_root.winfo_exists():
                temp_root.destroy()
            app_root.mainloop()

    except (ConnectionError, PermissionError) as e:
        if 'temp_root' in locals() and temp_root.winfo_exists():
             messagebox.showerror("Eroare Pornire Chat", str(e), parent=temp_root)
        print(f"Pornire eșuată: {e}")
    except Exception as e:
        import traceback; traceback.print_exc()
        if 'temp_root' in locals() and temp_root.winfo_exists():
            messagebox.showerror("Eroare Critică Chat", f"Eroare neașteptată: {e}", parent=temp_root)
    finally:
        if 'temp_root' in locals() and temp_root.winfo_exists(): temp_root.destroy()
        if database and database.is_connected(): database.close_connection()

if __name__ == "__main__":
    main()