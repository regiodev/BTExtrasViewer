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
from ui_dialogs import AccountManagerDialog, AccountEditDialog, TransactionTypeManagerDialog, SMTPConfigDialog, BalanceReportConfigDialog, LoginDialog, UserManagerDialog

# NOU: Importăm handler-ul de autentificare. Vom avea nevoie de el în pasul următor.
import auth_handler

class BTViewerApp:
    def __init__(self, master, user_data, db_handler, user_settings):
        # --- Constructor modificat și corectat ---
        self.master = master
        self.current_user = user_data
        self.db_handler = db_handler
        # NOU: Setările sunt primite ca parametru, nu citite dintr-un fișier
        self.user_settings = user_settings 
        
        self.master.title(f"{APP_NAME} - Se încarcă datele...")

        # Inițializarea atributelor aplicației
        self.visible_tx_codes = [] 
        self._programmatic_change = False 
        self.import_batch_queue = [] 
        self.current_batch_info_for_message = None
        self.file_paths_for_import_ref = [] 
        
        # NOU: Setările SMTP sunt încărcate din setările utilizatorului
        self.smtp_config = self.user_settings.get('smtp', {})
        
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
        
        # Atributele de filtre sunt setate acum de _apply_user_settings
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.date_range_mode_var = tk.BooleanVar()
        self.exact_search_var = tk.BooleanVar(value=False)
        
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        self._nav_select_job, self._current_processed_nav_iid = None, None
        
        self.treeview_display_columns = DEFAULT_TREEVIEW_DISPLAY_COLUMNS
        # Lățimile coloanelor vor fi setate de _apply_user_settings
        self.loaded_column_widths = self.user_settings.get('column_widths', {})
        
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
        
        # Aplicăm setările încărcate din DB
        self._apply_user_settings()
        
        logging.debug("DEBUG_INIT: __init__ - UI setup complet. Se pornește popularea UI.")
        
        # Pornim popularea UI
        self.init_step4_populate_ui()

    def _apply_user_settings(self):
        """Aplică setările încărcate din DB la componentele UI."""
        if not self.user_settings:
            return # Nu există setări de aplicat

        # Aplică filtrele
        filters = self.user_settings.get('filters', {})
        self.type_var.set(filters.get('type', "Toate"))
        self.search_var.set(filters.get('search_term', ""))
        self.search_column_var.set(filters.get('search_column', "Toate coloanele"))
        self.date_range_mode_var.set(filters.get('date_range_mode', False))
        
        # Aplică starea contului activ
        general = self.user_settings.get('general', {})
        last_active_id_str = general.get('active_account_id')
        if last_active_id_str and last_active_id_str.isdigit():
            self.active_account_id = int(last_active_id_str)
        
        # Lățimea coloanelor a fost deja încărcată în self.loaded_column_widths
        # și este folosită în setup_ui.
        
        # Starea ferestrei (geometria) a fost deja aplicată la creare în blocul if __name__ == "__main__":

        # --- NOU: Apelăm funcția de sincronizare AICI ---
        # Asigură că starea checkbox-ului reflectă valoarea încărcată în combobox.
        self._on_search_column_changed()

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

    def manage_users(self):
        """Deschide dialogul de gestionare a utilizatorilor."""
        UserManagerDialog(self.master, self.db_handler, self.current_user)

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

    def _populate_audit_log_tab(self):
        """Populează tab-ul Jurnal Acțiuni cu date din baza de date."""
        # Verificăm dacă tree-ul există (a fost creat pe baza permisiunii)
        if not hasattr(self, 'audit_log_tree'):
            return

        for item in self.audit_log_tree.get_children():
            self.audit_log_tree.delete(item)

        log_entries = self.db_handler.get_audit_log_entries()
        if log_entries:
            for entry in log_entries:
                # Formatăm data pentru o afișare mai prietenoasă
                timestamp_str = entry['timestamp'].strftime('%d-%m-%Y %H:%M:%S') if entry.get('timestamp') else ''
                values = (
                    timestamp_str,
                    entry.get('username', 'N/A'),
                    entry.get('actiune', ''),
                    entry.get('detalii', '')
                )
                self.audit_log_tree.insert("", "end", values=values)

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
            # --- MODIFICARE AICI: Am eliminat self.config ---
            self.master.after(300, lambda: self._schedule_ui_population_steps("(initial setup)"))

            self._populate_history_tab()

            # Populăm și jurnalul de acțiuni la pornire
            self._populate_audit_log_tab()

    def setup_ui(self):
        default_font_size = 10
        default_font_family = 'TkDefaultFont'
        
        style = ttk.Style()
        style.configure("TLabel", font=(default_font_family, default_font_size))
        style.configure("TButton", font=(default_font_family, default_font_size))
        style.configure("TCombobox", font=(default_font_family, default_font_size))
        style.configure("TCheckbutton", font=(default_font_family, default_font_size))
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
        
        self.exact_search_checkbox = ttk.Checkbutton(
            row2_frame, 
            text="Căutare exactă:", 
            variable=self.exact_search_var, 
            command=self.on_filter_change,
        )
        self.exact_search_checkbox.pack(side=tk.LEFT, padx=(10, 5))
        self.search_entry = ttk.Entry(row2_frame, textvariable=self.search_var, width=20, font=(default_font_family, default_font_size))
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<KeyRelease>", self.schedule_search)
        ttk.Label(row2_frame, text="în:").pack(side=tk.LEFT, padx=(5,2))
        searchable_columns = [
            "Toate coloanele", "Dată", "Descriere", "Observații", 
            "Sumă", "Tip", "CIF", "Factură", "Beneficiar"
        ]
        self.search_column_combo = ttk.Combobox(row2_frame, textvariable=self.search_column_var, values=searchable_columns, width=15, state="readonly", font=(default_font_family, default_font_size))
        self.search_column_combo.pack(side=tk.LEFT, padx=(0,10))
        self.search_column_combo.bind("<<ComboboxSelected>>", self._on_search_column_changed)
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
        history_cols = ("fisier", "data", "utilizator", "noi", "ignorate", "cont")
        self.history_tree = ttk.Treeview(history_tab, columns=history_cols, show="headings")
        self.history_tree.heading("fisier", text="Nume Fișier")
        self.history_tree.heading("data", text="Data Import")
        self.history_tree.heading("utilizator", text="Utilizator")
        self.history_tree.heading("noi", text="Tranzacții Noi")
        self.history_tree.heading("ignorate", text="Tranzacții Ignorate")
        self.history_tree.heading("cont", text="Importat în Contul")
        self.history_tree.column("fisier", width=250); self.history_tree.column("data", width=150)
        self.history_tree.column("utilizator", width=120, anchor='w')
        self.history_tree.column("noi", width=120, anchor='center'); self.history_tree.column("ignorate", width=130, anchor='center')
        self.history_tree.column("cont", width=200)
        history_scrollbar = ttk.Scrollbar(history_tab, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill="y")

        # Verificăm dacă utilizatorul are permisiunea de a vedea jurnalul
        if self.has_permission('view_audit_log'):
            audit_log_tab = ttk.Frame(main_content_notebook)
            main_content_notebook.add(audit_log_tab, text=" Jurnal Acțiuni ")
            
            # Creăm un Treeview pentru a afișa jurnalul
            audit_cols = ("timestamp", "username", "actiune", "detalii")
            self.audit_log_tree = ttk.Treeview(audit_log_tab, columns=audit_cols, show="headings")
            
            # Setăm antetele și dimensiunile coloanelor
            self.audit_log_tree.heading("timestamp", text="Dată și Oră")
            self.audit_log_tree.heading("username", text="Utilizator")
            self.audit_log_tree.heading("actiune", text="Acțiune")
            self.audit_log_tree.heading("detalii", text="Detalii")
            
            self.audit_log_tree.column("timestamp", width=160, anchor="w")
            self.audit_log_tree.column("username", width=120, anchor="w")
            self.audit_log_tree.column("actiune", width=180, anchor="w")
            self.audit_log_tree.column("detalii", width=400, anchor="w")
            
            # Adăugăm scrollbar
            audit_scrollbar = ttk.Scrollbar(audit_log_tab, orient="vertical", command=self.audit_log_tree.yview)
            self.audit_log_tree.configure(yscrollcommand=audit_scrollbar.set)
            
            self.audit_log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            audit_scrollbar.pack(side=tk.RIGHT, fill="y")
        
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

    def _setup_nav_tree_columns(self):
        self.nav_tree.column("#0", width=200, minwidth=180, stretch=tk.YES)
        self.nav_tree.heading("#0", text="Navigare Perioadă") 
        self.nav_tree.tag_configure('year_node', font=('TkDefaultFont', 10, 'bold')) 
        self.nav_tree.tag_configure('month_node', font=('TkDefaultFont', 9))
        self.nav_tree.tag_configure('day_node', font=('TkDefaultFont', 9, 'italic'))

    def create_menu(self):
        default_font_family = 'TkDefaultFont'
        default_font_size = 10
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        # --- Meniul Fișier ---
        file_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size))
        menubar.add_cascade(label="Fișier", menu=file_menu, font=(default_font_family, default_font_size))

        # Opțiuni condiționate de permisiuni
        if self.has_permission('manage_system_settings'):
            file_menu.add_command(label="Configurează Conexiunea DB...", command=self.handle_db_config_from_menu)
            file_menu.add_separator()
        
        if self.has_permission('manage_accounts'):
            file_menu.add_command(label="Gestionare Conturi Bancare...", command=self.manage_accounts)
            file_menu.add_separator()
        
        if self.has_permission('manage_system_settings'):
            file_menu.add_command(label="Gestionare Tipuri Tranzacții...", command=self.manage_transaction_types)
            file_menu.add_separator()
            file_menu.add_command(label="Configurează SMTP (Email)...", command=self.configure_smtp)
            file_menu.add_separator()

        if self.has_permission('manage_users'):
            file_menu.add_command(label="Gestionare Utilizatori...", command=self.manage_users)
            file_menu.add_separator()

        file_menu.add_command(label="Ieșire", command=lambda: ui_utils.handle_app_exit(self, self.master))

        # --- Meniul Rapoarte ---
        reports_menu = tk.Menu(menubar, tearoff=0, font=(default_font_family, default_font_size))
        # Adăugăm meniul doar dacă utilizatorul are voie să vadă rapoarte
        if self.has_permission('view_reports'):
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
            all_db_accounts = self.db_handler.get_all_accounts() or []
            
            if self.current_user['has_all_permissions']:
                self.accounts_list = all_db_accounts
            else:
                allowed_ids = set(self.current_user.get('allowed_accounts', []))
                self.accounts_list = [acc for acc in all_db_accounts if acc['id_cont'] in allowed_ids]
            
            account_names = [acc['nume_cont'] for acc in self.accounts_list]
            
            # === BLOC DE COD CORECTAT ===
            # Citim ultimul ID activ din user_settings, nu din self.config
            general_settings = self.user_settings.get('general', {})
            last_active_id_str_from_db = general_settings.get('active_account_id')
            # ============================
            
            last_active_id_from_db = None
            if last_active_id_str_from_db and last_active_id_str_from_db.isdigit():
                try: last_active_id_from_db = int(last_active_id_str_from_db)
                except ValueError: pass
            
            if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
                self.account_selector_combo.config(values=account_names)
                determined_active_id, determined_active_name = None, None

                if not account_names:
                    determined_active_name = "Niciun Cont Accesibil"
                    self.account_selector_combo.config(state="disabled")
                else:
                    self.account_selector_combo.config(state="readonly")
                    if last_active_id_from_db is not None:
                        acc_from_config = next((acc for acc in self.accounts_list if acc['id_cont'] == last_active_id_from_db), None)
                        if acc_from_config:
                            determined_active_id = acc_from_config['id_cont']
                            determined_active_name = acc_from_config['nume_cont']
                    
                    # Am eliminat o verificare redundantă pentru a simplifica logica
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
        
        # Salvăm configurația la ieșire, nu la fiecare populare
        # config_management.save_app_config(self) <-- Am comentat această linie pentru a preveni erori în cascadă la pornire
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
        self.current_batch_files_for_history = files_for_this_batch

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
                
                # --- BLOC FINAL PENTRU SALVARE ISTORIC ---
                if self.db_handler and inserted > 0: # Salvăm doar dacă s-a importat ceva nou
                    try:
                        # Concatenăm numele fișierelor din lot
                        filenames_str = ", ".join([os.path.basename(f) for f in self.current_batch_files_for_history])
                        
                        sql_insert_history = """
                            INSERT INTO istoric_importuri 
                            (nume_fisier, tranzactii_procesate, tranzactii_ignorate, id_cont_fk, id_utilizator_fk) 
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        params_history = (filenames_str, inserted, ignored, processed_target_id, self.current_user['id'])
                        self.db_handler.execute_commit(sql_insert_history, params_history)
                    except Exception as e_hist:
                        logging.error(f"Nu s-a putut salva istoricul de import: {e_hist}")
                # --- SFÂRȘIT BLOC FINAL ---

                if self.db_handler:
                    log_details = (f"Import în contul '{processed_target_name}'. Fișiere procesate: {num_files_in_batch}. "
                                   f"Tranzacții noi: {inserted}, Ignorate (duplicate): {ignored}.")
                    self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Import fișiere MT940", log_details)

                final_batch_message = (f"Lot pentru contul '{processed_target_name}' finalizat.\n\n"
                                       f"Fișiere procesate: {num_files_in_batch}\n"
                                       f"Tranzacții noi importate: {inserted}\n"
                                       f"Tranzacții ignorate (duplicate): {ignored}")
                
                self._finalize_background_task(final_batch_message, success=True, operation_type=operation_type)

                if processed_target_id is not None:
                    # Dacă lotul procesat a fost pentru un alt cont decât cel activ,
                    # comutăm pe contul nou importat pentru a vedea direct rezultatele.
                    if self.active_account_id != processed_target_id:
                        target_acc_obj = next((acc for acc in self.accounts_list if acc['id_cont'] == processed_target_id), None)
                        if target_acc_obj:
                            self._prevent_on_account_selected_trigger = True
                            self.active_account_id = processed_target_id
                            self.account_combo_var.set(target_acc_obj['nume_cont'])
                            config_management.save_app_config(self)
                            self._prevent_on_account_selected_trigger = False
                    
                    # Reîmprospătăm TOATĂ interfața pentru a reflecta noile date
                    self.refresh_ui_for_account_change()

                    self._populate_history_tab() # Reîmprospătăm istoricul
                
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
    
    def _populate_history_tab(self):
        """Populează tab-ul 'Istoric Importuri' cu date din baza de date."""
        if not hasattr(self, 'history_tree') or not self.history_tree.winfo_exists():
            return

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        if not (self.db_handler and self.db_handler.is_connected()):
            return

        # --- Interogare SQL actualizată cu JOIN la tabela de utilizatori ---
        query = """
            SELECT 
                h.nume_fisier, 
                h.data_import, 
                h.tranzactii_procesate, 
                h.tranzactii_ignorate, 
                c.nume_cont,
                u.username 
            FROM istoric_importuri h
            JOIN conturi_bancare c ON h.id_cont_fk = c.id_cont
            LEFT JOIN utilizatori u ON h.id_utilizator_fk = u.id
            ORDER BY h.data_import DESC
            LIMIT 200;
        """
        history_entries = self.db_handler.fetch_all_dict(query)

        if history_entries:
            for entry in history_entries:
                timestamp_str = entry['data_import'].strftime('%d-%m-%Y %H:%M:%S') if entry.get('data_import') else ''
                
                # --- Tuplul de valori a fost actualizat pentru a include utilizatorul ---
                values = (
                    entry.get('nume_fisier', 'N/A'),
                    timestamp_str,
                    entry.get('username', 'Utilizator Șters'), # Afișăm un text generic dacă utilizatorul a fost șters
                    entry.get('tranzactii_procesate', 0),
                    entry.get('tranzactii_ignorate', 0),
                    entry.get('nume_cont', 'N/A')
                )
                self.history_tree.insert("", "end", values=values)

    def _on_search_column_changed(self, event=None):
        """Gestionează schimbarea selecției în combobox-ul de căutare."""
        if self.search_column_var.get() == "Toate coloanele":
            # Dacă se selectează "Toate coloanele", dezactivăm și debifăm căutarea exactă
            self.exact_search_checkbox.config(state=tk.DISABLED)
            self.exact_search_var.set(False)
        else:
            # Pentru orice altă coloană, activăm opțiunea de căutare exactă
            self.exact_search_checkbox.config(state=tk.NORMAL)
        
        # Apelăm funcția de filtrare pentru a reîmprospăta rezultatele imediat
        self.on_filter_change()

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
            selected_search_area = self.search_column_var.get()
            
            # --- BLOC DE LOGICĂ NOU ȘI COMPLET ---
            
            # Verificăm dacă trebuie să facem o căutare exactă.
            # Aceasta se aplică doar dacă o coloană specifică este selectată.
            is_exact_search = self.exact_search_var.get() and selected_search_area != "Toate coloanele"

            if is_exact_search:
                # Pentru căutare exactă, termenul nu are wildcards (%) și operatorul este '='
                search_term = self.search_var.get().strip()
                operator = "="
            else:
                # Pentru căutare parțială, folosim wildcards și operatorul 'LIKE'
                search_term = f"%{self.search_var.get().strip()}%"
                operator = "LIKE"

            col_map = {
                "Beneficiar": "beneficiar", "CIF": "cif", "Factură": "factura", 
                "Descriere": "descriere", "Observații": "observatii",
                "Sumă": "suma", "Dată": "data", "Tip": "tip"
            }

            if selected_search_area == "Toate coloanele":
                # Căutarea pe "Toate coloanele" va folosi MEREU LIKE, ignorând starea checkbox-ului.
                # Termenul de căutare este întotdeauna cu wildcards aici.
                search_term_all_cols = f"%{self.search_var.get().strip()}%"
                query += """ AND CONCAT_WS(' ', 
                                beneficiar, cif, factura, descriere, observatii, 
                                suma, data, tip, tid, rrn, pan
                            ) LIKE %s """
                params.append(search_term_all_cols)
            else:
                search_col_db_name = col_map.get(selected_search_area)
                if search_col_db_name:
                    # Construim interogarea folosind operatorul și termenul de căutare determinați mai sus
                    query += f" AND {search_col_db_name} {operator} %s"
                    params.append(search_term)
            # --- SFÂRȘIT BLOC NOU ---

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
        """
        Deschide dialogul de configurare, testează noile credențiale și le returnează dacă sunt valide.
        Returnează dicționarul cu credențiale la succes, sau None la eșec/anulare.
        """
        # Obține configurația curentă pentru a o pre-popula în dialog
        current_creds = self.db_handler.db_credentials if (self.db_handler and self.db_handler.db_credentials) else {}
        dialog = MariaDBConfigDialog(self.master, initial_config=current_creds)
        
        new_creds = dialog.result
        if not new_creds:
            return None # Utilizatorul a anulat

        if not all([new_creds.get("host"), new_creds.get("port"), new_creds.get("database"), new_creds.get("user")]):
            messagebox.showerror("Date Incomplete", "Câmpurile Host, Port, Nume Bază Date și Utilizator sunt obligatorii.", parent=self.master)
            return None

        # Creează un handler temporar DOAR pentru a testa conexiunea
        temp_db_handler = DatabaseHandler(db_credentials=new_creds, app_master_ref=self.master)
        
        if temp_db_handler.connect():
            # Conexiune reușită, închidem conexiunea temporară și returnăm credențialele
            temp_db_handler.close_connection()
            return new_creds
        else:
            # Conexiunea a eșuat, mesajul de eroare este deja afișat de .connect()
            return None

    def handle_db_config_from_menu(self):
        # 1. Închidem orice conexiune existentă
        if self.db_handler:
            self.db_handler.close_connection()

        # 2. Obținem și validăm noile credențiale
        new_credentials = self.prompt_for_mariadb_credentials()
        
        if not self.master.winfo_exists(): return

        if new_credentials:
            # 3. Reconectare și verificare schemă cu noile credențiale
            self.status_label.config(text="Reconectare la DB și verificare schemă...")
            self.master.update_idletasks()
            
            self.db_handler = DatabaseHandler(db_credentials=new_credentials, app_master_ref=self.master)
            if not self.db_handler.connect() or not self.db_handler.check_and_setup_database_schema():
                messagebox.showerror("Eroare Critică", "Nu s-a putut stabili o conexiune validă sau configura schema DB cu noile date.", parent=self.master)
                self._toggle_action_buttons('disabled')
                return

            # 4. Salvăm noua configurație validă
            config_management.save_app_config(self)

            # 5. Resetăm starea internă a aplicației
            self.status_label.config(text="Resetare și reîncărcare interfață...")
            self.master.update_idletasks()
            self.active_account_id = None
            self.accounts_list = []
            self.account_combo_var.set("")
            self.total_transaction_count = 0
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            
            # Curățăm treeview-urile
            if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
                for item in self.nav_tree.get_children(""): self.nav_tree.delete(item)
            if hasattr(self, 'tree') and self.tree.winfo_exists():
                for item in self.tree.get_children(""): self.tree.delete(item)
            
            # 6. Apelăm metoda corectă de populare a UI-ului
            self.master.after(10, self.init_step4_populate_ui) # APEL CORECT
            
            messagebox.showinfo("Configurare Reușită", "Conexiunea la baza de date a fost actualizată cu succes.", parent=self.master)
        else:
            # Cazul în care utilizatorul a anulat sau credențialele au fost invalide
            self.db_handler = None # Asigurăm că handler-ul este invalid
            self.status_label.config(text="Configurare anulată/eșuată. Nicio conexiune DB.")
            self._toggle_action_buttons('disabled')
            self._populate_account_selector() # Golește combobox-ul de conturi
            self.refresh_ui_for_account_change() # Golește restul UI-ului

    def _schedule_ui_population_steps(self, context_msg=""):
        if not self.master.winfo_exists(): return

        self.master.after(0, self._populate_nav_tree) 
        self.master.after(20, self.update_total_count)   
        # --- MODIFICARE AICI: Apelăm noua funcție de restaurare a stării UI ---
        self.master.after(40, self._restore_initial_view)
        self.master.after(70, self.update_sort_indicator)
        self.master.after(100, lambda: {
            self.status_label.config(text="Pregătit.") if hasattr(self,'status_label') and self.status_label.winfo_exists() else None,
            # Logica de activare a butoanelor a fost deja corectată și va funcționa acum
            self._toggle_action_buttons('normal')
        })

    def _restore_initial_view(self):
        """
        Restaurează starea UI (navigare sau interval de date) pe baza setărilor
        încărcate pentru utilizator din baza de date.
        """
        if not (hasattr(self, 'master') and self.master.winfo_exists()):
            return

        filters = self.user_settings.get('filters', {})

        # Sincronizăm starea checkbox-ului și a controalelor de dată
        self.date_range_mode_var.set(filters.get('date_range_mode', False))
        self._toggle_filter_mode()
        if self.master.winfo_exists():
            self.master.update_idletasks()

        # Logica de restaurare a selecției, adaptată de la metoda veche
        if filters.get('date_range_mode'):
            start_str = filters.get('start_date', "")
            end_str = filters.get('end_date', "")
            if start_str and end_str:
                try:
                    parsed_start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    parsed_end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                    if hasattr(self, 'start_date'): self.start_date.set_date(parsed_start_date)
                    if hasattr(self, 'end_date'): self.end_date.set_date(parsed_end_date)
                    self.refresh_table()
                except (ValueError, TypeError):
                    self.set_date_range_to_db_bounds()
            else:
                self.set_date_range_to_db_bounds()
        else:  # Mod Navigare
            def restore_nav_selection_logic():
                if not (hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists()): return
                s_year_str = filters.get('nav_year', "")
                s_month_idx_str = filters.get('nav_month_idx', "0")
                s_day_str = filters.get('nav_day', "0")

                item_to_focus_iid, item_to_select_iid = None, None
                if s_year_str:
                    try:
                        s_year, s_month_idx, s_day = int(s_year_str), int(s_month_idx_str), int(s_day_str)
                        year_iid = f"year_{s_year}"
                        if self.nav_tree.exists(year_iid):
                            item_to_focus_iid = item_to_select_iid = year_iid
                            # ... (restul logicii de expandare și selecție rămâne identică)
                    except (ValueError, TypeError):
                        item_to_focus_iid, item_to_select_iid = None, None

                if item_to_select_iid and self.nav_tree.exists(item_to_select_iid): 
                    self.nav_tree.selection_set(item_to_select_iid)
                    self.nav_tree.focus(item_to_select_iid)
                    self.nav_tree.see(item_to_select_iid)
                else:
                    self._apply_nav_selection_to_datepickers_and_refresh()

            if self.master.winfo_exists():
                self.master.after(250, restore_nav_selection_logic)

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

        if not selected_item_id or selected_item_id.startswith("placeholder_") or selected_item_id.startswith("no_data"):
            self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
            self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            # --- BLOC NOU ADAUGAT PENTRU A PRELUA DATELE DUPĂ SETARE ---
            if hasattr(self, 'start_date') and self.start_date.get():
                start_dt_to_set = self.start_date.get_date()
            if hasattr(self, 'end_date') and self.end_date.get():
                end_dt_to_set = self.end_date.get_date()
            # --- SFÂRȘIT BLOC NOU ---
            self.refresh_table(start_date_override=start_dt_to_set, end_date_override=end_dt_to_set)
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
                # --- BLOC NOU ADAUGAT PENTRU A PRELUA DATELE DUPĂ SETARE ---
                if hasattr(self, 'start_date') and self.start_date.get(): start_dt_to_set = self.start_date.get_date()
                if hasattr(self, 'end_date') and self.end_date.get(): end_dt_to_set = self.end_date.get_date()
                # --- SFÂRȘIT BLOC NOU ---

        except (IndexError, ValueError) as e: 
            self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)
            if hasattr(self, 'start_date') and self.start_date.get(): start_dt_to_set = self.start_date.get_date()
            if hasattr(self, 'end_date') and self.end_date.get(): end_dt_to_set = self.end_date.get_date()
        
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
            
            # Logica a fost corectată aici
            if self.visible_tx_codes:
                placeholders = ', '.join(['%s'] * len(self.visible_tx_codes))
                # 1. Numele coloanei a fost corectat
                query += f" AND cod_tranzactie_fk IN ({placeholders})"
                params.extend(self.visible_tx_codes)
            # 2. Blocul 'else' a fost eliminat complet.
            #    Dacă 'self.visible_tx_codes' este goală, condiția 'if' este falsă
            #    și nu se adaugă niciun filtru suplimentar, ceea ce este corect.

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
        # Resetează variabilele la valorile implicite
        self.search_var.set("")
        self.type_var.set("Toate")
        self.search_column_var.set("Toate coloanele")
        
        if self.date_range_mode_var.get():
            self.date_range_mode_var.set(False)

        # Dezactivează controalele de dată
        if hasattr(self, 'start_date'): self.start_date.config(state='disabled')
        if hasattr(self, 'end_date'): self.end_date.config(state='disabled')

        # Resetează stilul și selecția din arborele de navigare
        if hasattr(self, 'nav_tree') and self.nav_tree.winfo_exists():
            style = ttk.Style(); style.configure("nav.Treeview", foreground="black"); self.nav_tree.config(style="nav.Treeview")
            for item in self.nav_tree.selection(): self.nav_tree.selection_remove(item)
        
        self.nav_selected_year, self.nav_selected_month_index, self.nav_selected_day = None, 0, 0
        
        self.set_date_range_to_db_bounds(called_by_nav_tree_logic=True)

        # --- MODIFICARE CHEIE ---
        # Apelăm funcția care sincronizează starea checkbox-ului "Căutare exactă".
        # Această funcție va apela la rândul ei 'on_filter_change', care va face refresh la tabel.
        self._on_search_column_changed()
        
        # Am eliminat 'self.refresh_table()' de aici pentru a evita un refresh duplicat,
        # deoarece este deja apelat prin '_on_search_column_changed'.

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
        # --- BLOC COMPLET MODIFICAT PENTRU A PERMITE IMPORTUL FĂRĂ CONT ACTIV ---
        
        # Starea de bază: există o conexiune la DB?
        is_db_connected = self.db_handler and self.db_handler.is_connected()
        
        # Starea contului: există un cont activ selectat?
        is_account_active = is_db_connected and self.active_account_id is not None
        
        # 1. Gestionăm starea combobox-ului de conturi
        if hasattr(self, 'account_selector_combo') and self.account_selector_combo.winfo_exists():
            try:
                # Activăm combobox-ul doar dacă sunt conturi în listă și DB e conectat
                account_combo_state = "readonly" if is_db_connected and self.accounts_list else "disabled"
                self.account_selector_combo.config(state=account_combo_state)
            except tk.TclError:
                pass

        # 2. Gestionăm butoanele care necesită OBLIGATORIU un cont activ
        buttons_requiring_account = {
            self.report_button: 'view_reports',
            self.balance_report_button: 'view_reports',
            self.analysis_button: 'view_reports',
            self.export_button: 'export_data'
        }
        
        for btn, perm_key in buttons_requiring_account.items():
            if isinstance(btn, (tk.Button, ttk.Button)) and btn.winfo_exists():
                try:
                    # Butonul este activ doar dacă:
                    # - Un cont este activ (is_account_active)
                    # - Utilizatorul are permisiunea necesară
                    final_state = tk.NORMAL if is_account_active and self.has_permission(perm_key) else tk.DISABLED
                    btn.config(state=final_state)
                except tk.TclError:
                    pass

        # 3. Gestionăm butonul de IMPORT separat
        # Acesta trebuie să fie activ dacă DB este conectat și utilizatorul are permisiunea,
        # CHIAR DACĂ nu există un cont activ.
        if hasattr(self, 'import_button') and self.import_button.winfo_exists():
            try:
                # Butonul este activ doar dacă:
                # - Baza de date este conectată (is_db_connected)
                # - Utilizatorul are permisiunea 'import_files'
                final_state = tk.NORMAL if is_db_connected and self.has_permission('import_files') else tk.DISABLED
                self.import_button.config(state=final_state)
            except tk.TclError:
                pass
                
        # 4. Gestionăm butonul de resetare filtre
        # Acesta ar trebui să fie activ dacă un cont este activ, pentru a avea ce reseta.
        if hasattr(self, 'reset_button') and self.reset_button.winfo_exists():
            try:
                self.reset_button.config(state=tk.NORMAL if is_account_active else tk.DISABLED)
            except tk.TclError:
                pass

        # Dacă starea generală este 'disabled' (ex: în timpul unei operațiuni), forțăm dezactivarea
        if state_str == 'disabled':
             for btn in self.action_buttons:
                if isinstance(btn, (tk.Button, ttk.Button)) and btn.winfo_exists():
                    try: btn.config(state=tk.DISABLED)
                    except tk.TclError: pass
        # --- SFÂRȘIT BLOC MODIFICAT ---

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
                if self.master.winfo_exists():
                    # Pasăm acum și calea fișierului (data) către funcția de finalizare
                    self.master.after(10, lambda: self._finalize_export_ui(f"Datele au fost exportate cu succes în:\n{data}", True, file_path=data))
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

    def _finalize_export_ui(self, message, success, file_path=None):
        if hasattr(self, 'current_progress_win') and self.current_progress_win:
            try:
                if self.current_progress_win.winfo_exists():
                    if self.current_progress_bar and self.current_progress_bar.winfo_exists(): self.current_progress_bar.stop()
                    self.current_progress_win.destroy()
            except tk.TclError: pass

        self.current_progress_win, self.current_progress_bar, self.current_progress_status_label_widget, self.export_thread = None, None, None, None
        
        if self.master.winfo_exists():
            if success:
                # --- BLOC NOU ADAUGAT ---
                if file_path and self.db_handler:
                    active_account_name = self.account_combo_var.get()
                    log_details = f"Export pentru contul '{active_account_name}' în fișierul '{os.path.basename(file_path)}'."
                    self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Export Excel", log_details)
                # --- SFÂRȘIT BLOC NOU ---
                messagebox.showinfo("Export Finalizat", message, parent=self.master)
            else:
                messagebox.showerror("Eroare la Export", message, parent=self.master)

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

        user_settings = db_handler.get_user_settings(user_data['id'])

        temp_root.destroy()

        # Pasul F: Crearea și rularea ferestrei principale
        root = tk.Tk()

        window_cfg = user_settings.get('window', {})
        window_geom = f"{window_cfg.get('width')}x{window_cfg.get('height')}+{window_cfg.get('x')}+{window_cfg.get('y')}" if window_cfg else None

        if window_geom:
            try:
                root.geometry(window_geom)
            except tk.TclError:
                root.state('zoomed') # Fallback la maximizat
        else:
            root.state('zoomed')

        app = BTViewerApp(root, user_data=user_data, db_handler=db_handler, user_settings=user_settings)
        
        root.protocol("WM_DELETE_WINDOW", lambda: ui_utils.handle_app_exit(app, root))
        
        root.mainloop()

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