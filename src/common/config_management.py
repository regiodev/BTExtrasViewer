# common/config_management.py - VERSIUNE CORECTATĂ

import os
import logging
import configparser
from .app_constants import APP_NAME

if os.name == 'nt':
    APP_DATA_DIR = os.path.join(os.getenv('LOCALAPPDATA'), APP_NAME)
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)

if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.ini')

def read_db_config_from_parser(config_parser_obj):
    """Citește configurația DB și o returnează cu chei standardizate."""
    db_credentials = None
    if config_parser_obj.has_section('Database'):
        host = config_parser_obj.get('Database', 'db_host', fallback=None)
        port_str = config_parser_obj.get('Database', 'db_port', fallback=None)
        name = config_parser_obj.get('Database', 'db_name', fallback=None)
        user = config_parser_obj.get('Database', 'db_user', fallback=None)
        password = config_parser_obj.get('Database', 'db_password', fallback="")

        if host and host.strip() and name and name.strip() and user and user.strip() and port_str and port_str.strip():
            try:
                port = int(port_str.strip())
            except ValueError:
                port = 3306
            
            db_credentials = {
                "host": host.strip(), "port": port, "database": name.strip(),
                "user": user.strip(), "password": password
            }
    return db_credentials

def save_db_credentials(db_creds_to_save):
    """Salvează DOAR credențialele DB în fișierul de configurare local."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')

    if not config.has_section('Database'):
        config.add_section('Database')

    config.set('Database', 'db_host', db_creds_to_save.get('host', ''))
    config.set('Database', 'db_port', str(db_creds_to_save.get('port', 3306)))
    config.set('Database', 'db_name', db_creds_to_save.get('database', ''))
    config.set('Database', 'db_user', db_creds_to_save.get('user', ''))
    config.set('Database', 'db_password', db_creds_to_save.get('password', ''))

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return True
    except Exception as e:
        logging.error(f"Eroare la scrierea config.ini (doar DB creds): {e}")
        return False

def save_app_config(app_instance, window_details=None):
    """
    Colectează toate setările și le salvează în baza de date
    pentru utilizatorul curent. Salvează local doar credențialele DB.
    """
    # Pasul 1: Salvează local credențialele de conectare la DB.
    db_creds_to_save = {}
    if hasattr(app_instance, 'db_handler') and app_instance.db_handler and app_instance.db_handler.db_credentials:
        db_creds_to_save = app_instance.db_handler.db_credentials
    save_db_credentials(db_creds_to_save)

    # Pasul 2: Colectează TOATE setările UI într-un dicționar Python.
    if not (hasattr(app_instance, 'current_user') and app_instance.current_user and 
            app_instance.db_handler and app_instance.db_handler.is_connected()):
        return

    settings = app_instance.user_settings if hasattr(app_instance, 'user_settings') else {}

    if window_details: settings['window'] = window_details
    if hasattr(app_instance, 'smtp_config') and app_instance.smtp_config: settings['smtp'] = app_instance.smtp_config

    if 'general' not in settings: settings['general'] = {}
    if hasattr(app_instance, 'active_account_id') and app_instance.active_account_id is not None:
        settings['general']['active_account_id'] = str(app_instance.active_account_id)

    filters = {
        'date_range_mode': app_instance.date_range_mode_var.get(),
        'type': app_instance.type_var.get(),
        'search_term': app_instance.search_var.get(),
        'search_column': app_instance.search_column_var.get()
    }
    if hasattr(app_instance, 'start_date') and app_instance.start_date.winfo_exists():
        if filters['date_range_mode']:
            filters['start_date'] = app_instance.start_date.get_date().strftime('%Y-%m-%d')
            filters['end_date'] = app_instance.end_date.get_date().strftime('%Y-%m-%d')
        else:
            filters['nav_year'] = str(app_instance.nav_selected_year or "")
            filters['nav_month_idx'] = str(app_instance.nav_selected_month_index or 0)
            filters['nav_day'] = str(app_instance.nav_selected_day or 0)
    settings['filters'] = filters

    if hasattr(app_instance, 'tree') and app_instance.tree.winfo_exists():
        widths = {col_id: app_instance.tree.column(col_id, 'width') for col_id in app_instance.treeview_display_columns}
        settings['column_widths'] = widths

    # Pasul 3: Salvează dicționarul de setări în baza de date.
    app_instance.db_handler.save_user_settings(app_instance.current_user['id'], settings)