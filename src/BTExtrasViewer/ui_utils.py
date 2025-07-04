# ui_utils.py
import tkinter as tk
import logging
from tkinter import messagebox
from common import config_management

def handle_app_exit(app_instance, root_window):
    """
    Funcție centralizată pentru a gestiona ieșirea curată din aplicație,
    asigurând salvarea completă a configurației.
    """
    if messagebox.askokcancel("Confirmare Ieșire", "Sunteți sigur că doriți să închideți aplicația?"):
        window_settings_to_save = {}
        # Folosim parametrul `root_window` pentru a verifica starea ferestrei
        if root_window and root_window.winfo_exists():
            current_state = root_window.state()
            if current_state == 'zoomed':
                window_settings_to_save = {'state': 'zoomed'}
            elif current_state == 'normal':
                if hasattr(app_instance, 'last_normal_geometry') and app_instance.last_normal_geometry:
                    window_settings_to_save = {'state': 'normal'}
                    for key, value in app_instance.last_normal_geometry.items():
                        window_settings_to_save[key] = str(value)

        # Salvăm configurația, INCLUSIV detaliile ferestrei
        if window_settings_to_save:
            config_management.save_app_config(app_instance, window_details=window_settings_to_save)
        else:
            config_management.save_app_config(app_instance)

        # Închide conexiunea la DB
        if hasattr(app_instance, 'db_handler') and app_instance.db_handler:
            app_instance.db_handler.close_connection()

        # Închide fereastra principală și termină aplicația
        if root_window and root_window.winfo_exists():
            root_window.quit()
            root_window.destroy()