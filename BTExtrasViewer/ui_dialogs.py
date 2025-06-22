# ui_dialogs.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
from .email_handler import test_smtp_connection
from datetime import date
from tkcalendar import DateEntry
# Modulele de bază sunt importate din 'common'
from common import config_management
from common import auth_handler
import mysql.connector
import logging
import re

class RoleManagerDialog(simpledialog.Dialog):
    """Dialog pentru managementul complet al rolurilor și permisiunilor."""
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.selected_role_id = None
        
        self.ALL_PERMISSIONS = {
            "Gestiune Utilizatori și Roluri": [
                ('manage_users', "Poate accesa fereastra 'Gestionare Utilizatori'"),
                ('manage_roles', "Poate accesa fereastra 'Gestionare Roluri'")
            ],
            "Gestiune Conturi Bancare": [
                ('manage_accounts', "Poate accesa 'Gestionare Conturi Bancare'"),
                ('create_account', "Poate adăuga conturi noi"),
                ('edit_account', "Poate edita conturile existente"),
                ('delete_account', "Poate șterge conturi")
            ],
            "Operațiuni cu Date": [
                ('import_files', "Poate importa fișiere MT940"),
                ('export_data', "Poate exporta date în Excel"),
                ('edit_transaction_notes', "Poate edita observațiile unei tranzacții")
            ],
            "Rapoarte și Analiză": [
                ('view_reports', "Poate vedea meniul și butoanele de rapoarte"),
                ('run_report_cashflow', "Poate genera raportul 'Flux de Numerar'"),
                ('run_report_balance_evolution', "Poate genera raportul 'Evoluție Sold'"),
                ('run_report_transaction_analysis', "Poate genera raportul 'Analiză Detaliată'"),
                ('send_reports_email', "Poate trimite rapoarte pe email")
            ],
            "Configurare și Jurnale": [
                ('configure_db', "Poate configura conexiunea la Baza de Date (Admin)"),
                ('configure_smtp', "Poate configura setările SMTP personale"),
                ('manage_transaction_types', "Poate modifica descrierile tipurilor de tranzacții"),
                ('manage_swift_codes', "Poate edita descrierile standard SWIFT"),
                ('manage_currencies', "Poate gestiona lista de valute"),
                ('view_import_history', "Poate vedea istoricul de importuri"),
                ('view_audit_log', "Poate vedea jurnalul de acțiuni")
            ]
        }
        
        super().__init__(parent, "Gestionare Roluri și Permisiuni")

    def body(self, master):
        main_pane = tk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        roles_frame = ttk.LabelFrame(main_pane, text="Roluri definite", width=200)
        main_pane.add(roles_frame, stretch="never")

        self.roles_listbox = tk.Listbox(roles_frame, exportselection=False)
        self.roles_listbox.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        self.roles_listbox.bind("<<ListboxSelect>>", self._on_role_select)
        
        roles_buttons_frame = ttk.Frame(roles_frame)
        roles_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.add_role_btn = ttk.Button(roles_buttons_frame, text="Adaugă", command=self._add_role)
        self.add_role_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.rename_role_btn = ttk.Button(roles_buttons_frame, text="Redenumește", command=self._rename_role, state=tk.DISABLED)
        self.rename_role_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.delete_role_btn = ttk.Button(roles_buttons_frame, text="Șterge", command=self._delete_role, state=tk.DISABLED)
        self.delete_role_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.permissions_main_frame = ttk.LabelFrame(main_pane, text="Permisiuni pentru rolul selectat")
        main_pane.add(self.permissions_main_frame, stretch="always")
        
        # --- MODIFICARE: Stocăm widget-urile, nu variabilele ---
        self.permission_widgets = {} 
        row_num = 0
        for category, perms in self.ALL_PERMISSIONS.items():
            cat_frame = ttk.LabelFrame(self.permissions_main_frame, text=category)
            cat_frame.pack(fill=tk.X, padx=10, pady=5)
            for key, desc in perms:
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(cat_frame, text=desc, variable=var, state=tk.DISABLED)
                # --- NOU: Atașăm variabila direct de widget ---
                cb.var = var 
                cb.pack(anchor=tk.W, padx=5)
                # --- MODIFICARE: Stocăm widget-ul (cb) ---
                self.permission_widgets[key] = cb 
            row_num += 1
            
        self.save_perms_btn = ttk.Button(self.permissions_main_frame, text="Salvează Permisiunile pentru Rol", command=self._save_permissions, state=tk.DISABLED)
        self.save_perms_btn.pack(pady=10)

        self._load_roles()
        return self.roles_listbox

    def _on_role_select(self, event):
        selections = self.roles_listbox.curselection()
        if not selections:
            self.selected_role_id = None
            self.rename_role_btn.config(state=tk.DISABLED)
            self.delete_role_btn.config(state=tk.DISABLED)
            self.save_perms_btn.config(state=tk.DISABLED)
            # --- MODIFICARE: Lucrăm cu widget-uri ---
            for key, widget in self.permission_widgets.items():
                widget.var.set(False)
                widget.config(state=tk.DISABLED)
        else:
            selected_index = selections[0]
            self.selected_role_id = self.all_roles_data[selected_index]['id']
            
            is_admin_role = (self.selected_role_id == 1)
            self.rename_role_btn.config(state=tk.DISABLED if is_admin_role else tk.NORMAL)
            self.delete_role_btn.config(state=tk.DISABLED if is_admin_role else tk.NORMAL)
            self.save_perms_btn.config(state=tk.NORMAL)
            
            role_permissions = self.db_handler.get_role_permissions(self.selected_role_id)
            # --- MODIFICARE: Lucrăm cu widget-uri și variabilele lor atașate ---
            for key, widget in self.permission_widgets.items():
                is_checked = key in role_permissions or 'all_permissions' in role_permissions
                widget.var.set(is_checked)
                widget.config(state=tk.DISABLED if is_admin_role else tk.NORMAL)

    def _save_permissions(self):
        if not self.selected_role_id: return
        # --- MODIFICARE: Citim starea de la variabila atașată widget-ului ---
        selected_permissions = [key for key, widget in self.permission_widgets.items() if widget.var.get()]
        if self.db_handler.save_permissions_for_role(self.selected_role_id, selected_permissions):
            messagebox.showinfo("Succes", "Permisiunile au fost salvate cu succes.", parent=self)
        else:
            messagebox.showerror("Eroare", "A apărut o eroare la salvarea permisiunilor.", parent=self)

    # ... restul metodelor (_load_roles, _add_role, etc.) rămân neschimbate ...
    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Închide", width=15, command=self.ok).pack(pady=5)
        box.pack()
    def _load_roles(self):
        self.roles_listbox.delete(0, tk.END)
        self.all_roles_data = self.db_handler.get_all_roles()
        for role in self.all_roles_data:
            self.roles_listbox.insert(tk.END, role['nume_rol'])
        self._on_role_select(None)
    def _add_role(self):
        new_name = simpledialog.askstring("Adaugă Rol", "Introduceți numele noului rol:", parent=self)
        if new_name and new_name.strip():
            success, message = self.db_handler.add_role(new_name.strip())
            if success: self._load_roles()
            else: messagebox.showerror("Eroare", message, parent=self)
    def _rename_role(self):
        if not self.selected_role_id: return
        current_name = self.roles_listbox.get(self.roles_listbox.curselection()[0])
        new_name = simpledialog.askstring("Redenumește Rol", f"Introduceți noul nume pentru rolul '{current_name}':", initialvalue=current_name, parent=self)
        if new_name and new_name.strip() != current_name:
            success, message = self.db_handler.rename_role(self.selected_role_id, new_name.strip())
            if success: self._load_roles()
            else: messagebox.showerror("Eroare", message, parent=self)
    def _delete_role(self):
        if not self.selected_role_id: return
        current_name = self.roles_listbox.get(self.roles_listbox.curselection()[0])
        if messagebox.askyesno("Confirmare Ștergere", f"Sunteți sigur că doriți să ștergeți rolul '{current_name}'?\n\nUtilizatorii care au acest rol îl vor pierde.", parent=self, icon='warning'):
            success, message = self.db_handler.delete_role(self.selected_role_id)
            if success: self._load_roles()
            else: messagebox.showerror("Eroare", message, parent=self)

