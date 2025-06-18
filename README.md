# BTExtrasViewer v3.4

O aplicație desktop pentru vizualizarea și analiza extraselor de cont în format MT940, cu conectare la o bază de date MariaDB/MySQL.

## Caracteristici Principale
- Import de fișiere MT940 multiple.
- Gestionare multi-cont cu IBAN-uri și valute diferite.
- Căutare și filtrare avansată a tranzacțiilor.
- Generare de rapoarte: Flux de Numerar, Evoluție Sold, Analiză Tranzacții.
- Export în format Excel și PDF.
- Trimitere rapoarte pe email prin SMTP.

## Instalare și Dependențe

### Prerechezite
Acest program necesită **Python 3.8+** și o bază de date **MariaDB (sau MySQL)** accesibilă.

De asemenea, pe sistemele Windows, este posibil să fie necesar pachetul **Microsoft C++ Redistributable**. Acesta poate fi descărcat de pe site-ul oficial Microsoft.

### Dependențe Python
Pentru a instala bibliotecile necesare, rulează următoarea comandă în terminal, în folderul proiectului:
```bash
pip install -r requirements.txt