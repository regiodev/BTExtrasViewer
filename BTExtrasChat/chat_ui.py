# BTExtrasChat/chat_ui.py

import tkinter as tk
from tkinter import ttk, simpledialog, scrolledtext, messagebox
import threading
import queue
import time
from datetime import datetime, timedelta
import mysql.connector

class ChatWindow:
    def __init__(self, master, db_handler, user_data, db_creds):
        self.master = master
        self.db_handler = db_handler
        self.current_user = user_data
        self.db_creds = db_creds

        self.master.title("BTExtras Chat")
        self.master.geometry("500x600")
        self.master.minsize(400, 400)

        self.active_conversation_id = None
        self.users_list = []
        self.unread_counts = {}
        self.conversation_details = {} # <-- LINIA NOUĂ, ADĂUGATĂ AICI
        
        self.message_queue = queue.Queue()
        self.is_running = True

        self._setup_ui()
        
        # Logica de pornire, în ordinea corectă
        self._load_initial_state() 
        self._populate_conversation_list()
        
        # 3. Pornim thread-urile pentru funcționalitățile în timp real
        self.polling_thread = threading.Thread(target=self._poll_for_new_messages, daemon=True)
        self.polling_thread.start()
        self.master.after(100, self._process_message_queue)
        self._schedule_user_list_refresh()

        # --- Creare Tooltip pentru Timestamp ---
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tooltip_label = ttk.Label(self.tooltip, text="", background="#FFFFE0", relief="solid", borderwidth=1, padding=2)
        self.tooltip_label.pack()

        self.line_to_message_map = {}

    def _schedule_user_list_refresh(self):
        """Reîmprospătează periodic lista de utilizatori pentru a actualiza statusul."""
        if self.is_running:
            self._populate_conversation_list()
            self.master.after(20000, self._schedule_user_list_refresh) # Reîmprospătare la 20 secunde

    def _on_manage_groups(self):
        """Deschide dialogul de administrare a grupurilor."""
        dialog = GroupManagerDialog(self.master, self.db_handler, self.current_user['id'])
        # După ce dialogul este închis, reîmprospătăm lista principală de conversații,
        # deoarece un grup ar fi putut fi redenumit, creat sau șters.
        self._populate_conversation_list()

    def _poll_for_new_messages(self):
        """Versiune finală: Rulează în fundal, caută mesaje noi și trimite heartbeat."""
        polling_conn = None
        try:
            polling_conn = mysql.connector.connect(**self.db_creds)
            
            while self.is_running:
                cursor = None
                try:
                    cursor = polling_conn.cursor(dictionary=True)

                    # 1. Heartbeat
                    cursor.execute(
                        "UPDATE utilizatori SET last_seen = CURRENT_TIMESTAMP WHERE id = %s",
                        (self.current_user['id'],)
                    )
                    polling_conn.commit()

                    # 2. Căutare mesaje noi
                    sql_select_new = """
                        SELECT
                            m.id, m.id_conversatie_fk, m.id_expeditor_fk, m.continut_mesaj, m.timestamp, m.stare,
                            COALESCE(u.nume_complet, u.username) AS expeditor
                        FROM
                            chat_mesaje m
                        JOIN chat_participanti p ON m.id_conversatie_fk = p.id_conversatie_fk
                        JOIN utilizatori u ON m.id_expeditor_fk = u.id
                        WHERE
                            p.id_utilizator_fk = %s
                            AND m.id_expeditor_fk != %s
                            AND m.stare = 'trimis'
                    """
                    cursor.execute(sql_select_new, (self.current_user['id'], self.current_user['id']))
                    new_messages = cursor.fetchall()
                    
                    if new_messages:
                        ids_to_update = [msg['id'] for msg in new_messages]
                        placeholders = ','.join(['%s'] * len(ids_to_update))
                        cursor.execute(
                            f"UPDATE chat_mesaje SET stare = 'livrat' WHERE id IN ({placeholders})",
                            tuple(ids_to_update)
                        )
                        polling_conn.commit()
                        
                        for msg in new_messages:
                            self.message_queue.put(msg)

                except mysql.connector.Error as db_err:
                    print(f"Eroare DB în bucla de polling: {db_err}.")
                    time.sleep(10)
                    if not (polling_conn and polling_conn.is_connected()):
                        polling_conn = mysql.connector.connect(**self.db_creds)
                finally:
                    if cursor:
                        cursor.close()
                
                time.sleep(3)
        except Exception as e:
            print(f"EROARE CRITICĂ în thread-ul de polling: {e}")
        finally:
            if polling_conn and polling_conn.is_connected():
                polling_conn.close()

    def _process_message_queue(self):
        """Procesează mesajele din coadă și le afișează sau le marchează ca necitite."""
        updated_unread_list = False
        try:
            while not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                
                if msg['id_conversatie_fk'] == self.active_conversation_id:
                    self._display_message(msg)
                else:
                    sender_id = msg['id_expeditor_fk']
                    self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1
                    updated_unread_list = True

        except queue.Empty:
            pass
        finally:
            if updated_unread_list:
                self._populate_conversation_list()
            
            if self.is_running:
                self.master.after(200, self._process_message_queue)

    def _display_message(self, msg_data):
        """Afișează un singur mesaj, adăugând prefix cu numele expeditorului pentru grupurri."""
        self.message_display.config(state="normal")
        
        is_my_message = msg_data['id_expeditor_fk'] == self.current_user['id']
        tag = "sent" if is_my_message else "received"
        
        # Obținem detaliile conversației active
        active_conv_details = self.conversation_details.get(self.active_conversation_id)
        
        prefix = ""
        # Adăugăm numele expeditorului DOAR dacă suntem într-un grup și NU este mesajul nostru
        if active_conv_details and active_conv_details['tip_conversatie'] == 'grup' and not is_my_message:
            # Folosim doar prenumele pentru a păstra interfața aerisită
            sender_name = (msg_data['expeditor'] or "Utilizator").split(' ')[0]
            prefix = f"{sender_name}:\n"
        
        # Obținem indexul de start înainte de a insera textul
        start_index = self.message_display.index(tk.END)
        
        # Construim mesajul final și îl inserăm
        formatted_message = f"{prefix}{msg_data['continut_mesaj']}"
        self.message_display.insert(tk.END, formatted_message, tag)
        
        if is_my_message and msg_data['stare'] == 'citit':
            self.message_display.insert(tk.END, " ✓", "read_receipt")
        
        self.message_display.insert(tk.END, "\n\n", "line_spacing") # Spațiu mai mare între mesaje
        
        end_index = self.message_display.index(tk.END)
        start_line = int(start_index.split('.')[0])
        end_line = int(end_index.split('.')[0])
        for i in range(start_line, end_line + 1):
             self.line_to_message_map[str(i)] = msg_data
        
        self.message_display.see(tk.END)
        self.message_display.config(state="disabled")

    def _setup_ui(self):
        """Construiește componentele vizuale ale ferestrei."""
        main_pane = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Panoul din Stânga: Lista de Conversații ---
        users_frame = ttk.LabelFrame(main_pane, text="Conversații", width=250)
        main_pane.add(users_frame, weight=1)

        # Revenim la modul 'headings' pentru control total asupra coloanelor
        self.user_tree = ttk.Treeview(users_frame, columns=("status_icon", "name"), show="headings", selectmode="browse")

        # Configurăm coloanele
        self.user_tree.column("#0", width=0, stretch=tk.NO) # Ascundem complet coloana arborescentă
        self.user_tree.column("status_icon", anchor="center", width=30, stretch=tk.NO)
        self.user_tree.column("name", anchor="w", width=180)

        # Setăm antete goale pentru a fi invizibile
        self.user_tree.heading("status_icon", text="")
        self.user_tree.heading("name", text="")

        self.user_tree.pack(fill=tk.BOTH, expand=True)
        # Am redenumit metoda de callback pentru claritate
        self.user_tree.bind("<<TreeviewSelect>>", self._on_conversation_selected) 

        # Configurăm stilurile pentru lista de conversații
        self.user_tree.tag_configure("online", foreground="green")
        self.user_tree.tag_configure("offline", foreground="red")
        self.user_tree.tag_configure("unread", font=("Segoe UI", 9, "bold"))
        self.user_tree.tag_configure("group_chat", foreground="#0000AA")
        
        # Creăm un cadru pentru butoanele de acțiune
        action_buttons_frame = ttk.Frame(users_frame)
        action_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0), padx=2)
        action_buttons_frame.columnconfigure((0, 1), weight=1) # Permite butoanelor să se extindă

        new_chat_button = ttk.Button(action_buttons_frame, text="Utilizatori", command=self._on_new_conversation)
        new_chat_button.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        manage_groups_button = ttk.Button(action_buttons_frame, text="Grupuri", command=self._on_manage_groups)
        manage_groups_button.grid(row=0, column=1, sticky="ew", padx=(2, 0))
        
        # --- Panoul din Dreapta: Conversația Activă ---
        chat_frame = ttk.Frame(main_pane)
        main_pane.add(chat_frame, weight=10)
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        self.message_display = scrolledtext.ScrolledText(chat_frame, state="disabled", wrap=tk.WORD, font=("Segoe UI", 10))
        self.message_display.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.message_display.bind("<Motion>", self._on_mouse_move_on_message)
        self.message_display.bind("<Leave>", self._hide_tooltip)
        
        self.message_display.tag_configure("read_receipt", foreground="blue", font=("Segoe UI", 8))
        self.message_display.tag_configure("sent", justify="right", foreground="#006400") # Verde închis pentru text
        self.message_display.tag_configure("received", justify="left", foreground="#00008B") # Albastru închis pentru text
        self.message_display.tag_configure("date_separator", justify="center", foreground="gray", font=("Segoe UI", 8, "italic"))
        
        self.message_input = ttk.Entry(chat_frame, font=("Segoe UI", 10))
        self.message_input.grid(row=1, column=0, sticky="ew", padx=(5, 0), pady=5)
        
        self.send_button = ttk.Button(chat_frame, text="Trimite")
        self.send_button.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=5)
        self.send_button.config(command=self._send_message)
        self.message_input.bind("<Return>", self._send_message)

        status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN, padding=(5, 3))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        display_name = self.current_user.get('nume_complet') or self.current_user['username']
        self.user_identity_label = ttk.Label(
            status_bar_frame,
            text=f"Conectat ca: {display_name}",
            font=("Segoe UI", 9, "bold")
        )
        self.user_identity_label.pack(side=tk.LEFT)

    def _on_mouse_move_on_message(self, event):
        """Afișează tooltip-ul când mouse-ul este deasupra unui mesaj."""
        try:
            # Obținem indexul textului de sub cursor (ex: '5.14')
            index = self.message_display.index(f"@{event.x},{event.y}")
            # Obținem doar numărul liniei (ex: '5')
            line_start_index = index.split('.')[0]
            
            # Căutăm în harta noastră dacă există un mesaj pe acea linie
            msg_data = self.line_to_message_map.get(line_start_index)

            if msg_data:
                timestamp_str = msg_data['timestamp'].strftime('%H:%M')
                self._show_tooltip(timestamp_str, event.x_root + 10, event.y_root + 10)
            else:
                self._hide_tooltip()
        except tk.TclError:
            self._hide_tooltip()

    def _show_tooltip(self, text, x, y):
        """Actualizează textul și poziția tooltip-ului și îl afișează."""
        self.tooltip_label.config(text=text)
        self.tooltip.geometry(f"+{x}+{y}")
        self.tooltip.deiconify() # Face tooltip-ul vizibil

    def _hide_tooltip(self, event=None):
        """Ascunde tooltip-ul."""
        self.tooltip.withdraw()

    def _send_message(self, event=None):
        """Trimite mesajul din câmpul de input în conversația activă."""
        message_text = self.message_input.get().strip()
        if not message_text or self.active_conversation_id is None:
            return

        try:
            success = self.db_handler.execute_commit(
                "INSERT INTO chat_mesaje (id_conversatie_fk, id_expeditor_fk, continut_mesaj) VALUES (%s, %s, %s)",
                (self.active_conversation_id, self.current_user['id'], message_text)
            )
            if success:
                self.message_input.delete(0, tk.END)
                # Reîncărcăm istoricul pentru a afișa și noul mesaj
                self._load_conversation_history()
            else:
                messagebox.showwarning("Eroare", "Mesajul nu a putut fi trimis.")
        except Exception as e:
            messagebox.showerror("Eroare Trimitere", str(e))

    def _on_conversation_selected(self, event=None):
        """Invocată la selecția unei conversații. Încarcă istoricul și resetează contoarele."""
        selection = self.user_tree.selection()
        if not selection or not selection[0]:
            return

        selected_conv_id = int(selection[0])
        if self.active_conversation_id == selected_conv_id:
            return
            
        self.active_conversation_id = selected_conv_id

        conv_details = self.conversation_details.get(selected_conv_id)
        if not conv_details:
            return

        display_name = conv_details.get('display_name')
        prefix = "Grup: " if conv_details.get('tip_conversatie') == 'grup' else ""
        self.master.title(f"BTExtras Chat - {prefix}{display_name}")
        
        self._load_conversation_history()

    def _mark_messages_as_read_in_db(self, message_ids_to_update):
        """
        Metodă care marchează o listă de ID-uri de mesaje ca fiind 'citit',
        folosind conexiunea principală a aplicației.
        """
        if not message_ids_to_update:
            return

        print(f"INFO: Se marchează ca 'citit' {len(message_ids_to_update)} mesaje.")
        
        try:
            # Folosim conexiunea deja existentă a handler-ului principal
            cursor = self.db_handler.conn.cursor()
            
            placeholders = ','.join(['%s'] * len(message_ids_to_update))
            sql_update = f"UPDATE chat_mesaje SET stare = 'citit' WHERE id IN ({placeholders})"
            
            cursor.execute(sql_update, tuple(message_ids_to_update))
            # Commit-ul nu este necesar, deoarece conexiunea principală este pe autocommit=True
            
            print(f"SUCCES: Comanda UPDATE a afectat {cursor.rowcount} rânduri.")
            cursor.close()
        except Exception as e:
            print(f"EROARE la marcarea mesajelor ca citite: {e}")

    def _get_or_create_conversation(self, partner_id):
        """
        Găsește o conversație 1-la-1 existentă sau creează una nouă.
        Folosește o interogare robustă pentru a preveni duplicatele.
        """
        my_id = self.current_user['id']
        
        # --- Interogare SQL robustă pentru a găsi conversația 1-la-1 ---
        sql_find = """
            SELECT p.id_conversatie_fk
            FROM chat_participanti p
            JOIN chat_conversatii c ON p.id_conversatie_fk = c.id
            WHERE c.tip_conversatie = 'unu_la_unu'
              AND p.id_utilizator_fk IN (%s, %s)
            GROUP BY p.id_conversatie_fk
            HAVING COUNT(DISTINCT p.id_utilizator_fk) = 2
            LIMIT 1;
        """
        conversation_id = self.db_handler.fetch_scalar(sql_find, (my_id, partner_id))

        if conversation_id:
            return conversation_id
        else:
            # Creare conversație nouă
            cursor = None
            try:
                cursor = self.db_handler.conn.cursor()
                cursor.execute("INSERT INTO chat_conversatii (tip_conversatie) VALUES ('unu_la_unu')")
                new_conv_id = cursor.lastrowid
                
                participants = [(new_conv_id, my_id), (new_conv_id, partner_id)]
                cursor.executemany("INSERT INTO chat_participanti (id_conversatie_fk, id_utilizator_fk) VALUES (%s, %s)", participants)
                
                return new_conv_id
            except Exception as e:
                messagebox.showerror("Eroare Creare Conversație", str(e))
                return None
            finally:
                if cursor:
                    cursor.close()

    def _load_initial_state(self):
        """
        Rulează o singură dată la pornire pentru a stabili starea inițială.
        Populează contoarele de necitite și stabilește ID-ul maxim de la care va porni polling-ul.
        """
        print("INFO: Se încarcă starea inițială (mesaje necitite și ultimul ID)...")
        # 1. Obținem contoarele corecte la pornire
        self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])

        # 2. Găsim ID-ul maxim al unui mesaj din conversațiile noastre
        # Aceasta va fi "linia de start" pentru polling-ul în timp real
        conv_ids_raw = self.db_handler.fetch_all_dict("SELECT id_conversatie_fk FROM chat_participanti WHERE id_utilizator_fk = %s", (self.current_user['id'],))
        if conv_ids_raw:
            conv_ids = tuple(item['id_conversatie_fk'] for item in conv_ids_raw)
            placeholders = ','.join(['%s'] * len(conv_ids))
            max_id = self.db_handler.fetch_scalar(
                f"SELECT MAX(id) FROM chat_mesaje WHERE id_conversatie_fk IN ({placeholders})",
                conv_ids
            )
            self.last_polled_message_id = max_id if max_id else 0
        else:
            self.last_polled_message_id = 0
            
        print(f"INFO: Stare inițială încărcată. Contoare: {self.unread_counts}. Polling-ul va porni de la ID > {self.last_polled_message_id}.")

    def _load_conversation_history(self):
        """
        Încarcă istoricul, marchează mesajele ca 'citit' în DB, apoi reîncarcă
        contoarele de necitite și reîmprospătează lista de conversații.
        """
        # ... (codul existent de la începutul metodei, până la if not messages:) ...
        self.message_display.config(state="normal")
        self.message_display.delete("1.0", tk.END)
        self.line_to_message_map.clear()

        if not self.active_conversation_id:
            self.message_display.config(state="disabled")
            return
        
        messages = self.db_handler.fetch_all_dict(
            """
            SELECT m.id, m.id_expeditor_fk, m.continut_mesaj, m.timestamp, m.stare,
                   COALESCE(u.nume_complet, u.username) AS expeditor
            FROM chat_mesaje m
            JOIN utilizatori u ON m.id_expeditor_fk = u.id
            WHERE m.id_conversatie_fk = %s ORDER BY m.timestamp ASC
            """, (self.active_conversation_id,)
        )
        
        if not messages:
            self.message_display.config(state="disabled")
            # Chiar dacă nu sunt mesaje, trebuie să reîmprospătăm contoarele
            self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
            self._populate_conversation_list()
            return

        ids_to_mark_as_read = [
            msg['id'] for msg in messages 
            if msg['id_expeditor_fk'] != self.current_user['id'] and msg['stare'] != 'citit'
        ]

        if ids_to_mark_as_read:
            self._mark_messages_as_read_in_db(ids_to_mark_as_read)
        
        # --- BLOC NOU ȘI CRUCIAL ---
        # După ce am marcat mesajele ca 'citit' în DB, cerem din nou starea reală a contoarelor
        self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
        # Și reîmprospătăm complet lista de conversații
        self._populate_conversation_list()
        
        # Afișăm mesajele din conversația curentă
        last_message_date = None
        for msg in messages:
            current_message_date = msg['timestamp'].date()
            if current_message_date != last_message_date:
                date_str = current_message_date.strftime('%d %B %Y')
                self.message_display.insert(tk.END, f"\n{date_str}\n", "date_separator")
                last_message_date = current_message_date
            
            # Actualizăm starea locală pentru a afișa bifa corect imediat
            if msg['id'] in ids_to_mark_as_read:
                msg['stare'] = 'citit'
            
            self._display_message(msg)

        self.message_display.config(state="disabled")

    def _on_create_group(self):
        """Deschide dialogul de creare a unui grup și salvează datele în DB."""
        # Preluăm o listă proaspătă de utilizatori disponibili pentru a o pasa dialogului
        available_users = self.db_handler.fetch_all_dict(
            "SELECT id, username, nume_complet FROM utilizatori WHERE activ = TRUE AND id != %s ORDER BY nume_complet ASC",
            (self.current_user['id'],)
        )
        if not available_users:
            messagebox.showinfo("Informație", "Nu există alți utilizatori disponibili pentru a crea un grup.", parent=self.master)
            return
            
        dialog = CreateGroupDialog(self.master, available_users)
        
        # dialog.result va fi populat doar dacă se apasă OK și validarea trece
        if dialog.result:
            group_name = dialog.result['participant_ids']
            # Adăugăm și creatorul grupului la lista de participanți
            participant_ids = dialog.result['participant_ids'] + [self.current_user['id']]
            
            # --- Operațiune tranzacțională în baza de date ---
            cursor = None
            try:
                cursor = self.db_handler.conn.cursor()
                
                # 1. Inserăm conversația de tip 'grup'
                cursor.execute(
                    "INSERT INTO chat_conversatii (nume_conversatie, tip_conversatie) VALUES (%s, 'grup')",
                    (dialog.result['group_name'],)
                )
                new_conversation_id = cursor.lastrowid
                
                # 2. Inserăm toți participanții
                participants_data = [(new_conversation_id, user_id) for user_id in participant_ids]
                cursor.executemany(
                    "INSERT INTO chat_participanti (id_conversatie_fk, id_utilizator_fk) VALUES (%s, %s)",
                    participants_data
                )
                
                # Nu este nevoie de commit() dacă folosim autocommit=True
                
                messagebox.showinfo("Succes", f"Grupul '{dialog.result['group_name']}' a fost creat.", parent=self.master)
                # Reîmprospătăm lista de conversații pentru a afișa noul grup
                self._populate_conversation_list()
                
            except Exception as e:
                messagebox.showerror("Eroare Bază de Date", f"Grupul nu a putut fi creat:\n{e}", parent=self.master)
            finally:
                if cursor:
                    cursor.close()

    def _populate_conversation_list(self):
        """
        Populează lista cu toate conversațiile și afișează statusul vizual
        (simbol + culoare) pentru conversațiile 1-la-1.
        """
        try:
            my_id = self.current_user['id']
            sql = """
                (SELECT
                    c.id AS conversation_id, 'unu_la_unu' as tip_conversatie,
                    other_p.id_utilizator_fk AS partner_id, ou.last_seen,
                    COALESCE(ou.nume_complet, ou.username) as display_name,
                    (SELECT MAX(timestamp) FROM chat_mesaje cm WHERE cm.id_conversatie_fk = c.id) as last_message_time
                FROM chat_conversatii c
                JOIN chat_participanti my_p ON c.id = my_p.id_conversatie_fk AND my_p.id_utilizator_fk = %s
                JOIN chat_participanti other_p ON c.id = other_p.id_conversatie_fk AND other_p.id_utilizator_fk != %s
                LEFT JOIN utilizatori ou ON other_p.id_utilizator_fk = ou.id
                WHERE c.tip_conversatie = 'unu_la_unu')
                UNION
                (SELECT c.id AS conversation_id, 'grup' as tip_conversatie,
                    NULL AS partner_id, NULL AS last_seen,
                    c.nume_conversatie AS display_name,
                    (SELECT MAX(timestamp) FROM chat_mesaje cm WHERE cm.id_conversatie_fk = c.id) as last_message_time
                FROM chat_conversatii c
                JOIN chat_participanti my_p ON c.id = my_p.id_conversatie_fk AND my_p.id_utilizator_fk = %s
                WHERE c.tip_conversatie = 'grup')
                ORDER BY last_message_time DESC;
            """
            conversations = self.db_handler.fetch_all_dict(sql, (my_id, my_id, my_id))
            
            selected_item_id = self.user_tree.selection()[0] if self.user_tree.selection() else None
            
            self.conversation_details.clear()
            self.user_tree.delete(*self.user_tree.get_children())

            if conversations:
                for conv in conversations:
                    self.conversation_details[conv['conversation_id']] = conv
                    
                    display_name = conv['display_name'] or "Conversație"
                    status_prefix = ""
                    tags_to_apply = []

                    status_symbol = ""
                    # Stabilim simbolul și tag-urile de culoare
                    if conv['tip_conversatie'] == 'unu_la_unu':
                        is_online = conv['last_seen'] and (datetime.now() - conv['last_seen'] < timedelta(seconds=15))
                        if is_online:
                            status_symbol = "✓"
                            tags_to_apply.append('online')
                        else:
                            status_symbol = "✗"
                            tags_to_apply.append('offline')
                    else: # Este grup
                        status_symbol = "G" # Simbol pentru grup
                        tags_to_apply.append('group_chat')

                    # Adăugăm contorul la nume dacă e cazul
                    unread_count = 0
                    if conv['tip_conversatie'] == 'unu_la_unu' and conv.get('partner_id'):
                        unread_count = self.unread_counts.get(conv['partner_id'], 0)
                    
                    if unread_count > 0:
                        display_name = f"{display_name} ({unread_count})"
                        tags_to_apply.append("unread")

                    # Inserăm datele în cele două coloane definite: 'status_icon' și 'name'
                    self.user_tree.insert(
                        "", 
                        "end", 
                        iid=conv['conversation_id'], 
                        values=(status_symbol, display_name), 
                        tags=tuple(tags_to_apply)
                    )

            if selected_item_id and self.user_tree.exists(selected_item_id):
                self.user_tree.selection_set(selected_item_id)

        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut încărca lista de conversații: {e}")

    def _on_new_conversation(self):
        """Deschide un dialog pentru a selecta un utilizator și a iniția o conversație 1-la-1."""
        available_users = self.db_handler.fetch_all_dict(
            "SELECT id, username, nume_complet FROM utilizatori WHERE activ = TRUE AND id != %s ORDER BY nume_complet ASC",
            (self.current_user['id'],)
        )
        if not available_users:
            messagebox.showinfo("Informație", "Nu există alți utilizatori disponibili.", parent=self.master)
            return

        dialog = NewChatDialog(self.master, available_users)
        
        if dialog.result:
            partner_id = dialog.result
            # Folosim metoda deja existentă pentru a găsi sau crea conversația
            conv_id = self._get_or_create_conversation(partner_id)
            if conv_id:
                # Reîmprospătăm lista pentru a ne asigura că noua conversație apare
                self._populate_conversation_list()
                # Selectăm automat conversația nou creată/găsită
                self.user_tree.selection_set(conv_id)
                self.user_tree.focus(conv_id)
                self.user_tree.see(conv_id)

    def on_closing(self):
        """Gestionează închiderea ferestrei și oprește thread-ul de polling."""
        print("Aplicația de chat se închide, se oprește polling-ul...")
        self.is_running = False
        self.master.destroy()

