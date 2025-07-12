# src/BTExtrasViewer/ui_help.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from common.app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, GLOBAL_HOTKEY_VIEWER, GLOBAL_HOTKEY_CHAT

class HelpDialog(tk.Toplevel):
    def __init__(self, parent, initial_topic_id='welcome'):
        super().__init__(parent)
        self.title(f"Ghid de Utilizare - {APP_NAME}")
        self.geometry("850x650")
        self.minsize(700, 500)
        self.transient(parent)
        self.grab_set()

        # Stocarea conținutului
        self.help_content = self._load_content_data()

        # Crearea widget-urilor
        self._create_widgets()
        self._setup_styles()
        self._populate_nav_tree()

        # Selectarea subiectului inițial
        if self.nav_tree.exists(initial_topic_id):
            self.nav_tree.selection_set(initial_topic_id)
            self.nav_tree.focus(initial_topic_id)
            self.nav_tree.see(initial_topic_id)

        self.center_window()

    def center_window(self):
        self.update_idletasks()
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{max(0, position_x)}+{max(0, position_y)}")

    def _create_widgets(self):
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(expand=True, fill="both", padx=10, pady=10)

        # Panoul de Navigare (stânga)
        nav_frame = ttk.Frame(main_pane, width=250)
        nav_frame.pack_propagate(False)
        self.nav_tree = ttk.Treeview(nav_frame, show="tree")
        self.nav_tree.pack(expand=True, fill="both")
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_nav_select)
        main_pane.add(nav_frame, weight=1)

        # Panoul de Conținut (dreapta)
        content_frame = ttk.Frame(main_pane)
        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state="disabled", font=("Segoe UI", 10), padx=10, pady=10)
        self.content_text.pack(expand=True, fill="both")
        main_pane.add(content_frame, weight=3)
        
    def _setup_styles(self):
        """Configurează tag-urile de stil pentru widget-ul de text."""
        self.content_text.tag_configure("h1", font=("Segoe UI", 16, "bold"), spacing3=15, foreground="#005A9E")
        self.content_text.tag_configure("h2", font=("Segoe UI", 13, "bold"), spacing1=18, spacing3=8, foreground="#34495E")
        self.content_text.tag_configure("h3", font=("Segoe UI", 11, "bold"), spacing1=12, spacing3=5, foreground="#34495E")
        self.content_text.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        self.content_text.tag_configure("italic", font=("Segoe UI", 10, "italic"))
        self.content_text.tag_configure("code", font=("Consolas", 10), background="#f0f0f0", relief="raised", borderwidth=1, lmargin1=15, lmargin2=15)
        self.content_text.tag_configure("list_item", lmargin1=20, lmargin2=35)
        self.content_text.tag_configure("normal", lmargin1=10, lmargin2=10)

    def _populate_nav_tree(self):
        """Construiește structura arborescentă a cuprinsului."""
        # Nivel 0
        self.nav_tree.insert("", "end", text="🚀 Bun Venit", iid="welcome", open=True)
        self.nav_tree.insert("", "end", text="🖥️ Session Manager", iid="session_manager", open=True)
        viewer_node = self.nav_tree.insert("", "end", text="📊 BTExtras Viewer", iid="viewer", open=True)
        chat_node = self.nav_tree.insert("", "end", text="💬 BTExtras Chat", iid="chat", open=True)
        admin_node = self.nav_tree.insert("", "end", text="🔐 Administrare & Securitate", iid="admin", open=True)
        self.nav_tree.insert("", "end", text="ℹ️ Despre Aplicație", iid="about", open=True)

        # Nivel 1 (sub Viewer)
        ui_node = self.nav_tree.insert(viewer_node, "end", text="Interfața Principală", iid="viewer_ui")
        ops_node = self.nav_tree.insert(viewer_node, "end", text="Operațiuni Cheie", iid="viewer_ops")
        reports_node = self.nav_tree.insert(viewer_node, "end", text="Rapoarte și Analiză", iid="viewer_reports")
        
        # Nivel 2 (sub Interfața Principală)
        self.nav_tree.insert(ui_node, "end", text="Navigarea Perioadei", iid="viewer_ui_nav")
        self.nav_tree.insert(ui_node, "end", text="Zona de Filtre", iid="viewer_ui_filters")
        self.nav_tree.insert(ui_node, "end", text="Lista de Tranzacții", iid="viewer_ui_list")
        
        # Nivel 2 (sub Operațiuni Cheie)
        self.nav_tree.insert(ops_node, "end", text="Import fișiere MT940", iid="viewer_ops_import")
        self.nav_tree.insert(ops_node, "end", text="Export în Excel", iid="viewer_ops_export")
        self.nav_tree.insert(ops_node, "end", text="Trimitere Export pe Email", iid="viewer_ops_email")

        # Nivel 1 (sub Administrare)
        self.nav_tree.insert(admin_node, "end", text="Gestionare Utilizatori", iid="admin_users")
        self.nav_tree.insert(admin_node, "end", text="Gestionare Roluri", iid="admin_roles")
        self.nav_tree.insert(admin_node, "end", text="Gestionare Conturi", iid="admin_accounts")
        self.nav_tree.insert(admin_node, "end", text="Configurare SMTP", iid="admin_smtp")

    def _on_nav_select(self, event):
        """Afișează conținutul corespunzător elementului selectat din arbore."""
        selected_id = self.nav_tree.focus()
        content = self.help_content.get(selected_id)
        if content:
            self._display_content(content)

    def _display_content(self, content_tuples):
        """Curăță și populează widget-ul de text cu conținutul formatat."""
        self.content_text.config(state="normal")
        self.content_text.delete("1.0", tk.END)
        for line, tags in content_tuples:
            self.content_text.insert(tk.END, line + "\n", tags)
        self.content_text.config(state="disabled")

    def _load_content_data(self):
        """Baza de date a conținutului de ajutor. Fiecare cheie corespunde unui 'iid' din arbore."""
        return {
            'welcome': [
                ("Bun Venit în BTExtras Suite!", "h1"),
                (f"Acest ghid vă va oferi toate informațiile necesare pentru a utiliza la maximum potențialul suitei {APP_NAME}. Navigați prin subiectele din panoul din stânga pentru a explora fiecare funcționalitate în parte.", "normal"),
                ("Prezentare Generală", "h2"),
                ("Suita este o soluție client-server complexă, destinată gestiunii, vizualizării și analizei extraselor de cont bancare, cu funcționalități integrate de comunicare securizată. Este compusă din trei module principale:", "normal"),
                ("   • Session Manager:", "bold"),
                ("     Piesa centrală care rulează discret în fundal (system tray) și gestionează pornirea și accesul rapid la celelalte module.", "list_item"),
                ("   • BTExtras Viewer:", "bold"),
                ("     Aplicația principală pentru importul, vizualizarea, filtrarea și raportarea datelor financiare.", "list_item"),
                ("   • BTExtras Chat:", "bold"),
                ("     O aplicație de comunicare internă, securizată, între utilizatorii sistemului.", "list_item")
            ],
            'session_manager': [
                ("Session Manager", "h1"),
                ("Componenta de bază a suitei, care rulează permanent în System Tray (zona de notificări de lângă ceas).", "normal"),
                ("Funcționalități", "h2"),
                ("   • Lansare Module: Click dreapta pe iconița BTExtras pentru a deschide un meniu de unde puteți lansa BTExtras Viewer sau BTExtras Chat.", "list_item"),
                ("   • Acces Rapid (Hotkeys): Folosiți combinațiile de taste globale pentru a aduce instantaneu în prim-plan ferestrele aplicațiilor, chiar dacă sunt minimizate sau în spatele altor ferestre:", "list_item"),
                (f"      - Pentru BTExtras Viewer: {GLOBAL_HOTKEY_VIEWER.upper()}", "code"),
                (f"      - Pentru BTExtras Chat: {GLOBAL_HOTKEY_CHAT.upper()}", "code"),
                ("   • Gestiunea Sesiunii: După ce vă autentificați în Viewer, Session Manager reține sesiunea dumneavoastră, permițând lansarea aplicației de Chat fără a necesita o nouă autentificare.", "list_item")
            ],
            'viewer_ui_nav': [
                ("Interfața Viewer: Navigarea Perioadei", "h1"),
                ("Panoul din stânga este dedicat navigării rapide și intuitive prin datele dumneavoastră.", "normal"),
                ("Structură Ierarhică", "h2"),
                ("Datele sunt organizate într-o structură arborescentă:", "normal"),
                ("   • Anul:", "bold"),
                ("     Cel mai înalt nivel. Dând click pe un an, veți vedea în lista din dreapta toate tranzacțiile din acel an.", "list_item"),
                ("   • Luna:", "bold"),
                ("     Click pe săgeata de lângă un an pentru a expanda și a vedea lunile disponibile. Selectarea unei luni va filtra tranzacțiile corespunzătoare.", "list_item"),
                ("   • Ziua:", "bold"),
                ("     Similar, puteți expanda o lună pentru a vedea zilele cu activitate. Selectarea unei zile afișează tranzacțiile din acea zi.", "list_item"),
                ("Acest sistem anulează și înlocuiește orice filtru setat în zona de 'Interval Dată Specific'.", "italic")
            ],
            'viewer_ui_filters': [
                ("Interfața Viewer: Zona de Filtre", "h1"),
                ("Deasupra listei de tranzacții se află o zonă puternică de filtrare și acțiuni.", "normal"),
                ("Contul Activ", "h2"),
                ("Folosiți meniul dropdown 'Cont Bancar Activ' pentru a comuta între conturile la care aveți acces. Toate datele afișate (navigare, tranzacții, totaluri) se vor actualiza instantaneu.", "normal"),
                ("Filtrare după Dată", "h2"),
                ("Bifați opțiunea 'Interval Dată Specific' pentru a activa calendarele 'De la' și 'Până la'. Acest mod vă permite să definiți un interval personalizat și are prioritate față de selecția din panoul de navigare.", "normal"),
                ("Filtrare după Tip și Conținut", "h2"),
                ("   • Tip: Alegeți să vedeți 'Toate' tranzacțiile, sau doar pe cele de tip 'credit' (intrări) sau 'debit' (ieșiri).", "list_item"),
                ("   • Căutare Text: Introduceți un termen în câmpul de căutare. Puteți alege din meniul dropdown alăturat coloana specifică în care să căutați (ex: Beneficiar, Descriere, Sumă) sau lăsați 'Toate coloanele' pentru o căutare generală.", "list_item"),
                ("   • Căutare Exactă: Când aveți o coloană specifică selectată, puteți bifa 'Căutare exactă' pentru a găsi potriviri perfecte, nu parțiale.", "list_item"),
                ("Butonul 'Resetează filtrele' anulează toate aceste setări și revine la afișarea tuturor datelor din contul activ.", "italic")
            ],
            'viewer_ui_list': [
                ("Interfața Viewer: Lista de Tranzacții", "h1"),
                ("Zona centrală a aplicației, unde sunt afișate datele financiare detaliate.", "normal"),
                ("Vizualizare", "h2"),
                ("Tabelul afișează tranzacțiile care corespund tuturor filtrelor active. Tranzacțiile de tip 'credit' sunt marcate cu un fundal verde deschis, iar cele de 'debit' cu roșu deschis, pentru o identificare vizuală rapidă.", "normal"),
                ("Sortare", "h2"),
                ("Dați click pe antetul oricărei coloane (ex: 'Data', 'Suma') pentru a sorta întregul set de date după acea coloană. Un al doilea click pe același antet va inversa ordinea de sortare (ascendent/descendent). O săgeată va indica coloana și direcția de sortare curentă.", "normal"),
                ("Detalii Tranzacție", "h2"),
                ("Efectuați un dublu-click pe orice rând din tabel pentru a deschide o fereastră nouă cu toate detaliile acelei tranzacții, inclusiv informații care nu sunt vizibile în tabelul principal. În această fereastră puteți adăuga sau modifica câmpul 'Observații' pentru a nota informații suplimentare.", "normal")
            ],
            'viewer_ops_import': [
                ("Operațiuni: Import fișiere MT940", "h1"),
                ("Aplicația simplifică procesul de adăugare a datelor noi.", "normal"),
                ("Procesul de Import", "h2"),
                ("1. Apăsați butonul 'Importă fișier MT940'.", "list_item"),
                ("2. Selectați unul sau mai multe fișiere de pe computer.", "list_item"),
                ("3. Sistemul inteligent va citi IBAN-ul din fiecare fișier și va încerca să-l asocieze automat cu un cont existent în baza de date.", "list_item"),
                ("4. Cont Nou Detectat: Dacă un fișier conține un IBAN care nu există în sistem, veți fi întrebat dacă doriți să creați un cont nou pentru acesta. Dacă acceptați, se va deschide fereastra de creare a contului, pre-populată cu IBAN-ul detectat.", "list_item"),
                ("5. Prevenirea Duplicatelor: Aplicația verifică fiecare tranzacție înainte de a o insera. Dacă o tranzacție identică (bazată pe dată, sumă, tip și descriere) există deja, aceasta va fi ignorată pentru a menține integritatea datelor.", "list_item"),
                ("Puteți vedea un sumar al tuturor importurilor în tab-ul 'Istoric Importuri'.", "italic")
            ],
            'viewer_ops_export': [
                ("Operațiuni: Export în Excel", "h1"),
                ("Puteți salva cu ușurință datele filtrate într-un fișier Excel formatat profesional.", "normal"),
                ("Cum Funcționează", "h2"),
                ("1. Aplicați orice combinație de filtre doriți (perioadă, tip, căutare text).", "list_item"),
                ("2. Apăsați butonul 'Exportă în Excel'.", "list_item"),
                ("3. Alegeți locația și numele fișierului în fereastra de salvare.", "list_item"),
                ("Fișierul Excel generat va conține exact datele afișate pe ecran, cu formatare specială: antet înghețat (freeze pane), funcționalitate de auto-filtrare, culori distincte pentru rânduri și lățimi de coloane ajustate automat.", "normal")
            ],
            'viewer_ops_email': [
                ("Operațiuni: Trimitere Export pe Email", "h1"),
                ("Această funcționalitate vă permite să trimiteți exportul Excel direct pe email, fără a-l salva local.", "normal"),
                ("Cum Funcționează", "h2"),
                ("1. Aplicați filtrele dorite pentru a obține setul de date relevant.", "list_item"),
                ("2. Apăsați butonul 'Trimite Export pe Email'.", "list_item"),
                ("3. Introduceți adresa de email a destinatarului în fereastra care apare.", "list_item"),
                ("4. Aplicația va genera automat fișierul Excel, va compune un email profesional care include un sumar al filtrelor aplicate și semnătura dumneavoastră, și va trimite emailul cu fișierul atașat.", "list_item"),
                ("Notă: Această funcționalitate necesită configurarea prealabilă a setărilor SMTP din meniul 'Administrare'.", "italic")
            ],
            'viewer_reports': [
                ("Rapoarte și Analiză", "h1"),
                ("Suita oferă trei tipuri de rapoarte avansate, accesibile din meniul 'Rapoarte'. Fiecare raport poate fi exportat în PDF sau Excel și trimis pe email.", "normal"),
                ("Analiză Flux de Numerar (Cash Flow)", "h2"),
                ("Oferă o imagine clară a intrărilor și ieșirilor totale, grupate lunar sau zilnic. Afișează un grafic cu bare pentru a compara vizual încasările și plățile, alături de un tabel sumar. Este ideal pentru a înțelege de unde vin și unde se duc banii într-o anumită perioadă.", "normal"),
                ("Evoluție Sold Cont", "h2"),
                ("Generează un grafic liniar care arată cum a evoluat soldul unui cont selectat de-a lungul timpului. Este perfect pentru a observa tendințele pe termen lung (creștere, scădere) și pentru a identifica perioadele cu fluctuații mari.", "normal"),
                ("Analiză Detaliată Tranzacții", "h2"),
                ("Cel mai complex raport, care grupează tranzacțiile după codul lor tehnic SWIFT (ex: 'NTRF', 'CMI') și le afișează într-un grafic cu bare stivuite. Permite o analiză fină a tipurilor de operațiuni care contribuie la fluxul de numerar, ajutând la identificarea celor mai frecvente sau mai valoroase tipuri de tranzacții.", "normal")
            ],
            'chat': [
                ("BTExtras Chat", "h1"),
                ("Un instrument de comunicare internă, rapid și securizat.", "normal"),
                ("Funcționalități Principale", "h2"),
                ("   • Conversații 1-la-1: Puteți iniția o conversație privată cu orice alt utilizator activ din sistem.", "list_item"),
                ("   • Conversații de Grup: Creați și administrați grupuri de discuții pentru echipe sau proiecte.", "list_item"),
                ("   • Status Online: În lista de conversații, un simbol verde (✓) indică utilizatorii activi în acel moment.", "list_item"),
                ("   • Notificări Mesaje Necitite: Conversațiile cu mesaje noi sunt evidențiate și afișează numărul de mesaje necitite.", "list_item"),
                ("   • Confirmări de Citire: Mesajele trimise de dumneavoastră vor afișa un simbol ✓ când au fost livrate și ✓✓ când au fost citite de către destinatar.", "list_item")
            ],
            'admin_users': [
                ("Administrare: Gestionare Utilizatori", "h1"),
                ("Această secțiune, accesibilă doar utilizatorilor cu permisiuni speciale, permite administrarea completă a conturilor de utilizator.", "normal"),
                ("Operațiuni Disponibile", "h2"),
                ("   • Adăugare: Creați conturi noi, specificând numele de utilizator, parola inițială și numele complet.", "list_item"),
                ("   • Modificare: Editați detaliile unui utilizator existent, resetați parola, schimbați rolurile și conturile la care are acces.", "list_item"),
                ("   • Activare/Dezactivare: Puteți dezactiva temporar un cont fără a-l șterge, blocându-i accesul la aplicație.", "list_item"),
                ("   • Ștergere: Eliminați permanent un cont de utilizator. Această acțiune nu poate fi anulată.", "list_item"),
                ("   • Setare Acces Tranzacții: Pentru fiecare utilizator, puteți defini dacă are voie să vadă toate tranzacțiile, doar pe cele de 'credit' sau doar pe cele de 'debit'.", "list_item")
            ],
            'admin_roles': [
                ("Administrare: Gestionare Roluri", "h1"),
                ("Rolurile definesc seturi de permisiuni care pot fi apoi asignate utilizatorilor.", "normal"),
                ("Permisiuni Granulare", "h2"),
                ("Fiecare rol poate avea o combinație specifică de permisiuni, cum ar fi:", "normal"),
                ("   • Dreptul de a administra alți utilizatori sau roluri.", "list_item"),
                ("   • Dreptul de a importa fișiere sau de a exporta date.", "list_item"),
                ("   • Dreptul de a vizualiza și genera diferite tipuri de rapoarte.", "list_item"),
                ("   • Dreptul de a vedea jurnalele de audit sau de a configura setări ale aplicației.", "list_item"),
                ("Rolul 'Administrator' are implicit toate permisiunile și nu poate fi modificat sau șters, pentru a asigura întotdeauna existența unui super-utilizator.", "italic")
            ],
            'admin_accounts': [ # << SECȚIUNE NOUĂ
                ("Administrare: Gestionare Conturi", "h1"),
                ("Această fereastră vă permite să administrați toate conturile bancare din sistem.", "normal"),
                ("Operațiuni Disponibile", "h2"),
                ("   • Adăugare Cont Nou: Apăsați butonul 'Adaugă Cont Nou' pentru a deschide fereastra de creare. Completați numele contului, IBAN-ul, numele băncii, valuta și alegeți o culoare distinctivă pentru o identificare vizuală ușoară.", "list_item"),
                ("   • Modificare Cont: Selectați un cont din listă și apăsați 'Modifică Selectat' (sau efectuați un dublu-click pe el). Puteți actualiza oricare dintre detaliile sale.", "list_item"),
                ("   • Ștergere Cont: Selectați un cont și apăsați 'Șterge Selectat'.", "list_item"),
                ("Atenție: Un cont bancar nu poate fi șters dacă are tranzacții asociate. Această măsură de siguranță previne pierderea accidentală de date financiare istorice.", "bold")
            ],
            'admin_smtp': [ # << SECȚIUNE NOUĂ
                ("Administrare: Configurare SMTP", "h1"),
                ("Această secțiune vă permite să configurați setările pentru serverul de email (SMTP), necesare pentru a trimite emailuri direct din aplicație.", "normal"),
                ("Setări Personale", "h2"),
                ("Fiecare utilizator își poate configura propriile setări SMTP. Acestea sunt salvate în profilul personal și nu sunt vizibile altor utilizatori.", "normal"),
                ("Câmpuri Necesare", "h3"),
                ("   • Server SMTP: Adresa serverului de email (ex: 'smtp.gmail.com', 'mail.yourcompany.ro').", "list_item"),
                ("   • Port: Portul folosit de server (ex: 465 pentru SSL/TLS, 587 pentru STARTTLS).", "list_item"),
                ("   • Securitate: Alegeți tipul de conexiune securizată (SSL/TLS sau STARTTLS).", "list_item"),
                ("   • Email Expeditor: Adresa de email care va apărea ca expeditor.", "list_item"),
                ("   • Utilizator: Numele de utilizator pentru autentificare la server (adesea identic cu adresa de email).", "list_item"),
                ("   • Parolă: Parola contului de email sau o 'parolă de aplicație' specifică (recomandat pentru servicii precum Gmail).", "list_item"),
                ("Butonul 'Testează Conexiunea' vă permite să verificați dacă setările introduse sunt corecte înainte de a le salva.", "italic")
            ],
            'about': [
                (f"{APP_NAME}", "h1"),
                (f"Versiune: {APP_VERSION}", "bold"),
                (APP_COPYRIGHT, "normal"),
                ("Această suită software este o soluție comercială dezvoltată de Regio Development.", "italic"),
                ("", "normal"),
                ("Pentru suport tehnic sau informații comerciale, vă rugăm să ne contactați:", "h2"),
                ("   • Email: office@regio-development.ro", "list_item"),
                ("   • Web: https://regio-cloud.ro/software", "list_item")
            ]
        }