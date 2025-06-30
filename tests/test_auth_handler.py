# tests/test_auth_handler.py

import sys
import os

# Acest bloc de cod este esențial pentru a permite testelor să "vadă"
# și să importe module din pachetul 'common' și din restul aplicației.
# El adaugă directorul rădăcină al proiectului (cel de deasupra lui 'tests')
# în calea de căutare a modulelor Python.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from common import auth_handler

def test_verificare_parola_corecta():
    """
    Testează dacă o parolă corectă trece de validare.
    """
    parola_originala = "ParolaMeaSigura123"
    
    # 1. Generează un salt și un hash pentru parola originală
    salt, parola_hash = auth_handler.hash_parola(parola_originala)
    
    # 2. Verifică parola folosind salt-ul și hash-ul generate
    rezultat = auth_handler.verifica_parola(
        parola_introdusa=parola_originala,
        salt_hex=salt,
        hash_stocat_hex=parola_hash
    )
    
    # 3. Afirmă (assert) că rezultatul trebuie să fie Adevărat (True)
    assert rezultat is True

def test_verificare_parola_incorecta():
    """
    Testează dacă o parolă incorectă eșuează la validare.
    """
    parola_originala = "ParolaMeaSigura123"
    parola_gresita = "parolagresita"
    
    # 1. Generează un salt și un hash pentru parola originală
    salt, parola_hash = auth_handler.hash_parola(parola_originala)
    
    # 2. Încearcă să validezi parola GREȘITĂ folosind același salt și hash
    rezultat = auth_handler.verifica_parola(
        parola_introdusa=parola_gresita,
        salt_hex=salt,
        hash_stocat_hex=parola_hash
    )
    
    # 3. Afirmă (assert) că rezultatul trebuie să fie Fals (False)
    assert rezultat is False

def test_hash_uri_diferite_pentru_aceeasi_parola():
    """
    Testează dacă pentru aceeași parolă se generează hash-uri diferite,
    datorită folosirii unui salt aleatoriu de fiecare dată. Aceasta este
    o proprietate crucială a unui sistem de hashing sigur.
    """
    parola = "aceeasi_parola"
    
    # Generează primul set de salt și hash
    salt1, hash1 = auth_handler.hash_parola(parola)
    
    # Generează al doilea set de salt și hash
    salt2, hash2 = auth_handler.hash_parola(parola)
    
    # Afirmă (assert) că cele două salt-uri sunt diferite
    assert salt1 != salt2
    
    # Afirmă (assert) că și cele două hash-uri rezultate sunt diferite
    assert hash1 != hash2