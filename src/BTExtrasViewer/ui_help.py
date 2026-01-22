# BTExtrasViewer/ui_help.py
# Sistem de Help profesional cu navigare, TOC și căutare

import tkinter as tk
from tkinter import ttk
import re

from common.app_constants import APP_NAME, APP_VERSION
from BTExtrasViewer.help_content import (
    HELP_SECTIONS, TOP_LEVEL_SECTIONS,
    get_section, get_section_title, get_section_icon,
    get_section_children, get_section_see_also, search_sections
)


class HelpBrowser(tk.Toplevel):
    """
    Browser de Help profesional cu:
    - Cuprins (TOC) în stânga cu secțiuni expandabile
    - Conținut formatat în dreapta
    - Navigare înapoi/înainte
    - Căutare în conținut
    - Link-uri cross-reference între secțiuni
    """

    def __init__(self, parent, initial_topic_id='welcome'):
        super().__init__(parent)
        self.title(f"Ghid de Utilizare - {APP_NAME}")
        self.geometry("1000x700")
        self.minsize(800, 500)
        self.transient(parent)

        # Starea navigării
        self.history = []
        self.history_index = -1
        self.current_section_id = None

        # Configurare stil
        self._configure_styles()

        # Creare widget-uri
        self._create_widgets()
        self._configure_text_tags()
        self._populate_toc()

        # Navigare la secțiunea inițială
        self.navigate_to(initial_topic_id, add_to_history=True)

        # Centrare fereastră
        self._center_window()

        # Bind pentru închidere cu Escape
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _configure_styles(self):
        """Configurează stilurile ttk."""
        style = ttk.Style()

        # Stil pentru Treeview-ul TOC
        style.configure(
            "Help.Treeview",
            font=("Segoe UI", 10),
            rowheight=28
        )
        style.configure(
            "Help.Treeview.Heading",
            font=("Segoe UI", 10, "bold")
        )

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
        """Creează structura de widget-uri."""
        # Frame principal
        main_frame = ttk.Frame(self, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === TOOLBAR ===
        self._create_toolbar(main_frame)

        # === PANELED WINDOW (TOC + CONTENT) ===
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Panel stânga - TOC
        toc_frame = self._create_toc_panel(paned)
        paned.add(toc_frame, weight=0)

        # Panel dreapta - Conținut
        content_frame = self._create_content_panel(paned)
        paned.add(content_frame, weight=1)

    def _create_toolbar(self, parent):
        """Creează bara de instrumente."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        # Butoane de navigare
        nav_frame = ttk.Frame(toolbar)
        nav_frame.pack(side=tk.LEFT)

        # Buton Acasă
        self.home_btn = ttk.Button(
            nav_frame, text="Acasa", width=8,
            command=lambda: self.navigate_to('welcome', add_to_history=True)
        )
        self.home_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Buton Înapoi
        self.back_btn = ttk.Button(
            nav_frame, text="< Inapoi", width=10,
            command=self._go_back
        )
        self.back_btn.pack(side=tk.LEFT, padx=(0, 2))

        # Buton Înainte
        self.forward_btn = ttk.Button(
            nav_frame, text="Inainte >", width=10,
            command=self._go_forward
        )
        self.forward_btn.pack(side=tk.LEFT)

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=15
        )

        # Căutare
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="Cauta:").pack(side=tk.LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", lambda e: self._perform_search())

        self.search_btn = ttk.Button(
            search_frame, text="Cauta",
            command=self._perform_search
        )
        self.search_btn.pack(side=tk.LEFT)

        # Buton pentru a șterge căutarea și a reveni
        self.clear_search_btn = ttk.Button(
            search_frame, text="X", width=3,
            command=self._clear_search
        )
        self.clear_search_btn.pack(side=tk.LEFT, padx=(5, 0))

    def _create_toc_panel(self, parent):
        """Creează panoul cu cuprinsul (TOC)."""
        frame = ttk.Frame(parent, width=280)
        frame.pack_propagate(False)

        # Titlu TOC
        title_label = ttk.Label(
            frame, text="Cuprins",
            font=("Segoe UI", 11, "bold")
        )
        title_label.pack(pady=(5, 10), anchor=tk.W, padx=5)

        # Treeview pentru TOC
        toc_container = ttk.Frame(frame)
        toc_container.pack(fill=tk.BOTH, expand=True)

        self.toc_tree = ttk.Treeview(
            toc_container,
            style="Help.Treeview",
            show="tree",
            selectmode="browse"
        )

        # Scrollbar pentru TOC
        toc_scroll = ttk.Scrollbar(
            toc_container, orient=tk.VERTICAL,
            command=self.toc_tree.yview
        )
        self.toc_tree.configure(yscrollcommand=toc_scroll.set)

        self.toc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        toc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind pentru selecție în TOC
        self.toc_tree.bind("<<TreeviewSelect>>", self._on_toc_select)

        return frame

    def _create_content_panel(self, parent):
        """Creează panoul cu conținutul."""
        frame = ttk.Frame(parent)

        # Text widget pentru conținut
        content_container = ttk.Frame(frame)
        content_container.pack(fill=tk.BOTH, expand=True)

        self.content_text = tk.Text(
            content_container,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            padx=20,
            pady=15,
            cursor="arrow",
            state=tk.DISABLED
        )

        # Scrollbar pentru conținut
        content_scroll = ttk.Scrollbar(
            content_container, orient=tk.VERTICAL,
            command=self.content_text.yview
        )
        self.content_text.configure(yscrollcommand=content_scroll.set)

        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        return frame

    def _configure_text_tags(self):
        """Configurează tag-urile pentru formatarea textului."""
        text = self.content_text

        # Titluri
        text.tag_configure('h1', font=('Segoe UI', 18, 'bold'),
                          foreground='#2c3e50', spacing3=15, spacing1=10)
        text.tag_configure('h2', font=('Segoe UI', 14, 'bold'),
                          foreground='#34495e', spacing3=10, spacing1=15)
        text.tag_configure('h3', font=('Segoe UI', 12, 'bold'),
                          foreground='#2980b9', spacing3=8, spacing1=12)

        # Text normal și formatări
        text.tag_configure('p', spacing1=5, spacing3=8, lmargin1=0, lmargin2=0)
        text.tag_configure('bold', font=('Segoe UI', 10, 'bold'))
        text.tag_configure('italic', font=('Segoe UI', 10, 'italic'))
        text.tag_configure('code', font=('Consolas', 10), background='#f5f5f5',
                          relief=tk.FLAT)
        text.tag_configure('kbd', font=('Consolas', 9, 'bold'), background='#ecf0f1',
                          foreground='#2c3e50', relief=tk.RAISED, borderwidth=1)

        # Liste
        text.tag_configure('bullet', lmargin1=25, lmargin2=45, spacing1=3, spacing3=3)
        text.tag_configure('bullet_icon', foreground='#3498db')

        # Box-uri speciale
        text.tag_configure('tip_box', background='#e8f6f3', lmargin1=15, lmargin2=15,
                          rmargin=15, spacing1=10, spacing3=10, relief=tk.FLAT,
                          borderwidth=0)
        text.tag_configure('tip_icon', foreground='#27ae60', font=('Segoe UI', 10, 'bold'))
        text.tag_configure('tip_text', foreground='#1e8449')

        text.tag_configure('warning_box', background='#fef9e7', lmargin1=15, lmargin2=15,
                          rmargin=15, spacing1=10, spacing3=10)
        text.tag_configure('warning_icon', foreground='#f39c12', font=('Segoe UI', 10, 'bold'))
        text.tag_configure('warning_text', foreground='#9a7d0a')

        text.tag_configure('note_box', background='#eaf2f8', lmargin1=15, lmargin2=15,
                          rmargin=15, spacing1=10, spacing3=10)
        text.tag_configure('note_icon', foreground='#3498db', font=('Segoe UI', 10, 'bold'))
        text.tag_configure('note_text', foreground='#2471a3')

        # Link-uri
        text.tag_configure('link', foreground='#3498db', underline=True)
        text.tag_bind('link', '<Enter>', lambda e: text.config(cursor='hand2'))
        text.tag_bind('link', '<Leave>', lambda e: text.config(cursor='arrow'))

        # Secțiune "Vezi și"
        text.tag_configure('see_also_header', font=('Segoe UI', 10, 'bold'),
                          foreground='#7f8c8d', spacing1=20)
        text.tag_configure('see_also_link', foreground='#3498db', underline=True)

        # Rezultate căutare
        text.tag_configure('search_highlight', background='#f9e79f')

    def _populate_toc(self):
        """Populează arborele de cuprins."""
        self.toc_tree.delete(*self.toc_tree.get_children())

        # Adăugăm secțiunile de top-level
        for section_id in TOP_LEVEL_SECTIONS:
            section = get_section(section_id)
            if not section:
                continue

            icon = get_section_icon(section_id)
            title = get_section_title(section_id)

            # Inserăm secțiunea de top-level
            parent_iid = self.toc_tree.insert(
                '', 'end',
                iid=section_id,
                text=f"  {icon}  {title}",
                open=False
            )

            # Adăugăm copiii
            children = get_section_children(section_id)
            for child_id in children:
                child_section = get_section(child_id)
                if not child_section:
                    continue

                child_icon = get_section_icon(child_id)
                child_title = get_section_title(child_id)

                self.toc_tree.insert(
                    parent_iid, 'end',
                    iid=child_id,
                    text=f"    {child_icon}  {child_title}"
                )

    def _on_toc_select(self, event):
        """Handler pentru selectarea unei secțiuni din TOC."""
        selection = self.toc_tree.selection()
        if selection:
            section_id = selection[0]
            if section_id != self.current_section_id:
                self.navigate_to(section_id, add_to_history=True)

    def navigate_to(self, section_id, add_to_history=True):
        """Navighează la o secțiune specificată."""
        section = get_section(section_id)
        if not section:
            return

        # Actualizăm istoricul
        if add_to_history:
            # Ștergem tot ce e după poziția curentă
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append(section_id)
            self.history_index = len(self.history) - 1

        self.current_section_id = section_id

        # Actualizăm butoanele de navigare
        self._update_nav_buttons()

        # Selectăm în TOC
        self._select_in_toc(section_id)

        # Afișăm conținutul
        self._display_content(section)

    def _select_in_toc(self, section_id):
        """Selectează și expandează secțiunea în TOC."""
        # Verificăm dacă secțiunea există în TOC
        if self.toc_tree.exists(section_id):
            # Găsim părintele și îl expandăm
            parent = self.toc_tree.parent(section_id)
            if parent:
                self.toc_tree.item(parent, open=True)

            # Selectăm și facem vizibilă secțiunea
            self.toc_tree.selection_set(section_id)
            self.toc_tree.see(section_id)

    def _display_content(self, section):
        """Afișează conținutul unei secțiuni."""
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)

        content = section.get('content', '')
        self._parse_and_insert_content(content)

        # Adăugăm secțiunea "Vezi și"
        see_also = section.get('see_also', [])
        if see_also:
            self._insert_see_also(see_also)

        self.content_text.config(state=tk.DISABLED)

        # Scroll la început
        self.content_text.see('1.0')

    def _parse_and_insert_content(self, content):
        """Parsează și inserează conținutul formatat."""
        text = self.content_text

        # Regex pentru tag-uri
        patterns = {
            'h1': re.compile(r'<h1>(.*?)</h1>', re.DOTALL),
            'h2': re.compile(r'<h2>(.*?)</h2>', re.DOTALL),
            'h3': re.compile(r'<h3>(.*?)</h3>', re.DOTALL),
            'p': re.compile(r'<p>(.*?)</p>', re.DOTALL),
            'b': re.compile(r'<b>(.*?)</b>', re.DOTALL),
            'bullet': re.compile(r'<bullet>(.*?)</bullet>', re.DOTALL),
            'tip': re.compile(r'<tip>(.*?)</tip>', re.DOTALL),
            'warning': re.compile(r'<warning>(.*?)</warning>', re.DOTALL),
            'note': re.compile(r'<note>(.*?)</note>', re.DOTALL),
            'code': re.compile(r'<code>(.*?)</code>', re.DOTALL),
            'kbd': re.compile(r'<kbd>(.*?)</kbd>', re.DOTALL),
            'link': re.compile(r'<link id="([^"]+)">(.*?)</link>', re.DOTALL),
            'br': re.compile(r'<br/?>', re.DOTALL),
        }

        # Procesăm conținutul linie cu linie (simplificat)
        lines = content.strip().split('\n')
        current_pos = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # H1
            match = patterns['h1'].match(line)
            if match:
                text.insert(tk.END, match.group(1) + '\n', 'h1')
                continue

            # H2
            match = patterns['h2'].match(line)
            if match:
                text.insert(tk.END, match.group(1) + '\n', 'h2')
                continue

            # H3
            match = patterns['h3'].match(line)
            if match:
                text.insert(tk.END, match.group(1) + '\n', 'h3')
                continue

            # Tip box
            match = patterns['tip'].match(line)
            if match:
                content_text = match.group(1)
                content_text = self._process_inline_tags(content_text)
                text.insert(tk.END, '\n')
                text.insert(tk.END, '  Sfat: ', ('tip_box', 'tip_icon'))
                self._insert_with_inline_formatting(content_text, 'tip_text', 'tip_box')
                text.insert(tk.END, '\n\n')
                continue

            # Warning box
            match = patterns['warning'].match(line)
            if match:
                content_text = match.group(1)
                content_text = self._process_inline_tags(content_text)
                text.insert(tk.END, '\n')
                text.insert(tk.END, '  Atentie: ', ('warning_box', 'warning_icon'))
                self._insert_with_inline_formatting(content_text, 'warning_text', 'warning_box')
                text.insert(tk.END, '\n\n')
                continue

            # Note box
            match = patterns['note'].match(line)
            if match:
                content_text = match.group(1)
                content_text = self._process_inline_tags(content_text)
                text.insert(tk.END, '\n')
                text.insert(tk.END, '  Nota: ', ('note_box', 'note_icon'))
                self._insert_with_inline_formatting(content_text, 'note_text', 'note_box')
                text.insert(tk.END, '\n\n')
                continue

            # Bullet
            match = patterns['bullet'].match(line)
            if match:
                bullet_content = match.group(1)
                text.insert(tk.END, '  \u2022  ', ('bullet', 'bullet_icon'))
                self._insert_with_inline_formatting(bullet_content, None, 'bullet')
                text.insert(tk.END, '\n')
                continue

            # Paragraph
            match = patterns['p'].match(line)
            if match:
                p_content = match.group(1)
                self._insert_with_inline_formatting(p_content, None, 'p')
                text.insert(tk.END, '\n\n')
                continue

            # Link standalone
            match = patterns['link'].match(line)
            if match:
                link_id = match.group(1)
                link_text = match.group(2)
                self._insert_link(link_id, link_text)
                text.insert(tk.END, '\n')
                continue

            # Default - tratăm ca paragraf simplu dacă nu e gol
            if line and not line.startswith('<'):
                text.insert(tk.END, line + '\n', 'p')

    def _process_inline_tags(self, text):
        """Procesează tag-uri inline simple (br -> newline)."""
        text = re.sub(r'<br/?>', '\n', text)
        return text

    def _insert_with_inline_formatting(self, content, base_tag=None, additional_tag=None):
        """Inserează text cu formatare inline (bold, code, kbd, links)."""
        text = self.content_text

        # Pattern pentru tag-uri inline
        pattern = re.compile(r'(<b>.*?</b>|<code>.*?</code>|<kbd>.*?</kbd>|<link id="[^"]+">.*?</link>|<br/?>)')

        parts = pattern.split(content)
        tags_list = []
        if base_tag:
            tags_list.append(base_tag)
        if additional_tag:
            tags_list.append(additional_tag)
        tags = tuple(tags_list) if tags_list else None

        for part in parts:
            if not part:
                continue

            # Bold
            bold_match = re.match(r'<b>(.*?)</b>', part, re.DOTALL)
            if bold_match:
                bold_tags = list(tags_list) + ['bold'] if tags_list else ['bold']
                text.insert(tk.END, bold_match.group(1), tuple(bold_tags))
                continue

            # Code
            code_match = re.match(r'<code>(.*?)</code>', part, re.DOTALL)
            if code_match:
                code_tags = list(tags_list) + ['code'] if tags_list else ['code']
                text.insert(tk.END, code_match.group(1), tuple(code_tags))
                continue

            # Kbd
            kbd_match = re.match(r'<kbd>(.*?)</kbd>', part, re.DOTALL)
            if kbd_match:
                kbd_tags = list(tags_list) + ['kbd'] if tags_list else ['kbd']
                text.insert(tk.END, kbd_match.group(1), tuple(kbd_tags))
                continue

            # Link
            link_match = re.match(r'<link id="([^"]+)">(.*?)</link>', part, re.DOTALL)
            if link_match:
                self._insert_link(link_match.group(1), link_match.group(2))
                continue

            # BR
            if part == '<br>' or part == '<br/>':
                text.insert(tk.END, '\n')
                continue

            # Text normal
            if tags:
                text.insert(tk.END, part, tags)
            else:
                text.insert(tk.END, part)

    def _insert_link(self, section_id, link_text):
        """Inserează un link clickabil către o altă secțiune."""
        text = self.content_text

        # Creăm un tag unic pentru acest link
        tag_name = f"link_{section_id}_{text.index(tk.INSERT)}"

        # Configurăm tag-ul
        text.tag_configure(tag_name, foreground='#3498db', underline=True)

        # Bind-uri pentru hover și click
        text.tag_bind(tag_name, '<Enter>',
                     lambda e: text.config(cursor='hand2'))
        text.tag_bind(tag_name, '<Leave>',
                     lambda e: text.config(cursor='arrow'))
        text.tag_bind(tag_name, '<Button-1>',
                     lambda e, sid=section_id: self.navigate_to(sid, add_to_history=True))

        # Inserăm textul link-ului
        text.insert(tk.END, f"  \u2192  {link_text}", tag_name)

    def _insert_see_also(self, see_also_ids):
        """Inserează secțiunea 'Vezi și' la sfârșitul conținutului."""
        text = self.content_text

        text.insert(tk.END, '\n\n')
        text.insert(tk.END, '\u2500' * 50 + '\n')
        text.insert(tk.END, 'Vezi si: ', 'see_also_header')

        for i, section_id in enumerate(see_also_ids):
            title = get_section_title(section_id)

            # Creăm tag unic pentru link
            tag_name = f"see_also_{section_id}_{i}"
            text.tag_configure(tag_name, foreground='#3498db', underline=True)
            text.tag_bind(tag_name, '<Enter>',
                         lambda e: text.config(cursor='hand2'))
            text.tag_bind(tag_name, '<Leave>',
                         lambda e: text.config(cursor='arrow'))
            text.tag_bind(tag_name, '<Button-1>',
                         lambda e, sid=section_id: self.navigate_to(sid, add_to_history=True))

            text.insert(tk.END, title, tag_name)

            if i < len(see_also_ids) - 1:
                text.insert(tk.END, '  |  ')

        text.insert(tk.END, '\n')

    def _update_nav_buttons(self):
        """Actualizează starea butoanelor de navigare."""
        # Buton Înapoi
        if self.history_index > 0:
            self.back_btn.config(state=tk.NORMAL)
        else:
            self.back_btn.config(state=tk.DISABLED)

        # Buton Înainte
        if self.history_index < len(self.history) - 1:
            self.forward_btn.config(state=tk.NORMAL)
        else:
            self.forward_btn.config(state=tk.DISABLED)

    def _go_back(self):
        """Navighează înapoi în istoric."""
        if self.history_index > 0:
            self.history_index -= 1
            section_id = self.history[self.history_index]
            self.navigate_to(section_id, add_to_history=False)

    def _go_forward(self):
        """Navighează înainte în istoric."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            section_id = self.history[self.history_index]
            self.navigate_to(section_id, add_to_history=False)

    def _perform_search(self):
        """Efectuează căutarea în conținutul help."""
        query = self.search_var.get().strip()
        if not query or len(query) < 2:
            return

        results = search_sections(query)
        self._display_search_results(query, results)

    def _display_search_results(self, query, results):
        """Afișează rezultatele căutării."""
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)

        text = self.content_text

        text.insert(tk.END, f'Rezultate cautare: "{query}"\n', 'h1')
        text.insert(tk.END, f'{len(results)} rezultat(e) gasite\n\n', 'p')

        if not results:
            text.insert(tk.END, 'Nu au fost gasite rezultate pentru cautarea dumneavoastra.\n\n', 'p')
            text.insert(tk.END, 'Sugestii:\n', 'h3')
            text.insert(tk.END, '  \u2022  Verificati ortografia\n', 'bullet')
            text.insert(tk.END, '  \u2022  Incercati termeni mai generali\n', 'bullet')
            text.insert(tk.END, '  \u2022  Folositi cuvinte cheie diferite\n', 'bullet')
        else:
            for result in results:
                section_id = result['id']
                title = result['title']
                icon = result['icon']
                context = result.get('context', '')

                # Creăm link pentru rezultat
                tag_name = f"search_result_{section_id}"
                text.tag_configure(tag_name, foreground='#2980b9', underline=True,
                                  font=('Segoe UI', 11, 'bold'))
                text.tag_bind(tag_name, '<Enter>',
                             lambda e: text.config(cursor='hand2'))
                text.tag_bind(tag_name, '<Leave>',
                             lambda e: text.config(cursor='arrow'))
                text.tag_bind(tag_name, '<Button-1>',
                             lambda e, sid=section_id: self.navigate_to(sid, add_to_history=True))

                text.insert(tk.END, f'{icon}  ', 'bullet_icon')
                text.insert(tk.END, title, tag_name)
                text.insert(tk.END, '\n')

                if context:
                    text.insert(tk.END, f'   {context}\n', 'p')

                text.insert(tk.END, '\n')

        self.content_text.config(state=tk.DISABLED)
        self.content_text.see('1.0')

    def _clear_search(self):
        """Șterge căutarea și revine la secțiunea curentă."""
        self.search_var.set('')
        if self.current_section_id:
            section = get_section(self.current_section_id)
            if section:
                self._display_content(section)


# Funcție de compatibilitate pentru codul existent
class HelpDialog(HelpBrowser):
    """Alias pentru compatibilitate cu codul existent."""
    pass


def show_help_browser(parent, initial_topic_id='welcome'):
    """
    Funcție helper pentru a afișa browserul de help.
    """
    browser = HelpBrowser(parent, initial_topic_id=initial_topic_id)
    browser.wait_window()