class AccountEditDialog(simpledialog.Dialog):

    def __init__(self, parent, db_handler, account_data=None, title=None):
        self.db_handler = db_handler
        self.account_data = account_data
        self.result = None
        self.selected_color = account_data.get('culoare_cont', '#FFFFFF') if account_data and account_data.get('culoare_cont') else '#FFFFFF'
        if title is None:
            title = "Adaugă Cont Nou" if account_data is None else "Editează Cont Bancar"
        self.available_currencies = db_handler.get_all_currencies()
        if not self.available_currencies: # Fallback în caz de eroare
            self.available_currencies = ["RON", "EUR", "USD"]
        
        super().__init__(parent, title=title)

    def body(self, master):
        tk.Label(master, text="Nume Cont*:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.name_entry = tk.Entry(master, width=40)
        self.name_entry.grid(row=0, column=1, pady=2, padx=5)
        tk.Label(master, text="IBAN:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.iban_entry = tk.Entry(master, width=40)
        self.iban_entry.grid(row=1, column=1, pady=2, padx=5)
        tk.Label(master, text="Nume Bancă:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.bank_entry = tk.Entry(master, width=40)
        self.bank_entry.grid(row=2, column=1, pady=2, padx=5)
        tk.Label(master, text="Valută:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.currency_var = tk.StringVar(value="RON")
        self.currency_combo = ttk.Combobox(master, textvariable=self.currency_var, 
                                           values=self.available_currencies, # <<<< MODIFICARE AICI
                                           state="readonly", width=38)
        self.currency_combo.grid(row=3, column=1, pady=2, padx=5)
        tk.Label(master, text="Observații:").grid(row=4, column=0, sticky=tk.NW, pady=2, padx=5)
        obs_text_frame = ttk.Frame(master)
        obs_text_frame.grid(row=4, column=1, pady=2, padx=5, sticky="ew")
        self.obs_text = tk.Text(obs_text_frame, width=38, height=4, wrap=tk.WORD)
        obs_scrollbar = ttk.Scrollbar(obs_text_frame, orient=tk.VERTICAL, command=self.obs_text.yview)
        self.obs_text.configure(yscrollcommand=obs_scrollbar.set)
        self.obs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        obs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(master, text="Culoare Cont:").grid(row=5, column=0, sticky=tk.W, pady=(5,2), padx=5)
        color_frame = ttk.Frame(master)
        color_frame.grid(row=5, column=1, sticky=tk.W, pady=(5,2), padx=5)
        self.color_preview = tk.Frame(color_frame, width=24, height=24, relief=tk.SUNKEN, borderwidth=1)
        self.color_preview.pack(side=tk.LEFT, padx=(0, 5))
        self.color_button = ttk.Button(color_frame, text="Alege Culoare", command=self._choose_color)
        self.color_button.pack(side=tk.LEFT)
        if self.account_data:
            self.name_entry.insert(0, self.account_data.get('nume_cont', ''))
            self.iban_entry.insert(0, self.account_data.get('iban', '') or '')
            self.bank_entry.insert(0, self.account_data.get('nume_banca', '') or '')
            self.currency_var.set(self.account_data.get('valuta', 'RON'))
            self.obs_text.insert(tk.END, self.account_data.get('observatii_cont', '') or '')
        try:
            self.color_preview.config(background=self.selected_color)
        except tk.TclError:
            self.selected_color = '#FFFFFF'
            self.color_preview.config(background=self.selected_color)
        return self.name_entry
    def _choose_color(self):
        color_code = colorchooser.askcolor(title="Alegeți o culoare pentru cont", initialcolor=self.selected_color, parent=self)
        if color_code and color_code[1]:
            self.selected_color = color_code[1]
            try:
                self.color_preview.config(background=self.selected_color)
            except tk.TclError:
                messagebox.showwarning("Culoare Invalidă", "Culoarea selectată nu este validă.", parent=self)
                self.selected_color = '#FFFFFF'
                self.color_preview.config(background=self.selected_color)
    def validate(self):
        name = self.name_entry.get().strip()
        iban = self.iban_entry.get().strip().upper()
        if not name:
            messagebox.showwarning("Validare Eșuată", "Numele contului este obligatoriu.", parent=self)
            return False
        if iban and not (len(iban) >= 15 and len(iban) <= 34 and iban.isalnum()):
            messagebox.showwarning("Validare Eșuată", "IBAN-ul, dacă este specificat, trebuie să aibă între 15 și 34 de caractere alfanumerice.", parent=self)
            return False
        if not re.match(r"^#[0-9a-fA-F]{6}$", self.selected_color):
            messagebox.showwarning("Validare Eșuată", "Formatul culorii selectate este invalid. Trebuie să fie de tipul #RRGGBB.", parent=self)
            return False
        query_name = "SELECT id_cont FROM conturi_bancare WHERE nume_cont = %s"
        params_name = [name]
        if self.account_data and 'id_cont' in self.account_data:
            query_name += " AND id_cont != %s"
            params_name.append(self.account_data['id_cont'])
        try:
            if self.db_handler.fetch_scalar(query_name, tuple(params_name)):
                messagebox.showwarning("Validare Eșuată", "Un cont cu acest nume există deja.", parent=self)
                return False
        except mysql.connector.Error as e:
            messagebox.showerror("Eroare DB", f"Eroare la verificarea numelui contului: {e}", parent=self)
            return False
        if iban:
            query_iban = "SELECT id_cont FROM conturi_bancare WHERE iban = %s"
            params_iban = [iban]
            if self.account_data and 'id_cont' in self.account_data:
                query_iban += " AND id_cont != %s"
                params_iban.append(self.account_data['id_cont'])
            try:
                if self.db_handler.fetch_scalar(query_iban, tuple(params_iban)):
                    messagebox.showwarning("Validare Eșuată", "Un cont cu acest IBAN există deja.", parent=self)
                    return False
            except mysql.connector.Error as e:
                messagebox.showerror("Eroare DB", f"Eroare la verificarea IBAN-ului: {e}", parent=self)
                return False
        return True
    def apply(self):
        self.result = {"nume_cont": self.name_entry.get().strip(), "iban": self.iban_entry.get().strip().upper() or None, "nume_banca": self.bank_entry.get().strip() or None, "valuta": self.currency_var.get(), "observatii_cont": self.obs_text.get("1.0", tk.END).strip() or None, "culoare_cont": self.selected_color}

class AccountManagerDialog(simpledialog.Dialog):
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.selected_account_id = None
        super().__init__(parent, title="Gestionare Conturi Bancare")
    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("nume_cont", "iban", "nume_banca", "valuta", "observatii_cont")
        self.accounts_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        col_widths = {"nume_cont": 150, "iban": 220, "nume_banca": 120, "valuta": 60, "observatii_cont": 200}
        col_align = {"nume_cont": tk.W, "iban": tk.W, "nume_banca": tk.W, "valuta": tk.CENTER, "observatii_cont": tk.W}
        for col in cols:
            text = col.replace("_", " ").capitalize()
            self.accounts_tree.heading(col, text=text)
            self.accounts_tree.column(col, width=col_widths.get(col, 100), anchor=col_align.get(col, tk.W), minwidth=50)
        self.accounts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.accounts_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.accounts_tree.configure(yscrollcommand=scrollbar.set)
        self.accounts_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.accounts_tree.bind("<Double-1>", lambda e: self._on_edit_account())
        button_container = ttk.Frame(master)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(0,10), padx=10)
        self.add_button = ttk.Button(button_container, text="Adaugă Cont Nou", command=self._on_add_account)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.edit_button = ttk.Button(button_container, text="Modifică Selectat", command=self._on_edit_account, state=tk.DISABLED)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ttk.Button(button_container, text="Șterge Selectat", command=self._on_delete_account, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.close_button = ttk.Button(button_container, text="Închide", command=self.ok)
        self.close_button.pack(side=tk.RIGHT, padx=5)
        self.load_accounts()
        return self.accounts_tree
    def buttonbox(self): pass
    def load_accounts(self):
        for item in self.accounts_tree.get_children(): self.accounts_tree.delete(item)
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showerror("Eroare", "Lipsă conexiune la baza de date.", parent=self)
            return
        accounts_data = self.db_handler.get_all_accounts()
        if accounts_data:
            for acc in accounts_data:
                values = (acc.get('nume_cont', ''), acc.get('iban', ''), acc.get('nume_banca', ''), acc.get('valuta', ''), acc.get('observatii_cont', ''))
                self.accounts_tree.insert("", tk.END, iid=acc['id_cont'], values=values)
        self._on_tree_select(None)
    def _on_tree_select(self, event):
        selected_items = self.accounts_tree.selection()
        if selected_items:
            try: self.selected_account_id = int(selected_items[0])
            except ValueError: self.selected_account_id = None
            self.edit_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_account_id = None
            self.edit_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
    def _on_add_account(self):
        dialog = AccountEditDialog(self, self.db_handler, title="Adaugă Cont Nou")
        if dialog.result:
            try:
                sql = """INSERT INTO conturi_bancare (nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont) VALUES (%s, %s, %s, %s, %s, %s)"""
                params = (dialog.result['nume_cont'], dialog.result['iban'], dialog.result['nume_banca'], dialog.result['valuta'], dialog.result['observatii_cont'], dialog.result.get('culoare_cont', '#FFFFFF'))
                if self.db_handler.execute_commit(sql, params):
                    messagebox.showinfo("Succes", "Contul a fost adăugat.", parent=self)
                    self.load_accounts()
            except Exception as e:
                messagebox.showerror("Eroare Adăugare", f"Eroare: {e}", parent=self)
    def _on_edit_account(self):
        if not self.selected_account_id:
            messagebox.showwarning("Atenție", "Selectați un cont pentru a-l modifica.", parent=self)
            return
        account_data = self.db_handler.fetch_one_dict("SELECT * FROM conturi_bancare WHERE id_cont = %s", (self.selected_account_id,))
        if not account_data:
            messagebox.showerror("Eroare", "Contul selectat nu a fost găsit în baza de date.", parent=self)
            self.load_accounts()
            return
        dialog = AccountEditDialog(self, self.db_handler, account_data=account_data, title="Modifică Cont Bancar")
        if dialog.result:
            try:
                sql = """UPDATE conturi_bancare SET nume_cont=%s, iban=%s, nume_banca=%s, valuta=%s, observatii_cont=%s, culoare_cont=%s WHERE id_cont=%s"""
                params = (dialog.result['nume_cont'], dialog.result['iban'], dialog.result['nume_banca'], dialog.result['valuta'], dialog.result['observatii_cont'], dialog.result.get('culoare_cont', '#FFFFFF'), self.selected_account_id)
                if self.db_handler.execute_commit(sql, params):
                    messagebox.showinfo("Succes", "Contul a fost modificat.", parent=self)
                    self.load_accounts()
            except Exception as e:
                messagebox.showerror("Eroare Modificare", f"Eroare: {e}", parent=self)
    def _on_delete_account(self):
        if not self.selected_account_id:
            messagebox.showwarning("Atenție", "Selectați un cont pentru a-l șterge.", parent=self)
            return
        try:
            item_values = self.accounts_tree.item(str(self.selected_account_id), 'values')
            account_name_display = item_values[0] if item_values and item_values[0] else f"ID: {self.selected_account_id}"
        except tk.TclError: account_name_display = f"ID: {self.selected_account_id}"
        num_tranzactii = self.db_handler.fetch_scalar("SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk = %s", (self.selected_account_id,))
        if num_tranzactii is not None and num_tranzactii > 0:
            messagebox.showerror("Ștergere Eșuată", f"Contul '{account_name_display}' nu poate fi șters (are {num_tranzactii} tranzacții asociate).", parent=self)
            return
        confirm_delete = messagebox.askyesno("Confirmare Ștergere", f"Sunteți sigur că doriți să ștergeți contul '{account_name_display}'?", parent=self)
        if confirm_delete:
            try:
                if self.db_handler.execute_commit("DELETE FROM conturi_bancare WHERE id_cont = %s", (self.selected_account_id,)):
                    messagebox.showinfo("Succes", "Contul a fost șters.", parent=self)
                    self.load_accounts()
            except mysql.connector.Error as e_db:
                 messagebox.showerror("Eroare Ștergere DB", f"Nu s-a putut șterge contul:\n{e_db.msg}", parent=self)
            except Exception as e:
                messagebox.showerror("Eroare Ștergere", f"Eroare: {e}", parent=self)

class TransactionTypeManagerDialog(simpledialog.Dialog):
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.parent = parent
        self.check_vars = {}
        self.visibility_settings = config_management.load_transaction_type_visibility()
        super().__init__(parent, "Gestionare Vizibilitate Tipuri Tranzacții")
    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("cod", "descriere_tip", "vizibilitate_locala")
        self.types_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        self.types_tree.heading("cod", text="Cod Tehnic")
        self.types_tree.heading("descriere_tip", text="Descriere Personalizată")
        self.types_tree.heading("vizibilitate_locala", text="Vizibil Local (în Liste/Rapoarte)")
        self.types_tree.column("cod", width=100, anchor="w", stretch=False)
        self.types_tree.column("descriere_tip", width=300, anchor="w")
        self.types_tree.column("vizibilitate_locala", width=200, anchor="center", stretch=False)
        self.types_tree.tag_configure('vizibil', background='#D5F5E3')
        self.types_tree.tag_configure('ascuns', background='#FADBD8')
        self.types_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.types_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.types_tree.configure(yscrollcommand=scrollbar.set)
        self.types_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        button_container = ttk.Frame(master)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(0,10), padx=10)
        self.edit_button = ttk.Button(button_container, text="Modifică Descriere", command=self._on_edit_description, state=tk.DISABLED)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.toggle_button = ttk.Button(button_container, text="Comută Vizibilitate", command=self._on_toggle_visibility, state=tk.DISABLED)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_container, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=5)
        self.load_transaction_types()
        return self.types_tree
    def buttonbox(self): pass
    def load_transaction_types(self):
        for item in self.types_tree.get_children(): self.types_tree.delete(item)
        if not self.db_handler.is_connected(): return
        types_data = self.db_handler.fetch_all_dict("SELECT cod, descriere_tip FROM tipuri_tranzactii ORDER BY cod")
        if types_data:
            for type_info in types_data:
                cod = type_info['cod']
                is_visible = self.visibility_settings.get(cod.lower(), True)
                visibility_text = "Vizibil" if is_visible else "Ascuns"
                row_tag = 'vizibil' if is_visible else 'ascuns'
                values = (cod, type_info['descriere_tip'], visibility_text)
                self.types_tree.insert("", tk.END, iid=cod, values=values, tags=(row_tag,))
        self._on_tree_select(None)
    def _on_tree_select(self, event):
        selected_items = self.types_tree.selection()
        if selected_items:
            self.selected_code = selected_items[0]
            self.edit_button.config(state=tk.NORMAL)
            self.toggle_button.config(state=tk.NORMAL)
        else:
            self.selected_code = None
            self.edit_button.config(state=tk.DISABLED)
            self.toggle_button.config(state=tk.DISABLED)
    def _on_edit_description(self):
        if not self.selected_code: return
        current_description = self.types_tree.item(self.selected_code, 'values')[1]
        new_description = simpledialog.askstring("Modifică Descriere", f"Introduceți noua descriere pentru codul '{self.selected_code}':", initialvalue=current_description, parent=self)
        if new_description and new_description.strip():
            if self.db_handler.execute_commit("UPDATE tipuri_tranzactii SET descriere_tip = %s WHERE cod = %s", (new_description.strip(), self.selected_code)):
                self.load_transaction_types()
    def _on_toggle_visibility(self):
        if not self.selected_code: return
        cod_key = self.selected_code.lower()
        current_visibility = self.visibility_settings.get(cod_key, True)
        self.visibility_settings[cod_key] = not current_visibility
        config_management.save_transaction_type_visibility(self.visibility_settings)
        self.load_transaction_types()

class SMTPConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, initial_config=None):
        self.initial_config = initial_config or {}
        super().__init__(parent, "Configurare Trimitere Email (SMTP)")
    def body(self, master):
        tk.Label(master, text="Server SMTP:").grid(row=0, sticky="w", pady=2)
        self.server_entry = tk.Entry(master, width=40)
        self.server_entry.grid(row=0, column=1, pady=2)
        self.server_entry.insert(0, self.initial_config.get('server', ''))
        tk.Label(master, text="Port:").grid(row=1, sticky="w", pady=2)
        self.port_entry = tk.Entry(master, width=40)
        self.port_entry.grid(row=1, column=1, pady=2)
        self.port_entry.insert(0, self.initial_config.get('port', '465'))
        tk.Label(master, text="Securitate:").grid(row=2, sticky="w", pady=2)
        self.security_var = tk.StringVar(value=self.initial_config.get('security', 'SSL/TLS'))
        self.security_combo = ttk.Combobox(master, textvariable=self.security_var, values=["SSL/TLS", "STARTTLS", "Niciuna"], state="readonly", width=38)
        self.security_combo.grid(row=2, column=1, pady=2)
        tk.Label(master, text="Email Expeditor:").grid(row=3, sticky="w", pady=2)
        self.sender_email_entry = tk.Entry(master, width=40)
        self.sender_email_entry.grid(row=3, column=1, pady=2)
        self.sender_email_entry.insert(0, self.initial_config.get('sender_email', ''))
        tk.Label(master, text="Utilizator (dacă e diferit):").grid(row=4, sticky="w", pady=2)
        self.user_entry = tk.Entry(master, width=40)
        self.user_entry.grid(row=4, column=1, pady=2)
        self.user_entry.insert(0, self.initial_config.get('user', ''))
        tk.Label(master, text="Parola:").grid(row=5, sticky="w", pady=2)
        self.password_entry = tk.Entry(master, show="*", width=40)
        self.password_entry.grid(row=5, column=1, pady=2)
        self.password_entry.insert(0, self.initial_config.get('password', ''))
        return self.server_entry
    def buttonbox(self):
        box = ttk.Frame(self)
        test_button = ttk.Button(box, text="Testează Conexiunea", width=20, command=self.test_connection)
        test_button.pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Salvează", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Anulează", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()
    def get_current_config(self):
        try: port = int(self.port_entry.get().strip())
        except ValueError: port = 0
        user = self.user_entry.get().strip()
        sender = self.sender_email_entry.get().strip()
        return {'server': self.server_entry.get().strip(), 'port': port, 'security': self.security_var.get(), 'sender_email': sender, 'user': user if user else sender, 'password': self.password_entry.get()}
    def test_connection(self):
        config = self.get_current_config()
        success, message = test_smtp_connection(config)
        if success: messagebox.showinfo("Test Conexiune", message, parent=self)
        else: messagebox.showerror("Test Conexiune", message, parent=self)
    def validate(self):
        config = self.get_current_config()
        if not all([config['server'], config['port'], config['sender_email'], config['user']]):
            messagebox.showwarning("Date Incomplete", "Câmpurile Server, Port, Email Expeditor și Utilizator sunt obligatorii.", parent=self)
            return 0
        return 1
    def apply(self):
        self.result = self.get_current_config()

class BalanceReportConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, app_instance, accounts_list):
        self.accounts_list = accounts_list
        self.main_app_instance = app_instance
        super().__init__(parent, "Configurare Raport Evoluție Sold")
    def body(self, master):
        tk.Label(master, text="Cont Bancar:").grid(row=0, sticky="w", pady=2, padx=5)
        self.account_var = tk.StringVar()
        account_names = [acc['nume_cont'] for acc in self.accounts_list]
        self.account_combo = ttk.Combobox(master, textvariable=self.account_var, values=account_names, state="readonly", width=38)
        self.account_combo.grid(row=0, column=1, pady=2, padx=5)
        if account_names:
            active_account_name = self.main_app_instance.account_combo_var.get()
            if active_account_name in account_names: self.account_combo.set(active_account_name)
            else: self.account_combo.set(account_names[0])
        tk.Label(master, text="Data de început:").grid(row=1, sticky="w", pady=2, padx=5)
        self.start_date_entry = DateEntry(master, date_pattern='yyyy-mm-dd', width=38)
        self.start_date_entry.grid(row=1, column=1, pady=2, padx=5)
        today = date.today()
        self.start_date_entry.set_date(today.replace(day=1, month=1))
        tk.Label(master, text="Data de sfârșit:").grid(row=2, sticky="w", pady=2, padx=5)
        self.end_date_entry = DateEntry(master, date_pattern='yyyy-mm-dd', width=38)
        self.end_date_entry.grid(row=2, column=1, pady=2, padx=5)
        tk.Label(master, text="Granularitate:").grid(row=3, sticky="w", pady=2, padx=5)
        self.granularity_var = tk.StringVar(value="Zilnică")
        self.granularity_combo = ttk.Combobox(master, textvariable=self.granularity_var, values=["Zilnică", "Lună", "Anuală"], state="readonly", width=38)
        self.granularity_combo.grid(row=3, column=1, pady=2, padx=5)
        return self.account_combo
    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Generează Raport", width=15, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Anulează", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=5)
    def validate(self):
        if not self.account_var.get():
            messagebox.showwarning("Selecție Invalidă", "Vă rugăm selectați un cont.", parent=self)
            return 0
        try:
            start_date = self.start_date_entry.get_date()
            end_date = self.end_date_entry.get_date()
        except (TypeError, ValueError):
             messagebox.showwarning("Dată Invalidă", "Vă rugăm introduceți o dată validă.", parent=self)
             return 0
        if start_date > end_date:
            messagebox.showwarning("Interval Invalid", "Data de început nu poate fi după data de sfârșit.", parent=self)
            return 0
        return 1
    def apply(self):
        selected_account = next((acc for acc in self.accounts_list if acc['nume_cont'] == self.account_var.get()), None)
        if not selected_account:
            self.result = None
            return
        self.result = {"account_id": selected_account['id_cont'], "account_name": selected_account['nume_cont'], "start_date": self.start_date_entry.get_date(), "end_date": self.end_date_entry.get_date(), "granularity": self.granularity_var.get(), "currency": selected_account.get('valuta', 'RON')}

