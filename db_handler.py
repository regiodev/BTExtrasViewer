# db_handler.py
import mysql.connector
from mysql.connector import errorcode
import logging
import tkinter as tk
from tkinter import simpledialog, messagebox

# Importăm handler-ul de autentificare pentru a putea crea utilizatorul admin
import auth_handler

# --- CONSTANTE SQL PENTRU STRUCTURA BAZEI DE DATE ---
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
    data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
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
        # Am eliminat parametrii individuali și folosim un singur dicționar
        super().__init__(parent, title or "Configurare Conexiune MariaDB")

    def body(self, master):
        tk.Label(master, text="Host (IP NAS):").grid(row=0, sticky=tk.W, pady=2)
        self.host_entry = tk.Entry(master, width=30)
        self.host_entry.grid(row=0, column=1, pady=2)
        self.host_entry.insert(0, self.initial_config.get('host', '')) # Folosim cheia 'host'

        tk.Label(master, text="Port:").grid(row=1, sticky=tk.W, pady=2)
        self.port_entry = tk.Entry(master, width=30)
        self.port_entry.grid(row=1, column=1, pady=2)
        self.port_entry.insert(0, self.initial_config.get('port', '3306'))

        tk.Label(master, text="Nume Bază Date:").grid(row=2, sticky=tk.W, pady=2)
        self.dbname_entry = tk.Entry(master, width=30)
        self.dbname_entry.grid(row=2, column=1, pady=2)
        self.dbname_entry.insert(0, self.initial_config.get('database', '')) # Folosim cheia 'database'

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
            "database": self.dbname_entry.get().strip(), # Folosim cheia 'database'
            "user": self.user_entry.get().strip(),
            "password": self.password_entry.get()
        }

