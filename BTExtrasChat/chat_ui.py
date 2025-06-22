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
        self.db_handler = db_handler # Folosit de thread-ul principal (UI)
        self.current_user = user_data
        self.db_creds = db_creds # Salvăm datele de conectare pentru noul thread

        self.master.title("BTExtras Chat")
        self.master.geometry("900x600")
        self.master.minsize(600, 400)

        self.active_conversation_id = None
        self.last_message_id = 0
        self.users_list = []
        self.unread_counts = {} # Dicționar pentru a stoca mesajele necitite {user_id: count}

        # Coadă pentru comunicare sigură între thread-uri
        self.message_queue = queue.Queue()
        self.is_running = True # Flag pentru a opri thread-ul la închidere

        self._setup_ui()
        self._populate_user_list()

        # Pornim thread-ul de polling
        self.polling_thread = threading.Thread(target=self._poll_for_new_messages, daemon=True)
        self.polling_thread.start()

        # Pornim verificarea periodică a cozii de mesaje
        self.master.after(100, self._process_message_queue)
        self._schedule_user_list_refresh()

    def _schedule_user_list_refresh(self):
        """Reîmprospătează periodic lista de utilizatori pentru a actualiza statusul."""
        if self.is_running:
            self._populate_user_list()
            self.master.after(20000, self._schedule_user_list_refresh) # Reîmprospătare la 20 secunde

    def _poll_for_new_messages(self):
        """Rulează în fundal, pe propria conexiune la DB. Caută mesaje noi în TOATE conversațiile relevante."""
        polling_conn = None
        try:
            polling_conn = mysql.connector.connect(**self.db_creds)
            
            # Preluăm o singură dată ID-urile tuturor conversațiilor la care participă utilizatorul
            conv_cursor = polling_conn.cursor(buffered=True)
            conv_cursor.execute("SELECT id_conversatie_fk FROM chat_participanti WHERE id_utilizator_fk = %s", (self.current_user['id'],))
            my_conv_ids = tuple(item[0] for item in conv_cursor.fetchall())
            conv_cursor.close()

            # Dacă utilizatorul nu are nicio conversație, nu are rost să continuăm
            if not my_conv_ids:
                print("Utilizatorul nu participă la nicio conversație. Thread-ul de polling se oprește.")
                return

            update_cursor = polling_conn.cursor()
            while self.is_running:
                try:
                    # 1. Heartbeat: Actualizăm statusul nostru
                    update_cursor.execute(
                        "UPDATE utilizatori SET last_seen = CURRENT_TIMESTAMP WHERE id = %s",
                        (self.current_user['id'],)
                    )
                    polling_conn.commit()

                    # 2. Căutare mesaje noi în TOATE conversațiile mele
                    placeholders = ','.join(['%s'] * len(my_conv_ids))
                    sql_query = f"""
                        SELECT m.id, m.id_conversatie_fk, m.id_expeditor_fk, m.continut_mesaj, m.timestamp, 
                               COALESCE(u.nume_complet, u.username) AS expeditor
                        FROM chat_mesaje m
                        JOIN utilizatori u ON m.id_expeditor_fk = u.id
                        WHERE m.id_conversatie_fk IN ({placeholders}) 
                          AND m.id > %s 
                          AND m.id_expeditor_fk != %s
                        ORDER BY m.id ASC
                    """
                    params = my_conv_ids + (self.last_message_id, self.current_user['id'])
                    
                    fetch_cursor = polling_conn.cursor(dictionary=True, buffered=True)
                    fetch_cursor.execute(sql_query, params)
                    new_messages = fetch_cursor.fetchall()
                    fetch_cursor.close()
                    
                    if new_messages:
                        for msg in new_messages:
                            self.message_queue.put(msg)
                        self.last_message_id = new_messages[-1]['id']
                
                except mysql.connector.Error as db_err:
                    print(f"Eroare DB în thread-ul de polling: {db_err}. Se reîncearcă.")
                    time.sleep(10)
                    # Încercăm să recreăm conexiunea în caz de problemă
                    if polling_conn and polling_conn.is_connected():
                        polling_conn.close()
                    polling_conn = mysql.connector.connect(**self.db_creds)
                    update_cursor = polling_conn.cursor()

                except Exception as e:
                    print(f"Eroare în thread-ul de polling: {e}")
                
                time.sleep(3) # Reducem intervalul înapoi la 3 secunde pentru reactivitate mai bună
        
        finally:
            if polling_conn and polling_conn.is_connected():
                polling_conn.close()
                print("Conexiunea thread-ului de polling a fost închisă.") 

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
        """Funcție helper pentru a formata și afișa un singur mesaj."""
        self.message_display.config(state="normal")
        timestamp_str = msg_data['timestamp'].strftime('%d-%m-%Y %H:%M')
        
        # Stabilim tag-ul pentru aliniere și culoare
        tag = "sent" if msg_data['expeditor'] == self.current_user['username'] else "received"
        
        formatted_message = f"[{timestamp_str}] {msg_data['expeditor']}: {msg_data['continut_mesaj']}\n"
        self.message_display.insert(tk.END, formatted_message, tag)
        
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
        self.user_tree.tag_configure("online", foreground="green")
        self.user_tree.tag_configure("offline", foreground="gray")
        self.user_tree.tag_configure("unread", font=("Segoe UI", 9, "bold"))

        # Vom adăuga un eveniment de click simplu aici
        self.user_tree.bind("<<TreeviewSelect>>", self._on_user_selected)

        # --- Panoul din Dreapta: Conversația Activă ---
        chat_frame = ttk.Frame(main_pane)
        main_pane.add(chat_frame, weight=3)
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        # Zona de afișare a mesajelor 
        self.message_display = scrolledtext.ScrolledText(chat_frame, state="disabled", wrap=tk.WORD, font=("Segoe UI", 10))
        self.message_display.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # Zona de introducere a mesajelor 
        self.message_input = ttk.Entry(chat_frame, font=("Segoe UI", 10))
        self.message_input.grid(row=1, column=0, sticky="ew", padx=(5, 0), pady=5)
        
        self.send_button = ttk.Button(chat_frame, text="Trimite")
        self.send_button.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=5)

        self.send_button.config(command=self._send_message)
        self.message_input.bind("<Return>", self._send_message) # Permite trimiterea cu tasta Enter
        status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN, padding=(5, 3))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        # Eticheta pentru identificare utilizator
        # Folosim numele complet, dacă există; altfel, revenim la username
        display_name = self.current_user.get('nume_complet') or self.current_user['username']
        
        self.user_identity_label = ttk.Label(
            status_bar_frame,
            text=f"Conectat ca: {display_name}",
            font=("Segoe UI", 9, "bold")
        )
        self.user_identity_label.pack(side=tk.LEFT)

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
        """Invocată la selecția unui utilizator. Inițiază o conversație 1-la-1."""
        selection = self.user_tree.selection()
        if not selection:
            return
        
        partner_id = int(selection[0])

        # Resetăm contorul de mesaje necitite pentru această conversație
        if partner_id in self.unread_counts:
            del self.unread_counts[partner_id]
            self._populate_user_list() # Reîmprospătăm lista pentru a elimina contorul vizual

        my_id = self.current_user['id']

        # Găsește sau creează conversația
        new_conversation_id = self._get_or_create_conversation(partner_id)

        # Verificăm dacă s-a schimbat conversația
        if self.active_conversation_id != new_conversation_id:
            self.active_conversation_id = new_conversation_id
            self.last_message_id = 0 # Resetăm ID-ul pentru noua conversație

        # Încarcă istoricul mesajelor
        if self.active_conversation_id:
            partner_username = self.user_tree.item(selection[0], "values")[0]
            self.master.title(f"BTExtras Chat - Conversație cu {partner_username}") # Actualizăm titlul ferestrei
            self._load_conversation_history()

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
                
                self.db_handler.conn.commit()
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
            
    def _load_conversation_history(self):
        """Încarcă și afișează mesajele pentru conversația activă."""
        self.message_display.config(state="normal")
        self.message_display.delete("1.0", tk.END)

        if not self.active_conversation_id:
            self.message_display.config(state="disabled")
            return

        messages = self.db_handler.fetch_all_dict(
            """
            SELECT m.id, m.continut_mesaj, m.timestamp, 
                   COALESCE(u.nume_complet, u.username) AS expeditor
            FROM chat_mesaje m
            JOIN utilizatori u ON m.id_expeditor_fk = u.id
            WHERE m.id_conversatie_fk = %s ORDER BY m.timestamp ASC
            """, (self.active_conversation_id,)
        )

        if messages:
            for msg in messages:
                self._display_message(msg)
            # Setăm ID-ul ultimului mesaj pentru ca polling-ul să știe de unde să continue
            self.last_message_id = messages[-1]['id']
        else:
            self.last_message_id = 0 # Niciun mesaj în conversație

        self.message_display.config(state="disabled")

    def _populate_user_list(self):
        """Populează lista de utilizatori și determină statusul lor pe baza 'last_seen'."""
        try:
            # Forțăm finalizarea tranzacției curente pentru a vedea cele mai noi date
            self.db_handler.conn.commit()

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