# BTExtrasChat/chat_ui.py

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Menu, END, Toplevel, Frame, simpledialog, Listbox
import threading
import queue
import time
from datetime import datetime, timedelta
import pymysql
from pymysql.cursors import DictCursor
import os
import socket
import sys
from common.app_constants import CHAT_COMMAND_PORT
from common.db_handler import DatabaseHandler, get_new_db_connection

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
        
        # Inițializăm dicționarul pentru a stoca etichetele de stare ale mesajelor (✓, ✓✓)
        self.message_status_labels = {}
        
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
        """
        Versiune finală: Apelează _show_window() direct din acest thread
        pentru a evita orice blocaj al cozii de mesaje sau al buclei 'after'.
        """
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('127.0.0.1', CHAT_COMMAND_PORT))
            server_socket.listen(1)
            print(f"INFO (Chat): Serverul de comenzi ascultă pe portul {CHAT_COMMAND_PORT}.")

            while self.is_running:
                conn, addr = server_socket.accept()
                with conn:
                    data = conn.recv(1024)
                    if data == b'SHOW_WINDOW':
                        print("DEBUG (Chat): Comanda SHOW_WINDOW primită. Se apelează direct _show_window().")
                        # Apelăm funcția direct, ocolind coada de mesaje.
                        self._show_window()
        
        except OSError as e:
            if not self.is_running:
                print("INFO (Chat): Serverul de comenzi s-a oprit.")
            else:
                print(f"EROARE CRITICĂ (Chat): Serverul de comenzi a eșuat: {e}")
        except Exception as e:
            print(f"EROARE CRITICĂ (Chat): Eroare neașteptată în serverul de comenzi: {e}")
        finally:
            if server_socket:
                server_socket.close()

    def _schedule_user_list_refresh(self):
        """Reîmprospătează periodic lista de utilizatori pentru a actualiza statusul."""
        if self.is_running:
            # PAS CRITIC ADĂUGAT: Actualizăm contoarele din DB înainte de a redesena.
            self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
            
            # Acum redesenăm lista, având garanția că folosim date proaspete.
            self._populate_conversation_list()
            
            # Programăm următoarea reîmprospătare.
            self.master.after(20000, self._schedule_user_list_refresh)

    def _on_manage_groups(self):
        """Deschide dialogul de administrare a grupurilor."""
        dialog = GroupManagerDialog(self.master, self.db_handler, self.current_user['id'])
        self._populate_conversation_list()

    def _poll_for_new_messages(self):
        """
        Versiune refactorizată: Acest thread este strict READ-ONLY.
        Doar citește datele din DB și le pune în coadă pentru a fi procesate
        de thread-ul principal. Elimină complet riscul de blocare (lock).
        """
        connection = get_new_db_connection(self.db_creds)
        if not connection:
            print("EROARE CRITICĂ (Chat Polling): Conexiunea DB a eșuat. Thread-ul se oprește.")
            return

        my_id = self.current_user['id']
        try:
            while self.is_running:
                try:
                    connection.ping(reconnect=True)
                    
                    with connection.cursor() as cursor:
                        # 1. Trimitere heartbeat (singura scriere, dar pe tabela utilizatori, nu intră în conflict)
                        cursor.execute("UPDATE utilizatori SET last_seen = CURRENT_TIMESTAMP WHERE id = %s", (my_id,))
                        connection.commit() # Commit dedicat doar pentru heartbeat

                        # 2. Căutare mesaje noi pentru mine (READ-ONLY)
                        sql_new = """
                            SELECT m.id, m.id_conversatie_fk, m.id_expeditor_fk, m.continut_mesaj, m.timestamp,
                                COALESCE(u.nume_complet, u.username) AS expeditor
                            FROM chat_mesaje m
                            JOIN chat_participanti p ON m.id_conversatie_fk = p.id_conversatie_fk
                            JOIN utilizatori u ON m.id_expeditor_fk = u.id
                            WHERE p.id_utilizator_fk = %s AND m.id_expeditor_fk != %s AND m.stare = 'trimis'
                        """
                        cursor.execute(sql_new, (my_id, my_id))
                        new_messages = cursor.fetchall()
                        if new_messages:
                            for msg in new_messages:
                                self.message_queue.put(('new_message', msg))
                        
                        # 3. Căutare actualizări de stare pentru mesajele mele (READ-ONLY)
                        sql_status = """
                            SELECT id, id_conversatie_fk, stare 
                            FROM chat_mesaje 
                            WHERE id_expeditor_fk = %s AND stare IN ('livrat', 'citit')
                        """
                        cursor.execute(sql_status, (my_id,))
                        status_updates = cursor.fetchall()
                        if status_updates:
                            for update in status_updates:
                                self.message_queue.put(('status_update', update))

                except pymysql.Error as db_err:
                    print(f"AVERTISMENT (Chat Polling): Eroare DB, se reîncearcă... Detalii: {db_err}")

                time.sleep(2) # Putem reduce timpul de așteptare la 2 secunde
                
        except Exception as e:
            import traceback
            print(f"EROARE CRITICĂ în thread-ul de polling al chat-ului: {e}")
            traceback.print_exc()
        finally:
            if connection:
                connection.close()

    def _quit_application(self):
        """Oprește toate procesele de fundal și închide complet aplicația."""
        self.is_running = False
        # Ne asigurăm că thread-ul de comenzi se oprește prin închiderea socket-ului
        # Acest pas este opțional, dar curat - închiderea aplicației oricum va opri thread-ul daemon
        try:
            # Ne conectăm la propriul server pentru a-l debloca din 'accept'
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', CHAT_COMMAND_PORT))
        except:
            pass # Ignorăm erorile, scopul este doar deblocarea

        self.master.after(100, self.master.destroy)

    def _update_message_status_in_ui(self, message_id, new_status):
        """Găsește eticheta de status a unui mesaj și îi actualizează textul."""
        if message_id in self.message_status_labels:
            status_label = self.message_status_labels[message_id]
            if status_label.winfo_exists():
                status_text = ""
                if new_status == 'livrat':
                    status_text = "✓"
                elif new_status == 'citit' or new_status == 'vazut_de_expeditor':
                    status_text = "✓✓"
                
                status_label.config(text=status_text)

    def _update_message_status_in_ui(self, message_id, new_status):
        """Găsește eticheta de status a unui mesaj și îi actualizează textul."""
        if message_id in self.message_status_labels:
            status_label = self.message_status_labels[message_id]
            if status_label.winfo_exists():
                status_text = ""
                if new_status == 'livrat':
                    status_text = "✓"
                elif new_status == 'citit' or new_status == 'vazut_de_expeditor':
                    status_text = "✓✓"
                
                status_label.config(text=status_text)

    def _process_message_queue(self):
        """
        Versiune refactorizată: Procesează evenimentele din coadă și este
        singurul responsabil pentru TOATE operațiunile de scriere în DB,
        eliminând conflictele și rezolvând problema afișării duplicate.
        """
        try:
            while not self.message_queue.empty():
                # Folosim 'get_nowait' pentru a evita blocarea
                event_type, data = self.message_queue.get_nowait()

                if event_type == 'new_message':
                    conv_id = data['id_conversatie_fk']
                    
                    # Pas 1: Thread-ul principal marchează mesajul ca 'livrat'
                    # Aceasta este o operațiune sigură, fără conflict
                    self.db_handler.execute_commit(
                        "UPDATE chat_mesaje SET stare = 'livrat' WHERE id = %s AND stare = 'trimis'", 
                        (data['id'],)
                    )

                    # Pas 2: Actualizăm contoarele de mesaje necitite
                    self.unread_counts = self.db_handler.get_unread_message_counts(self.current_user['id'])
                    self._populate_conversation_list() # Reîmprospătăm lista din stânga

                    # Pas 3: Gestionăm afișarea pentru a evita duplicarea
                    if conv_id == self.active_conversation_id:
                        # Dacă fereastra de chat este deja deschisă, reîncărcăm tot istoricul.
                        # _load_conversation_history se va ocupa și de afișare și de marcarea ca 'citit'.
                        self._load_conversation_history()
                    
                elif event_type == 'status_update':
                    # Extragem starea primită ('livrat' sau 'citit') din datele evenimentului
                    new_status = data['stare']

                    # 1. Actualizăm interfața grafică a expeditorului (bifele ✓ sau ✓✓)
                    #    dacă conversația este deschisă pe ecran.
                    if data['id_conversatie_fk'] == self.active_conversation_id:
                        self._update_message_status_in_ui(data['id'], new_status)

                    # 2. CORECȚIE CRITICĂ: Actualizăm starea în baza de date la 'vazut_de_expeditor'
                    #    DOAR dacă mesajul a fost confirmat ca fiind 'citit'.
                    #    Acest lucru lasă starea 'livrat' neschimbată, permițând contorului
                    #    destinatarului să funcționeze corect.
                    if new_status == 'citit':
                        self.db_handler.execute_commit(
                            "UPDATE chat_mesaje SET stare = 'vazut_de_expeditor' WHERE id = %s AND stare = 'citit'",
                            (data['id'],)
                        )
                
        except queue.Empty:
            pass # Normal, coada este goală
        finally:
            if self.is_running:
                self.master.after(200, self._process_message_queue) # Verificăm coada mai des

    def _display_message(self, msg_data, is_new=False):
        """
        Afișează un singur mesaj în fereastra de chat.
        Versiune definitivă cu mapare precisă bazată pe tag-uri.
        """
        if not self.message_display.winfo_exists(): return
        self.message_display.config(state="normal")

        # --- NOUA LOGICĂ DE MAPARE, BAZATĂ PE TAG-URI ---
        # Pas 1: Creăm un tag temporar și unic pentru acest mesaj.
        message_id_tag = f"msg_{msg_data['id']}"

        # Pas 2: Construim și inserăm conținutul principal (textul),
        # aplicând atât tag-ul de stil ('sent'/'received'), cât și tag-ul unic.
        is_my_message = msg_data['id_expeditor_fk'] == self.current_user['id']
        style_tag = "sent" if is_my_message else "received"
        
        active_conv_details = self.conversation_details.get(self.active_conversation_id)
        prefix = ""
        if active_conv_details and active_conv_details['tip_conversatie'] == 'grup' and not is_my_message:
            sender_name = (msg_data.get('expeditor') or "Utilizator").split(' ')[0]
            prefix = f"{sender_name}:\n"
        
        self.message_display.insert(tk.END, f"{prefix}{msg_data['continut_mesaj']}", (style_tag, message_id_tag))

        # Pas 3: Obținem intervalul exact al textului inserat folosind tag-ul unic.
        tag_range = self.message_display.tag_ranges(message_id_tag)

        if tag_range:
            start_index = self.message_display.index(tag_range[0])
            end_index = self.message_display.index(tag_range[1])
            
            start_line = int(start_index.split('.')[0])
            end_line = int(end_index.split('.')[0])
            
            # Mapăm fiecare linie din intervalul returnat
            for line_num in range(start_line, end_line + 1):
                self.line_to_message_map[str(line_num)] = msg_data

        # Pas 4: Ștergem tag-ul temporar pentru a nu se acumula în memorie.
        self.message_display.tag_delete(message_id_tag)
        # --- SFÂRȘIT LOGICĂ DE MAPARE ---

        # Continuăm cu inserarea componentelor non-text (eticheta de status, spațierea)
        if is_my_message:
            status_label = ttk.Label(self.message_display, text="", font=("Segoe UI", 8), foreground="blue")
            
            stare = msg_data.get('stare')
            status_text = ""
            if stare == 'trimis':
                status_text = " "
            elif stare == 'livrat':
                status_text = " ✓"
            elif stare == 'citit' or stare == 'vazut_de_expeditor':
                status_text = " ✓✓"
            status_label.config(text=status_text)
            
            self.message_status_labels[msg_data['id']] = status_label
            self.message_display.window_create(tk.END, window=status_label)
        
        self.message_display.insert(tk.END, "\n\n", "line_spacing")
        
        if is_new:
            self.message_display.see(tk.END)
            
        self.message_display.config(state="disabled")

    def _setup_ui(self):
        """Construiește componentele vizuale ale ferestrei."""
        # --- BLOC NOU PENTRU CREAREA MENIULUI ---
        menubar = tk.Menu(self.master)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Ieșire", command=self._quit_application)
        menubar.add_cascade(label="Fișier", menu=file_menu)
        self.master.config(menu=menubar)
        # --- SFÂRȘIT BLOC ---
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
        self.message_display.tag_configure("sent", justify="right", foreground="#006400", lmargin1=10, lmargin2=10, rmargin=10)
        self.message_display.tag_configure("received", justify="left", foreground="#00008B", lmargin1=10, lmargin2=10, rmargin=10)
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
                timestamp_str = msg_data['timestamp'].strftime('%d %B %Y, %H:%M')
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

    def _select_conversation_in_listbox(self, target_conv_id):
        """Găsește și selectează o conversație în listbox pe baza ID-ului său."""
        if not target_conv_id:
            return
        
        target_index = None
        for index, conv_id in self.listbox_map.items():
            if conv_id == target_conv_id:
                target_index = index
                break
        
        if target_index is not None and self.conversation_listbox.winfo_exists():
            self.conversation_listbox.selection_clear(0, tk.END)
            self.conversation_listbox.selection_set(target_index)
            self.conversation_listbox.see(target_index)
            self._on_conversation_selected(None)

    def _send_message(self, event=None):
        """
        Versiune refactorizată: După trimiterea unui mesaj, forțează o
        reîncărcare completă a istoricului conversației active.
        Acest lucru asigură că fereastra de chat este mereu curată și afișează
        doar mesajele relevante, eliminând afișarea reziduală.
        """
        if not self.db_handler.is_connected():
            messagebox.showwarning("Conexiune Pierdută", "Conexiunea la baza de date s-a pierdut. S-a încercat reconectarea. Vă rugăm trimiteți din nou mesajul.", parent=self.master)
            return

        message_text = self.message_input.get().strip()
        if not message_text or self.active_conversation_id is None:
            return

        # Trimitem mesajul în baza de date
        new_message_id = self.db_handler.send_chat_message(
            self.active_conversation_id, self.current_user['id'], message_text
        )

        if new_message_id:
            # Ștergem textul din câmpul de introducere
            self.message_input.delete(0, tk.END)
            
            # Actualizăm lista de conversații din stânga pentru a o aduce pe cea curentă în top
            self._populate_conversation_list()
            
            # AICI ESTE CORECȚIA CRITICĂ:
            # Reîncărcăm complet istoricul conversației. Această funcție va șterge
            # mesajele vechi și va afișa tot istoricul corect, inclusiv noul mesaj trimis.
            self._load_conversation_history()
        else:
            messagebox.showerror("Eroare", "Mesajul nu a putut fi trimis. Verificați conexiunea și reîncercați.", parent=self.master)

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
        """Marchează o listă specifică de ID-uri de mesaje ca fiind 'citit' în DB."""
        if not message_ids_to_update:
            return
        
        try:
            placeholders = ','.join(['%s'] * len(message_ids_to_update))
            # Actualizăm starea doar pentru ID-urile specificate
            sql_update = f"UPDATE chat_mesaje SET stare = 'citit' WHERE id IN ({placeholders})"
            self.db_handler.execute_commit(sql_update, tuple(message_ids_to_update))
        except Exception as e:
            print(f"EROARE la marcarea mesajelor ca citite: {e}")
    
    def _mark_messages_as_read(self, conversation_id):
        """Marchează toate mesajele necitite dintr-o conversație ca fiind 'citit'."""
        if not conversation_id: return
        
        # Marchează în baza de date
        sql_update = """
            UPDATE chat_mesaje 
            SET stare = 'citit' 
            WHERE id_conversatie_fk = %s 
            AND id_expeditor_fk != %s 
            AND stare != 'citit'
        """
        self.db_handler.execute_commit(sql_update, (conversation_id, self.current_user['id']))
        
        # Resetează contorul de mesaje necitite în UI și actualizează lista
        if conversation_id in self.unread_counts:
            self.unread_counts[conversation_id] = 0
        self._update_conversation_list_item(conversation_id)

    def _get_or_create_conversation(self, partner_id):
        my_id = self.current_user['id']
        
        # Pasul 1: Verificăm dacă există deja o conversație (folosind conexiunea principală, acum sigură)
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
            # Pasul 2: Dacă nu există, apelăm noua metodă atomică pentru a o crea
            return self.db_handler.create_one_on_one_conversation(my_id, partner_id)

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

        # --- ÎNCEPUT BLOC MODIFICAT ---
        # Păstrăm logica originală de a apela _display_message,
        # dar adăugăm verificarea datei înainte de fiecare apel.
        
        last_message_date = None
        for msg in messages:
            # Pas 1: Verificăm dacă data s-a schimbat
            current_message_date = msg['timestamp'].date()
            if current_message_date != last_message_date:
                # Dacă da, inserăm separatorul de dată direct în widget
                date_str = current_message_date.strftime('%d %B %Y')
                self.message_display.insert(tk.END, f"\n{date_str}\n", "date_separator")
                last_message_date = current_message_date
            
            # Pas 2: Actualizăm starea mesajului în memorie dacă a fost marcat ca citit acum
            if msg['id'] in ids_to_mark_as_read:
                msg['stare'] = 'citit'
            
            # Pas 3: Apelăm funcția originală pentru a afișa mesajul.
            # Aceasta va gestiona starea (bifa) exact ca înainte.
            self._display_message(msg)
        # --- SFÂRȘIT BLOC MODIFICAT ---

        self.message_display.config(state="disabled")
        self.message_display.see(tk.END)

    def _populate_conversation_list(self):
        """
        Încarcă și afișează toate conversațiile pentru utilizatorul curent.
        Versiune finală care elimină opțiunea "-font" incompatibilă.
        """
        try:
            current_selection_id = self.active_conversation_id

            self.conversation_listbox.delete(0, tk.END)
            self.listbox_map.clear()
            self.conversation_details.clear()
            
            my_id = self.current_user['id']
            
            sql = """
                SELECT
                    c.id AS conversation_id, c.tip_conversatie, c.nume_conversatie AS nume_grup,
                    (
                        SELECT GROUP_CONCAT(COALESCE(u.nume_complet, u.username) SEPARATOR ', ')
                        FROM chat_participanti cp JOIN utilizatori u ON cp.id_utilizator_fk = u.id
                        WHERE cp.id_conversatie_fk = c.id AND cp.id_utilizator_fk != %s
                    ) AS participant_names,
                    (
                        SELECT MAX(u.last_seen)
                        FROM chat_participanti cp JOIN utilizatori u ON cp.id_utilizator_fk = u.id
                        WHERE cp.id_conversatie_fk = c.id AND cp.id_utilizator_fk != %s
                    ) as partner_last_seen,
                    (SELECT MAX(timestamp) FROM chat_mesaje cm WHERE cm.id_conversatie_fk = c.id) as last_message_time
                FROM chat_conversatii c
                WHERE c.id IN (SELECT id_conversatie_fk FROM chat_participanti WHERE id_utilizator_fk = %s)
                ORDER BY last_message_time DESC;
            """
            
            conversations = self.db_handler.fetch_all_dict(sql, (my_id, my_id, my_id))
            if not conversations:
                return

            for index, conv in enumerate(conversations):
                conv_id = conv['conversation_id']
                self.conversation_details[conv_id] = conv
                
                if conv['tip_conversatie'] == 'grup':
                    display_name = conv['nume_grup'] or 'Grup fără nume'
                    status_symbol = "●"
                    is_online = False # Statusul online nu se aplică la grupuri
                    color = '#0000AA' # Albastru pentru grup
                else:
                    display_name = conv['participant_names'] or 'Utilizator șters'
                    last_seen = conv.get('partner_last_seen')
                    is_online = last_seen and (datetime.now() - last_seen < timedelta(seconds=15))
                    status_symbol = "✓" if is_online else "✗"
                    color = 'green' if is_online else '#A93226' # Verde/Roșu pentru utilizatori
                
                # --- BLOC PENTRU AFIȘAREA NUMĂRULUI ---
                unread_count = self.unread_counts.get(conv_id, 0)
                
                # Construim textul final
                final_display_text = f" {status_symbol} {display_name}"
                if unread_count > 0:
                    # Adăugăm numărul de mesaje necitite și îngroșăm textul
                    final_display_text += f" ({unread_count})"
                    # Setăm culoarea textului pe roșu pentru a atrage atenția
                    item_color = '#E67E22' # O nuanță de portocaliu pentru notificări
                else:
                    item_color = color # Culoarea standard (verde/albastru/roșu)
                # --- SFÂRȘIT BLOC ---
                
                self.conversation_listbox.insert(index, final_display_text)
                self.listbox_map[index] = conv_id
                
                self.conversation_listbox.itemconfig(index, {'fg': item_color})

                # LINIA NOUĂ PENTRU FUNDAL
                if unread_count > 0:
                    self.conversation_listbox.itemconfig(index, {'bg': '#E0FFFF'}) # Culoare Cyan deschis pentru fundal

            if current_selection_id:
                for i, conv_id in self.listbox_map.items():
                    if conv_id == current_selection_id:
                        self.conversation_listbox.selection_set(i)
                        break
            elif self.conversation_listbox.size() > 0:
                self.conversation_listbox.selection_set(0)
                self._on_conversation_selected(None)

        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut încărca lista de conversații: {str(e)}", parent=self.master)

    def _on_new_conversation(self):
        """
        Versiune finală: Verifică dacă există utilizatori, apoi deschide noul dialog custom.
        """
        # Pasul 1: Verificăm dacă există utilizatori disponibili
        available_users = self.db_handler.fetch_all_dict(
            "SELECT id, username, nume_complet FROM utilizatori WHERE id != %s AND activ = 1",
            (self.current_user['id'],)
        )

        if not available_users:
            messagebox.showinfo("Niciun Utilizator", "Nu există alți utilizatori activi în sistem pentru a începe o conversație.", parent=self.master)
            return

        # Pasul 2: Creăm și afișăm noul dialog, care este acum robust
        dialog = UserSelectionDialog(self.master, available_users)
        self.master.wait_window(dialog)

        # Pasul 3: Procesăm rezultatul
        if dialog.result:
            partner_id = dialog.result.get('id')
            if not partner_id:
                return

            conversation_id = self._get_or_create_conversation(partner_id)
            
            if conversation_id:
                self.active_conversation_id = conversation_id
                self._populate_conversation_list()
                self._select_conversation_in_listbox(conversation_id)

