# db_handler.py
import mysql.connector
from mysql.connector import errorcode
import logging
import tkinter as tk
from tkinter import simpledialog, messagebox
import json

# Importăm auth_handler, care este acum un modul 'frate' în pachetul 'common'
from . import auth_handler

# --- CONSTANTE SQL PENTRU STRUCTURA BAZEI DE DATE (neschimbate) ---
DB_STRUCTURE_CONTURI_BANCARE_MARIADB = """
CREATE TABLE IF NOT EXISTS conturi_bancare (
    id_cont INT AUTO_INCREMENT PRIMARY KEY,
    nume_cont VARCHAR(100) NOT NULL,
    iban VARCHAR(34) UNIQUE,
    nume_banca VARCHAR(100),
    valuta VARCHAR(10) DEFAULT 'RON',
    data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observatii_cont TEXT,
    culoare_cont VARCHAR(7) DEFAULT '#FFFFFF',
    CONSTRAINT uq_nume_cont UNIQUE (nume_cont)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_VALUTE = """
CREATE TABLE IF NOT EXISTS valute (
    cod_valuta VARCHAR(5) PRIMARY KEY,
    data_adaugare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_SWIFT_CODES = """
CREATE TABLE IF NOT EXISTS swift_code_descriptions (
    cod_swift VARCHAR(4) PRIMARY KEY,
    descriere_standard TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_TIPURI_TRANZACTII_MARIADB = """
CREATE TABLE IF NOT EXISTS tipuri_tranzactii (
    cod VARCHAR(4) PRIMARY KEY,
    descriere_tip VARCHAR(255) NOT NULL,
    este_operational BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
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
    sold_dupa_tranzactie DECIMAL(15, 2),
    observatii VARCHAR(300),
    CONSTRAINT fk_tranzactie_cont FOREIGN KEY (id_cont_fk) REFERENCES conturi_bancare(id_cont) ON DELETE RESTRICT,
    CONSTRAINT fk_tranzactie_tip FOREIGN KEY (cod_tranzactie_fk) REFERENCES tipuri_tranzactii(cod) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
CREATE_TABLE_ISTORIC_IMPORTURI = """
CREATE TABLE IF NOT EXISTS istoric_importuri (
    id_import INT AUTO_INCREMENT PRIMARY KEY,
    nume_fisier VARCHAR(255) NOT NULL,
    data_import TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tranzactii_procesate INT NOT NULL,
    tranzactii_ignorate INT NOT NULL,
    id_cont_fk INT NOT NULL,
    id_utilizator_fk INT,
    FOREIGN KEY (id_cont_fk) REFERENCES conturi_bancare(id_cont) ON DELETE CASCADE,
    FOREIGN KEY (id_utilizator_fk) REFERENCES utilizatori(id) ON DELETE SET NULL
) ENGINE=InnoDB;
"""

DB_STRUCTURE_UTILIZATORI = """
CREATE TABLE IF NOT EXISTS utilizatori (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    parola_hash VARCHAR(256) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    nume_complet VARCHAR(100),
    activ BOOLEAN DEFAULT TRUE,
    data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    setari_ui JSON DEFAULT NULL,
    tranzactie_acces ENUM('toate', 'credit', 'debit') NOT NULL DEFAULT 'toate'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
# Notă: Scriptul de mai sus este doar pentru referință, presupunând că ALTER a fost deja rulat.

DB_STRUCTURE_ROLURI = """
CREATE TABLE IF NOT EXISTS roluri (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nume_rol VARCHAR(50) NOT NULL UNIQUE,
    descriere TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_UTILIZATORI_ROLURI = """
CREATE TABLE IF NOT EXISTS utilizatori_roluri (
    id_utilizator INT,
    id_rol INT,
    PRIMARY KEY (id_utilizator, id_rol),
    FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id) ON DELETE CASCADE,
    FOREIGN KEY (id_rol) REFERENCES roluri(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_ROLURI_PERMISIUNI = """
CREATE TABLE IF NOT EXISTS roluri_permisiuni (
    id_rol INT,
    cheie_permisiune VARCHAR(100),
    PRIMARY KEY (id_rol, cheie_permisiune),
    FOREIGN KEY (id_rol) REFERENCES roluri(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_UTILIZATORI_CONTURI = """
CREATE TABLE IF NOT EXISTS utilizatori_conturi_permise (
    id_utilizator INT,
    id_cont INT,
    PRIMARY KEY (id_utilizator, id_cont),
    FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id) ON DELETE CASCADE,
    FOREIGN KEY (id_cont) REFERENCES conturi_bancare(id_cont) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
DB_STRUCTURE_JURNAL_ACTIUNI = """
CREATE TABLE IF NOT EXISTS jurnal_actiuni (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_utilizator INT,
    username VARCHAR(50),
    actiune VARCHAR(255) NOT NULL,
    detalii TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

class MariaDBConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial_config=None):
        self.initial_config = initial_config or {}
        super().__init__(parent, title or "Configurare Conexiune MariaDB")

    def body(self, master):
        tk.Label(master, text="Host (IP NAS):").grid(row=0, sticky=tk.W, pady=2)
        self.host_entry = tk.Entry(master, width=30)
        self.host_entry.grid(row=0, column=1, pady=2)
        self.host_entry.insert(0, self.initial_config.get('host', ''))

        tk.Label(master, text="Port:").grid(row=1, sticky=tk.W, pady=2)
        self.port_entry = tk.Entry(master, width=30)
        self.port_entry.grid(row=1, column=1, pady=2)
        self.port_entry.insert(0, self.initial_config.get('port', '3306'))

        tk.Label(master, text="Nume Bază Date:").grid(row=2, sticky=tk.W, pady=2)
        self.dbname_entry = tk.Entry(master, width=30)
        self.dbname_entry.grid(row=2, column=1, pady=2)
        self.dbname_entry.insert(0, self.initial_config.get('database', ''))

        tk.Label(master, text="Utilizator DB:").grid(row=3, sticky=tk.W, pady=2)
        self.user_entry = tk.Entry(master, width=30)
        self.user_entry.grid(row=3, column=1, pady=2)
        self.user_entry.insert(0, self.initial_config.get('user', ''))

        tk.Label(master, text="Parolă DB:").grid(row=4, sticky=tk.W, pady=2)
        self.password_entry = tk.Entry(master, show="*", width=30)
        self.password_entry.grid(row=4, column=1, pady=2)
        self.password_entry.insert(0, self.initial_config.get('password', ''))
        
        return self.host_entry

    def apply(self):
        try:
            port = int(self.port_entry.get())
        except (ValueError, TypeError):
            port = 3306
            
        self.result = {
            "host": self.host_entry.get().strip(),
            "port": port,
            "database": self.dbname_entry.get().strip(),
            "user": self.user_entry.get().strip(),
            "password": self.password_entry.get()
        }

class DatabaseHandler:
    def __init__(self, db_credentials=None, app_master_ref=None):
        self.conn = None
        self.db_credentials = db_credentials
        self.app_master_ref = app_master_ref

    def _seed_swift_codes_table(self):
        """Populează tabela cu descrierile standard ale codurilor SWIFT dacă aceasta este goală."""
        if not self.is_connected(): return
        
        try:
            count = self.fetch_scalar("SELECT COUNT(*) FROM swift_code_descriptions")
            if count == 0:
                logging.info("Tabela swift_code_descriptions este goală. Se populează cu datele standard în limba română...")
                
                # Lista a fost actualizată cu descrierile în limba română din fișierul Excel.
                swift_data = [
                    ('BOE', 'Cambie (Bill of exchange)'),
                    ('BRF', 'Taxa de brokeraj (Brokerage fee)'),
                    ('CAR', 'Tranzactie cu cardul (Card transaction)'),
                    ('CAS', 'Scrisori de numerar/Cecuri (Cash letters/Cheques)'),
                    ('CDT', 'Transfer de credit (Credit transfer)'),
                    ('CEC', 'Debit de la tert consumator (Consumer third party debit)'),
                    ('CHG', 'Taxe si alte cheltuieli (Charges and other expenses)'),
                    ('CHK', 'Cecuri (Cheques)'),
                    ('CLR', 'Compensare scrisori de numerar/cecuri (Cash letters/Cheques clearing)'),
                    ('CMI', 'Element de gestionare a numerarului; de ex. sweeping (Cash management item; e.g. sweeping)'),
                    ('CMN', 'Element de gestionare a numerarului - Fara aviz (Cash management item - No-advise)'),
                    ('CMP', 'Cereri de compensare (Compensation claims)'),
                    ('CMS', 'Element de gestionare a numerarului - Aviz (Cash management item - Advise)'),
                    ('CMT', 'Element de gestionare a numerarului - Transfer (Cash management item - Transfer)'),
                    ('CMZ', 'Element de gestionare a numerarului - Aviz/Transfer (Cash management item - Advise/Transfer)'),
                    ('COL', 'Colectari (Collections)'),
                    ('COM', 'Comision (Commission)'),
                    ('COU', 'Plati de cupoane (Coupon payments)'),
                    ('CRE', 'Credit (Credit)'),
                    ('DCR', 'Credit documentar (Documentary credit)'),
                    ('DEB', 'Debit (Debit)'),
                    ('DIV', 'Dividend (Dividend)'),
                    ('EQV', 'Suma echivalenta (Equivalent amount)'),
                    ('EXT', 'Extra (Extra)'),
                    ('FEX', 'Schimb valutar (Foreign exchange)'),
                    ('INT', 'Dobanda (Interest)'),
                    ('LBX', 'Caseta de valori (Lockbox)'),
                    ('LDP', 'Depozit de imprumut (Loan deposit)'),
                    ('MAR', 'Plati in marja (Margin payments)'),
                    ('MAT', 'Scadenta (Maturity)'),
                    ('MSC', 'Diverse (Miscellaneous)'),
                    ('NWI', 'Emisiune noua (New-issuance)'),
                    ('ODC', 'Taxa de descoperire de cont (Overdraft charge)'),
                    ('PCH', 'Cumparare/Vanzare (Purchase/Sale)'),
                    ('POP', 'Punct de cumparare (Point of purchase)'),
                    ('PRN', 'Plata principalului (Principal pay-down)'),
                    ('REC', 'Incasare (Receipt)'),
                    ('RED', 'Rascumparare (Redemption)'),
                    ('REP', 'Operatiune Repo (Repo)'),
                    ('RET', 'Returnare (Return)'),
                    ('SAL', 'Salariu/Pensie (Salary/Pension)'),
                    ('SEC', 'Valori mobiliare (Securities)'),
                    ('STO', 'Ordin de plata programat (Standing order)'),
                    ('STP', 'Imprumut de valori mobiliare (Securities lending)'),
                    ('SUB', 'Subscriere (Subscription)'),
                    ('SWP', 'Ordin de plata SWIFT (SWIFT payment order)'),
                    ('TAX', 'Impozit (Tax)'),
                    ('TCK', 'Cecuri de calatorie (Travellers cheques)'),
                    ('TRF', 'Transfer (Transfer)'),
                    ('TRN', 'Tranzactie (Transaction)'),
                    ('UWC', 'Angajament de subscriere (Underwriting commitment)'),
                    ('VDA', 'Ajustarea datei valorii (Value date adjustment)'),
                    ('WAR', 'Mandat (Warrant)'),
                    ('NCHG', 'Comisioane sau cheltuieli aplicate de entitati terte, nu de banca'),
                    ('NCOL', 'Incasare de sume in numele clientului (de la o terta parte, NU de la banca)'),
                    ('NFEX', 'Schimb valutar initiata prin sau de un tert, nu direct de banca'),
                    ('NINT', 'Dobanda creditata in contul clientului'),
                    ('NLDP', 'Imprumut primit sau un depozit de la un tert'),
                    ('NMSC', 'Tranzactie diversa, neclasificata, in favoarea clientului'),
                    ('NTRF', 'Transfer de tip Ordin de Plata (Network Transfer)'),
                    ('NTDB', 'Transfer de debit in retea (Network Debit Transfer)'),
                    ('NTCR', 'Transfer de credit in retea (Network Credit Transfer)'),
                    ('NTCF', 'Transfer de numerar in avans in retea (Network Cash-in-advance Transfer)'),
                    ('NTRY', 'Intrare (generica) (Entry (Generic))'),
                    ('RTI', 'Element returnat (Return Item)')
                ]

                with self.conn.cursor() as cursor:
                    sql_insert = "INSERT INTO swift_code_descriptions (cod_swift, descriere_standard) VALUES (%s, %s)"
                    cursor.executemany(sql_insert, swift_data)
                
                self.conn.commit()
                logging.info(f"{len(swift_data)} înregistrări SWIFT standard au fost inserate.")

        except mysql.connector.Error as err:
            logging.error(f"Eroare la popularea tabelei swift_code_descriptions: {err.msg}")
            self.conn.rollback()

    # --- METODE EXISTENTE (majoritatea neschimbate) ---
    def connect(self):
        if not self.db_credentials:
            logging.error("Credentiale DB lipsesc. Conectare eșuată.")
            return False
        try:
            self.conn = mysql.connector.connect(**self.db_credentials, autocommit=False)
            logging.info(f"Conectat cu succes la DB '{self.db_credentials.get('database')}' pe host '{self.db_credentials.get('host')}'.")
            return True
        except mysql.connector.Error as err:
            logging.error(f"Eroare conectare la MariaDB: {err}")
            self.conn = None
            if self.app_master_ref:
                messagebox.showerror("Eroare Conexiune DB", f"Nu s-a putut conecta la serverul de baze de date:\n{err}", parent=self.app_master_ref)
            return False

    def close_connection(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()
            logging.info("Conexiune la baza de date închisă.")

    def is_connected(self):
        return self.conn is not None and self.conn.is_connected()

    def check_and_setup_database_schema(self):
        if not self.is_connected(): return False
        
        logging.info("Verificare și configurare schemă bază de date...")
        
        all_tables_scripts = [
                DB_STRUCTURE_CONTURI_BANCARE_MARIADB, DB_STRUCTURE_TIPURI_TRANZACTII_MARIADB,
                DB_STRUCTURE_UTILIZATORI, DB_STRUCTURE_ROLURI, DB_STRUCTURE_TRANZACTII_V2_MARIADB,
                CREATE_TABLE_ISTORIC_IMPORTURI, DB_STRUCTURE_UTILIZATORI_ROLURI,
                DB_STRUCTURE_ROLURI_PERMISIUNI, DB_STRUCTURE_UTILIZATORI_CONTURI,
                DB_STRUCTURE_JURNAL_ACTIUNI,
                DB_STRUCTURE_SWIFT_CODES,
                DB_STRUCTURE_VALUTE
            ]
        
        try:
            with self.conn.cursor() as cursor:
                for table_script in all_tables_scripts:
                    cursor.execute(table_script)
            self.conn.commit()
            logging.info("Toate tabelele au fost verificate/create cu succes.")
            self._seed_initial_data()
            self._seed_swift_codes_table()
            self._seed_valute_table()
            return True
        
        except mysql.connector.Error as err:
            logging.error(f"Eroare la crearea schemei DB: {err.msg}")
            self.conn.rollback()
            return False

    def _seed_initial_data(self):
        if not self.is_connected(): return

        try:
            if self.fetch_scalar("SELECT COUNT(*) FROM roluri") == 0:
                logging.info("Nu există roluri. Se inserează rolurile implicite...")
                with self.conn.cursor() as cursor:
                    cursor.execute("INSERT INTO roluri (nume_rol, descriere) VALUES (%s, %s)", ('Administrator', 'Acces total la toate funcționalitățile aplicației.'))
                    id_rol_admin = cursor.lastrowid
                    cursor.execute("INSERT INTO roluri_permisiuni (id_rol, cheie_permisiune) VALUES (%s, %s)", (id_rol_admin, 'all_permissions'))
                    
                    cursor.execute("INSERT INTO roluri (nume_rol, descriere) VALUES (%s, %s)", ('Operator Date', 'Acces limitat pentru import și vizualizare rapoarte.'))
                    id_rol_operator = cursor.lastrowid
                    
                    # --- MODIFICAT: Adăugăm noua permisiune pentru SMTP ---
                    permisiuni_operator = [
                        'import_files', 'export_data', 'view_reports', 'run_report_cashflow', 
                        'run_report_balance_evolution', 'run_report_transaction_analysis', 
                        'view_import_history', 'configure_smtp'
                    ]

                    cursor.execute("INSERT INTO roluri_permisiuni (id_rol, cheie_permisiune) VALUES (%s, %s)", (id_rol_admin, 'manage_swift_codes'))

                    for perm in permisiuni_operator:
                        cursor.execute("INSERT INTO roluri_permisiuni (id_rol, cheie_permisiune) VALUES (%s, %s)", (id_rol_operator, perm))

                self.conn.commit()
                logging.info("Rolurile 'Administrator' și 'Operator Date' au fost create.")

            if self.fetch_scalar("SELECT COUNT(*) FROM utilizatori") == 0:
                # ... (restul metodei rămâne neschimbat) ...
                logging.info("Nu există utilizatori. Se creează utilizatorul 'admin' implicit...")
                admin_user, admin_pass = 'admin', 'admin123'
                salt, pass_hash = auth_handler.hash_parola(admin_pass)
                with self.conn.cursor() as cursor:
                    query_user = "INSERT INTO utilizatori (username, parola_hash, salt, nume_complet, activ) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(query_user, (admin_user, pass_hash, salt, 'Administrator Sistem', True))
                    id_user_admin = cursor.lastrowid
                    id_rol_admin = self.fetch_scalar("SELECT id FROM roluri WHERE nume_rol = 'Administrator'")
                    if id_user_admin and id_rol_admin:
                        query_role = "INSERT INTO utilizatori_roluri (id_utilizator, id_rol) VALUES (%s, %s)"
                        cursor.execute(query_role, (id_user_admin, id_rol_admin))
                self.conn.commit()
                logging.warning(f"Utilizator 'admin' creat cu parola temporară: '{admin_pass}'")
                if self.app_master_ref:
                    messagebox.showinfo("Utilizator Implicit Creat", f"A fost creat un cont de administrator:\n\nUtilizator: {admin_user}\nParolă: {admin_pass}", parent=self.app_master_ref)
        except mysql.connector.Error as err:
            logging.error(f"Eroare la inserarea datelor inițiale (seed): {err.msg}")
            self.conn.rollback()

    def fetch_all_dict(self, query, params=None):
        if not self.is_connected(): return []
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Eroare SQL la fetch_all_dict: {e.msg}")
            return []

    def fetch_one_dict(self, query, params=None):
        if not self.is_connected(): return None
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except mysql.connector.Error as e:
            logging.error(f"Eroare SQL la fetch_one_dict: {e.msg}")
            return None

    def fetch_scalar(self, query, params=None):
        if not self.is_connected(): return None
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params or ())
                result = cursor.fetchone()
            return result[0] if result and len(result) > 0 else None
        except mysql.connector.Error as e:
            logging.error(f"Eroare SQL la fetch_scalar: {e.msg}")
            return None

    def execute_commit(self, query, params=None):
        if not self.is_connected(): return False
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params or ())
            self.conn.commit()
            return True
        except mysql.connector.Error as e:
            logging.error(f"EROARE SQL în execute_commit: {e.msg}")
            self.conn.rollback() # Anulăm tranzacția în caz de eroare
            if self.app_master_ref:
                messagebox.showerror("Eroare Execuție Query", f"Eroare SQL: {e.msg}", parent=self.app_master_ref)
            return False

    def get_all_currencies(self):
        """Returnează o listă cu toate codurile de valute din baza de date."""
        if not self.is_connected(): return []
        results = self.fetch_all_dict("SELECT cod_valuta FROM valute ORDER BY cod_valuta ASC")
        return [r['cod_valuta'] for r in results]

    def add_currency(self, cod_valuta):
        """Adaugă o nouă valută în baza de date."""
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        try:
            sql = "INSERT INTO valute (cod_valuta) VALUES (%s)"
            if self.execute_commit(sql, (cod_valuta,)):
                return True, "Valuta a fost adăugată."
            else:
                return False, "Eroare la adăugarea valutei."
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                return False, "Această valută există deja."
            return False, f"Eroare DB: {e.msg}"

    def delete_currency(self, cod_valuta):
        """Șterge o valută, doar dacă nu este folosită de niciun cont."""
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        
        # Verificare critică: nu ștergem o valută dacă este în uz
        usage_count = self.fetch_scalar("SELECT COUNT(*) FROM conturi_bancare WHERE valuta = %s", (cod_valuta,))
        if usage_count > 0:
            return False, f"Valuta '{cod_valuta}' nu poate fi ștearsă deoarece este folosită de {usage_count} cont(uri)."
            
        sql = "DELETE FROM valute WHERE cod_valuta = %s"
        if self.execute_commit(sql, (cod_valuta,)):
            return True, "Valuta a fost ștearsă."
        else:
            return False, "Eroare la ștergerea valutei."

    def _seed_valute_table(self):
        """Populează tabela `valute` cu o listă implicită dacă tabela este goală."""
        if not self.is_connected(): return
        
        try:
            count = self.fetch_scalar("SELECT COUNT(*) FROM valute")
            if count == 0:
                logging.info("Tabela valute este goală. Se populează cu datele standard...")
                
                valute_standard = [('RON',), ('EUR',), ('USD',), ('GBP',), ('CHF',)]

                with self.conn.cursor() as cursor:
                    sql_insert = "INSERT INTO valute (cod_valuta) VALUES (%s)"
                    cursor.executemany(sql_insert, valute_standard)
                
                self.conn.commit()
                logging.info(f"{len(valute_standard)} valute standard au fost inserate.")

        except mysql.connector.Error as err:
            logging.error(f"Eroare la popularea tabelei valute: {err.msg}")
            self.conn.rollback()

    def get_all_accounts(self):
        if not self.is_connected(): return []
        return self.fetch_all_dict(
            "SELECT id_cont, nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont "
            "FROM conturi_bancare ORDER BY nume_cont ASC"
        )
        
    def log_action(self, user_id, username, action, details=""):
        query = "INSERT INTO jurnal_actiuni (id_utilizator, username, actiune, detalii) VALUES (%s, %s, %s, %s)"
        self.execute_commit(query, (user_id, username, action, details))

    def get_audit_log_entries(self):
        if not self.is_connected(): return []
        query = "SELECT username, actiune, detalii, timestamp FROM jurnal_actiuni ORDER BY timestamp DESC;"
        return self.fetch_all_dict(query)

    # --- METODE PENTRU SETĂRI UI (JSON) ---
    def get_user_settings(self, user_id):
        if not self.is_connected(): return {}
        raw_settings = self.fetch_scalar("SELECT setari_ui FROM utilizatori WHERE id = %s", (user_id,))
        if raw_settings:
            try:
                return json.loads(raw_settings)
            except json.JSONDecodeError:
                logging.error(f"Eroare la decodarea setărilor JSON pentru user ID {user_id}")
                return {}
        return {}

    def save_user_settings(self, user_id, settings_dict):
        if not self.is_connected(): return False
        try:
            settings_json = json.dumps(settings_dict, indent=4)
            return self.execute_commit(
                "UPDATE utilizatori SET setari_ui = %s WHERE id = %s",
                (settings_json, user_id)
            )
        except TypeError as e:
            logging.error(f"Eroare la serializarea setărilor în JSON pentru user ID {user_id}: {e}")
            return False

    # --- METODE MODIFICATE PENTRU A INCLUDE 'tranzactie_acces' ---

    # --- METODĂ MODIFICATĂ ---
    def get_user_by_username(self, username):
        # Adăugăm 'tranzactie_acces' la interogare
        query = "SELECT id, username, parola_hash, salt, activ, tranzactie_acces FROM utilizatori WHERE username = %s"
        return self.fetch_one_dict(query, (username,))

    # --- METODĂ MODIFICATĂ ---
    def get_user_details(self, user_id):
        """Returnează detaliile complete pentru un utilizator, inclusiv rolurile, conturile și accesul la tranzacții."""
        if not self.is_connected(): return None

        # Adăugăm 'tranzactie_acces' la interogare
        user_info = self.fetch_one_dict("SELECT id, username, nume_complet, activ, tranzactie_acces FROM utilizatori WHERE id = %s", (user_id,))
        if not user_info:
            return None

        roles_raw = self.fetch_all_dict("SELECT id_rol FROM utilizatori_roluri WHERE id_utilizator = %s", (user_id,))
        user_info['role_ids'] = {r['id_rol'] for r in roles_raw}

        accounts_raw = self.fetch_all_dict("SELECT id_cont FROM utilizatori_conturi_permise WHERE id_utilizator = %s", (user_id,))
        user_info['account_ids'] = {acc['id_cont'] for acc in accounts_raw}

        return user_info

    # --- METODE NOI PENTRU GESTIONAREA ROLURILOR ȘI PERMISIUNILOR ---

    # --- METODĂ NOUĂ ---
    def get_all_roles(self):
        """Returnează toate rolurile definite (ID, nume, descriere)."""
        if not self.is_connected(): return []
        return self.fetch_all_dict("SELECT id, nume_rol, descriere FROM roluri ORDER BY nume_rol ASC")

    # --- METODĂ NOUĂ ---
    def add_role(self, role_name, description=''):
        """Adaugă un rol nou în baza de date."""
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        try:
            sql = "INSERT INTO roluri (nume_rol, descriere) VALUES (%s, %s)"
            if self.execute_commit(sql, (role_name, description)):
                return True, "Rolul a fost adăugat cu succes."
            else:
                return False, "Eroare la adăugarea rolului."
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                return False, "Un rol cu acest nume există deja."
            return False, f"Eroare DB: {e.msg}"

    # --- METODĂ NOUĂ ---
    def rename_role(self, role_id, new_name):
        """Redenumește un rol existent."""
        if role_id == 1:
            return False, "Rolul 'Administrator' nu poate fi redenumit."
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        try:
            sql = "UPDATE roluri SET nume_rol = %s WHERE id = %s"
            if self.execute_commit(sql, (new_name, role_id)):
                return True, "Rolul a fost redenumit."
            else:
                return False, "Eroare la redenumirea rolului."
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                return False, "Un rol cu acest nume există deja."
            return False, f"Eroare DB: {e.msg}"

    # --- METODĂ NOUĂ ---
    def delete_role(self, role_id):
        """Șterge un rol. 'ON DELETE CASCADE' va curăța tabelele de legătură."""
        if role_id == 1:
            return False, "Rolul 'Administrator' nu poate fi șters."
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        
        # Verificăm dacă rolul este încă utilizat
        user_count = self.fetch_scalar("SELECT COUNT(*) FROM utilizatori_roluri WHERE id_rol = %s", (role_id,))
        if user_count > 0:
            return False, f"Rolul este încă asignat la {user_count} utilizator(i) și nu poate fi șters."

        sql = "DELETE FROM roluri WHERE id = %s"
        if self.execute_commit(sql, (role_id,)):
            return True, "Rolul a fost șters."
        else:
            return False, "Eroare la ștergerea rolului."

    # --- METODĂ NOUĂ ---
    def get_role_permissions(self, role_id):
        """Returnează o listă cu cheile de permisiune pentru un anumit rol."""
        if not self.is_connected(): return []
        sql = "SELECT cheie_permisiune FROM roluri_permisiuni WHERE id_rol = %s"
        results = self.fetch_all_dict(sql, (role_id,))
        return [p['cheie_permisiune'] for p in results]

    def save_permissions_for_role(self, role_id, permissions_list):
        """Salvează setul complet de permisiuni pentru un rol, într-o tranzacție."""
        if not self.is_connected(): return False
        
        cursor = None  # Inițializăm cursorul ca None
        try:
            # --- MODIFICARE: Am eliminat self.conn.start_transaction() ---
            # Tranzacția va fi gestionată implicit de connector.
            
            cursor = self.conn.cursor()

            # Ștergem permisiunile vechi
            cursor.execute("DELETE FROM roluri_permisiuni WHERE id_rol = %s", (role_id,))

            # Inserăm permisiunile noi, dacă există
            if permissions_list:
                sql_insert = "INSERT INTO roluri_permisiuni (id_rol, cheie_permisiune) VALUES (%s, %s)"
                data_to_insert = [(role_id, perm) for perm in permissions_list]
                cursor.executemany(sql_insert, data_to_insert)
            
            # Finalizăm tranzacția prin commit
            self.conn.commit()
            return True
        except mysql.connector.Error as e:
            logging.error(f"Eroare la salvarea permisiunilor pentru rolul {role_id}: {e}")
            self.conn.rollback() # Anulăm orice modificare în caz de eroare
            return False
        finally:
            # Asigurăm închiderea cursorului
            if cursor:
                cursor.close()

    def get_all_swift_descriptions(self):
        """Returnează toate descrierile standard SWIFT din baza de date."""
        if not self.is_connected(): return []
        return self.fetch_all_dict("SELECT cod_swift, descriere_standard FROM swift_code_descriptions ORDER BY cod_swift ASC")

    def update_swift_description(self, code, description):
        """Actualizează descrierea standard pentru un cod SWIFT."""
        if not self.is_connected(): return False
        sql = "UPDATE swift_code_descriptions SET descriere_standard = %s WHERE cod_swift = %s"
        return self.execute_commit(sql, (description, code))
    
    def get_user_permissions(self, user_id):
        query = """
            SELECT DISTINCT rp.cheie_permisiune
            FROM roluri_permisiuni rp
            JOIN utilizatori_roluri ur ON rp.id_rol = ur.id_rol
            WHERE ur.id_utilizator = %s
        """
        results = self.fetch_all_dict(query, (user_id,))
        if any(p['cheie_permisiune'] == 'all_permissions' for p in results):
            return ['all_permissions']
        return [p['cheie_permisiune'] for p in results]

    def get_allowed_accounts_for_user(self, user_id):
        query = "SELECT id_cont FROM utilizatori_conturi_permise WHERE id_utilizator = %s"
        results = self.fetch_all_dict(query, (user_id,))
        return [acc['id_cont'] for acc in results]

    def get_all_users_with_roles(self):
        if not self.is_connected(): return []
        query = """
            SELECT u.id, u.username, u.nume_complet, u.activ, 
                   GROUP_CONCAT(r.nume_rol SEPARATOR ', ') as roluri
            FROM utilizatori u
            LEFT JOIN utilizatori_roluri ur ON u.id = ur.id_utilizator
            LEFT JOIN roluri r ON ur.id_rol = r.id
            GROUP BY u.id, u.username, u.nume_complet, u.activ
            ORDER BY u.username ASC;
        """
        return self.fetch_all_dict(query)

    def toggle_user_status(self, user_id):
        if user_id == 1:
            return False, "Utilizatorul administrator principal nu poate fi dezactivat."
        if not self.is_connected(): return False, "Fără conexiune la baza de date."
        query = "UPDATE utilizatori SET activ = NOT activ WHERE id = %s AND id != 1"
        try:
            if self.execute_commit(query, (user_id,)):
                 return True, "Starea utilizatorului a fost actualizată."
            else:
                 return False, "Eroare la actualizarea stării."
        except mysql.connector.Error as e:
            logging.error(f"Eroare la schimbarea stării utilizatorului ID {user_id}: {e}")
            return False, f"Eroare DB: {e.msg}"
        
    def count_active_admins(self):
        if not self.is_connected(): return 0
        query = """
            SELECT COUNT(u.id)
            FROM utilizatori u
            JOIN utilizatori_roluri ur ON u.id = ur.id_utilizator
            JOIN roluri r ON ur.id_rol = r.id
            WHERE u.activ = TRUE AND r.nume_rol = 'Administrator';
        """
        count = self.fetch_scalar(query)
        return count if count is not None else 0

    def delete_user(self, user_id):
        if user_id == 1:
            return False, "Utilizatorul administrator principal (ID 1) nu poate fi șters."
        if not self.is_connected():
            return False, "Fără conexiune la baza de date."
        query = "DELETE FROM utilizatori WHERE id = %s"
        if self.execute_commit(query, (user_id,)):
             return True, "Utilizatorul a fost șters cu succes."
        else:
             return False, "Eroare DB la ștergere."