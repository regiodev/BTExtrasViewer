# BTExtrasViewer/ui_help.py

import tkinter as tk
from tkinter import ttk, scrolledtext
from common.app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, GLOBAL_HOTKEY_VIEWER, GLOBAL_HOTKEY_CHAT

class HelpDialog(tk.Toplevel):
    def __init__(self, parent, initial_tab=0):
        super().__init__(parent)
        self.title(f"Ajutor - {APP_NAME}")
        self.geometry("750x600")
        self.minsize(600, 450)
        self.transient(parent)
        self.grab_set()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # Crearea tab-urilor cu conținut
        self._create_tab("Introducere", self._get_intro_text())
        self._create_tab("Interfața Principală", self._get_main_ui_text())
        self._create_tab("Import & Export", self._get_import_export_text())
        self._create_tab("Rapoarte", self._get_reports_text())
        self._create_tab("Utilizatori și Roluri", self._get_security_text())
        self._create_tab("Chat & Comenzi Rapide", self._get_chat_hotkeys_text())
        self._create_tab("Despre", self._get_about_text())
        
        # Selectarea tab-ului inițial
        self.notebook.select(initial_tab)

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

    def _create_tab(self, title, content):
        """Creează un tab și adaugă conținutul formatat."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)

        st = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state="disabled", font=("TkDefaultFont", 10))
        st.pack(expand=True, fill="both")

        # Configurarea tag-urilor pentru formatare
        st.tag_configure("h1", font=("TkDefaultFont", 14, "bold"), spacing3=10)
        st.tag_configure("h2", font=("TkDefaultFont", 11, "bold"), spacing1=15, spacing3=5)
        st.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        st.tag_configure("italic", font=("TkDefaultFont", 9, "italic"))
        st.tag_configure("code", font=("Courier New", 9), background="#f0f0f0")

        # Adăugarea conținutului
        st.config(state="normal")
        for line, tags in content:
            st.insert(tk.END, line + "\n", tags)
        st.config(state="disabled")

    # --- Texte pentru fiecare secțiune de ajutor ---

    def _get_intro_text(self):
        return [
            (f"Bun venit la {APP_NAME}!", "h1"),
            (f"Această suită de aplicații este o soluție completă pentru gestiunea, vizualizarea și analiza extraselor de cont în format MT940. Oferă un mediu securizat, multi-utilizator, cu datele centralizate pe un server de baze de date MariaDB/MySQL.", "normal"),
            ("Sistemul este compus din trei componente principale:", "normal"),
            ("   • Session Manager: Piesa centrală care rulează în fundal și oferă acces rapid la celelalte module.", "normal"),
            ("   • BTExtras Viewer: Aplicația principală pentru vizualizarea tranzacțiilor, filtrare și generare de rapoarte.", "normal"),
            ("   • BTExtras Chat: O aplicație de comunicare internă între utilizatorii sistemului.", "normal"),
            ("Folosiți tab-urile de mai sus pentru a explora în detaliu fiecare funcționalitate.", "italic")
        ]
        
    def _get_main_ui_text(self):
        return [
            ("Interfața Principală (Viewer)", "h1"),
            ("Fereastra principală este împărțită în mai multe zone cheie:", "normal"),
            ("Navigare Perioadă", "h2"),
            ("În panoul din stânga, aveți un arbore de navigare ierarhic. Puteți selecta un an, o lună sau o zi pentru a filtra rapid tranzacțiile afișate în lista principală.", "normal"),
            ("Filtre și Acțiuni", "h2"),
            ("Deasupra listei de tranzacții se află controalele principale:", "normal"),
            ("   • Cont Bancar Activ: Alegeți contul ale cărui tranzacții doriți să le vizualizați.", "normal"),
            ("   • Butoane Rapoarte: Acces rapid pentru a genera rapoartele 'Analiză Cash Flow', 'Evoluție Sold' și 'Analiză Tranzacții'.", "normal"),
            ("   • Interval Dată Specific: Permite filtrarea tranzacțiilor între două date calendaristice, independent de selecția din arborele de navigare.", "normal"),
            ("   • Căutare: Căutați un text specific în toate coloanele sau într-o coloană selectată. Puteți bifa 'Căutare exactă' pentru potriviri perfecte.", "normal"),
            ("Lista de Tranzacții", "h2"),
            ("Afișează toate tranzacțiile conform filtrelor active. Puteți sorta datele dând click pe antetul unei coloane. Un dublu-click pe o tranzacție va deschide o fereastră cu toate detaliile acesteia, unde puteți edita câmpul de observații.", "normal")
        ]

    def _get_import_export_text(self):
        return [
            ("Import și Export", "h1"),
            ("Import fișiere MT940", "h2"),
            ("Aplicația permite importul unuia sau mai multor fișiere MT940 simultan.", "normal"),
            ("   1. Apăsați butonul 'Importă fișier MT940'.", "normal"),
            ("   2. Selectați fișierele dorite.", "normal"),
            ("   3. Sistemul va încerca să identifice automat contul bancar pe baza IBAN-ului din fișier.", "normal"),
            ("   4. Dacă IBAN-ul nu este găsit, veți fi rugat să asociați manual fișierul unui cont existent sau să creați un cont nou.", "normal"),
            ("   5. Tranzacțiile duplicat sunt ignorate automat pentru a menține integritatea datelor.", "normal"),
            ("Export în Excel și PDF", "h2"),
            ("Orice set de date afișat în lista principală (după aplicarea filtrelor) poate fi exportat în format Excel (.xlsx) folosind butonul 'Exportă în Excel'.", "normal"),
            ("Fiecare raport generat în aplicație are, de asemenea, propriile butoane pentru a exporta rezultatele detaliate în format Excel sau PDF.", "normal")
        ]

    def _get_reports_text(self):
        return [
            ("Generarea de Rapoarte", "h1"),
            ("Suita oferă trei tipuri de rapoarte puternice, accesibile din meniul 'Rapoarte' sau din butoanele de acțiuni rapide.", "normal"),
            ("Analiză Flux de Numerar (Cash Flow)", "h2"),
            ("Acest raport oferă o imagine clară a intrărilor și ieșirilor totale, grupate lunar sau zilnic. Afișează un grafic cu bare pentru a compara vizual încasările și plățile, precum și un tabel sumar.", "normal"),
            ("Evoluție Sold Cont", "h2"),
            ("Generează un grafic liniar care arată cum a evoluat soldul unui cont selectat pe o perioadă de timp specificată. Este util pentru a observa tendințele pe termen lung.", "normal"),
            ("Analiză Detaliată Tranzacții", "h2"),
            ("Cel mai complex raport, care grupează tranzacțiile după codul lor tehnic (ex: 'NTRF', 'CMI') și le afișează într-un grafic cu bare stivuite. Permite o analiză fină a tipurilor de operațiuni care contribuie la fluxul de numerar.", "normal")
        ]

    def _get_security_text(self):
        return [
            ("Utilizatori, Roluri și Permisiuni", "h1"),
            ("Sistemul de securitate este granular și controlează accesul la funcționalități și date.", "normal"),
            ("Roluri", "h2"),
            ("Fiecare utilizator are unul sau mai multe roluri (ex: Administrator, Operator Date). Un rol este un set predefinit de permisiuni.", "normal"),
            ("Permisiuni pe Funcționalități", "h2"),
            ("Rolurile dictează ce butoane și meniuri sunt vizibile sau active pentru un utilizator. De exemplu, doar un utilizator cu permisiunea 'manage_users' poate accesa fereastra de gestionare a utilizatorilor.", "normal"),
            ("Permisiuni pe Date", "h2"),
            ("Securitatea se aplică și la nivel de date:", "normal"),
            ("   • Acces la Conturi: Unui utilizator i se pot asigna doar anumite conturi bancare. Acesta nu va putea vedea sau interacționa cu tranzacțiile din alte conturi.", "normal"),
            ("   • Acces la Tranzacții: Unui utilizator i se poate restricționa accesul pentru a vedea doar tranzacțiile de tip 'credit', doar cele de tip 'debit' sau ambele.", "normal")
        ]

    def _get_chat_hotkeys_text(self):
        return [
            ("Chat și Comenzi Rapide", "h1"),
            ("Comunicare Integrată", "h2"),
            ("Aplicația BTExtras Chat permite comunicarea în timp real între utilizatorii conectați la sistem. Puteți purta conversații private sau puteți crea grupuri de discuții. Statusul online al utilizatorilor este afișat în lista de conversații.", "normal"),
            ("Comenzi Rapide Globale (Hotkeys)", "h2"),
            ("Chiar dacă ferestrele aplicațiilor sunt închise sau în plan secund, puteți folosi următoarele combinații de taste pentru a le aduce rapid în prim-plan:", "normal"),
            (f"   • Deschide/Afișează BTExtras Viewer: ", "normal"),
            (f"     {GLOBAL_HOTKEY_VIEWER.upper()}", "code"),
            (f"   • Deschide/Afișează BTExtras Chat: ", "normal"),
            (f"     {GLOBAL_HOTKEY_CHAT.upper()}", "code")
        ]

    def _get_about_text(self):
        return [
            (f"{APP_NAME}", "h1"),
            (f"Versiune: {APP_VERSION}", "bold"),
            (APP_COPYRIGHT, "normal"),
            ("Această suită software este o soluție comercială dezvoltată de Regio Development.", "italic"),
            ("", "normal"),
            ("Pentru suport tehnic sau informații comerciale, vă rugăm să ne contactați:", "h2"),
            ("   • Email: office@regio-development.ro", "normal"),
            ("   • Web: https://regio-cloud.ro/software", "normal")
        ]