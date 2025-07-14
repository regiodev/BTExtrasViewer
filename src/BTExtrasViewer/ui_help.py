# BTExtrasViewer/ui_help.py - VERSIUNE FINALĂ

import tkinter as tk
from tkinter import ttk, scrolledtext
from common.app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, GLOBAL_HOTKEY_VIEWER, GLOBAL_HOTKEY_CHAT

class HelpDialog(tk.Toplevel):
    """
    Fereastră de dialog care afișează un ghid de utilizare complet și formatat
    pentru suita de aplicații BTExtras.
    """
    def __init__(self, parent, initial_topic_id='welcome'):
        super().__init__(parent)
        self.title(f"Ghid de Utilizare - {APP_NAME}")
        self.geometry("900x700")
        self.minsize(600, 500)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._configure_tags()
        self._populate_content()
        
        # Facem textul non-editabil după ce a fost inserat
        self.text_area.config(state=tk.DISABLED)

        self.center_window()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Navigăm la topicul inițial, dacă este specificat
        if initial_topic_id != 'welcome':
            # Folosim 'after' pentru a ne asigura că fereastra este complet desenată
            self.after(100, lambda: self.scroll_to_topic(initial_topic_id))

    def scroll_to_topic(self, topic_id):
        """Derulează fereastra la tag-ul specificat."""
        try:
            # Folosim un tag unic pentru a marca începutul fiecărui topic
            self.text_area.see(f"topic_{topic_id}.first")
        except tk.TclError:
            print(f"Warning: Topic ID '{topic_id}' not found in help content.")

    def center_window(self):
        """Centrează fereastra de dialog relativ la fereastra principală."""
        self.update_idletasks()
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{max(0, position_x)}+{max(0, position_y)}")

    def _create_widgets(self):
        """Creează și aranjează widget-urile în fereastră."""
        main_frame = ttk.Frame(self, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Segoe UI", 10), relief=tk.FLAT, padx=15, pady=5)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        close_button = ttk.Button(main_frame, text="Închide", command=self.destroy)
        close_button.pack(pady=(10, 5))

    def _configure_tags(self):
        """Definește stilurile (culori, fonturi) pentru formatarea textului."""
        # Titluri
        self.text_area.tag_configure('h1', font=('Segoe UI', 16, 'bold'), foreground='#2c3e50', spacing3=15, justify='center')
        self.text_area.tag_configure('h2', font=('Segoe UI', 13, 'bold'), foreground='#34495e', spacing3=10, lmargin1=10)
        self.text_area.tag_configure('h3', font=('Segoe UI', 11, 'bold'), foreground='#2980b9', spacing3=8, lmargin1=20)
        
        # Stiluri de text
        self.text_area.tag_configure('bold', font=('Segoe UI', 10, 'bold'))
        self.text_area.tag_configure('italic', font=('Segoe UI', 10, 'italic'))
        self.text_area.tag_configure('code', font=('Consolas', 10), background='#ecf0f1', relief=tk.RAISED, borderwidth=1, lmargin1=30, lmargin2=30, rmargin=30)
        
        # Culori pentru evidențiere
        self.text_area.tag_configure('highlight_blue', foreground='#2980b9')
        self.text_area.tag_configure('highlight_green', foreground='#27ae60')
        self.text_area.tag_configure('highlight_red', foreground='#c0392b')
        
        # Paragrafe și liste
        self.text_area.tag_configure('paragraph', lmargin1=20, spacing1=5)
        self.text_area.tag_configure('bullet', lmargin1=35, lmargin2=55)
        
        # Copyright
        self.text_area.tag_configure('copyright', justify='center', font=('Segoe UI', 8, 'italic'), foreground='gray', spacing1=20)

    def _insert(self, text, tags=None):
        """Metodă ajutătoare pentru a insera text cu tagurile specificate."""
        self.text_area.insert(tk.END, text, tags)

    def _populate_content(self):
        """Construiește și inserează conținutul complet al ghidului de utilizare."""
        
        self._insert(f"{APP_NAME} - Ghid de Utilizare\n", ('h1', 'topic_welcome'))
        
        self._insert("Bun venit în ghidul de utilizare pentru suita de aplicații BTExtras. Acest document vă va oferi o imagine de ansamblu completă asupra funcționalităților și modului de operare al aplicației.\n\n", 'paragraph')
        
        # --- Secțiunea 1 ---
        self._insert("1. Arhitectura Aplicației\n", ('h2', 'topic_architecture'))
        self._insert("Suita BTExtras este compusă din trei componente principale care lucrează împreună:\n", 'paragraph')
        self._insert(" • Session Manager: ", ('bullet', 'bold'))
        self._insert("Rulează în fundal și apare ca o iconiță în System Tray (lângă ceas). Gestionează pornirea și oprirea celorlalte module și ascultă după combinațiile de taste globale.\n", 'bullet')
        self._insert(" • BTExtrasViewer: ", ('bullet', 'bold'))
        self._insert("Este aplicația principală pentru vizualizarea, importul, filtrarea și generarea de rapoarte pe baza extraselor bancare.\n", 'bullet')
        self._insert(" • BTExtrasChat: ", ('bullet', 'bold'))
        self._insert("Un modul de chat securizat, integrat, care permite comunicarea între utilizatorii definiți în sistem.\n", 'bullet')

        # --- Secțiunea 2 ---
        self._insert("\n2. Ghid de Utilizare - BTExtrasViewer\n", ('h2', 'topic_viewer'))
        
        self._insert("2.1. Autentificare și Securitate\n", 'h3')
        self._insert("Accesul în aplicație este securizat pe bază de ", 'paragraph')
        self._insert("utilizator", ('bold', 'highlight_blue'))
        self._insert(" și ", 'paragraph')
        self._insert("parolă", ('bold', 'highlight_blue'))
        self._insert(". Drepturile fiecărui utilizator sunt definite de rolurile care îi sunt atribuite. Parolele sunt stocate în baza de date folosind metode de hashing securizate (pbkdf2_hmac cu salt), asigurând confidențialitatea acestora.\n", 'paragraph')
        self._insert("Resetarea Parolei: ", ('paragraph', 'bold'))
        self._insert("Dacă ați uitat parola, puteți folosi linkul 'Am uitat parola...' din fereastra de login. Veți primi un cod de resetare pe adresa de email asociată contului. Această funcționalitate necesită configurarea SMTP de către un administrator.\n", 'paragraph')
        
        self._insert("2.2. Fereastra Principală\n", 'h3')
        self._insert("Interfața principală este împărțită în următoarele zone:\n", 'paragraph')
        self._insert(" • Meniul Principal: ", ('bullet', 'bold'))
        self._insert("Conține toate acțiunile disponibile, grupate logic (Fișier, Administrare, Rapoarte, Ajutor).\n", 'bullet')
        self._insert(" • Panoul de Filtre: ", ('bullet', 'bold'))
        self._insert("Permite filtrarea rapidă a tranzacțiilor afișate. Puteți filtra după cont, perioadă (interval calendaristic sau navigare ierarhică an/lună/zi), tipul tranzacției (credit/debit) și puteți căuta un text specific (exact sau parțial) în diverse coloane.\n", 'bullet')
        self._insert(" • Lista de Tranzacții: ", ('bullet', 'bold'))
        self._insert("Afișează tranzacțiile conform filtrelor aplicate. Puteți redimensiona și sorta coloanele, iar setările se salvează pentru fiecare utilizator.\n", 'bullet')
        self._insert(" • Bara de Stare: ", ('bullet', 'bold'))
        self._insert("Afișează informații utile: starea conexiunii DB, contul activ, numărul de tranzacții afișate și totalurile pentru acestea.\n", 'bullet')
        
        self._insert("2.3. Importul și Exportul Datelor\n", 'h3')
        self._insert("Import (fișiere MT940): ", ('paragraph', 'bold'))
        self._insert("Aplicația permite importul tranzacțiilor din fișiere standard ", 'paragraph')
        self._insert("MT940", ('bold', 'highlight_green'))
        self._insert(". La import, aplicația încearcă să asocieze automat fișierul cu un cont pe baza IBAN-ului. Dacă nu găsește o potrivire, permite utilizatorului să aleagă contul țintă.\n", 'paragraph')
        self._insert("Export Excel: ", ('paragraph', 'bold'))
        self._insert("Butonul 'Export Excel' salvează pe disc un fișier .xlsx ce conține lista de tranzacții exact așa cum este afișată și filtrată în fereastra principală.\n", 'paragraph')
        self._insert("Export pe Email: ", ('paragraph', 'bold'))
        self._insert("Butonul 'Export pe email' generează același fișier Excel și îl atașează unui email nou, permițând trimiterea rapidă către un destinatar.\n", 'paragraph')

        self._insert("2.4. Generarea de Rapoarte\n", ('h3', 'topic_reports'))
        self._insert("Trei tipuri de rapoarte sunt disponibile din meniul 'Rapoarte':\n", 'paragraph')
        self._insert(" • Flux de Numerar (Cash Flow): ", ('bullet', 'bold'))
        self._insert("Prezintă un grafic și un tabel cu totalul încasărilor și plăților, grupate zilnic sau lunar, pentru un cont și o perioadă selectată.\n", 'bullet')
        self._insert(" • Evoluție Sold: ", ('bullet', 'bold'))
        self._insert("Generează un grafic liniar care arată evoluția soldului unui cont în timp, la o granularitate zilnică, lunară sau anuală.\n", 'bullet')
        self._insert(" • Analiză Detaliată a Tranzacțiilor: ", ('bullet', 'bold'))
        self._insert("Oferă o vizualizare detaliată, sub formă de grafic și tabel, a sumelor agregate pe coduri de tranzacție și pe perioade (zilnic, lunar, anual).\n", 'bullet')
        self._insert("Toate rapoartele pot fi exportate în format ", 'paragraph')
        self._insert("PDF", ('highlight_red', 'bold'))
        self._insert(" sau ", 'paragraph')
        self._insert("Excel", ('highlight_green', 'bold'))
        self._insert(" și pot fi trimise direct pe email ca atașament PDF.\n", 'paragraph')
        
        # --- Secțiunea 3 ---
        self._insert("\n3. Administrarea Sistemului\n", ('h2', 'topic_admin'))
        self._insert("Secțiunea de Administrare este accesibilă doar utilizatorilor cu permisiunile corespunzătoare (de obicei, rolul 'Administrator').\n", 'paragraph')
        
        self._insert("3.1. Gestionare Utilizatori\n", 'h3')
        self._insert("Fereastra permite administratorilor să:\n", 'paragraph')
        self._insert(" • Adauge utilizatori noi ", ('bullet', 'highlight_green'))
        self._insert("(specificând username, nume complet, email, parolă).\n", 'bullet')
        self._insert(" • Editeze utilizatorii existenți, să le asigneze roluri și conturi bancare specifice.\n", 'bullet')
        self._insert(" • Activeze, dezactiveze sau să șteargă permanent ", ('bullet', 'highlight_red'))
        self._insert("un cont de utilizator.\n", 'bullet')

        self._insert("3.2. Gestionare Roluri și Permisiuni\n", 'h3')
        self._insert("Acesta este centrul sistemului de securitate. Aici se pot crea roluri noi (ex: Contabil), redenumi sau șterge roluri existente și, cel mai important, se pot atribui ", 'paragraph')
        self._insert("permisiuni granulare", ('bold'))
        self._insert(" fiecărui rol, bifând exact ce acțiuni poate efectua un utilizator.\n", 'paragraph')
        
        self._insert("3.3. Gestionare Conturi Bancare\n", 'h3')
        self._insert("Permite adăugarea, modificarea sau ștergerea conturilor bancare. Un cont nu poate fi șters dacă are tranzacții asociate. Se poate personaliza o ", 'paragraph')
        self._insert("culoare", ('bold'))
        self._insert(" pentru fiecare cont.\n", 'paragraph')
        
        self._insert("3.4. Alte Configurări Administrative\n", 'h3')
        self._insert(" • Setări Email Sistem: ", ('bullet', 'bold'))
        self._insert("Configurarea serverului SMTP folosit de sistem pentru a trimite emailuri de resetare a parolei. Esențial pentru funcționalitatea 'Am uitat parola...'.\n", 'bullet')
        self._insert(" • Configurează SMTP (Email): ", ('bullet', 'bold'))
        self._insert("Permite fiecărui utilizator (cu permisiune) să își configureze propriul server SMTP pentru a trimite rapoarte și exporturi.\n", 'bullet')
        self._insert(" • Gestionare Tipuri Tranzacții: ", ('bullet', 'bold'))
        self._insert("Permite modificarea descrierilor personalizate pentru codurile de tranzacție (ex: 'NTRF') și setarea vizibilității acestora în liste și rapoarte (setare per utilizator).\n", 'bullet')
        self._insert(" • Gestionare Descrieri Standard SWIFT: ", ('bullet', 'bold'))
        self._insert("Modificarea descrierilor standard asociate codurilor SWIFT (ex: 'CHG' -> 'Taxe si alte cheltuieli').\n", 'bullet')
        self._insert(" • Gestionare Valute: ", ('bullet', 'bold'))
        self._insert("Administrarea listei de valute disponibile la crearea/editarea conturilor bancare.\n", 'bullet')
        
        # --- Secțiunea 4 ---
        self._insert("\n4. Combinații de Taste și Informații\n", ('h2', 'topic_about'))
        self._insert("Pentru un acces rapid, puteți folosi următoarele combinații de taste globale (funcționează oriunde în Windows, dacă Session Manager rulează):\n", 'paragraph')
        self._insert(f" • Deschide BTExtrasViewer: ", ('bullet', 'bold'))
        self._insert(f" {GLOBAL_HOTKEY_VIEWER} \n", ('bullet', 'code'))
        self._insert(f" • Deschide BTExtrasChat: ", ('bullet', 'bold'))
        self._insert(f" {GLOBAL_HOTKEY_CHAT} \n", ('bullet', 'code'))
        
        self._insert("\n\n\n\n") # Spațiu liber
        self._insert(f"{APP_COPYRIGHT}\n", 'copyright')