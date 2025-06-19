# auth_handler.py
import hashlib
import os
import logging
import hmac

# Constante pentru hashing - MODIFICATE PENTRU CORECTITUDINE
HASH_NAME = 'sha256'      # Algoritmul de hash care va fi folosit de PBKDF2
HASH_ITERATIONS = 390000  # Am crescut numărul de iterații pentru securitate sporită (recomandat de OWASP în 2023)
HASH_SALT_SIZE = 16       # Dimensiunea salt-ului în bytes

def hash_parola(parola: str) -> tuple[str, str]:
    """
    Generează un salt aleatoriu și criptează parola folosind PBKDF2.
    
    Returnează:
        Un tuplu conținând (salt-ul în format hex, hash-ul parolei în format hex).
    """
    salt = os.urandom(HASH_SALT_SIZE)
    # Apelul funcției a fost CORECTAT - are 5 argumente
    hash_derivat = hashlib.pbkdf2_hmac(
        HASH_NAME,                 # 1. Numele algoritmului de hash
        parola.encode('utf-8'),    # 2. Parola
        salt,                      # 3. Salt-ul
        HASH_ITERATIONS,           # 4. Numărul de iterații
        dklen=None                 # 5. Lungimea cheii (se folosește default)
    )
    return salt.hex(), hash_derivat.hex()

def verifica_parola(parola_introdusa: str, salt_hex: str, hash_stocat_hex: str) -> bool:
    """
    Verifică dacă o parolă introdusă corespunde cu hash-ul stocat.
    
    Args:
        parola_introdusa: Parola în clar, introdusă de utilizator.
        salt_hex: Salt-ul stocat (în format hex) asociat cu utilizatorul.
        hash_stocat_hex: Hash-ul parolei stocat (în format hex).

    Returnează:
        True dacă parola este corectă, False altfel.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        hash_stocat = bytes.fromhex(hash_stocat_hex)
    except (ValueError, TypeError):
        logging.error("Salt-ul sau hash-ul stocat nu este într-un format hex valid.")
        return False

    # Apelul funcției a fost CORECTAT
    hash_nou_derivat = hashlib.pbkdf2_hmac(
        HASH_NAME,
        parola_introdusa.encode('utf-8'),
        salt,
        HASH_ITERATIONS,
        dklen=None
    )
    
    # Comparație sigură, rezistentă la "timing attacks"
    return hmac.compare_digest(hash_nou_derivat, hash_stocat)