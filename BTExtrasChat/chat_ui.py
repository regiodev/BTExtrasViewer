# BTExtrasChat/chat_ui.py

import tkinter as tk
from tkinter import ttk, simpledialog, scrolledtext, messagebox
import threading
import queue
import time
from datetime import datetime, timedelta
import mysql.connector
import os
import socket
import sys
from common.app_constants import CHAT_COMMAND_PORT

# Am eliminat importurile pentru pystray și PIL

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
        self.conversation_details = {}
        # Harta pentru a lega indexul din listbox de ID-ul conversației
        self.listbox_map = {}
        # Atributul a fost mutat aici pentru a fi disponibil de la început
        self.line_to_message_map = {}
        
        self.message_queue = queue.Queue()
        self.is_running = True
        
        self._setup_ui()
        self._load_initial_state()
        self._populate_conversation_list()
        
        # Pornim thread-urile
        self.polling_thread = threading.Thread(target=self._poll_for_new_messages, daemon=True)
        self.polling_thread.start()
        self.master.after(100, self._process_message_queue)
        self._schedule_user_list_refresh()
        self.command_server_thread = threading.Thread(target=self._listen_for_commands, daemon=True)
        self.command_server_thread.start()

        # Creare Tooltip pentru Timestamp
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tooltip_label = ttk.Label(self.tooltip, text="", background="#FFFFE0", relief="solid", borderwidth=1, padding=2)
        self.tooltip_label.pack()

    def _show_window(self):
        """Readuce fereastra în prim-plan, dându-i focus."""
        def bring_to_front():
            self.master.deiconify()
            self.master.lift()
            self.master.attributes('-topmost', 1)
            self.master.after(100, lambda: self.master.attributes('-topmost', 0))
            self.master.focus_force()

        self.master.after(0, bring_to_front)

    def _quit_application(self):
        """Oprește toate procesele și programează închiderea aplicației."""
        self.is_running = False
        self.master.after(100, self.master.destroy)

    def on_closing(self):
        """La apăsarea pe 'X', fereastra doar se ascunde."""
        self.master.withdraw()

    def _listen_for_commands(self):
        """Ascultă pentru comenzi externe (ex: de la SessionManager)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('127.0.0.1', CHAT_COMMAND_PORT))
                server_socket.listen()
                print(f"INFO: Serverul de comenzi al Chat-ului ascultă pe portul {CHAT_COMMAND_PORT}.")

                while self.is_running:
                    try:
                        server_socket.settimeout(1.0)
                        conn, addr = server_socket.accept()
                        with conn:
                            data = conn.recv(1024)
                            if data == b'SHOW_WINDOW':
                                self.message_queue.put('__SHOW_WINDOW__')
                    except socket.timeout:
                        continue
        except Exception as e:
            print(f"AVERTISMENT/EROARE în serverul de comenzi al Chat-ului: {e}")

    def _schedule_user_list_refresh(self):
        """Reîmprospătează periodic lista de utilizatori pentru a actualiza statusul."""
        if self.is_running:
            self._populate_conversation_list()
            self.master.after(20000, self._schedule_user_list_refresh)

    def _on_manage_groups(self):
        """Deschide dialogul de administrare a grupurilor."""
        dialog = GroupManagerDialog(self.master, self.db_handler, self.current_user['id'])
        self._populate_conversation_list()

    def _poll_for_new_messages(self):
        """Rulează în fundal, caută mesaje noi și trimite heartbeat."""
        polling_conn = None
        try:
            polling_conn = mysql.connector.connect(**self.db_creds)
            
            while self.is_running:
                cursor = None
                try:
                    cursor = polling_conn.cursor(dictionary=True)
                    cursor.execute(
                        "UPDATE utilizatori SET last_seen = CURRENT_TIMESTAMP WHERE id = %s",
                        (self.current_user['id'],)
                    )
                    polling_conn.commit()

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
        """Procesează mesajele și comenzile speciale din coadă."""
        updated_unread_list = False
        try:
            while not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                
                if isinstance(msg, str) and msg == '__SHOW_WINDOW__':
                    print("INFO (Chat): Comanda de afișare fereastră primită în coadă.")
                    self._show_window()
                elif isinstance(msg, dict):
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
        
        active_conv_details = self.conversation_details.get(self.active_conversation_id)
        
        prefix = ""
        if active_conv_details and active_conv_details['tip_conversatie'] == 'grup' and not is_my_message:
            sender_name = (msg_data['expeditor'] or "Utilizator").split(' ')[0]
            prefix = f"{sender_name}:\n"
        
        start_index = self.message_display.index(tk.END)
        
        formatted_message = f"{prefix}{msg_data['continut_mesaj']}"
        self.message_display.insert(tk.END, formatted_message, tag)
        
        if is_my_message and msg_data['stare'] == 'citit':
            self.message_display.insert(tk.END, " ✓", "read_receipt")
        
        self.message_display.insert(tk.END, "\n\n", "line_spacing")
        
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

        # --- BLOC MODIFICAT PENTRU LISTBOX ---
        users_frame = ttk.LabelFrame(main_pane, text="Conversații", width=250)
        main_pane.add(users_frame, weight=1)

        # Creăm un Frame pentru Listbox și Scrollbar
        listbox_container = ttk.Frame(users_frame)
        listbox_container.pack(fill=tk.BOTH, expand=True)

        self.conversation_listbox = tk.Listbox(
            listbox_container, 
            selectmode=tk.SINGLE, 
            exportselection=False,
            font=("Segoe UI", 10),
            activestyle='none' # Elimină sublinierea la hover
        )
        
        # Creăm un scrollbar și îl legăm de Listbox
        scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL, command=self.conversation_listbox.yview)
        self.conversation_listbox.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conversation_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Legăm evenimentul de selecție
        self.conversation_listbox.bind("<<ListboxSelect>>", self._on_conversation_selected)
        # --- SFÂRȘIT BLOC MODIFICAT ---
        
        action_buttons_frame = ttk.Frame(users_frame)
        action_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0), padx=2)
        action_buttons_frame.columnconfigure((0, 1), weight=1)

        new_chat_button = ttk.Button(action_buttons_frame, text="Utilizatori", command=self._on_new_conversation)
        new_chat_button.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        manage_groups_button = ttk.Button(action_buttons_frame, text="Grupuri", command=self._on_manage_groups)
        manage_groups_button.grid(row=0, column=1, sticky="ew", padx=(2, 0))
        
        chat_frame = ttk.Frame(main_pane)
        main_pane.add(chat_frame, weight=10)
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        self.message_display = scrolledtext.ScrolledText(chat_frame, state="disabled", wrap=tk.WORD, font=("Segoe UI", 10))
        self.message_display.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.message_display.bind("<Motion>", self._on_mouse_move_on_message)
        self.message_display.bind("<Leave>", self._hide_tooltip)
        
        self.message_display.tag_configure("read_receipt", foreground="blue", font=("Segoe UI", 8))
        self.message_display.tag_configure("sent", justify="right", foreground="#006400")
        self.message_display.tag_configure("received", justify="left", foreground="#00008B")
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
        try:
            index = self.message_display.index(f"@{event.x},{event.y}")
            line_start_index = index.split('.')[0]
            msg_data = self.line_to_message_map.get(line_start_index)

            if msg_data:
                timestamp_str = msg_data['timestamp'].strftime('%H:%M')
                self._show_tooltip(timestamp_str, event.x_root + 10, event.y_root + 10)
            else:
                self._hide_tooltip()
        except tk.TclError:
            self._hide_tooltip()

    def _show_tooltip(self, text, x, y):
        self.tooltip_label.config(text=text)
        self.tooltip.geometry(f"+{x}+{y}")
        self.tooltip.deiconify()

    def _hide_tooltip(self, event=None):
        self.tooltip.withdraw()

    def _send_message(self, event=None):
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
                self._load_conversation_history()
            else:
                messagebox.showwarning("Eroare", "Mesajul nu a putut fi trimis.")
        except Exception as e:
            messagebox.showerror("Eroare Trimitere", str(e))

    def _on_conversation_selected(self, event=None):
        selection_indices = self.conversation_listbox.curselection()
        if not selection_indices:
            return

        selected_index = selection_indices[0]
        selected_conv_id = self.listbox_map.get(selected_index)
            
        if not selected_conv_id or self.active_conversation_id == selected_conv_id:
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
        if not message_ids_to_update:
            return
        
        try:
            cursor = self.db_handler.conn.cursor()
            placeholders = ','.join(['%s'] * len(message_ids_to_update))
            sql_update = f"UPDATE chat_mesaje SET stare = 'citit' WHERE id IN ({placeholders})"
            cursor.execute(sql_update, tuple(message_ids_to_update))
            cursor.close()
        except Exception as e:
            print(f"EROARE la marcarea mesajelor ca citite: {e}")

    def _get_or_create_conversation(self, partner_id):
        my_id = self.current_user['id']
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
        print("INFO: Se încarcă starea inițială (mesaje necitite)...")
        self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
        print(f"INFO: Stare inițială încărcată. Contoare: {self.unread_counts}.")

    def _load_conversation_history(self):
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
        
        ids_to_mark_as_read = [
            msg['id'] for msg in messages 
            if msg['id_expeditor_fk'] != self.current_user['id'] and msg['stare'] != 'citit'
        ]

        if ids_to_mark_as_read:
            self._mark_messages_as_read_in_db(ids_to_mark_as_read)
        
        self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
        self._populate_conversation_list()
        
        if not messages:
            self.message_display.config(state="disabled")
            return

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

    def _populate_conversation_list(self):
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
            
            current_selection_indices = self.conversation_listbox.curselection()
            
            self.conversation_listbox.delete(0, tk.END)
            self.listbox_map.clear()
            self.conversation_details.clear()

            if conversations:
                for index, conv in enumerate(conversations):
                    self.conversation_details[conv['conversation_id']] = conv
                    
                    display_name = conv['display_name'] or "Conversație"
                    status_symbol = ""
                    is_online = False
                    
                    if conv['tip_conversatie'] == 'unu_la_unu':
                        is_online = conv['last_seen'] and (datetime.now() - conv['last_seen'] < timedelta(seconds=15))
                        status_symbol = "✓" if is_online else "✗"
                    else:
                        status_symbol = "●"

                    unread_count = 0
                    if conv['tip_conversatie'] == 'grup':
                        group_unread_messages = self.db_handler.fetch_scalar("""
                            SELECT COUNT(*) FROM chat_mesaje
                            WHERE id_conversatie_fk = %s AND id_expeditor_fk != %s AND stare != 'citit'
                        """, (conv['conversation_id'], my_id))
                        unread_count = group_unread_messages or 0
                    else:
                        partner_id = conv.get('partner_id')
                        if partner_id:
                            unread_count = self.unread_counts.get(partner_id, 0)
                    
                    # --- BLOC MODIFICAT PENTRU A FOLOSI ASTERISC ---
                    unread_prefix = ""
                    if unread_count > 0:
                        display_name = f"{display_name} ({unread_count})"
                        unread_prefix = "* " # Adăugăm asteriscul
                    
                    final_display_text = f" {status_symbol} {unread_prefix}{display_name}"
                    self.conversation_listbox.insert(index, final_display_text)
                    self.listbox_map[index] = conv['conversation_id']
                    
                    # Aplicăm stilurile (doar culoare, fără font)
                    color_to_apply = 'black'
                    if conv['tip_conversatie'] == 'grup':
                        color_to_apply = '#0000AA' # Albastru pentru grupuri
                    elif is_online:
                        color_to_apply = 'green' # Verde pentru online
                    else:
                        color_to_apply = '#A93226' # Roșu pentru offline
                        
                    self.conversation_listbox.itemconfig(index, {'fg': color_to_apply})
                    # --- SFÂRȘIT BLOC MODIFICAT ---

            if current_selection_indices:
                self.conversation_listbox.selection_set(current_selection_indices[0])
            else:
                if self.conversation_listbox.size() > 0:
                    self.conversation_listbox.selection_set(0)
                    self._on_conversation_selected(event=None)

        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut încărca lista de conversații: {e}")

    def _on_new_conversation(self):
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
            conv_id = self._get_or_create_conversation(partner_id)
            if conv_id:
                # Reîmprospătăm lista de conversații
                self._populate_conversation_list()
                
                # Căutăm indexul listbox-ului care corespunde noului ID de conversație
                target_index = None
                # Inversăm harta pentru a găsi cheia (index) după valoare (conv_id)
                for index, c_id in self.listbox_map.items():
                    if c_id == conv_id:
                        target_index = index
                        break
                
                # Dacă am găsit indexul, selectăm elementul în Listbox
                if target_index is not None:
                    self.conversation_listbox.selection_set(target_index)
                    self.conversation_listbox.see(target_index) # Asigură vizibilitatea
                    # Apelăm manual handler-ul pentru a încărca istoricul
                    self._on_conversation_selected()

class CreateGroupDialog(simpledialog.Dialog):
    def __init__(self, parent, all_users):
        self.all_users = all_users
        self.result = None
        super().__init__(parent, "Creare Conversație de Grup Nouă")

    def body(self, master):
        main_pane = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        groups_list_frame = ttk.LabelFrame(main_pane, text="Grupurile Mele", width=250)
        main_pane.add(groups_list_frame, weight=1)
        self.groups_listbox = tk.Listbox(groups_list_frame, exportselection=False)
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        details_frame = ttk.LabelFrame(main_pane, text="Detalii Grup Selectat")
        main_pane.add(details_frame, weight=2)

        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume:").pack(side=tk.LEFT)
        self.group_name_var = tk.StringVar(master)
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
        self.delete_group_button = ttk.Button(group_actions_frame, text="Șterge Grupul", state="disabled", command=self._delete_group)
        self.delete_group_button.pack(side=tk.RIGHT)
        
        self._populate_group_list()
        return self.groups_listbox

    def validate(self):
        self.group_name = self.group_name_entry.get().strip()
        self.selected_indices = self.user_listbox.curselection()

        if not self.group_name:
            messagebox.showwarning("Date Incomplete", "Numele grupului este obligatoriu.", parent=self)
            return 0
        
        if not self.selected_indices:
            messagebox.showwarning("Date Incomplete", "Selectați cel puțin un alt participant.", parent=self)
            return 0
            
        return 1

    def apply(self):
        selected_user_ids = [self.all_users[i]['id'] for i in self.selected_indices]
        self.result = {
            "group_name": self.group_name,
            "participant_ids": selected_user_ids
        }

class NewChatDialog(simpledialog.Dialog):
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

class AddParticipantDialog(simpledialog.Dialog):
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

class GroupManagerDialog(tk.Toplevel):
    def __init__(self, parent, db_handler, user_id):
        # 1. Inițializăm ca Toplevel, nu ca simpledialog
        super().__init__(parent)
        
        # 2. Setăm proprietățile ferestrei direct pe 'self'
        self.title("Administrare Grupuri")
        self.geometry("700x500")
        
        # 3. Ne asigurăm că dialogul este modal și rămâne deasupra părintelui
        self.transient(parent)
        self.grab_set()

        # Atributele interne rămân la fel
        self.db_handler = db_handler
        self.current_user_id = user_id
        self.selected_group_id = None
        self.listbox_map = {}
        self.participants_map = {}
        
        # 4. Construim widget-urile
        self._create_widgets()
        
        # 5. Încărcăm datele inițiale
        self._populate_group_list()

    def _create_widgets(self):
        """Metodă nouă care înlocuiește 'body' și 'buttonbox'."""
        
        # Folosim 'self' ca părinte principal pentru widget-uri
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Panoul din stânga (lista de grupuri) ---
        groups_list_frame = ttk.LabelFrame(main_pane, text="Grupurile Mele", width=250)
        main_pane.add(groups_list_frame, weight=1)
        self.groups_listbox = tk.Listbox(groups_list_frame, exportselection=False)
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        # --- Panoul din dreapta (detalii) ---
        details_frame = ttk.LabelFrame(main_pane, text="Detalii Grup Selectat")
        main_pane.add(details_frame, weight=2)

        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume:").pack(side=tk.LEFT)
        self.group_name_var = tk.StringVar(self) # Părintele este 'self'
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

        # --- Butoanele de acțiune de jos ---
        bottom_actions_frame = ttk.Frame(details_frame)
        bottom_actions_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        self.delete_group_button = ttk.Button(bottom_actions_frame, text="Șterge Grupul", state="disabled", command=self._delete_group)
        self.delete_group_button.pack(side=tk.RIGHT)
        
        # --- Butoanele principale ale dialogului (fostul 'buttonbox') ---
        main_button_frame = ttk.Frame(self)
        main_button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.create_new_group_button = ttk.Button(main_button_frame, text="Creează un Grup Nou...", command=self._create_new_group)
        self.create_new_group_button.pack(side=tk.LEFT, padx=5)
        # Butonul de închidere distruge fereastra 'self'
        ttk.Button(main_button_frame, text="Închide", command=self.destroy).pack(side=tk.RIGHT)

    # --- Restul metodelor (logica internă) rămân neschimbate ---
    # Le includ aici pentru a putea înlocui clasa cu totul.

    def _populate_group_list(self):
        current_selection_indices = self.groups_listbox.curselection()
        
        self.groups_listbox.delete(0, tk.END)
        self.listbox_map.clear()
        
        my_groups = self.db_handler.get_groups_for_user(self.current_user_id)
        for index, group in enumerate(my_groups):
            self.groups_listbox.insert(index, group['nume_conversatie'])
            self.listbox_map[index] = group['id']
        
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

    def _delete_group(self):
        if not self.selected_group_id: return

        group_name = self.group_name_var.get()
        if messagebox.askyesno("Confirmare Ștergere", f"Sunteți absolut sigur că doriți să ștergeți PERMANENT grupul '{group_name}'?\n\nToate mesajele din acest grup vor fi pierdute.", icon='warning', parent=self):
            if self.db_handler.delete_group(self.selected_group_id):
                messagebox.showinfo("Succes", "Grupul a fost șters.", parent=self)
                self._populate_group_list()
            else:
                messagebox.showerror("Eroare", "Grupul nu a putut fi șters.", parent=self)

    def _create_new_group(self):
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