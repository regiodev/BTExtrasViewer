# ui_dialogs.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
from email_handler import test_smtp_connection
from datetime import date
from tkcalendar import DateEntry
import config_management
import mysql.connector # Importat pentru mysql.connector.Error în AccountEditDialog.validate
import logging
import re

class AccountEditDialog(simpledialog.Dialog):
    """
    Dialog modal pentru adăugarea sau modificarea unui cont bancar.
    Gestionează acum și selectarea unei culori pentru cont.
    """
    def __init__(self, parent, db_handler, account_data=None, title=None):
        self.db_handler = db_handler
        self.account_data = account_data
        self.result = None
        
        # Inițializează culoarea selectată din datele contului sau cu o valoare default (alb)
        self.selected_color = account_data.get('culoare_cont', '#FFFFFF') if account_data and account_data.get('culoare_cont') else '#FFFFFF'
        
        if title is None:
            title = "Adaugă Cont Nou" if account_data is None else "Editează Cont Bancar"
        
        super().__init__(parent, title=title)

    def body(self, master):
        # Rândul 0: Nume Cont
        tk.Label(master, text="Nume Cont*:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.name_entry = tk.Entry(master, width=40)
        self.name_entry.grid(row=0, column=1, pady=2, padx=5)

        # Rândul 1: IBAN
        tk.Label(master, text="IBAN:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.iban_entry = tk.Entry(master, width=40)
        self.iban_entry.grid(row=1, column=1, pady=2, padx=5)

        # Rândul 2: Nume Bancă
        tk.Label(master, text="Nume Bancă:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.bank_entry = tk.Entry(master, width=40)
        self.bank_entry.grid(row=2, column=1, pady=2, padx=5)

        # Rândul 3: Valută
        tk.Label(master, text="Valută:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.currency_var = tk.StringVar(value="RON")
        self.currency_combo = ttk.Combobox(master, textvariable=self.currency_var, 
                                           values=["RON", "EUR", "USD", "GBP", "CHF"], 
                                           state="readonly", width=38)
        self.currency_combo.grid(row=3, column=1, pady=2, padx=5)

        # Rândul 4: Observații
        tk.Label(master, text="Observații:").grid(row=4, column=0, sticky=tk.NW, pady=2, padx=5)
        obs_text_frame = ttk.Frame(master)
        obs_text_frame.grid(row=4, column=1, pady=2, padx=5, sticky="ew")
        
        self.obs_text = tk.Text(obs_text_frame, width=38, height=4, wrap=tk.WORD)
        obs_scrollbar = ttk.Scrollbar(obs_text_frame, orient=tk.VERTICAL, command=self.obs_text.yview)
        self.obs_text.configure(yscrollcommand=obs_scrollbar.set)
        
        self.obs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        obs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Rândul 5: Culoare Cont (Secțiunea nouă)
        tk.Label(master, text="Culoare Cont:").grid(row=5, column=0, sticky=tk.W, pady=(5,2), padx=5)
        color_frame = ttk.Frame(master)
        color_frame.grid(row=5, column=1, sticky=tk.W, pady=(5,2), padx=5)

        self.color_preview = tk.Frame(color_frame, width=24, height=24, relief=tk.SUNKEN, borderwidth=1)
        self.color_preview.pack(side=tk.LEFT, padx=(0, 5))
        
        self.color_button = ttk.Button(color_frame, text="Alege Culoare", command=self._choose_color)
        self.color_button.pack(side=tk.LEFT)
        
        # Pre-populare date pentru editare
        if self.account_data:
            self.name_entry.insert(0, self.account_data.get('nume_cont', ''))
            self.iban_entry.insert(0, self.account_data.get('iban', '') or '')
            self.bank_entry.insert(0, self.account_data.get('nume_banca', '') or '')
            self.currency_var.set(self.account_data.get('valuta', 'RON'))
            self.obs_text.insert(tk.END, self.account_data.get('observatii_cont', '') or '')
        
        # Setează culoarea inițială pentru preview, cu validare
        try:
            self.color_preview.config(background=self.selected_color)
        except tk.TclError:
            self.selected_color = '#FFFFFF' # Fallback la alb dacă culoarea din DB e invalidă
            self.color_preview.config(background=self.selected_color)
        
        return self.name_entry # Focus inițial

    def _choose_color(self):
        # Deschide dialogul standard de selectare a culorii
        color_code = colorchooser.askcolor(title="Alegeți o culoare pentru cont", 
                                           initialcolor=self.selected_color, 
                                           parent=self)
        if color_code and color_code[1]: # color_code[1] este string-ul hex #rrggbb
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
        
        # Verificare unicitate nume cont
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

        # Verificare unicitate IBAN (dacă este specificat)
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
        # Se adaugă 'culoare_cont' la dicționarul de rezultate
        self.result = {
            "nume_cont": self.name_entry.get().strip(),
            "iban": self.iban_entry.get().strip().upper() or None,
            "nume_banca": self.bank_entry.get().strip() or None,
            "valuta": self.currency_var.get(),
            "observatii_cont": self.obs_text.get("1.0", tk.END).strip() or None,
            "culoare_cont": self.selected_color
        }

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

    def buttonbox(self):
        pass # Suprascris pentru a nu afișa OK/Cancel default

    def load_accounts(self):
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        if not (self.db_handler and self.db_handler.is_connected()):
            messagebox.showerror("Eroare", "Lipsă conexiune la baza de date.", parent=self) # Corectat: self
            return
        accounts_data = self.db_handler.get_all_accounts()
        if accounts_data:
            for acc in accounts_data:
                values = (
                    acc.get('nume_cont', ''), acc.get('iban', ''), acc.get('nume_banca', ''), 
                    acc.get('valuta', ''), acc.get('observatii_cont', '')
                )
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
        # Corectat: Folosim 'self' ca părinte, deoarece AccountManagerDialog este fereastra
        dialog = AccountEditDialog(self, self.db_handler, title="Adaugă Cont Nou") 
        if dialog.result:
            try:
                sql = """INSERT INTO conturi_bancare (nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont) 
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                params = (dialog.result['nume_cont'], dialog.result['iban'], 
                          dialog.result['nume_banca'], dialog.result['valuta'], 
                          dialog.result['observatii_cont'], dialog.result.get('culoare_cont', '#FFFFFF'))
                if self.db_handler.execute_commit(sql, params):
                    messagebox.showinfo("Succes", "Contul a fost adăugat.", parent=self) # Corectat: self
                    self.load_accounts()
            except Exception as e:
                messagebox.showerror("Eroare Adăugare", f"Eroare: {e}", parent=self) # Corectat: self

    def _on_edit_account(self):
        if not self.selected_account_id:
            messagebox.showwarning("Atenție", "Selectați un cont pentru a-l modifica.", parent=self) # Corectat: self
            return
        account_data = self.db_handler.fetch_one_dict(
            "SELECT * FROM conturi_bancare WHERE id_cont = %s", (self.selected_account_id,)
        )
        if not account_data:
            messagebox.showerror("Eroare", "Contul selectat nu a fost găsit în baza de date.", parent=self) # Corectat: self
            self.load_accounts()
            return
        dialog = AccountEditDialog(self, self.db_handler, account_data=account_data, title="Modifică Cont Bancar") # Corectat: self
        if dialog.result:
            try:
                sql = """UPDATE conturi_bancare SET 
                         nume_cont=%s, iban=%s, nume_banca=%s, valuta=%s, observatii_cont=%s, culoare_cont=%s
                         WHERE id_cont=%s"""
                params = (dialog.result['nume_cont'], dialog.result['iban'],
                          dialog.result['nume_banca'], dialog.result['valuta'],
                          dialog.result['observatii_cont'], dialog.result.get('culoare_cont', '#FFFFFF'), 
                          self.selected_account_id)
                if self.db_handler.execute_commit(sql, params):
                    messagebox.showinfo("Succes", "Contul a fost modificat.", parent=self) # Corectat: self
                    self.load_accounts()
            except Exception as e:
                messagebox.showerror("Eroare Modificare", f"Eroare: {e}", parent=self) # Corectat: self

    def _on_delete_account(self):
        if not self.selected_account_id:
            messagebox.showwarning("Atenție", "Selectați un cont pentru a-l șterge.", parent=self) # Corectat: self
            return
        try:
            item_values = self.accounts_tree.item(str(self.selected_account_id), 'values')
            account_name_display = item_values[0] if item_values and item_values[0] else f"ID: {self.selected_account_id}"
        except tk.TclError: account_name_display = f"ID: {self.selected_account_id}"
        num_tranzactii = self.db_handler.fetch_scalar(
            "SELECT COUNT(*) FROM tranzactii WHERE id_cont_fk = %s", (self.selected_account_id,)
        )
        if num_tranzactii is not None and num_tranzactii > 0:
            messagebox.showerror("Ștergere Eșuată", f"Contul '{account_name_display}' nu poate fi șters (are {num_tranzactii} tranzacții asociate).", parent=self) # Corectat: self
            return
        confirm_delete = messagebox.askyesno("Confirmare Ștergere", f"Sunteți sigur că doriți să ștergeți contul '{account_name_display}'?", parent=self) # Corectat: self
        if confirm_delete:
            try:
                if self.db_handler.execute_commit("DELETE FROM conturi_bancare WHERE id_cont = %s", (self.selected_account_id,)):
                    messagebox.showinfo("Succes", "Contul a fost șters.", parent=self) # Corectat: self
                    self.load_accounts()
            except mysql.connector.Error as e_db:
                 messagebox.showerror("Eroare Ștergere DB", f"Nu s-a putut șterge contul:\n{e_db.msg}", parent=self) # Corectat: self
            except Exception as e:
                messagebox.showerror("Eroare Ștergere", f"Eroare: {e}", parent=self) # Corectat: self


class TransactionTypeManagerDialog(simpledialog.Dialog):
    """Dialog pentru gestionarea tipurilor de tranzacții (categorii)."""
    def __init__(self, parent, db_handler):
        # CORECȚIE: Asigurăm că db_handler este setat ÎNAINTE de a apela super().__init__
        # care, la rândul său, apelează self.body() unde db_handler este necesar.
        self.db_handler = db_handler
        self.parent = parent
        self.check_vars = {}
        # Încărcăm setările de vizibilitate din fișierul de configurare o singură dată la inițializare
        self.visibility_settings = config_management.load_transaction_type_visibility()
        
        # Apelul la super() trebuie să vină după inițializarea atributelor necesare în self.body()
        super().__init__(parent, "Gestionare Vizibilitate Tipuri Tranzacții")
        
        # ELIMINARE: Apelul la metoda inexistentă a fost eliminat.
        # self._populate_list()

    def body(self, master):
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # MODIFICARE: Redenumim coloana pentru claritate
        cols = ("cod", "descriere_tip", "vizibilitate_locala")
        self.types_tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="browse")
        
        self.types_tree.heading("cod", text="Cod Tehnic")
        self.types_tree.heading("descriere_tip", text="Descriere Personalizată")
        # MODIFICARE: Schimbăm textul antetului
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
        
        # MODIFICARE: Redenumim butonul pentru claritate
        self.toggle_button = ttk.Button(button_container, text="Comută Vizibilitate", command=self._on_toggle_visibility, state=tk.DISABLED)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_container, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=5)
        
        # Apelăm metoda de populare a tabelului
        self.load_transaction_types()
        return self.types_tree

    def buttonbox(self): pass

    def load_transaction_types(self):
        """Populează tabelul cu date din DB și stări din config.ini."""
        for item in self.types_tree.get_children(): self.types_tree.delete(item)
        if not self.db_handler.is_connected(): return
        
        # Preluăm toate tipurile definite în DB pentru a avea lista completă
        types_data = self.db_handler.fetch_all_dict("SELECT cod, descriere_tip FROM tipuri_tranzactii ORDER BY cod")
        
        if types_data:
            for type_info in types_data:
                cod = type_info['cod']
                
                # MODIFICARE: Starea se determină din setările locale, nu din DB
                # Dacă o setare nu există în config.ini (ex: un tip nou adăugat), se consideră vizibilă implicit (True)
                is_visible = self.visibility_settings.get(cod.lower(), True) # Folosim .lower() pentru consistență
                
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
        new_description = simpledialog.askstring("Modifică Descriere", f"Introduceți noua descriere pentru codul '{self.selected_code}':",
                                                  initialvalue=current_description, parent=self)
        if new_description and new_description.strip():
            # Actualizarea descrierii în DB rămâne validă
            if self.db_handler.execute_commit("UPDATE tipuri_tranzactii SET descriere_tip = %s WHERE cod = %s", (new_description.strip(), self.selected_code)):
                self.load_transaction_types()

    def _on_toggle_visibility(self):
        """MODIFICAT: Comută vizibilitatea în config.ini, nu în DB."""
        if not self.selected_code: return
        
        cod_key = self.selected_code.lower()
        
        # 1. Obținem starea curentă din setările locale (default True dacă lipsește)
        current_visibility = self.visibility_settings.get(cod_key, True)
        
        # 2. Inversăm starea
        self.visibility_settings[cod_key] = not current_visibility
        
        # 3. Salvăm întregul dicționar de setări înapoi în config.ini
        config_management.save_transaction_type_visibility(self.visibility_settings)
        
        # 4. Reîmprospătăm tabelul din dialog pentru a reflecta schimbarea
        self.load_transaction_types()

    # Am eliminat metoda save_changes() care nu era folosită, deoarece salvarea
    # se face acum instant la fiecare comutare. La închiderea dialogului,
    # fereastra principală va reîncărca automat setările.

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
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            port = 0
            
        user = self.user_entry.get().strip()
        sender = self.sender_email_entry.get().strip()

        return {
            'server': self.server_entry.get().strip(),
            'port': port,
            'security': self.security_var.get(),
            'sender_email': sender,
            'user': user if user else sender, # Dacă user e gol, folosim emailul expeditorului
            'password': self.password_entry.get()
        }

    def test_connection(self):
        config = self.get_current_config()
        success, message = test_smtp_connection(config)
        if success:
            messagebox.showinfo("Test Conexiune", message, parent=self)
        else:
            messagebox.showerror("Test Conexiune", message, parent=self)

    def validate(self):
        config = self.get_current_config()
        if not all([config['server'], config['port'], config['sender_email'], config['user']]):
            messagebox.showwarning("Date Incomplete", "Câmpurile Server, Port, Email Expeditor și Utilizator sunt obligatorii.", parent=self)
            return 0
        return 1

    def apply(self):
        self.result = self.get_current_config()

class BalanceReportConfigDialog(simpledialog.Dialog):
    """Dialog pentru configurarea parametrilor raportului de evoluție a soldului."""
    def __init__(self, parent, app_instance, accounts_list):
        self.accounts_list = accounts_list
        self.main_app_instance = app_instance # Stocăm instanța aplicației
        # 'parent' este acum self.master din btextrasviewer_main.py
        super().__init__(parent, "Configurare Raport Evoluție Sold")

    def body(self, master):
        tk.Label(master, text="Cont Bancar:").grid(row=0, sticky="w", pady=2, padx=5)
        self.account_var = tk.StringVar()
        account_names = [acc['nume_cont'] for acc in self.accounts_list]
        self.account_combo = ttk.Combobox(master, textvariable=self.account_var, values=account_names, state="readonly", width=38)
        self.account_combo.grid(row=0, column=1, pady=2, padx=5)
        
        if account_names:
            # Preselectăm contul activ din fereastra principală
            active_account_name = self.main_app_instance.account_combo_var.get()
            if active_account_name in account_names:
                self.account_combo.set(active_account_name)
            else:
                self.account_combo.set(account_names[0])

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

        self.result = {
            "account_id": selected_account['id_cont'],
            "account_name": selected_account['nume_cont'],
            "start_date": self.start_date_entry.get_date(),
            "end_date": self.end_date_entry.get_date(),
            "granularity": self.granularity_var.get(),
            "currency": selected_account.get('valuta', 'RON')
        }