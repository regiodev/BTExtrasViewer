# ui_utils.py
import tkinter as tk
import logging
# Modulul de configurare este importat din 'common'
from common.config_management import save_app_config

def handle_app_exit(app_instance, root_window):
    """
    Gestionează acțiunile la închiderea aplicației: salvează configurația,
    închide conexiunea DB și distruge fereastra principală.
    """
    window_details = {}
    if root_window.winfo_exists():
        # Salvăm starea ferestrei (dimensiuni, poziție) doar dacă nu este maximizată
        if root_window.state() == 'normal':
            try:
                window_details = {
                    'width': str(root_window.winfo_width()),
                    'height': str(root_window.winfo_height()),
                    'x': str(root_window.winfo_x()),
                    'y': str(root_window.winfo_y())
                }
            except tk.TclError:
                # Fereastra ar putea fi distrusă între timp
                pass
    
    # Salvează configurația aplicației (inclusiv lățimea coloanelor, filtrele, etc.)
    # Condiția 'if' a fost eliminată pentru a asigura salvarea necondiționată la ieșire.
    save_app_config(app_instance, window_details=window_details)

    # Închide conexiunea la baza de date, dacă există una activă
    if hasattr(app_instance, 'db_handler') and app_instance.db_handler:
        app_instance.db_handler.close_connection()
    elif hasattr(app_instance, 'conn') and app_instance.conn and app_instance.conn.is_connected():
        try:
            app_instance.conn.close()
        except Exception as e_conn_close:
            logging.error(f"Eroare la închiderea conexiunii DB (fallback la ieșire): {e_conn_close}")
            
    # Distruge fereastra principală a aplicației
    if root_window.winfo_exists():
        try:
            root_window.destroy()
        except tk.TclError:
            # Fereastra este deja pe cale de a fi distrusă
            pass