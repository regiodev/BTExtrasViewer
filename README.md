# BTExtrasViewer

O aplicație desktop avansată, client-server, pentru vizualizarea, analiza și managementul extraselor de cont bancare în format MT940, cu un sistem de permisiuni granular bazat pe roluri.

## Funcționalități Principale

### Management Tranzacții
- **Import Multi-Fișier:** Importă unul sau mai multe extrase de cont în format MT940 simultan.
- **Detecție Automată a Contului:** Identifică automat contul bancar corect pe baza IBAN-ului din fișierul de import.
- **Creare Conturi la Import:** Permite crearea unui nou cont bancar direct din fluxul de import dacă IBAN-ul detectat nu există în baza de date.
- **Vizualizare Avansată:** Afișează tranzacțiile într-un tabel sortabil și personalizabil.
- **Filtrare și Căutare:** Permite filtrarea tranzacțiilor după perioadă, tip (credit/debit) și căutare text exactă sau parțială în diverse coloane.
- **Navigare Ierarhică:** Un panou de navigare arborescent permite explorarea rapidă a tranzacțiilor pe ani, luni și zile.
- **Editare Observații:** Permite adăugarea și modificarea de observații pentru fiecare tranzacție în parte.

### Rapoarte și Analiză
Aplicația poate genera rapoarte complexe, oferind o imagine de ansamblu asupra sănătății financiare:
- **Analiză Flux de Numerar (Cash Flow):** Un raport vizual (grafic cu bare) și tabelar care prezintă totalul încasărilor și plăților pe perioade zilnice sau lunare.
- **Evoluție Sold:** Un grafic liniar care arată evoluția soldului unui cont pe o perioadă selectată.
- **Analiză Detaliată a Tranzacțiilor:** Un raport avansat cu grafice de tip "stacked bar" care grupează tranzacțiile după cod și perioadă.
- **Export PDF și Excel:** Toate rapoartele pot fi exportate în formate profesionale, gata pentru a fi arhivate sau prezentate.
- **Trimitere pe Email:** Funcționalitate integrată pentru a trimite rapoartele generate direct din aplicație, folosind o configurație SMTP per-utilizator.

### Securitate și Multi-User (RBAC)
Aceasta este cea mai avansată componentă a aplicației, transformând-o într-o unealtă de business sigură:
- **Arhitectură Client-Server:** Datele sunt centralizate într-o bază de date MariaDB/MySQL, permițând accesul simultan pentru mai mulți utilizatori dintr-o rețea locală (ex: de pe un NAS).
- **Autentificare Utilizatori:** Acces securizat pe bază de nume de utilizator și parolă. Parolele sunt stocate folosind metode de hashing sigure (PBKDF2 cu salt).
- **Sistem de Roluri și Permisiuni (RBAC):**
    - **Roluri Personalizabile:** Un administrator poate crea, redenumi și șterge roluri (profile de utilizator), ex: "Administrator", "Contabil", "Operator Date", "Auditor Extern".
    - **Permisiuni Granulare:** Fiecărui rol i se pot atribui permisiuni specifice pentru aproape fiecare acțiune din aplicație (vezi lista de mai jos).
    - **Acces per Cont:** Unui utilizator i se poate acorda acces doar la anumite conturi bancare.
    - **Acces per Tip de Tranzacție:** Unui utilizator i se poate limita accesul pentru a vedea doar tranzacțiile de tip `credit`, `debit` sau `toate`.
- **Jurnal de Acțiuni (Audit Trail):** Toate acțiunile importante (login, import, creare utilizator, modificare rol, etc.) sunt înregistrate într-un jurnal detaliat, specificând cine și când a efectuat acțiunea.

## Tehnologii și Cerințe

- **Limbaj:** Python 3
- **Bază de Date:** MariaDB (recomandat) sau MySQL
- **Interfață Grafică:** Tkinter (ttk)
- **Librării Python necesare:**
    - `mysql-connector-python`
    - `tkcalendar`
    - `pandas`
    - `openpyxl`
    - `matplotlib`
    - `reportlab`
    - `SQLAlchemy` (recomandat pentru a evita avertismente la exportul cu `pandas`)

Pentru o instalare ușoară, poți crea un fișier `requirements.txt` cu următorul conținut:
```txt
mysql-connector-python
tkcalendar
pandas
openpyxl
matplotlib
reportlab
SQLAlchemy