class CreateGroupDialog(simpledialog.Dialog):
    """Fereastră de dialog pentru crearea unei noi conversații de grup."""
    def __init__(self, parent, all_users):
        self.all_users = all_users
        self.result = None
        super().__init__(parent, "Creare Conversație de Grup Nouă")

    def body(self, master):
        ttk.Label(master, text="Numele Grupului:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.group_name_entry = ttk.Entry(master, width=40)
        self.group_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(master, text="Selectați Participanții:").grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        
        list_frame = ttk.Frame(master)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5)
        
        self.user_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, exportselection=False, height=10)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_listbox.yview)
        self.user_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.user_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populăm lista cu utilizatori disponibili
        for user in self.all_users:
            display_name = user.get('nume_complet') or user['username']
            # Stocăm ID-ul și numele pentru a le recupera ulterior
            self.user_listbox.insert(tk.END, display_name)
            self.user_listbox.user_data = self.all_users

        return self.group_name_entry

    def validate(self):
        self.group_name = self.group_name_entry.get().strip()
        self.selected_indices = self.user_listbox.curselection()

        if not self.group_name:
            messagebox.showwarning("Date Incomplete", "Numele grupului este obligatoriu.", parent=self)
            return 0
        
        # Este necesar cel puțin un alt participant pe lângă creator
        if not self.selected_indices:
            messagebox.showwarning("Date Incomplete", "Selectați cel puțin un alt participant.", parent=self)
            return 0
            
        return 1

    def apply(self):
        # Colectăm ID-urile utilizatorilor selectați
        selected_user_ids = [self.user_listbox.user_data[i]['id'] for i in self.selected_indices]
        
        self.result = {
            "group_name": self.group_name,
            "participant_ids": selected_user_ids
        }

