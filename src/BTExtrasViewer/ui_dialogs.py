# ui_dialogs.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
from .email_handler import test_smtp_connection
from common.app_constants import APP_NAME
from datetime import date
from datetime import datetime
from tkcalendar import DateEntry
# Modulele de bază sunt importate din 'common'
from common.config_management import save_app_config
from common import auth_handler # Acesta poate rămâne așa sau poate fi schimbat, dar îl lăsăm momentan pentru simplitate
import pymysql
import logging
import hashlib
import re

class RoleManagerDialog(simpledialog.Dialog):
    """Dialog pentru managementul complet al rolurilor și permisiunilor."""
    def __init__(self, parent, db_handler):
        self.db_handler = db_handler
        self.selected_role_id = None
        self.all_roles_data = []
        
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
        main_frame = ttk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        roles_frame = ttk.LabelFrame(main_frame, text="Roluri definite", width=250)
        roles_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

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

        self.permissions_main_frame = ttk.LabelFrame(main_frame, text="Permisiuni pentru rolul selectat")
        self.permissions_main_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.permission_widgets = {}
        for category, perms in self.ALL_PERMISSIONS.items():
            cat_frame = ttk.LabelFrame(self.permissions_main_frame, text=category)
            cat_frame.pack(fill=tk.X, padx=10, pady=5, anchor="n")
            for key, desc in perms:
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(cat_frame, text=desc, variable=var, state=tk.DISABLED)
                cb.var = var
                cb.pack(anchor=tk.W, padx=5, pady=1)
                self.permission_widgets[key] = cb
            
        self.save_perms_btn = ttk.Button(self.permissions_main_frame, text="Salvează Permisiunile pentru Rol", command=self._save_permissions, state=tk.DISABLED)
        self.save_perms_btn.pack(pady=10, side=tk.BOTTOM)

        self._load_roles()
        return self.roles_listbox

    def buttonbox(self):
        # Butonul de închidere este acum adăugat în metoda 'body' a dialogului principal al aplicației.
        # Lăsăm această funcție goală pentru a urma modelul celorlalte dialoguri complexe.
        pass

    def _on_role_select(self, event):
        selections = self.roles_listbox.curselection()
        if not selections:
            self.selected_role_id = None
            self.rename_role_btn.config(state=tk.DISABLED)
            self.delete_role_btn.config(state=tk.DISABLED)
            self.save_perms_btn.config(state=tk.DISABLED)
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
            for key, widget in self.permission_widgets.items():
                is_checked = key in role_permissions or 'all_permissions' in role_permissions
                widget.var.set(is_checked)
                widget.config(state=tk.DISABLED if is_admin_role else tk.NORMAL)

    def _save_permissions(self):
        if not self.selected_role_id: return
        selected_permissions = [key for key, widget in self.permission_widgets.items() if widget.var.get()]
        if self.db_handler.save_permissions_for_role(self.selected_role_id, selected_permissions):
            messagebox.showinfo("Succes", "Permisiunile au fost salvate cu succes.", parent=self)
        else:
            messagebox.showerror("Eroare", "A apărut o eroare la salvarea permisiunilor.", parent=self)

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
        nume_cont = self.name_entry.get().strip()
        if not nume_cont:
            messagebox.showwarning("Date Incomplete", "Numele contului este obligatoriu.", parent=self)
            return 0  # 0 înseamnă eșec, dialogul rămâne deschis

        # Verificăm dacă numele contului există deja, doar la adăugare
        if not self.account_data:  # account_data este None doar când adăugăm un cont nou
            try:
                existing_account = self.db_handler.fetch_one_dict("SELECT id_cont FROM conturi_bancare WHERE nume_cont = %s", (nume_cont,))
                if existing_account:
                    messagebox.showerror("Nume Duplicat", "Un cont cu acest nume există deja.", parent=self)
                    return 0
            except pymysql.Error as e:
                messagebox.showerror("Eroare DB", f"Nu s-a putut verifica unicitatea numelui:\n{e}", parent=self)
                return 0
        
        return 1  # 1 înseamnă succes, dialogul se va închide
        
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
                params = (
                    dialog.result['nume_cont'], 
                    dialog.result['iban'], 
                    dialog.result['nume_banca'], 
                    dialog.result['valuta'], 
                    dialog.result['observatii_cont'], 
                    dialog.result.get('culoare_cont', '#FFFFFF')
                )
                if self.db_handler.execute_commit(sql, params):
                    messagebox.showinfo("Succes", "Contul a fost adăugat.", parent=self)
                    self.load_accounts()
            except Exception as e:
                # Acest bloc prinde eroarea și afișează fereastra pe care ați văzut-o
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
            except pymysql.Error as e_db:
                 messagebox.showerror("Eroare Ștergere DB", f"Nu s-a putut șterge contul:\n{e_db.msg}", parent=self)
            except Exception as e:
                messagebox.showerror("Eroare Ștergere", f"Eroare: {e}", parent=self)

