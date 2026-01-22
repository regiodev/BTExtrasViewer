# BTExtrasViewer/help_content.py
# Conținut structurat pentru sistemul de Help

from common.app_constants import (
    APP_NAME, APP_VERSION, GLOBAL_HOTKEY_VIEWER, GLOBAL_HOTKEY_CHAT
)

# Structura ierarhică a secțiunilor de help
# Fiecare secțiune are: title, icon, content, children (optional), see_also (optional)

HELP_SECTIONS = {
    # ===== PAGINA PRINCIPALĂ =====
    "welcome": {
        "title": "Bun venit",
        "icon": "🏠",
        "content": f"""
<h1>Bun venit în {APP_NAME}</h1>

<p>{APP_NAME} este o suită completă de aplicații pentru gestionarea și analiza extraselor de cont bancare. Aplicația vă permite să importați, vizualizați, filtrați și să generați rapoarte detaliate asupra tranzacțiilor bancare.</p>

<tip>Folosiți combinația de taste <kbd>{GLOBAL_HOTKEY_VIEWER.upper()}</kbd> pentru a deschide rapid aplicația de oriunde din Windows!</tip>

<h2>Capitole principale</h2>

<link id="introduction">Introducere și Prezentare Generală</link>
<link id="authentication">Autentificare și Securitate</link>
<link id="transactions">Gestionarea Tranzacțiilor</link>
<link id="navigation">Navigare și Filtre</link>
<link id="import">Import Date</link>
<link id="export">Export Date</link>
<link id="reports">Rapoarte și Analize</link>
<link id="administration">Administrare Sistem</link>
<link id="shortcuts">Comenzi Rapide</link>
<link id="troubleshooting">Depanare</link>
""",
        "children": ["introduction", "authentication", "transactions", "navigation",
                     "import", "export", "reports", "administration", "shortcuts", "troubleshooting"]
    },

    # ===== INTRODUCERE =====
    "introduction": {
        "title": "Introducere",
        "icon": "📖",
        "content": """
<h1>Introducere</h1>

<p>BTExtras Suite este o suită profesională de aplicații desktop concepută pentru gestionarea și analiza extraselor de cont bancare în format MT940.</p>

<h2>Ce puteți face cu BTExtras Suite?</h2>

<bullet>Importați automat extrase bancare în format MT940</bullet>
<bullet>Vizualizați și filtrați tranzacțiile după multiple criterii</bullet>
<bullet>Generați rapoarte detaliate (Flux de Numerar, Evoluție Sold, Analize)</bullet>
<bullet>Exportați date în Excel sau trimiteți pe email</bullet>
<bullet>Gestionați mai multe conturi bancare și valute</bullet>
<bullet>Administrați utilizatori cu sistem de roluri și permisiuni</bullet>
""",
        "children": ["overview", "architecture", "requirements", "first_start"],
        "see_also": ["authentication", "transactions"]
    },

    "overview": {
        "title": "Prezentare generală",
        "icon": "📋",
        "content": f"""
<h1>Prezentare generală</h1>

<p><b>{APP_NAME}</b> versiunea <b>{APP_VERSION}</b> este componenta principală a suitei BTExtras, dedicată vizualizării și gestionării extraselor de cont bancare.</p>

<h2>Funcționalități principale</h2>

<bullet><b>Import MT940</b> - Importați automat fișiere în format bancar standard MT940</bullet>
<bullet><b>Vizualizare tranzacții</b> - Listare completă cu sortare și filtrare avansată</bullet>
<bullet><b>Rapoarte</b> - Generați rapoarte de flux de numerar, evoluție sold și analize detaliate</bullet>
<bullet><b>Export</b> - Exportați date în format Excel (.xlsx) sau trimiteți direct pe email</bullet>
<bullet><b>Multi-cont</b> - Gestionați simultan mai multe conturi bancare în diverse valute</bullet>
<bullet><b>Securitate</b> - Sistem complet de roluri și permisiuni pentru control acces</bullet>

<note>Aplicația funcționează împreună cu Session Manager, care rulează în fundal și oferă acces rapid prin combinații de taste globale.</note>
""",
        "see_also": ["architecture", "requirements"]
    },

    "architecture": {
        "title": "Arhitectura aplicației",
        "icon": "🏗️",
        "content": f"""
<h1>Arhitectura aplicației</h1>

<p>Suita BTExtras este compusă din trei componente principale care lucrează împreună:</p>

<h2>Session Manager</h2>
<p>Rulează în fundal și apare ca o iconiță în System Tray (zona de notificări, lângă ceas). Gestionează pornirea și oprirea celorlalte module și ascultă după combinațiile de taste globale.</p>

<h2>BTExtrasViewer</h2>
<p>Este aplicația principală pentru vizualizarea, importul, filtrarea și generarea de rapoarte pe baza extraselor bancare. Aceasta este aplicația pe care o folosiți în prezent.</p>

<h2>BTExtrasChat</h2>
<p>Un modul de chat securizat, integrat, care permite comunicarea între utilizatorii definiți în sistem.</p>

<tip>Toate cele trei componente folosesc aceeași bază de date centralizată și partajează sistemul de autentificare.</tip>

<h2>Comunicare inter-proces</h2>
<p>Componentele comunică între ele prin conexiuni TCP locale, permițând Session Manager-ului să controleze ciclul de viață al celorlalte aplicații și să transmită comenzi (ex: afișare fereastră).</p>
""",
        "see_also": ["shortcuts", "overview"]
    },

    "requirements": {
        "title": "Cerințe de sistem",
        "icon": "💻",
        "content": """
<h1>Cerințe de sistem</h1>

<h2>Sistem de operare</h2>
<bullet>Windows 10 sau mai recent (recomandat)</bullet>
<bullet>Windows 7/8.1 (suportat cu limitări)</bullet>

<h2>Hardware minim</h2>
<bullet>Procesor: 1 GHz sau mai rapid</bullet>
<bullet>Memorie RAM: 2 GB (recomandat 4 GB)</bullet>
<bullet>Spațiu pe disc: 200 MB pentru aplicație</bullet>
<bullet>Rezoluție ecran: minimum 1280x720</bullet>

<h2>Software necesar</h2>
<bullet><b>Bază de date:</b> MariaDB 10.5+ sau MySQL 5.7+</bullet>
<bullet><b>Conexiune rețea:</b> Pentru acces la baza de date (local sau rețea)</bullet>

<note>La prima pornire, aplicația va solicita datele de conectare la baza de date. Asigurați-vă că aveți aceste informații la îndemână.</note>
""",
        "see_also": ["first_start", "db_config"]
    },

    "first_start": {
        "title": "Prima pornire",
        "icon": "🚀",
        "content": """
<h1>Prima pornire și configurare</h1>

<h2>Pasul 1: Configurare bază de date</h2>
<p>La prima pornire, aplicația va afișa un dialog pentru configurarea conexiunii la baza de date. Introduceți:</p>
<bullet><b>Server:</b> Adresa serverului de baze de date (ex: localhost sau IP)</bullet>
<bullet><b>Port:</b> Portul MySQL/MariaDB (implicit: 3306)</bullet>
<bullet><b>Bază de date:</b> Numele bazei de date (ex: btextras_db)</bullet>
<bullet><b>Utilizator:</b> Numele utilizatorului de baze de date</bullet>
<bullet><b>Parolă:</b> Parola pentru baza de date</bullet>

<h2>Pasul 2: Autentificare</h2>
<p>După conectarea reușită la baza de date, va apărea fereastra de autentificare.</p>

<warning>La prima instalare, se creează automat un cont de administrator cu:<br/>
<b>Utilizator:</b> admin<br/>
<b>Parolă:</b> admin123<br/>
<br/>
<b>IMPORTANT:</b> Schimbați această parolă imediat după prima autentificare!</warning>

<h2>Pasul 3: Configurare inițială</h2>
<p>După autentificare, vă recomandăm să:</p>
<bullet>Schimbați parola implicită de administrator</bullet>
<bullet>Adăugați conturile bancare pe care le veți gestiona</bullet>
<bullet>Creați utilizatori suplimentari dacă este cazul</bullet>
<bullet>Configurați setările SMTP pentru funcționalitatea de email</bullet>
""",
        "see_also": ["authentication", "account_management", "user_management"]
    },

    # ===== AUTENTIFICARE =====
    "authentication": {
        "title": "Autentificare",
        "icon": "🔐",
        "content": """
<h1>Autentificare și Securitate</h1>

<p>Accesul în aplicație este securizat pe bază de <b>utilizator</b> și <b>parolă</b>. Drepturile fiecărui utilizator sunt definite de rolurile care îi sunt atribuite.</p>

<h2>Securitatea parolelor</h2>
<p>Parolele sunt stocate în baza de date folosind metode de hashing securizate (PBKDF2 cu salt și 390.000 de iterații), asigurând confidențialitatea acestora. Nimeni, nici măcar administratorii, nu pot vedea parolele originale.</p>

<tip>Folosiți parole complexe care conțin litere mari și mici, cifre și caractere speciale.</tip>
""",
        "children": ["login", "password_reset", "change_password"],
        "see_also": ["user_management", "role_management"]
    },

    "login": {
        "title": "Conectare",
        "icon": "🔑",
        "content": """
<h1>Conectare la aplicație</h1>

<p>Pentru a vă autentifica în aplicație:</p>

<bullet>Introduceți <b>numele de utilizator</b> în primul câmp</bullet>
<bullet>Introduceți <b>parola</b> în al doilea câmp</bullet>
<bullet>Apăsați butonul <b>Conectare</b> sau tasta <b>Enter</b></bullet>

<h2>Probleme la autentificare?</h2>

<bullet>Verificați că ați introdus corect numele de utilizator (sensibil la majuscule/minuscule)</bullet>
<bullet>Verificați că tasta Caps Lock nu este activată</bullet>
<bullet>Dacă ați uitat parola, folosiți opțiunea "Am uitat parola..."</bullet>
<bullet>Contactați administratorul dacă contul vă este dezactivat</bullet>

<note>După 3 încercări consecutive de autentificare eșuate, contul poate fi blocat temporar pentru securitate.</note>
""",
        "see_also": ["password_reset", "change_password"]
    },

    "password_reset": {
        "title": "Resetare parolă",
        "icon": "📧",
        "content": """
<h1>Resetare parolă uitată</h1>

<p>Dacă ați uitat parola, puteți solicita resetarea acesteia urmând pașii de mai jos:</p>

<h2>Procedură de resetare</h2>

<bullet>În fereastra de autentificare, apăsați pe linkul <b>"Am uitat parola..."</b></bullet>
<bullet>Introduceți adresa de email asociată contului dumneavoastră</bullet>
<bullet>Veți primi un email cu un cod de resetare (valid 15 minute)</bullet>
<bullet>Introduceți codul primit și setați o nouă parolă</bullet>

<warning>Această funcționalitate necesită configurarea SMTP de către un administrator. Dacă nu primiți emailul, contactați administratorul sistemului.</warning>

<h2>Nu primiți emailul?</h2>
<bullet>Verificați folderul de Spam/Junk</bullet>
<bullet>Asigurați-vă că adresa de email este corectă în profil</bullet>
<bullet>Contactați administratorul pentru asistență</bullet>
""",
        "see_also": ["login", "smtp_system_config"]
    },

    "change_password": {
        "title": "Schimbare parolă",
        "icon": "🔄",
        "content": """
<h1>Schimbare parolă</h1>

<p>Puteți schimba parola în orice moment din meniu:</p>
<p><b>Fișier → Schimbă Parola...</b></p>

<h2>Procedură</h2>

<bullet>Introduceți parola curentă pentru verificare</bullet>
<bullet>Introduceți noua parolă</bullet>
<bullet>Confirmați noua parolă (reintroduceți-o)</bullet>
<bullet>Apăsați <b>Salvează</b></bullet>

<h2>Recomandări pentru o parolă sigură</h2>

<bullet>Minimum 8 caractere</bullet>
<bullet>Combinație de litere mari și mici</bullet>
<bullet>Includeți cifre și caractere speciale (!@#$%)</bullet>
<bullet>Evitați informații personale (nume, data nașterii)</bullet>
<bullet>Nu reutilizați parole de la alte conturi</bullet>

<tip>Schimbați parola periodic (la fiecare 3-6 luni) pentru securitate sporită.</tip>
""",
        "see_also": ["login", "password_reset"]
    },

    # ===== TRANZACȚII =====
    "transactions": {
        "title": "Tranzacții",
        "icon": "💳",
        "content": """
<h1>Gestionarea Tranzacțiilor</h1>

<p>Fereastra principală a aplicației afișează lista de tranzacții pentru contul selectat. Puteți vizualiza, filtra, căuta și analiza tranzacțiile în detaliu.</p>

<h2>Coloanele afișate</h2>

<bullet><b>Data</b> - Data efectuării tranzacției</bullet>
<bullet><b>Descriere</b> - Descrierea tranzacției din extras</bullet>
<bullet><b>Observații</b> - Note personalizate (editabile)</bullet>
<bullet><b>Suma</b> - Valoarea tranzacției</bullet>
<bullet><b>Tip</b> - Credit (intrare) sau Debit (ieșire)</bullet>
<bullet><b>CIF</b> - Codul fiscal al partenerului (dacă există)</bullet>
<bullet><b>Factură</b> - Numărul facturii asociate (dacă există)</bullet>
<bullet><b>Beneficiar</b> - Numele beneficiarului/plătitorului</bullet>

<tip>Puteți redimensiona coloanele trăgând de marginile antetului. Lățimile se salvează automat.</tip>
""",
        "children": ["view_transactions", "filter_transactions", "search_transactions", "transaction_details"],
        "see_also": ["navigation", "export"]
    },

    "view_transactions": {
        "title": "Vizualizare",
        "icon": "👁️",
        "content": """
<h1>Vizualizarea tranzacțiilor</h1>

<h2>Lista de tranzacții</h2>
<p>Tranzacțiile sunt afișate într-un tabel cu coloane configurabile. Fiecare rând reprezintă o tranzacție din extrasul bancar.</p>

<h2>Sortare</h2>
<p>Faceți click pe antetul unei coloane pentru a sorta după acea coloană. Click repetat alternează între sortare ascendentă și descendentă.</p>

<h2>Bara de stare</h2>
<p>În partea de jos a ferestrei veți găsi informații despre:</p>
<bullet>Starea conexiunii la baza de date</bullet>
<bullet>Contul bancar activ selectat</bullet>
<bullet>Numărul de tranzacții afișate</bullet>
<bullet>Totalul creditelor și debitelor pentru tranzacțiile afișate</bullet>

<h2>Culori și indicatori</h2>
<bullet><b>Verde</b> - Tranzacții de tip Credit (încasări)</bullet>
<bullet><b>Roșu</b> - Tranzacții de tip Debit (plăți)</bullet>

<tip>Dublu-click pe o tranzacție pentru a vizualiza toate detaliile acesteia.</tip>
""",
        "see_also": ["filter_transactions", "search_transactions"]
    },

    "filter_transactions": {
        "title": "Filtrare",
        "icon": "🔍",
        "content": """
<h1>Filtrarea tranzacțiilor</h1>

<p>Panoul de filtre din partea stângă a ferestrei permite restrângerea listei de tranzacții afișate.</p>

<h2>Filtrare după cont</h2>
<p>Selectați contul bancar dorit din lista derulantă din partea de sus. Puteți gestiona doar conturile pentru care aveți permisiuni.</p>

<h2>Filtrare după perioadă</h2>
<p>Există două moduri de filtrare temporală:</p>

<bullet><b>Navigare ierarhică</b> - Selectați an → lună → zi din arborele de navigare</bullet>
<bullet><b>Interval de date</b> - Bifați "Interval de date" și selectați data de început și sfârșit</bullet>

<h2>Filtrare după tip</h2>
<bullet><b>Toate</b> - Afișează atât credite cât și debite</bullet>
<bullet><b>Credit</b> - Doar încasări (sume intrate în cont)</bullet>
<bullet><b>Debit</b> - Doar plăți (sume ieșite din cont)</bullet>

<note>Unii utilizatori pot avea restricții de vizualizare (doar credit sau doar debit) configurate de administrator.</note>

<h2>Resetare filtre</h2>
<p>Butonul <b>Resetează filtre</b> readuce toate filtrele la valorile implicite.</p>
""",
        "see_also": ["search_transactions", "navigation"]
    },

    "search_transactions": {
        "title": "Căutare",
        "icon": "🔎",
        "content": """
<h1>Căutarea în tranzacții</h1>

<p>Funcția de căutare permite găsirea rapidă a tranzacțiilor după diverse criterii.</p>

<h2>Câmpul de căutare</h2>
<bullet>Introduceți textul dorit în câmpul de căutare</bullet>
<bullet>Selectați coloana în care să se caute din lista derulantă</bullet>
<bullet>Căutarea se activează automat după ce terminați de scris</bullet>

<h2>Opțiuni de căutare</h2>

<bullet><b>Căutare parțială</b> (implicit) - Găsește tranzacții care conțin textul</bullet>
<bullet><b>Căutare exactă</b> - Bifați opțiunea pentru a căuta potrivire exactă</bullet>

<h2>Coloane disponibile pentru căutare</h2>
<bullet>Toate coloanele</bullet>
<bullet>Descriere</bullet>
<bullet>Observații</bullet>
<bullet>Beneficiar</bullet>
<bullet>CIF</bullet>
<bullet>Factură</bullet>

<tip>Pentru căutare rapidă, introduceți textul și apăsați Enter. Pentru ștergerea căutării, ștergeți textul din câmp.</tip>
""",
        "see_also": ["filter_transactions", "view_transactions"]
    },

    "transaction_details": {
        "title": "Detalii tranzacție",
        "icon": "📄",
        "content": """
<h1>Detalii tranzacție</h1>

<p>Pentru a vizualiza toate informațiile despre o tranzacție, faceți dublu-click pe rândul acesteia în listă.</p>

<h2>Informații disponibile</h2>

<bullet><b>Date generale:</b> Data, suma, tipul (credit/debit)</bullet>
<bullet><b>Descriere:</b> Textul complet al descrierii din extras</bullet>
<bullet><b>Partener:</b> Beneficiar, CIF, cont IBAN partener</bullet>
<bullet><b>Referințe:</b> Număr factură, TID, RRN, PAN (pentru tranzacții card)</bullet>
<bullet><b>Coduri:</b> Cod tranzacție, cod SWIFT</bullet>
<bullet><b>Observații:</b> Note personale (editabile)</bullet>

<h2>Editarea observațiilor</h2>
<p>Câmpul "Observații" poate fi editat pentru a adăuga note personale la tranzacție. Aceste note sunt salvate în baza de date și pot fi căutate ulterior.</p>

<tip>Folosiți observațiile pentru a marca tranzacțiile cu informații suplimentare utile (ex: "Factură plătită", "De verificat", etc.)</tip>
""",
        "see_also": ["view_transactions", "search_transactions"]
    },

    # ===== NAVIGARE =====
    "navigation": {
        "title": "Navigare și Filtre",
        "icon": "🧭",
        "content": """
<h1>Navigare și Filtre</h1>

<p>Panoul din stânga ferestrei principale oferă instrumente pentru navigarea și filtrarea tranzacțiilor.</p>
""",
        "children": ["account_selection", "date_navigation", "date_range_mode"],
        "see_also": ["transactions", "filter_transactions"]
    },

    "account_selection": {
        "title": "Selectare cont",
        "icon": "🏦",
        "content": """
<h1>Selectarea contului bancar</h1>

<p>În partea de sus a panoului de filtre se află selectorul de cont bancar.</p>

<h2>Cum funcționează</h2>
<bullet>Faceți click pe lista derulantă pentru a vedea conturile disponibile</bullet>
<bullet>Selectați contul dorit</bullet>
<bullet>Lista de tranzacții se actualizează automat</bullet>

<h2>Indicatorul de culoare</h2>
<p>Lângă numele contului veți vedea un pătrat colorat. Această culoare:</p>
<bullet>Este configurabilă pentru fiecare cont</bullet>
<bullet>Ajută la identificarea rapidă a contului activ</bullet>
<bullet>Poate fi modificată din Gestionare Conturi Bancare</bullet>

<note>Veți vedea doar conturile pentru care aveți permisiuni de acces. Administratorul poate restricționa accesul la anumite conturi.</note>
""",
        "see_also": ["account_management", "navigation"]
    },

    "date_navigation": {
        "title": "Navigare pe perioade",
        "icon": "📅",
        "content": """
<h1>Navigare pe perioade (An/Lună/Zi)</h1>

<p>Arborele de navigare temporală permite selectarea rapidă a perioadei dorite.</p>

<h2>Structura arborelui</h2>
<bullet><b>Nivel 1 - Ani:</b> Click pentru a vedea toate tranzacțiile din anul respectiv</bullet>
<bullet><b>Nivel 2 - Luni:</b> Expandați anul și selectați o lună</bullet>
<bullet><b>Nivel 3 - Zile:</b> Expandați luna pentru a vedea zilele cu tranzacții</bullet>

<h2>Indicatori numerici</h2>
<p>Lângă fiecare element veți vedea între paranteze numărul de tranzacții:</p>
<bullet>2024 (150) - 150 tranzacții în anul 2024</bullet>
<bullet>Ianuarie (45) - 45 tranzacții în ianuarie</bullet>
<bullet>15 (3) - 3 tranzacții în ziua de 15</bullet>

<tip>Click pe un element selectează doar acea perioadă. Pentru a vedea toate tranzacțiile, folosiți butonul "Resetează filtre".</tip>
""",
        "see_also": ["date_range_mode", "filter_transactions"]
    },

    "date_range_mode": {
        "title": "Interval de date",
        "icon": "📆",
        "content": """
<h1>Modul Interval de Date</h1>

<p>Pentru o selecție mai precisă a perioadei, puteți folosi modul "Interval de date".</p>

<h2>Activare</h2>
<bullet>Bifați caseta <b>"Interval de date"</b> din panoul de filtre</bullet>
<bullet>Vor apărea două selectoare de dată: "De la" și "Până la"</bullet>

<h2>Utilizare</h2>
<bullet>Selectați data de început din primul calendar</bullet>
<bullet>Selectați data de sfârșit din al doilea calendar</bullet>
<bullet>Lista se actualizează automat</bullet>

<h2>Diferențe față de navigarea ierarhică</h2>
<bullet>Permite selectarea de perioade care traversează luni sau ani</bullet>
<bullet>Oferă control precis asupra intervalului</bullet>
<bullet>Util pentru rapoarte pe perioade specifice</bullet>

<note>Când modul interval este activ, arborele de navigare din stânga este dezactivat.</note>
""",
        "see_also": ["date_navigation", "filter_transactions"]
    },

    # ===== IMPORT =====
    "import": {
        "title": "Import Date",
        "icon": "📥",
        "content": """
<h1>Import Date</h1>

<p>BTExtrasViewer permite importul tranzacțiilor din fișiere în format standard MT940 (SWIFT).</p>
""",
        "children": ["import_mt940", "import_iban_detect", "import_duplicates", "import_history"],
        "see_also": ["export", "transactions"]
    },

    "import_mt940": {
        "title": "Import fișiere MT940",
        "icon": "📂",
        "content": """
<h1>Importul fișierelor MT940</h1>

<p>Fișierele MT940 sunt extrase de cont bancar în format standardizat SWIFT, exportate de majoritatea băncilor.</p>

<h2>Procedură de import</h2>

<bullet>Accesați <b>Fișier → Import MT940...</b> sau apăsați butonul <b>Import</b></bullet>
<bullet>Selectați unul sau mai multe fișiere MT940 (.sta, .mt940, .txt)</bullet>
<bullet>Aplicația va procesa fișierele și va importa tranzacțiile</bullet>

<h2>Import în lot (batch)</h2>
<p>Puteți selecta mai multe fișiere simultan. Aplicația le va procesa pe rând, afișând progresul.</p>

<h2>Ce se întâmplă la import</h2>
<bullet>Se citește IBAN-ul din fișier</bullet>
<bullet>Se asociază automat cu contul corespunzător (sau se solicită selecția)</bullet>
<bullet>Se verifică tranzacțiile duplicate</bullet>
<bullet>Se importă doar tranzacțiile noi</bullet>

<tip>Verificați raportul de import la final pentru a vedea câte tranzacții au fost importate și dacă au fost identificate duplicate.</tip>
""",
        "see_also": ["import_iban_detect", "import_duplicates"]
    },

    "import_iban_detect": {
        "title": "Auto-detectare IBAN",
        "icon": "🔍",
        "content": """
<h1>Auto-detectarea IBAN-ului</h1>

<p>La importul unui fișier MT940, aplicația extrage automat IBAN-ul din câmpul :25: al fișierului.</p>

<h2>Scenarii posibile</h2>

<h3>IBAN găsit și asociat</h3>
<p>Dacă IBAN-ul din fișier corespunde unui cont existent în sistem, asocierea se face automat.</p>

<h3>IBAN negăsit</h3>
<p>Dacă IBAN-ul nu este recunoscut, va apărea un dialog pentru a selecta manual contul țintă din lista de conturi disponibile.</p>

<h3>IBAN invalid sau lipsă</h3>
<p>Dacă fișierul nu conține un IBAN valid, veți fi solicitat să selectați contul manual.</p>

<note>Asigurați-vă că toate conturile bancare sunt configurate corect cu IBAN-ul complet pentru a beneficia de asocierea automată.</note>
""",
        "see_also": ["import_mt940", "account_management"]
    },

    "import_duplicates": {
        "title": "Prevenire duplicate",
        "icon": "🚫",
        "content": """
<h1>Prevenirea duplicatelor</h1>

<p>Sistemul previne automat importul tranzacțiilor duplicate.</p>

<h2>Cum funcționează</h2>
<p>La importul fiecărei tranzacții, aplicația verifică dacă există deja o tranzacție cu aceleași caracteristici:</p>
<bullet>Aceeași dată</bullet>
<bullet>Aceeași sumă</bullet>
<bullet>Același tip (credit/debit)</bullet>
<bullet>Aceleași referințe (dacă există)</bullet>

<h2>Raport de import</h2>
<p>La finalul importului, veți primi un sumar cu:</p>
<bullet>Numărul total de tranzacții din fișier</bullet>
<bullet>Numărul de tranzacții importate cu succes</bullet>
<bullet>Numărul de tranzacții ignorate (duplicate)</bullet>

<tip>Puteți importa același fișier de mai multe ori fără teama de a crea duplicate. Aplicația va importa doar tranzacțiile noi.</tip>
""",
        "see_also": ["import_mt940", "import_history"]
    },

    "import_history": {
        "title": "Istoricul importurilor",
        "icon": "📜",
        "content": """
<h1>Istoricul importurilor</h1>

<p>Aplicația păstrează un istoric al tuturor operațiunilor de import efectuate.</p>

<h2>Informații stocate</h2>
<bullet>Data și ora importului</bullet>
<bullet>Numele fișierului importat</bullet>
<bullet>Contul bancar asociat</bullet>
<bullet>Numărul de tranzacții importate</bullet>
<bullet>Utilizatorul care a efectuat importul</bullet>

<h2>Accesare istoric</h2>
<p>Istoricul importurilor poate fi consultat de administratori pentru audit și verificare.</p>

<note>Istoricul ajută la identificarea sursei datelor și la urmărirea modificărilor în sistem.</note>
""",
        "see_also": ["import_mt940", "import_duplicates"]
    },

    # ===== EXPORT =====
    "export": {
        "title": "Export Date",
        "icon": "📤",
        "content": """
<h1>Export Date</h1>

<p>BTExtrasViewer oferă mai multe opțiuni pentru exportul tranzacțiilor.</p>
""",
        "children": ["export_excel", "export_email"],
        "see_also": ["import", "reports"]
    },

    "export_excel": {
        "title": "Export Excel",
        "icon": "📊",
        "content": """
<h1>Export în Excel</h1>

<p>Exportați lista de tranzacții afișată curent într-un fișier Excel (.xlsx).</p>

<h2>Procedură</h2>
<bullet>Aplicați filtrele dorite pentru a selecta tranzacțiile</bullet>
<bullet>Apăsați butonul <b>Export Excel</b> sau accesați <b>Fișier → Export Excel...</b></bullet>
<bullet>Alegeți locația și numele fișierului</bullet>
<bullet>Fișierul Excel va fi creat automat</bullet>

<h2>Ce conține exportul</h2>
<bullet>Toate coloanele vizibile în tabel</bullet>
<bullet>Doar tranzacțiile care respectă filtrele active</bullet>
<bullet>Formatare automată (antet, lățimi coloane)</bullet>
<bullet>Totaluri la sfârșitul listei</bullet>

<tip>Exportul respectă exact ceea ce vedeți în listă. Aplicați filtrele corecte înainte de export pentru a obține datele dorite.</tip>
""",
        "see_also": ["export_email", "filter_transactions"]
    },

    "export_email": {
        "title": "Trimitere pe email",
        "icon": "📧",
        "content": """
<h1>Trimitere pe email</h1>

<p>Puteți trimite lista de tranzacții direct pe email, ca fișier Excel atașat.</p>

<h2>Procedură</h2>
<bullet>Aplicați filtrele dorite</bullet>
<bullet>Apăsați butonul <b>Export pe email</b></bullet>
<bullet>Se va deschide fereastra de compunere email</bullet>
<bullet>Introduceți destinatarul și, opțional, un mesaj</bullet>
<bullet>Apăsați <b>Trimite</b></bullet>

<h2>Cerințe</h2>
<p>Pentru a utiliza această funcționalitate, trebuie să aveți configurat serverul SMTP:</p>
<bullet>Accesați <b>Administrare → Configurează SMTP...</b></bullet>
<bullet>Introduceți datele serverului de email</bullet>

<note>Configurarea SMTP este individuală pentru fiecare utilizator. Contactați administratorul IT pentru datele de conectare.</note>
""",
        "see_also": ["export_excel", "smtp_config"]
    },

    # ===== RAPOARTE =====
    "reports": {
        "title": "Rapoarte",
        "icon": "📈",
        "content": """
<h1>Rapoarte și Analize</h1>

<p>BTExtrasViewer oferă trei tipuri de rapoarte pentru analiza datelor financiare.</p>

<h2>Accesare rapoarte</h2>
<p>Toate rapoartele sunt accesibile din meniul <b>Rapoarte</b>.</p>

<h2>Opțiuni de export</h2>
<p>Fiecare raport poate fi:</p>
<bullet>Vizualizat în aplicație (grafic + tabel)</bullet>
<bullet>Exportat în PDF</bullet>
<bullet>Exportat în Excel</bullet>
<bullet>Trimis pe email (ca PDF atașat)</bullet>
""",
        "children": ["report_cashflow", "report_balance", "report_analysis"],
        "see_also": ["export", "transactions"]
    },

    "report_cashflow": {
        "title": "Flux de Numerar",
        "icon": "💰",
        "content": """
<h1>Raport Flux de Numerar (Cash Flow)</h1>

<p>Prezintă o analiză a intrărilor și ieșirilor de numerar pentru un cont și o perioadă selectată.</p>

<h2>Accesare</h2>
<p><b>Rapoarte → Flux de Numerar (Cash Flow)...</b></p>

<h2>Configurare raport</h2>
<bullet><b>Cont bancar:</b> Selectați contul de analizat</bullet>
<bullet><b>Perioadă:</b> Alegeți intervalul de date</bullet>
<bullet><b>Grupare:</b> Zilnic sau Lunar</bullet>

<h2>Ce afișează</h2>
<bullet><b>Grafic:</b> Bare verzi (încasări) și roșii (plăți) pe perioadă</bullet>
<bullet><b>Tabel:</b> Detalii numerice pentru fiecare perioadă</bullet>
<bullet><b>Totaluri:</b> Sumele totale pentru încasări, plăți și sold net</bullet>

<tip>Folosiți gruparea lunară pentru tendințe pe termen lung și zilnică pentru analiză detaliată.</tip>
""",
        "see_also": ["report_balance", "report_analysis"]
    },

    "report_balance": {
        "title": "Evoluție Sold",
        "icon": "📉",
        "content": """
<h1>Raport Evoluție Sold</h1>

<p>Generează un grafic liniar care arată evoluția soldului unui cont în timp.</p>

<h2>Accesare</h2>
<p><b>Rapoarte → Evoluție Sold...</b></p>

<h2>Configurare raport</h2>
<bullet><b>Cont bancar:</b> Selectați contul</bullet>
<bullet><b>Perioadă:</b> Intervalul de analizat</bullet>
<bullet><b>Granularitate:</b> Zilnic, Lunar sau Anual</bullet>

<h2>Ce afișează</h2>
<bullet><b>Grafic liniar:</b> Evoluția soldului în timp</bullet>
<bullet><b>Puncte de referință:</b> Sold inițial și final</bullet>
<bullet><b>Tendință:</b> Vizualizarea creșterii sau scăderii soldului</bullet>

<note>Soldul este calculat pe baza tranzacțiilor din sistem. Pentru acuratețe, asigurați-vă că toate extrasele sunt importate.</note>
""",
        "see_also": ["report_cashflow", "report_analysis"]
    },

    "report_analysis": {
        "title": "Analiză Tranzacții",
        "icon": "📊",
        "content": """
<h1>Raport Analiză Detaliată Tranzacții</h1>

<p>Oferă o vizualizare detaliată a sumelor agregate pe tipuri de tranzacție și perioade.</p>

<h2>Accesare</h2>
<p><b>Rapoarte → Analiză Detaliată Tranzacții...</b></p>

<h2>Configurare raport</h2>
<bullet><b>Cont bancar:</b> Selectați contul</bullet>
<bullet><b>Perioadă:</b> Intervalul de analizat</bullet>
<bullet><b>Grupare:</b> Pe tip tranzacție, zilnic, lunar sau anual</bullet>

<h2>Ce afișează</h2>
<bullet><b>Grafic:</b> Distribuția sumelor pe categorii</bullet>
<bullet><b>Tabel:</b> Detalii pentru fiecare tip de tranzacție</bullet>
<bullet><b>Statistici:</b> Procente, medii, valori maxime/minime</bullet>

<tip>Acest raport este util pentru identificarea categoriilor principale de cheltuieli sau încasări.</tip>
""",
        "see_also": ["report_cashflow", "report_balance"]
    },

    # ===== ADMINISTRARE =====
    "administration": {
        "title": "Administrare",
        "icon": "⚙️",
        "content": """
<h1>Administrare Sistem</h1>

<p>Secțiunea de Administrare este accesibilă doar utilizatorilor cu permisiunile corespunzătoare (de obicei, rolul "Administrator").</p>

<warning>Modificările din această secțiune afectează întregul sistem și toți utilizatorii. Procedați cu atenție.</warning>
""",
        "children": ["user_management", "role_management", "account_management",
                     "transaction_types", "swift_codes", "currency_management",
                     "db_config", "smtp_config", "smtp_system_config"],
        "see_also": ["authentication"]
    },

    "user_management": {
        "title": "Utilizatori",
        "icon": "👥",
        "content": """
<h1>Gestionarea Utilizatorilor</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Utilizatori...</b></p>

<h2>Funcționalități</h2>

<h3>Adăugare utilizator nou</h3>
<bullet>Introduceți username (unic în sistem)</bullet>
<bullet>Introduceți numele complet</bullet>
<bullet>Introduceți adresa de email</bullet>
<bullet>Setați parola inițială</bullet>
<bullet>Selectați rolurile dorite</bullet>
<bullet>Selectați conturile bancare accesibile</bullet>

<h3>Editare utilizator</h3>
<bullet>Modificați datele de profil</bullet>
<bullet>Schimbați rolurile asignate</bullet>
<bullet>Modificați accesul la conturi</bullet>
<bullet>Setați restricții pe tip tranzacție (toate/credit/debit)</bullet>

<h3>Activare/Dezactivare</h3>
<p>Utilizatorii dezactivați nu se pot autentifica, dar datele lor rămân în sistem.</p>

<h3>Ștergere</h3>
<p>Ștergerea permanentă elimină utilizatorul din sistem. Această acțiune este ireversibilă.</p>

<warning>Nu puteți șterge propriul cont de utilizator sau ultimul administrator din sistem.</warning>
""",
        "see_also": ["role_management", "account_management"]
    },

    "role_management": {
        "title": "Roluri",
        "icon": "🎭",
        "content": """
<h1>Gestionarea Rolurilor și Permisiunilor</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Roluri și Permisiuni...</b></p>

<h2>Ce este un rol?</h2>
<p>Un rol este un set de permisiuni grupate logic. Utilizatorilor li se atribuie roluri, nu permisiuni individuale.</p>

<h2>Exemple de roluri</h2>
<bullet><b>Administrator:</b> Acces complet la toate funcțiile</bullet>
<bullet><b>Contabil:</b> Vizualizare și rapoarte, fără administrare</bullet>
<bullet><b>Operator:</b> Doar import și vizualizare de bază</bullet>

<h2>Permisiuni disponibile</h2>
<bullet>manage_users - Gestionare utilizatori</bullet>
<bullet>manage_roles - Gestionare roluri</bullet>
<bullet>manage_accounts - Gestionare conturi bancare</bullet>
<bullet>import_files - Import fișiere MT940</bullet>
<bullet>export_data - Export date</bullet>
<bullet>view_reports - Vizualizare rapoarte</bullet>
<bullet>...și altele</bullet>

<tip>Creați roluri care reflectă funcțiile din organizație pentru o administrare mai ușoară.</tip>
""",
        "see_also": ["user_management"]
    },

    "account_management": {
        "title": "Conturi bancare",
        "icon": "🏦",
        "content": """
<h1>Gestionarea Conturilor Bancare</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Conturi Bancare...</b></p>

<h2>Adăugare cont nou</h2>
<bullet><b>Denumire:</b> Numele afișat în aplicație</bullet>
<bullet><b>IBAN:</b> Codul IBAN complet (pentru auto-detectare la import)</bullet>
<bullet><b>Monedă:</b> RON, EUR, USD, etc.</bullet>
<bullet><b>Culoare:</b> Culoarea de identificare în interfață</bullet>

<h2>Editare cont</h2>
<p>Puteți modifica orice câmp al unui cont existent.</p>

<h2>Ștergere cont</h2>
<p>Un cont poate fi șters doar dacă nu are tranzacții asociate.</p>

<warning>Înainte de a șterge un cont, trebuie să ștergeți toate tranzacțiile asociate. Aceasta este o măsură de siguranță pentru a preveni pierderea accidentală a datelor.</warning>
""",
        "see_also": ["currency_management", "user_management"]
    },

    "transaction_types": {
        "title": "Tipuri tranzacții",
        "icon": "🏷️",
        "content": """
<h1>Gestionarea Tipurilor de Tranzacții</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Tipuri Tranzacții...</b></p>

<h2>Ce sunt tipurile de tranzacții?</h2>
<p>Codurile de tranzacție (ex: NTRF, NCHK) identifică categoria operațiunii bancare. Fiecare cod are o descriere asociată.</p>

<h2>Funcționalități</h2>
<bullet><b>Vizualizare:</b> Lista tuturor codurilor de tranzacție din sistem</bullet>
<bullet><b>Editare descriere:</b> Personalizați descrierea pentru fiecare cod</bullet>
<bullet><b>Vizibilitate:</b> Setați ce tipuri apar în rapoarte (per utilizator)</bullet>

<tip>Descrierile personalizate ajută la înțelegerea mai rapidă a tipului de tranzacție în liste și rapoarte.</tip>
""",
        "see_also": ["swift_codes"]
    },

    "swift_codes": {
        "title": "Coduri SWIFT",
        "icon": "🌐",
        "content": """
<h1>Gestionarea Descrierilor Standard SWIFT</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Descrieri Standard SWIFT...</b></p>

<h2>Ce sunt codurile SWIFT?</h2>
<p>Codurile SWIFT (ex: CHG, TRF) sunt coduri standardizate internațional pentru tipurile de operațiuni bancare.</p>

<h2>Funcționalități</h2>
<bullet>Vizualizarea tuturor codurilor SWIFT cunoscute</bullet>
<bullet>Editarea descrierilor în limba română</bullet>
<bullet>Adăugarea de coduri noi</bullet>

<note>Descrierile SWIFT ajută la interpretarea extraselor bancare care folosesc aceste coduri standardizate.</note>
""",
        "see_also": ["transaction_types"]
    },

    "currency_management": {
        "title": "Valute",
        "icon": "💱",
        "content": """
<h1>Gestionarea Valutelor</h1>

<h2>Accesare</h2>
<p><b>Administrare → Gestionare Valute...</b></p>

<h2>Funcționalități</h2>
<bullet>Vizualizarea valutelor disponibile</bullet>
<bullet>Adăugarea de valute noi (cod ISO, denumire, simbol)</bullet>
<bullet>Editarea valutelor existente</bullet>
<bullet>Ștergerea valutelor nefolosite</bullet>

<h2>Valute predefinite</h2>
<bullet>RON - Leu românesc</bullet>
<bullet>EUR - Euro</bullet>
<bullet>USD - Dolar american</bullet>

<note>O valută nu poate fi ștearsă dacă există conturi bancare care o folosesc.</note>
""",
        "see_also": ["account_management"]
    },

    "db_config": {
        "title": "Configurare DB",
        "icon": "🗄️",
        "content": """
<h1>Configurarea Conexiunii la Baza de Date</h1>

<h2>Accesare</h2>
<p><b>Fișier → Configurare conexiune DB...</b></p>

<h2>Parametri de conexiune</h2>
<bullet><b>Server:</b> Adresa serverului (IP sau hostname)</bullet>
<bullet><b>Port:</b> Portul MySQL/MariaDB (implicit 3306)</bullet>
<bullet><b>Bază de date:</b> Numele bazei de date</bullet>
<bullet><b>Utilizator:</b> Numele de utilizator MySQL</bullet>
<bullet><b>Parolă:</b> Parola MySQL</bullet>

<h2>Unde se salvează?</h2>
<p>Credențialele sunt salvate local în fișierul config.ini din:</p>
<p><code>%LOCALAPPDATA%\\BTExtrasViewer\\config.ini</code></p>

<warning>Credențialele bazei de date sunt stocate în text clar. Asigurați-vă că computerul este securizat corespunzător.</warning>
""",
        "see_also": ["requirements", "first_start"]
    },

    "smtp_config": {
        "title": "Configurare SMTP",
        "icon": "📬",
        "content": """
<h1>Configurarea SMTP (Email personal)</h1>

<h2>Accesare</h2>
<p><b>Administrare → Configurează SMTP (Email)...</b></p>

<h2>Ce este SMTP?</h2>
<p>SMTP (Simple Mail Transfer Protocol) este protocolul folosit pentru trimiterea emailurilor. Fiecare utilizator își poate configura propriul server SMTP.</p>

<h2>Parametri necesari</h2>
<bullet><b>Server SMTP:</b> ex: smtp.gmail.com, smtp.office365.com</bullet>
<bullet><b>Port:</b> 587 (TLS) sau 465 (SSL)</bullet>
<bullet><b>Utilizator:</b> Adresa de email completă</bullet>
<bullet><b>Parolă:</b> Parola sau parola de aplicație</bullet>
<bullet><b>TLS/SSL:</b> Tipul de criptare</bullet>

<tip>Pentru Gmail, trebuie să activați "Parole pentru aplicații" din setările contului Google și să folosiți acea parolă, nu parola normală.</tip>
""",
        "see_also": ["smtp_system_config", "export_email"]
    },

    "smtp_system_config": {
        "title": "SMTP Sistem",
        "icon": "📮",
        "content": """
<h1>Setări Email Sistem</h1>

<h2>Accesare</h2>
<p><b>Administrare → Setări Email Sistem...</b></p>

<h2>Ce face această configurare?</h2>
<p>Configurează serverul SMTP folosit de <b>sistem</b> pentru:</p>
<bullet>Trimiterea emailurilor de resetare a parolei</bullet>
<bullet>Notificări automate de sistem (dacă sunt configurate)</bullet>

<h2>Diferența față de SMTP personal</h2>
<bullet><b>SMTP personal:</b> Folosit de fiecare utilizator pentru export pe email</bullet>
<bullet><b>SMTP sistem:</b> Folosit de aplicație pentru funcții administrative</bullet>

<warning>Fără configurarea SMTP de sistem, funcționalitatea "Am uitat parola" nu va funcționa.</warning>
""",
        "see_also": ["smtp_config", "password_reset"]
    },

    # ===== COMENZI RAPIDE =====
    "shortcuts": {
        "title": "Comenzi Rapide",
        "icon": "⌨️",
        "content": f"""
<h1>Comenzi Rapide (Hotkeys)</h1>

<p>BTExtras Suite oferă combinații de taste pentru acces rapid la funcționalități.</p>

<h2>Combinații globale</h2>
<p>Acestea funcționează oriunde în Windows, dacă Session Manager rulează în fundal:</p>

<bullet><kbd>{GLOBAL_HOTKEY_VIEWER.upper()}</kbd> - Deschide/Afișează BTExtrasViewer</bullet>
<bullet><kbd>{GLOBAL_HOTKEY_CHAT.upper()}</kbd> - Deschide/Afișează BTExtrasChat</bullet>

<h2>Combinații în aplicație</h2>
<bullet><kbd>F5</kbd> - Reîmprospătare listă tranzacții</bullet>
<bullet><kbd>Ctrl+F</kbd> - Focus pe câmpul de căutare</bullet>
<bullet><kbd>Ctrl+E</kbd> - Export Excel</bullet>
<bullet><kbd>Escape</kbd> - Închide dialogul curent</bullet>
<bullet><kbd>Enter</kbd> - Confirmă acțiunea în dialoguri</bullet>

<h2>Navigare în liste</h2>
<bullet><kbd>Sus/Jos</kbd> - Navigare între rânduri</bullet>
<bullet><kbd>Home/End</kbd> - Salt la primul/ultimul rând</bullet>
<bullet><kbd>Page Up/Down</kbd> - Scroll rapid</bullet>

<tip>Session Manager trebuie să ruleze în fundal (iconiță în System Tray) pentru ca hotkey-urile globale să funcționeze.</tip>
""",
        "see_also": ["architecture", "welcome"]
    },

    # ===== DEPANARE =====
    "troubleshooting": {
        "title": "Depanare",
        "icon": "🔧",
        "content": """
<h1>Depanare și Probleme Frecvente</h1>

<p>Această secțiune vă ajută să rezolvați problemele comune întâlnite în utilizarea aplicației.</p>
""",
        "children": ["troubleshooting_connection", "troubleshooting_login", "troubleshooting_import", "troubleshooting_contact"],
        "see_also": ["requirements", "first_start"]
    },

    "troubleshooting_connection": {
        "title": "Erori de conexiune",
        "icon": "🔌",
        "content": """
<h1>Probleme de conexiune la baza de date</h1>

<h2>Mesaj: "Nu se poate conecta la baza de date"</h2>

<h3>Verificări de făcut:</h3>
<bullet>Serverul de baze de date este pornit?</bullet>
<bullet>Adresa serverului este corectă?</bullet>
<bullet>Portul este corect (implicit 3306)?</bullet>
<bullet>Firewall-ul permite conexiunea?</bullet>
<bullet>Credențialele sunt corecte?</bullet>

<h3>Soluții:</h3>
<bullet>Verificați că serviciul MySQL/MariaDB rulează pe server</bullet>
<bullet>Testați conexiunea cu un client MySQL</bullet>
<bullet>Verificați setările firewall pe server și client</bullet>
<bullet>Reconfigurați conexiunea din Fișier → Configurare conexiune DB</bullet>

<h2>Mesaj: "Baza de date nu există"</h2>
<p>Creați baza de date pe server înainte de prima conectare:</p>
<code>CREATE DATABASE btextras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;</code>
""",
        "see_also": ["db_config", "requirements"]
    },

    "troubleshooting_login": {
        "title": "Probleme autentificare",
        "icon": "🔐",
        "content": """
<h1>Probleme la autentificare</h1>

<h2>Mesaj: "Utilizator sau parolă incorectă"</h2>
<bullet>Verificați că numele de utilizator este scris corect</bullet>
<bullet>Verificați că tasta Caps Lock nu este activată</bullet>
<bullet>Încercați resetarea parolei</bullet>

<h2>Mesaj: "Contul este dezactivat"</h2>
<p>Contactați un administrator pentru reactivarea contului.</p>

<h2>Nu primiți email de resetare parolă</h2>
<bullet>Verificați folderul Spam/Junk</bullet>
<bullet>Verificați că adresa de email este corectă în profil</bullet>
<bullet>Contactați administratorul - SMTP de sistem poate fi neconfigurat</bullet>

<h2>Prima autentificare - cont admin</h2>
<p>La prima instalare, folosiți:</p>
<bullet><b>Utilizator:</b> admin</bullet>
<bullet><b>Parolă:</b> admin123</bullet>
<p>Veți fi obligat să schimbați parola la prima conectare.</p>
""",
        "see_also": ["login", "password_reset"]
    },

    "troubleshooting_import": {
        "title": "Probleme import",
        "icon": "📥",
        "content": """
<h1>Probleme la importul fișierelor</h1>

<h2>Mesaj: "Fișierul nu este în format MT940 valid"</h2>
<bullet>Verificați că fișierul este într-adevăr în format MT940</bullet>
<bullet>Unele bănci exportă în formate proprietare - contactați banca</bullet>
<bullet>Încercați să deschideți fișierul în Notepad pentru verificare</bullet>

<h2>Mesaj: "IBAN-ul nu corespunde niciunui cont"</h2>
<bullet>Verificați că contul bancar este adăugat în sistem</bullet>
<bullet>Verificați că IBAN-ul contului este introdus complet și corect</bullet>
<bullet>Selectați manual contul când vi se solicită</bullet>

<h2>Importul nu adaugă tranzacții noi</h2>
<p>Tranzacțiile sunt probabil duplicate. Verificați:</p>
<bullet>Dacă fișierul a mai fost importat anterior</bullet>
<bullet>Raportul de import pentru detalii despre tranzacțiile ignorate</bullet>

<h2>Caractere ciudate în descrieri</h2>
<p>Problema este de codificare. Fișierele MT940 pot folosi diferite codificări de caractere. Contactați banca pentru fișiere cu codificare UTF-8.</p>
""",
        "see_also": ["import_mt940", "import_duplicates"]
    },

    "troubleshooting_contact": {
        "title": "Contact suport",
        "icon": "📞",
        "content": """
<h1>Contact Suport Tehnic</h1>

<p>Dacă nu ați reușit să rezolvați problema, contactați suportul tehnic:</p>

<h2>Regio Development SRL</h2>

<bullet><b>Website:</b> www.regio-development.ro</bullet>
<bullet><b>Email:</b> office@regio-development.ro</bullet>

<h2>Informații utile la contactare</h2>
<p>Pentru a primi ajutor rapid, pregătiți următoarele informații:</p>
<bullet>Versiunea aplicației (Ajutor → Despre)</bullet>
<bullet>Mesajul de eroare exact (screenshot dacă e posibil)</bullet>
<bullet>Pașii pentru reproducerea problemei</bullet>
<bullet>Sistemul de operare folosit</bullet>

<tip>Capturi de ecran (screenshot) cu erorile întâmpinate ajută foarte mult la diagnosticarea problemelor.</tip>
""",
        "see_also": ["troubleshooting"]
    }
}

