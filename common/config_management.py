# config_management.py
import os
import logging
import configparser
# Importăm constantele din același pachet 'common'
from .app_constants import APP_NAME, DEFAULT_TREEVIEW_DISPLAY_COLUMNS 

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

        if host and host.strip() and \
           name and name.strip() and \
           user and user.strip() and \
           port_str and port_str.strip():
            try:
                port = int(port_str.strip())
            except ValueError:
                port = 3306 # Port implicit
            # Se returnează dicționarul cu cheile standardizate
            db_credentials = {
                "host": host.strip(),
                "port": port,
                "database": name.strip(),
                "user": user.strip(),
                "password": password
            }
    return db_credentials

# --- NOU: Funcție pentru a citi configurația SMTP ---
def read_smtp_config_from_parser(config_parser_obj):
    """Citește configurația SMTP dintr-un obiect ConfigParser."""
    smtp_config = {}
    if config_parser_obj.has_section('SMTP'):
        smtp_config = {
            'server': config_parser_obj.get('SMTP', 'server', fallback=None),
            'port': config_parser_obj.getint('SMTP', 'port', fallback=None),
            'security': config_parser_obj.get('SMTP', 'security', fallback='SSL/TLS'),
            'sender_email': config_parser_obj.get('SMTP', 'sender_email', fallback=None),
            'user': config_parser_obj.get('SMTP', 'user', fallback=None),
            'password': config_parser_obj.get('SMTP', 'password', fallback=None),
        }
    return smtp_config
# ----------------------------------------------------

def read_column_widths_from_file():
    """Citește lățimile coloanelor direct din fișierul CONFIG_FILE."""
    config = configparser.ConfigParser()
    widths = {}
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding='utf-8')
            if config.has_section('ColumnWidths'):
                for col_id in DEFAULT_TREEVIEW_DISPLAY_COLUMNS:
                    width = config.getint('ColumnWidths', col_id, fallback=-1)
                    if width != -1:
                        widths[col_id] = width
        except Exception as e:
            logging.error(f"Eroare la citirea lățimilor coloanelor din config: {e}")
    return widths

def load_filters_from_parser(config_parser_obj):
    """Încarcă filtrele dintr-un obiect ConfigParser."""
    filters = {
        'date_range_mode': False, 'type': "Toate", 'search_term': "",
        'search_column': "Descriere", 'start_date': "", 'end_date': "",
        'nav_year': "", 'nav_month_idx': "0", 'nav_day': "0"
    }
    if config_parser_obj.has_section('Filters'):
        filters['date_range_mode'] = config_parser_obj.getboolean('Filters', 'date_range_mode', fallback=False)
        filters['type'] = config_parser_obj.get('Filters', 'type', fallback="Toate")
        filters['search_term'] = config_parser_obj.get('Filters', 'search_term', fallback="")
        filters['search_column'] = config_parser_obj.get('Filters', 'search_column', fallback="Toate coloanele")
        if filters['date_range_mode']:
            filters['start_date'] = config_parser_obj.get('Filters', 'start_date', fallback="")
            filters['end_date'] = config_parser_obj.get('Filters', 'end_date', fallback="")
        else: # Mod Navigare
            filters['nav_year'] = config_parser_obj.get('Filters', 'nav_year', fallback="")
            filters['nav_month_idx'] = config_parser_obj.get('Filters', 'nav_month_idx', fallback="0")
            filters['nav_day'] = config_parser_obj.get('Filters', 'nav_day', fallback="0")
    return filters

