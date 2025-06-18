# email_handler.py
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
# --- NOU: Importăm librăria pentru a detecta tipurile MIME ---
import mimetypes

def send_report_email(smtp_config, recipient_email, subject, body, attachment_path):
    """
    Construiește și trimite un email cu un atașament folosind setările SMTP furnizate.
    Returnează un tuplu (success: bool, message: str).
    """
    if not all(smtp_config.get(k) for k in ['server', 'port', 'user', 'password', 'sender_email']):
        return False, "Setările SMTP sunt incomplete. Vă rugăm configurați SMTP din meniu."

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config['sender_email']
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # --- MODIFICARE: Logica de creare a atașamentului ---
        # Detectăm tipul MIME pe baza extensiei fișierului
        ctype, encoding = mimetypes.guess_type(attachment_path)
        if ctype is None or encoding is not None:
            ctype = 'application/octet-stream'  # Tip generic dacă nu poate fi ghicit
        
        maintype, subtype = ctype.split('/', 1)

        # Citim conținutul fișierului și creăm atașamentul cu tipul MIME corect
        with open(attachment_path, 'rb') as fp:
            part = MIMEBase(maintype, subtype)
            part.set_payload(fp.read())
        # --------------------------------------------------------

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(attachment_path)}',
        )
        msg.attach(part)

        # Conectare și trimitere (codul rămâne neschimbat)
        server = None
        security = smtp_config.get('security', 'SSL/TLS')

        if security == 'SSL/TLS':
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config['port'], context=context)
        else:
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
            if security == 'STARTTLS':
                server.starttls(context=ssl.create_default_context())
        
        server.login(smtp_config['user'], smtp_config['password'])
        server.send_message(msg)
        server.quit()
        
        return True, "Emailul a fost trimis cu succes!"

    except smtplib.SMTPAuthenticationError:
        return False, "Eroare de autentificare. Verificați utilizatorul și parola SMTP."
    except smtplib.SMTPServerDisconnected:
        return False, "Serverul SMTP s-a deconectat. Verificați setările și conexiunea la internet."
    except ConnectionRefusedError:
        return False, f"Conexiune refuzată de serverul {smtp_config['server']}. Verificați adresa serverului și portul."
    except Exception as e:
        return False, f"A apărut o eroare la trimiterea emailului:\n{type(e).__name__}: {e}"

def test_smtp_connection(smtp_config):
    # ... (funcția existentă, neschimbată) ...
    if not all(smtp_config.get(k) for k in ['server', 'port', 'user', 'password']):
        return False, "Setările SMTP esențiale (server, port, user, parolă) sunt incomplete."

    try:
        server = None
        security = smtp_config.get('security', 'SSL/TLS')

        if security == 'SSL/TLS':
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config['port'], timeout=10, context=context)
        else:
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'], timeout=10)
            if security == 'STARTTLS':
                server.starttls(context=ssl.create_default_context())
        
        server.login(smtp_config['user'], smtp_config['password'])
        server.quit()
        return True, "Conexiune și autentificare reușite!"
    except Exception as e:
        return False, f"Testul a eșuat:\n{type(e).__name__}: {e}"