# Lista pentru ordinea afișării în TOC
HELP_SECTIONS_ORDER = [
    "welcome",
    "introduction",
    "overview",
    "architecture",
    "requirements",
    "first_start",
    "authentication",
    "login",
    "password_reset",
    "change_password",
    "transactions",
    "view_transactions",
    "filter_transactions",
    "search_transactions",
    "transaction_details",
    "navigation",
    "account_selection",
    "date_navigation",
    "date_range_mode",
    "import",
    "import_mt940",
    "import_iban_detect",
    "import_duplicates",
    "import_history",
    "export",
    "export_excel",
    "export_email",
    "reports",
    "report_cashflow",
    "report_balance",
    "report_analysis",
    "administration",
    "user_management",
    "role_management",
    "account_management",
    "transaction_types",
    "swift_codes",
    "currency_management",
    "db_config",
    "smtp_config",
    "smtp_system_config",
    "shortcuts",
    "troubleshooting",
    "troubleshooting_connection",
    "troubleshooting_login",
    "troubleshooting_import",
    "troubleshooting_contact"
]

# Secțiunile de top-level pentru TOC
TOP_LEVEL_SECTIONS = [
    "welcome",
    "introduction",
    "authentication",
    "transactions",
    "navigation",
    "import",
    "export",
    "reports",
    "administration",
    "shortcuts",
    "troubleshooting"
]


