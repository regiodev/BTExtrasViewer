# config_management.py
import os
import logging
import configparser
from app_constants import APP_NAME, DEFAULT_TREEVIEW_DISPLAY_COLUMNS # Importăm din modulul nostru

if os.name == 'nt':
    APP_DATA_DIR = os.path.join(os.getenv('LOCALAPPDATA'), APP_NAME)
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)

if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.ini')

def read_db_config_from_parser(config_parser_obj):
    """Citește configurația DB dintr-un obiect ConfigParser deja încărcat."""
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
            db_credentials = {
                "db_host": host.strip(),
                "db_port": port,
                "db_name": name.strip(),
                "db_user": user.strip(),
                "db_password": password
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
    """Salvează configurația aplicației în CONFIG_FILE."""
    config = configparser.ConfigParser()
    # Este o practică bună să citești întâi fișierul existent pentru a păstra secțiuni neatinse
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding='utf-8')
        except Exception as e:
            logging.warning(f"Atenție: Nu s-a putut citi config.ini existent la salvare: {e}")

    if not config.has_section('Database'): config.add_section('Database')
    config.set('Database', 'db_host', app_instance.db_host or "")
    config.set('Database', 'db_port', str(app_instance.db_port or 3306))
    config.set('Database', 'db_name', app_instance.db_name or "")
    config.set('Database', 'db_user', app_instance.db_user or "")
    config.set('Database', 'db_password', app_instance.db_password or "") # Parola se salvează
    if hasattr(app_instance, 'smtp_config') and app_instance.smtp_config:
        if not config.has_section('SMTP'):
            config.add_section('SMTP')
        
        config.set('SMTP', 'server', app_instance.smtp_config.get('server', ''))
        config.set('SMTP', 'port', str(app_instance.smtp_config.get('port', '')))
        config.set('SMTP', 'security', app_instance.smtp_config.get('security', 'SSL/TLS'))
        config.set('SMTP', 'sender_email', app_instance.smtp_config.get('sender_email', ''))
        config.set('SMTP', 'user', app_instance.smtp_config.get('user', ''))
        config.set('SMTP', 'password', app_instance.smtp_config.get('password', ''))
    
    if not config.has_section('General'):
        config.add_section('General')
    
    # Preluăm active_account_id direct din atributul instanței aplicației
    active_id_to_save = "" # Valoare default dacă app_instance nu are atributul sau e None
    if hasattr(app_instance, 'active_account_id') and app_instance.active_account_id is not None:
        active_id_to_save = str(app_instance.active_account_id)
    config.set('General', 'active_account_id', active_id_to_save)

    if not config.has_section('Filters'): config.add_section('Filters')
    config.set('Filters', 'date_range_mode', str(app_instance.date_range_mode_var.get()))
    
    start_date_val = None
    if hasattr(app_instance, 'start_date') and app_instance.start_date.winfo_exists() and app_instance.start_date.get():
        start_date_val = app_instance.start_date.get_date()
    
    end_date_val = None
    if hasattr(app_instance, 'end_date') and app_instance.end_date.winfo_exists() and app_instance.end_date.get():
        end_date_val = app_instance.end_date.get_date()

    if app_instance.date_range_mode_var.get():
        config.set('Filters', 'start_date', start_date_val.strftime('%Y-%m-%d') if start_date_val else "")
        config.set('Filters', 'end_date', end_date_val.strftime('%Y-%m-%d') if end_date_val else "")
        config.set('Filters', 'nav_year', "")
        config.set('Filters', 'nav_month_idx', "0")
        config.set('Filters', 'nav_day', "0")
    else: # Mod Navigare
        config.set('Filters', 'start_date', "")
        config.set('Filters', 'end_date', "")
        config.set('Filters', 'nav_year', str(app_instance.nav_selected_year or ""))
        config.set('Filters', 'nav_month_idx', str(app_instance.nav_selected_month_index or 0))
        config.set('Filters', 'nav_day', str(app_instance.nav_selected_day or 0))

    config.set('Filters', 'type', app_instance.type_var.get())
    config.set('Filters', 'search_term', app_instance.search_var.get())
    config.set('Filters', 'search_column', app_instance.search_column_var.get())

    if hasattr(app_instance, 'tree') and app_instance.tree.winfo_exists():
        if not config.has_section('ColumnWidths'): config.add_section('ColumnWidths')
        # Folosim treeview_display_columns din instanța aplicației, nu constanta,
        # în caz că se va permite personalizarea coloanelor afișate în viitor.
        for col_id in app_instance.treeview_display_columns:
            try:
                config.set('ColumnWidths', col_id, str(app_instance.tree.column(col_id, 'width')))
            except Exception: # tk.TclError e specific, dar prindem mai larg
                pass # Ignoră erorile la salvarea lățimii unei coloane (ex: widget distrus)
    
    if window_details:
        if not config.has_section('Window'): config.add_section('Window')
        for k, v_val in window_details.items(): # Am redenumit v în v_val pentru a evita conflictul
            config.set('Window', k, v_val)
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except Exception as e:
        logging.error(f"Eroare la scrierea config.ini: {e}")

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