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
    APP_DATA_DIR 
)
import re 
from queue import Queue, Empty 
import threading

# Importurile din modulele noastre
from app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, DEFAULT_TREEVIEW_DISPLAY_COLUMNS, MONTH_MAP_FOR_NAV, REVERSE_MONTH_MAP_FOR_NAV
import config_management
from db_handler import DatabaseHandler, MariaDBConfigDialog # Corectat, db_handler este aici
import file_processing 
from file_processing import extract_iban_from_mt940, threaded_import_worker, threaded_export_worker
import ui_utils
from ui_dialogs import AccountManagerDialog, AccountEditDialog, TransactionTypeManagerDialog, SMTPConfigDialog, BalanceReportConfigDialog, LoginDialog

# NOU: Importăm handler-ul de autentificare. Vom avea nevoie de el în pasul următor.
import auth_handler

class BTViewerApp:
    def _load_visible_transaction_types(self):
        """Încarcă din config.ini codurile de tranzacții vizibile."""
        if not (self.db_handler and self.db_handler.is_connected()):
            self.visible_tx_codes = []
            return

        visibility_settings = config_management.load_transaction_type_visibility()
        all_types = self.db_handler.fetch_all_dict("SELECT cod FROM tipuri_tranzactii")
        if not all_types:
            self.visible_tx_codes = []
            return

        all_codes = [item['cod'] for item in all_types]
        visible_codes = []
        for code in all_codes:
            if visibility_settings.get(code, True):
                visible_codes.append(code)

        self.visible_tx_codes = visible_codes

    def __init__(self, master, user_data, db_handler, config_parser):
        # --- Bloc de inițializare nou și corectat ---
        self.master = master
        self.current_user = user_data
        self.db_handler = db_handler
        self.config = config_parser # Stocăm obiectul de configurare pasat
        
        self.master.title(f"{APP_NAME} - Se încarcă datele...")

        # Inițializarea atributelor aplicației
        self.visible_tx_codes = [] 
        self._programmatic_change = False 
        self.import_batch_queue = [] 
        self.current_batch_info_for_message = None
        self.file_paths_for_import_ref = [] 
        self.smtp_config = {}
        self._applying_nav_selection = False
        self._prevent_on_account_selected_trigger = False
        
        self.active_account_id = None
        self.accounts_list = [] 
        self.account_combo_var = tk.StringVar()
        self.sort_column = 'data'
        self.sort_direction = 'DESC'
        self.total_transaction_count = 0
        self.search_job = None
        
        self.month_map_for_nav = MONTH_MAP_FOR_NAV
        self.reverse_month_map_for_nav = REVERSE_MONTH_MAP_FOR_NAV
        
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar(value="Toate coloanele")
        self.type_var = tk.StringVar(value="Toate")
        self.date_range_mode_var = tk.BooleanVar(value=False)
        
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        self._nav_select_job, self._current_processed_nav_iid = None, None
        
        self.treeview_display_columns = DEFAULT_TREEVIEW_DISPLAY_COLUMNS
        self.loaded_column_widths = config_management.read_column_widths_from_file()

        self.current_progress_win = None
        self.current_progress_bar = None
        self.current_progress_status_label_widget = None
        self.queue = Queue() 
        self.import_thread = None 
        self.export_thread = None 
        
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

        # Construim interfața grafică
        self.setup_ui()
        
        logging.debug("DEBUG_INIT: __init__ - UI setup complet. Se pornește popularea UI.")
        
        # Pornim direct popularea UI, deoarece DB este deja gata.
        self.init_step4_populate_ui()

    # NOU: Adăugați această metodă helper în clasa BTViewerApp
    def has_permission(self, permission_key):
        """Verifică dacă utilizatorul curent are o anumită permisiune."""
        if not self.current_user:
            return False
        # Administratorul are toate permisiunile
        if self.current_user.get('has_all_permissions'):
            return True
        # Verifică dacă permisiunea există în lista de permisiuni a utilizatorului
        return permission_key in self.current_user.get('permissions', [])
    
    # VECHI: Metodele init_step1_read_config, connect_to_db, 
    # init_step2_connect, init_step2b_prompt_credentials, și init_step3_check_table
    # pot fi ȘTERSE din clasa BTViewerApp, deoarece logica lor a fost mutată
    # în secvența de pornire.

    def configure_smtp(self):
        dialog = SMTPConfigDialog(self.master, initial_config=self.smtp_config)
        if dialog.result:
            self.smtp_config = dialog.result
            config_management.save_app_config(self) # Re-folosim functia existenta
            messagebox.showinfo("Configurare SMTP", "Setările SMTP au fost salvate.", parent=self.master)

    def manage_transaction_types(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Trebuie să fiți conectat la baza de date.", parent=self.master)
            return

        dialog = TransactionTypeManagerDialog(self.master, self.db_handler)
        self._load_visible_transaction_types()
        self.refresh_ui_for_account_change()
       
    def show_cash_flow_report(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date pentru a genera rapoarte.", parent=self.master)
            return
        
        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

        start_date, end_date = None, None

        if self.date_range_mode_var.get():
            try:
                if hasattr(self, 'start_date') and self.start_date.get():
                    start_date = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.get():
                    end_date = self.end_date.get_date()
            except Exception as e_get_date:
                 logging.warning(f"Atenție: Nu s-au putut prelua datele din DateEntry: {e_get_date}")
        else:
            if self.nav_selected_year:
                current_year, current_month, current_day = self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day
                
                if current_month == 0:
                    start_date = date(current_year, 1, 1)
                    end_date = date(current_year, 12, 31)
                else:
                    if current_day == 0:
                        _, num_days = calendar.monthrange(current_year, current_month)
                        start_date = date(current_year, current_month, 1)
                        end_date = date(current_year, current_month, num_days)
                    else:
                        start_date = end_date = date(current_year, current_month, current_day)

        if not start_date or not end_date:
            row = self.db_handler.fetch_one_dict(
                "SELECT MIN(data) as min_d, MAX(data) as max_d FROM tranzactii WHERE id_cont_fk = %s", 
                (self.active_account_id,)
            )
            if row:
                start_date = row.get('min_d') or date.today()
                end_date = row.get('max_d') or date.today()
            else:
                start_date = end_date = date.today()

        initial_context = {
            'active_account_id': self.active_account_id,
            'start_date': start_date,
            'end_date': end_date,
            'visible_tx_codes': self.visible_tx_codes
        }
        
        report_dialog = CashFlowReportDialog(self.master, self.db_handler, self.accounts_list, initial_context=initial_context, smtp_config=self.smtp_config)
    
    def show_balance_report(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date.", parent=self.master)
            return

        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

        config_dialog = BalanceReportConfigDialog(self.master, self, self.accounts_list)

        if config_dialog.result:
            report_config = config_dialog.result
            report_config['visible_tx_codes'] = self.visible_tx_codes
            BalanceEvolutionReportDialog(self.master, self.db_handler, self.smtp_config, report_config)

    def show_transaction_analysis_report(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showwarning("Fără Conexiune", "Vă rugăm asigurați o conexiune la baza de date.", parent=self.master)
            return

        if not self.accounts_list:
            messagebox.showwarning("Fără Conturi", "Nu există conturi definite pentru a genera rapoarte.", parent=self.master)
            return

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
            start_date, end_date = date.today().replace(day=1, month=1), date.today()

        active_account = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
        currency = active_account.get('valuta', 'RON') if active_account else 'RON'

        initial_context = {
            'active_account_id': self.active_account_id,
            'start_date': start_date,
            'end_date': end_date,
            'visible_tx_codes': self.visible_tx_codes,
            'accounts_list': self.accounts_list,
            'db_handler': self.db_handler,
            'currency': currency
        }

        TransactionAnalysisReportDialog(self.master, self.db_handler, initial_context)

    # =========================================================================
    # METODA MODIFICATĂ PENTRU A CORESPUNDE CU NOUL DB_HANDLER
    # =========================================================================
    
    def init_step4_populate_ui(self):
        if not self.master.winfo_exists(): return

        final_title = f"{APP_NAME} v{APP_VERSION} (client-server multicont)  |  {APP_COPYRIGHT}"
        self.master.title(final_title)

        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Se încarcă configurația conturilor...")
        if self.master.winfo_exists(): self.master.update_idletasks()

        self._populate_account_selector() 

        if self.master.winfo_exists():
            self.master.after(300, lambda: self._schedule_ui_population_steps(self.config, "(initial setup)"))

    def setup_ui(self):
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
        self.active_account_color_indicator = tk.Frame(account_selector_frame, width=20, height=20, relief=tk.SUNKEN, borderwidth=1, background="SystemButtonFace")
        self.active_account_color_indicator.pack(side=tk.LEFT, padx=(2, 5), pady=2)
        self.account_selector_combo = ttk.Combobox(account_selector_frame, textvariable=self.account_combo_var, state="disabled", width=45, font=(default_font_family, default_font_size))
        self.account_selector_combo.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)
        self.account_selector_combo.bind("<<ComboboxSelected>>", self._on_account_selected)

        action_buttons_frame = tk.Frame(row1_frame)
        action_buttons_frame.pack(side=tk.RIGHT)
        self.report_button = tk.Button(action_buttons_frame, text="Analiză Cash Flow", command=self.show_cash_flow_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#D5F5E3", activebackground="#BDECB6")
        self.report_button.pack(side=tk.LEFT, padx=(0, 5))

        self.balance_report_button = tk.Button(action_buttons_frame, text="Evoluție Sold", command=self.show_balance_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#D4E6F1", activebackground="#A9CCE3")
        self.balance_report_button.pack(side=tk.LEFT, padx=5)

        self.analysis_button = tk.Button(action_buttons_frame, text="Analiză Tranzacții", command=self.show_transaction_analysis_report, font=(default_font_family, default_font_size, 'bold'), relief=tk.RAISED, borderwidth=2, background="#FEF9E7", activebackground="#FDEBD0")
        self.analysis_button.pack(side=tk.LEFT, padx=5)

        self.export_button = tk.Button(action_buttons_frame, text="Exportă în Excel", command=self.export_to_excel, font=(default_font_family, default_font_size), relief=tk.RAISED, borderwidth=2)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.import_button = tk.Button(action_buttons_frame, text="Importă fișier MT940", command=self.import_mt940, font=(default_font_family, default_font_size), relief=tk.RAISED, borderwidth=2)
        self.import_button.pack(side=tk.LEFT, padx=5)

        row2_frame = tk.Frame(top_controls_container)
        row2_frame.pack(fill=tk.X, expand=True, pady=(5,0))
        self.date_range_checkbox = tk.Checkbutton(row2_frame, text="Interval Dată Specific:", variable=self.date_range_mode_var, command=self._toggle_filter_mode, font=(default_font_family, default_font_size))
        self.date_range_checkbox.pack(side=tk.LEFT, padx=(0,10))
        ttk.Label(row2_frame, text="De la:").pack(side=tk.LEFT, padx=(0, 2))
        self.start_date = DateEntry(row2_frame, date_pattern='yyyy-mm-dd', width=12, state='disabled', font=(default_font_family, default_font_size))
        self.start_date.pack(side=tk.LEFT, padx=(0,5))
        self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
        ttk.Label(row2_frame, text="Până la:").pack(side=tk.LEFT, padx=(5, 2))
        self.end_date = DateEntry(row2_frame, date_pattern='yyyy-mm-dd', width=12, state='disabled', font=(default_font_family, default_font_size))
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

        for col in self.treeview_display_columns:
            width = self.loaded_column_widths.get(col, default_widths.get(col, 100))
            self.tree.column(col, anchor="w", width=width, minwidth=40)

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
        
        self.action_buttons = [self.report_button, self.balance_report_button, self.analysis_button, self.export_button, self.import_button, self.reset_button]
        
        self._toggle_action_buttons('disabled')

    # Restul metodelor clasei BTViewerApp rămân neschimbate...
    # ... (de la _setup_nav_tree_columns până la final)
    def _setup_nav_tree_columns(self):
        self.nav_tree.column("#0", width=200, minwidth=180, stretch=tk.YES)
        self.nav_tree.heading("#0", text="Navigare Perioadă") 
        self.nav_tree.tag_configure('year_node', font=('TkDefaultFont', 10, 'bold')) 
        self.nav_tree.tag_configure('month_node', font=('TkDefaultFont', 9))
        self.nav_tree.tag_configure('day_node', font=('TkDefaultFont', 9, 'italic'))

    def _load_and_apply_filters_from_config(self, config_parser_obj):
        if not (hasattr(self, 'master') and self.master.winfo_exists()): return
        
        filters = config_management.load_filters_from_parser(config_parser_obj)
        self.type_var.set(filters['type'])
        self.search_var.set(filters['search_term'])
        self.search_column_var.set(filters['search_column'])
        
        if hasattr(self, 'start_date') and self.start_date.winfo_exists(): self.start_date.unbind("<<DateEntrySelected>>")
        if hasattr(self, 'end_date') and self.end_date.winfo_exists(): self.end_date.unbind("<<DateEntrySelected>>")

        self.date_range_mode_var.set(filters['date_range_mode'])
        self._toggle_filter_mode() 
        
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
        
        else:
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

        if hasattr(self, 'start_date') and self.start_date.winfo_exists(): self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
        if hasattr(self, 'end_date') and self.end_date.winfo_exists(): self.end_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)

    def create_menu(self):
        default_font_family = 'TkDefaultFont'
        default_font_size = 10
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size))
        menubar.add_cascade(label="Fișier", menu=file_menu, font=(default_font_family, default_font_size))
        file_menu.add_command(label="Configurează Conexiunea DB...", command=self.handle_db_config_from_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Gestionare Conturi Bancare...", command=self.manage_accounts)
        file_menu.add_separator()
        file_menu.add_command(label="Gestionare Tipuri Tranzacții...", command=self.manage_transaction_types)
        file_menu.add_separator()
        file_menu.add_command(label="Configurează SMTP (Email)...", command=self.configure_smtp)
        file_menu.add_separator()
        file_menu.add_command(label="Ieșire", command=lambda: ui_utils.handle_app_exit(self, self.master))
        reports_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size))
        menubar.add_cascade(label="Rapoarte", menu=reports_menu, font=(default_font_family, default_font_size))
        reports_menu.add_command(label="Analiză Flux de Numerar...", command=self.show_cash_flow_report)
        reports_menu.add_command(label="Evoluție Sold Cont...", command=self.show_balance_report)
        reports_menu.add_command(label="Analiză Detaliată Tranzacții...", command=self.show_transaction_analysis_report)
    
    def _on_account_selected(self, event=None):
        if self._prevent_on_account_selected_trigger: return

        selected_account_name = self.account_combo_var.get()
        selected_account_obj = next((acc for acc in self.accounts_list if acc['nume_cont'] == selected_account_name), None)

        if selected_account_obj:
            if self.active_account_id != selected_account_obj['id_cont']: 
                self.active_account_id = selected_account_obj['id_cont']
                config_management.save_app_config(self) 
                self.refresh_ui_for_account_change()
            else:
                self.refresh_ui_for_account_change()
        else:
            self.active_account_id = None 
            self.refresh_ui_for_account_change() 
            if self.master.winfo_exists():
                messagebox.showwarning("Selecție Cont Invalidă", "Contul selectat nu este valid.", parent=self.master)

    def refresh_ui_for_account_change(self):
        if not self.master.winfo_exists(): return

        self._load_visible_transaction_types()
        self.update_total_count() 
        self._populate_nav_tree() 
        self.reset_filters() 
        self._update_status_label()
        self._update_active_account_color_indicator() 

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
                    color_to_set = "#FFFFFF" 
        try:
            self.active_account_color_indicator.config(background=color_to_set)
        except tk.TclError as e:
            try: self.active_account_color_indicator.config(background="SystemButtonFace")
            except tk.TclError: pass


    def _update_status_label(self):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            # --- BLOC MODIFICAT ---
            db_info_part = "Deconectat. | "
            if self.db_handler and self.db_handler.is_connected() and self.db_handler.db_credentials:
                creds = self.db_handler.db_credentials
                db_info_part = f"DB: {creds.get('user')}@{creds.get('host')}:{creds.get('port')}/{creds.get('database')} | "
            # --- SFÂRȘIT BLOC MODIFICAT ---

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
        if not (self.db_handler and self.db_handler.is_connected()):
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=[])
                self.account_combo_var.set("Fără Conexiune DB")
                self.account_selector_combo.config(state="disabled")
            self.active_account_id = None
            self.accounts_list = []
            if self.master.winfo_exists(): self.master.after(50, self.refresh_ui_for_account_change)
            return

        try:
            # --- BLOC MODIFICAT PENTRU A VERIFICA PERMISIUNILE UTILIZATORULUI ---
            all_db_accounts = self.db_handler.get_all_accounts() or []
            
            if self.current_user['has_all_permissions']:
                # Administratorul vede toate conturile
                self.accounts_list = all_db_accounts
            else:
                # Alți utilizatori văd doar conturile permise
                allowed_ids = set(self.current_user.get('allowed_accounts', []))
                self.accounts_list = [acc for acc in all_db_accounts if acc['id_cont'] in allowed_ids]
            
            account_names = [acc['nume_cont'] for acc in self.accounts_list]
            # --- SFÂRȘIT BLOC MODIFICAT ---

            last_active_id_str_from_config = None
            if self.config and self.config.has_section('General') and self.config.has_option('General', 'active_account_id'):
                last_active_id_str_from_config = self.config.get('General', 'active_account_id')
            
            last_active_id_from_config = None
            if last_active_id_str_from_config and last_active_id_str_from_config.isdigit():
                try: last_active_id_from_config = int(last_active_id_str_from_config)
                except ValueError: pass
            
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=account_names)
                determined_active_id, determined_active_name = None, None

                if not account_names:
                    determined_active_name = "Niciun Cont Accesibil"
                    self.account_selector_combo.config(state="disabled")
                else:
                    self.account_selector_combo.config(state="readonly")
                    if last_active_id_from_config is not None:
                        acc_from_config = next((acc for acc in self.accounts_list if acc['id_cont'] == last_active_id_from_config), None)
                        if acc_from_config:
                            determined_active_id = acc_from_config['id_cont']
                            determined_active_name = acc_from_config['nume_cont']
                    if determined_active_id is None and self.active_account_id is not None:
                        acc_current_active = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
                        if acc_current_active:
                            determined_active_id = acc_current_active['id_cont']
                            determined_active_name = acc_current_active['nume_cont']
                        else: self.active_account_id = None
                    if determined_active_id is None and self.accounts_list:
                        determined_active_id = self.accounts_list[0]['id_cont']
                        determined_active_name = self.accounts_list[0]['nume_cont']
                
                self.active_account_id = determined_active_id
                self.account_combo_var.set(determined_active_name if determined_active_name else "Selectați Cont")
            else:
                self.active_account_id = self.accounts_list[0]['id_cont'] if self.accounts_list else None
        except Exception as e:
            if self.master.winfo_exists(): messagebox.showerror("Eroare Încărcare Conturi", f"Eroare: {e}", parent=self.master)
            self.active_account_id = None; self.accounts_list = []
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=[]); self.account_combo_var.set("Eroare"); self.account_selector_combo.config(state="disabled")
        
        config_management.save_app_config(self)
        if self.master.winfo_exists(): self.master.after(50, self.refresh_ui_for_account_change)

    def manage_accounts(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            if self.master.winfo_exists(): messagebox.showwarning("Fără Conexiune", "Conectați-vă la DB.", parent=self.master)
            return
        dialog = AccountManagerDialog(self.master, self.db_handler) 
        self.master.wait_window(dialog.top) 
        self._populate_account_selector() 

    def _ask_user_to_select_account_for_import(self, parent_window, prompt_message):
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
        dialog_width, dialog_height = dialog.winfo_width(), dialog.winfo_height()
        parent_x, parent_y, parent_width, parent_height = parent_window.winfo_x(), parent_window.winfo_y(), parent_window.winfo_width(), parent_window.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        dialog.geometry(f"+{position_x}+{position_y}")
        
        parent_window.wait_window(dialog)
        return result_id


    def import_mt940(self):
        if not (self.db_handler and self.db_handler.is_connected()):
            if self.master.winfo_exists():
                messagebox.showwarning("Fără Conexiune", "Vă rugăm configurați și stabiliți o conexiune la baza de date.", parent=self.master)
            return

        selected_file_paths = filedialog.askopenfilenames(
            master=self.master,
            title="Selectează unul sau mai multe fișiere MT940",
            filetypes=[("Fișiere MT940", "*.sta *.STA *.txt"), ("Toate fișierele", "*.*")]
        )
        if not selected_file_paths:
            return
        
        self.file_paths_for_import_ref = selected_file_paths
        self.import_batch_queue = []
        temp_account_to_files_map = {} 

        for file_path in selected_file_paths:
            current_ui_active_account_id = self.active_account_id
            current_ui_active_account_iban, current_ui_active_account_name = None, "N/A"
            if current_ui_active_account_id:
                acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == current_ui_active_account_id), None)
                if acc_obj:
                    current_ui_active_account_iban = acc_obj.get('iban')
                    current_ui_active_account_name = acc_obj.get('nume_cont')
            
            iban_from_file_raw = extract_iban_from_mt940(file_path)
            iban_from_file = iban_from_file_raw.replace(" ", "").upper() if iban_from_file_raw else None
            
            target_account_id_for_this_file = None

            if not iban_from_file:
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
                else:
                    continue 
            
            else: 
                normalized_iban_current_ui_active = current_ui_active_account_iban.replace(" ", "").upper() if current_ui_active_account_iban else None
                if normalized_iban_current_ui_active and iban_from_file == normalized_iban_current_ui_active:
                    target_account_id_for_this_file = current_ui_active_account_id
                else: 
                    account_matching_db = self.db_handler.fetch_one_dict(
                        "SELECT id_cont, nume_cont, iban FROM conturi_bancare WHERE REPLACE(UPPER(iban), ' ', '') = %s", (iban_from_file,)
                    )
                    if account_matching_db:
                        matched_id, matched_name = account_matching_db['id_cont'], account_matching_db['nume_cont']
                        
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
                            else:
                                continue 
                    else:
                        msg = (f"Fișierul '{os.path.basename(file_path)}' (IBAN: {iban_from_file})\n"
                               f"NU este înregistrat în aplicație.\n\nOpțiuni:\n"
                               "1. Adăugați cont nou pentru acest IBAN (Apăsați 'Da').\n"
                               "2. Selectați manual un alt cont existent (Apăsați 'Nu').\n"
                               "3. Anulați pentru acest fișier (Apăsați 'Anulează').")
                        user_choice = messagebox.askyesnocancel(f"Cont Nou Detectat pentru {os.path.basename(file_path)}", msg, parent=self.master, icon='question')

                        if user_choice is True:
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
                                        else: continue
                                    else: continue
                                except Exception as e_add_f: continue
                            else: continue
                        elif user_choice is False:
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
                            else: continue
                        else:
                            continue
            
            if target_account_id_for_this_file is not None:
                if target_account_id_for_this_file not in temp_account_to_files_map: temp_account_to_files_map[target_account_id_for_this_file] = []
                temp_account_to_files_map[target_account_id_for_this_file].append(file_path)

        for acc_id, files_list in temp_account_to_files_map.items():
            if files_list: self.import_batch_queue.append({'target_id': acc_id, 'files': list(files_list)})
        
        if not self.import_batch_queue:
            if self.master.winfo_exists(): messagebox.showinfo("Import Anulat", "Niciun fișier nu a fost programat pentru import.", parent=self.master)
            return

        self._process_next_import_batch()

    def _process_next_import_batch(self):
        if not self.import_batch_queue:
            if self.master.winfo_exists():
                messagebox.showinfo("Importuri Finalizate", "Toate loturile de fișiere selectate au fost procesate.", parent=self.master)
            self._toggle_action_buttons('normal')
            self.refresh_ui_for_account_change()
            return

        current_batch = self.import_batch_queue.pop(0)
        target_id, files_for_this_batch = current_batch['target_id'], current_batch['files']
        
        self.current_batch_info_for_message = {'target_id': target_id, 'num_files': len(files_for_this_batch)}

        acc_obj_batch = next((acc for acc in self.accounts_list if acc['id_cont'] == target_id), None)
        target_name_batch = acc_obj_batch['nume_cont'] if acc_obj_batch else f"ID Cont {target_id}"
        
        self._toggle_action_buttons('disabled')
        
        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = \
            file_processing.create_progress_window(self.master, f"Import Lot Cont: {target_name_batch}", f"Se procesează {len(files_for_this_batch)} fișier(e)...")
        
        if self.current_progress_bar and self.current_progress_bar.winfo_exists():
            self.current_progress_bar['maximum'] = len(files_for_this_batch)

        self.import_thread = threading.Thread(target=threaded_import_worker, args=(self, files_for_this_batch, self.queue, target_id))
        self.import_thread.daemon = True
        self.import_thread.start()
        if self.master.winfo_exists():
            self.master.after(100, self._check_batch_import_progress)

    def _finalize_background_task(self, message, success, operation_type):
        if hasattr(self, 'current_progress_win') and self.current_progress_win and self.current_progress_win.winfo_exists():
            try:
                if hasattr(self, 'current_progress_bar') and self.current_progress_bar.winfo_exists(): self.current_progress_bar.stop()
                self.current_progress_win.destroy()
            except tk.TclError: pass
        
        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = None, None, None
        
        if operation_type and hasattr(self, f"{operation_type}_thread"): 
            setattr(self, f"{operation_type}_thread", None)

        if not self.import_batch_queue:
            self._toggle_action_buttons('normal')

        if self.master.winfo_exists():
            if success: messagebox.showinfo("Operațiune Finalizată", message, parent=self.master)
            else: messagebox.showerror("Eroare Operațiune", message, parent=self.master)

    def _check_batch_import_progress(self):
        try:
            msg = self.queue.get_nowait()
            msg_type = msg[0]
            
            if msg_type == "done":
                operation_type, results = msg[1], msg[2]
                inserted, ignored = results[0], results[1]
                
                batch_info = self.current_batch_info_for_message or {}
                num_files_in_batch = batch_info.get('num_files', 'N/A')
                processed_target_id = batch_info.get('target_id')
                processed_target_name = next((acc['nume_cont'] for acc in self.accounts_list if acc['id_cont'] == processed_target_id), f"ID {processed_target_id}")
                
                final_batch_message = (f"Lot pentru contul '{processed_target_name}' finalizat.\n\n"
                                       f"Fișiere procesate: {num_files_in_batch}\n"
                                       f"Tranzacții noi importate: {inserted}\n"
                                       f"Tranzacții ignorate (duplicate): {ignored}")
                
                self._finalize_background_task(final_batch_message, success=True, operation_type=operation_type)

                if processed_target_id is not None:
                    if self.db_handler: self.db_handler.close_connection()
                    if not self.connect_to_db():
                        if self.master.winfo_exists(): 
                            messagebox.showerror("Eroare Conexiune", "Nu s-a putut reconecta la DB după import.", parent=self.master)
                        self.import_batch_queue = []
                        if self.master.winfo_exists(): self.master.after(100, self._process_next_import_batch);
                        return

                    if self.active_account_id != processed_target_id:
                        target_acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == processed_target_id), None)
                        if target_acc_obj:
                            self._prevent_on_account_selected_trigger = True
                            self.active_account_id = processed_target_id
                            self.account_combo_var.set(target_acc_obj['nume_cont'])
                            config_management.save_app_config(self)
                            self._prevent_on_account_selected_trigger = False
                    
                    self.refresh_ui_for_account_change()

                    if self.master.winfo_exists():
                        self.master.update_idletasks()
                
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
                operation_type, error_message = msg[1], msg[2]
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
            logging.error(f"Eroare CRITICĂ în _check_batch_import_progress: {type(e).__name__}: {e}", exc_info=True)
    
    def refresh_table(self, start_date_override=None, end_date_override=None):
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
        
        # ---- BLOC DE COD CORECTAT ----
        # Acest bloc va adăuga filtrul doar dacă există coduri vizibile de filtrat.
        # Dacă lista este goală, nu se adaugă niciun filtru, permițând afișarea tuturor tranzacțiilor.
        if self.visible_tx_codes:
            placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
            # Am corectat numele coloanei din 'cod_tranzactie' în 'cod_tranzactie_fk'
            query += f" AND cod_tranzactie_fk IN ({placeholders})"
            params.extend(self.visible_tx_codes)
        # Am eliminat complet secțiunea 'else' care adăuga "AND 1=0".
        # ---- SFÂRȘIT BLOC CORECTAT ----

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
                query += " AND CONCAT_WS(' ', beneficiar, cif, factura, descriere, observatii) LIKE %s"
                params.append(search_term)
            else:
                col_map = {"Beneficiar": "beneficiar", "CIF": "cif", "Factura": "factura", "Descriere": "descriere", "Observatii": "observatii"}
                search_col_db_name = col_map.get(selected_search_area, "descriere")
                query += f" AND {search_col_db_name} LIKE %s"
                params.append(search_term)

        sort_col_db = self.sort_column
        if sort_col_db not in select_cols_list and sort_col_db != 'id': sort_col_db = 'data' 
        sort_dir = 'ASC' if self.sort_direction == 'ASC' else 'DESC'
        query += f" ORDER BY {sort_col_db} {sort_dir}, id ASC"

        all_rows = self.db_handler.fetch_all_dict(query, tuple(params))

        if all_rows:
            for row_dict in all_rows:
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
                
                tags_to_apply = ('credit_row',) if row_dict.get('tip') == 'credit' else ('debit_row',) if row_dict.get('tip') == 'debit' else ()
                
                if self.tree.winfo_exists():
                    # Presupunand ca 'id' din DB este unic si poate fi folosit ca IID
                    self.tree.insert('', 'end', values=tuple(values), tags=tags_to_apply, iid=row_dict['id'])
        
        self.update_sort_indicator()
        self._update_status_label()
        self._calculate_and_update_totals() 

    def _calculate_and_update_totals(self):
        if not (hasattr(self, 'tree') and self.tree.winfo_exists()): return

        active_account_currency = "RON"
        if self.active_account_id and self.accounts_list:
            active_account = next((acc for acc in self.accounts_list if acc['id_cont'] == self.active_account_id), None)
            if active_account and active_account.get('valuta'):
                active_account_currency = active_account.get('valuta')

        total_credit, total_debit = 0.0, 0.0

        try:
            suma_col_index = self.treeview_display_columns.index('suma')
            tip_col_index = self.treeview_display_columns.index('tip')
        except ValueError:
            return

        for item_id in self.tree.get_children(""):
            try:
                item_values = self.tree.item(item_id, 'values')
                suma_str, tip_str = item_values[suma_col_index], item_values[tip_col_index]
                suma_val = float(suma_str)

                if tip_str == 'credit': total_credit += suma_val
                elif tip_str == 'debit': total_debit += suma_val
            except (ValueError, IndexError):
                continue
        
        sold = total_credit - total_debit
        total_credit_str = f"{total_credit:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        total_debit_str = f"{total_debit:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        sold_str = f"{sold:,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        if hasattr(self, 'total_credit_label') and self.total_credit_label.winfo_exists(): self.total_credit_label.config(text=total_credit_str)
        if hasattr(self, 'total_debit_label') and self.total_debit_label.winfo_exists(): self.total_debit_label.config(text=total_debit_str)
        if hasattr(self, 'sold_label') and self.sold_label.winfo_exists():
            self.sold_label.config(text=sold_str, foreground="black" if sold == 0 else ("#006400" if sold > 0 else "#8B0000"))

    def prompt_for_mariadb_credentials(self):
        success = False
        dialog = MariaDBConfigDialog(self.master, initial_config={
            'host': self.db_host, 'port': self.db_port, 'database': self.db_name,
            'user': self.db_user, 'password': self.db_password
        })
        creds = dialog.result
        
        if not self.master.winfo_exists(): return False
        self.master.update_idletasks() 

        if creds:
            if not all([creds["host"], creds["port"], creds["database"], creds["user"]]):
                if self.master.winfo_exists(): messagebox.showerror("Date Incomplete", "Toate câmpurile (excepție parola) sunt obligatorii.", parent=self.master)
            else:
                self.db_host, self.db_port, self.db_name, self.db_user, self.db_password = \
                    creds["host"].strip(), creds["port"], creds["database"].strip(), creds["user"].strip(), creds["password"]
                
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
            
            self.active_account_id = None
            self.accounts_list = []
            self.account_combo_var.set("")
            self.total_transaction_count = 0
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            
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

    def _schedule_ui_population_steps(self, config_parser_for_filters, context_msg=""):
        if not self.master.winfo_exists(): return

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
            # Am corectat numele coloanei și am eliminat clauza 'else'
            query_years += f" AND cod_tranzactie_fk IN ({placeholders})"
            params_years.extend(self.visible_tx_codes)
        query_years += " ORDER BY an DESC"
        
        years_data_dicts = self.db_handler.fetch_all_dict(query_years, tuple(params_years))

        if not years_data_dicts:
            if self.nav_tree.winfo_exists(): self.nav_tree.insert("", "end", text="Nicio tranzacție vizibilă", iid="no_data_root"); return

        for year_dict in years_data_dicts:
            year_val = year_dict.get('an')
            if year_val is None: continue
            
            query_count = "SELECT COUNT(*) FROM tranzactii WHERE YEAR(data) = %s AND id_cont_fk = %s"
            params_count = [year_val, self.active_account_id]
            # Am eliminat clauza 'else' pentru a număra corect toate tranzacțiile 
            # atunci când niciun filtru de vizibilitate nu este activ.
            if self.visible_tx_codes:
                placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
                query_count += f" AND cod_tranzactie_fk IN ({placeholders})"
                params_count.extend(self.visible_tx_codes)
            
            year_tx_count = self.db_handler.fetch_scalar(query_count, tuple(params_count)) or 0

            if year_tx_count > 0:
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

        filter_clause, params_filter = "", []
        if self.visible_tx_codes:
            placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
            # Am corectat numele coloanei și am eliminat clauza 'else'
            filter_clause = f" AND cod_tranzactie_fk IN ({placeholders})"
            params_filter.extend(self.visible_tx_codes)

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
                    query_count_day = f"SELECT COUNT(*) FROM tranzactii WHERE YEAR(data) = %s AND MONTH(data) = %s AND DAY(data) = %s AND id_cont_fk = %s {filter_clause}"
                    params_count_day = [year_val, month_idx, day_val, self.active_account_id] + params_filter
                    day_tx_count = self.db_handler.fetch_scalar(query_count_day, tuple(params_count_day)) or 0
                    if day_tx_count > 0:
                        day_display_text = f"    {day_val:02d} ({day_tx_count} tranzacții)"
                        day_iid = f"{item_id}_day_{day_val:02d}"
                        self.nav_tree.insert(item_id, "end", text=day_display_text, iid=day_iid, tags=('day_node',))

        if not is_open_event and self.nav_tree.exists(item_id):
            self.nav_tree.item(item_id, open=not self.nav_tree.item(item_id, "open"))

    def _toggle_filter_mode(self):
        if self._programmatic_change: return

        is_range_mode = self.date_range_mode_var.get()
        self._programmatic_change = True
        if is_range_mode:
            if hasattr(self, 'start_date'): self.start_date.config(state='normal')
            if hasattr(self, 'end_date'): self.end_date.config(state='normal')
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                style = ttk.Style(); style.configure("nav.Treeview", foreground="#aaaaaa"); self.nav_tree.config(style="nav.Treeview")
                for item_sel in self.nav_tree.selection(): self.nav_tree.selection_remove(item_sel)
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            self.refresh_table()
        else:
            if hasattr(self, 'start_date'): self.start_date.config(state='disabled')
            if hasattr(self, 'end_date'): self.end_date.config(state='disabled')
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                style = ttk.Style(); style.configure("nav.Treeview", foreground="black"); self.nav_tree.config(style="nav.Treeview")
            self._apply_nav_selection_to_datepickers_and_refresh()
        
        self.master.after(10, lambda: setattr(self, '_programmatic_change', False))

    def _on_nav_tree_select(self, event=None):
        if self._programmatic_change or self._applying_nav_selection: return

        if self.date_range_mode_var.get():
            self._programmatic_change = True
            self.date_range_mode_var.set(False)
            self._toggle_filter_mode()
        else:
            self._apply_nav_selection_to_datepickers_and_refresh()

    def _apply_nav_selection_to_datepickers_and_refresh(self, nav_item_id_to_process=None):
        if not hasattr(self, 'nav_tree') or not self.nav_tree.winfo_exists(): self._applying_nav_selection = False; return
        if self._applying_nav_selection and not nav_item_id_to_process : self._applying_nav_selection = False; return
        
        self._applying_nav_selection = True
        selected_item_id = nav_item_id_to_process or (self.nav_tree.focus() if self.nav_tree.winfo_exists() else None)
        start_dt_to_set, end_dt_to_set = None, None

        if not selected_item_id or selected_item_id.startswith("placeholder_"):
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
            
            if start_dt_to_set and end_dt_to_set and hasattr(self, 'start_date') and hasattr(self, 'end_date'):
                self.start_date.set_date(start_dt_to_set)
                self.end_date.set_date(end_dt_to_set)
            else:
                self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True) 
                if hasattr(self, 'start_date'): start_dt_to_set = self.start_date.get_date()
                if hasattr(self, 'end_date'): end_dt_to_set = self.end_date.get_date()
        except (IndexError, ValueError) as e: 
            self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            start_dt_to_set, end_dt_to_set = self.start_date.get_date(), self.end_date.get_date()
        
        if self.master.winfo_exists(): self.master.update_idletasks()
        self.refresh_table(start_date_override=start_dt_to_set, end_date_override=end_dt_to_set)
        self._applying_nav_selection = False

    def on_date_picker_change(self, event=None):
        if self.date_range_mode_var.get(): 
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)
            self._current_processed_nav_iid, self.nav_selected_year = None, None
            self.nav_selected_month_index, self.nav_selected_day = 0, 0
            self.refresh_table()

    def on_filter_change(self, event=None): self.refresh_table()
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

    def update_total_count(self):
        if self.db_handler and self.db_handler.is_connected() and self.active_account_id:
            query = "SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk = %s"
            params = [self.active_account_id]
            if self.visible_tx_codes:
                placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
                query += f" AND cod_tranzactie IN ({placeholders})"
                params.extend(self.visible_tx_codes)
            else:
                query += " AND 1=0"
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
        
        if hasattr(self, 'start_date') and hasattr(self, 'end_date'):
            try:
                self.start_date.unbind("<<DateEntrySelected>>"); self.end_date.unbind("<<DateEntrySelected>>")
                self.start_date.set_date(final_start); self.end_date.set_date(final_end)
                self.start_date.bind("<<DateEntrySelected>>", self.on_date_picker_change); self.end_date.bind("<<DateEntrySelected>>", self.on_date_picker_change)
            except tk.TclError: pass
            except Exception: pass
        
        if not called_by_nav_tree_logic:
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)

    def reset_filters(self):
        self.search_var.set("")
        self.type_var.set("Toate")
        self.search_column_var.set("Toate coloanele")
        
        if self.date_range_mode_var.get():
            self.date_range_mode_var.set(False)

        if hasattr(self, 'start_date'): self.start_date.config(state='disabled')
        if hasattr(self, 'end_date'): self.end_date.config(state='disabled')
        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            style = ttk.Style(); style.configure("nav.Treeview", foreground="black"); self.nav_tree.config(style="nav.Treeview")

        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        
        self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
        self.refresh_table()

    def show_transaction_details(self, event):
        if not hasattr(self, 'tree') or not self.tree.winfo_exists(): return
        item_id_str = self.tree.focus()
        if not item_id_str: return 
        try: item_id = int(item_id_str)
        except ValueError: return

        if not (self.db_handler and self.db_handler.is_connected()): messagebox.showerror("Eroare DB", "Nu există conexiune.", parent=self.master); return
        transaction_data = self.db_handler.fetch_one_dict("SELECT * FROM tranzactii WHERE id = %s", (item_id,))
        if not transaction_data: messagebox.showerror("Eroare", f"Tranzacția ID: {item_id} nu a fost găsită.", parent=self.master); return
        
        active_account_currency = "RON"
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
        
        # O listă de câmpuri de afișat
        fields_to_show = [("ID:", "id"), ("Dată:", "data"), ("Sumă:", "suma"), ("Tip:", "tip"),
                          ("Beneficiar:", "beneficiar"), ("CIF:", "cif"), ("Factură:", "factura"),
                          ("TID:", "tid"), ("RRN:", "rrn"),("PAN Mascat:", "pan"),
                          ("Descriere completă:", "descriere"), ("Observații (editabil):", "observatii")]

        row_idx = 0
        for label_text, col_name in fields_to_show:
            value = transaction_data.get(col_name)
            if col_name != "observatii" and (value is None or (isinstance(value, str) and not value.strip())): continue
            
            ttk.Label(main_frame, text=label_text, font=('TkDefaultFont', 10, 'bold')).grid(row=row_idx, column=0, sticky='nw', padx=5, pady=(2,0))
            
            if col_name == "observatii":
                obs_text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=5, font=('TkDefaultFont', 10))
                obs_text_widget.grid(row=row_idx, column=1, sticky='nwe', padx=5, pady=(2,0))
                obs_text_widget.insert(tk.END, str(value) if value is not None else "")
            else:
                value_text = str(value) if value is not None else ""
                font_style, text_color, wrap_len = ('TkDefaultFont', 10), 'black', 0
                
                if isinstance(value, date): value_text = value.strftime('%d-%m-%Y')
                elif col_name == "suma":
                    try: value_text = f"{float(value):,.2f} {active_account_currency}".replace(",", "X").replace(".", ",").replace("X", ".")
                    except (ValueError, TypeError): value_text = str(value) + f" {active_account_currency}"
                    font_style = ('TkDefaultFont', 10, 'bold')
                    text_color = '#006400' if transaction_data.get('tip') == 'credit' else '#8B0000'
                elif col_name == "tip":
                    font_style = ('TkDefaultFont', 10, 'bold')
                    text_color = '#006400' if value == 'credit' else '#8B0000'
                elif col_name == "descriere": wrap_len = 450
                
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

    def export_to_excel(self):
        if not (self.db_handler and self.db_handler.is_connected() and self.active_account_id):
            messagebox.showwarning("Fără Conexiune / Cont", "Vă rugăm selectați un cont și asigurați o conexiune la baza de date.", parent=self.master)
            return

        file_path = filedialog.asksaveasfilename(master=self.master, title="Salvare Export Excel",
            defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")])
        if not file_path: return

        self._toggle_action_buttons('disabled')

        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget = \
            file_processing.create_progress_window(self.master, "Export în Desfășurare", "Se pregătește exportul datelor...")

        if self.current_progress_bar and self.current_progress_bar.winfo_exists():
            self.current_progress_bar.config(mode='indeterminate'); self.current_progress_bar.start(10)
        
        select_clause_export = "data, descriere, observatii, suma, tip, cif, factura, beneficiar"
        query = f"SELECT {select_clause_export} FROM tranzactii WHERE id_cont_fk = %s"
        params = [self.active_account_id]

        start_date_for_export, end_date_for_export = None, None
        if self.date_range_mode_var.get():
            if hasattr(self, 'start_date') and self.start_date.get(): start_date_for_export = self.start_date.get_date()
            if hasattr(self, 'end_date') and self.end_date.get(): end_date_for_export = self.end_date.get_date()
        elif self.nav_selected_year is not None:
            current_year, current_month, current_day = self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day
            if current_month == 0: start_date_for_export, end_date_for_export = date(current_year, 1, 1), date(current_year, 12, 31)
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

        sort_col_export, sort_dir_export = self.sort_column, self.sort_direction
        query += f" ORDER BY {sort_col_export} {sort_dir_export}, id ASC"
        
        self.export_thread = threading.Thread(target=threaded_export_worker, args=(self, query, tuple(params), file_path, self.queue))
        self.export_thread.daemon = True
        self.export_thread.start()
        if self.master.winfo_exists():
            self.master.after(100, self._check_export_progress)

    def _check_export_progress(self):
        try:
            msg = self.queue.get_nowait()
            msg_type, data = msg[0], msg[1]

            if msg_type == "status": 
                if self.current_progress_status_label_widget and self.current_progress_status_label_widget.winfo_exists(): self.current_progress_status_label_widget.config(text=data)
                if self.master.winfo_exists(): self.master.after(100, self._check_export_progress)
            elif msg_type == "done": 
                self._toggle_action_buttons('normal')
                if self.master.winfo_exists(): self.master.after(10, lambda: self._finalize_export_ui(f"Datele au fost exportate cu succes în:\n{data}", True))
            elif msg_type == "error": 
                self._toggle_action_buttons('normal')
                if self.master.winfo_exists(): self.master.after(10, lambda: self._finalize_export_ui(data, False))
        except Empty:
            if hasattr(self, 'export_thread') and self.export_thread and self.export_thread.is_alive():
                if self.master.winfo_exists(): self.master.after(100, self._check_export_progress)
            else:
                self._toggle_action_buttons('normal')
        except Exception as e:
            logging.error(f"Eroare generală în _check_export_progress: {e}")
            if self.current_progress_win and self.current_progress_win.winfo_exists(): self.current_progress_win.destroy()
            self._toggle_action_buttons('normal')

    def _finalize_export_ui(self, message, success):
        if hasattr(self, 'current_progress_win') and self.current_progress_win:
            try:
                if self.current_progress_win.winfo_exists():
                    if self.current_progress_bar and self.current_progress_bar.winfo_exists(): self.current_progress_bar.stop()
                    self.current_progress_win.destroy()
            except tk.TclError: pass

        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget, self.export_thread = None, None, None, None
        
        if self.master.winfo_exists():
            if success: messagebox.showinfo("Export Finalizat", message, parent=self.master)
            else: messagebox.showerror("Eroare la Export", message, parent=self.master)

    def exit_app(self, message=None):
        if message and hasattr(self, 'master') and self.master.winfo_exists():
            try: messagebox.showerror("Închidere Aplicație", message, parent=self.master)
            except tk.TclError: pass
        
        if hasattr(self, 'db_handler') and self.db_handler: self.db_handler.close_connection()
        
        if hasattr(self, 'master') and self.master.winfo_exists():
            try: self.master.destroy()
            except tk.TclError: pass


if __name__ == "__main__":
    # 1. Inițializare logging
    log_file_path = os.path.join(APP_DATA_DIR, 'app_activity.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s',
        filename=log_file_path,
        filemode='w',
        encoding='utf-8'
    )

    # 2. Secvența de pornire și autentificare
    db_handler = None
    temp_root = tk.Tk()
    temp_root.withdraw()

    try:
        # Pasul A: Citirea configurației DB
        config = configparser.ConfigParser()
        db_credentials = None
        if os.path.exists(config_management.CONFIG_FILE):
            config.read(config_management.CONFIG_FILE, encoding='utf-8')
            db_credentials = config_management.read_db_config_from_parser(config)

        # Pasul B: Conectarea la Baza de Date
        db_handler = DatabaseHandler(db_credentials=db_credentials, app_master_ref=temp_root)
        if not db_handler.connect():
            dialog = MariaDBConfigDialog(temp_root, initial_config=(db_credentials or {}))
            creds = dialog.result
            if creds and all(creds.values()):
                db_handler.db_credentials = creds
                if not db_handler.connect():
                    raise ConnectionError("Conectarea la DB a eșuat chiar și după introducerea manuală a credențialelor.")
            else:
                raise ConnectionError("Configurarea conexiunii DB a fost anulată.")

        # Pasul C: Verificarea și crearea schemei DB
        if not db_handler.check_and_setup_database_schema():
            raise SystemError("Schema bazei de date nu a putut fi verificată sau creată.")

        # Pasul D: Afișarea ferestrei de Login
        login_dialog = LoginDialog(temp_root, db_handler)
        user_data = login_dialog.result

        if not user_data:
            raise PermissionError("Autentificare anulată de utilizator.")

        # --- Autentificare reușită. Urmează pornirea aplicației principale. ---

        # === BLOC MODIFICAT PENTRU A REZOLVA PROBLEMA FERESTREI GOALE ===
        # Pasul E: Distrugem fereastra temporară ACUM, deoarece nu mai avem nevoie de ea.
        temp_root.destroy()

        # Pasul F: Crearea și rularea ferestrei principale
        root = tk.Tk()
        window_geom, zoomed = config_management.load_window_config_from_file()
        if window_geom and not zoomed:
            try: root.geometry(window_geom)
            except tk.TclError: root.geometry("1200x700")
        else:
            try: root.state('zoomed')
            except tk.TclError:
                w_screen, h_screen = root.winfo_screenwidth(), root.winfo_screenheight()
                root.geometry(f"{w_screen}x{h_screen}+0+0")
        
        app = BTViewerApp(root, user_data=user_data, db_handler=db_handler, config_parser=config)
        
        root.protocol("WM_DELETE_WINDOW", lambda: ui_utils.handle_app_exit(app, root))
        
        root.mainloop()
        # === SFÂRȘIT BLOC MODIFICAT ===

    except (ConnectionError, SystemError, PermissionError) as e:
        if db_handler and db_handler.is_connected():
            db_handler.close_connection()
        messagebox.showerror("Eroare la Pornire", str(e), parent=temp_root)
        logging.error(f"Pornire eșuată: {e}")
        if temp_root.winfo_exists():
            temp_root.destroy()
    except Exception as e_main:
        if db_handler and db_handler.is_connected():
            db_handler.close_connection()
        logging.critical(f"Eroare neașteptată în procesul de pornire: {e_main}", exc_info=True)
        messagebox.showerror("Eroare Critică", f"A apărut o eroare neașteptată la pornire: {e_main}", parent=temp_root)
        if temp_root.winfo_exists():
            temp_root.destroy()