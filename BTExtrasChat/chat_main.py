# BTExtrasChat/chat_main.py

import os
import tkinter as tk
from tkinter import messagebox
import sys
import logging

# Adăugăm directorul rădăcină în calea Python pentru a găsi pachetul 'common'
# Acest lucru este necesar pentru a rula scriptul direct în timpul dezvoltării
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Importăm modulele din directorul comun
from common import config_management, db_handler
from BTExtrasViewer.ui_dialogs import LoginDialog # Temporar, folosim dialogul existent
from .chat_ui import ChatWindow # Am adăugat '.' pentru a face importul relativ

def main():
    """Funcția principală pentru pornirea aplicației de chat."""
    db_credentials = None
    try:
        # 1. Citirea configurației DB
        if os.path.exists(config_management.CONFIG_FILE):
            config = config_management.configparser.ConfigParser()
            config.read(config_management.CONFIG_FILE, encoding='utf-8')
            db_credentials = config_management.read_db_config_from_parser(config)
        else:
            messagebox.showerror("Configurare Lipsă", "Fișierul config.ini nu a fost găsit. Rulați mai întâi aplicația principală.")
            return

        # 2. Conectare la DB și verificare schemă 
        database = db_handler.DatabaseHandler(db_credentials=db_credentials)
        if not database.connect():
            messagebox.showerror("Eroare Critică", "Nu s-a putut inițializa conexiunea cu baza de date.")
            return

        # --- MODIFICARE CHEIE: Activăm autocommit PENTRU aplicația de chat ---
        database.conn.autocommit = True
        print("INFO: Conexiunea la DB pentru chat a fost setată pe autocommit=True.")
        
        # Asigură-te că tabelele de chat există
        database.check_and_setup_database_schema()

        # 3. Autentificare utilizator (folosind același LoginDialog) 
        temp_root_for_login = tk.Tk()
        temp_root_for_login.withdraw()
        login_dialog = LoginDialog(temp_root_for_login, database)
        user_data = login_dialog.result
        temp_root_for_login.destroy()

        if not user_data:
            print("Autentificare anulată. Aplicația se va închide.")
            return

        # 4. Lansarea ferestrei principale de chat 
        root = tk.Tk()
        # Pasăm și datele de conectare la DB (db_credentials)
        app = ChatWindow(root, database, user_data, db_credentials)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()

    except Exception as e:
        messagebox.showerror("Eroare Neprevăzută", f"A apărut o eroare la pornirea aplicației de chat: {e}")
        logging.error("Eroare critică la pornirea Chat", exc_info=True)

if __name__ == "__main__":
    main()