# db_handler.py
import mysql.connector
from mysql.connector import errorcode # Import necesar pentru gestionarea erorilor specifice MySQL
import logging
import tkinter as tk
from tkinter import simpledialog, messagebox

# CONSTANTE SQL PENTRU NOUA STRUCTURĂ
DB_STRUCTURE_CONTURI_BANCARE_MARIADB = """
CREATE TABLE IF NOT EXISTS conturi_bancare (
    id_cont INT AUTO_INCREMENT PRIMARY KEY,
    nume_cont VARCHAR(100) NOT NULL,
    iban VARCHAR(34) UNIQUE,
    nume_banca VARCHAR(100),
    valuta VARCHAR(10) DEFAULT 'RON',
    data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observatii_cont TEXT,
    culoare_cont VARCHAR(7) DEFAULT '#FFFFFF',  -- NOU: Culoarea contului (ex: #RRGGBB), default alb
    CONSTRAINT uq_nume_cont UNIQUE (nume_cont)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_TABLE_CONTURI_BANCARE = """
CREATE TABLE IF NOT EXISTS conturi_bancare (
    id_cont INT AUTO_INCREMENT PRIMARY KEY,
    nume_cont VARCHAR(255) NOT NULL UNIQUE,
    iban VARCHAR(34) NOT NULL UNIQUE,
    culoare_cont VARCHAR(7),
    este_default BOOLEAN DEFAULT FALSE
) ENGINE=InnoDB;
"""

# --- ADAUGARE: Definim structura pentru noua tabelă de istoric ---
CREATE_TABLE_ISTORIC_IMPORTURI = """
CREATE TABLE IF NOT EXISTS istoric_importuri (
    id_import INT AUTO_INCREMENT PRIMARY KEY,
    nume_fisier VARCHAR(255) NOT NULL,
    data_import TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tranzactii_procesate INT NOT NULL,
    tranzactii_ignorate INT NOT NULL,
    id_cont_fk INT NOT NULL,
    FOREIGN KEY (id_cont_fk) REFERENCES conturi_bancare(id_cont) ON DELETE CASCADE
) ENGINE=InnoDB;
"""
# --------------------------------------------------------------------

DB_STRUCTURE_TRANZACTII_V2_MARIADB = """
CREATE TABLE IF NOT EXISTS tranzactii (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_cont_fk INT NOT NULL,
    data DATE,
    descriere TEXT,
    suma DECIMAL(15, 2),
    tip VARCHAR(10),
    cod_tranzactie_fk VARCHAR(4),
    cif VARCHAR(50),
    factura VARCHAR(100),
    beneficiar VARCHAR(255),
    tid VARCHAR(100),
    rrn VARCHAR(100),
    pan VARCHAR(100),
    cont VARCHAR(100),
    sold_initial DECIMAL(15, 2),
    sold_final DECIMAL(15, 2),
    sold_dupa_tranzactie DECIMAL(15, 2), -- NOU: Stochează soldul curent
    observatii VARCHAR(300),
    CONSTRAINT fk_tranzactie_cont FOREIGN KEY (id_cont_fk) REFERENCES conturi_bancare(id_cont) ON DELETE RESTRICT,
    CONSTRAINT fk_tranzactie_tip FOREIGN KEY (cod_tranzactie_fk) REFERENCES tipuri_tranzactii(cod) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

DB_ALTER_TRANZACTII_ADD_COLUMN_ID_CONT_FK_MARIADB = """
ALTER TABLE tranzactii ADD COLUMN id_cont_fk INT NULL DEFAULT NULL AFTER id;
"""
DB_STRUCTURE_TIPURI_TRANZACTII_MARIADB = """
CREATE TABLE IF NOT EXISTS tipuri_tranzactii (
    cod VARCHAR(4) PRIMARY KEY,
    descriere_tip VARCHAR(255) NOT NULL,
    este_operational BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

class MariaDBConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial_host=None, initial_port=None,
                 initial_dbname=None, initial_user=None, initial_password=None):
        self.initial_host = initial_host
        self.initial_port = initial_port
        self.initial_dbname = initial_dbname
        self.initial_user = initial_user
        self.initial_password = initial_password
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="Host (IP NAS):").grid(row=0, sticky=tk.W, pady=2)
        self.host_entry = tk.Entry(master, width=30)
        self.host_entry.grid(row=0, column=1, pady=2)
        if self.initial_host: self.host_entry.insert(0, self.initial_host)

        tk.Label(master, text="Port:").grid(row=1, sticky=tk.W, pady=2)
        self.port_entry = tk.Entry(master, width=30)
        self.port_entry.grid(row=1, column=1, pady=2)
        self.port_entry.insert(0, str(self.initial_port or "3306"))

        tk.Label(master, text="Nume Bază Date:").grid(row=2, sticky=tk.W, pady=2)
        self.dbname_entry = tk.Entry(master, width=30)
        self.dbname_entry.grid(row=2, column=1, pady=2)
        if self.initial_dbname: self.dbname_entry.insert(0, self.initial_dbname)

        tk.Label(master, text="Utilizator DB:").grid(row=3, sticky=tk.W, pady=2)
        self.user_entry = tk.Entry(master, width=30)
        self.user_entry.grid(row=3, column=1, pady=2)
        if self.initial_user: self.user_entry.insert(0, self.initial_user)

        tk.Label(master, text="Parolă DB:").grid(row=4, sticky=tk.W, pady=2)
        self.password_entry = tk.Entry(master, show="*", width=30)
        self.password_entry.grid(row=4, column=1, pady=2)
        if self.initial_password: self.password_entry.insert(0, self.initial_password)
        
        return self.host_entry # Focus inițial

    def apply(self):
        self.result = {
            "host": self.host_entry.get(),
            "port": self.port_entry.get(),
            "dbname": self.dbname_entry.get(),
            "user": self.user_entry.get(),
            "password": self.password_entry.get()
        }

class DatabaseHandler:
    def __init__(self, db_host, db_port, db_name, db_user, db_password, app_master_ref=None):
        self.db_host = db_host
        self.db_port = int(db_port) if db_port else 3306 # Asigură că portul e int
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.conn = None
        self.app_master_ref = app_master_ref # Pentru a afișa messagebox-uri din handler

    def connect_to_db_internal(self):
        # Închide orice conexiune veche înainte de a încerca una nouă, pentru o stare curată.
        if self.conn and self.conn.is_connected():
            try:
                self.conn.close()
            except Exception as e_close:
                logging.debug(f"DEBUG_DB_HANDLER: Eroare la închiderea conexiunii DB existente: {e_close}")
        self.conn = None # Resetăm conn

        try:
            # Verifică dacă toate credențialele necesare sunt prezente
            if not all([self.db_host, self.db_port, self.db_name, self.db_user]):
                if self.app_master_ref and self.app_master_ref.winfo_exists():
                     messagebox.showerror("Date Conexiune Lipsă", "Host, port, nume DB și utilizator sunt obligatorii.", parent=self.app_master_ref)
                return False

            logging.debug("DEBUG_DB_HANDLER: Pregătire pentru apelul mysql.connector.connect() cu use_pure=True...")
            logging.debug(f"DEBUG_DB_HANDLER: Detalii: host={self.db_host}, port={self.db_port}, user={self.db_user}, db={self.db_name}")

            # Apelul de conectare la baza de date.
            # 'use_pure=True' este crucial pentru a evita problemele cu driverele C.
            self.conn = mysql.connector.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                connect_timeout=10, # Adaugă un timeout pentru conectare
                use_pure=True      # Forțează implementarea pur Python
            )
            
            logging.debug("DEBUG_DB_HANDLER: Apelul mysql.connector.connect() s-a finalizat cu succes.")
            return self.is_connected()
        
        except mysql.connector.Error as err:
            # Gestionează erorile specifice de conectare MySQL
            error_message = f"Eroare MySQL {err.errno}:\n{err.msg}"
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                error_message = "Acces refuzat. Verificați utilizatorul și parola."
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                error_message = f"Baza de date '{self.db_name}' nu există."
            elif err.errno in [errorcode.CR_CONN_HOST_ERROR, errorcode.CR_CONNECTION_ERROR]:
                 error_message = f"Nu se poate conecta la hostul DB '{self.db_host}:{self.db_port}'. Verificați adresa și firewall-ul."

            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Conexiune DB", error_message, parent=self.app_master_ref)
            else:
                logging.error(f"EROARE CONEXIUNE DB (fără UI): {error_message}")
            self.conn = None
            return False

        except Exception as e: # Prinde orice altă eroare neașteptată
            error_message_gen = f"Eroare neașteptată la conectarea la DB ({type(e).__name__}):\n{e}"
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                 messagebox.showerror("Eroare Necunoscută Conexiune", error_message_gen, parent=self.app_master_ref)
            else:
                logging.error(f"EROARE NECUNOSCUTĂ CONEXIUNE (fără UI): {error_message_gen}")
            self.conn = None
            return False

    def close_connection(self):
        if self.conn and self.conn.is_connected():
            try:
                self.conn.close()
                logging.debug("DEBUG_DB_HANDLER: Conexiune DB închisă.")
            except Exception as e:
                logging.error(f"Eroare la închiderea explicită a conexiunii DB: {e}")
        self.conn = None

    def is_connected(self):
        try: # Adăugăm try-except pentru robustețe
            return self.conn is not None and self.conn.is_connected()
        except:
            return False

    def _table_exists(self, cursor, table_name):
        try:
            # Corecție: Se face înlocuirea înainte de f-string pentru a evita eroarea de sintaxă.
            escaped_table_name = table_name.replace('_', '\\_') 
            cursor.execute(f"SHOW TABLES LIKE '{escaped_table_name}'")
            return cursor.fetchone() is not None
        except mysql.connector.Error as e:
            logging.error(f"Eroare la _table_exists pentru {table_name}: {e}")
            return False


    def _column_exists(self, cursor, table_name, column_name):
        # Asigură-te că self.db_name este setat și valid
        current_db_name = self.db_name
        if not current_db_name and self.is_connected(): # Încearcă să obții DB curent dacă nu e setat
            try:
                cursor.execute("SELECT DATABASE()")
                res = cursor.fetchone()
                if res and res[0]: current_db_name = res[0]
            except Exception as e_get_db:
                logging.debug(f"DEBUG_DB_HANDLER: Nu s-a putut obține DB curent pentru _column_exists: {e_get_db}")

        if not current_db_name:
            logging.error(f"Atenție: Numele bazei de date nu este disponibil pentru _column_exists ({table_name}.{column_name}).")
            return False
        
        query = """
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """
        try:
            cursor.execute(query, (current_db_name, table_name, column_name))
            return cursor.fetchone() is not None
        except mysql.connector.Error as e:
            logging.error(f"Eroare la verificarea coloanei {table_name}.{column_name} (DB: {current_db_name}): {e}")
            return False
            
    def _foreign_key_exists(self, cursor, table_name, constraint_name):
        current_db_name = self.db_name
        if not current_db_name and self.is_connected():
            try:
                cursor.execute("SELECT DATABASE()")
                res = cursor.fetchone()
                if res and res[0]: current_db_name = res[0]
            except: pass

        if not current_db_name: 
            logging.debug(f"DEBUG: _foreign_key_exists - db_name indisponibil pentru {table_name}.{constraint_name}")
            return False

        query = """
            SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s 
            AND CONSTRAINT_NAME = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'
        """
        try:
            cursor.execute(query, (current_db_name, table_name, constraint_name))
            return cursor.fetchone() is not None
        except mysql.connector.Error as e:
            logging.error(f"Eroare la verificarea FK {constraint_name} pe {table_name} (DB: {current_db_name}): {e}")
            return False

    def check_and_setup_database_schema(self, app_instance_ref):
        if not self.is_connected():
            return False

        master_ref = self.app_master_ref
        try:
            with self.conn.cursor() as cursor:
                # 1. Tabela 'tipuri_tranzactii'
                if not self._table_exists(cursor, 'tipuri_tranzactii'):
                    logging.debug("DEBUG_SCHEMA: Se creează tabela 'tipuri_tranzactii'...")
                    cursor.execute(DB_STRUCTURE_TIPURI_TRANZACTII_MARIADB)
                    self.conn.commit()

                # 2. Tabela 'conturi_bancare'
                if not self._table_exists(cursor, 'conturi_bancare'):
                    logging.debug("DEBUG_SCHEMA: Se creează tabela 'conturi_bancare'...")
                    cursor.execute(DB_STRUCTURE_CONTURI_BANCARE_MARIADB)
                    self.conn.commit()
                else:
                    if not self._column_exists(cursor, 'conturi_bancare', 'culoare_cont'):
                        logging.debug("DEBUG_SCHEMA: Se adaugă coloana 'culoare_cont'...")
                        cursor.execute("ALTER TABLE conturi_bancare ADD COLUMN culoare_cont VARCHAR(7) DEFAULT '#FFFFFF' AFTER observatii_cont;")
                        self.conn.commit()

                # 3. Tabela 'tranzactii'
                if not self._table_exists(cursor, 'tranzactii'):
                    logging.debug("DEBUG_SCHEMA: Se creează tabela 'tranzactii' (structură nouă)...")
                    cursor.execute(DB_STRUCTURE_TRANZACTII_V2_MARIADB)
                    self.conn.commit()
                else:
                    # Acest bloc se execută DOAR dacă tabela 'tranzactii' există deja
                    logging.debug("DEBUG_SCHEMA: Tabela 'tranzactii' există. Se verifică structura...")
                    
                    if not self._column_exists(cursor, 'tranzactii', 'id_cont_fk'):
                        cursor.execute(DB_ALTER_TRANZACTII_ADD_COLUMN_ID_CONT_FK_MARIADB)
                        app_instance_ref.migration_needed_for_existing_transactions = True

                    if not self._column_exists(cursor, 'tranzactii', 'cod_tranzactie_fk'):
                        cursor.execute("ALTER TABLE tranzactii ADD COLUMN cod_tranzactie_fk VARCHAR(4) NULL DEFAULT NULL AFTER tip;")

                    if not self._foreign_key_exists(cursor, 'tranzactii', 'fk_tranzactie_tip'):
                        cursor.execute("ALTER TABLE tranzactii ADD CONSTRAINT fk_tranzactie_tip FOREIGN KEY (cod_tranzactie_fk) REFERENCES tipuri_tranzactii(cod) ON DELETE SET NULL;")

                    if not self._column_exists(cursor, 'tranzactii', 'sold_initial'):
                        cursor.execute("ALTER TABLE tranzactii ADD COLUMN sold_initial DECIMAL(15, 2) NULL AFTER cont;")
                    
                    if not self._column_exists(cursor, 'tranzactii', 'sold_final'):
                        cursor.execute("ALTER TABLE tranzactii ADD COLUMN sold_final DECIMAL(15, 2) NULL AFTER sold_initial;")

                    if not self._column_exists(cursor, 'tranzactii', 'sold_dupa_tranzactie'):
                        cursor.execute("ALTER TABLE tranzactii ADD COLUMN sold_dupa_tranzactie DECIMAL(15, 2) NULL AFTER sold_final;")
                    
                    self.conn.commit()

            return True

        except Exception as e:
            if master_ref and master_ref.winfo_exists():
                messagebox.showerror("Eroare Schemă DB", f"O eroare neașteptată la schema DB:\n{e}", parent=master_ref)
            return False

    def get_all_accounts(self):
        if not self.is_connected(): 
            logging.debug("DEBUG_DB_HANDLER: get_all_accounts - Fără conexiune DB")
            return []
        try:
            # Asigură-te că 'culoare_cont' este inclus în SELECT
            accounts = self.fetch_all_dict(
                "SELECT id_cont, nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont "
                "FROM conturi_bancare ORDER BY nume_cont ASC"
            ) # Paranteza corectată aici
            return accounts if accounts else []
        except Exception as e:
            logging.debug(f"DEBUG_DB_HANDLER: Eroare în get_all_accounts: {e}")
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare DB", f"Nu s-au putut prelua conturile bancare:\n{e}", parent=self.app_master_ref)
            return []

    def fetch_all_dict(self, query, params=None):
        if not self.is_connected(): return []
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except mysql.connector.Error as e:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Preluare Date", f"Eroare SQL:\n{e.msg}", parent=self.app_master_ref)
            else: logging.error(f"EROARE SQL (fără UI) în fetch_all_dict: {e.msg}")
            return []
        except Exception as e_gen:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Preluare Date", f"Eroare generală:\n{e_gen}", parent=self.app_master_ref)
            else: logging.error(f"EROARE GENERALA (fără UI) în fetch_all_dict: {e_gen}")
            return []


    def fetch_one_dict(self, query, params=None):
        if not self.is_connected(): return None
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except mysql.connector.Error as e:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Preluare Rând", f"Eroare SQL:\n{e.msg}", parent=self.app_master_ref)
            else: logging.error(f"EROARE SQL (fără UI) în fetch_one_dict: {e.msg}")
            return None
        except Exception as e_gen:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Preluare Rând", f"Eroare generală:\n{e_gen}", parent=self.app_master_ref)
            else: logging.error(f"EROARE GENERALA (fără UI) în fetch_one_dict: {e_gen}")
            return None
            
    def fetch_scalar(self, query, params=None):
        if not self.is_connected(): return None
        try:
            with self.conn.cursor() as cursor: # Nu dictionary=True pentru fetch_scalar
                cursor.execute(query, params or ())
                result = cursor.fetchone()
                return result[0] if result and len(result) > 0 else None
        except mysql.connector.Error as e:
            logging.error(f"Eroare SQL la fetch_scalar ({query[:50]}...): {e.msg}")
            return None
        except Exception as e_gen:
             logging.error(f"Eroare generală la fetch_scalar ({query[:50]}...): {e_gen}")
             return None


    def execute_commit(self, query, params=None):
        if not self.is_connected(): return False
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params or ())
            self.conn.commit()
            return True
        except mysql.connector.Error as e:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Execuție Query", f"Eroare SQL la modificare date:\n{e.msg}", parent=self.app_master_ref)
            else: logging.error(f"EROARE SQL (fără UI) în execute_commit: {e.msg}")
            # Considerați self.conn.rollback() aici dacă este necesar, deși with context ar trebui să gestioneze
            return False
        except Exception as e_gen:
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare Execuție Query", f"Eroare generală la modificare date:\n{e_gen}", parent=self.app_master_ref)
            else: logging.error(f"EROARE GENERALA (fără UI) în execute_commit: {e_gen}")
            return False