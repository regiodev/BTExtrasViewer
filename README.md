# BTExtras Suite v4.4.2

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-activ-brightgreen)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

**BTExtras Suite** este o suită de aplicații desktop complexe, de tip client-server, destinată gestiunii, vizualizării și analizei extraselor de cont bancare, cu funcționalități integrate de comunicare securizată. Construită în Python, suita oferă o soluție multi-utilizator robustă, cu un sistem avansat de roluri și permisiuni, stocând datele într-o bază de date centralizată MariaDB/MySQL.

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

* **Sistem Centralizat (Session Manager):** O componentă discretă care rulează în system tray, gestionează procesele aplicațiilor, oferă acces rapid prin iconiță și comenzi rapide globale (hotkeys).
* **Management Multi-Cont (Viewer):** Gestionarea centralizată a mai multor conturi bancare.
* **Import Avansat MT940 (Viewer):** Procesarea fișierelor de extras de cont în format MT940, cu detecție automată a IBAN-ului, prevenirea duplicatelor și crearea de noi conturi direct din fluxul de import.
* **Comunicare Integrată (Chat):** O aplicație de chat securizată, multi-utilizator, pentru comunicare internă, cu suport pentru conversații de grup și status online.
* **Vizualizare și Filtrare Detaliată (Viewer):** O interfață puternică pentru vizualizarea tranzacțiilor, cu navigare ierarhică (an/lună/zi) și opțiuni avansate de filtrare și căutare.
* **Sistem de Raportare Complex (Viewer):** Generarea de rapoarte vizuale și tabelare:
    * Analiză Flux de Numerar (Cash Flow).
    * Grafic de Evoluție a Soldului.
    * Analiză Detaliată a Tranzacțiilor pe categorii.
* **Exporturi Multiple:** Toate datele filtrate și rapoartele pot fi exportate în format **Excel (.xlsx)** sau **PDF**.
* **Notificări prin Email:** Posibilitatea de a trimite rapoartele generate direct pe email, folosind o configurație SMTP personală.
* **Securitate Multi-Utilizator:** Un sistem granular de roluri și permisiuni care controlează accesul atât la funcționalități, cât și la datele specifice (conturi, tipuri de tranzacții).
* **Jurnalizare Acțiuni (Audit Log):** Înregistrarea acțiunilor importante efectuate de utilizatori pentru o trasabilitate completă.

---

## Arhitectura Tehnică

Suita implementează o arhitectură **multi-proces** cu un backend centralizat:

* **Session Manager:** Piesa centrală a suitei. Un proces persistent și ușor care rulează în fundal, fiind responsabil de:
    * Lansarea și gestionarea aplicațiilor `Viewer` și `Chat`.
    * Crearea unei iconițe în system tray pentru acces rapid.
    * Înregistrarea de comenzi rapide globale (hotkeys) pentru a aduce în prim-plan ferestrele aplicațiilor.

* **Aplicații Client (GUI):**
    * **BTExtrasViewer:** Interfața principală pentru analiză de date, construită cu **Tkinter**. Logica este structurată în module specializate (`btextrasviewer_main.py`, `ui_dialogs.py`, `ui_reports.py`).
    * **BTExtrasChat:** Interfața pentru comunicare, construită de asemenea cu **Tkinter**.

* **Server (Baza de Date):** Un server **MariaDB** sau **MySQL** acționează ca backend, centralizând toate datele: utilizatori, roluri, permisiuni, conturi, tranzacții, mesaje de chat și setări personalizate.

* **Strat de Acces la Date (DAL):** Modulul `common/db_handler.py` servește ca unică punte de legătură între clienți și server. Acesta abstractizează toate interogările SQL și gestionează conexiunea la baza de date.

* **Gestionarea Configurației:** Se folosește o abordare hibridă:
    1.  **Fișier local `config.ini`:** Stochează *doar* credențialele de conectare la baza de date.
    2.  **Setări în Baza de Date:** Toate setările de interfață (filtre, lățimi de coloane, cont activ, configurații SMTP) sunt salvate în format JSON în profilul fiecărui utilizator.

---

## Tehnologii Folosite

* **Limbaj:** Python
* **Interfață Grafică (GUI):** Tkinter, Ttk, tkcalendar, pystray, Pillow
* **Bază de Date:** MariaDB / MySQL
* **Conector Bază de Date:** `pymysql`, `SQLAlchemy` (utilizat de Pandas)
* **Manipulare Date:** `pandas`, `numpy`
* **Grafice și Rapoarte:** `matplotlib`, `reportlab`
* **Fișiere Excel:** `openpyxl`
* **Evenimente Globale:** `keyboard`
* **Email (SMTP):** `smtplib`, `ssl`

---

## Cerințe preliminare

Înainte de a rula aplicația din sursă, asigurați-vă că aveți instalate următoarele:

