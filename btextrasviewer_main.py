# btextrasviewer_main.py
import os
import logging
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog, scrolledtext
from datetime import datetime, date
import calendar
from tkcalendar import DateEntry
from ui_reports import CashFlowReportDialog, BalanceEvolutionReportDialog, TransactionAnalysisReportDialog
from config_management import (
    read_smtp_config_from_parser,
    APP_DATA_DIR # Adăugați acest element
)
import re 
from queue import Queue, Empty 
import threading

# Importurile din modulele noastre
from app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, DEFAULT_TREEVIEW_DISPLAY_COLUMNS, MONTH_MAP_FOR_NAV, REVERSE_MONTH_MAP_FOR_NAV
import config_management
from db_handler import DatabaseHandler, MariaDBConfigDialog
import file_processing 
from file_processing import extract_iban_from_mt940, threaded_import_worker, threaded_export_worker
import ui_utils
from ui_dialogs import AccountManagerDialog, AccountEditDialog, TransactionTypeManagerDialog, SMTPConfigDialog, BalanceReportConfigDialog

class BTViewerApp:
    def _load_visible_transaction_types(self):
        """Încarcă din config.ini codurile de tranzacții vizibile."""
        if not (self.db_handler and self.db_handler.is_connected()):
            self.visible_tx_codes = []
            return

        # Încarcă setările salvate din config.ini
        visibility_settings = config_management.load_transaction_type_visibility()

        # Preia TOATE tipurile de tranzacții posibile din DB
        all_types = self.db_handler.fetch_all_dict("SELECT cod FROM tipuri_tranzactii")
        if not all_types:
            self.visible_tx_codes = []
            return

        all_codes = [item['cod'] for item in all_types]

        visible_codes = []
        for code in all_codes:
            # Dacă un cod nu are o setare în fișier (e nou), îl considerăm vizibil implicit.
            # Altfel, folosim setarea din fișier.
            if visibility_settings.get(code, True): # Implicit True
                visible_codes.append(code)

        self.visible_tx_codes = visible_codes

    def __init__(self, master):
        self.visible_tx_codes = [] # NOU: Va stoca codurile vizibile
        self._programmatic_change = False # NOU: Flag pentru a preveni buclele de evenimente
        self.master = master
        self.master.title(f"{APP_NAME} - Se inițializează...")
        
        # Atribute pentru gestionarea importului pe loturi
        self.import_batch_queue = [] 
        self.current_batch_info_for_message = None
        self.file_paths_for_import_ref = [] 
        
       # ADAUGARE: Atribut pentru configurarea SMTP
        self.smtp_config = {}

        # Flag-uri de stare internă
        self._applying_nav_selection = False
        self._prevent_on_account_selected_trigger = False
        
        # Detalii conexiune DB
        self.db_host, self.db_port, self.db_name, self.db_user, self.db_password = None, None, None, None, None
        self.db_handler = None
        self.migration_needed_for_existing_transactions = False

        # Detalii cont activ și lista de conturi
        self.active_account_id = None
        self.accounts_list = [] 
        self.account_combo_var = tk.StringVar()

        # Setări pentru sortare și căutare
        self.sort_column = 'data'
        self.sort_direction = 'DESC'
        self.total_transaction_count = 0
        self.search_job = None
        
        # Hărți pentru lunile anului (navigare)
        self.month_map_for_nav = MONTH_MAP_FOR_NAV
        self.reverse_month_map_for_nav = REVERSE_MONTH_MAP_FOR_NAV
        
        # Variabile Tkinter pentru filtre
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar(value="Toate coloanele")
        self.type_var = tk.StringVar(value="Toate")
        self.date_range_mode_var = tk.BooleanVar(value=False)
        
        # Atribute pentru starea navigației
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        self._nav_select_job, self._current_processed_nav_iid = None, None
        
        # Configurare Treeview principal
        self.treeview_display_columns = DEFAULT_TREEVIEW_DISPLAY_COLUMNS
        self.loaded_column_widths = config_management.read_column_widths_from_file()

        # Atribute pentru fereastra de progres și comunicare cu thread-urile
        self.current_progress_win = None
        self.current_progress_bar = None
        self.current_progress_status_label_widget = None
        self.queue = Queue() 
        self.import_thread = None 
        self.export_thread = None 
        
        self.config = None # Obiectul ConfigParser încărcat
        
        # Atribute UI care trebuie referențiate ulterior
        self.status_label = None
        self.account_selector_combo = None
        self.active_account_color_indicator = None
        self.date_range_checkbox = None
        self.start_date = None
        self.end_date = None
        self.type_combo = None
        self.search_entry = None
        self.search_column_combo = None
        self.reset_button = None
        self.export_button = None
        self.import_button = None
        self.action_buttons = []
        self.nav_tree = None
        self.tree = None

        # Construiește interfața grafică
        self.setup_ui()
        logging.debug("DEBUG_INIT: __init__ - UI setup complet. Se programează init_step1_read_config.")
        
        # Începe secvența de inițializare a datelor și conexiunii
        self.master.after(10, self.init_step1_read_config)

    def configure_smtp(self):
        dialog = SMTPConfigDialog(self.master, initial_config=self.smtp_config)
        if dialog.result:
            self.smtp_config = dialog.result
            save_app_config(self)
            messagebox.showinfo("Configurare SMTP", "Setările SMTP au fost salvate.", parent=self.master)

    def manage_transaction_types(self):
        """Deschide dialogul pentru gestionarea tipurilor de tranzacții."""
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Trebuie să fiți conectat la baza de date.", parent=self.master)
            return

        dialog = TransactionTypeManagerDialog(self.master, self.db_handler)
        # După ce fereastra este închisă, reîncărcăm setările și reîmprospătăm totul
        self._load_visible_transaction_types()
        self.refresh_ui_for_account_change()
       
    def show_cash_flow_report(self):
        """Deschide fereastra de dialog pentru raport, pasând contextul curent."""
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date pentru a genera rapoarte.", parent=self.master)
            return
        
        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

        # 1. Adună contextul filtrelor curente din interfața principală
        start_date, end_date = None, None

        if self.date_range_mode_var.get():
            # Mod "Interval Dată": citim direct din widget-uri (care sunt active)
            logging.debug("DEBUG_REPORT_CTX: Preluare context din mod Interval Dată.")
            try:
                if hasattr(self, 'start_date') and self.start_date.get():
                    start_date = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.get():
                    end_date = self.end_date.get_date()
            except Exception as e_get_date:
                 logging.warning(f"Atenție: Nu s-au putut prelua datele din DateEntry: {e_get_date}")
        else:
            # Mod "Navigare": calculăm intervalul pe baza selecției din arbore
            logging.debug("DEBUG_REPORT_CTX: Preluare context din mod Navigare.")
            if self.nav_selected_year:
                current_year = self.nav_selected_year
                current_month = self.nav_selected_month_index
                current_day = self.nav_selected_day
                
                if current_month == 0: # S-a selectat un an întreg
                    start_date = date(current_year, 1, 1)
                    end_date = date(current_year, 12, 31)
                else:
                    if current_day == 0: # S-a selectat o lună întreagă
                        _, num_days = calendar.monthrange(current_year, current_month)
                        start_date = date(current_year, current_month, 1)
                        end_date = date(current_year, current_month, num_days)
                    else: # S-a selectat o singură zi
                        start_date = end_date = date(current_year, current_month, current_day)

        # Fallback: Dacă, din orice motiv, datele nu au fost setate (ex: nicio selecție în nav_tree)
        if not start_date or not end_date:
            logging.debug("DEBUG_REPORT_CTX: Datele nu au putut fi determinate. Fallback la limitele DB.")
            row = self.db_handler.fetch_one_dict(
                "SELECT MIN(data) as min_d, MAX(data) as max_d FROM tranzactii WHERE id_cont_fk = %s", 
                (self.active_account_id,)
            )
            if row:
                start_date = row.get('min_d') or date.today()
                end_date = row.get('max_d') or date.today()
            else: # Nicio tranzacție în cont, folosim ziua de azi
                start_date = end_date = date.today()

        initial_context = {
            'active_account_id': self.active_account_id,
            'start_date': start_date,
            'end_date': end_date,
            'visible_tx_codes': self.visible_tx_codes # NOU: Pasează lista de coduri vizibile
        }
        
        logging.debug(f"DEBUG_REPORT: Se deschide raportul cu contextul final: {initial_context}")

        # 2. Pasează contextul la crearea dialogului de raport
        # Asigură-te că ui_reports este importat la începutul fișierului
        report_dialog = CashFlowReportDialog(self.master, self.db_handler, self.accounts_list, initial_context=initial_context, smtp_config=self.smtp_config)
    
    # Adăugați această metodă nouă în clasa BTViewerApp
    def show_balance_report(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date.", parent=self.master)
            return

        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

        # Pas 1: Deschide dialogul de configurare
        config_dialog = BalanceReportConfigDialog(self.master, self, self.accounts_list)

        # Pas 2: Dacă utilizatorul a confirmat, deschide fereastra de raport
        if config_dialog.result:
            report_config = config_dialog.result
            # ADAUGĂM LINIA DE MAI JOS:
            report_config['visible_tx_codes'] = self.visible_tx_codes
            BalanceEvolutionReportDialog(self.master, self.db_handler, self.smtp_config, report_config)

    def show_transaction_analysis_report(self):
        """Deschide fereastra pentru raportul de analiză detaliată a tranzacțiilor."""
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date.", parent=self.master)
            return

        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

        # Colectăm contextul inițial din fereastra principală
        start_date, end_date = None, None
        if self.date_range_mode_var.get():
            try:
                if hasattr(self, 'start_date') and self.start_date.get():
                    start_date = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.get():
                    end_date = self.end_date.get_date()
            except Exception as e:
                logging.warning(f"Atenție: Nu s-au putut prelua datele din DateEntry: {e}")
        else:
            if self.nav_selected_year:
                current_year, current_month, current_day = self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day
                if current_month == 0:
                    start_date, end_date = date(current_year, 1, 1), date(current_year, 12, 31)
                elif current_day == 0:
                    _, num_days = calendar.monthrange(current_year, current_month)
                    start_date, end_date = date(current_year, current_month, 1), date(current_year, current_month, num_days)
                else:
                    start_date = end_date = date(current_year, current_month, current_day)

        if not start_date or not end_date:
            # Fallback dacă nu se poate determina perioada
            start_date, end_date = date.today().replace(day=1, month=1), date.today()

        # NOU: Preluăm și moneda contului activ
        active_account = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
        currency = active_account.get('valuta', 'RON') if active_account else 'RON'

        initial_context = {
            'active_account_id': self.active_account_id,
            'start_date': start_date,
            'end_date': end_date,
            'visible_tx_codes': self.visible_tx_codes,
            'accounts_list': self.accounts_list,
            'db_handler': self.db_handler, # Pasăm și handler-ul DB
            'currency': currency # MODIFICAT: Adăugăm moneda
        }

        # Lansăm fereastra de raport, pasând contextul
        TransactionAnalysisReportDialog(self.master, self.db_handler, initial_context)

    def init_step1_read_config(self):
        if not self.master.winfo_exists(): return
        logging.debug("DEBUG_INIT: Intrat în init_step1_read_config.")
        
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Se citește configurația...")
        self.master.update_idletasks()

        self.config = configparser.ConfigParser()
        db_credentials_found_in_config = False
        
        if os.path.exists(config_management.CONFIG_FILE):
            try:
                self.config.read(config_management.CONFIG_FILE, encoding='utf-8')
                db_creds = config_management.read_db_config_from_parser(self.config)
                if db_creds:
                    self.db_host = db_creds["db_host"]
                    self.db_port = db_creds["db_port"]
                    self.db_name = db_creds["db_name"]
                    self.db_user = db_creds["db_user"]
                    self.db_password = db_creds["db_password"]
                #Citim și configurația SMTP
                    self.smtp_config = read_smtp_config_from_parser(self.config)
                    db_credentials_found_in_config = True
            except Exception as e:
                logging.error(f"Eroare la citirea/parsarea config.ini: {e}")
        
        logging.debug(f"DEBUG_INIT: Ieșit din init_step1_read_config. db_credentials_found: {db_credentials_found_in_config}")
        if db_credentials_found_in_config:
            self.master.after(10, self.init_step2_connect)
        else:
            self.db_host, self.db_port, self.db_name, self.db_user, self.db_password = None, 3306, None, None, ""
            self.master.after(10, self.init_step2b_prompt_credentials)

    def connect_to_db(self):
        logging.debug("DEBUG_CONNECT_DB: Încercare conectare/reconectare...")
        if not all([self.db_host, self.db_port, self.db_name, self.db_user]):
            if self.master.winfo_exists():
                messagebox.showerror("Date Conexiune Incomplete", "Lipsesc informații esențiale pentru conexiunea la baza de date.", parent=self.master)
            return False
        
        if self.db_handler: 
            logging.debug("DEBUG_CONNECT_DB: Handler DB existent. Se închide conexiunea veche (dacă există).")
            self.db_handler.close_connection()

        logging.debug("DEBUG_CONNECT_DB: Se creează/actualizează DatabaseHandler.")
        self.db_handler = DatabaseHandler(
            self.db_host, self.db_port, self.db_name, 
            self.db_user, self.db_password, 
            app_master_ref=self.master
        )
        connection_status = self.db_handler.connect_to_db_internal()
        logging.debug(f"DEBUG_CONNECT_DB: Starea conexiunii după încercare: {connection_status}")
        return connection_status

    def init_step2_connect(self):
        if not self.master.winfo_exists(): return
        logging.debug("DEBUG_INIT: Intrat în init_step2_connect.")
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Se conectează la baza de date...")
        self.master.update_idletasks()

        if self.connect_to_db():
            logging.debug("DEBUG_INIT: init_step2_connect - Conexiune reușită. Se programează init_step3.")
            self.master.after(10, self.init_step3_check_table)
        else:
            logging.debug("DEBUG_INIT: init_step2_connect - Conexiune eșuată. Se programează prompt credențiale.")
            self.master.after(10, self.init_step2b_prompt_credentials)
    
    def init_step2b_prompt_credentials(self):
        if not self.master.winfo_exists(): return
        logging.debug("DEBUG_INIT: Intrat în init_step2b_prompt_credentials.")
        
        prompt_successful = self.prompt_for_mariadb_credentials()
        
        if not self.master.winfo_exists(): return 
        self.master.update_idletasks()

        logging.debug(f"DEBUG_INIT: Ieșit din init_step2b_prompt_credentials. Prompt reușit: {prompt_successful}")
        if prompt_successful:
            self.master.after(10, self.init_step3_check_table)
            if self.master.winfo_exists():
                messagebox.showinfo("Configurare Reușită", "Conexiunea la baza de date a fost actualizată.", parent=self.master)
        else:
            self.exit_app("Configurarea bazei de date a fost anulată sau a eșuat. Aplicația se va închide.")
    
    def init_step3_check_table(self):
        if not self.master.winfo_exists(): return
        logging.debug("DEBUG_INIT: Intrat în init_step3_check_table.")
        if not (self.db_handler and self.db_handler.is_connected()):
            if self.master.winfo_exists():
                messagebox.showerror("Eroare Conexiune", "Conexiunea la baza de date nu este activă. Se încearcă reconfigurarea.", parent=self.master)
            self.master.after(10, self.init_step2b_prompt_credentials)
            return

        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Se verifică structura bazei de date...")
        self.master.update_idletasks()

        table_ok = self.db_handler.check_and_setup_database_schema(app_instance_ref=self)
            
        if not self.master.winfo_exists(): return 
            
        logging.debug(f"DEBUG_INIT: Ieșit din init_step3_check_table. Table OK: {table_ok}")
        if table_ok:
            self.master.after(10, self.init_step4_populate_ui)
        else:
            self.exit_app("Aplicația nu poate funcționa fără o schemă validă a bazei de date. Verificați mesajele anterioare.")
            
    def init_step4_populate_ui(self):
        if not self.master.winfo_exists(): 
            logging.debug("DEBUG_INIT: init_step4_populate_ui - Master window nu mai există. Ieșire.")
            return
        logging.debug("DEBUG_INIT: Intrat în init_step4_populate_ui.")

        final_title = f"{APP_NAME} v{APP_VERSION} (client-server multicont)  |  {APP_COPYRIGHT}"
        self.master.title(final_title)

        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Se încarcă configurația conturilor...")
        if self.master.winfo_exists(): self.master.update_idletasks()

        self._populate_account_selector() 

        if self.master.winfo_exists():
            self.master.after(100, self._handle_initial_data_migration_if_needed)

        if self.master.winfo_exists():
            self.master.after(300, lambda: self._schedule_ui_population_steps(self.config, "(initial setup)"))
            self._load_visible_transaction_types()

        logging.debug("DEBUG_INIT: Ieșit din init_step4_populate_ui.")

    # --- UI Setup și Meniu ---
    def setup_ui(self):
        logging.debug("DEBUG_SETUP_UI: Început setup_ui.")
        default_font_size = 10
        default_font_family = 'TkDefaultFont'
        
        style = ttk.Style()
        style.configure("TLabel", font=(default_font_family, default_font_size))
        style.configure("TButton", font=(default_font_family, default_font_size))
        style.configure("TCombobox", font=(default_font_family, default_font_size))
        self.master.option_add("*TCombobox*Listbox*Font", (default_font_family, default_font_size))
        style.configure("Treeview.Heading", font=(default_font_family, default_font_size, 'bold'))
        style.configure("Treeview", font=(default_font_family, default_font_size), rowheight=int(default_font_size * 2.2) + 4)
        style.configure("nav.Treeview", font=(default_font_family, default_font_size), rowheight=int(default_font_size * 2.0) + 2)
        style.map("nav.Treeview", background=[('selected', 'lightblue')], foreground=[('selected', 'black')])
        style.configure("Vertical.TScrollbar", troughcolor='#EAEAEA', background='#C1C1C1', gripcount=0, width=18, arrowsize=14, arrowcolor='black', bordercolor='#A0A0A0')
        style.map("Vertical.TScrollbar", background=[('active', '#A1A1A1')])
        style.configure("Custom.TNotebook.Tab", font=(default_font_family, default_font_size), padding=[10, 5], background="#ECECEC")
        style.map("Custom.TNotebook.Tab", background=[("selected", "#FFFFFF"), ("active", "#e0e0e0")], foreground=[("selected", "#000000")], expand=[("selected", [1, 1, 1, 0])])
        style.configure("Custom.TNotebook", tabposition='nw')
        
        self.create_menu()
        main_paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        nav_frame_container = ttk.Frame(main_paned_window, width=230, relief=tk.SUNKEN, borderwidth=1)
        nav_frame_container.pack_propagate(False)
        main_paned_window.add(nav_frame_container, weight=0)
        
        ttk.Label(nav_frame_container, text="Navigare Perioadă:", font=(default_font_family, 10, 'bold')).pack(pady=(5,2), padx=5, anchor='w')
        
        self.nav_tree = ttk.Treeview(nav_frame_container, show="tree", selectmode="browse", style="nav.Treeview")
        self.nav_tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0,5))
        self._setup_nav_tree_columns() 
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_nav_tree_select)
        self.nav_tree.bind("<<TreeviewOpen>>", self._on_nav_tree_expand_or_double_click)
        self.nav_tree.bind("<Double-1>", self._on_nav_tree_expand_or_double_click)
        
        right_pane_frame = ttk.Frame(main_paned_window)
        main_paned_window.add(right_pane_frame, weight=1)
        
        top_controls_container = tk.Frame(right_pane_frame)
        top_controls_container.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0,5))

        row1_frame = tk.Frame(top_controls_container)
        row1_frame.pack(fill=tk.X, expand=True)

        account_selector_frame = ttk.Frame(row1_frame)
        account_selector_frame.pack(side=tk.LEFT)
        ttk.Label(account_selector_frame, text="Cont Bancar Activ:", font=(default_font_family, default_font_size, 'bold')).pack(side=tk.LEFT, padx=(0,2))
        self.active_account_color_indicator = tk.Frame(account_selector_frame, width=120, height=20, relief=tk.SUNKEN, borderwidth=1, background="SystemButtonFace")
        self.active_account_color_indicator.pack(side=tk.LEFT, padx=(2, 5), pady=2)
        self.account_selector_combo = ttk.Combobox(account_selector_frame, textvariable=self.account_combo_var, state="disabled", width=45, font=(default_font_family, default_font_size))
        self.account_selector_combo.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)
        self.account_selector_combo.bind("<<ComboboxSelected>>", self._on_account_selected)

        action_buttons_frame = tk.Frame(row1_frame)
        action_buttons_frame.pack(side=tk.RIGHT)
        self.report_button = tk.Button(action_buttons_frame, text="Analiză Cash Flow", command=self.show_cash_flow_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#D5F5E3", activebackground="#BDECB6")
        self.report_button.pack(side=tk.LEFT, padx=(0, 5))

        # --- BUTON NOU: Evoluție Sold ---
        self.balance_report_button = tk.Button(action_buttons_frame, text="Evoluție Sold", command=self.show_balance_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#D4E6F1", activebackground="#A9CCE3")
        self.balance_report_button.pack(side=tk.LEFT, padx=5)
        # -------------------------------

        # --- BUTON NOU: Analiză Tranzacții ---
        self.analysis_button = tk.Button(action_buttons_frame, text="Analiză Tranzacții", command=self.show_transaction_analysis_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#FEF9E7", activebackground="#FDEBD0")
        self.analysis_button.pack(side=tk.LEFT, padx=5)
        # ------------------------------------

        self.export_button = tk.Button(action_buttons_frame, text="Exportă în Excel", command=self.export_to_excel, font=(default_font_family, default_font_size), relief=tk.RAISED, borderwidth=2)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.import_button = tk.Button(action_buttons_frame, text="Importă fișier MT940", command=self.import_mt940, font=(default_font_family, default_font_size), relief=tk.RAISED, borderwidth=2)
        self.import_button.pack(side=tk.LEFT, padx=5)

        row2_frame = tk.Frame(top_controls_container)
        row2_frame.pack(fill=tk.X, expand=True, pady=(5,0))
        self.date_range_checkbox = tk.Checkbutton(row2_frame, text="Interval Dată Specific:", variable=self.date_range_mode_var, command=self._toggle_filter_mode, font=(default_font_family, default_font_size))
        self.date_range_checkbox.pack(side=tk.LEFT, padx=(0,10))
        ttk.Label(row2_frame, text="De la:").pack(side=tk.LEFT, padx=(0, 2))
        self.start_date = DateEntry(row2_frame, date_pattern='yyyy-MM-dd', width=12, state='disabled', font=(default_font_family, default_font_size))
        self.start_date.pack(side=tk.LEFT, padx=(0,5))
        self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
        ttk.Label(row2_frame, text="Până la:").pack(side=tk.LEFT, padx=(5, 2))
        self.end_date = DateEntry(row2_frame, date_pattern='yyyy-MM-dd', width=12, state='disabled', font=(default_font_family, default_font_size))
        self.end_date.pack(side=tk.LEFT, padx=(0,10))
        self.end_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
        ttk.Label(row2_frame, text="Tip:").pack(side=tk.LEFT)
        self.type_combo = ttk.Combobox(row2_frame, textvariable=self.type_var, values=["Toate", "credit", "debit"], width=10, state="readonly", font=(default_font_family, default_font_size))
        self.type_combo.pack(side=tk.LEFT, padx=(2,10))
        self.type_combo.bind("<<ComboboxSelected>>", self.on_filter_change)
        ttk.Label(row2_frame, text="Căutare:").pack(side=tk.LEFT, padx=(5,2))
        self.search_entry = ttk.Entry(row2_frame, textvariable=self.search_var, width=20, font=(default_font_family, default_font_size))
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<KeyRelease>", self.schedule_search)
        ttk.Label(row2_frame, text="în:").pack(side=tk.LEFT, padx=(5,2))
        self.search_column_combo = ttk.Combobox(row2_frame, textvariable=self.search_column_var, values=["Toate coloanele", "Beneficiar", "CIF", "Factura", "Descriere", "Observatii"], width=15, state="readonly", font=(default_font_family, default_font_size))
        self.search_column_combo.pack(side=tk.LEFT, padx=(0,10))
        self.search_column_combo.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.reset_button = ttk.Button(row2_frame, text="Resetează filtrele", command=self.reset_filters)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        main_content_notebook = ttk.Notebook(right_pane_frame, style="Custom.TNotebook")
        main_content_notebook.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        transactions_tab = ttk.Frame(main_content_notebook)
        main_content_notebook.add(transactions_tab, text=" Listă Tranzacții ")
        self.tree = ttk.Treeview(transactions_tab, columns=self.treeview_display_columns, show="headings", style="Treeview")
        self.tree.tag_configure('credit_row', background='#E6FFE6')
        self.tree.tag_configure('debit_row', background='#FFE6E6')
       
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(transactions_tab, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        default_widths = {"data": 80, "descriere": 300, "observatii": 200, "suma": 90, "tip": 60, "cif": 80, "factura": 80, "beneficiar": 180}

        # O singură buclă pentru a configura complet fiecare coloană
        for col in self.treeview_display_columns:
            # Preluăm lățimea corectă (din fișierul de configurare sau valoarea implicită)
            width = self.loaded_column_widths.get(col, default_widths.get(col, 100))
            self.tree.column(col, anchor="w", width=width, minwidth=40)

            # Configurăm antetul (heading) cu textul și comanda de sortare într-un singur apel
            header_text = col.upper() if col == 'cif' else col.capitalize().replace("_", " ")
            self.tree.heading(col, text=header_text, command=lambda c=col: self.toggle_sort(c))
        self.tree.bind("<Double-1>", self.show_transaction_details)
        history_tab = ttk.Frame(main_content_notebook)
        main_content_notebook.add(history_tab, text=" Istoric Importuri ")
        history_cols = ("fisier", "data", "noi", "ignorate", "cont")
        self.history_tree = ttk.Treeview(history_tab, columns=history_cols, show="headings")
        self.history_tree.heading("fisier", text="Nume Fișier")
        self.history_tree.heading("data", text="Data Import")
        self.history_tree.heading("noi", text="Tranzacții Noi")
        self.history_tree.heading("ignorate", text="Tranzacții Ignorate")
        self.history_tree.heading("cont", text="Importat în Contul")
        self.history_tree.column("fisier", width=250); self.history_tree.column("data", width=150)
        self.history_tree.column("noi", width=120, anchor='center'); self.history_tree.column("ignorate", width=130, anchor='center')
        self.history_tree.column("cont", width=200)
        history_scrollbar = ttk.Scrollbar(history_tab, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill="y")
        
        footer_frame = tk.Frame(self.master, bd=1, relief=tk.SUNKEN)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame_left = ttk.Frame(footer_frame)
        status_frame_left.pack(side=tk.LEFT, padx=5, pady=2, fill=tk.X, expand=True)
        self.status_label = tk.Label(status_frame_left, text="Așteptare inițializare...", anchor="w", font=(default_font_family, default_font_size))
        self.status_label.pack(side=tk.LEFT)
        totals_frame = ttk.Frame(footer_frame)
        totals_frame.pack(side=tk.RIGHT, padx=10, pady=2)
        ttk.Label(totals_frame, text="Total Intrări:", font=(default_font_family, default_font_size, 'bold')).grid(row=0, column=0, sticky="e")
        self.total_credit_label = ttk.Label(totals_frame, text="0.00 RON", font=(default_font_family, default_font_size, 'bold'), foreground="#006400")
        self.total_credit_label.grid(row=0, column=1, sticky="w", padx=(5,15))
        ttk.Label(totals_frame, text="Total Ieșiri:", font=(default_font_family, default_font_size, 'bold')).grid(row=0, column=2, sticky="e")
        self.total_debit_label = ttk.Label(totals_frame, text="0.00 RON", font=(default_font_family, default_font_size, 'bold'), foreground="#8B0000")
        self.total_debit_label.grid(row=0, column=3, sticky="w", padx=(5,15))
        ttk.Label(totals_frame, text="Balanță Perioadă:", font=(default_font_family, default_font_size, 'bold')).grid(row=0, column=4, sticky="e")
        self.sold_label = ttk.Label(totals_frame, text="0.00 RON", font=(default_font_family, default_font_size, 'bold'))
        self.sold_label.grid(row=0, column=5, sticky="w", padx=5)
        
        # --- MODIFICARE: Adăugăm noul buton la lista de butoane gestionate ---
        self.action_buttons = [self.report_button, self.balance_report_button, self.analysis_button, self.export_button, self.import_button, self.reset_button]
        # ---------------------------------------------------------------------
        
        self._toggle_action_buttons('disabled')
        logging.debug("DEBUG_SETUP_UI: Sfârșit setup_ui.")

    def _setup_nav_tree_columns(self):
        """Configurează aspectul coloanei principale din arborele de navigare."""
        self.nav_tree.column("#0", width=200, minwidth=180, stretch=tk.YES)
        self.nav_tree.heading("#0", text="Navigare Perioadă") 
        
        # Definește tag-uri pentru a stiliza diferit nodurile de an, lună și zi
        self.nav_tree.tag_configure('year_node', font=('TkDefaultFont', 10, 'bold')) 
        self.nav_tree.tag_configure('month_node', font=('TkDefaultFont', 9))
        self.nav_tree.tag_configure('day_node', font=('TkDefaultFont', 9, 'italic'))

    def _load_and_apply_filters_from_config(self, config_parser_obj):
        if not (hasattr(self, 'master') and self.master.winfo_exists()): return
        logging.debug("DEBUG: Se încarcă și aplică filtrele din configurație.")
        
        filters = config_management.load_filters_from_parser(config_parser_obj)
        self.type_var.set(filters['type'])
        self.search_var.set(filters['search_term'])
        self.search_column_var.set(filters['search_column'])
        
        # Unbind temporar pentru a nu declanșa evenimente la setarea programatică a datelor
        if hasattr(self, 'start_date') and self.start_date.winfo_exists(): self.start_date.unbind("<<DateEntrySelected>>")
        if hasattr(self, 'end_date') and self.end_date.winfo_exists(): self.end_date.unbind("<<DateEntrySelected>>")

        self.date_range_mode_var.set(filters['date_range_mode'])
        self._toggle_filter_mode() # Aplică starea controalelor (enabled/disabled)
        
        if self.master.winfo_exists(): self.master.update_idletasks()

        if filters['date_range_mode']:
            start_str, end_str = filters['start_date'], filters['end_date']
            parsed_start_date, parsed_end_date = None, None
            if start_str and end_str:
                try:
                    parsed_start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    parsed_end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                    if hasattr(self, 'start_date'): self.start_date.set_date(parsed_start_date)
                    if hasattr(self, 'end_date'): self.end_date.set_date(parsed_end_date)
                except (ValueError, TypeError): parsed_start_date, parsed_end_date = None, None
            
            if not (parsed_start_date and parsed_end_date):
                self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
                if hasattr(self, 'start_date'): parsed_start_date = self.start_date.get_date()
                if hasattr(self, 'end_date'): parsed_end_date = self.end_date.get_date()
            
            if self.master.winfo_exists(): self.master.update_idletasks()
            self.refresh_table(start_date_override=parsed_start_date, end_date_override=parsed_end_date)
        
        else: # Mod Navigare
            def restore_nav_selection_logic():
                if not (hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists()): return
                s_year_str, s_month_idx_str, s_day_str = filters['nav_year'], filters['nav_month_idx'], filters['nav_day']
                item_to_focus_iid, item_to_select_iid = None, None
                if s_year_str:
                    try:
                        s_year, s_month_idx, s_day = int(s_year_str), int(s_month_idx_str), int(s_day_str)
                        year_iid = f"year_{s_year}"
                        if self.nav_tree.exists(year_iid):
                            item_to_focus_iid = item_to_select_iid = year_iid
                            if s_month_idx != 0:
                                if not self.nav_tree.item(year_iid, "open"):
                                    self.nav_tree.item(year_iid, open=True); self._on_nav_tree_expand_or_double_click(item_to_expand=year_iid); self.master.update_idletasks()
                                month_iid = f"{year_iid}_month_{s_month_idx:02d}"
                                if self.nav_tree.exists(month_iid):
                                    item_to_focus_iid = item_to_select_iid = month_iid
                                    if s_day != 0:
                                        if not self.nav_tree.item(month_iid, "open"):
                                            self.nav_tree.item(month_iid, open=True); self._on_nav_tree_expand_or_double_click(item_to_expand=month_iid); self.master.update_idletasks()
                                        day_iid = f"{month_iid}_day_{s_day:02d}"
                                        if self.nav_tree.exists(day_iid): item_to_focus_iid = item_to_select_iid = day_iid
                    except: item_to_focus_iid, item_to_select_iid = None, None
                
                if not item_to_select_iid and hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                    children = self.nav_tree.get_children("")
                    if children and children[0] not in ["no_data_root", "no_data_root_disconnected_or_no_account"]: 
                        item_to_focus_iid = item_to_select_iid = children[0]
                if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                    for sel_item in self.nav_tree.selection(): self.nav_tree.selection_remove(sel_item)
                    if item_to_focus_iid and self.nav_tree.exists(item_to_focus_iid): self.nav_tree.focus(item_to_focus_iid)
                    if item_to_select_iid and self.nav_tree.exists(item_to_select_iid): 
                        self.nav_tree.selection_set(item_to_select_iid)
                        self.nav_tree.see(item_to_select_iid)
                
                self._apply_nav_selection_to_datepickers_and_refresh(nav_item_id_to_process = (self.nav_tree.focus() if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists() else None) or None)

            if self.master.winfo_exists(): self.master.after(250, restore_nav_selection_logic)

        # Re-bind evenimentele după setarea programatică
        if hasattr(self, 'start_date') and self.start_date.winfo_exists(): self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
        if hasattr(self, 'end_date') and self.end_date.winfo_exists(): self.end_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)

    def create_menu(self):
        default_font_family = 'TkDefaultFont'
        default_font_size = 10
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size)) # ADAUGĂ FONT
        menubar.add_cascade(label="Fișier", menu=file_menu, font=(default_font_family, default_font_size)) #
        file_menu.add_command(label="Configurează Conexiunea DB...", command=self.handle_db_config_from_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Gestionare Conturi Bancare...", command=self.manage_accounts)
        file_menu.add_separator()
        file_menu.add_command(label="Gestionare Tipuri Tranzacții...", command=self.manage_transaction_types)
        file_menu.add_separator()
        file_menu.add_command(label="Configurează SMTP (Email)...", command=self.configure_smtp)
        file_menu.add_separator()
        file_menu.add_command(label="Ieșire", command=lambda: ui_utils.handle_app_exit(self, self.master))
        reports_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size)) # ADAUGĂ FONT
        menubar.add_cascade(label="Rapoarte", menu=reports_menu, font=(default_font_family, default_font_size)) # ADAUGĂ FONT
        reports_menu.add_command(label="Analiză Flux de Numerar...", command=self.show_cash_flow_report)
        reports_menu.add_command(label="Evoluție Sold Cont...", command=self.show_balance_report)
        reports_menu.add_command(label="Analiză Detaliată Tranzacții...", command=self.show_transaction_analysis_report)
    
    def _on_account_selected(self, event=None):
        if self._prevent_on_account_selected_trigger:
            logging.debug("DEBUG: _on_account_selected - trigger prevenit programatic.")
            return

        logging.debug("DEBUG: _on_account_selected - a fost apelat.")
        selected_account_name = self.account_combo_var.get()
        selected_account_obj = next((acc for acc in self.accounts_list if acc['nume_cont'] == selected_account_name), None)

        if selected_account_obj:
            if self.active_account_id != selected_account_obj['id_cont']: 
                self.active_account_id = selected_account_obj['id_cont']
                config_management.save_app_config(self) 
                self.refresh_ui_for_account_change()
            else:
                logging.debug("DEBUG: _on_account_selected - contul selectat este același cu cel activ.")
                self.refresh_ui_for_account_change()
        else:
            self.active_account_id = None 
            self.refresh_ui_for_account_change() 
            if self.master.winfo_exists():
                messagebox.showwarning("Selecție Cont Invalidă", "Contul selectat nu este valid.", parent=self.master)

    def refresh_ui_for_account_change(self):
        if not self.master.winfo_exists(): return
        logging.debug(f"DEBUG: refresh_ui_for_account_change - Cont activ ID: {self.active_account_id}")

        self.update_total_count() 
        self._populate_nav_tree() 
        self.reset_filters() 

        self._update_status_label()
        self._update_active_account_color_indicator() 
        logging.debug(f"DEBUG: refresh_ui_for_account_change - UI reîmprospătat pentru cont ID: {self.active_account_id}")

    def _update_active_account_color_indicator(self):
        if not (hasattr(self, 'active_account_color_indicator') and self.active_account_color_indicator.winfo_exists()):
            return
        color_to_set = "SystemButtonFace" 
        if self.active_account_id and self.accounts_list:
            active_acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
            if active_acc_obj:
                color_hex = active_acc_obj.get('culoare_cont')
                if color_hex and re.match(r"^#[0-9a-fA-F]{6}$", color_hex):
                    color_to_set = color_hex
                else:
                    logging.debug(f"DEBUG: Culoare cont invalidă sau lipsă ('{color_hex}') pentru cont ID {self.active_account_id}. Se folosește default (#FFFFFF).")
                    color_to_set = "#FFFFFF" 
        try:
            self.active_account_color_indicator.config(background=color_to_set)
        except tk.TclError as e:
            logging.debug(f"DEBUG: Eroare Tcl la setarea culorii indicatorului: {e}. Culoare: {color_to_set}")
            try: self.active_account_color_indicator.config(background="SystemButtonFace")
            except tk.TclError: pass


    def _update_status_label(self):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            db_info_part = f"DB: {self.db_user}@{self.db_host}:{self.db_port}/{self.db_name} | " if self.db_handler and self.db_handler.is_connected() and self.db_host else "Deconectat. | "
            account_info_part = "Cont: Neselectat. | "
            if self.active_account_id:
                active_account_name = self.account_combo_var.get()
                if not active_account_name and self.accounts_list:
                    acc = next((a for a in self.accounts_list if a['id_cont'] == self.active_account_id), None)
                    if acc: active_account_name = acc['nume_cont']
                active_account_name = active_account_name or "N/A"
                account_info_part = f"Cont activ: {active_account_name} (ID: {self.active_account_id}) | "
            filters_active = self.date_range_mode_var.get() or (self.nav_selected_year is not None) or (self.type_var.get() != "Toate") or (self.search_var.get() != "")
            transaction_count_part = ""
            if not (self.db_handler and self.db_handler.is_connected() and self.active_account_id):
                transaction_count_part = "Nicio tranzacție."
            elif self.total_transaction_count == 0 :
                 transaction_count_part = "Nicio tranzacție pentru acest cont."
            elif filters_active:
                displayed_count = len(self.tree.get_children("")) if hasattr(self, 'tree') and self.tree.winfo_exists() else 0
                transaction_count_part = f"Afișate: {displayed_count} din {self.total_transaction_count}"
            else:
                transaction_count_part = f"Total tranzacții: {self.total_transaction_count}"
            self.status_label.config(text=db_info_part + account_info_part + transaction_count_part)


    def _populate_account_selector(self):
        logging.debug("DEBUG_POPULATE_ACCOUNTS: Început.")
        if not (self.db_handler and self.db_handler.is_connected()):
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=[])
                self.account_combo_var.set("Fără Conexiune DB")
                self.account_selector_combo.config(state="disabled")
            self.active_account_id = None
            self.accounts_list = []
            if self.master.winfo_exists(): self.master.after(50, self.refresh_ui_for_account_change)
            logging.debug("DEBUG_POPULATE_ACCOUNTS: Fără conexiune DB.")
            return

        try:
            self.accounts_list = self.db_handler.get_all_accounts() or []
            account_names = [acc['nume_cont'] for acc in self.accounts_list]
            logging.debug(f"DEBUG_POPULATE_ACCOUNTS: Conturi din DB ({len(account_names)}): {account_names}")

            last_active_id_str_from_config = None
            if self.config and self.config.has_section('General') and self.config.has_option('General', 'active_account_id'):
                last_active_id_str_from_config = self.config.get('General', 'active_account_id')
            
            last_active_id_from_config = None
            if last_active_id_str_from_config and last_active_id_str_from_config.isdigit():
                try: last_active_id_from_config = int(last_active_id_str_from_config)
                except ValueError: logging.debug(f"DEBUG: ID cont invalid (ValueError) în config: '{last_active_id_str_from_config}'")
            logging.debug(f"DEBUG_POPULATE_ACCOUNTS: ID din config: {last_active_id_from_config}")

            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=account_names)
                determined_active_id = None
                determined_active_name = None

                if not account_names:
                    determined_active_name = "Niciun Cont Configurat"
                    self.account_selector_combo.config(state="disabled")
                else:
                    self.account_selector_combo.config(state="readonly")
                    if last_active_id_from_config is not None:
                        acc_from_config = next((acc for acc in self.accounts_list if acc['id_cont'] == last_active_id_from_config), None)
                        if acc_from_config:
                            determined_active_id = acc_from_config['id_cont']
                            determined_active_name = acc_from_config['nume_cont']
                            logging.debug(f"DEBUG_POPULATE_ACCOUNTS: Restaurat din config: ID={determined_active_id}, Nume='{determined_active_name}'")
                    if determined_active_id is None and self.active_account_id is not None:
                        acc_current_active = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
                        if acc_current_active:
                            determined_active_id = acc_current_active['id_cont']
                            determined_active_name = acc_current_active['nume_cont']
                            logging.debug(f"DEBUG_POPULATE_ACCOUNTS: Folosit self.active_account_id existent: ID={determined_active_id}, Nume='{determined_active_name}'")
                        else: self.active_account_id = None
                    if determined_active_id is None and self.accounts_list:
                        determined_active_id = self.accounts_list[0]['id_cont']
                        determined_active_name = self.accounts_list[0]['nume_cont']
                        logging.debug(f"DEBUG_POPULATE_ACCOUNTS: Selectat primul din listă: ID={determined_active_id}, Nume='{determined_active_name}'")
                
                self.active_account_id = determined_active_id
                self.account_combo_var.set(determined_active_name if determined_active_name else "Selectați Cont")
            else:
                self.active_account_id = self.accounts_list[0]['id_cont'] if self.accounts_list else None
        except Exception as e:
            logging.debug(f"DEBUG: Excepție în _populate_account_selector: {e}")
            if self.master.winfo_exists(): messagebox.showerror("Eroare Încărcare Conturi", f"Eroare: {e}", parent=self.master)
            self.active_account_id = None; self.accounts_list = []
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=[]); self.account_combo_var.set("Eroare"); self.account_selector_combo.config(state="disabled")
        
        config_management.save_app_config(self)
        logging.debug(f"DEBUG_POPULATE_ACCOUNTS: Config salvat. ID Cont activ final: {self.active_account_id}")
        if self.master.winfo_exists(): self.master.after(50, self.refresh_ui_for_account_change)
        logging.debug("DEBUG_POPULATE_ACCOUNTS: Sfârșit.")

    def manage_accounts(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            if self.master.winfo_exists(): messagebox.showwarning("Fără Conexiune", "Conectați-vă la DB.", parent=self.master)
            return
        dialog = AccountManagerDialog(self.master, self.db_handler) 
        self.master.wait_window(dialog.top) 
        logging.debug("DEBUG: manage_accounts - Se re-populează selectorul.")
        self._populate_account_selector() 
        if self.master.winfo_exists(): self.master.after(100, self._handle_initial_data_migration_if_needed)

    def _handle_initial_data_migration_if_needed(self):
        if not self.migration_needed_for_existing_transactions: return
        if not (self.db_handler and self.db_handler.is_connected()): logging.debug("DEBUG: Migrare amânată - fără conexiune DB."); return
        if not self.accounts_list:
            if self.master.winfo_exists(): messagebox.showinfo("Migrare Amânată", "Nu există conturi configurate.", parent=self.master)
            logging.debug("DEBUG: Migrare amânată - nu există conturi."); return
        if not self.active_account_id:
            if self.accounts_list: self.active_account_id = self.accounts_list[0]['id_cont']
            else: 
                if self.master.winfo_exists(): messagebox.showinfo("Migrare Imposibilă", "Niciun cont bancar definit.", parent=self.master)
                logging.debug("DEBUG: Migrare imposibilă - niciun cont."); return
        target_account_id = self.active_account_id
        target_account_name = next((acc['nume_cont'] for acc in self.accounts_list if acc['id_cont'] == target_account_id), "Necunoscut")
        unassigned_count = self.db_handler.fetch_scalar("SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk IS NULL")
        if unassigned_count is None: 
            if self.master.winfo_exists(): messagebox.showerror("Eroare DB", "Nu s-a putut verifica nr. tranzacții neasociate.", parent=self.master)
            return
        if unassigned_count == 0:
            self.migration_needed_for_existing_transactions = False 
            logging.debug("DEBUG: Nicio tranzacție neasociată. Finalizare schemă.")
            self._finalize_tranzactii_schema_after_migration(target_account_id_for_fk_check=None)
            return
        if self.master.winfo_exists():
            user_confirm = messagebox.askyesno("Migrare Tranzacții", f"{unassigned_count} tranzacții vechi neasociate.\nAsociați cu '{target_account_name}' (ID: {target_account_id})?", parent=self.master)
            if user_confirm:
                if self.db_handler.execute_commit("UPDATE tranzactii SET id_cont_fk = %s WHERE id_cont_fk IS NULL", (target_account_id,)):
                    messagebox.showinfo("Migrare Reușită", f"{unassigned_count} tranzacții asociate.", parent=self.master)
                    self.migration_needed_for_existing_transactions = False 
                    self._finalize_tranzactii_schema_after_migration(target_account_id_for_fk_check=target_account_id)
                    self.refresh_ui_for_account_change() 
                else: messagebox.showerror("Eroare Migrare", "Nu s-au putut asocia tranzacțiile.", parent=self.master)
            else: messagebox.showinfo("Migrare Amânată", "Asocierea a fost amânată.", parent=self.master)

    def _finalize_tranzactii_schema_after_migration(self, target_account_id_for_fk_check):
        if not (self.db_handler and self.db_handler.is_connected()): return
        try:
            if target_account_id_for_fk_check: 
                check_nulls = self.db_handler.fetch_scalar("SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk IS NULL")
                if check_nulls and check_nulls > 0:
                    if self.master.winfo_exists(): messagebox.showwarning("Atenție Schemă", "Încă există tranzacții neasociate.", parent=self.master)
                    return 
            with self.db_handler.conn.cursor() as cursor:
                if not self.db_handler._foreign_key_exists(cursor, 'tranzactii', 'fk_tranzactie_cont'):
                    self.db_handler.execute_commit("ALTER TABLE tranzactii ADD CONSTRAINT fk_tranzactie_cont FOREIGN KEY (id_cont_fk) REFERENCES conturi_bancare(id_cont) ON DELETE RESTRICT")
                    logging.debug("DEBUG: FK 'fk_tranzactie_cont' adăugată.")
            self.db_handler.execute_commit("ALTER TABLE tranzactii MODIFY COLUMN id_cont_fk INT NOT NULL")
            logging.debug("DEBUG: 'id_cont_fk' setată NOT NULL.")
            self.migration_needed_for_existing_transactions = False
            if self.master.winfo_exists(): messagebox.showinfo("Info Schemă", "Schema 'tranzactii' actualizată (NOT NULL și FK).", parent=self.master)
        except Exception as e_schema:
            error_msg = f"Eroare finalizare schemă 'tranzactii': {e_schema}"
            if hasattr(e_schema, 'errno'): # Specific pentru mysql.connector.Error
                 if e_schema.errno == 1452 : error_msg = f"Eroare FK: {e_schema.msg}. Verificați asocierile."
                 elif e_schema.errno == 1048: error_msg = f"Eroare NOT NULL: {e_schema.msg}. Asociați toate tranzacțiile."
            if self.master.winfo_exists(): messagebox.showwarning("Atenție Schemă DB", error_msg, parent=self.master)
            logging.debug(f"DEBUG: Eroare finalizare schemă: {e_schema}")
# Continuare Clasa BTViewerApp

    def _ask_user_to_select_account_for_import(self, parent_window, prompt_message):
        """
        Deschide un dialog simplu pentru a permite utilizatorului să selecteze un cont
        din lista conturilor existente (self.accounts_list).
        Returnează ID-ul contului selectat sau None dacă se anulează.
        """
        if not self.accounts_list:
            if parent_window.winfo_exists():
                messagebox.showerror("Niciun Cont Definit", 
                                     "Nu există conturi bancare definite în aplicație. "
                                     "Vă rugăm adăugați un cont mai întâi prin meniul 'Fișier'.", 
                                     parent=parent_window)
            return None

        dialog = tk.Toplevel(parent_window)
        dialog.title("Selectați Contul Țintă")
        dialog.transient(parent_window)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(dialog, text=prompt_message, wraplength=380).pack(padx=10, pady=10)

        selected_account_name = tk.StringVar()
        account_names = [acc['nume_cont'] for acc in self.accounts_list]
        
        current_active_account_object = None
        if self.active_account_id:
            current_active_account_object = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
        
        if current_active_account_object:
            selected_account_name.set(current_active_account_object['nume_cont'])
        elif account_names:
            selected_account_name.set(account_names[0])

        combo = ttk.Combobox(dialog, textvariable=selected_account_name, values=account_names, state="readonly", width=40)
        combo.pack(padx=10, pady=5)
        if account_names: combo.focus_set()

        result_id = None 

        def on_ok():
            nonlocal result_id
            chosen_name = selected_account_name.get()
            chosen_account = next((acc for acc in self.accounts_list if acc['nume_cont'] == chosen_name), None)
            if chosen_account:
                confirm_msg = (f"Sunteți sigur că doriți să importați tranzacțiile în contul:\n\n"
                               f"Nume: {chosen_account['nume_cont']}\n"
                               f"IBAN: {chosen_account.get('iban', 'N/A')}\n\n"
                               "Această acțiune nu poate fi anulată după import.")
                if messagebox.askyesno("Supraconfirmare Alocare", confirm_msg, parent=dialog, icon='warning'):
                    result_id = chosen_account['id_cont']
                    dialog.destroy()
            else:
                messagebox.showerror("Eroare Selecție", "Vă rugăm selectați un cont valid.", parent=dialog)

        def on_cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(padx=10, pady=(5, 10), fill=tk.X)
        
        ok_button = ttk.Button(button_frame, text="Confirmă și Importă", command=on_ok)
        ok_button.pack(side=tk.RIGHT, padx=(5,0))
        
        cancel_button = ttk.Button(button_frame, text="Anulează Import", command=on_cancel)
        cancel_button.pack(side=tk.RIGHT, padx=5)

        if not account_names: ok_button.config(state="disabled")

        dialog.update_idletasks()
        dialog_width = dialog.winfo_width()
        dialog_height = dialog.winfo_height()
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        dialog.geometry(f"+{position_x}+{position_y}")
        
        parent_window.wait_window(dialog)
        return result_id


    def import_mt940(self):
        print(f"***** IMPORT_MT940 APELATĂ (LOGICĂ BATCH DINAMICĂ) LA: {datetime.now()} *****")

        if not (self.db_handler and self.db_handler.is_connected()):
            if self.master.winfo_exists():
                messagebox.showwarning("Fără Conexiune", "Vă rugăm configurați și stabiliți o conexiune la baza de date.", parent=self.master)
            return
        logging.debug("DEBUG_IMPORT_BATCH: Conexiune DB OK.")

        selected_file_paths = filedialog.askopenfilenames(
            master=self.master,
            title="Selectează unul sau mai multe fișiere MT940",
            filetypes=[("Fișiere MT940", "*.sta *.STA *.txt"), ("Toate fișierele", "*.*")]
        )
        if not selected_file_paths:
            logging.debug("DEBUG_IMPORT_BATCH: Niciun fișier selectat.")
            return
        
        self.file_paths_for_import_ref = selected_file_paths
        logging.debug(f"DEBUG_IMPORT_BATCH: Fișiere selectate: {selected_file_paths}")

        self.import_batch_queue = []
        temp_account_to_files_map = {} 

        for file_path in selected_file_paths:
            logging.debug(f"\nDEBUG_IMPORT_BATCH: Procesare pentru determinare cont: '{os.path.basename(file_path)}'")
            
            current_ui_active_account_id = self.active_account_id
            current_ui_active_account_iban = None
            current_ui_active_account_name = "N/A (Niciunul activ)"
            if current_ui_active_account_id:
                acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == current_ui_active_account_id), None)
                if acc_obj:
                    current_ui_active_account_iban = acc_obj.get('iban')
                    current_ui_active_account_name = acc_obj.get('nume_cont')
            logging.debug(f"DEBUG_IMPORT_BATCH: Cont activ UI (pentru acest fișier): ID={current_ui_active_account_id}, Nume='{current_ui_active_account_name}', IBAN='{current_ui_active_account_iban}'")

            iban_from_file_raw = extract_iban_from_mt940(file_path)
            iban_from_file = iban_from_file_raw.replace(" ", "").upper() if iban_from_file_raw else None
            logging.debug(f"DEBUG_IMPORT_BATCH: IBAN extras: '{iban_from_file}' (Raw: '{iban_from_file_raw}')")

            target_account_id_for_this_file = None

            if not iban_from_file:
                logging.debug(f"DEBUG_IMPORT_BATCH: IBAN indetectabil pentru '{os.path.basename(file_path)}'. Se cere selectare manuală.")
                prompt_msg = (f"Nu s-a putut extrage un IBAN valid din fișierul:\n'{os.path.basename(file_path)}'.\n\n"
                              "Vă rugăm selectați din lista de mai jos contul în care doriți să importați acest fișier:")
                chosen_id = self._ask_user_to_select_account_for_import(self.master, prompt_msg)
                if chosen_id:
                    target_account_id_for_this_file = chosen_id
                    if self.active_account_id != chosen_id:
                        chosen_account_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == chosen_id), None)
                        if chosen_account_obj:
                            self._prevent_on_account_selected_trigger = True
                            self.active_account_id = chosen_id
                            self.account_combo_var.set(chosen_account_obj['nume_cont'])
                            config_management.save_app_config(self)
                            self._prevent_on_account_selected_trigger = False
                    logging.debug(f"DEBUG_IMPORT_BATCH: Utilizatorul a selectat manual contul ID={chosen_id} pentru '{os.path.basename(file_path)}'")
                else:
                    logging.debug(f"DEBUG_IMPORT_BATCH: Utilizatorul a anulat selectarea pentru '{os.path.basename(file_path)}'. Fișier omis.")
                    continue 
            
            else: 
                normalized_iban_current_ui_active = current_ui_active_account_iban.replace(" ", "").upper() if current_ui_active_account_iban else None
                logging.debug(f"DEBUG_IMPORT_BATCH: IBAN fișier: '{iban_from_file}'. IBAN UI (curent): '{normalized_iban_current_ui_active}' (Nume: '{current_ui_active_account_name}')")

                if normalized_iban_current_ui_active and iban_from_file == normalized_iban_current_ui_active:
                    logging.debug(f"DEBUG_IMPORT_BATCH: IBAN-urile CORESPUND. Se folosește contul UI curent: ID={current_ui_active_account_id}")
                    target_account_id_for_this_file = current_ui_active_account_id
                else: 
                    logging.debug(f"DEBUG_IMPORT_BATCH: IBAN-uri diferite/cont UI curent fără IBAN. Căutare IBAN fișier ('{iban_from_file}') în DB...")
                    account_matching_db = self.db_handler.fetch_one_dict(
                        "SELECT id_cont, nume_cont, iban FROM conturi_bancare WHERE REPLACE(UPPER(iban), ' ', '') = %s", (iban_from_file,)
                    )
                    if account_matching_db:
                        matched_id = account_matching_db['id_cont']
                        matched_name = account_matching_db['nume_cont']
                        logging.debug(f"DEBUG_IMPORT_BATCH: Găsit în DB: ID={matched_id}, Nume='{matched_name}'")
                        
                        if current_ui_active_account_id and matched_id == current_ui_active_account_id:
                            target_account_id_for_this_file = current_ui_active_account_id
                        else:
                            msg = (f"Fișierul '{os.path.basename(file_path)}' (IBAN: {iban_from_file})\n"
                                   f"corespunde contului deja înregistrat:\n   Nume: {matched_name}\n\n"
                                   f"Importați tranzacțiile din acest fișier în contul '{matched_name}'?")
                            if self.master.winfo_exists() and messagebox.askyesno("Confirmare Cont pentru Fișier", msg, parent=self.master):
                                target_account_id_for_this_file = matched_id
                                self._prevent_on_account_selected_trigger = True
                                self.active_account_id = matched_id
                                self.account_combo_var.set(matched_name)
                                config_management.save_app_config(self)
                                self._prevent_on_account_selected_trigger = False
                                logging.debug(f"DEBUG_IMPORT_BATCH: Utilizator a confirmat. Import în cont existent: ID={matched_id}")
                            else:
                                logging.debug(f"DEBUG_IMPORT_BATCH: Utilizatorul a anulat. Fișier '{os.path.basename(file_path)}' omis.")
                                continue 
                    else:
                        logging.debug(f"DEBUG_IMPORT_BATCH: IBAN-ul din fișier ('{iban_from_file}') NU e în DB.")
                        msg = (f"Fișierul '{os.path.basename(file_path)}' (IBAN: {iban_from_file})\n"
                               f"NU este înregistrat în aplicație.\n\nOpțiuni:\n"
                               "1. Adăugați cont nou pentru acest IBAN (Apăsați 'Da').\n"
                               "2. Selectați manual un alt cont existent (Apăsați 'Nu').\n"
                               "3. Anulați pentru acest fișier (Apăsați 'Anulează').")
                        user_choice = messagebox.askyesnocancel(f"Cont Nou Detectat pentru {os.path.basename(file_path)}", msg, parent=self.master, icon='question')

                        if user_choice is True: # Adaugă cont nou
                            dialog = AccountEditDialog(self.master, self.db_handler, account_data={'iban': iban_from_file_raw}, title=f"Adaugă Cont pentru {os.path.basename(file_path)}")
                            if dialog.result:
                                try:
                                    res = dialog.result
                                    sql_ins = "INSERT INTO conturi_bancare (nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont) VALUES (%s,%s,%s,%s,%s,%s)"
                                    params_ins = (res['nume_cont'],res['iban'],res['nume_banca'],res['valuta'],res['observatii_cont'], res.get('culoare_cont', '#FFFFFF'))
                                    if self.db_handler.execute_commit(sql_ins, params_ins):
                                        new_id = self.db_handler.fetch_scalar("SELECT LAST_INSERT_ID()")
                                        if new_id: 
                                            target_account_id_for_this_file=new_id
                                            self._prevent_on_account_selected_trigger=True
                                            self.active_account_id=new_id
                                            config_management.save_app_config(self)
                                            self._prevent_on_account_selected_trigger=False
                                            self._populate_account_selector()
                                            acc_o=next((a for a in self.accounts_list if a['id_cont']==new_id),None)
                                            self.account_combo_var.set(acc_o['nume_cont'] if acc_o else "")
                                        else: logging.debug(f"DEBUG_IMPORT_BATCH: Eroare LAST_INSERT_ID. Fișier omis."); continue
                                    else: logging.debug(f"DEBUG_IMPORT_BATCH: Eroare INSERT cont. Fișier omis."); continue
                                except Exception as e_add_f: logging.debug(f"DEBUG_IMPORT_BATCH: Excepție add cont: {e_add_f}. Fișier omis."); continue
                            else: logging.debug(f"DEBUG_IMPORT_BATCH: Anulat adăugare cont. Fișier omis."); continue
                        elif user_choice is False: # Selectează manual
                            prompt_manual = (f"IBAN din '{os.path.basename(file_path)}' ({iban_from_file}) e necunoscut.\nSelectați contul țintă:")
                            chosen_manual_id = self._ask_user_to_select_account_for_import(self.master, prompt_manual)
                            if chosen_manual_id: 
                                target_account_id_for_this_file = chosen_manual_id
                                if self.active_account_id != chosen_manual_id: 
                                    acc_m_obj = next((a for a in self.accounts_list if a['id_cont']==chosen_manual_id), None)
                                    if acc_m_obj: 
                                        self._prevent_on_account_selected_trigger=True
                                        self.active_account_id=chosen_manual_id
                                        self.account_combo_var.set(acc_m_obj['nume_cont'])
                                        config_management.save_app_config(self)
                                        self._prevent_on_account_selected_trigger=False
                                logging.debug(f"DEBUG_IMPORT_BATCH: Utilizatorul a selectat manual contul ID={chosen_manual_id} pentru '{os.path.basename(file_path)}'")
                            else: logging.debug(f"DEBUG_IMPORT_BATCH: Anulat selecție manuală. Fișier omis."); continue
                        else: # Cancel
                            logging.debug(f"DEBUG_IMPORT_BATCH: Anulat pt '{os.path.basename(file_path)}'. Fișier omis.")
                            continue
            
            if target_account_id_for_this_file is not None:
                if target_account_id_for_this_file not in temp_account_to_files_map: temp_account_to_files_map[target_account_id_for_this_file] = []
                temp_account_to_files_map[target_account_id_for_this_file].append(file_path)
                logging.debug(f"DEBUG_IMPORT_BATCH: Fișierul '{os.path.basename(file_path)}' adăugat la lotul pentru cont ID={target_account_id_for_this_file}")

        for acc_id, files_list in temp_account_to_files_map.items():
            if files_list: self.import_batch_queue.append({'target_id': acc_id, 'files': list(files_list)})
        
        if not self.import_batch_queue:
            if self.master.winfo_exists(): messagebox.showinfo("Import Anulat", "Niciun fișier nu a fost programat pentru import.", parent=self.master)
            return

        logging.debug(f"DEBUG_IMPORT_BATCH: Coada de loturi pregătită: {self.import_batch_queue}")
        self._process_next_import_batch()

    def _process_next_import_batch(self):
        if not self.import_batch_queue:
            logging.debug("DEBUG_IMPORT_BATCH: Toate loturile de import au fost procesate.")
            if self.master.winfo_exists():
                messagebox.showinfo("Importuri Finalizate", "Toate loturile de fișiere selectate au fost procesate.", parent=self.master)
            self._toggle_action_buttons('normal')
            self.refresh_ui_for_account_change()
            return

        current_batch = self.import_batch_queue.pop(0)
        target_id = current_batch['target_id']
        files_for_this_batch = current_batch['files']
        
        self.current_batch_info_for_message = {'target_id': target_id, 'num_files': len(files_for_this_batch)}

        acc_obj_batch = next((acc for acc in self.accounts_list if acc['id_cont'] == target_id), None)
        target_name_batch = acc_obj_batch['nume_cont'] if acc_obj_batch else f"ID Cont {target_id}"
        
        logging.debug(f"DEBUG_IMPORT_BATCH: Se pornește importul pentru lot: Cont '{target_name_batch}' (ID={target_id}), Fișiere: {len(files_for_this_batch)}")

        self._toggle_action_buttons('disabled')
        
        self.current_progress_win = None
        self.current_progress_bar = None
        self.current_progress_status_label_widget = None

        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = \
            file_processing.create_progress_window(self.master, f"Import Lot Cont: {target_name_batch}", f"Se procesează {len(files_for_this_batch)} fișier(e)...")
        
        if self.current_progress_bar and self.current_progress_bar.winfo_exists():
            self.current_progress_bar['maximum'] = len(files_for_this_batch)

        self.import_thread = threading.Thread(
            target=threaded_import_worker,
            args=(self, files_for_this_batch, self.queue, target_id)
        )
        self.import_thread.daemon = True
        self.import_thread.start()
        if self.master.winfo_exists():
            self.master.after(100, self._check_batch_import_progress)

    def _finalize_background_task(self, message, success, operation_type):
        """Metodă generală pentru a finaliza un task de fundal."""
        logging.debug(f"DEBUG_FINALIZE_TASK: Finalizare pentru '{operation_type}'. Succes: {success}")
        
        if hasattr(self, 'current_progress_win') and self.current_progress_win and self.current_progress_win.winfo_exists():
            try:
                if hasattr(self, 'current_progress_bar') and self.current_progress_bar.winfo_exists(): self.current_progress_bar.stop()
                self.current_progress_win.destroy()
                logging.debug("DEBUG_FINALIZE_TASK: Fereastra de progres a fost distrusă.")
            except tk.TclError as e: logging.debug(f"DEBUG_FINALIZE_TASK: Eroare Tcl la închiderea ferestrei: {e}")
        
        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = None, None, None
        
        if operation_type and hasattr(self, f"{operation_type}_thread"): 
            setattr(self, f"{operation_type}_thread", None)

        if not self.import_batch_queue: # Reactivează butoanele doar dacă e ultimul lot sau nu e un import
            self._toggle_action_buttons('normal')

        if self.master.winfo_exists():
            if success: 
                messagebox.showinfo("Operațiune Finalizată", message, parent=self.master)
            else: 
                messagebox.showerror("Eroare Operațiune", message, parent=self.master)

    def _check_batch_import_progress(self):
        try:
            msg = self.queue.get_nowait()
            msg_type = msg[0]
            
            if msg_type == "done":
                operation_type = msg[1]
                results = msg[2]
                inserted, ignored = results[0], results[1]
                
                batch_info = self.current_batch_info_for_message or {}
                num_files_in_batch = batch_info.get('num_files', 'N/A')
                processed_target_id = batch_info.get('target_id')
                processed_target_name = next((acc['nume_cont'] for acc in self.accounts_list if acc['id_cont'] == processed_target_id), f"ID {processed_target_id}")
                
                final_batch_message = (
                    f"Lot pentru contul '{processed_target_name}' finalizat.\n\n"
                    f"Fișiere procesate: {num_files_in_batch}\n"
                    f"Tranzacții noi importate: {inserted}\n"
                    f"Tranzacții ignorate (duplicate): {ignored}"
                )
                
                # Pas 1: Finalizează UI-ul de progres (închide fereastra, arată mesaj)
                self._finalize_background_task(final_batch_message, success=True, operation_type=operation_type)

                if processed_target_id is not None:
                    # --- CORECȚIA FINALĂ PENTRU REFRESH ---

                    # Pas 2: Forțează reconectarea la DB pentru a vedea datele noi
                    logging.debug("DEBUG_REFRESH: Forțare reconectare la DB pentru firul principal...")
                    if self.db_handler:
                        self.db_handler.close_connection()
                    if not self.connect_to_db():
                        if self.master.winfo_exists(): 
                            messagebox.showerror("Eroare Conexiune", "Nu s-a putut reconecta la DB după import.", parent=self.master)
                        # Oprim procesarea următoarelor loturi dacă reconectarea eșuează
                        self.import_batch_queue = []
                        if self.master.winfo_exists(): self.master.after(100, self._process_next_import_batch);
                        return

                    # Pas 3: Actualizează contul activ în UI dacă e necesar
                    if self.active_account_id != processed_target_id:
                        target_acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == processed_target_id), None)
                        if target_acc_obj:
                            self._prevent_on_account_selected_trigger = True
                            self.active_account_id = processed_target_id
                            self.account_combo_var.set(target_acc_obj['nume_cont'])
                            config_management.save_app_config(self)
                            self._prevent_on_account_selected_trigger = False
                    
                    # Pas 4: Reîncarcă datele de bază folosind noua conexiune
                    logging.debug("DEBUG_REFRESH: Reîncărcare date de bază (tipuri, număr total, arbore nav)...")
                    self._load_visible_transaction_types()
                    self.update_total_count()
                    self._populate_nav_tree()

                    # Pas 5: Reîmprospătează tabela principală cu datele noi, PĂSTRÂND filtrele curente
                    logging.debug("DEBUG_REFRESH: Reîmprospătare tabelă principală...")
                    self.refresh_table()

                    # Asigură că și status bar-ul și totalurile sunt la zi
                    self._update_status_label()
                    self._calculate_and_update_totals()

                    if self.master.winfo_exists():
                        self.master.update_idletasks()
                
                # Trecem la următorul lot din coadă, dacă există
                if self.master.winfo_exists():
                    self.master.after(100, self._process_next_import_batch)
            
            elif msg_type == "progress":
                if hasattr(self, 'current_progress_win') and self.current_progress_win.winfo_exists():
                    if hasattr(self, 'current_progress_bar') and self.current_progress_bar.winfo_exists():
                        self.current_progress_bar['value'] = msg[1] + 1
                    if hasattr(self, 'current_progress_status_label_widget') and self.current_progress_status_label_widget.winfo_exists():
                        self.current_progress_status_label_widget.config(text=msg[2])
                if self.master.winfo_exists():
                    self.master.after(100, self._check_batch_import_progress)
            
            elif msg_type == "error":
                operation_type = msg[1]; error_message = msg[2]
                self._finalize_background_task(error_message, success=False, operation_type=operation_type)
                if operation_type == 'import_batch': self.import_batch_queue = []
        
        except Empty:
            if hasattr(self, 'import_thread') and self.import_thread and self.import_thread.is_alive():
                if self.master.winfo_exists(): self.master.after(100, self._check_batch_import_progress)
            else:
                if self.import_batch_queue:
                    if self.master.winfo_exists(): self.master.after(100, self._process_next_import_batch)
                else: self._toggle_action_buttons('normal')
        
        except Exception as e:
            logging.error(f"ErOARE CRITICĂ în _check_batch_import_progress: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_table(self, start_date_override=None, end_date_override=None):
        logging.debug(f"DEBUG_REFRESH_TABLE: Intrat în refresh_table. Cont activ ID: {self.active_account_id}")

        if not (self.db_handler and self.db_handler.is_connected() and
                hasattr(self, 'tree') and self.tree.winfo_exists() and 
                self.active_account_id is not None):
            
            if hasattr(self, 'tree') and self.tree.winfo_exists():
                for item in self.tree.get_children(""): self.tree.delete(item)
            self._update_status_label(); self._calculate_and_update_totals()
            return

        for item in self.tree.get_children(""): self.tree.delete(item)

        select_cols_list = ['id', 'data', 'tip'] + [c for c in self.treeview_display_columns if c not in ['id', 'data', 'tip']]
        select_clause = ", ".join(select_cols_list)
        query = f"SELECT {select_clause} FROM tranzactii WHERE id_cont_fk = %s"
        params = [self.active_account_id]
        
        if self.visible_tx_codes:
            # Creăm un șir de placeholderi (%s, %s, ...)
            placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
            query += f" AND cod_tranzactie_fk IN ({placeholders})"
            params.extend(self.visible_tx_codes)
        else:
            # Dacă niciun tip nu e vizibil, nu afișăm nicio tranzacție operațională
            query += " AND 1=0" # O condiție care este mereu falsă

        start_date_to_use, end_date_to_use = start_date_override, end_date_override
        if start_date_to_use is None:
            if self.date_range_mode_var.get():
                if hasattr(self, 'start_date') and self.start_date.get(): start_date_to_use = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.get(): end_date_to_use = self.end_date.get_date()
            else:
                if self.nav_selected_year:
                    year, month, day = self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day
                    if month == 0: start_date_to_use, end_date_to_use = date(year, 1, 1), date(year, 12, 31)
                    else:
                        if day == 0: _, num_days = calendar.monthrange(year, month); start_date_to_use, end_date_to_use = date(year, month, 1), date(year, month, num_days)
                        else: start_date_to_use = end_date_to_use = date(year, month, day)
        
        if start_date_to_use: query += " AND data >= %s"; params.append(start_date_to_use.strftime('%Y-%m-%d'))
        if end_date_to_use: query += " AND data <= %s"; params.append(end_date_to_use.strftime('%Y-%m-%d'))
        
        if self.type_var.get() != "Toate": query += " AND tip = %s"; params.append(self.type_var.get())
        if self.search_var.get():
            search_term = f"%{self.search_var.get()}%"
            selected_search_area = self.search_column_var.get()

            if selected_search_area == "Toate coloanele":
                # Căutare eficientă în toate coloanele text relevante folosind CONCAT_WS
                query += " AND CONCAT_WS(' ', beneficiar, cif, factura, descriere, observatii) LIKE %s"
                params.append(search_term)
            else:
                # Căutare într-o singură coloană, specificată
                col_map = {"Beneficiar": "beneficiar", "CIF": "cif", "Factura": "factura", "Descriere": "descriere", "Observatii": "observatii"}
                search_col_db_name = col_map.get(selected_search_area, "descriere")
                query += f" AND {search_col_db_name} LIKE %s"
                params.append(search_term)

        sort_col_db = self.sort_column
        if sort_col_db not in select_cols_list and sort_col_db != 'id': sort_col_db = 'data' 
        sort_dir = 'ASC' if self.sort_direction == 'ASC' else 'DESC'
        query += f" ORDER BY {sort_col_db} {sort_dir}"
        if sort_col_db != 'id': query += ", id ASC"

        logging.debug(f"DEBUG_REFRESH_TABLE: Query: {query}, Params: {params}")
        all_rows = self.db_handler.fetch_all_dict(query, tuple(params))
        logging.debug(f"DEBUG_REFRESH_TABLE: Număr rânduri returnate: {len(all_rows if all_rows else [])}")

        if all_rows:
            for row_dict in all_rows:
                # --- ÎNTREG ACEST BLOC TREBUIE SĂ FIE ÎN INTERIORUL BUCLEI FOR ---
                values = []
                for col_name in self.treeview_display_columns: 
                    val = row_dict.get(col_name)
                    if col_name == 'data' and isinstance(val, (datetime, date)):
                        values.append(val.strftime('%Y-%m-%d'))
                    elif col_name == 'suma' and val is not None:
                        try:
                            values.append(f"{float(val):.2f}") 
                        except ValueError:
                            values.append(str(val))
                    else:
                        values.append(str(val) if val is not None else "")
                
                tags_to_apply = ()
                if row_dict.get('tip') == 'credit':
                    tags_to_apply = ('credit_row',)
                elif row_dict.get('tip') == 'debit':
                    tags_to_apply = ('debit_row',)
                
                if self.tree.winfo_exists():
                    self.tree.insert('', 'end', values=tuple(values), tags=tags_to_apply, iid=row_dict['id'])
                # --- SFÂRȘITUL BLOCULUI CARE TREBUIE SĂ FIE ÎN BUCĂL ---
        
        self.update_sort_indicator()
        self._update_status_label()
        self._calculate_and_update_totals() 
        logging.debug("DEBUG_REFRESH_TABLE: Tabel reîmprospătat.")

    def _calculate_and_update_totals(self):
        """
        Calculează și actualizează totalurile pentru intrări, ieșiri și sold
        pe baza tranzacțiilor afișate și a monedei contului activ.
        """
        if not (hasattr(self, 'tree') and self.tree.winfo_exists()):
            return

        # --- MODIFICARE: Preluăm moneda contului activ ---
        active_account_currency = "RON" # Valoare implicită în caz de eroare
        if self.active_account_id and self.accounts_list:
            active_account = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
            if active_account and active_account.get('valuta'):
                active_account_currency = active_account.get('valuta')
        # --- SFÂRȘIT MODIFICARE ---

        total_credit = 0.0
        total_debit = 0.0

        try:
            suma_col_index = self.treeview_display_columns.index('suma')
            tip_col_index = self.treeview_display_columns.index('tip')
        except ValueError:
            logging.debug("EROARE: Coloanele 'suma' sau 'tip' nu sunt în treeview_display_columns. Nu se pot calcula totalurile.")
            return

        for item_id in self.tree.get_children(""):
            try:
                item_values = self.tree.item(item_id, 'values')
                suma_str = item_values[suma_col_index]
                tip_str = item_values[tip_col_index]
                suma_val = float(suma_str)

                if tip_str == 'credit':
                    total_credit += suma_val
                elif tip_str == 'debit':
                    total_debit += suma_val
            except (ValueError, IndexError) as e:
                logging.warning(f"Atenție: Rândul cu ID {item_id} nu a putut fi procesat pentru calculul totalurilor: {e}")
                continue
        
        sold = total_credit - total_debit

        # --- MODIFICARE: Folosim moneda dinamică la formatarea textului ---
        total_credit_str = f"{total_credit:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        total_debit_str = f"{total_debit:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        sold_str = f"{sold:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        # --- SFÂRȘIT MODIFICARE ---

        if hasattr(self, 'total_credit_label') and self.total_credit_label.winfo_exists():
            self.total_credit_label.config(text=total_credit_str)
        
        if hasattr(self, 'total_debit_label') and self.total_debit_label.winfo_exists():
            self.total_debit_label.config(text=total_debit_str)
        
        if hasattr(self, 'sold_label') and self.sold_label.winfo_exists():
            self.sold_label.config(text=sold_str)
            sold_color = "black"
            if sold > 0:
                sold_color = "#006400" # Verde închis
            elif sold < 0:
                sold_color = "#8B0000" # Roșu închis
            self.sold_label.config(foreground=sold_color)

    def prompt_for_mariadb_credentials(self):
        success = False
        dialog = MariaDBConfigDialog(self.master, "Configurare Conexiune MariaDB", 
                                     initial_host=self.db_host, initial_port=self.db_port, 
                                     initial_dbname=self.db_name, initial_user=self.db_user, 
                                     initial_password=self.db_password)
        result = dialog.result
        
        if not self.master.winfo_exists(): return False
        self.master.update_idletasks() 

        if result:
            creds = result
            if not all([creds["host"], creds["port"], creds["dbname"], creds["user"]]):
                if self.master.winfo_exists(): messagebox.showerror("Date Incomplete", "Toate câmpurile (excepție parola) sunt obligatorii.", parent=self.master)
            else:
                self.db_host, self.db_name, self.db_user, self.db_password = creds["host"].strip(), creds["dbname"].strip(), creds["user"].strip(), creds["password"]
                try: self.db_port = int(creds["port"].strip())
                except ValueError: 
                    self.db_port = 3306
                    if self.master.winfo_exists(): messagebox.showwarning("Port Invalid", f"Portul '{creds['port'].strip()}' este invalid. Se folosește 3306.", parent=self.master)
                
                if self.connect_to_db():
                    config_management.save_app_config(self)
                    success = True
        return success

    def handle_db_config_from_menu(self):
        if self.db_handler:
            self.db_handler.close_connection()
            self.db_handler = None
        
        prompt_successful = self.prompt_for_mariadb_credentials()
        
        if not self.master.winfo_exists(): return
        self.master.update_idletasks()

        if prompt_successful:
            if hasattr(self, 'status_label') and self.status_label.winfo_exists(): self.status_label.config(text="Actualizare după reconfigurare DB...")
            self.master.update_idletasks()
            
            # Resetare completă a stării UI
            self.active_account_id = None
            self.accounts_list = []
            self.account_combo_var.set("")
            self.total_transaction_count = 0
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            self._applying_nav_selection = False

            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.get_children(""): self.nav_tree.delete(item)
            if hasattr(self, 'tree') and self.tree.winfo_exists():
                for item in self.tree.get_children(""): self.tree.delete(item)

            self.master.after(10, self.init_step3_check_table) 
            
            if self.master.winfo_exists(): messagebox.showinfo("Configurare Reușită", "Conexiunea la baza de date a fost actualizată.", parent=self.master)
        else: 
            if not (self.db_handler and self.db_handler.is_connected()):
                if hasattr(self, 'status_label') and self.status_label.winfo_exists(): self.status_label.config(text="Configurare anulată/eșuată. Nicio conexiune DB.")
                self._toggle_action_buttons('disabled')
# Continuare Clasa BTViewerApp

    def _schedule_ui_population_steps(self, config_parser_for_filters, context_msg=""):
        if not self.master.winfo_exists(): return
        logging.debug(f"DEBUG: _schedule_ui_population_steps - Context: {context_msg}")

        # Acestea vor folosi self.active_account_id dacă e setat.
        # Ele sunt deja apelate de refresh_ui_for_account_change, dar un apel aici asigură
        # că sunt populate la pornirea inițială.
        self.master.after(0, self._populate_nav_tree) 
        self.master.after(20, self.update_total_count)   
        
        self.master.after(40, lambda: self._load_and_apply_filters_from_config(config_parser_for_filters))
        
        self.master.after(70, self.update_sort_indicator)
        self.master.after(100, lambda: {
            self.status_label.config(text="Pregătit.") if hasattr(self,'status_label') and self.status_label.winfo_exists() else None,
            self._toggle_action_buttons('normal' if self.db_handler and self.db_handler.is_connected() and self.active_account_id else 'disabled')
        })

    def _populate_nav_tree(self):
        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            for item in self.nav_tree.get_children(""): self.nav_tree.delete(item)
        else: return

        if not (self.db_handler and self.db_handler.is_connected() and self.active_account_id):
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                self.nav_tree.insert("", "end", text="Selectați un cont", iid="no_data_root_disconnected_or_no_account")
            return

        query_years = "SELECT DISTINCT YEAR(data) as an FROM tranzactii WHERE data IS NOT NULL AND id_cont_fk = %s"
        params_years = [self.active_account_id]
        if self.visible_tx_codes:
            placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
            query_years += f" AND cod_tranzactie_fk IN ({placeholders})"
            params_years.extend(self.visible_tx_codes)
        else: query_years += " AND 1=0"
        query_years += " ORDER BY an DESC"
        
        years_data_dicts = self.db_handler.fetch_all_dict(query_years, tuple(params_years))

        if not years_data_dicts:
            if self.nav_tree.winfo_exists(): self.nav_tree.insert("", "end", text="Nicio tranzacție vizibilă", iid="no_data_root"); return

        for year_dict in years_data_dicts:
            year_val = year_dict.get('an')
            if year_val is None: continue
            
            query_count = "SELECT COUNT(*) FROM tranzactii WHERE YEAR(data) = %s AND id_cont_fk = %s"
            params_count = [year_val, self.active_account_id]
            if self.visible_tx_codes:
                placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
                query_count += f" AND cod_tranzactie_fk IN ({placeholders})"
                params_count.extend(self.visible_tx_codes)
            else: query_count += " AND 1=0"
            
            year_tx_count = self.db_handler.fetch_scalar(query_count, tuple(params_count)) or 0

            if year_tx_count > 0: # Afișăm anul doar dacă are tranzacții vizibile
                year_display_text = f"Anul {year_val} ({year_tx_count} tranzacții)"
                year_node_iid = f"year_{year_val}"
                if self.nav_tree.winfo_exists():
                    self.nav_tree.insert("", "end", text=year_display_text, iid=year_node_iid, open=False, tags=('year_node',))
                    self.nav_tree.insert(year_node_iid, "end", text="  (Încarcă lunile...)", iid=f"placeholder_months_{year_val}", tags=('month_node',))

    def _on_nav_tree_expand_or_double_click(self, event=None, item_to_expand=None):
        if not (hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists() and self.db_handler and self.db_handler.is_connected() and self.active_account_id): return
        
        item_id = item_to_expand or (self.nav_tree.focus() if self.nav_tree.winfo_exists() else None)
        if not item_id or item_id.startswith("placeholder_"): return
        
        is_open_event = event is not None and hasattr(event, 'type') and str(event.type) == 'TreeviewOpen'

        # Construim clauza de filtrare o singură dată
        filter_clause = ""
        params_filter = []
        if self.visible_tx_codes:
            placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
            filter_clause = f" AND cod_tranzactie_fk IN ({placeholders})"
            params_filter.extend(self.visible_tx_codes)
        else: filter_clause = " AND 1=0"

        if item_id.startswith("year_") and "month" not in item_id:
            year_str = item_id.split('_')[1]; year_val = int(year_str)
            placeholder_iid = f"placeholder_months_{year_str}"
            if self.nav_tree.exists(placeholder_iid):
                self.nav_tree.delete(placeholder_iid)
                query = f"SELECT DISTINCT MONTH(data) as luna FROM tranzactii WHERE YEAR(data) = %s AND id_cont_fk = %s {filter_clause} ORDER BY luna ASC"
                params = [year_val, self.active_account_id] + params_filter
                months_dicts = self.db_handler.fetch_all_dict(query, tuple(params))
                for month_dict in months_dicts:
                    month_idx = month_dict['luna']
                    query_count = f"SELECT COUNT(*) FROM tranzactii WHERE YEAR(data) = %s AND MONTH(data) = %s AND id_cont_fk = %s {filter_clause}"
                    params_count = [year_val, month_idx, self.active_account_id] + params_filter
                    month_tx_count = self.db_handler.fetch_scalar(query_count, tuple(params_count)) or 0
                    if month_tx_count > 0:
                        month_name = self.reverse_month_map_for_nav.get(month_idx, f"Luna {month_idx}")
                        month_iid = f"{item_id}_month_{month_idx:02d}"
                        self.nav_tree.insert(item_id, "end", text=f"  {month_name} ({month_tx_count} tranzacții)", iid=month_iid, open=False, tags=('month_node',))
                        self.nav_tree.insert(month_iid, "end", text="    (Încarcă zile...)", iid=f"placeholder_days_{year_str}_{month_idx:02d}", tags=('day_node',))

        elif "month" in item_id:
            parts = item_id.split('_'); year_val, month_idx = int(parts[1]), int(parts[3])
            placeholder_iid = f"placeholder_days_{year_val}_{month_idx:02d}"
            if self.nav_tree.exists(placeholder_iid):
                self.nav_tree.delete(placeholder_iid)
                query = f"SELECT DISTINCT DAY(data) as zi FROM tranzactii WHERE YEAR(data) = %s AND MONTH(data) = %s AND id_cont_fk = %s {filter_clause} ORDER BY zi ASC"
                params = [year_val, month_idx, self.active_account_id] + params_filter
                days_dicts = self.db_handler.fetch_all_dict(query, tuple(params))
                for day_dict in days_dicts:
                    day_val = day_dict['zi']
                    
                    # --- ADAUGARE: Interogare pentru a număra tranzacțiile pentru fiecare zi ---
                    query_count_day = f"SELECT COUNT(*) FROM tranzactii WHERE YEAR(data) = %s AND MONTH(data) = %s AND DAY(data) = %s AND id_cont_fk = %s {filter_clause}"
                    params_count_day = [year_val, month_idx, day_val, self.active_account_id] + params_filter
                    day_tx_count = self.db_handler.fetch_scalar(query_count_day, tuple(params_count_day)) or 0
                    # -------------------------------------------------------------------------
                    
                    if day_tx_count > 0:
                        # --- MODIFICARE: Adăugăm numărul de tranzacții la textul afișat ---
                        day_display_text = f"    {day_val:02d} ({day_tx_count} tranzacții)"
                        day_iid = f"{item_id}_day_{day_val:02d}"
                        self.nav_tree.insert(item_id, "end", text=day_display_text, iid=day_iid, tags=('day_node',))
                        # --------------------------------------------------------------------

        if not is_open_event and self.nav_tree.exists(item_id):
            self.nav_tree.item(item_id, open=not self.nav_tree.item(item_id, "open"))

    def _toggle_filter_mode(self):
        """
        Actualizează starea vizuală a controalelor de filtrare și declanșează un refresh,
        prevenind buclele de evenimente.
        """
        if self._programmatic_change:
            return # Ieși dacă schimbarea este inițiată de altă parte a codului

        is_range_mode = self.date_range_mode_var.get()
        logging.debug(f"DEBUG_FILTER_MODE: Intrat în _toggle_filter_mode. Modul este acum: {'Interval Dată' if is_range_mode else 'Navigare'}")
        
        # Setăm flag-ul pentru a indica o schimbare programatică
        self._programmatic_change = True

        if is_range_mode:
            # Activează modul "Interval Dată"
            if hasattr(self, 'start_date'): self.start_date.config(state='normal')
            if hasattr(self, 'end_date'): self.end_date.config(state='normal')
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                style = ttk.Style()
                style.configure("nav.Treeview", foreground="#aaaaaa")
                self.nav_tree.config(style="nav.Treeview")
                for item_sel in self.nav_tree.selection():
                    self.nav_tree.selection_remove(item_sel) # Aceasta declanșează evenimentul
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            self.refresh_table()
        else:
            # Activează modul "Navigare"
            if hasattr(self, 'start_date'): self.start_date.config(state='disabled')
            if hasattr(self, 'end_date'): self.end_date.config(state='disabled')
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                style = ttk.Style()
                style.configure("nav.Treeview", foreground="black")
                self.nav_tree.config(style="nav.Treeview")
            self._apply_nav_selection_to_datepickers_and_refresh()
        
        # Resetăm flag-ul după ce toate acțiunile s-au încheiat
        self.master.after(10, lambda: setattr(self, '_programmatic_change', False))

    def _on_nav_tree_select(self, event=None):
        if self._programmatic_change:
            logging.debug("DEBUG: _on_nav_tree_select - Apel anulat de flag-ul _programmatic_change.")
            return
        if self._applying_nav_selection:
            return

        logging.debug("DEBUG: _on_nav_tree_select - Apelat de utilizator.")
        if self.date_range_mode_var.get():
            self._programmatic_change = True # Setăm flag-ul pentru a controla lanțul
            self.date_range_mode_var.set(False) # Comută pe modul Navigare
            self._toggle_filter_mode() # Aplică schimbarea
            # Flag-ul va fi resetat la sfârșitul _toggle_filter_mode
        else:
            self._apply_nav_selection_to_datepickers_and_refresh()

    def _apply_nav_selection_to_datepickers_and_refresh(self, nav_item_id_to_process=None):
        if not hasattr(self, 'nav_tree') or not self.nav_tree.winfo_exists(): self._applying_nav_selection = False; return
        if self._applying_nav_selection and not nav_item_id_to_process : self._applying_nav_selection = False; return
        
        self._applying_nav_selection = True

        selected_item_id = nav_item_id_to_process or (self.nav_tree.focus() if self.nav_tree.winfo_exists() else None)
        start_dt_to_set, end_dt_to_set = None, None

        if not selected_item_id or selected_item_id.startswith("placeholder_") or \
           selected_item_id.endswith(("_err_", "_no_months", "_no_days", "_empty", "_disconnected_or_no_account")):
            if selected_item_id == "no_data_root" or selected_item_id == "no_data_root_disconnected_or_no_account":
                self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
                self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            self._applying_nav_selection = False
            return

        current_nav_year, current_nav_month_idx, current_nav_day = None, 0, 0
        parts = selected_item_id.split("_")
        try:
            if parts[0] == "year": current_nav_year = int(parts[1])
            if len(parts) > 2 and parts[2] == "month": current_nav_month_idx = int(parts[3])
            if len(parts) > 4 and parts[4] == "day": current_nav_day = int(parts[5])
            
            if current_nav_year:
                self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = current_nav_year, current_nav_month_idx, current_nav_day
                if current_nav_month_idx == 0: start_dt_to_set, end_dt_to_set = date(current_nav_year, 1, 1), date(current_nav_year, 12, 31)
                else:
                    if current_nav_day == 0: 
                        _, num_days = calendar.monthrange(current_nav_year, current_nav_month_idx)
                        start_dt_to_set, end_dt_to_set = date(current_nav_year, current_nav_month_idx, 1), date(current_nav_year, current_nav_month_idx, num_days)
                    else: 
                        start_dt_to_set = end_dt_to_set = date(current_nav_year, current_nav_month_idx, current_nav_day)
            
            if start_dt_to_set and end_dt_to_set and hasattr(self, 'start_date') and self.start_date.winfo_exists() and hasattr(self, 'end_date') and self.end_date.winfo_exists():
                self.start_date.set_date(start_dt_to_set)
                self.end_date.set_date(end_dt_to_set)
            else:
                self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True) 
                if hasattr(self, 'start_date') and self.start_date.winfo_exists(): start_dt_to_set = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.winfo_exists(): end_dt_to_set = self.end_date.get_date()
        except (IndexError, ValueError) as e_parse: 
            logging.error(f"Eroare parsare ID navigație '{selected_item_id}': {e_parse}")
            self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            start_dt_to_set, end_dt_to_set = self.start_date.get_date(), self.end_date.get_date()
        except Exception as e_apply_nav: 
            logging.error(f"Eroare în _apply_nav_selection: {e_apply_nav}")
            self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            start_dt_to_set, end_dt_to_set = self.start_date.get_date(), self.end_date.get_date()
        
        if self.master.winfo_exists(): self.master.update_idletasks()
        self.refresh_table(start_date_override=start_dt_to_set, end_date_override=end_dt_to_set)
        self._applying_nav_selection = False

    def on_date_picker_change(self, event=None):
        if self.date_range_mode_var.get(): 
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)
            self._current_processed_nav_iid = None
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            self.refresh_table()

    def on_filter_change(self, event=None): 
        self.refresh_table()

    def schedule_search(self, event=None):
        if self.search_job: self.master.after_cancel(self.search_job)
        self.search_job = self.master.after(400, self.refresh_table)

    def toggle_sort(self, column_name):
        if self.sort_column == column_name: self.sort_direction = 'ASC' if self.sort_direction == 'DESC' else 'DESC'
        else: self.sort_column, self.sort_direction = column_name, ('ASC' if column_name != 'data' else 'DESC')
        self.update_sort_indicator()
        self.refresh_table()

    def update_sort_indicator(self):
        if not (hasattr(self, 'tree') and self.tree.winfo_exists()): return
        arrow = ' ▼' if self.sort_direction == 'DESC' else ' ▲'
        for col in self.treeview_display_columns: 
            try: self.tree.heading(col, text=col.capitalize().replace("_", " "))
            except tk.TclError: pass
        
        if self.sort_column in self.treeview_display_columns:
            try: self.tree.heading(self.sort_column, text=f"{self.sort_column.capitalize().replace('_', ' ')}{arrow}")
            except tk.TclError: pass