class TransactionTypeManagerDialog(simpledialog.Dialog):
    def __init__(self, parent, db_handler, app_instance):
        self.db_handler = db_handler
        # MODIFICARE: Salvăm o referință la instanța aplicației principale
        self.app_instance = app_instance 
        self.check_vars = {}
        
        # MODIFICARE: Citim setările din profilul utilizatorului, nu dintr-un fișier global
        if 'transaction_type_visibility' not in self.app_instance.user_settings:
            self.app_instance.user_settings['transaction_type_visibility'] = {}
        self.visibility_settings = self.app_instance.user_settings['transaction_type_visibility']

        super().__init__(parent, "Gestionare Vizibilitate Tipuri Tranzacții")

    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("cod", "descriere_tip", "vizibilitate")
        self.types_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        self.types_tree.heading("cod", text="Cod Tehnic")
        self.types_tree.heading("descriere_tip", text="Descriere Personalizată")
        self.types_tree.heading("vizibilitate", text="Vizibil în Liste/Rapoarte")
        self.types_tree.column("cod", width=100, anchor="w", stretch=False)
        self.types_tree.column("descriere_tip", width=300, anchor="w")
        self.types_tree.column("vizibilitate", width=200, anchor="center", stretch=False)
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

    def buttonbox(self):
        pass

    def load_transaction_types(self):
        for item in self.types_tree.get_children(): self.types_tree.delete(item)
        if not self.db_handler.is_connected(): return
        
        types_data = self.db_handler.fetch_all_dict("SELECT cod, descriere_tip FROM tipuri_tranzactii ORDER BY cod")
        if types_data:
            for type_info in types_data:
                cod = type_info['cod']
                # Folosim cheia cu litere mici pentru consistență
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
        
        # MODIFICARE: Salvăm întregul bloc de setări în DB prin funcția centralizată
        save_app_config(self.app_instance)
        
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
        # ... (codul pentru câmpurile username și password rămâne neschimbat) ...
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        tk.Label(master, text="Nume utilizator:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.username_entry = tk.Entry(master, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(master, text="Parola:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.password_entry = tk.Entry(master, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # --- BLOC NOU: Adăugare link pentru parolă uitată ---
        forgot_password_label = tk.Label(master, text="Am uitat parola...", fg="blue", cursor="hand2")
        forgot_password_label.grid(row=2, column=1, sticky=tk.E, padx=5, pady=(0, 5))
        forgot_password_label.bind("<Button-1>", self._handle_forgot_password)
        # --- SFÂRȘIT BLOC NOU ---
        
        self.parent = master.winfo_toplevel()
        self.parent.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() // 2) - (self.winfo_height() // 2)
        if x > 0 and y > 0: 
            self.geometry(f"+{x}+{y}")
        return self.username_entry

    # --- Gestionează procesul de resetare ---
    def _handle_forgot_password(self, event=None):
        # Importuri locale necesare
        import secrets
        from datetime import datetime, timedelta
        
        identifier = simpledialog.askstring("Resetare Parolă", "Introduceți numele de utilizator sau adresa de email:", parent=self)
        if not identifier:
            return

        # 1. Verificare configurare SMTP
        system_smtp_config = self.db_handler.get_system_settings()
        if not all(system_smtp_config.get(k) for k in ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_parola']):
            messagebox.showerror("Eroare Configurare", "Funcționalitatea de resetare a parolei nu este activă.\nContactați administratorul de sistem.", parent=self)
            return

        # 2. Găsire utilizator
        user_data = self.db_handler.get_user_by_username_or_email(identifier)
        if not user_data:
            messagebox.showwarning("Utilizator Inexistent", "Niciun cont nu a fost găsit pentru datele introduse.", parent=self)
            return

        try:
            # 3. Generare Token și Expirare
            raw_token = secrets.token_urlsafe(16)
            expiration_date = datetime.now() + timedelta(minutes=15)

            # --- MODIFICAREA CHEIE AICI ---
            # Folosim un hash standard (SHA256), fără "salt" aleatoriu.
            token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
            # --- SFÂRȘIT MODIFICARE ---

            # 4. Stocare Token Hash în DB
            sql_store_token = """
                INSERT INTO parola_reset_tokens (id_utilizator, token_hash, data_expirare)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE token_hash = VALUES(token_hash), data_expirare = VALUES(data_expirare)
            """
            self.db_handler.execute_commit(sql_store_token, (user_data['id'], token_hash, expiration_date))

            # 5. Trimitere Email cu Token-ul Brut
            from .email_composer import create_password_token_html
            from .email_handler import send_password_reset_email

            subject = f"Cerere Resetare Parolă - {APP_NAME}"
            html_body = create_password_token_html(user_data.get('nume_complet'), user_data['username'], raw_token)
            
            smtp_config_for_sending = {
                'server': system_smtp_config['smtp_host'],
                'port': system_smtp_config['smtp_port'],
                'user': system_smtp_config['smtp_user'],
                'password': system_smtp_config['smtp_parola'],
                'sender_email': system_smtp_config['smtp_adresa_expeditor'],
                'security': 'STARTTLS' if system_smtp_config.get('smtp_use_tls', True) else 'Niciuna'
            }

            email_sent, message = send_password_reset_email(smtp_config_for_sending, user_data['email'], subject, html_body)

            if email_sent:
                messagebox.showinfo("Verificați Emailul", f"Un cod de verificare a fost trimis la adresa {user_data['email']}.\nIntroduceți codul în fereastra următoare.", parent=self)
                
                # 6. Deschidem dialogul pentru finalizarea resetării
                dialog_class_to_use = ResetPasswordWithTokenDialog if 'ResetPasswordWithTokenDialog' in globals() else globals().get('ResetPasswordWithTokenDialog')
                reset_dialog = dialog_class_to_use(self, self.db_handler, user_data['id'])
                
                if reset_dialog.result:
                    messagebox.showinfo("Succes", "Parola a fost schimbată cu succes!", parent=self)
            else:
                messagebox.showerror("Eroare Trimitere Email", f"Nu s-a putut trimite emailul de resetare.\nContactați administratorul.\n\nDetalii: {message}", parent=self)

        except Exception as e:
            messagebox.showerror("Eroare Proces", f"A apărut o eroare în timpul procesului de resetare:\n{e}", parent=self)


    def validate(self):
        try:
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
            
            # --- BLOC MODIFICAT PENTRU APEL CORECT ---
            is_password_valid = auth_handler.verifica_parola(
                parola_introdusa=password, 
                salt_hex=user_db_data.get('salt'), 
                hash_stocat_hex=user_db_data.get('parola_hash')
            )
            # --- SFÂRȘIT BLOC MODIFICAT ---

            if not is_password_valid:
                messagebox.showerror("Autentificare eșuată", "Nume de utilizator sau parolă incorectă.", parent=self)
                return False
            
            user_id = user_db_data['id']
            permissions = self.db_handler.get_user_permissions(user_id)
            
            # --- LINIA DE DEPANARE DE ADĂUGAT ---
            print(f"DEBUG: Permisiuni încărcate pentru user ID {user_id}: {permissions}")
            # --- SFÂRȘIT LINIE DE DEPANARE ---
            
            allowed_accounts = self.db_handler.get_allowed_accounts_for_user(user_id)
            
            self.result = {
                'id': user_id, 'username': username, 'nume_complet': user_db_data.get('nume_complet'),
                'permissions': permissions, 'allowed_accounts': allowed_accounts,
                'has_all_permissions': 'all_permissions' in permissions,
                'tranzactie_acces': user_db_data.get('tranzactie_acces', 'toate'),
                'force_password_change': user_db_data.get('parola_schimbata_necesar')
            }
            
            self.db_handler.log_action(user_id, username, "Login reușit")
            return True
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Eroare Necunoscută la Autentificare", f"A apărut o problemă neașteptată:\n\n{type(e).__name__}: {e}", parent=self)
            return False

    def apply(self):
        pass # Nu este necesar, validarea face totul

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
        
        # --- Câmp nou pentru Email ---
        tk.Label(details_frame, text="Adresă Email*:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.email_entry = tk.Entry(details_frame, width=40)
        self.email_entry.grid(row=2, column=1, padx=5, pady=2)
        # --- Sfârșit câmp nou ---

        password_label_text = "Parola*:" if not self.user_id else "Parolă nouă:"
        tk.Label(details_frame, text=password_label_text).grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.password_entry = tk.Entry(details_frame, show="*", width=40)
        self.password_entry.grid(row=3, column=1, padx=5, pady=2)
        if self.user_id:
            tk.Label(details_frame, text="(lasă gol pentru a nu schimba)", font=("TkDefaultFont", 8, "italic")).grid(row=3, column=2, sticky=tk.W)
        
        # --- Secțiune pentru Acces Tranzacții ---
        tk.Label(details_frame, text="Acces Tranzacții:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.tx_access_var = tk.StringVar(value='toate')
        self.tx_access_combo = ttk.Combobox(details_frame, textvariable=self.tx_access_var, values=['toate', 'credit', 'debit'], state='readonly', width=38)
        self.tx_access_combo.grid(row=4, column=1, pady=2, padx=5)

        permissions_frame = ttk.Frame(main_frame)
        permissions_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        permissions_frame.grid_columnconfigure(0, weight=1)
        permissions_frame.grid_columnconfigure(1, weight=1)

        # Panou pentru ROLURI
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

        # Panou pentru CONTURI BANCARE
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
            self.email_entry.insert(0, self.user_data.get('email') or '') # NOU: Pre-populare email
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
        email = self.email_entry.get().strip() # NOU: Colectare email

        # NOU: Validare email
        if not email or "@" not in email or "." not in email.split('@')[1]:
            messagebox.showerror("Eroare", "Adresa de email este invalidă sau lipsește.", parent=self)
            self.result = None
            return # Previne închiderea dialogului

        tx_access = self.tx_access_var.get()
        
        selected_role_indices = self.roles_listbox.curselection()
        selected_role_ids = [self.all_roles[i]['id'] for i in selected_role_indices]

        selected_account_indices = self.accounts_listbox.curselection()
        selected_account_ids = [self.all_accounts[i]['id_cont'] for i in selected_account_indices]

        cursor = None
        try:
            cursor = self.db_handler.conn.cursor()
            
            if self.user_id: 
                # --- Logică de MODIFICARE ---
                if password:
                    salt, pass_hash = auth_handler.hash_parola(password)
                    # MODIFICAT: Se adaugă email la UPDATE
                    cursor.execute("UPDATE utilizatori SET nume_complet = %s, email = %s, parola_hash = %s, salt = %s, tranzactie_acces = %s WHERE id = %s",
                                   (fullname, email, pass_hash, salt, tx_access, self.user_id))
                else:
                    # MODIFICAT: Se adaugă email la UPDATE
                    cursor.execute("UPDATE utilizatori SET nume_complet = %s, email = %s, tranzactie_acces = %s WHERE id = %s", (fullname, email, tx_access, self.user_id))

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
                # MODIFICAT: Se adaugă email la INSERT
                cursor.execute("INSERT INTO utilizatori (username, nume_complet, email, parola_hash, salt, tranzactie_acces) VALUES (%s, %s, %s, %s, %s, %s)",
                               (username, fullname, email, pass_hash, salt, tx_access))
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

        except pymysql.Error as e:
            # Anularea tranzacției în caz de eroare
            self.db_handler.conn.rollback()
            # MODIFICARE: Folosim e.args[1] pentru un mesaj de eroare mai clar de la PyMySQL
            error_message = e.args[1] if len(e.args) > 1 else str(e)
            messagebox.showerror("Eroare Bază de Date", f"Nu s-a putut salva utilizatorul:\n{error_message}", parent=self)
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
        cols = ("username", "email", "nume_complet", "roluri", "stare") # NOU: Adăugat 'email'
        self.users_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        
        # NOU: Actualizat lățimi și headere
        col_widths = {"username": 150, "email": 200, "nume_complet": 200, "roluri": 250, "stare": 80}
        for col in cols:
            header_text = col.replace("_", " ").replace("nume complet", "Nume Complet").capitalize()
            self.users_tree.heading(col, text=header_text)
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
        
        # --- BUTON NOU PENTRU SETĂRI SMTP DE SISTEM ---
        self.system_smtp_button = ttk.Button(button_container, text="Setări Email Sistem", command=self._on_open_system_smtp_settings)
        self.system_smtp_button.pack(side=tk.LEFT, padx=(15, 5))
        # --- SFÂRȘIT BUTON NOU ---

        ttk.Button(button_container, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=5)
        
        self.load_users()
        return self.users_tree

    def buttonbox(self): pass

    def load_users(self):
        for item in self.users_tree.get_children(): self.users_tree.delete(item)
        # NOU: Interogarea va trebui actualizată pentru a prelua și emailul
        # Vom presupune că `get_all_users_with_roles` va fi actualizată sau deja preia toate câmpurile necesare.
        # Pentru moment, adaptăm popularea.
        users_data = self.db_handler.fetch_all_dict(
            """
            SELECT u.id, u.username, u.email, u.nume_complet, u.activ, 
                   GROUP_CONCAT(r.nume_rol SEPARATOR ', ') as roluri
            FROM utilizatori u
            LEFT JOIN utilizatori_roluri ur ON u.id = ur.id_utilizator
            LEFT JOIN roluri r ON ur.id_rol = r.id
            GROUP BY u.id, u.username, u.email, u.nume_complet, u.activ
            ORDER BY u.username ASC;
            """
        )
        if users_data:
            for user in users_data:
                stare = "Activ" if user['activ'] else "Inactiv"
                tags = () if user['activ'] else ('inactive',)
                values = (
                    user['username'], 
                    user.get('email', 'N/A'), # Afișăm emailul
                    user.get('nume_complet', ''), 
                    user.get('roluri', 'N/A'), 
                    stare
                )
                self.users_tree.insert("", tk.END, iid=user['id'], values=values, tags=tags)
        self._on_tree_select(None)

    # --- METODĂ NOUĂ PENTRU A DESCHIDE DIALOGUL SMTP ---
    def _on_open_system_smtp_settings(self):
        """Deschide dialogul de configurare a setărilor SMTP de sistem."""
        try:
            # Preluăm setările curente din baza de date
            current_config = self.db_handler.get_system_settings()
            
            # Creăm și afișăm dialogul, pasându-i setările curente
            # Dialogul se va ocupa singur de salvarea datelor la apăsarea butonului "Salvează"
            dialog = SystemSmtpConfigDialog(self, self.db_handler, initial_config=current_config)
            
        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut deschide dialogul de setări:\n{e}", parent=self)

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

class ForcePasswordChangeDialog(simpledialog.Dialog):
    """Dialog modal care forțează utilizatorul să schimbe parola."""
    def __init__(self, parent, db_handler, user_id, username):
        self.db_handler = db_handler
        self.user_id = user_id
        self.username = username
        self.result = None  # Inițializăm rezultatul
        super().__init__(parent, "Schimbare Parolă Obligatorie")

    def body(self, master):
        ttk.Label(master, text=f"Utilizator: {self.username}", font=("TkDefaultFont", 10, "bold")).grid(row=0, columnspan=2, pady=(5,10))
        ttk.Label(master, text="Parolă nouă:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.new_pass_entry = ttk.Entry(master, show="*", width=30)
        self.new_pass_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(master, text="Confirmare parolă:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.confirm_pass_entry = ttk.Entry(master, show="*", width=30)
        self.confirm_pass_entry.grid(row=2, column=1, padx=5, pady=2)
        
        return self.new_pass_entry # Focus pe primul câmp de parolă

    def validate(self):
        """Validează datele introduse de utilizator."""
        new_pass = self.new_pass_entry.get()
        confirm_pass = self.confirm_pass_entry.get()

        if not new_pass or not confirm_pass:
            messagebox.showwarning("Date Incomplete", "Ambele câmpuri pentru parolă sunt obligatorii.", parent=self)
            return False
        
        if new_pass != confirm_pass:
            messagebox.showerror("Parole Diferite", "Parolele introduse nu se potrivesc.", parent=self)
            self.confirm_pass_entry.focus_set()
            return False
            
        if len(new_pass) < 8:
            messagebox.showwarning("Parolă Prea Scurtă", "Parola trebuie să conțină cel puțin 8 caractere.", parent=self)
            return False
            
        return True

    def apply(self):
        """Aplică schimbarea parolei în baza de date."""
        new_password = self.new_pass_entry.get()
        salt, pass_hash = auth_handler.hash_parola(new_password)
        
        sql = """
            UPDATE utilizatori 
            SET parola_hash = %s, salt = %s, parola_schimbata_necesar = FALSE 
            WHERE id = %s
        """
        if self.db_handler.execute_commit(sql, (pass_hash, salt, self.user_id)):
            messagebox.showinfo("Succes", "Parola a fost schimbată. Vă rugăm să vă autentificați din nou cu noua parolă.", parent=self.master)
            self.result = True
        else:
            messagebox.showerror("Eroare DB", "Nu s-a putut actualiza parola în baza de date.", parent=self)
            self.result = False

class SystemSmtpConfigDialog(simpledialog.Dialog):
    """Dialog pentru configurarea setărilor SMTP la nivel de sistem."""
    def __init__(self, parent, db_handler, initial_config=None):
        self.db_handler = db_handler
        self.initial_config = initial_config or {}
        super().__init__(parent, "Configurare Email Sistem (Resetare Parole)")

    def body(self, master):
        tk.Label(master, text="Host SMTP:").grid(row=0, sticky=tk.W, pady=2)
        self.host_entry = tk.Entry(master, width=40)
        self.host_entry.grid(row=0, column=1, pady=2)
        self.host_entry.insert(0, self.initial_config.get('smtp_host', ''))

        tk.Label(master, text="Port:").grid(row=1, sticky=tk.W, pady=2)
        self.port_entry = tk.Entry(master, width=40)
        self.port_entry.grid(row=1, column=1, pady=2)
        self.port_entry.insert(0, self.initial_config.get('smtp_port', '587'))

        tk.Label(master, text="Utilizator (Email):").grid(row=2, sticky=tk.W, pady=2)
        self.user_entry = tk.Entry(master, width=40)
        self.user_entry.grid(row=2, column=1, pady=2)
        self.user_entry.insert(0, self.initial_config.get('smtp_user', ''))

        tk.Label(master, text="Parolă:").grid(row=3, sticky=tk.W, pady=2)
        self.password_entry = tk.Entry(master, show="*", width=40)
        self.password_entry.grid(row=3, column=1, pady=2)
        self.password_entry.insert(0, self.initial_config.get('smtp_parola', ''))

        tk.Label(master, text="Adresă Expeditor:").grid(row=4, sticky=tk.W, pady=2)
        self.sender_entry = tk.Entry(master, width=40)
        self.sender_entry.grid(row=4, column=1, pady=2)
        self.sender_entry.insert(0, self.initial_config.get('smtp_adresa_expeditor', ''))
        
        self.use_tls_var = tk.BooleanVar(value=self.initial_config.get('smtp_use_tls', True))
        tk.Checkbutton(master, text="Utilizează TLS", variable=self.use_tls_var).grid(row=5, columnspan=2, pady=5)

        return self.host_entry

    def validate(self):
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()
        user = self.user_entry.get().strip()
        
        if not all([host, port, user]):
            messagebox.showwarning("Date Incomplete", "Host-ul, portul și utilizatorul sunt obligatorii.", parent=self)
            return 0
        
        try:
            int(port)
        except ValueError:
            messagebox.showwarning("Format Invalid", "Portul trebuie să fie un număr.", parent=self)
            return 0
            
        return 1

    def apply(self):
        self.result = {
            "smtp_host": self.host_entry.get().strip(),
            "smtp_port": int(self.port_entry.get().strip()),
            "smtp_user": self.user_entry.get().strip(),
            "smtp_parola": self.password_entry.get(),
            "smtp_adresa_expeditor": self.sender_entry.get().strip() or self.user_entry.get().strip(),
            "smtp_use_tls": self.use_tls_var.get()
        }
        
        # Salvare directă în baza de date
        try:
            for cheie, valoare in self.result.items():
                # Folosim o interogare de tip "INSERT ... ON DUPLICATE KEY UPDATE" pentru simplitate
                sql = """
                    INSERT INTO setari_sistem (cheie_setare, valoare_setare) 
                    VALUES (%s, %s) 
                    ON DUPLICATE KEY UPDATE valoare_setare = %s
                """
                self.db_handler.execute_commit(sql, (cheie, str(valoare), str(valoare)))
            
            messagebox.showinfo("Succes", "Setările SMTP ale sistemului au fost salvate.", parent=self.parent)

        except Exception as e:
            messagebox.showerror("Eroare Salvare", f"Nu s-au putut salva setările în baza de date:\n{e}", parent=self)
            self.result = None # Anulăm rezultatul în caz de eroare

class ChangePasswordDialog(simpledialog.Dialog):
    """Dialog pentru schimbarea voluntară a parolei de către utilizatorul autentificat."""
    def __init__(self, parent, db_handler, current_user):
        self.db_handler = db_handler
        self.current_user = current_user
        super().__init__(parent, "Schimbare Parolă Personală")

    def body(self, master):
        tk.Label(master, text="Parola curentă:").grid(row=0, sticky=tk.W, pady=5, padx=5)
        self.current_pass_entry = tk.Entry(master, show="*", width=35)
        self.current_pass_entry.grid(row=0, column=1, pady=5, padx=5)

        tk.Label(master, text="Parola nouă:").grid(row=1, sticky=tk.W, pady=5, padx=5)
        self.new_pass_entry = tk.Entry(master, show="*", width=35)
        self.new_pass_entry.grid(row=1, column=1, pady=5, padx=5)

        tk.Label(master, text="Confirmă parola nouă:").grid(row=2, sticky=tk.W, pady=5, padx=5)
        self.confirm_pass_entry = tk.Entry(master, show="*", width=35)
        self.confirm_pass_entry.grid(row=2, column=1, pady=5, padx=5)
        
        return self.current_pass_entry

    def validate(self):
        current_pass = self.current_pass_entry.get()
        new_pass = self.new_pass_entry.get()
        confirm_pass = self.confirm_pass_entry.get()

        if not all([current_pass, new_pass, confirm_pass]):
            messagebox.showwarning("Date Incomplete", "Toate câmpurile sunt obligatorii.", parent=self)
            return 0

        # Verificăm parola curentă
        user_db_data = self.db_handler.get_user_by_username(self.current_user['username'])
        is_valid = auth_handler.verifica_parola(current_pass, user_db_data['salt'], user_db_data['parola_hash'])
        
        if not is_valid:
            messagebox.showerror("Eroare", "Parola curentă este incorectă.", parent=self)
            return 0
            
        if len(new_pass) < 8:
            messagebox.showwarning("Parolă Prea Scurtă", "Parola nouă trebuie să aibă cel puțin 8 caractere.", parent=self)
            return 0

        if new_pass != confirm_pass:
            messagebox.showerror("Eroare", "Parolele noi nu se potrivesc.", parent=self)
            return 0
        
        return 1

    def apply(self):
        new_password = self.new_pass_entry.get()
        # Folosim metoda existentă, dar setăm force_change la False
        success = self.db_handler.update_user_password(self.current_user['id'], new_password, force_change=False)
        
        if success:
            log_details = f"Utilizatorul '{self.current_user['username']}' și-a schimbat parola."
            self.db_handler.log_action(self.current_user['id'], self.current_user['username'], "Schimbare parolă voluntară", log_details)
            messagebox.showinfo("Succes", "Parola a fost schimbată cu succes.", parent=self)
        else:
            messagebox.showerror("Eroare DB", "A apărut o problemă la actualizarea parolei în baza de date.", parent=self)

class ResetPasswordWithTokenDialog(simpledialog.Dialog):
    """Dialog pentru finalizarea procesului de resetare folosind token-ul din email."""
    def __init__(self, parent, db_handler, user_id):
        self.db_handler = db_handler
        self.user_id = user_id
        super().__init__(parent, "Verificare Cod și Setare Parolă Nouă")

    def body(self, master):
        tk.Label(master, text="Cod Verificare (din email):").grid(row=0, sticky=tk.W, pady=5, padx=5)
        self.token_entry = tk.Entry(master, width=45)
        self.token_entry.grid(row=0, column=1, pady=5, padx=5)

        tk.Label(master, text="Parola nouă:").grid(row=1, sticky=tk.W, pady=5, padx=5)
        self.new_pass_entry = tk.Entry(master, show="*", width=45)
        self.new_pass_entry.grid(row=1, column=1, pady=5, padx=5)

        tk.Label(master, text="Confirmă parola nouă:").grid(row=2, sticky=tk.W, pady=5, padx=5)
        self.confirm_pass_entry = tk.Entry(master, show="*", width=45)
        self.confirm_pass_entry.grid(row=2, column=1, pady=5, padx=5)
        
        return self.token_entry

    def validate(self):
        # Validări preliminare pe câmpuri
        if not all([self.token_entry.get(), self.new_pass_entry.get(), self.confirm_pass_entry.get()]):
            messagebox.showwarning("Date Incomplete", "Toate câmpurile sunt obligatorii.", parent=self)
            return 0
        if self.new_pass_entry.get() != self.confirm_pass_entry.get():
            messagebox.showerror("Eroare", "Parolele noi nu se potrivesc.", parent=self)
            return 0
        if len(self.new_pass_entry.get()) < 8:
            messagebox.showwarning("Parolă Prea Scurtă", "Parola nouă trebuie să aibă cel puțin 8 caractere.", parent=self)
            return 0
        
        # Validare Token în DB
        raw_token = self.token_entry.get()
        token_data = self.db_handler.fetch_one_dict(
            "SELECT token_hash, data_expirare FROM parola_reset_tokens WHERE id_utilizator = %s", (self.user_id,)
        )

        if not token_data:
            messagebox.showerror("Eroare", "Cod invalid sau expirat. Vă rugăm reîncercați procesul de resetare.", parent=self)
            return 0

        # Verificăm expirarea
        if datetime.now() > token_data['data_expirare']:
            messagebox.showerror("Eroare", "Codul de resetare a expirat. Vă rugăm reîncercați procesul.", parent=self)
            return 0

        # Generăm hash-ul pentru token-ul introdus folosind aceeași metodă ca la creare
        hash_to_check = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # Comparăm hash-ul generat cu cel stocat în baza de date
        if hash_to_check != token_data['token_hash']:
            messagebox.showerror("Eroare", "Cod de verificare invalid. Asigurați-vă că ați copiat corect codul.", parent=self)
            return 0

        return 1

    def apply(self):
        new_password = self.new_pass_entry.get()
        
        # Token valid. Actualizăm parola și ștergem token-ul.
        update_success = self.db_handler.update_user_password(self.user_id, new_password, force_change=False)
        
        if update_success:
            # Ștergem token-ul folosit
            self.db_handler.execute_commit("DELETE FROM parola_reset_tokens WHERE id_utilizator = %s", (self.user_id,))
            self.result = True
        else:
            messagebox.showerror("Eroare DB", "Nu s-a putut actualiza parola în baza de date.", parent=self)
            self.result = False