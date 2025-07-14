# src/BTExtrasViewer/email_composer.py

from datetime import datetime
from common.app_constants import APP_NAME

# Paleta de culori globală
HEADER_COLOR = "#005A9E"  # Albastru închis
BG_COLOR = "#F4F7F9"      # Un gri foarte deschis
TABLE_HEADER_BG = "#EAECEE"
TEXT_COLOR = "#34495E"
BORDER_COLOR = "#D5DBDB"

def _get_base_styles():
    """Returnează stilurile CSS de bază pentru template-urile de email."""
    return f"""
        <style>
            body {{ font-family: Arial, sans-serif; background-color: {BG_COLOR}; color: {TEXT_COLOR}; margin: 0; padding: 20px; }}
            .container {{ background-color: #ffffff; border: 1px solid {BORDER_COLOR}; border-radius: 8px; max-width: 680px; margin: auto; overflow: hidden; }}
            .header {{ background-color: {HEADER_COLOR}; padding: 20px; text-align: center; }}
            .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; }}
            .content {{ padding: 25px 30px; }}
            .content h2 {{ color: {HEADER_COLOR}; border-bottom: 2px solid {TABLE_HEADER_BG}; padding-bottom: 5px; font-size: 18px; }}
            .content p {{ line-height: 1.6; }}
            .filter-summary ul {{ list-style-type: none; padding-left: 0; }}
            .filter-summary li {{ background-color: {TABLE_HEADER_BG}; margin-bottom: 8px; padding: 10px; border-radius: 4px; border-left: 4px solid {HEADER_COLOR}; }}
            .footer {{ background-color: {TABLE_HEADER_BG}; padding: 20px 30px; font-size: 12px; color: #7F8C8D; }}
            .signature-table {{ width: 100%; }}
            .logo-cell {{ width: 80px; vertical-align: top; }}
            .logo-cell img {{ width: 70px; height: auto; }}
            .sender-details-cell {{ padding-left: 15px; vertical-align: top; }}
        </style>
    """