class DatabaseHandler:
    def __init__(self, db_credentials=None, app_master_ref=None):
        self.conn = None
        self.db_credentials = db_credentials
        self.app_master_ref = app_master_ref

    def get_audit_log_entries(self):
        """Preia toate înregistrările din jurnalul de acțiuni, ordonate descrescător după data."""
        if not self.is_connected(): return []
        query = """
            SELECT username, actiune, detalii, timestamp 
            FROM jurnal_actiuni 
            ORDER BY timestamp DESC;
        """
        return self.fetch_all_dict(query)

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
            DB_STRUCTURE_CONTURI_BANCARE_MARIADB,
            DB_STRUCTURE_TIPURI_TRANZACTII_MARIADB,
            DB_STRUCTURE_TRANZACTII_V2_MARIADB, # Folosim V2
            CREATE_TABLE_ISTORIC_IMPORTURI,
            DB_STRUCTURE_UTILIZATORI,
            DB_STRUCTURE_ROLURI,
            DB_STRUCTURE_UTILIZATORI_ROLURI,
            DB_STRUCTURE_ROLURI_PERMISIUNI,
            DB_STRUCTURE_UTILIZATORI_CONTURI,
            DB_STRUCTURE_JURNAL_ACTIUNI
        ]
        
        try:
            with self.conn.cursor() as cursor:
                for table_script in all_tables_scripts:
                    cursor.execute(table_script)
            self.conn.commit()
            logging.info("Toate tabelele au fost verificate/create cu succes.")
            self._seed_initial_data()
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
                    cursor.execute("INSERT INTO roluri (nume_rol, descriere) VALUES ('Administrator', 'Acces total la toate funcționalitățile aplicației.')")
                    id_rol_admin = cursor.lastrowid
                    cursor.execute("INSERT INTO roluri_permisiuni (id_rol, cheie_permisiune) VALUES (%s, %s)", (id_rol_admin, 'all_permissions'))
                self.conn.commit()
                logging.info("Rolul 'Administrator' a fost creat.")

            if self.fetch_scalar("SELECT COUNT(*) FROM utilizatori") == 0:
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

    # =========================================================================
    # NOU: Metoda get_all_accounts a fost adăugată înapoi
    # =========================================================================
    def get_all_accounts(self):
        if not self.is_connected():
            logging.debug("DEBUG_DB_HANDLER: get_all_accounts - Fără conexiune DB")
            return []
        try:
            accounts = self.fetch_all_dict(
                "SELECT id_cont, nume_cont, iban, nume_banca, valuta, observatii_cont, culoare_cont "
                "FROM conturi_bancare ORDER BY nume_cont ASC"
            )
            return accounts if accounts else []
        except Exception as e:
            logging.error(f"Eroare în get_all_accounts: {e}")
            if self.app_master_ref and self.app_master_ref.winfo_exists():
                messagebox.showerror("Eroare DB", f"Nu s-au putut prelua conturile bancare:\n{e}", parent=self.app_master_ref)
            return []
    # =========================================================================

    def get_user_by_username(self, username):
        query = "SELECT id, username, parola_hash, salt, activ FROM utilizatori WHERE username = %s"
        return self.fetch_one_dict(query, (username,))

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

    def log_action(self, user_id, username, action, details=""):
        query = "INSERT INTO jurnal_actiuni (id_utilizator, username, actiune, detalii) VALUES (%s, %s, %s, %s)"
        self.execute_commit(query, (user_id, username, action, details))

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
            if self.app_master_ref:
                messagebox.showerror("Eroare Execuție Query", f"Eroare SQL: {e.msg}", parent=self.app_master_ref)
            return False

    def get_all_roles(self):
        """Returnează toate rolurile definite în baza de date."""
        if not self.is_connected(): return []
        return self.fetch_all_dict("SELECT id, nume_rol FROM roluri ORDER BY nume_rol ASC")

    def get_user_details(self, user_id):
        """Returnează detaliile complete pentru un utilizator, inclusiv rolurile și conturile asignate."""
        if not self.is_connected(): return None

        user_info = self.fetch_one_dict("SELECT id, username, nume_complet, activ FROM utilizatori WHERE id = %s", (user_id,))
        if not user_info:
            return None

        # Preluăm ID-urile rolurilor asignate utilizatorului
        roles_raw = self.fetch_all_dict("SELECT id_rol FROM utilizatori_roluri WHERE id_utilizator = %s", (user_id,))
        user_info['role_ids'] = {r['id_rol'] for r in roles_raw}

        # Preluăm ID-urile conturilor permise pentru utilizator
        accounts_raw = self.fetch_all_dict("SELECT id_cont FROM utilizatori_conturi_permise WHERE id_utilizator = %s", (user_id,))
        user_info['account_ids'] = {acc['id_cont'] for acc in accounts_raw}

        return user_info

    def get_all_users_with_roles(self):
        """Preia toți utilizatorii și o listă concatenată a rolurilor lor."""
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
        """Inversează starea 'activ' a unui utilizator."""
        if not self.is_connected(): return False
        # Prevenim dezactivarea utilizatorului cu ID 1 (considerat super-admin)
        if user_id == 1:
            logging.warning("Încercare de dezactivare a utilizatorului cu ID 1 (admin) a fost blocată.")
            return False, "Utilizatorul administrator principal nu poate fi dezactivat."

        query = "UPDATE utilizatori SET activ = NOT activ WHERE id = %s AND id != 1"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (user_id,))
            self.conn.commit()
            return True, "Starea utilizatorului a fost actualizată."
        except mysql.connector.Error as e:
            logging.error(f"Eroare la schimbarea stării utilizatorului ID {user_id}: {e}")
            return False, f"Eroare DB: {e.msg}"
        
    def count_active_admins(self):
        """Numără câți utilizatori activi au rolul de Administrator."""
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
        """Șterge un utilizator din baza de date."""
        if user_id == 1:
            return False, "Utilizatorul administrator principal (ID 1) nu poate fi șters."
        if not self.is_connected():
            return False, "Fără conexiune la baza de date."
        
        # 'ON DELETE CASCADE' din schema DB se va ocupa de ștergerea legăturilor
        # din tabelele utilizatori_roluri și utilizatori_conturi_permise.
        query = "DELETE FROM utilizatori WHERE id = %s"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (user_id,))
            self.conn.commit()
            return True, "Utilizatorul a fost șters cu succes."
        except mysql.connector.Error as e:
            self.conn.rollback()
            return False, f"Eroare DB la ștergere: {e.msg}"