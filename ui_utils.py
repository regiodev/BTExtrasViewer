# ui_utils.py
import tkinter as tk # Necesar dacă vom adăuga alte funcții UI aici
import logging
# Importăm save_app_config direct din config_management
from config_management import save_app_config

def handle_app_exit(app_instance, root_window):
    """Gestionează acțiunile la închiderea aplicației."""
    # --- Copiază aici conținutul funcției save_window_state_on_exit ---
    # Adaptează pentru a folosi app_instance și save_app_config
    window_details = {}
    if root_window.winfo_exists(): # Verifică dacă fereastra încă există
        if root_window.state() == 'normal':
            try:
                window_details = {
                    'width': str(root_window.winfo_width()),
                    'height': str(root_window.winfo_height()),
                    'x': str(root_window.winfo_x()),
                    'y': str(root_window.winfo_y())
                }
            except tk.TclError: # Poate apărea dacă fereastra e distrusă între timp
                pass 
    
    # Salvează configurația aplicației (inclusiv detaliile ferestrei)
    # Asigură-te că app_instance.save_config (care va fi save_app_config) este corect apelat
    if hasattr(app_instance, 'db_host'): # Verifică dacă atributele necesare pentru salvare există
        save_app_config(app_instance, window_details=window_details)

    # Închide conexiunea la DB dacă există și e gestionată de app_instance.db_handler
    if hasattr(app_instance, 'db_handler') and app_instance.db_handler:
        app_instance.db_handler.close_connection()
    # Fallback pentru cazul în care db_handler nu e implementat complet, dar conn există (mai puțin probabil după refactorizare)
    elif hasattr(app_instance, 'conn') and app_instance.conn and app_instance.conn.is_connected():
        try:
            app_instance.conn.close()
        except Exception as e_conn_close:
            logging.error(f"Eroare la închiderea conexiunii DB (fallback la ieșire): {e_conn_close}")
            
    if root_window.winfo_exists():
        try:
            root_window.destroy()
        except tk.TclError:
            pass # Fereastra e deja pe cale de a fi distrusă