class NewChatDialog(simpledialog.Dialog):
    """Fereastră de dialog pentru selectarea unui utilizator pentru o nouă conversație 1-la-1."""
    def __init__(self, parent, available_users):
        self.available_users = available_users
        self.result = None
        super().__init__(parent, "Începe o Conversație Nouă")

    def body(self, master):
        ttk.Label(master, text="Selectați un utilizator:").pack(padx=5, pady=5)
        
        self.listbox = tk.Listbox(master, height=10, width=50, exportselection=False)
        self.listbox.pack(padx=5, pady=5)

        for user in self.available_users:
            display_name = user.get('nume_complet') or user.get('username')
            self.listbox.insert(tk.END, display_name)
        
        return self.listbox

    def validate(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Selecție Invalidă", "Vă rugăm selectați un utilizator.", parent=self)
            return 0
        return 1

    def apply(self):
        selected_index = self.listbox.curselection()[0]
        self.result = self.available_users[selected_index]['id']

class GroupManagerDialog(simpledialog.Dialog):
    """Fereastră de dialog pentru administrarea conversațiilor de grup."""
    def __init__(self, parent, db_handler, user_id):
        self.db_handler = db_handler
        self.current_user_id = user_id
        self.selected_group_id = None
        super().__init__(parent, "Administrare Grupuri")

    def body(self, master):
        self.master.geometry("700x500") # Setăm o dimensiune mai mare
        main_pane = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Panoul din Stânga: Lista de Grupuri ---
        groups_list_frame = ttk.LabelFrame(main_pane, text="Grupurile Mele", width=250)
        main_pane.add(groups_list_frame, weight=1)
        
        self.groups_listbox = tk.Listbox(groups_list_frame, exportselection=False)
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select) # Vom activa în pasul următor

        # --- Panoul din Dreapta: Detalii și Acțiuni Grup ---
        details_frame = ttk.LabelFrame(main_pane, text="Detalii Grup Selectat")
        main_pane.add(details_frame, weight=2)

        # Numele grupului
        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume:").pack(side=tk.LEFT)
        self.group_name_var = tk.StringVar()
        self.group_name_entry = ttk.Entry(name_frame, textvariable=self.group_name_var, state="disabled")
        self.group_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.save_name_button = ttk.Button(name_frame, text="Salvează Nume", state="disabled")
        self.save_name_button.pack(side=tk.LEFT)

        # Lista de participanți
        participants_frame = ttk.LabelFrame(details_frame, text="Participanți")
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.participants_listbox = tk.Listbox(participants_frame, exportselection=False)
        self.participants_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Butoane de acțiune pentru participanți
        participant_actions_frame = ttk.Frame(details_frame)
        participant_actions_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_participant_button = ttk.Button(participant_actions_frame, text="Adaugă Participant", state="disabled")
        self.add_participant_button.pack(side=tk.LEFT)
        self.remove_participant_button = ttk.Button(participant_actions_frame, text="Șterge Participant", state="disabled")
        self.remove_participant_button.pack(side=tk.LEFT, padx=5)

        # Butoane de acțiune pentru întregul grup
        group_actions_frame = ttk.Frame(details_frame)
        group_actions_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        self.delete_group_button = ttk.Button(group_actions_frame, text="Șterge Grupul", state="disabled")
        self.delete_group_button.pack(side=tk.RIGHT)
        
        return self.groups_listbox

    def buttonbox(self):
        # Suprascriem pentru a avea butoanele noastre
        box = ttk.Frame(self)
        # Butonul de creare grup nou va fi aici
        self.create_new_group_button = ttk.Button(box, text="Creează un Grup Nou...")
        self.create_new_group_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        ttk.Button(box, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=10, pady=10)
        box.pack()

