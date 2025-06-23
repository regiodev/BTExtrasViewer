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
        self.master.geometry("900x600")
        self.master.minsize(600, 400)

        self.active_conversation_id = None
        self.users_list = []
        self.unread_counts = {}
        self.last_polled_message_id = 0 # Va fi setat de _load_initial_state

        self.message_queue = queue.Queue()
        self.is_running = True

        self._setup_ui()
        
        # Logica de pornire, în ordinea corectă
        self._load_initial_state() # 1. Stabilim starea de la pornire
        self._populate_user_list() # 2. Afișăm corect interfața
        
        # 3. Pornim thread-urile pentru viitor
        self.polling_thread = threading.Thread(target=self._poll_for_new_messages, daemon=True)
        self.polling_thread.start()
        self.master.after(100, self._process_message_queue)
        self._schedule_user_list_refresh()

        # --- Creare Tooltip pentru Timestamp ---
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.withdraw() # Îl ascundem initial
        self.tooltip.overrideredirect(True) # Fără margini de fereastră
        self.tooltip_label = ttk.Label(self.tooltip, text="", background="#FFFFE0", relief="solid", borderwidth=1, padding=2)
        self.tooltip_label.pack()

        self.line_to_message_map = {} # Hartă: 'linie.coloană' -> msg_data

    def _schedule_user_list_refresh(self):
        """Reîmprospătează periodic lista de utilizatori pentru a actualiza statusul."""
        if self.is_running:
            self._populate_user_list()
            self.master.after(20000, self._schedule_user_list_refresh) # Reîmprospătare la 20 secunde

    def _fetch_and_process_new_messages(self, cursor, polling_conn, my_conv_ids):
        """Metodă helper care caută mesaje noi ('trimis') și le marchează ca 'livrat'."""
        if not my_conv_ids:
            return

        placeholders = ','.join(['%s'] * len(my_conv_ids))
        sql_select = f"""
            SELECT m.id, m.id_conversatie_fk, m.id_expeditor_fk, m.continut_mesaj, m.timestamp, m.stare,
                   COALESCE(u.nume_complet, u.username) AS expeditor
            FROM chat_mesaje m JOIN utilizatori u ON m.id_expeditor_fk = u.id
            WHERE m.id_conversatie_fk IN ({placeholders})
              AND m.id_expeditor_fk != %s
              AND m.stare = 'trimis'
        """
        params = my_conv_ids + (self.current_user['id'],)
        cursor.execute(sql_select, params)
        new_messages = cursor.fetchall()

        if new_messages:
            message_ids_to_update = [msg['id'] for msg in new_messages]
            
            update_placeholders = ','.join(['%s'] * len(message_ids_to_update))
            cursor.execute(
                f"UPDATE chat_mesaje SET stare = 'livrat' WHERE id IN ({update_placeholders})",
                tuple(message_ids_to_update)
            )
            polling_conn.commit()

            for msg in new_messages:
                self.message_queue.put(msg)

    def _poll_for_new_messages(self):
        """Rulează în fundal și caută DOAR mesaje noi, cu ID mai mare decât cel de la pornire."""
        polling_conn = None
        try:
            polling_conn = mysql.connector.connect(**self.db_creds)
            polling_conn.autocommit = True
            
            while self.is_running:
                try:
                    # Heartbeat
                    cursor = polling_conn.cursor(dictionary=True)
                    cursor.execute(
                        "UPDATE utilizatori SET last_seen = CURRENT_TIMESTAMP WHERE id = %s",
                        (self.current_user['id'],)
                    )
                    
                    # Căutăm DOAR mesaje cu ID mai mare, apărute în timpul sesiunii
                    sql_select = """
                        SELECT m.id, m.id_conversatie_fk, m.id_expeditor_fk, m.continut_mesaj, m.timestamp, m.stare,
                               COALESCE(u.nume_complet, u.username) AS expeditor
                        FROM chat_mesaje m JOIN utilizatori u ON m.id_expeditor_fk = u.id
                        WHERE m.id > %s AND m.id_expeditor_fk != %s
                    """
                    cursor.execute(sql_select, (self.last_polled_message_id, self.current_user['id']))
                    new_messages = cursor.fetchall()

                    if new_messages:
                        # Actualizăm ultimul ID văzut cu cel mai recent mesaj
                        self.last_polled_message_id = new_messages[-1]['id']
                        
                        # Nu mai este nevoie să schimbăm starea în 'livrat',
                        # deoarece logica ID > last_id previne reprocesarea.
                        
                        for msg in new_messages:
                            # Verificăm dacă mesajul este pentru una din conversațiile noastre
                            # (necesar deoarece WHERE nu mai filtrează după conv_id)
                             conv_ids_raw = self.db_handler.fetch_all_dict("SELECT id_conversatie_fk FROM chat_participanti WHERE id_utilizator_fk = %s", (self.current_user['id'],))
                             my_conv_ids = [item['id_conversatie_fk'] for item in conv_ids_raw]
                             if msg['id_conversatie_fk'] in my_conv_ids:
                                self.message_queue.put(msg)

                except mysql.connector.Error as db_err:
                    print(f"Eroare DB în bucla de polling: {db_err}.")
                    time.sleep(10)
                    if not (polling_conn and polling_conn.is_connected()):
                        polling_conn = mysql.connector.connect(**self.db_creds)
                        polling_conn.autocommit = True
                
                time.sleep(3)
        
        except Exception as e:
            print(f"EROARE CRITICĂ în thread-ul de polling, se va opri: {e}")
        finally:
            if polling_conn and polling_conn.is_connected():
                polling_conn.close()

    def _process_message_queue(self):
        """Procesează mesajele din coadă și le afișează sau le marchează ca necitite."""
        updated_unread_list = False
        try:
            while not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                
                # Verificăm dacă mesajul aparține conversației active
                if msg['id_conversatie_fk'] == self.active_conversation_id:
                    self._display_message(msg)
                else:
                    # Mesajul este pentru altă conversație, deci este necitit
                    sender_id = msg['id_expeditor_fk']
                    # Incrementăm contorul pentru expeditor
                    self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1
                    updated_unread_list = True

        except queue.Empty:
            pass
        finally:
            # Dacă am actualizat vreun contor, reîmprospătăm lista de utilizatori
            if updated_unread_list:
                self._populate_user_list()
            
            if self.is_running:
                self.master.after(200, self._process_message_queue)

    def _display_message(self, msg_data):
        """Afișează doar conținutul mesajului și populează harta pentru tooltip."""
        self.message_display.config(state="normal")
        
        is_my_message = msg_data['id_expeditor_fk'] == self.current_user['id']
        tag = "sent" if is_my_message else "received"
        
        # Obținem indexul de start înainte de a insera textul
        start_index = self.message_display.index(tk.END)
        
        # Inserăm doar conținutul mesajului
        self.message_display.insert(tk.END, msg_data['continut_mesaj'], tag)
        
        # Adăugăm indicatorul de citire
        if is_my_message and msg_data['stare'] == 'citit':
            self.message_display.insert(tk.END, " ✓", "read_receipt")
        
        self.message_display.insert(tk.END, "\n") # Adăugăm o linie nouă la final
        
        # Obținem indexul de final
        end_index = self.message_display.index(tk.END)

        # Adăugăm intrări în hartă pentru fiecare linie pe care o ocupă mesajul
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

        # --- Panoul din Stânga: Lista de Utilizatori ---
        users_frame = ttk.LabelFrame(main_pane, text="Utilizatori", width=250)
        main_pane.add(users_frame, weight=1)

        self.user_tree = ttk.Treeview(users_frame, columns=("username", "status"), show="headings", selectmode="browse")
        self.user_tree.heading("username", text="Utilizator")
        self.user_tree.heading("status", text="Status")
        self.user_tree.column("username", width=150)
        self.user_tree.column("status", width=50, anchor="center")
        self.user_tree.pack(fill=tk.BOTH, expand=True)
        self.user_tree.bind("<<TreeviewSelect>>", self._on_user_selected)

        # Configurăm stilurile pentru lista de utilizatori
        self.user_tree.tag_configure("online", foreground="green")
        self.user_tree.tag_configure("offline", foreground="gray")
        self.user_tree.tag_configure("unread", font=("Segoe UI", 9, "bold"))
        
        # --- Panoul din Dreapta: Conversația Activă ---
        chat_frame = ttk.Frame(main_pane)
        main_pane.add(chat_frame, weight=3)
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        # Zona de afișare a mesajelor
        self.message_display = scrolledtext.ScrolledText(chat_frame, state="disabled", wrap=tk.WORD, font=("Segoe UI", 10))
        self.message_display.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.message_display.bind("<Motion>", self._on_mouse_move_on_message)
        self.message_display.bind("<Leave>", self._hide_tooltip)
        
        # --- Configurare tag-uri pentru fereastra de mesaje ---
        self.message_display.tag_configure("read_receipt", foreground="blue", font=("Segoe UI", 8))
        
        # Adăugam și tag-uri pentru aliniere si background color
        self.message_display.tag_configure("sent", justify="right", background="#dcf8c6", wrap=tk.WORD)
        self.message_display.tag_configure("received", justify="left", background="#f0f0f0", wrap=tk.WORD)
        self.message_display.tag_configure(
            "date_separator", 
            justify="center", 
            foreground="gray", 
            font=("Segoe UI", 8, "italic")
        )
        
        # Zona de introducere a mesajelor
        self.message_input = ttk.Entry(chat_frame, font=("Segoe UI", 10))
        self.message_input.grid(row=1, column=0, sticky="ew", padx=(5, 0), pady=5)
        
        self.send_button = ttk.Button(chat_frame, text="Trimite")
        self.send_button.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=5)
        self.send_button.config(command=self._send_message)
        self.message_input.bind("<Return>", self._send_message)

        # --- Bara de Stare (Status Bar) ---
        status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN, padding=(5, 3))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        # Eticheta pentru identificare utilizator
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

    def _on_user_selected(self, event=None):
        """Invocată la selecția unui utilizator. Găsește/creează conversația și încarcă istoricul."""
        selection = self.user_tree.selection()
        if not selection:
            return
        
        partner_id = int(selection[0])

        # Resetăm contorul de mesaje necitite pentru această conversație
        if partner_id in self.unread_counts:
            del self.unread_counts[partner_id]
            self._populate_user_list() # Reîmprospătăm lista pentru a elimina contorul vizual

        new_conversation_id = self._get_or_create_conversation(partner_id)
        
        if self.active_conversation_id != new_conversation_id:
            self.active_conversation_id = new_conversation_id
        
        if self.active_conversation_id:
            partner_username = self.user_tree.item(selection[0], "values")[0]
            self.master.title(f"BTExtras Chat - Conversație cu {partner_username}")
            
            # Acum, doar apelăm încărcarea istoricului.
            # Logica de marcare ca 'citit' va fi în interiorul acestei metode.
            self._load_conversation_history()

    def _mark_messages_as_read_in_db(self, message_ids_to_update):
        """
        O metodă complet izolată care deschide o conexiune nouă doar pentru a
        marca o listă de ID-uri de mesaje ca fiind 'citit'.
        """
        if not message_ids_to_update:
            return

        temp_conn = None
        try:
            temp_conn = mysql.connector.connect(**self.db_creds)
            cursor = temp_conn.cursor()
            
            placeholders = ','.join(['%s'] * len(message_ids_to_update))
            sql_update = f"UPDATE chat_mesaje SET stare = 'citit' WHERE id IN ({placeholders})"
            
            cursor.execute(sql_update, tuple(message_ids_to_update))
            temp_conn.commit()
            cursor.close()

        except Exception as e:
            print(f"EROARE la marcarea mesajelor ca citite (conexiune izolată): {e}")
            if temp_conn and temp_conn.is_connected():
                temp_conn.rollback()
        finally:
            if temp_conn and temp_conn.is_connected():
                temp_conn.close()

    def _get_or_create_conversation(self, partner_id):
        """Găsește o conversație 1-la-1 existentă sau creează una nouă."""
        my_id = self.current_user['id']
        
        # SQL pentru a găsi o conversație 1-la-1 între 2 useri
        sql_find = """
            SELECT p1.id_conversatie_fk FROM chat_participanti p1
            JOIN chat_participanti p2 ON p1.id_conversatie_fk = p2.id_conversatie_fk
            JOIN chat_conversatii c ON p1.id_conversatie_fk = c.id
            WHERE p1.id_utilizator_fk = %s AND p2.id_utilizator_fk = %s AND c.tip_conversatie = 'unu_la_unu'
        """
        conversation_id = self.db_handler.fetch_scalar(sql_find, (my_id, partner_id))

        if conversation_id:
            return conversation_id
        else:
            # Creare conversație nouă
            cursor = None # Inițializăm cursorul
            try:
                # Creăm un cursor standard, deoarece problema a fost rezolvată în db_handler
                cursor = self.db_handler.conn.cursor()
                
                # 1. Creează conversația
                cursor.execute("INSERT INTO chat_conversatii (tip_conversatie) VALUES ('unu_la_unu')")
                new_conv_id = cursor.lastrowid
                
                # 2. Adaugă ambii participanți
                participants = [(new_conv_id, my_id), (new_conv_id, partner_id)]
                cursor.executemany("INSERT INTO chat_participanti (id_conversatie_fk, id_utilizator_fk) VALUES (%s, %s)", participants)
                
                return new_conv_id
            except Exception as e:
                messagebox.showerror("Eroare Creare Conversație", str(e))
                if self.db_handler.conn.is_connected():
                    self.db_handler.conn.rollback()
                return None
            finally:
                # Ne asigurăm că închidem cursorul
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
        """Încarcă istoricul, afișează mesajele și APELEAZĂ metoda izolată de marcare ca 'citit'."""
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
            return

        ids_to_mark_as_read = [
            msg['id'] for msg in messages 
            if msg['id_expeditor_fk'] != self.current_user['id'] and msg['stare'] != 'citit'
        ]

        if ids_to_mark_as_read:
            self._mark_messages_as_read_in_db(ids_to_mark_as_read)
        
        last_message_date = None
        for msg in messages:
            current_message_date = msg['timestamp'].date()
            if current_message_date != last_message_date:
                date_str = current_message_date.strftime('%d %B %Y')
                self.message_display.insert(tk.END, f"\n{date_str}\n", "date_separator")
                last_message_date = current_message_date
            
            if msg['id'] in ids_to_mark_as_read:
                msg['stare'] = 'citit'
            
            self._display_message(msg)

        self.message_display.config(state="disabled")

    def _populate_user_list(self):
        """Populează lista de utilizatori și determină statusul lor pe baza 'last_seen'."""
        try:

            # Preluăm și 'last_seen'
            self.users_list = self.db_handler.fetch_all_dict(
                "SELECT id, username, nume_complet, last_seen FROM utilizatori WHERE activ = TRUE AND id != %s ORDER BY nume_complet ASC",
                (self.current_user['id'],)
            )

            # Salvăm selecția curentă pentru a o restaura
            selected_item = self.user_tree.selection()

            # Ștergem intrările vechi
            for item in self.user_tree.get_children():
                self.user_tree.delete(item)

            if self.users_list:
                for user in self.users_list:
                    display_name = user.get('nume_complet') or user['username']
                    
                    # Verificăm dacă există mesaje necitite de la acest utilizator
                    unread_count = self.unread_counts.get(user['id'], 0)
                    if unread_count > 0:
                        display_name = f"{display_name} ({unread_count})"

                    # Determinăm statusul
                    status = "Offline"
                    if user['last_seen']:
                        # Considerăm un utilizator online dacă a fost activ în ultimele 15 secunde
                        if datetime.now() - user['last_seen'] < timedelta(seconds=15):
                            status = "Online"
                    
                    # Adăugăm tag-urile pentru stilizare
                    tags_to_apply = []
                    tags_to_apply.append("online" if status == "Online" else "offline")
                    if unread_count > 0:
                        tags_to_apply.append("unread")

                    self.user_tree.insert("", "end", iid=user['id'], values=(display_name, status), tags=tuple(tags_to_apply))

            # Restaurăm selecția, dacă mai este validă
            if selected_item and self.user_tree.exists(selected_item[0]):
                self.user_tree.selection_set(selected_item[0])

        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut încărca lista de utilizatori: {e}")

    def on_closing(self):
        """Gestionează închiderea ferestrei și oprește thread-ul de polling."""
        print("Aplicația de chat se închide, se oprește polling-ul...")
        self.is_running = False
        self.master.destroy()