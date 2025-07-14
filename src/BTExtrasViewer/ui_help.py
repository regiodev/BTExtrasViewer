# BTExtrasViewer/ui_help.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from common.app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, GLOBAL_HOTKEY_VIEWER, GLOBAL_HOTKEY_CHAT

class HelpDialog(tk.Toplevel):
    def __init__(self, parent, initial_topic_id='welcome'):
        super().__init__(parent)
        self.title(f"Manual de Utilizare - {APP_NAME}")
        self.geometry("900x700")
        self.minsize(750, 550)
        self.transient(parent)
        self.grab_set()

        self.help_content = self._load_content_data()

        self._create_widgets()
        self._setup_styles()
        self._populate_nav_tree()
        self._setup_hyperlinks()

        if self.nav_tree.exists(initial_topic_id):
            self.jump_to_topic(initial_topic_id)

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

        nav_frame = ttk.Frame(main_pane, width=280)
        nav_frame.pack_propagate(False)
        self.nav_tree = ttk.Treeview(nav_frame, show="tree", selectmode="browse")
        self.nav_tree.pack(expand=True, fill="both")
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_nav_select)
        main_pane.add(nav_frame, weight=1)

        content_frame = ttk.Frame(main_pane)
        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state="disabled", font=("Segoe UI", 10), padx=15, pady=10, relief="flat", background="#FFFFFF")
        self.content_text.pack(expand=True, fill="both")
        main_pane.add(content_frame, weight=3)
        
    def _setup_styles(self):
        # Stiluri pentru titluri
        self.content_text.tag_configure("h1", font=("Segoe UI", 18, "bold"), spacing3=15, foreground="#004A8D")
        self.content_text.tag_configure("h2", font=("Segoe UI", 14, "bold"), spacing1=18, spacing3=8, foreground="#2C3E50")
        self.content_text.tag_configure("h3", font=("Segoe UI", 11, "bold"), spacing1=12, spacing3=5, foreground="#34495E")
        
        # Stiluri pentru text
        self.content_text.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        self.content_text.tag_configure("italic", font=("Segoe UI", 10, "italic"))
        self.content_text.tag_configure("normal", lmargin1=10, lmargin2=10)
        
        # Stiluri speciale
        self.content_text.tag_configure("code", font=("Consolas", 10), background="#ECF0F1", relief="solid", borderwidth=1, lmargin1=15, lmargin2=15, wrap="none")
        self.content_text.tag_configure("list_item", lmargin1=25, lmargin2=40)
        self.content_text.tag_configure("note", lmargin1=15, lmargin2=15, background="#FDF2E9", foreground="#AF601A", relief="solid", borderwidth=1, borderoff=True, padding=10)
        self.content_text.tag_configure("highlight_red", foreground="red", font=("Segoe UI", 10, "bold"))
        
        # Stiluri pentru hyperlink-uri
        self.content_text.tag_configure("link", foreground="#0056b3", underline=True)

    def _setup_hyperlinks(self):
        """Leagă evenimentele de mouse la tag-ul 'link' pentru a simula hyperlink-uri."""
        self.content_text.tag_bind("link", "<Enter>", lambda e: self.content_text.config(cursor="hand2"))
        self.content_text.tag_bind("link", "<Leave>", lambda e: self.content_text.config(cursor=""))
        self.content_text.tag_bind("link", "<Button-1>", self._on_link_click)
        
    def _populate_nav_tree(self):
        # Nivel 0 - Rădăcină
        self.nav_tree.insert("", "end", text="🚀 Bun Venit", iid="welcome", open=True)
        self.nav_tree.insert("", "end", text="🖥️ Session Manager", iid="session_manager")
        
        # Nivel 0 - BTExtras Viewer
        viewer_node = self.nav_tree.insert("", "end", text="📊 BTExtras Viewer", iid="viewer", open=True)
        # Nivel 1 - Sub Viewer
        ui_node = self.nav_tree.insert(viewer_node, "end", text="Interfața Principală", iid="viewer_ui")
        ops_node = self.nav_tree.insert(viewer_node, "end", text="Operațiuni cu Date", iid="viewer_ops")
        reports_node = self.nav_tree.insert(viewer_node, "end", text="Rapoarte și Analiză", iid="viewer_reports")
        
        # Nivel 0 - BTExtras Chat
        self.nav_tree.insert("", "end", text="💬 BTExtras Chat", iid="chat")
        
        # Nivel 0 - Securitate și Administrare
        security_node = self.nav_tree.insert("", "end", text="🔑 Securitate & Administrare", iid="security", open=True)
        # Nivel 1 - Sub Securitate
        self.nav_tree.insert(security_node, "end", text="Schimbarea Parolei Personale", iid="security_change_password")
        self.nav_tree.insert(security_node, "end", text="Resetarea Parolei Uitate", iid="security_forgot_password")
        admin_node = self.nav_tree.insert(security_node, "end", text="Panou de Administrare", iid="admin", open=True)

        # Nivel 2 - Sub Panou de Administrare
        self.nav_tree.insert(admin_node, "end", text="Gestionare Utilizatori", iid="admin_users")
        self.nav_tree.insert(admin_node, "end", text="Gestionare Roluri și Permisiuni", iid="admin_roles")
        self.nav_tree.insert(admin_node, "end", text="Gestionare Conturi Bancare", iid="admin_accounts")
        self.nav_tree.insert(admin_node, "end", text="Configurare Email Sistem (SMTP)", iid="admin_smtp_system")

        # Nivel 0 - Despre
        self.nav_tree.insert("", "end", text="ℹ️ Despre Aplicație", iid="about")

    def jump_to_topic(self, topic_id):
        """Selectează și afișează un subiect specific în manual."""
        if self.nav_tree.exists(topic_id):
            self.nav_tree.selection_set(topic_id)
            self.nav_tree.focus(topic_id)
            self.nav_tree.see(topic_id)

    def _on_link_click(self, event):
        """Gestionează click-ul pe un text marcat ca hyperlink."""
        index = self.content_text.index(f"@{event.x},{event.y}")
        tags = self.content_text.tag_names(index)
        for tag in tags:
            if tag.startswith("link-"):
                topic_id = tag.split('-', 1)[1]
                self.jump_to_topic(topic_id)
                return

    def _on_nav_select(self, event):
        selected_id = self.nav_tree.focus()
        content = self.help_content.get(selected_id)
        if content:
            self._display_content(content)

    def _display_content(self, content_tuples):
        self.content_text.config(state="normal")
        self.content_text.delete("1.0", tk.END)
        for line, tags in content_tuples:
            self.content_text.insert(tk.END, line + "\n", tags)
        self.content_text.config(state="disabled")

    def _load_content_data(self):
        # Baza de date a conținutului, acum extinsă și cu hyperlink-uri
        return {
            'welcome': [
                ("Bun Venit în Suita BTExtras!", "h1"),
                (f"Acest manual interactiv vă oferă toate informațiile necesare pentru a utiliza la maximum potențialul suitei {APP_NAME}. Navigați prin subiectele din panoul din stânga pentru a explora fiecare funcționalitate.", "normal"),
                ("Prezentare Generală", "h2"),
                ("Suita BTExtras este o soluție client-server complexă, destinată gestiunii, vizualizării și analizei extraselor de cont, cu funcționalități integrate de comunicare securizată. Este compusă din trei module principale:", "normal"),
                ("   • Session Manager:", "bold"),
                ("     Piesa centrală care rulează discret în fundal (în zona de notificări) și gestionează pornirea și accesul rapid la celelalte module. Acesta asigură o experiență de utilizare fluidă și integrată.", "list_item"),
                ("   • BTExtras Viewer:", "bold"),
                ("     Aplicația principală pentru importul, vizualizarea, filtrarea și raportarea datelor financiare. Este instrumentul dumneavoastră principal de lucru cu datele bancare.", "list_item"),
                ("   • BTExtras Chat:", "bold"),
                ("     O aplicație de comunicare internă, securizată, în timp real, între utilizatorii sistemului, facilitând colaborarea.", "list_item")
            ],
            'session_manager': [
                ("Session Manager", "h1"),
                ("Este componenta de bază a suitei, care rulează permanent în System Tray (zona de notificări de lângă ceas) atâta timp cât suita este activă.", "normal"),
                ("Funcționalități Principale", "h2"),
                ("   • Lansare Module:", "bold"),
                ("     Click-dreapta pe iconița BTExtras deschide un meniu contextual. De aici puteți lansa BTExtras Viewer sau BTExtras Chat, sau puteți închide complet suita.", "list_item"),
                ("   • Acces Rapid (Hotkeys):", "bold"),
                ("     Folosiți combinațiile de taste globale pentru a aduce instantaneu în prim-plan ferestrele aplicațiilor, chiar dacă sunt minimizate sau în spatele altor ferestre:", "list_item"),
                (f"      - Pentru BTExtras Viewer: {GLOBAL_HOTKEY_VIEWER.upper()}", "code"),
                (f"      - Pentru BTExtras Chat: {GLOBAL_HOTKEY_CHAT.upper()}", "code"),
                ("   • Gestiunea Sesiunii (Single Sign-On):", "bold"),
                ("     După ce vă autentificați în Viewer, Session Manager reține sesiunea dumneavoastră. Acest lucru permite lansarea aplicației de Chat fără a necesita o nouă parolă, asigurând o experiență de lucru continuă și securizată.", "list_item")
            ],
            'security_change_password': [
                ("Schimbarea Voluntară a Parolei", "h1"),
                ("Din motive de securitate, este recomandat să vă schimbați parola periodic. Puteți face acest lucru oricând, direct din aplicație.", "normal"),
                ("Procedura de Schimbare", "h2"),
                ("1.  Asigurați-vă că sunteți autentificat în aplicația BTExtras Viewer.", "list_item"),
                ("2.  Accesați meniul principal, opțiunea 'Fișier' -> 'Schimbă Parola...'.", "list_item"),
                ("3.  În fereastra care se deschide, completați cele trei câmpuri:", "list_item"),
                ("      • Parola curentă: Introduceți parola pe care o folosiți în prezent.", "code"),
                ("      • Parola nouă: Introduceți noua parolă dorită. Trebuie să aibă minim 8 caractere.", "code"),
                ("      • Confirmă parola nouă: Reintroduceți noua parolă pentru a evita greșelile de tastare.", "code"),
                ("4.  Apăsați 'OK'. Dacă toate datele sunt corecte, parola va fi schimbată instantaneu.", "list_item"),
                ("", "normal"),
                ("Dacă parola curentă este incorectă sau parolele noi nu se potrivesc, veți primi un mesaj de eroare și va trebui să reîncercați.", "note")
            ],
            'security_forgot_password': [
                ("Resetarea Parolei Uitate", "h1"),
                ("Dacă ați uitat parola, puteți folosi acest mecanism securizat pentru a o reseta, cu condiția ca un administrator să fi configurat adresa de email a sistemului.", "normal"),
                ("Procedura de Resetare", "h2"),
                ("1.  În fereastra de autentificare, dați click pe link-ul 'Am uitat parola...'.", "list_item"),
                ("2.  Introduceți numele dumneavoastră de utilizator sau adresa de email asociată contului și apăsați 'OK'.", "list_item"),
                ("3.  Sistemul va trimite automat un email la adresa dumneavoastră, care conține un cod de verificare (token) de unică folosință, valabil timp de 15 minute.", "list_item"),
                ("     Parola dumneavoastră actuală NU este modificată în acest pas.", ("note", "bold")),
                ("4.  O nouă fereastră va apărea în aplicație, solicitând introducerea codului de verificare și a noii parole dorite.", "list_item"),
                ("5.  Copiați codul din email și introduceți-l în câmpul 'Cod Verificare'.", "list_item"),
                ("6.  Introduceți și confirmați noua parolă, apoi apăsați 'OK'.", "list_item"),
                ("Dacă codul este valid și nu a expirat, parola va fi actualizată și veți putea să vă autentificați cu noua parolă.", "normal"),
                ("Dacă întâmpinați probleme, contactați un administrator pentru a verifica dacă ", ("normal")),
                ("funcționalitatea de trimitere a emailurilor", ("link", "link-admin_smtp_system")),
                (" este configurată corect.", ("normal"))
            ],
            'admin_users': [
                ("Gestionare Utilizatori", "h1"),
                ("Această secțiune, accesibilă doar administratorilor, permite administrarea completă a conturilor de utilizator.", "normal"),
                ("Operațiuni Disponibile", "h2"),
                ("   • Adăugare:", "bold"),
                ("     Creați conturi noi, specificând numele de utilizator, parola inițială, numele complet și, obligatoriu, o adresă de email validă.", "list_item"),
                ("   • Modificare:", "bold"),
                ("     Editați detaliile unui utilizator existent, resetați-i parola, schimbați-i adresa de email sau ajustați-i permisiunile.", "list_item"),
                ("   • Activare/Dezactivare:", "bold"),
                ("     Puteți dezactiva temporar un cont fără a-l șterge, blocându-i accesul la aplicație. Acest lucru este util pentru angajații aflați în concediu sau pentru suspendări temporare.", "list_item"),
                ("   • Ștergere:", "bold"),
                ("     Eliminați permanent un cont de utilizator. Această acțiune este ireversibilă.", "list_item"),
                ("   • Atribuire Roluri și Conturi:", "bold"),
                ("     Pentru fiecare utilizator, puteți selecta multiple ", ("list_item")),
                ("roluri", ("link", "link-admin_roles")),
                (" pentru a-i defini permisiunile, și multiple ", ("list_item")),
                ("conturi bancare", ("link", "link-admin_accounts")),
                (" la care va avea acces.", ("list_item"))
            ],
            'admin_roles': [
                ("Gestionare Roluri și Permisiuni", "h1"),
                ("Rolurile sunt pachete de permisiuni care definesc ce acțiuni poate efectua un utilizator. Acest sistem granular permite un control strict asupra accesului la date și funcționalități.", "normal"),
                ("Managementul Rolurilor", "h2"),
                ("Puteți crea, redenumi sau șterge roluri. De exemplu, puteți crea un rol 'Contabil' care are doar permisiuni de vizualizare și export, și un rol 'Manager' care poate vedea și rapoarte.", "normal"),
                ("Permisiuni Detaliate", "h2"),
                ("Fiecare rol poate avea o combinație specifică de permisiuni, grupate pe categorii:", "normal"),
                ("   • Gestiune Utilizatori și Roluri: Cine poate crea și modifica conturi de utilizator sau alte roluri.", "list_item"),
                ("   • Operațiuni cu Date: Cine poate importa fișiere MT940 sau exporta date în Excel.", "list_item"),
                ("   • Rapoarte și Analiză: Cine poate genera diverse tipuri de rapoarte financiare.", "list_item"),
                ("   • Configurare și Jurnale: Cine poate vedea jurnalele de audit sau modifica setările aplicației.", "list_item"),
                ("", "normal"),
                ("Rolul implicit 'Administrator' are toate permisiunile și nu poate fi modificat sau șters. Acest lucru asigură că există întotdeauna cel puțin un super-utilizator în sistem.", ("note", "bold"))
            ],
            'admin_smtp_system': [
                ("Configurare Email de Sistem (SMTP)", "h1"),
                ("Această secțiune permite unui administrator să configureze un cont de email centralizat, pe care sistemul îl va folosi pentru a trimite automat emailuri, cum ar fi cele pentru resetarea parolei.", "normal"),
                ("Accesare Configurare", "h2"),
                ("Navigați la 'Administrare' -> 'Gestionare Utilizatori...'. În fereastra care apare, apăsați pe butonul 'Setări Email Sistem'.", "normal"),
                ("Câmpuri Necesare", "h2"),
                ("Pentru o configurare corectă, trebuie să completați următoarele câmpuri cu datele furnizate de provider-ul dumneavoastră de email (ex: Google, Microsoft 365, serverul propriu):", "normal"),
                ("   • Host SMTP: Adresa serverului de email (ex: 'smtp.gmail.com').", "list_item"),
                ("   • Port: Portul folosit de server (ex: 587 pentru TLS, 465 pentru SSL).", "list_item"),
                ("   • Utilizator (Email): Adresa de email completă a contului care va trimite mesajele.", "list_item"),
                ("   • Parolă: Parola contului de email. Pentru servicii precum Gmail, este posibil să fie necesară o 'Parolă de Aplicație' specială.", "list_item"),
                ("   • Adresă Expeditor: Adresa de email care va apărea ca expeditor (de obicei, aceeași cu utilizatorul).", "list_item"),
                ("   • Utilizează TLS: Această opțiune ar trebui să fie bifată pentru majoritatea serverelor moderne pentru a asigura o conexiune securizată.", "list_item")
            ],
            # Alte secțiuni (am omis conținutul lor pentru concizie, dar structura arată cum se leagă)
            'viewer_ui': [("Interfața Principală BTExtras Viewer", "h1"), ("...", "normal")],
            'viewer_ops': [("Operațiuni cu Date", "h1"), ("...", "normal")],
            'viewer_reports': [("Rapoarte și Analiză", "h1"), ("...", "normal")],
            'chat': [("BTExtras Chat", "h1"), ("...", "normal")],
            'admin_accounts': [("Gestionare Conturi Bancare", "h1"), ("...", "normal")],
            'about': [("Despre Aplicație", "h1"), (f"Versiune: {APP_VERSION}", "normal")]
        }