1.  **Python:** Versiunea 3.9 sau mai recentă.
2.  **Server de Baze de Date:** O instanță funcțională de MariaDB sau MySQL.
3.  **Git:** Pentru a clona repository-ul.

---

## Instalare și Configurare

Urmați acești pași pentru a pune în funcțiune suita de aplicații.

### Pasul 1: Clonarea Repository-ului

    git clone https://github.com/your-username/BTExtras-Suite.git
    cd BTExtras-Suite

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

Instalați toate bibliotecile necesare folosind fișierul `requirements.txt`:

    pip install -r requirements.txt

---

## Utilizare

1.  **Lansarea Suitei:**
    Punctul de intrare principal al suitei este **Session Manager**. Acesta trebuie lansat primul și va rula în fundal.

        python src/session_manager.py

2.  **Prima Lansare și Configurarea Conexiunii:**
    * La prima lansare a unei aplicații client (ex: `BTExtrasViewer`) din meniul iconiței din system tray, aceasta nu se va putea conecta și va afișa automat o fereastră de dialog pentru a introduce credențialele bazei de date.
    * Completați detaliile: Host, Port, Nume Bază Date, Utilizator DB, Parolă DB.

3.  **Crearea Automată a Schemei:**
    După o conexiune reușită, aplicația va verifica și va crea automat toate tabelele necesare.

4.  **Autentificare:**
    * Va apărea fereastra de login. La prima rulare absolută, aplicația creează un utilizator implicit:
        * **Utilizator:** `admin`
        * **Parolă:** `admin123`
    * Este **CRUCIAL** să schimbați această parolă imediat după prima autentificare. Aplicația vă va forța să faceți acest lucru.

5.  **Accesarea Aplicațiilor:**
    * După autentificare, folosiți meniul iconiței din system tray (click dreapta) pentru a deschide **BTExtras Viewer** sau **BTExtras Chat**.
    * Folosiți comenzile rapide globale (`Ctrl+Alt+B` pentru Viewer, `Ctrl+Alt+C` pentru Chat) pentru a aduce rapid în prim-plan ferestrele aplicațiilor.

---

## Sistemul de Roluri și Permisiuni (Analiză Detaliată)

Securitatea și accesul granular sunt pilonii centrali ai arhitecturii. Sistemul este implementat pe două niveluri distincte pentru a asigura o protecție completă.

### Structura Bazei de Date

Fundația sistemului este formată din tabele interconectate, cele mai importante fiind:
* `utilizatori`: Stochează datele de login, setările `JSON` și dreptul de acces la tranzacții (`credit`/`debit`/`toate`).
* `roluri`: Definește rolurile (ex: `Administrator`, `Operator Date`).
* `utilizatori_roluri`: Leagă utilizatorii de roluri.
* `roluri_permisiuni`: Asociază rolurilor chei de permisiuni granulare (ex: `'manage_users'`, `'import_files'`).
* `utilizatori_conturi_permise`: Leagă direct utilizatorii de conturile bancare pe care au dreptul să le vadă.

### Niveluri de Securitate

#### Nivelul 1: Controlul Interfeței Grafice (UI)

Acest nivel determină **ce funcționalități poate vedea și accesa** un utilizator în aplicație.

* **Mecanism:** Metoda `has_permission(permission_key)` este folosită pentru a verifica drepturile utilizatorului logat.
* **Implementare:** Meniurile, opțiunile de meniu și butoanele principale sunt afișate sau activate condiționat. Rolul special **Administrator** are o permisiune `'all_permissions'` care îi oferă acces total.

#### Nivelul 2: Controlul Accesului la Date (Data-Level)

Acest nivel, cel mai important, determină **ce date poate vedea** un utilizator.

1.  **Restricționare la Nivel de Cont Bancar:**
    * **Mecanism:** Tabela `utilizatori_conturi_permise`.
    * **Implementare:** Lista de conturi afișată în meniul dropdown este populată doar cu conturile la care utilizatorul curent are acces explicit.

2.  **Restricționare la Nivel de Tip de Tranzacție (Credit/Debit):**
    * **Mecanism:** Coloana `tranzactie_acces` din tabela `utilizatori`.
    * **Implementare:** Aceasta este o formă de *Row-Level Security*. Toate interogările SQL care extrag tranzacții sunt modificate dinamic pentru a adăuga o condiție suplimentară (`AND tip = 'credit'` sau `AND tip = 'debit'`), filtrând datele direct la sursă.

---

## Contribuții

Contribuțiile sunt binevenite! Vă rugăm să deschideți un "issue" pentru a discuta despre modificările pe care doriți să le faceți sau un "pull request" dacă ați implementat deja o funcționalitate sau o corecție.

---

## Licență

Acest proiect este licențiat sub licența MIT. Consultați fișierul `LICENSE` pentru mai multe detalii.

---
*BTExtras Suite - © 2025 Regio Development. Toate drepturile rezervate.*