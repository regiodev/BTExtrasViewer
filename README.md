# BTExtrasViewer v4.2

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-activ-brightgreen)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

**BTExtrasViewer** este o aplicație desktop complexă, de tip client-server, destinată gestiunii, vizualizării și analizei extraselor de cont bancare. Construită în Python, aplicația oferă o soluție multi-utilizator robustă, cu un sistem avansat de roluri și permisiuni, stocând datele într-o bază de date centralizată MariaDB/MySQL.

![App Screenshot](https://user-images.githubusercontent.com/10636246/188358599-44755a60-e448-4e89-9e8c-52a5509a25b2.png)
*(Notă: Imaginea de mai sus este un exemplu. Înlocuiți cu o captură de ecran reală a aplicației.)*

---

## Cuprins

- [Funcționalități Cheie](#funcționalități-cheie)
- [Arhitectura Tehnică](#arhitectura-tehnică)
- [Tehnologii Folosite](#tehnologii-folosite)
- [Cerințe preliminare](#cerințe-preliminare)
- [Instalare și Configurare](#instalare-și-configurare)
  - [Pasul 1: Clonarea Repository-ului](#pasul-1-clonarea-repository-ului)
  - [Pasul 2: Crearea Bazei de Date](#pasul-2-crearea-bazei-de-date)
  - [Pasul 3: Instalarea Dependințelor](#pasul-3-instalarea-dependințelor)
- [Utilizare](#utilizare)
- [Sistemul de Roluri și Permisiuni (Analiză Detaliată)](#sistemul-de-roluri-și-permisiuni-analiză-detaliată)
  - [Structura Bazei de Date](#structura-bazei-de-date)
  - [Niveluri de Securitate](#niveluri-de-securitate)
- [Contribuții](#contribuții)
- [Licență](#licență)

---

## Funcționalități Cheie

* **Management Multi-Cont:** Gestionarea centralizată a mai multor conturi bancare.
* **Import Avansat MT940:** Procesarea fișierelor de extras de cont în format MT940, cu detecție automată a IBAN-ului, prevenirea duplicatelor și crearea de noi conturi direct din fluxul de import.
* **Vizualizare și Filtrare Detaliată:** O interfață principală puternică pentru vizualizarea tranzacțiilor, cu navigare ierarhică (an/lună/zi) și opțiuni avansate de filtrare și căutare (inclusiv căutare exactă).
* **Sistem de Raportare Complex:** Generarea de rapoarte vizuale și tabelare:
    * Analiză Flux de Numerar (Cash Flow).
    * Grafic de Evoluție a Soldului.
    * Analiză Detaliată a Tranzacțiilor pe categorii.
* **Exporturi Multiple:** Toate datele filtrate și rapoartele pot fi exportate în format **Excel (.xlsx)** sau **PDF**.
* **Notificări prin Email:** Posibilitatea de a trimite rapoartele generate direct pe email, folosind o configurație SMTP personală.
* **Securitate Multi-Utilizator:** Un sistem granular de roluri și permisiuni care controlează accesul atât la funcționalități, cât și la datele specifice (conturi, tipuri de tranzacții).
* **Jurnalizare Acțiuni (Audit Log):** Înregistrarea acțiunilor importante efectuate de utilizatori pentru o trasabilitate completă.

---

## Arhitectura Tehnică

Aplicația implementează o arhitectură **client-server** clasică:

* **Client (GUI):** Interfața grafică, construită cu **Tkinter**, este responsabilă de interacțiunea cu utilizatorul și prezentarea datelor. Logica interfeței este structurată în module specializate (`btextrasviewer_main.py`, `ui_dialogs.py`, `ui_reports.py`).

* **Server (Baza de Date):** Un server **MariaDB** sau **MySQL** acționează ca backend, centralizând toate datele: utilizatori, roluri, permisiuni, conturi, tranzacții, istoric și setări personalizate.

* **Strat de Acces la Date (DAL):** Modulul `db_handler.py` servește ca unică punte de legătură între client și server. Acesta abstractizează toate interogările SQL și gestionează conexiunea la baza de date.

* **Gestionarea Configurației:** Se folosește o abordare hibridă inteligentă:
    1.  **Fișier local `config.ini`:** Stochează *doar* credențialele de conectare la baza de date, permițând aplicației să localizeze serverul.
    2.  **Setări în Baza de Date:** Toate setările de interfață (filtre, lățimi de coloane, cont activ, configurații SMTP) sunt salvate în format JSON în profilul fiecărui utilizator din baza de date. Acest lucru asigură o experiență consistentă pentru utilizator, indiferent de mașina de pe care se conectează.

---

## Tehnologii Folosite

* **Limbaj:** Python
* **Interfață Grafică (GUI):** Tkinter, Ttk, Tkinter.scrolledtext, tkcalendar
* **Bază de Date:** MariaDB / MySQL
* **Conector Bază de Date:** `mysql-connector-python`, `SQLAlchemy` (utilizat de Pandas)
* **Manipulare Date:** `pandas`, `numpy`
* **Grafice și Rapoarte:** `matplotlib`, `reportlab`
* **Fișiere Excel:** `openpyxl`
* **Email (SMTP):** `smtplib`, `ssl`

---

## Cerințe preliminare

Înainte de a rula aplicația, asigurați-vă că aveți instalate următoarele:

1.  **Python:** Versiunea 3.9 sau mai recentă.
2.  **Server de Baze de Date:** O instanță funcțională de MariaDB sau MySQL.
3.  **Git:** Pentru a clona repository-ul.

---

## Instalare și Configurare

Urmați acești pași pentru a pune în funcțiune aplicația.

### Pasul 1: Clonarea Repository-ului

    git clone https://github.com/your-username/BTExtrasViewer.git
    cd BTExtrasViewer

### Pasul 2: Crearea Bazei de Date

Conectați-vă la serverul de baze de date și creați o bază de date goală pentru aplicație.

    CREATE DATABASE btextras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

*Notă: Puteți alege orice nume pentru baza de date.*

### Pasul 3: Instalarea Dependințelor

Este recomandat să creați un mediu virtual pentru a izola dependințele proiectului.

    # Crearea și activarea unui mediu virtual (pe Linux/macOS)
    python3 -m venv venv
    source venv/bin/activate

    # Pe Windows
    py -m venv venv
    venv\Scripts\activate

Instalați toate bibliotecile necesare:

    pip install mysql-connector-python pandas openpyxl matplotlib numpy tkcalendar reportlab sqlalchemy

---

## Utilizare

1.  **Prima Lansare și Configurarea Conexiunii:**
    La prima lansare, aplicația nu se va putea conecta și va afișa automat o fereastră de dialog pentru a introduce credențialele bazei de date (`MariaDBConfigDialog`).
    * **Host:** Adresa IP sau numele serverului de baze de date.
    * **Port:** Portul serverului (de obicei `3306`).
    * **Nume Bază Date:** Numele bazei de date create la pasul anterior (ex: `btextras_db`).
    * **Utilizator DB:** Utilizatorul cu drepturi pe acea bază de date.
    * **Parolă DB:** Parola utilizatorului.

2.  **Crearea Automată a Schemei:**
    După o conexiune reușită, aplicația va verifica și va crea automat toate tabelele necesare (`check_and_setup_database_schema`).

3.  **Autentificare:**
    Va apărea fereastra de login (`LoginDialog`). La prima rulare absolută, aplicația creează un utilizator implicit (`_seed_initial_data`):
    * **Utilizator:** `admin`
    * **Parolă:** `admin123`

    *Este **CRUCIAL** să schimbați această parolă imediat după prima autentificare.*

4.  **Lansarea Aplicației:**
    Executați scriptul principal din rădăcina proiectului:

        python btextrasviewer_main.py

---

## Sistemul de Roluri și Permisiuni (Analiză Detaliată)

Securitatea și accesul granular sunt pilonii centrali ai arhitecturii. Sistemul este implementat pe două niveluri distincte pentru a asigura o protecție completă.

### Structura Bazei de Date

Fundația sistemului este formată din 5 tabele interconectate:
* `utilizatori`: Stochează datele de login, setările `JSON` și dreptul de acces la tranzacții (`credit`/`debit`/`toate`).
* `roluri`: Definește rolurile (ex: `Administrator`, `Operator Date`).
* `utilizatori_roluri`: Leagă utilizatorii de roluri.
* `roluri_permisiuni`: Asociază rolurilor chei de permisiuni granulare (ex: `'manage_users'`, `'import_files'`).
* `utilizatori_conturi_permise`: Leagă direct utilizatorii de conturile bancare pe care au dreptul să le vadă.

### Niveluri de Securitate

#### Nivelul 1: Controlul Interfeței Grafice (UI)

Acest nivel determină **ce funcționalități poate vedea și accesa** un utilizator în aplicație.

* **Mecanism:** Metoda `has_permission(permission_key)` din `btextrasviewer_main.py` este folosită pentru a verifica drepturile utilizatorului logat.
* **Implementare:** Meniurile, opțiunile de meniu și butoanele principale sunt afișate sau activate condiționat. De exemplu, meniul "Administrare" și opțiunile sale sunt vizibile doar pentru utilizatorii cu permisiuni precum `manage_roles` sau `manage_accounts`. Rolul special **Administrator** are o permisiune `'all_permissions'` care îi oferă acces total.

#### Nivelul 2: Controlul Accesului la Date (Data-Level)

Acest nivel, cel mai important, determină **ce date poate vedea** un utilizator, chiar dacă are acces la o funcționalitate.

1.  **Restricționare la Nivel de Cont Bancar:**
    * **Mecanism:** Tabela `utilizatori_conturi_permise`.
    * **Implementare:** Lista de conturi afișată în meniul dropdown este populată doar cu conturile la care utilizatorul curent are acces explicit (`_populate_account_selector`). Astfel, un utilizator nu poate vizualiza sau rula rapoarte pentru un cont care nu i-a fost asignat.

2.  **Restricționare la Nivel de Tip de Tranzacție (Credit/Debit):**
    * **Mecanism:** Coloana `tranzactie_acces` din tabela `utilizatori`, care poate fi `'toate'`, `'credit'` sau `'debit'`.
    * **Implementare:** Aceasta este o formă de *Row-Level Security*. Toate interogările SQL care extrag tranzacții (`refresh_table`, rapoartele) sunt modificate dinamic prin metoda `_get_access_filter_sql()`. Aceasta adaugă la clauza `WHERE` o condiție suplimentară (`AND tip = 'credit'` sau `AND tip = 'debit'`), filtrând datele direct la sursă, în baza de date.

---

## Contribuții

Contribuțiile sunt binevenite! Vă rugăm să deschideți un "issue" pentru a discuta despre modificările pe care doriți să le faceți sau un "pull request" dacă ați implementat deja o funcționalitate sau o corecție.

---

## Licență

Acest proiect este licențiat sub licența MIT. Consultați fișierul `LICENSE` pentru mai multe detalii.

---
*BTExtrasViewer - © 2025 Regio Development. Toate drepturile rezervate.*