class AddParticipantDialog(simpledialog.Dialog):
    """Dialog pentru a selecta utilizatori noi de adăugat într-un grup."""
    def __init__(self, parent, users_to_add):
        self.users_to_add = users_to_add
        self.result = None
        super().__init__(parent, "Adaugă Participanți Noi")

    def body(self, master):
        self.title("Adaugă Participanți")
        ttk.Label(master, text="Selectați utilizatorii pe care doriți să îi adăugați:").pack(padx=5, pady=5)
        
        list_frame = ttk.Frame(master)
        list_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        self.listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, exportselection=False, height=10, width=40)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for user in self.users_to_add:
            display_name = user.get('nume_complet') or user.get('username')
            self.listbox.insert(tk.END, display_name)
        
        return self.listbox

    def apply(self):
        selected_indices = self.listbox.curselection()
        if selected_indices:
            self.result = [self.users_to_add[i]['id'] for i in selected_indices]

# Acum, înlocuiți clasa GroupManagerDialog existentă cu această versiune completă
class GroupManagerDialog(simpledialog.Dialog):
    """Fereastră de dialog pentru administrarea conversațiilor de grup."""
    def __init__(self, parent, db_handler, user_id):
        self.db_handler = db_handler
        self.current_user_id = user_id
        self.selected_group_id = None
        self.listbox_map = {}
        self.participants_map = {}
        super().__init__(parent, "Administrare Grupuri")

    def body(self, master):
        self.master.geometry("700x500")
        main_pane = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Panoul din Stânga
        groups_list_frame = ttk.LabelFrame(main_pane, text="Grupurile Mele", width=250)
        main_pane.add(groups_list_frame, weight=1)
        self.groups_listbox = tk.Listbox(groups_list_frame, exportselection=False)
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        # Panoul din Dreapta
        details_frame = ttk.LabelFrame(main_pane, text="Detalii Grup Selectat")
        main_pane.add(details_frame, weight=2)

        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume:").pack(side=tk.LEFT)
        self.group_name_var = tk.StringVar()
        self.group_name_entry = ttk.Entry(name_frame, textvariable=self.group_name_var, state="disabled")
        self.group_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.save_name_button = ttk.Button(name_frame, text="Salvează Nume", state="disabled", command=self._save_group_name)
        self.save_name_button.pack(side=tk.LEFT)

        participants_frame = ttk.LabelFrame(details_frame, text="Participanți")
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.participants_listbox = tk.Listbox(participants_frame, exportselection=False)
        self.participants_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.participants_listbox.bind("<<ListboxSelect>>", self._on_participant_select)

        participant_actions_frame = ttk.Frame(details_frame)
        participant_actions_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_participant_button = ttk.Button(participant_actions_frame, text="Adaugă Participant", state="disabled", command=self._add_participant)
        self.add_participant_button.pack(side=tk.LEFT)
        self.remove_participant_button = ttk.Button(participant_actions_frame, text="Șterge Participant", state="disabled", command=self._remove_participant)
        self.remove_participant_button.pack(side=tk.LEFT, padx=5)

        group_actions_frame = ttk.Frame(details_frame)
        group_actions_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        self.delete_group_button = ttk.Button(group_actions_frame, text="Șterge Grupul", state="disabled")
        self.delete_group_button.pack(side=tk.RIGHT)
        
        self._populate_group_list()
        return self.groups_listbox

    def buttonbox(self):
        box = ttk.Frame(self)
        self.create_new_group_button = ttk.Button(box, text="Creează un Grup Nou...")
        self.create_new_group_button.pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(box, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=10, pady=10)
        box.pack()

    def _populate_group_list(self):
        """Populează lista de grupuri din stânga."""
        current_selection = self.groups_listbox.curselection()
        self.groups_listbox.delete(0, tk.END)
        self.listbox_map.clear()
        
        my_groups = self.db_handler.get_groups_for_user(self.current_user_id)
        for index, group in enumerate(my_groups):
            self.groups_listbox.insert(index, group['nume_conversatie'])
            self.listbox_map[index] = group['id']
        
        if current_selection:
            self.groups_listbox.selection_set(current_selection[0])
        
        self._clear_details_panel()
        self._on_group_select()

    def _clear_details_panel(self):
        """Golește panoul din dreapta și dezactivează butoanele."""
        self.group_name_var.set("")
        self.participants_listbox.delete(0, tk.END)
        self.group_name_entry.config(state="disabled")
        self.save_name_button.config(state="disabled")
        self.add_participant_button.config(state="disabled")
        self.remove_participant_button.config(state="disabled")
        self.delete_group_button.config(state="disabled")
        self.selected_group_id = None

    def _on_group_select(self, event=None):
        """Invocată la click pe un grup. Afișează detaliile în panoul din dreapta."""
        selection_indices = self.groups_listbox.curselection()
        if not selection_indices:
            self._clear_details_panel()
            return
        
        selected_index = selection_indices[0]
        self.selected_group_id = self.listbox_map.get(selected_index)

        if not self.selected_group_id: return

        group_name = self.groups_listbox.get(selected_index)
        self.group_name_var.set(group_name)
        self.group_name_entry.config(state="normal")
        self.save_name_button.config(state="normal")
        self.add_participant_button.config(state="normal")
        self.delete_group_button.config(state="normal")
        self.remove_participant_button.config(state="disabled")

        self.participants_listbox.delete(0, tk.END)
        self.participants_map.clear()
        participants = self.db_handler.get_group_participants(self.selected_group_id)
        for index, p in enumerate(participants):
            self.participants_listbox.insert(index, p['display_name'])
            self.participants_map[index] = p['id']

    def _on_participant_select(self, event=None):
        """Activează butonul de ștergere la selecția unui participant."""
        if self.participants_listbox.curselection():
            self.remove_participant_button.config(state="normal")
        else:
            self.remove_participant_button.config(state="disabled")

    def _save_group_name(self):
        """Salvează noul nume pentru grupul selectat."""
        if not self.selected_group_id: return
        new_name = self.group_name_var.get().strip()
        if not new_name:
            messagebox.showwarning("Nume Invalid", "Numele grupului nu poate fi gol.", parent=self)
            return

        if self.db_handler.update_group_name(self.selected_group_id, new_name):
            messagebox.showinfo("Succes", "Numele grupului a fost actualizat.", parent=self)
            self._populate_group_list()
        else:
            messagebox.showerror("Eroare", "Numele grupului nu a putut fi salvat.", parent=self)
            
    def _add_participant(self):
        """Adaugă participanți noi la grupul curent."""
        if not self.selected_group_id: return

        all_users = self.db_handler.fetch_all_dict("SELECT id, username, nume_complet FROM utilizatori WHERE activ = TRUE")
        current_participant_ids = set(self.participants_map.values())
        
        users_to_add = [user for user in all_users if user['id'] not in current_participant_ids]
        
        if not users_to_add:
            messagebox.showinfo("Informație", "Toți utilizatorii sunt deja în acest grup.", parent=self)
            return

        dialog = AddParticipantDialog(self, users_to_add)
        if dialog.result:
            for user_id in dialog.result:
                self.db_handler.add_participant_to_group(self.selected_group_id, user_id)
            # Reîmprospătăm panoul de detalii
            self._on_group_select()

    def _remove_participant(self):
        """Șterge un participant selectat din grupul curent."""
        selection = self.participants_listbox.curselection()
        if not self.selected_group_id or not selection: return

        if len(self.participants_map) <= 2:
            messagebox.showwarning("Acțiune Nepermisă", "Un grup trebuie să aibă cel puțin 2 participanți.", parent=self)
            return

        selected_index = selection[0]
        user_id_to_remove = self.participants_map.get(selected_index)
        
        if user_id_to_remove == self.current_user_id:
            messagebox.showwarning("Acțiune Nepermisă", "Nu vă puteți șterge singur dintr-un grup.", parent=self)
            return
            
        user_name = self.participants_listbox.get(selected_index)
        if messagebox.askyesno("Confirmare", f"Sunteți sigur că doriți să ștergeți participantul '{user_name}' din grup?", parent=self):
            if self.db_handler.remove_participant_from_group(self.selected_group_id, user_id_to_remove):
                self._on_group_select()
            else:
                messagebox.showerror("Eroare", "Participantul nu a putut fi șters.", parent=self)

