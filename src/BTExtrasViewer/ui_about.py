# BTExtrasViewer/ui_about.py
# Dialog "Despre BTExtras Suite"

import tkinter as tk
from tkinter import ttk
import webbrowser
import os
import sys

from common.app_constants import APP_NAME, APP_VERSION, APP_COPYRIGHT


class AboutDialog(tk.Toplevel):
    """
    Dialog profesional pentru afișarea informațiilor despre aplicație.
    """

    # Informații despre dezvoltator
    DEVELOPER_NAME = "Regio Development SRL"
    DEVELOPER_WEBSITE = "https://regio-development.ro"
    DEVELOPER_EMAIL = "office@regio-development.ro"

    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"Despre {APP_NAME}")

        # Configurare fereastră
        self.geometry("420x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Configurare stil
        self.configure(bg="#ffffff")

        self._create_widgets()
        self._center_window()

        # Bind pentru închidere cu Escape
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _center_window(self):
        """Centrează fereastra relativ la fereastra părinte."""
        self.update_idletasks()
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{max(0, position_x)}+{max(0, position_y)}")

    def _create_widgets(self):
        """Creează widget-urile dialogului."""
        # Frame principal cu padding
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === LOGO ===
        logo_frame = ttk.Frame(main_frame)
        logo_frame.pack(pady=(0, 15))

        # Încercăm să încărcăm logo-ul
        logo_loaded = False
        try:
            # Determinăm calea către assets
            if getattr(sys, 'frozen', False):
                # Rulăm din executabil PyInstaller
                base_path = sys._MEIPASS
                logo_path = os.path.join(base_path, "assets", "BT_logo.ico")
            else:
                # Rulăm din sursă
                current_dir = os.path.dirname(os.path.abspath(__file__))
                logo_path = os.path.join(current_dir, "..", "assets", "BT_logo.ico")

            if os.path.exists(logo_path):
                # Încărcăm iconița ca PhotoImage
                self.logo_image = tk.PhotoImage(file=logo_path)
                # Redimensionăm dacă e prea mare
                if self.logo_image.width() > 80:
                    self.logo_image = self.logo_image.subsample(
                        self.logo_image.width() // 80
                    )
                logo_label = ttk.Label(logo_frame, image=self.logo_image)
                logo_label.pack()
                logo_loaded = True
        except Exception:
            pass

        # Dacă logo-ul nu s-a încărcat, afișăm un icon text
        if not logo_loaded:
            icon_label = ttk.Label(
                logo_frame,
                text="BT",
                font=("Segoe UI", 36, "bold"),
                foreground="#2c3e50"
            )
            icon_label.pack()

        # === NUMELE APLICAȚIEI ===
        app_name_label = ttk.Label(
            main_frame,
            text="BTExtras Suite",
            font=("Segoe UI", 18, "bold"),
            foreground="#2c3e50"
        )
        app_name_label.pack(pady=(0, 5))

        # === VERSIUNEA ===
        version_label = ttk.Label(
            main_frame,
            text=f"Versiunea {APP_VERSION}",
            font=("Segoe UI", 11),
            foreground="#7f8c8d"
        )
        version_label.pack(pady=(0, 15))

        # === DESCRIERE ===
        description_label = ttk.Label(
            main_frame,
            text="Suită de aplicații pentru gestionarea\nși analiza extraselor de cont bancare",
            font=("Segoe UI", 10),
            foreground="#34495e",
            justify=tk.CENTER
        )
        description_label.pack(pady=(0, 20))

        # === SEPARATOR ===
        separator = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=10)

        # === INFORMAȚII DEZVOLTATOR ===
        dev_frame = ttk.Frame(main_frame)
        dev_frame.pack(pady=10)

        # Dezvoltator
        dev_title = ttk.Label(
            dev_frame,
            text="Dezvoltator",
            font=("Segoe UI", 9),
            foreground="#95a5a6"
        )
        dev_title.pack()

        dev_name = ttk.Label(
            dev_frame,
            text=self.DEVELOPER_NAME,
            font=("Segoe UI", 10, "bold"),
            foreground="#2c3e50"
        )
        dev_name.pack(pady=(2, 10))

        # Website (link clickabil)
        website_label = ttk.Label(
            dev_frame,
            text=self.DEVELOPER_WEBSITE.replace("https://", ""),
            font=("Segoe UI", 10),
            foreground="#3498db",
            cursor="hand2"
        )
        website_label.pack()
        website_label.bind("<Button-1>", lambda e: self._open_url(self.DEVELOPER_WEBSITE))
        website_label.bind("<Enter>", lambda e: website_label.configure(
            font=("Segoe UI", 10, "underline")
        ))
        website_label.bind("<Leave>", lambda e: website_label.configure(
            font=("Segoe UI", 10)
        ))

        # Email (link clickabil)
        email_label = ttk.Label(
            dev_frame,
            text=self.DEVELOPER_EMAIL,
            font=("Segoe UI", 10),
            foreground="#3498db",
            cursor="hand2"
        )
        email_label.pack(pady=(5, 0))
        email_label.bind("<Button-1>", lambda e: self._open_email(self.DEVELOPER_EMAIL))
        email_label.bind("<Enter>", lambda e: email_label.configure(
            font=("Segoe UI", 10, "underline")
        ))
        email_label.bind("<Leave>", lambda e: email_label.configure(
            font=("Segoe UI", 10)
        ))

        # === COPYRIGHT ===
        copyright_label = ttk.Label(
            main_frame,
            text=APP_COPYRIGHT,
            font=("Segoe UI", 9),
            foreground="#bdc3c7"
        )
        copyright_label.pack(side=tk.BOTTOM, pady=(20, 0))

        # === BUTON OK ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, pady=(10, 0))

        ok_button = ttk.Button(
            button_frame,
            text="OK",
            command=self.destroy,
            width=15
        )
        ok_button.pack()
        ok_button.focus_set()

        # Bind Enter pentru butonul OK
        ok_button.bind("<Return>", lambda e: self.destroy())

    def _open_url(self, url):
        """Deschide un URL în browser-ul implicit."""
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _open_email(self, email):
        """Deschide clientul de email pentru o nouă adresă."""
        try:
            webbrowser.open(f"mailto:{email}")
        except Exception:
            pass


def show_about_dialog(parent):
    """
    Funcție helper pentru a afișa dialogul About.
    """
    dialog = AboutDialog(parent)
    dialog.wait_window()
