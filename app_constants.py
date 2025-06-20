# app_constants.py
import locale
import calendar
import logging
from datetime import datetime

APP_NAME = "BTExtrasViewer"
APP_VERSION = " 4.0"

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
        # For Python versions where calendar.month_name might not be localized correctly by setlocale
        # or if strftime %B is not behaving as expected.
        # This provides a basic English fallback if Romanian names fail.
        # A more robust solution might involve a predefined dictionary for Romanian month names.
        import calendar
        month_name_en = calendar.month_name[i]
        if month_name_en: # Ensure it's not an empty string for index 0
             MONTH_MAP_FOR_NAV[month_name_en.capitalize()] = i

REVERSE_MONTH_MAP_FOR_NAV = {v: k for k, v in MONTH_MAP_FOR_NAV.items()}

# Adaugă aici și alte constante dacă identificăm ulterior
# De exemplu, SQL-ul pentru structura DB va merge în db_handler.py

APP_COPYRIGHT = f"© {datetime.now().year} Regio Development. Toate drepturile rezervate."