def get_section(section_id):
    """Returnează o secțiune de help după ID."""
    return HELP_SECTIONS.get(section_id)


def get_section_title(section_id):
    """Returnează titlul unei secțiuni."""
    section = HELP_SECTIONS.get(section_id)
    return section.get("title", section_id) if section else section_id


def get_section_icon(section_id):
    """Returnează iconița unei secțiuni."""
    section = HELP_SECTIONS.get(section_id)
    return section.get("icon", "📄") if section else "📄"


def get_section_children(section_id):
    """Returnează lista de copii ai unei secțiuni."""
    section = HELP_SECTIONS.get(section_id)
    return section.get("children", []) if section else []


def get_section_see_also(section_id):
    """Returnează lista de secțiuni relacionate."""
    section = HELP_SECTIONS.get(section_id)
    return section.get("see_also", []) if section else []


def search_sections(query):
    """
    Caută în toate secțiunile de help.
    Returnează o listă de (section_id, section_title, match_context).
    """
    results = []
    query_lower = query.lower()

    for section_id, section in HELP_SECTIONS.items():
        title = section.get("title", "")
        content = section.get("content", "")

        # Căutăm în titlu și conținut
        title_match = query_lower in title.lower()
        content_lower = content.lower()
        content_match = query_lower in content_lower

        if title_match or content_match:
            # Extragem contextul potrivirii
            context = ""
            if content_match:
                # Găsim poziția și extragem un fragment
                pos = content_lower.find(query_lower)
                start = max(0, pos - 40)
                end = min(len(content), pos + len(query) + 40)
                context = content[start:end]
                # Curățăm tag-urile HTML pentru afișare
                import re
                context = re.sub(r'<[^>]+>', '', context)
                context = "..." + context.strip() + "..."

            results.append({
                "id": section_id,
                "title": title,
                "icon": section.get("icon", "📄"),
                "context": context,
                "title_match": title_match
            })

    # Sortăm - potrivirile în titlu primele
    results.sort(key=lambda x: (not x["title_match"], x["title"]))

    return results