class CreateGroupDialog(simpledialog.Dialog):
    def __init__(self, parent, all_users):
        self.all_users = all_users
        self.result = None
        super().__init__(parent, "Creare Conversație de Grup Nouă")

    def body(self, master):
        # Frame pentru numele grupului
        name_frame = ttk.Frame(master)
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(name_frame, text="Nume Grup:").pack(side=tk.LEFT)
        self.group_name_entry = ttk.Entry(name_frame, width=40)
        self.group_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Frame pentru lista de utilizatori
        users_frame = ttk.LabelFrame(master, text="Selectați Participanții (Ctrl+Click pentru selecție multiplă)")
        users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        list_container = ttk.Frame(users_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.user_listbox = tk.Listbox(list_container, selectmode=tk.MULTIPLE, exportselection=False, height=10)
        self.user_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.user_listbox.yview)
        self.user_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populăm lista cu utilizatorii disponibili
        for user in self.all_users:
            display_name = user.get('nume_complet') or user.get('username')
            self.user_listbox.insert(tk.END, display_name)

        # Returnăm widget-ul care trebuie să aibă focus inițial
        return self.group_name_entry

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

class UserSelectionDialog(tk.Toplevel):
    """
    Fereastră de dialog custom pentru selecția unui utilizator.
    Rescrisă de la zero pentru a fi robustă și a elimina eroarea TclError.
    """
    def __init__(self, parent, users_list):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Selectați un Utilizator")
        self.resizable(False, False)

        self.users = users_list
        self.result = None

        # --- Crearea widget-urilor ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.listbox = Listbox(list_frame, width=50, height=10, font=("Segoe UI", 10), exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        for user in self.users:
            display_name = user.get('nume_complet') or user.get('username')
            self.listbox.insert(END, display_name)
        
        self.listbox.bind("<Double-1>", self._on_ok)
        if self.users:
            self.listbox.focus_set()
            self.listbox.selection_set(0)

        # --- Crearea butoanelor ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", side="bottom")

        # Butonul de anulare (dreapta) este împachetat primul
        cancel_button = ttk.Button(button_frame, text="Renunță", command=self._on_cancel)
        cancel_button.pack(side="right")

        # Butonul OK (stânga) este împachetat al doilea
        ok_button = ttk.Button(button_frame, text="OK", command=self._on_ok)
        ok_button.pack(side="right", padx=(5, 0))
        
        # Protocol pentru închiderea cu 'X'
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Centrarea ferestrei
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{position_x}+{position_y}")

    def _on_ok(self, event=None):
        selections = self.listbox.curselection()
        if not selections:
            messagebox.showwarning("Nicio Selecție", "Vă rugăm selectați un utilizator.", parent=self)
            return
        
        selected_index = selections[0]
        self.result = self.users[selected_index]
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()