class GroupManagerDialog(simpledialog.Dialog):
    """Fereastră de dialog pentru administrarea conversațiilor de grup."""
    def __init__(self, parent, db_handler, user_id):
        self.db_handler = db_handler
        self.current_user_id = user_id
        self.selected_group_id = None
        self.listbox_map = {}
        self.participants_map = {}
        super().__init__(parent, "Administrare Grupuri")

    def body(self, master):
        self.master.geometry("700x500")
        main_pane = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Panoul din Stânga
        groups_list_frame = ttk.LabelFrame(main_pane, text="Grupurile Mele", width=250)
        main_pane.add(groups_list_frame, weight=1)
        self.groups_listbox = tk.Listbox(groups_list_frame, exportselection=False)
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        # Panoul din Dreapta
        details_frame = ttk.LabelFrame(main_pane, text="Detalii Grup Selectat")
        main_pane.add(details_frame, weight=2)

        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume:").pack(side=tk.LEFT)
        self.group_name_var = tk.StringVar()
        self.group_name_entry = ttk.Entry(name_frame, textvariable=self.group_name_var, state="disabled")
        self.group_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.save_name_button = ttk.Button(name_frame, text="Salvează Nume", state="disabled", command=self._save_group_name)
        self.save_name_button.pack(side=tk.LEFT)

        participants_frame = ttk.LabelFrame(details_frame, text="Participanți")
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.participants_listbox = tk.Listbox(participants_frame, exportselection=False)
        self.participants_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.participants_listbox.bind("<<ListboxSelect>>", self._on_participant_select)

        participant_actions_frame = ttk.Frame(details_frame)
        participant_actions_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_participant_button = ttk.Button(participant_actions_frame, text="Adaugă Participant", state="disabled", command=self._add_participant)
        self.add_participant_button.pack(side=tk.LEFT)
        self.remove_participant_button = ttk.Button(participant_actions_frame, text="Șterge Participant", state="disabled", command=self._remove_participant)
        self.remove_participant_button.pack(side=tk.LEFT, padx=5)

        group_actions_frame = ttk.Frame(details_frame)
        group_actions_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        self.delete_group_button = ttk.Button(group_actions_frame, text="Șterge Grupul", state="disabled", command=self._delete_group) # Am adăugat command
        self.delete_group_button.pack(side=tk.RIGHT)
        
        self._populate_group_list()
        return self.groups_listbox

    def buttonbox(self):
        box = ttk.Frame(self)
        self.create_new_group_button = ttk.Button(box, text="Creează un Grup Nou...", command=self._create_new_group) # Am adăugat command
        self.create_new_group_button.pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(box, text="Închide", command=self.ok).pack(side=tk.RIGHT, padx=10, pady=10)
        box.pack()

    # ... metodele _populate_group_list, _clear_details_panel, _on_group_select, etc. rămân la fel ca în pasul anterior ...
    # Le includem aici pentru a avea o clasă completă și a evita erorile.

    def _populate_group_list(self):
        current_selection_indices = self.groups_listbox.curselection()
        
        self.groups_listbox.delete(0, tk.END)
        self.listbox_map.clear()
        
        my_groups = self.db_handler.get_groups_for_user(self.current_user_id)
        for index, group in enumerate(my_groups):
            self.groups_listbox.insert(index, group['nume_conversatie'])
            self.listbox_map[index] = group['id']
        
        # Restaurăm selecția dacă mai este validă
        if current_selection_indices:
            try: self.groups_listbox.selection_set(current_selection_indices[0])
            except tk.TclError: pass
        
        self._on_group_select()

    def _clear_details_panel(self):
        self.group_name_var.set("")
        self.participants_listbox.delete(0, tk.END)
        self.group_name_entry.config(state="disabled")
        self.save_name_button.config(state="disabled")
        self.add_participant_button.config(state="disabled")
        self.remove_participant_button.config(state="disabled")
        self.delete_group_button.config(state="disabled")
        self.selected_group_id = None

    def _on_group_select(self, event=None):
        selection_indices = self.groups_listbox.curselection()
        if not selection_indices:
            self._clear_details_panel()
            return
        
        selected_index = selection_indices[0]
        self.selected_group_id = self.listbox_map.get(selected_index)
        if not self.selected_group_id: return

        group_name = self.groups_listbox.get(selected_index)
        self.group_name_var.set(group_name)
        self.group_name_entry.config(state="normal")
        self.save_name_button.config(state="normal")
        self.add_participant_button.config(state="normal")
        self.delete_group_button.config(state="normal")
        self.remove_participant_button.config(state="disabled")

        self.participants_listbox.delete(0, tk.END)
        self.participants_map.clear()
        participants = self.db_handler.get_group_participants(self.selected_group_id)
        for index, p in enumerate(participants):
            self.participants_listbox.insert(index, p['display_name'])
            self.participants_map[index] = p['id']

    def _on_participant_select(self, event=None):
        if not self.participants_listbox.curselection():
            self.remove_participant_button.config(state="disabled")
            return
        
        selected_index = self.participants_listbox.curselection()[0]
        user_id_to_remove = self.participants_map.get(selected_index)

        if user_id_to_remove == self.current_user_id:
            self.remove_participant_button.config(state="disabled")
        else:
            self.remove_participant_button.config(state="normal")

    def _save_group_name(self):
        if not self.selected_group_id: return
        new_name = self.group_name_var.get().strip()
        if not new_name:
            messagebox.showwarning("Nume Invalid", "Numele grupului nu poate fi gol.", parent=self)
            return

        if self.db_handler.update_group_name(self.selected_group_id, new_name):
            messagebox.showinfo("Succes", "Numele grupului a fost actualizat.", parent=self)
            self._populate_group_list()
        else:
            messagebox.showerror("Eroare", "Numele grupului nu a putut fi salvat.", parent=self)
            
    def _add_participant(self):
        if not self.selected_group_id: return
        all_users = self.db_handler.fetch_all_dict("SELECT id, username, nume_complet FROM utilizatori WHERE activ = TRUE")
        current_participant_ids = set(self.participants_map.values())
        users_to_add = [user for user in all_users if user['id'] not in current_participant_ids]
        
        if not users_to_add:
            messagebox.showinfo("Informație", "Toți utilizatorii sunt deja în acest grup.", parent=self)
            return

        dialog = AddParticipantDialog(self, users_to_add)
        if dialog.result:
            for user_id in dialog.result:
                self.db_handler.add_participant_to_group(self.selected_group_id, user_id)
            self._on_group_select()

    def _remove_participant(self):
        selection = self.participants_listbox.curselection()
        if not self.selected_group_id or not selection: return

        if len(self.participants_map) <= 2:
            messagebox.showwarning("Acțiune Nepermisă", "Un grup trebuie să aibă cel puțin 2 participanți.", parent=self)
            return

        selected_index = selection[0]
        user_id_to_remove = self.participants_map.get(selected_index)
        if user_id_to_remove == self.current_user_id:
            messagebox.showwarning("Acțiune Nepermisă", "Nu vă puteți șterge singur dintr-un grup.", parent=self)
            return
            
        user_name = self.participants_listbox.get(selected_index)
        if messagebox.askyesno("Confirmare", f"Sunteți sigur că doriți să ștergeți participantul '{user_name}' din grup?", parent=self):
            if self.db_handler.remove_participant_from_group(self.selected_group_id, user_id_to_remove):
                self._on_group_select()
            else:
                messagebox.showerror("Eroare", "Participantul nu a putut fi șters.", parent=self)

    # --- METODE NOI PENTRU ULTIMELE BUTOANE ---
    def _delete_group(self):
        """Șterge grupul selectat curent."""
        if not self.selected_group_id: return

        group_name = self.group_name_var.get()
        if messagebox.askyesno("Confirmare Ștergere", f"Sunteți absolut sigur că doriți să ștergeți PERMANENT grupul '{group_name}'?\n\nToate mesajele din acest grup vor fi pierdute.", icon='warning', parent=self):
            if self.db_handler.delete_group(self.selected_group_id):
                messagebox.showinfo("Succes", "Grupul a fost șters.", parent=self)
                self._populate_group_list()
            else:
                messagebox.showerror("Eroare", "Grupul nu a putut fi șters.", parent=self)

    def _create_new_group(self):
        """Deschide dialogul de creare a unui grup nou."""
        # Refolosim logica din vechea metodă _on_create_group
        all_users = self.db_handler.fetch_all_dict(
            "SELECT id, username, nume_complet FROM utilizatori WHERE activ = TRUE AND id != %s",
            (self.current_user_id,)
        )
        dialog = CreateGroupDialog(self, all_users)
        
        if dialog.result:
            participant_ids = dialog.result['participant_ids'] + [self.current_user_id]
            group_name = dialog.result['group_name']
            
            cursor = None
            try:
                cursor = self.db_handler.conn.cursor()
                cursor.execute(
                    "INSERT INTO chat_conversatii (nume_conversatie, tip_conversatie) VALUES (%s, 'grup')",
                    (group_name,)
                )
                new_conv_id = cursor.lastrowid
                
                participants_data = [(new_conv_id, user_id) for user_id in participant_ids]
                cursor.executemany(
                    "INSERT INTO chat_participanti (id_conversatie_fk, id_utilizator_fk) VALUES (%s, %s)",
                    participants_data
                )
                
                messagebox.showinfo("Succes", f"Grupul '{group_name}' a fost creat.", parent=self)
                self._populate_group_list()
                
            except Exception as e:
                messagebox.showerror("Eroare Bază de Date", f"Grupul nu a putut fi creat:\n{e}", parent=self)
            finally:
                if cursor:
                    cursor.close()