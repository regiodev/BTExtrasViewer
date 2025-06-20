# BTExtrasViewer

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![UI](https://img.shields.io/badge/UI-Tkinter-orange)
![Database](https://img.shields.io/badge/Database-MariaDB%20%7C%20MySQL-green)

O aplicație desktop avansată, multi-utilizator și multi-cont, pentru vizualizarea, gestionarea și analiza extraselor de cont bancare în format MT940. Aplicația utilizează o arhitectură client-server, conectându-se la o bază de date MariaDB/MySQL pentru a stoca și centraliza toate datele în mod securizat.

## Caracteristici Principale

- **Management Multi-Cont:** Adăugați și gestionați multiple conturi bancare, fiecare cu IBAN, monedă și culoare de identificare proprie.
- **Import Inteligent MT940:** Importați unul sau mai multe fișiere MT940. Aplicația detectează automat IBAN-ul din fișier și îl asociază contului corespunzător sau vă permite să creați un cont nou.
- **Management Utilizatori și Roluri:** Sistem de autentificare securizat cu roluri și permisiuni granulare. Administratorii pot gestiona utilizatori, pot acorda/revoca permisiuni și pot reseta parole.
- **Securitate:** Parolele utilizatorilor sunt stocate folosind tehnici moderne de hashing (PBKDF2-HMAC-SHA256) cu salt unic pentru fiecare utilizator.
- **Filtrare și Căutare Avansată:** Filtrați tranzacțiile după perioadă (navigare arborescentă sau interval de date), tip (credit/debit) și căutați text în multiple câmpuri (beneficiar, CIF, descriere, etc.).
- **Rapoarte Detaliate:**
    - **Analiză Flux de Numerar (Cash Flow):** Vizualizați grafic și tabelar intrările și ieșirile pe o perioadă selectată.
    - **Evoluție Sold Cont:** Generați un grafic interactiv cu evoluția soldului în timp.
    - **Analiză Detaliată Tranzacții:** Un raport complex care grupează tranzacțiile după cod și perioadă, cu grafice de tip "stacked bar".
- **Export Date:** Exportați datele filtrate în format PDF (pentru rapoarte) și Microsoft Excel (.xlsx) pentru analize suplimentare.
- **Jurnal de Audit:** Aplicația înregistrează acțiunile importante (login, creare/modificare utilizatori, importuri, exporturi) într-un jurnal de audit, asigurând trasabilitatea completă.
- **Arhitectură Client-Server:** Toate datele sunt stocate centralizat într-o bază de date MariaDB/MySQL, permițând accesul multi-utilizator de pe stații de lucru diferite.

## Capturi de Ecran

*(Notă: Adăugați aici capturile de ecran ale aplicației. Se recomandă imagini cu: fereastra principală, un raport generat, fereastra de gestionare a conturilor și fereastra de gestionare a utilizatorilor.)*

**Fereastra Principală:**
`[Introduceți aici o imagine cu fereastra principală]`

**Exemplu de Raport (Evoluție Sold):**
`[Introduceți aici o imagine cu un raport]`

## Arhitectură Tehnică

- **Limbaj de Programare:** Python 3.10+
- **Interfață Grafică (UI):** Tkinter, ttk, tkcalendar
- **Bază de Date:** MariaDB sau MySQL
- **Componente Cheie:**
    - **Conector DB:** `mysql-connector-python`, `SQLAlchemy`
    - **Rapoarte & Grafice:** `Matplotlib`, `pandas`
    - **Export Date:** `openpyxl` (Excel), `reportlab` (PDF)

## Cerințe (Prerequisites)

- **Python:** Versiunea 3.10 sau mai recentă.
- **Bază de Date:** Un server MariaDB sau MySQL funcțional, accesibil în rețeaua locală.
- **Pip:** Managerul de pachete pentru Python, de obicei inclus cu instalarea Python.

## Instalare și Configurare

Urmați acești pași pentru a rula aplicația:

1.  **Clonați repository-ul:**
    ```bash
    git clone [https://github.com/nume-utilizator/BTExtrasViewer.git](https://github.com/nume-utilizator/BTExtrasViewer.git)
    cd BTExtrasViewer
    ```

2.  **Instalați dependențele:**
    Este recomandat să creați un mediu virtual. Apoi, instalați pachetele necesare folosind fișierul `requirements.txt`.
    
    *Creați un fișier `requirements.txt` cu următorul conținut:*
    ```text
    mysql-connector-python
    tkcalendar
    matplotlib
    pandas
    openpyxl
    reportlab
    SQLAlchemy
    ```
    
    *Rulați comanda de instalare:*
    ```bash
    pip install -r requirements.txt
    ```

3.  **Prima Rulare și Configurarea Bazei de Date:**
    Rulați aplicația pentru prima dată din consolă:
    ```bash
    python btextrasviewer_main.py
    ```
    - La prima execuție, va apărea o fereastră de **configurare a conexiunii la baza de date**. Introduceți detaliile serverului dumneavoastră MariaDB/MySQL.
    - Aplicația va crea automat toate tabelele necesare și un **utilizator administrator implicit**:
        - **Utilizator:** `admin`
        - **Parolă:** `admin123`

4.  **Autentificare:**
    - După configurarea bazei de date, va apărea fereastra de login. Folosiți credențialele de mai sus pentru a vă autentifica.
    - **IMPORTANT:** Este crucial să schimbați parola utilizatorului `admin` imediat după prima autentificare, din meniul de gestionare a utilizatorilor.

## Utilizare

- **Gestionare Conturi:** Din meniul `Fișier` -> `Gestionare Conturi Bancare...`, adăugați conturile pe care le veți folosi.
- **Import:** Folosiți butonul `Importă fișier MT940` pentru a selecta și importa extrasele de cont.
- **Navigare:** Folosiți arborele de navigare din stânga sau filtrele de dată din partea de sus pentru a vizualiza tranzacțiile dintr-o anumită perioadă.
- **Rapoarte:** Generați rapoarte folosind butoanele dedicate din partea dreapta-sus sau din meniul `Rapoarte`.
- **Gestionare Utilizatori:** Dacă sunteți administrator, puteți gestiona utilizatorii din meniul `Fișier` -> `Gestionare Utilizatori...`.

## Structura Proiectului

Proiectul este organizat modular pentru o mentenanță ușoară:
- `btextrasviewer_main.py`: Fișierul principal, conține clasa `BTViewerApp`, logica UI și bucla de evenimente.
- `db_handler.py`: Data Access Layer (DAL). Gestionează toate interacțiunile cu baza de date.
- `ui_dialogs.py`: Conține clasele pentru toate ferestrele de dialog modale (login, editare cont, editare utilizator, etc.).
- `ui_reports.py`: Conține clasele pentru ferestrele de rapoarte (Cash Flow, Evoluție Sold, etc.).
- `file_processing.py`: Gestionează parsarea fișierelor MT940 și operațiunile de import/export în fire de execuție separate.
- `config_management.py`: Gestionează citirea și scrierea fișierului de configurare `config.ini`.
- `auth_handler.py`: Gestionează hashing-ul și verificarea securizată a parolelor.
- `app_constants.py`: Stochează constante globale ale aplicației.
- `ui_utils.py`: Conține funcții utilitare pentru UI, cum ar fi logica de închidere a aplicației.
- `email_handler.py`: Gestionează logica pentru trimiterea rapoartelor prin email.

## Contribuții

Contribuțiile sunt binevenite. Vă rugăm să deschideți un "issue" pentru a discuta modificările pe care doriți să le faceți.

## Licență

*(Notă: Adăugați aici licența sub care doriți să publicați proiectul, de exemplu: MIT, GPL, etc.)*
Acest proiect este licențiat sub termenii licenței MIT.

---
© 2025 Regio Development. Toate drepturile rezervate.