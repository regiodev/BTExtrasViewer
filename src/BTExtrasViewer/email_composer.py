# src/BTExtrasViewer/email_composer.py
from datetime import datetime

def create_export_summary_html(user_data, filter_summary, company_name, logo_cid):
    """
    Generează corpul HTML profesional pentru emailul de notificare a exportului.

    :param user_data: Dicționar cu datele utilizatorului autentificat.
    :param filter_summary: Dicționar cu filtrele aplicate la momentul exportului.
    :param company_name: Numele companiei (hard-coded).
    :param logo_cid: Content-ID pentru logo-ul atașat.
    :return: Un string conținând corpul HTML al emailului.
    """

    # Paleta de culori inspirată de logo-ul companiei (un albastru închis corporativ)
    HEADER_COLOR = "#005A9E"  # Albastru închis
    BG_COLOR = "#F4F7F9"      # Un gri foarte deschis
    TABLE_HEADER_BG = "#EAECEE"
    TEXT_COLOR = "#34495E"
    BORDER_COLOR = "#D5DBDB"

    # Extragem datele utilizatorului pentru semnătură
    sender_name = user_data.get('nume_complet') or user_data.get('username', 'Utilizator BTExtras')
    sender_role = ", ".join(user_data.get('roles_list', ['Utilizator']))
    sender_email = user_data.get('smtp_sender_email', 'Nespecificat')

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

    # Compunem documentul HTML
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
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
        </div>
    </body>
    </html>
    """
    return html_body