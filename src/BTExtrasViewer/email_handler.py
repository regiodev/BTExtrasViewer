# src/BTExtrasViewer/email_handler.py
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import os
import mimetypes
import sys

# Constanta pentru Content-ID-ul logo-ului
LOGO_CID = 'btextras_logo_01'
COMPANY_NAME = "SC Balneoclimaterica SRL"

def get_logo_path():
    """Helper pentru a determina calea corectă către logo."""
    if getattr(sys, 'frozen', False):
        # Calea în aplicația compilată (PyInstaller)
        base_path = os.path.dirname(sys.executable)
        # În structura compilată, assets este în directorul părinte al BTExtrasViewer.exe
        return os.path.join(base_path, "..", "assets", "logo_companie.png")
    else:
        # Calea în timpul dezvoltării (rulare din sursă)
        # Presupunem că email_handler.py este în src/BTExtrasViewer/
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, "..", "assets", "logo_companie.png")


def send_report_email(smtp_config, recipient_email, subject, html_body, attachment_path):
    """
    MODIFICAT: Trimite un email cu un raport PDF atașat, folosind un corp HTML formatat și logo.
    """
    if not all(smtp_config.get(k) for k in ['server', 'port', 'user', 'password', 'sender_email']):
        return False, "Setările SMTP sunt incomplete. Vă rugăm configurați SMTP din meniu."

    try:
        # Folosim 'related' pentru a putea încorpora imagini în HTML
        msg = MIMEMultipart('related')
        msg['From'] = smtp_config['sender_email']
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Creăm partea de conținut (HTML)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        # Fallback text simplu
        plain_text_part = MIMEText("Acest email conține un raport atașat și necesită un client de email compatibil HTML.", 'plain')
        msg_alternative.attach(plain_text_part)
        
        # Partea HTML (primită ca parametru)
        html_part = MIMEText(html_body, 'html')
        msg_alternative.attach(html_part)

        # Atașăm logo-ul
        logo_path = get_logo_path()
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_img = MIMEImage(f.read())
            logo_img.add_header('Content-ID', f'<{LOGO_CID}>')
            msg.attach(logo_img)

        # Atașăm fișierul PDF (din calea de pe disc)
        ctype, encoding = mimetypes.guess_type(attachment_path)
        if ctype is None or encoding is not None:
            ctype = 'application/octet-stream'
        
        maintype, subtype = ctype.split('/', 1)

        with open(attachment_path, 'rb') as fp:
            part = MIMEBase(maintype, subtype)
            part.set_payload(fp.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(attachment_path)}',
        )
        msg.attach(part)

        # Logica de trimitere (neschimbată)
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

    # Gestionarea erorilor (neschimbată)
    except smtplib.SMTPAuthenticationError:
        return False, "Eroare de autentificare. Verificați utilizatorul și parola SMTP."
    except smtplib.SMTPServerDisconnected:
        return False, "Serverul SMTP s-a deconectat. Verificați setările și conexiunea la internet."
    except ConnectionRefusedError:
        return False, f"Conexiune refuzată de serverul {smtp_config['server']}. Verificați adresa serverului și portul."
    except Exception as e:
        return False, f"A apărut o eroare la trimiterea emailului:\n{type(e).__name__}: {e}"

def send_email_with_memory_attachment(smtp_config, recipient_email, subject, html_body, attachment_buffer, attachment_filename, logo_path=None, logo_cid=None):
    """
    Trimite un email cu un corp HTML și un atașament din memorie (BytesIO).
    Această funcție rămâne neschimbată, fiind folosită pentru exporturile Excel.
    """
    if not all(smtp_config.get(k) for k in ['server', 'port', 'user', 'password', 'sender_email']):
        return False, "Setările SMTP sunt incomplete. Vă rugăm configurați SMTP din meniu."

    try:
        # Folosim 'alternative' pentru a trimite atât HTML, cât și un fallback text simplu
        msg = MIMEMultipart('related')
        msg['From'] = smtp_config['sender_email']
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Creăm partea de conținut (HTML)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        # Fallback text simplu (opțional, dar bună practică)
        plain_text_part = MIMEText("Acest email conține conținut HTML și necesită un client de email compatibil.", 'plain')
        msg_alternative.attach(plain_text_part)
        
        # Partea HTML
        html_part = MIMEText(html_body, 'html')
        msg_alternative.attach(html_part)

        # Atașăm imaginea logo (dacă există) și o legăm prin Content-ID (cid)
        # Folosim get_logo_path() pentru consistență
        logo_path = get_logo_path() 
        if logo_path and logo_cid and os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_img = MIMEImage(f.read())
            logo_img.add_header('Content-ID', f'<{logo_cid}>')
            msg.attach(logo_img)

        # Atașăm fișierul Excel din bufferul de memorie
        excel_part = MIMEBase('application', "octet-stream")
        excel_part.set_payload(attachment_buffer.getvalue())
        encoders.encode_base64(excel_part)
        excel_part.add_header('Content-Disposition', f'attachment; filename="{attachment_filename}"')
        msg.attach(excel_part)

        # Logica de trimitere rămâne identică
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
    # Funcția rămâne neschimbată
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
    
def send_password_reset_email(smtp_config, recipient_email, subject, html_body):
    """Trimite un email simplu, formatat HTML, fără atașamente."""
    if not all(smtp_config.get(k) for k in ['server', 'port', 'user', 'password', 'sender_email']):
        return False, "Setările SMTP sunt incomplete."

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_config['sender_email']
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Atașăm corpul HTML
        msg.attach(MIMEText(html_body, 'html'))

        server = None
        security = smtp_config.get('security', 'SSL/TLS')

        if security == 'SSL/TLS':
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config['port'], context=context)
        else: # Include STARTTLS și 'Niciuna'
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
            if security == 'STARTTLS':
                server.starttls(context=ssl.create_default_context())
        
        server.login(smtp_config['user'], smtp_config['password'])
        server.send_message(msg)
        server.quit()
        
        return True, "Emailul a fost trimis cu succes!"

    except Exception as e:
        logging.error(f"Eroare la trimiterea emailului de resetare: {e}", exc_info=True)
        return False, str(e)