class LoginDialog(simpledialog.Dialog):
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        super().__init__(parent, "Autentificare BTExtrasViewer")
    def body(self, master):
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        tk.Label(master, text="Nume utilizator:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.username_entry = tk.Entry(master, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(master, text="Parola:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.password_entry = tk.Entry(master, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        self.parent = master.winfo_toplevel()
        self.parent.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        return self.username_entry
    def validate(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("Date lipsă", "Numele de utilizator și parola sunt obligatorii.", parent=self)
            return False
        user_db_data = self.db_handler.get_user_by_username(username)
        if not user_db_data:
            messagebox.showerror("Autentificare eșuată", "Nume de utilizator sau parolă incorectă.", parent=self)
            return False
        if not user_db_data.get('activ'):
            messagebox.showerror("Cont inactiv", "Acest cont de utilizator este inactiv.", parent=self)
            return False
        is_password_valid = auth_handler.verifica_parola(parola_introdusa=password, salt_hex=user_db_data['salt'], hash_stocat_hex=user_db_data['parola_hash'])
        if not is_password_valid:
            messagebox.showerror("Autentificare eșuată", "Nume de utilizator sau parolă incorectă.", parent=self)
            return False
        user_id = user_db_data['id']
        permissions = self.db_handler.get_user_permissions(user_id)
        allowed_accounts = self.db_handler.get_allowed_accounts_for_user(user_id)
        self.result = {
            'id': user_id,
            'username': username,
            'nume_complet': user_db_data.get('nume_complet'), # <-- LINIE NOUĂ
            'permissions': permissions, 
            'allowed_accounts': allowed_accounts,
            'has_all_permissions': 'all_permissions' in permissions,
            'tranzactie_acces': user_db_data.get('tranzactie_acces', 'toate')
        }
        self.db_handler.log_action(user_id, username, "Login reușit")
        return True
    def apply(self): pass

class UserEditDialog(simpledialog.Dialog):
    """Dialog modal pentru adăugarea sau modificarea unui utilizator, bazat pe roluri."""
    def __init__(self, parent, db_handler, user_id=None, current_user=None):
        self.db_handler = db_handler
        self.user_id = user_id
        self.current_user = current_user
        self.user_data = None
        if self.user_id:
            self.user_data = self.db_handler.get_user_details(self.user_id)
            title = f"Editare Utilizator: {self.user_data['username']}"
        else:
            title = "Adaugă Utilizator Nou"
        super().__init__(parent, title)

    def body(self, master):
        main_frame = ttk.Frame(master)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        details_frame = ttk.LabelFrame(main_frame, text="Detalii Utilizator")
        details_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        tk.Label(details_frame, text="Nume utilizator*:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.username_entry = tk.Entry(details_frame, width=40)
        self.username_entry.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(details_frame, text="Nume complet:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.fullname_entry = tk.Entry(details_frame, width=40)
        self.fullname_entry.grid(row=1, column=1, padx=5, pady=2)

        password_label_text = "Parola*:" if not self.user_id else "Parolă nouă:"
        tk.Label(details_frame, text=password_label_text).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.password_entry = tk.Entry(details_frame, show="*", width=40)
        self.password_entry.grid(row=2, column=1, padx=5, pady=2)
        if self.user_id:
            tk.Label(details_frame, text="(lasă gol pentru a nu schimba)", font=("TkDefaultFont", 8, "italic")).grid(row=2, column=2, sticky=tk.W)
        
        # --- SECȚIUNE NOUĂ PENTRU ACCES TRANZACȚII ---
        tk.Label(details_frame, text="Acces Tranzacții:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.tx_access_var = tk.StringVar(value='toate')
        self.tx_access_combo = ttk.Combobox(details_frame, textvariable=self.tx_access_var, values=['toate', 'credit', 'debit'], state='readonly', width=38)
        self.tx_access_combo.grid(row=3, column=1, pady=2, padx=5)


        permissions_frame = ttk.Frame(main_frame)
        permissions_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        permissions_frame.grid_columnconfigure(0, weight=1)
        permissions_frame.grid_columnconfigure(1, weight=1)

        # --- Panou pentru ROLURI (înlocuiește permisiunile individuale) ---
        roles_frame = ttk.LabelFrame(permissions_frame, text="Roluri Asignate")
        roles_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        
        self.roles_listbox = tk.Listbox(roles_frame, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        roles_scrollbar = ttk.Scrollbar(roles_frame, orient=tk.VERTICAL, command=self.roles_listbox.yview)
        self.roles_listbox.configure(yscrollcommand=roles_scrollbar.set)
        self.roles_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roles_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.all_roles = self.db_handler.get_all_roles()
        for role in self.all_roles:
            self.roles_listbox.insert(tk.END, role['nume_rol'])

        # --- Panou pentru CONTURI BANCARE ---
        accounts_frame = ttk.LabelFrame(permissions_frame, text="Conturi Bancare Permise")
        accounts_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")

        self.accounts_listbox = tk.Listbox(accounts_frame, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        accounts_scrollbar = ttk.Scrollbar(accounts_frame, orient=tk.VERTICAL, command=self.accounts_listbox.yview)
        self.accounts_listbox.configure(yscrollcommand=accounts_scrollbar.set)
        self.accounts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        accounts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.all_accounts = self.db_handler.get_all_accounts()
        for acc in self.all_accounts:
            self.accounts_listbox.insert(tk.END, acc['nume_cont'])

        # Pre-populare date pentru editare
        if self.user_data:
            self.username_entry.insert(0, self.user_data.get('username') or '')
            self.username_entry.config(state=tk.DISABLED)
            self.fullname_entry.insert(0, self.user_data.get('nume_complet') or '')
            self.tx_access_var.set(self.user_data.get('tranzactie_acces', 'toate'))
            
            for i, role in enumerate(self.all_roles):
                if role['id'] in self.user_data.get('role_ids', set()):
                    self.roles_listbox.selection_set(i)
            
            for i, acc in enumerate(self.all_accounts):
                if acc['id_cont'] in self.user_data.get('account_ids', set()):
                    self.accounts_listbox.selection_set(i)

        return self.username_entry

    def validate(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showwarning("Validare eșuată", "Numele de utilizator este obligatoriu.", parent=self)
            return False
        if not self.user_id:
            if not self.password_entry.get():
                messagebox.showwarning("Validare eșuată", "Parola este obligatorie la crearea unui utilizator nou.", parent=self)
                return False
            existing_user = self.db_handler.fetch_scalar("SELECT id FROM utilizatori WHERE username = %s", (username,))
            if existing_user:
                messagebox.showwarning("Validare eșuată", "Acest nume de utilizator există deja.", parent=self)
                return False
        
        if self.user_id:
            is_currently_admin = False
            admin_role_id = None
            for role in self.all_roles:
                if role['nume_rol'] == 'Administrator':
                    admin_role_id = role['id']
                    if admin_role_id in self.user_data.get('role_ids', set()):
                        is_currently_admin = True
                    break
            if is_currently_admin:
                admin_count = self.db_handler.count_active_admins()
                if admin_count <= 1:
                    selected_indices = self.roles_listbox.curselection()
                    new_selected_role_ids = {self.all_roles[i]['id'] for i in selected_indices}
                    if admin_role_id not in new_selected_role_ids:
                        messagebox.showerror("Operațiune Nepermisă", "Nu puteți elimina rolul de 'Administrator' de la singurul cont de administrator activ.", parent=self)
                        return False
        return True

    def apply(self):
        # Pasul 1: Colectarea datelor din formular
        username = self.username_entry.get().strip()
        fullname = self.fullname_entry.get().strip() or None
        password = self.password_entry.get()
        tx_access = self.tx_access_var.get()
        
        selected_role_indices = self.roles_listbox.curselection()
        selected_role_ids = [self.all_roles[i]['id'] for i in selected_role_indices]

        selected_account_indices = self.accounts_listbox.curselection()
        selected_account_ids = [self.all_accounts[i]['id_cont'] for i in selected_account_indices]

        cursor = None
        try:
            # --- MODIFICARE: Am eliminat blocurile de management manual al tranzacției ---
            # if self.db_handler.conn.in_transaction: ...
            # self.db_handler.conn.start_transaction()
            
            cursor = self.db_handler.conn.cursor()
            
            if self.user_id: 
                # --- Logică de MODIFICARE ---
                if password:
                    salt, pass_hash = auth_handler.hash_parola(password)
                    cursor.execute("UPDATE utilizatori SET nume_complet = %s, parola_hash = %s, salt = %s, tranzactie_acces = %s WHERE id = %s",
                                   (fullname, pass_hash, salt, tx_access, self.user_id))
                else:
                    cursor.execute("UPDATE utilizatori SET nume_complet = %s, tranzactie_acces = %s WHERE id = %s", (fullname, tx_access, self.user_id))

                cursor.execute("DELETE FROM utilizatori_roluri WHERE id_utilizator = %s", (self.user_id,))
                if selected_role_ids:
                    cursor.executemany("INSERT INTO utilizatori_roluri (id_utilizator, id_rol) VALUES (%s, %s)", [(self.user_id, r_id) for r_id in selected_role_ids])

                cursor.execute("DELETE FROM utilizatori_conturi_permise WHERE id_utilizator = %s", (self.user_id,))
                if selected_account_ids:
                    cursor.executemany("INSERT INTO utilizatori_conturi_permise (id_utilizator, id_cont) VALUES (%s, %s)", [(self.user_id, a_id) for a_id in selected_account_ids])
                
                log_details = f"Utilizatorul '{username}' a fost modificat."
                self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Modificare utilizator", log_details)
            else: 
                # --- Logică de ADĂUGARE ---
                salt, pass_hash = auth_handler.hash_parola(password)
                cursor.execute("INSERT INTO utilizatori (username, nume_complet, parola_hash, salt, tranzactie_acces) VALUES (%s, %s, %s, %s, %s)",
                               (username, fullname, pass_hash, salt, tx_access))
                new_user_id = cursor.lastrowid
                
                if selected_role_ids:
                    cursor.executemany("INSERT INTO utilizatori_roluri (id_utilizator, id_rol) VALUES (%s, %s)", [(new_user_id, r_id) for r_id in selected_role_ids])
                
                if selected_account_ids:
                    cursor.executemany("INSERT INTO utilizatori_conturi_permise (id_utilizator, id_cont) VALUES (%s, %s)", [(new_user_id, a_id) for a_id in selected_account_ids])

                log_details = f"Utilizatorul '{username}' a fost creat."
                self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Adăugare utilizator", log_details)

            # Finalizarea cu succes a tranzacției
            self.db_handler.conn.commit()
            self.result = True

        except mysql.connector.Error as e:
            # Anularea tranzacției în caz de eroare
            self.db_handler.conn.rollback()
            messagebox.showerror("Eroare Bază de Date", f"Nu s-a putut salva utilizatorul:\n{e.msg}", parent=self)
            self.result = False
        finally:
            # Închiderea cursorului la final
            if cursor:
                cursor.close()

# --- CLASĂ MODIFICATĂ: UserManagerDialog ---
class UserManagerDialog(simpledialog.Dialog):
    def __init__(self, parent, db_handler, current_user):
        self.db_handler = db_handler
        self.current_user = current_user
        self.selected_user_id = None
        self.selected_user_is_active = None
        super().__init__(parent, "Gestionare Utilizatori")
    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("username", "nume_complet", "roluri", "stare")
        self.users_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        col_widths = {"username": 150, "nume_complet": 200, "roluri": 250, "stare": 80}
        for col in cols:
            self.users_tree.heading(col, text=col.replace("_", " ").capitalize())
            self.users_tree.column(col, width=col_widths.get(col, 150), anchor=tk.W)
        self.users_tree.tag_configure('inactive', foreground='gray')
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        self.users_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.users_tree.bind("<Double-1>", lambda e: self._on_edit_user())
        button_container = ttk.Frame(master)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(0,10), padx=10)
        self.add_button = ttk.Button(button_container, text="Adaugă Utilizator", command=self._on_add_user)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.edit_button = ttk.Button(button_container, text="Modifică Selectat", command=self._on_edit_user, state=tk.DISABLED)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.toggle_status_button = ttk.Button(button_container, text="Activează/Dezactivează", command=self._on_toggle_status, state=tk.DISABLED)
        self.toggle_status_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ttk.Button(button_container, text="Șterge Utilizator", command=self._on_delete_user, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_container, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=5)
        self.load_users()
        return self.users_tree
    def buttonbox(self): pass
    def load_users(self):
        for item in self.users_tree.get_children(): self.users_tree.delete(item)
        users_data = self.db_handler.get_all_users_with_roles()
        if users_data:
            for user in users_data:
                stare = "Activ" if user['activ'] else "Inactiv"
                tags = () if user['activ'] else ('inactive',)
                values = (user['username'], user.get('nume_complet', ''), user.get('roluri', 'N/A'), stare)
                self.users_tree.insert("", tk.END, iid=user['id'], values=values, tags=tags)
        self._on_tree_select(None)
    def _on_tree_select(self, event=None):
        selected_items = self.users_tree.selection()
        if selected_items:
            self.selected_user_id = int(selected_items[0])
            item_data = self.users_tree.item(selected_items[0])
            self.selected_user_is_active = item_data['values'][3] == "Activ"
            self.edit_button.config(state=tk.NORMAL)
            if self.selected_user_id == 1:
                self.toggle_status_button.config(state=tk.DISABLED, text="Dezactivează")
                self.delete_button.config(state=tk.DISABLED)
            else:
                self.toggle_status_button.config(state=tk.NORMAL)
                self.toggle_status_button.config(text="Dezactivează" if self.selected_user_is_active else "Activează")
                self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_user_id = None
            self.selected_user_is_active = None
            self.edit_button.config(state=tk.DISABLED)
            self.toggle_status_button.config(state=tk.DISABLED, text="Activează/Dezactivează")
            self.delete_button.config(state=tk.DISABLED)
    def _on_delete_user(self):
        if not self.selected_user_id: return
        try:
            item_values = self.users_tree.item(self.selected_user_id)['values']
            username = item_values[0]
            roles_str = item_values[2]
            is_admin = 'Administrator' in (roles_str or '')
        except (IndexError, tk.TclError):
            messagebox.showerror("Eroare", "Nu s-au putut prelua detaliile utilizatorului selectat.", parent=self)
            return
        if is_admin:
            admin_count = self.db_handler.count_active_admins()
            if admin_count <= 1:
                messagebox.showerror("Operațiune Nepermisă", "Nu puteți șterge singurul cont de administrator activ.", parent=self)
                return
        if messagebox.askyesno("Confirmare Ștergere", f"Sunteți absolut sigur că doriți să ștergeți PERMANENT utilizatorul '{username}'?\n\nAceastă acțiune nu poate fi anulată.", parent=self, icon='warning'):
            success, message = self.db_handler.delete_user(self.selected_user_id)
            if success:
                log_details = f"Utilizatorul '{username}' (ID: {self.selected_user_id}) a fost șters."
                self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Ștergere utilizator", log_details)
                messagebox.showinfo("Succes", message, parent=self)
                self.load_users()
            else:
                messagebox.showerror("Eroare", message, parent=self)
    def _on_add_user(self):
        dialog = UserEditDialog(self, self.db_handler, current_user=self.current_user)
        if dialog.result:
            messagebox.showinfo("Succes", "Utilizatorul a fost adăugat.", parent=self)
            self.load_users()
    def _on_edit_user(self):
        if not self.selected_user_id: return
        dialog = UserEditDialog(self, self.db_handler, user_id=self.selected_user_id, current_user=self.current_user)
        if dialog.result:
            messagebox.showinfo("Succes", "Utilizatorul a fost modificat.", parent=self)
            self.load_users()
    def _on_toggle_status(self):
        if not self.selected_user_id: return
        item_values = self.users_tree.item(self.selected_user_id)['values']
        username = item_values[0]
        roles_str = item_values[2]
        is_admin = 'Administrator' in (roles_str or '')
        action_text = "dezactivați" if self.selected_user_is_active else "activați"
        if is_admin and self.selected_user_is_active:
            admin_count = self.db_handler.count_active_admins()
            if admin_count <= 1:
                messagebox.showerror("Operațiune Nepermisă", "Nu puteți dezactiva singurul cont de administrator activ.", parent=self)
                return
        if messagebox.askyesno("Confirmare", f"Sunteți sigur că doriți să {action_text} utilizatorul '{username}'?", parent=self):
            success, message = self.db_handler.toggle_user_status(self.selected_user_id)
            if success:
                log_action_text = f"Dezactivare utilizator" if self.selected_user_is_active else "Activare utilizator"
                log_details = f"Utilizatorul '{username}' a fost {action_text}."
                self.db_handler.log_action(self.current_user['id'], self.current_user['username'], log_action_text, log_details)
                self.load_users()
            else:
                messagebox.showerror("Eroare", message, parent=self)

class SwiftCodeManagerDialog(simpledialog.Dialog):
    """Dialog pentru managementul descrierilor standard ale codurilor SWIFT."""
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.selected_code = None
        super().__init__(parent, "Gestionare Descrieri Standard SWIFT")

    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("cod", "descriere")
        self.codes_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        self.codes_tree.heading("cod", text="Cod SWIFT")
        self.codes_tree.heading("descriere", text="Descriere Standard")
        self.codes_tree.column("cod", width=100, anchor="w", stretch=False)
        self.codes_tree.column("descriere", width=450, anchor="w")
        self.codes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.codes_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.codes_tree.configure(yscrollcommand=scrollbar.set)
        self.codes_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.codes_tree.bind("<Double-1>", lambda e: self._on_edit_description())

        button_container = ttk.Frame(master)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10), padx=10)
        self.edit_button = ttk.Button(button_container, text="Modifică Descriere", command=self._on_edit_description, state=tk.DISABLED)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_container, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=5)
        
        self.load_codes()
        return self.codes_tree

    def buttonbox(self): pass

    def load_codes(self):
        for item in self.codes_tree.get_children(): self.codes_tree.delete(item)
        if not self.db_handler.is_connected(): return
        
        # Creăm o metodă nouă în db_handler pentru a prelua aceste date
        codes_data = self.db_handler.get_all_swift_descriptions()
        if codes_data:
            for code_info in codes_data:
                values = (code_info['cod_swift'], code_info['descriere_standard'])
                self.codes_tree.insert("", tk.END, iid=code_info['cod_swift'], values=values)
        self._on_tree_select(None)

    def _on_tree_select(self, event):
        selected_items = self.codes_tree.selection()
        if selected_items:
            self.selected_code = selected_items[0]
            self.edit_button.config(state=tk.NORMAL)
        else:
            self.selected_code = None
            self.edit_button.config(state=tk.DISABLED)

    def _on_edit_description(self):
        if not self.selected_code: return
        current_description = self.codes_tree.item(self.selected_code, 'values')[1]
        new_description = simpledialog.askstring("Modifică Descriere", f"Introduceți noua descriere pentru codul '{self.selected_code}':", initialvalue=current_description, parent=self)
        if new_description and new_description.strip():
            # Creăm o metodă nouă în db_handler pentru update
            if self.db_handler.update_swift_description(self.selected_code, new_description.strip()):
                self.load_codes()
            else:
                messagebox.showerror("Eroare", "Nu s-a putut actualiza descrierea.", parent=self)

class CurrencyManagerDialog(simpledialog.Dialog):
    """Dialog pentru managementul valutelor disponibile în aplicație."""
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.selected_currency = None
        super().__init__(parent, "Gestionare Valute")

    def body(self, master):
        list_frame = ttk.Frame(master)
        list_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.currency_listbox = tk.Listbox(list_frame, exportselection=False, height=10)
        self.currency_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.currency_listbox.bind("<<ListboxSelect>>", self._on_list_select)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.currency_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.currency_listbox.configure(yscrollcommand=scrollbar.set)
        
        button_container = ttk.Frame(master)
        button_container.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.add_btn = ttk.Button(button_container, text="Adaugă Valută", command=self._add_currency)
        self.add_btn.pack(side=tk.LEFT)
        self.delete_btn = ttk.Button(button_container, text="Șterge Selectat", command=self._delete_currency, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=5)

        self.load_currencies()
        return self.currency_listbox
        
    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Închide", width=15, command=self.ok).pack(pady=5)
        box.pack()

    def load_currencies(self):
        self.currency_listbox.delete(0, tk.END)
        all_currencies = self.db_handler.get_all_currencies()
        for curr in all_currencies:
            self.currency_listbox.insert(tk.END, curr)
        self._on_list_select(None)

    def _on_list_select(self, event):
        selections = self.currency_listbox.curselection()
        if selections:
            self.selected_currency = self.currency_listbox.get(selections[0])
            # Nu permitem ștergerea RON
            if self.selected_currency == "RON":
                self.delete_btn.config(state=tk.DISABLED)
            else:
                self.delete_btn.config(state=tk.NORMAL)
        else:
            self.selected_currency = None
            self.delete_btn.config(state=tk.DISABLED)
            
    def _add_currency(self):
        new_curr = simpledialog.askstring("Adaugă Valută", "Introduceți codul noii valute (ex: HUF, CAD):", parent=self)
        if new_curr:
            new_curr = new_curr.strip().upper()
            if not (3 <= len(new_curr) <= 5 and new_curr.isalpha()):
                messagebox.showerror("Format Invalid", "Codul valutei trebuie să conțină între 3 și 5 litere.", parent=self)
                return
            
            success, message = self.db_handler.add_currency(new_curr)
            if success:
                self.load_currencies()
            else:
                messagebox.showerror("Eroare Adăugare", message, parent=self)

    def _delete_currency(self):
        if not self.selected_currency: return
        
        if messagebox.askyesno("Confirmare Ștergere", f"Sunteți sigur că doriți să ștergeți valuta '{self.selected_currency}'?", icon='warning', parent=self):
            success, message = self.db_handler.delete_currency(self.selected_currency)
            if success:
                self.load_currencies()
            else:
                messagebox.showerror("Ștergere Eșuată", message, parent=self)