# Continuare Clasa BTViewerApp

    def update_total_count(self):
        if self.db_handler and self.db_handler.is_connected() and self.active_account_id:
            query = "SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk = %s"
            params = [self.active_account_id]
            
            if self.visible_tx_codes:
                placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
                query += f" AND cod_tranzactie_fk IN ({placeholders})"
                params.extend(self.visible_tx_codes)
            else:
                query += " AND 1=0" # Dacă nu sunt tipuri vizibile, nu numărăm nimic
            
            self.total_transaction_count = self.db_handler.fetch_scalar(query, tuple(params)) or 0
        else:
            self.total_transaction_count = 0
        self._update_status_label()
            
    def set_date_range_to_db_bounds(self, called_by_nav_tree_logic=False):
        min_date_db, max_date_db = None, None
        if self.db_handler and self.db_handler.is_connected() and self.active_account_id:
            query_bounds = "SELECT MIN(data) as min_d, MAX(data) as max_d FROM tranzactii WHERE id_cont_fk = %s"
            row = self.db_handler.fetch_one_dict(query_bounds, (self.active_account_id,))
            if row: min_date_db, max_date_db = row.get('min_d'), row.get('max_d')
        
        final_start, final_end = (min_date_db or date.today()), (max_date_db or date.today())
        
        if hasattr(self, 'start_date') and self.start_date.winfo_exists() and hasattr(self, 'end_date') and self.end_date.winfo_exists():
            try:
                self.start_date.unbind("<<DateEntrySelected>>"); self.end_date.unbind("<<DateEntrySelected>>")
                self.start_date.set_date(final_start); self.end_date.set_date(final_end)
                self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change); self.end_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
            except tk.TclError: logging.debug("DEBUG: TclError în set_date_range_to_db_bounds la set_date.")
            except Exception as e_sdr: logging.debug(f"DEBUG: Eroare în set_date_range_to_db_bounds: {e_sdr}")
        
        if not called_by_nav_tree_logic:
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)

    def reset_filters(self):
        """Resetează toate filtrele la starea lor inițială."""
        logging.debug("DEBUG: reset_filters - Apelat.")
        
        # Resetează variabilele de căutare și tip
        self.search_var.set("")
        self.type_var.set("Toate")
        self.search_column_var.set("Toate coloanele")
        
        # Dacă eram în modul interval de dată, comutăm înapoi la modul de navigare
        if self.date_range_mode_var.get():
            self.date_range_mode_var.set(False)
            # Nu mai apelăm _toggle_filter_mode de aici pentru a evita apeluri în cascadă.
            # Logica de mai jos va face refresh-ul necesar.

        # Dezactivează selectorii de dată și reactivează arborele de navigație
        if hasattr(self, 'start_date'): self.start_date.config(state='disabled')
        if hasattr(self, 'end_date'): self.end_date.config(state='disabled')
        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            style = ttk.Style()
            style.configure("nav.Treeview", foreground="black")
            self.nav_tree.config(style="nav.Treeview")

        # Golește selecția curentă din arbore și resetează variabilele de navigație
        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            for item in self.nav_tree.selection():
                self.nav_tree.selection_remove(item)
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        
        # Setează datele la limitele maxime ale contului activ
        self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
        
        # Forțează un refresh final cu starea resetată
        self.refresh_table()


    def show_transaction_details(self, event):
        if not hasattr(self, 'tree') or not self.tree.winfo_exists(): return
        item_id_str = self.tree.focus()
        if not item_id_str or item_id_str.startswith("sep_"): return 
        try: item_id = int(item_id_str)
        except ValueError: print(f"ID tranzacție invalid: {item_id_str}"); return

        if not (self.db_handler and self.db_handler.is_connected()): messagebox.showerror("Eroare DB", "Nu există conexiune.", parent=self.master); return
        transaction_data = self.db_handler.fetch_one_dict("SELECT * FROM tranzactii WHERE id = %s", (item_id,))
        if not transaction_data: messagebox.showerror("Eroare", f"Tranzacția ID: {item_id} nu a fost găsită.", parent=self.master); return
        
        # NOU: Preluăm moneda contului activ
        active_account_currency = "RON" # Fallback
        if self.active_account_id and self.accounts_list:
            active_account = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
            if active_account and active_account.get('valuta'):
                active_account_currency = active_account.get('valuta')

        details_window = tk.Toplevel(self.master)
        details_window.title(f"Detalii Tranzacție ID: {item_id}")
        details_window.transient(self.master)
        details_window.grab_set()
        main_frame = ttk.Frame(details_window, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)
        row_idx, obs_text_widget = 0, None

        # --- MODIFICARE: Reintroducem soldurile și adăugăm noul sold curent ---
        labels_to_display = [
            ("ID:", "id"), ("Dată:", "data"), ("Sumă:", "suma"), ("Tip:", "tip"),
            ("Sold după Tranzacție:", "sold_dupa_tranzactie"),
            ("Sold Inițial (Extras):", "sold_initial"), 
            ("Sold Final (Extras):", "sold_final"),
            ("Beneficiar:", "beneficiar"), ("CIF:", "cif"), ("Factură:", "factura"),
            ("Cont Partener:", "cont"), ("TID:", "tid"), ("RRN:", "rrn"),
            ("PAN Mascat:", "pan"), ("Descriere completă:", "descriere"), ("Observații (editabil):", "observatii")
        ]
        # ------------------------------------------------------------------
        
        for label_text, col_name in labels_to_display:
            value = transaction_data.get(col_name)
            if col_name != "observatii" and value is None: continue
            if isinstance(value, str) and not value.strip(): continue

            ttk.Label(main_frame, text=label_text, font=('TkDefaultFont', 10, 'bold')).grid(row=row_idx, column=0, sticky='nw', padx=5, pady=(2,0))
            if col_name == "observatii":
                obs_text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=5, font=('TkDefaultFont', 10))
                obs_text_widget.grid(row=row_idx, column=1, sticky='nwe', padx=5, pady=(2,0))
                obs_text_widget.insert(tk.END, str(value) if value is not None else "")
            else:
                value_text = str(value) if value is not None else ""
                font_style = ('TkDefaultFont', 10)
                text_color = 'black'
                wrap_len = 0
                if isinstance(value, date): value_text = value.strftime('%d-%m-%Y')
                
                if col_name in ["suma", "sold_initial", "sold_final", "sold_dupa_tranzactie"]:
                    try:
                        # MODIFICAT: Folosim moneda dinamică
                        value_text = f"{float(value):,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
                        font_style = ('TkDefaultFont', 10, 'bold')
                        if col_name == "suma":
                            text_color = '#006400' if transaction_data.get('tip') == 'credit' else '#8B0000'
                    except (ValueError, TypeError):
                        # MODIFICAT: Folosim moneda dinamică și aici
                        value_text = str(value) + f" {active_account_currency}"
                elif col_name == "tip":
                    font_style = ('TkDefaultFont', 10, 'bold')
                    text_color = '#006400' if value == 'credit' else '#8B0000'
                elif col_name == "descriere":
                    wrap_len = 450
                
                value_label = ttk.Label(main_frame, text=value_text, font=font_style, foreground=text_color)
                if wrap_len > 0: value_label.config(wraplength=wrap_len, justify='left')
                value_label.grid(row=row_idx, column=1, sticky='nw', padx=5, pady=(2,0))
            row_idx += 1
            
        main_frame.grid_columnconfigure(1, weight=1)
        button_frame_details = ttk.Frame(main_frame)
        button_frame_details.grid(row=row_idx, column=0, columnspan=2, pady=(15,5), sticky='e')
        ttk.Button(button_frame_details, text="Salvează Observații", command=lambda: self._save_observation_and_close(item_id, obs_text_widget, details_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame_details, text="Închide", command=details_window.destroy).pack(side=tk.LEFT, padx=5)
        details_window.update_idletasks()
        master_x, master_y, master_w, master_h = self.master.winfo_x(), self.master.winfo_y(), self.master.winfo_width(), self.master.winfo_height()
        win_w, win_h = details_window.winfo_width(), details_window.winfo_height()
        details_window.geometry(f"+{max(0, master_x + (master_w - win_w) // 2)}+{max(0, master_y + (master_h - win_h) // 2)}")
        details_window.focus_set()
        if obs_text_widget: obs_text_widget.focus_set()

    def _save_observation_and_close(self, transaction_id, text_widget, window_to_close):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showerror("Eroare DB", "Fără conexiune DB.", parent=window_to_close)
            return
        observation_text = text_widget.get("1.0", "end-1c").strip()
        if len(observation_text) > 300:
            messagebox.showwarning("Observație Prea Lungă", f"Text ({len(observation_text)}) depășește limita de 300.", parent=window_to_close)
            return
        if self.db_handler.execute_commit("UPDATE tranzactii SET observatii = %s WHERE id = %s", (observation_text, transaction_id)):
            self.refresh_table()
            window_to_close.destroy()

    def _toggle_action_buttons(self, state_str):
        final_state = tk.NORMAL if state_str == 'normal' else tk.DISABLED
        if hasattr(self, 'action_buttons'):
            for btn in self.action_buttons:
                if isinstance(btn, (tk.Button, ttk.Button)) and btn.winfo_exists():
                    try: btn.config(state=final_state)
                    except tk.TclError: pass
        if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
             try: self.account_selector_combo.config(state="readonly" if final_state == tk.NORMAL and self.accounts_list else "disabled")
             except tk.TclError: pass
# Continuare Clasa BTViewerApp

    def export_to_excel(self):
        if not (self.db_handler and self.db_handler.is_connected() and self.active_account_id):
            messagebox.showwarning("Fără Conexiune / Cont", "Vă rugăm selectați un cont și asigurați o conexiune la baza de date.", parent=self.master)
            return

        file_path = filedialog.asksaveasfilename(
            master=self.master,
            title="Salvare Export Excel",
            defaultextension=".xlsx", 
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if not file_path:
            return

        self._toggle_action_buttons('disabled')

        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = \
            file_processing.create_progress_window(self.master, "Export în Desfășurare", "Se pregătește exportul datelor...")

        if self.current_progress_bar and self.current_progress_bar.winfo_exists():
            self.current_progress_bar.config(mode='indeterminate')
            self.current_progress_bar.start(10)
        
        select_clause_export = "data, descriere, observatii, suma, tip, cif, factura, beneficiar, cont, sold_initial, sold_final"
        query = f"SELECT {select_clause_export} FROM tranzactii WHERE id_cont_fk = %s"
        params = [self.active_account_id]

        start_date_for_export, end_date_for_export = None, None
        if self.date_range_mode_var.get():
            if hasattr(self, 'start_date') and self.start_date.winfo_exists() and self.start_date.get(): 
                start_date_for_export = self.start_date.get_date()
            if hasattr(self, 'end_date') and self.end_date.winfo_exists() and self.end_date.get(): 
                end_date_for_export = self.end_date.get_date()
        elif self.nav_selected_year is not None:
            current_year, current_month, current_day = self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day
            if current_month == 0:
                start_date_for_export, end_date_for_export = date(current_year, 1, 1), date(current_year, 12, 31)
            else:
                if current_day == 0:
                    _, num_days = calendar.monthrange(current_year, current_month)
                    start_date_for_export, end_date_for_export = date(current_year, current_month, 1), date(current_year, current_month, num_days)
                else:
                    start_date_for_export = end_date_for_export = date(current_year, current_month, current_day)
        
        if start_date_for_export: query += " AND data >= %s"; params.append(start_date_for_export.strftime('%Y-%m-%d'))
        if end_date_for_export: query += " AND data <= %s"; params.append(end_date_for_export.strftime('%Y-%m-%d'))
        if self.type_var.get() != "Toate": query += " AND tip = %s"; params.append(self.type_var.get())
        if self.search_var.get():
            col_map = {"Beneficiar": "beneficiar", "CIF": "cif", "Factura": "factura", "Descriere": "descriere", "Observatii": "observatii"}
            search_col_key = self.search_column_var.get(); search_col = col_map.get(search_col_key, "descriere")
            query += f" AND {search_col} LIKE %s"; params.append(f"%{self.search_var.get()}%")

        sort_col_export = self.sort_column
        sort_dir_export = self.sort_direction
        query += f" ORDER BY {sort_col_export} {sort_dir_export}"
        if sort_col_export != 'id': query += ", id ASC"
        
        self.export_thread = threading.Thread(
            target=threaded_export_worker,
            args=(self, query, tuple(params), file_path, self.queue)
        )
        self.export_thread.daemon = True
        self.export_thread.start()
        if self.master.winfo_exists():
            self.master.after(100, self._check_export_progress)

    def _check_export_progress(self):
        try:
            msg = self.queue.get_nowait()
            msg_type = msg[0]

            if msg_type == "status": 
                if hasattr(self, 'current_progress_win') and self.current_progress_win and self.current_progress_win.winfo_exists(): 
                    if hasattr(self, 'current_progress_status_label_widget') and self.current_progress_status_label_widget and self.current_progress_status_label_widget.winfo_exists(): 
                        self.current_progress_status_label_widget.config(text=msg[1])
                if self.master.winfo_exists(): self.master.after(100, self._check_export_progress)
            elif msg_type == "done": 
                self._toggle_action_buttons('normal')
                if self.master.winfo_exists(): self.master.after(10, lambda: self._finalize_export_ui(f"Datele au fost exportate cu succes în:\n{msg[1]}", True))
            elif msg_type == "error": 
                self._toggle_action_buttons('normal')
                if self.master.winfo_exists(): self.master.after(10, lambda: self._finalize_export_ui(msg[1], False))
        except Empty:
            if hasattr(self, 'export_thread') and self.export_thread and self.export_thread.is_alive():
                if self.master.winfo_exists(): self.master.after(100, self._check_export_progress)
            else:
                logging.debug("DEBUG: Thread-ul de export s-a terminat, dar nu s-a primit mesaj 'done'/'error'.")
                self._toggle_action_buttons('normal')
        except tk.TclError as e:
            print(f"TclError în _check_export_progress: {e}")
        except Exception as e_general:
            logging.error(f"Eroare generală în _check_export_progress: {e_general}")
            if hasattr(self, 'current_progress_win') and self.current_progress_win and self.current_progress_win.winfo_exists():
                try: self.current_progress_win.destroy()
                except tk.TclError: pass
            self._toggle_action_buttons('normal')

    def _finalize_export_ui(self, message, success):
        logging.debug(f"DEBUG_PROGRESS: Intrat în _finalize_export_ui.")
        if hasattr(self, 'current_progress_win') and self.current_progress_win:
            try:
                if self.current_progress_win.winfo_exists():
                    if hasattr(self, 'current_progress_bar') and self.current_progress_bar and self.current_progress_bar.winfo_exists():
                        self.current_progress_bar.stop()
                    self.current_progress_win.destroy()
                    logging.debug("DEBUG_PROGRESS: Fereastra de progres export închisă.")
            except tk.TclError: pass
            except Exception as e_fin_exp: logging.debug(f"DEBUG_PROGRESS: Eroare în _finalize_export_ui: {e_fin_exp}")

        self.current_progress_win = None
        self.current_progress_bar = None
        self.current_progress_status_label_widget = None
        self.export_thread = None
        
        if self.master.winfo_exists():
            if success:
                messagebox.showinfo("Export Finalizat", message, parent=self.master)
            else:
                messagebox.showerror("Eroare la Export", message, parent=self.master)
# Continuare Clasa BTViewerApp

    def exit_app(self, message=None):
        """Închide aplicația, afișând un mesaj opțional."""
        if message and hasattr(self, 'master') and self.master.winfo_exists():
            try:
                messagebox.showerror("Închidere Aplicație", message, parent=self.master)
            except tk.TclError:
                print(f"INFO: Nu s-a putut afișa mesajul de ieșire (fereastra master indisponibilă): {message}")
        
        # Închiderea aplicației se face prin ui_utils.handle_app_exit, care e mai completă.
        # Acest exit_app este mai mult un fallback pentru erori fatale.
        # Apelul corect se face din protocolul WM_DELETE_WINDOW.
        # Aici doar ne asigurăm că resursele sunt eliberate.
        if hasattr(self, 'db_handler') and self.db_handler: 
            self.db_handler.close_connection()
        
        if hasattr(self, 'master') and self.master.winfo_exists():
            try:
                self.master.destroy()
            except tk.TclError:
                pass # Fereastra ar putea fi deja în proces de închidere

# --- Sfârșitul Definiției Clasei BTViewerApp ---


# --- Blocul Principal de Execuție ---
if __name__ == "__main__":

    # --- AICI SE ADAUGĂ CONFIGURAREA LOGGING ---
    # Această configurație stabilește setările de bază pentru întreaga aplicație.
    # CORECȚIE: Definim calea către fișierul de log înainte de a o folosi.
    # Folosim directorul specific aplicației, determinat în config_management.py
    log_file_path = os.path.join(APP_DATA_DIR, 'app_activity.log')

    # Această configurație stabilește setările de bază pentru întreaga aplicație.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s',
        filename=log_file_path,  # Acum variabila 'log_file_path' există și are o valoare validă.
        filemode='w',
        encoding='utf-8' # Este o practică bună să specificăm encoding-ul
    )
    # -------------------------------------------

    root = tk.Tk()
    
    # Încărcarea și aplicarea geometriei ferestrei
    window_geom, zoomed = config_management.load_window_config_from_file()
    if window_geom and not zoomed:
        try:
            root.geometry(window_geom)
        except tk.TclError as e_geom:
            logging.error(f"Eroare la setarea geometriei salvate: {e_geom}. Se folosesc dimensiuni default.")
            root.geometry("1200x700")
    else: 
        try: 
            root.state('zoomed')
        except tk.TclError:
            # Fallback pentru sisteme care nu suportă 'zoomed'
            w_screen = root.winfo_screenwidth()
            h_screen = root.winfo_screenheight()
            root.geometry(f"{w_screen}x{h_screen}+0+0")

    app = BTViewerApp(root)

    # Protocolul de închidere, calea corectă pentru a gestiona închiderea normală
    if root.winfo_exists():
        root.protocol("WM_DELETE_WINDOW", lambda: ui_utils.handle_app_exit(app, root))
    
    try:
        # Pornește bucla principală de evenimente
        root.mainloop()
    except KeyboardInterrupt:
        # Gestionează cazul în care utilizatorul apasă Ctrl+C în consolă
        print("\nAplicație întreruptă (KeyboardInterrupt). Se închide...")
        # Asigură închiderea curată și aici
        if root.winfo_exists():
             ui_utils.handle_app_exit(app, root)
    except Exception as e_main:
        # Prinde alte erori neașteptate care ar putea opri mainloop
        logging.error(f"Eroare neașteptată în bucla principală (mainloop): {e_main}")
        if root.winfo_exists():
             ui_utils.handle_app_exit(app, root)
    # Am eliminat complet blocul 'finally' care cauza eroarea la închiderea normală.