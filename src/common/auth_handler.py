# src/common/auth_handler.py - VERSIUNE FINALĂ ȘI CORECTĂ

import hashlib
import os
import logging
import hmac

# Constante de securitate
HASH_SALT_SIZE = 16
HASH_NAME = 'sha256'
HASH_ITERATIONS = 390000

def hash_parola(parola: str) -> tuple[str, str]:
    """
    Generează un hash securizat pentru o parolă, folosind un salt aleatoriu.
    Returnează un tuplu (salt_hex, hash_hex).
    """
    salt = os.urandom(HASH_SALT_SIZE)
    hash_derivat = hashlib.pbkdf2_hmac(
        HASH_NAME,
        parola.encode('utf-8'),
        salt,
        HASH_ITERATIONS
    )
    return salt.hex(), hash_derivat.hex()

def verifica_parola(parola_introdusa: str, salt_hex: str, hash_stocat_hex: str) -> bool:
    """
    Verifică o parolă introdusă comparând-o cu hash-ul și sarea stocate.
    Acceptă sarea și hash-ul ca argumente separate.
    Returnează True dacă parola este corectă, altfel False.
    """
    try:
        # Verificăm dacă salt-ul și hash-ul stocat sunt valide, altfel returnăm False direct.
        if not salt_hex or not hash_stocat_hex:
            logging.error("Sarea (salt) sau hash-ul stocat sunt goale.")
            return False
        
        salt = bytes.fromhex(salt_hex)
        hash_stocat = bytes.fromhex(hash_stocat_hex)
    except (ValueError, TypeError) as e:
        logging.error(f"Sarea (salt) sau hash-ul stocat nu este într-un format hex valid: {e}")
        return False

    # Generăm un nou hash folosind parola introdusă și sarea stocată
    hash_nou_derivat = hashlib.pbkdf2_hmac(
        HASH_NAME,
        parola_introdusa.encode('utf-8'),
        salt,
        HASH_ITERATIONS
    )
    
    # Comparăm în mod sigur cele două hash-uri pentru a preveni atacurile de tip "timing"
    return hmac.compare_digest(hash_nou_derivat, hash_stocat)