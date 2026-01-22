# app_constants.py
import locale
import calendar
import logging
from datetime import datetime

APP_NAME = "BTExtrasViewer"
APP_VERSION = "4.7.5"

# Locale setting
try:
    locale.setlocale(locale.LC_TIME, 'ro_RO.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Romanian_Romania.1250')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'ro_RO')
        except locale.Error:
            logging.warning("Atenție: Nu s-a putut seta localizarea în română pentru formatarea datelor.")

DEFAULT_TREEVIEW_DISPLAY_COLUMNS = ("data", "descriere", "observatii", "suma", "tip", "cif", "factura", "beneficiar")

MONTH_MAP_FOR_NAV = {}
for i in range(1, 13):
    try:
        month_name = datetime(2000, i, 1).strftime('%B').capitalize()
        MONTH_MAP_FOR_NAV[month_name] = i
    except ValueError: # Fallback for some systems
        import calendar
        month_name_en = calendar.month_name[i]
        if month_name_en:
             MONTH_MAP_FOR_NAV[month_name_en.capitalize()] = i

REVERSE_MONTH_MAP_FOR_NAV = {v: k for k, v in MONTH_MAP_FOR_NAV.items()}

APP_COPYRIGHT = f"© {datetime.now().year} Regio Development. Toate drepturile rezervate."

# Constante pentru comunicare inter-proces
SESSION_COMMAND_PORT = 12343
VIEWER_COMMAND_PORT = 12344
CHAT_COMMAND_PORT = 12345

# Constante pentru combinațiile de taste globale
GLOBAL_HOTKEY_CHAT = 'ctrl+alt+c'
GLOBAL_HOTKEY_VIEWER = 'ctrl+alt+b'

# Porturi arbitrare pentru blocarea de instanță unică
SESSION_MANAGER_LOCK_PORT = 54321
VIEWER_LOCK_PORT = 54322
CHAT_LOCK_PORT = 54323