def save_app_config(app_instance, window_details=None):
    """
    NOUĂ VERSIUNE: Colectează toate setările și le salvează în baza de date
    pentru utilizatorul curent. Salvează local doar credențialele DB.
    """
    # Pasul 1: Salvează local doar credențialele de conectare la DB.
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
    
    if not config.has_section('Database'):
        config.add_section('Database')
    
    db_creds_to_save = {}
    if hasattr(app_instance, 'db_handler') and app_instance.db_handler and app_instance.db_handler.db_credentials:
        db_creds_to_save = app_instance.db_handler.db_credentials

    config.set('Database', 'db_host', db_creds_to_save.get('host', ''))
    config.set('Database', 'db_port', str(db_creds_to_save.get('port', 3306)))
    config.set('Database', 'db_name', db_creds_to_save.get('database', ''))
    config.set('Database', 'db_user', db_creds_to_save.get('user', ''))
    config.set('Database', 'db_password', db_creds_to_save.get('password', ''))

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except Exception as e:
        logging.error(f"Eroare la scrierea config.ini (doar DB creds): {e}")

    # Pasul 2: Colectează TOATE setările UI într-un dicționar Python.
    if not (app_instance.db_handler and app_instance.db_handler.is_connected()):
        return # Nu putem salva setările utilizatorului fără conexiune

    settings = {}

    # Setări Fereastră
    if window_details:
        settings['window'] = window_details

    # Setări SMTP
    if hasattr(app_instance, 'smtp_config') and app_instance.smtp_config:
        settings['smtp'] = app_instance.smtp_config

    # Setări Generale
    active_id_to_save = ""
    if hasattr(app_instance, 'active_account_id') and app_instance.active_account_id is not None:
        active_id_to_save = str(app_instance.active_account_id)
    settings['general'] = {'active_account_id': active_id_to_save}

    # Setări Filtre
    filters = {
        'date_range_mode': app_instance.date_range_mode_var.get(),
        'type': app_instance.type_var.get(),
        'search_term': app_instance.search_var.get(),
        'search_column': app_instance.search_column_var.get()
    }
    if filters['date_range_mode']:
        filters['start_date'] = app_instance.start_date.get_date().strftime('%Y-%m-%d') if hasattr(app_instance, 'start_date') and app_instance.start_date.winfo_exists() else ""
        filters['end_date'] = app_instance.end_date.get_date().strftime('%Y-%m-%d') if hasattr(app_instance, 'end_date') and app_instance.end_date.winfo_exists() else ""
    else:
        filters['nav_year'] = str(app_instance.nav_selected_year or "")
        filters['nav_month_idx'] = str(app_instance.nav_selected_month_index or 0)
        filters['nav_day'] = str(app_instance.nav_selected_day or 0)
    settings['filters'] = filters

    # Setări Lățime Coloane
    if hasattr(app_instance, 'tree') and app_instance.tree.winfo_exists():
        widths = {}
        for col_id in app_instance.treeview_display_columns:
            try:
                widths[col_id] = app_instance.tree.column(col_id, 'width')
            except Exception:
                pass
        settings['column_widths'] = widths

    # Pasul 3: Salvează dicționarul de setări în baza de date.
    app_instance.db_handler.save_user_settings(app_instance.current_user['id'], settings)

def load_window_config_from_file():
    """Încarcă configurația ferestrei din CONFIG_FILE."""
    config = configparser.ConfigParser()
    window_geom = None
    is_zoomed = True # Implicit, aplicația pornește maximizată
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding='utf-8')
            if config.has_section('Window') and config.get('Window', 'width', fallback=None):
                w = config.getint('Window', 'width', fallback=1200)
                h = config.getint('Window', 'height', fallback=700)
                x = config.getint('Window', 'x', fallback=None)
                y = config.getint('Window', 'y', fallback=None)
                if x is not None and y is not None: # Asigură-te că x și y sunt valide
                    window_geom = f"{w}x{h}+{x}+{y}"
                else:
                    window_geom = f"{w}x{h}"
                is_zoomed = False # Dacă avem geometrie salvată, nu e zoomed
        except Exception as e:
             logging.error(f"Eroare la citirea configurației ferestrei: {e}")
    return window_geom, is_zoomed

def load_transaction_type_visibility():
    """Încarcă vizibilitatea tipurilor de tranzacții din config.ini."""
    config = configparser.ConfigParser()
    visibility_settings = {}
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding='utf-8')
            if config.has_section('TransactionTypeVisibility'):
                for key, value in config.items('TransactionTypeVisibility'):
                    # CORECȚIE: Salvăm cheia în dicționar așa cum este citită (cu litere mici)
                    # Am eliminat conversia .upper() care cauza problema.
                    visibility_settings[key] = config.getboolean('TransactionTypeVisibility', key)
        except Exception as e:
            logging.error(f"Eroare la citirea setărilor de vizibilitate din config: {e}")
    return visibility_settings

def save_transaction_type_visibility(visibility_dict):
    """Salvează vizibilitatea tipurilor de tranzacții în config.ini."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')

    if not config.has_section('TransactionTypeVisibility'):
        config.add_section('TransactionTypeVisibility')

    for code, is_visible in visibility_dict.items():
        config.set('TransactionTypeVisibility', code, str(is_visible))

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except Exception as e:
        logging.error(f"Eroare la scrierea config.ini: {e}")