def create_password_token_html(username, token):
    """Generează corpul HTML pentru emailul care conține token-ul de resetare."""
    styles = _get_base_styles()
    
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">{styles}
    </head>
    <body>
        <div class="container">
            <div class="header"><h1>Cerere Resetare Parolă</h1></div>
            <div class="content">
                <p>Bună ziua, {username},</p>
                <p>Am primit o cerere de resetare a parolei pentru contul dumneavoastră în aplicația <strong>{APP_NAME}</strong>.</p>
                <p>Pentru a seta o parolă nouă, introduceți următorul cod de verificare în fereastra aplicației:</p>
                <div style="font-size: 18px; font-family: 'Courier New', monospace; text-align: center; padding: 15px; background-color: #f0f0f0; border: 1px dashed #ccc; margin: 20px 0; letter-spacing: 2px;">
                    {token}
                </div>
                <p>Acest cod este valabil timp de <strong>15 minute</strong>.</p>
                <p><strong>Important:</strong> Dacă nu ați solicitat această resetare, puteți ignora acest email în siguranță; parola dumneavoastră NU a fost schimbată.</p>
            </div>
            <div class="footer">
                 <p style="text-align: center; margin-top: 20px;">Email generat automat la data de {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_body

def _generate_signature_html(user_data, company_name, logo_cid):
    """Generează blocul de semnătură HTML."""
    sender_name = user_data.get('nume_complet') or user_data.get('username', 'Utilizator BTExtras')
    # Asigurăm că roles_list există, chiar dacă nu a fost populată anterior
    sender_role = ", ".join(user_data.get('roles_list', ['Utilizator']))
    sender_email = user_data.get('smtp_sender_email', 'Nespecificat')

    return f"""
    <div class="footer">
        <table class="signature-table">
            <tr>
                <td class="logo-cell">
                    <img src="cid:{logo_cid}" alt="Company Logo">
                </td>
                <td class="sender-details-cell">
                    <strong>{sender_name}</strong><br>
                    {sender_role}<br>
                    {company_name}<br>
                    Email: {sender_email}
                </td>
            </tr>
        </table>
        <p style="text-align: center; margin-top: 20px;">Email generat automat la data de {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}.</p>
    </div>
    """

def create_export_summary_html(user_data, filter_summary, company_name, logo_cid):
    """
    Generează corpul HTML profesional pentru emailul de notificare a exportului Excel.
    """
    # Construim sumarul filtrelor într-un format lizibil
    filter_lines = []
    if filter_summary.get('date_range_mode'):
        filter_lines.append(f"<li><b>Interval de date:</b> De la {filter_summary.get('start_date', 'N/A')} până la {filter_summary.get('end_date', 'N/A')}</li>")
    else:
        filter_lines.append(f"<li><b>Perioadă Navigare:</b> {filter_summary.get('nav_selection', 'Toate tranzacțiile')}</li>")

    filter_lines.append(f"<li><b>Tip Tranzacție:</b> {filter_summary.get('type', 'Toate')}</li>")
    if filter_summary.get('search_term'):
        filter_lines.append(f"<li><b>Termen Căutat:</b> '{filter_summary['search_term']}' în '{filter_summary['search_column']}'</li>")

    filters_html = "\n".join(filter_lines)
    signature_html = _generate_signature_html(user_data, company_name, logo_cid)
    styles = _get_base_styles()

    # Compunem documentul HTML
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
        {styles}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Export de Date - {company_name}</h1>
            </div>
            <div class="content">
                <p>Bună ziua,</p>
                <p>Atașat acestui email găsiți un export de tranzacții în format Excel, generat din aplicația <strong>BTExtras Suite</strong>.</p>
                
                <h2>Rezumat Export</h2>
                <div class="filter-summary">
                    <ul>
                        {filters_html}
                    </ul>
                </div>
                
                <p>Documentul atașat conține toate tranzacțiile care corespund acestor criterii de filtrare la data generării.</p>
            </div>
            {signature_html}
        </div>
    </body>
    </html>
    """
    return html_body

def create_report_delivery_html(user_data, report_name, company_name, logo_cid):
    """
    Generează corpul HTML profesional pentru emailul de livrare a unui raport PDF.
    """
    signature_html = _generate_signature_html(user_data, company_name, logo_cid)
    styles = _get_base_styles()

    # Compunem documentul HTML
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
        {styles}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Raport Financiar - {company_name}</h1>
            </div>
            <div class="content">
                <p>Bună ziua,</p>
                <p>Atașat acestui email găsiți raportul solicitat, în format PDF.</p>
                
                <h2>Detalii Raport</h2>
                <div class="filter-summary">
                    <ul>
                        <li><b>Tip Raport:</b> {report_name}</li>
                    </ul>
                </div>
                
                <p>Acest raport a fost generat automat de aplicația <strong>BTExtras Suite</strong> conform parametrilor selectați.</p>
            </div>
            {signature_html}
        </div>
    </body>
    </html>
    """
    return html_body

def create_password_reset_html(username, temporary_password):
    """Generează corpul HTML pentru emailul de resetare a parolei."""
    styles = _get_base_styles() # Refolosim stilurile definite
    
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
        {styles}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Resetare Parolă</h1>
            </div>
            <div class="content">
                <p>Bună ziua, {username},</p>
                <p>Ați solicitat o resetare a parolei pentru contul dumneavoastră în aplicația <strong>{APP_NAME}</strong>.</p>
                <p>Noua dumneavoastră parolă temporară este:</p>
                <div style="font-size: 20px; font-weight: bold; letter-spacing: 2px; text-align: center; padding: 15px; background-color: #f0f0f0; border-radius: 5px; margin: 20px 0;">
                    {temporary_password}
                </div>
                <p>Vă rugăm să folosiți această parolă pentru a vă autentifica. La prima autentificare, sistemul vă va solicita să setați o nouă parolă personală.</p>
                <p>Dacă nu ați solicitat această resetare, vă rugăm să ignorați acest email sau să contactați administratorul de sistem.</p>
            </div>
            <div class="footer">
                 <p style="text-align: center; margin-top: 20px;">Email generat automat la data de {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_body