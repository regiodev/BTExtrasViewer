# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BTExtras Suite is a complex multi-application desktop suite for managing, viewing, and analyzing bank account statements (Romanian: "extrase de cont bancare"). It's a client-server system built in Python with Tkinter, using MariaDB/MySQL as the centralized backend.

The suite consists of three interconnected applications:
- **Session Manager** - Background process that runs in system tray and manages the lifecycle of other applications
- **BTExtrasViewer** - Main application for bank statement import, viewing, filtering, and reporting
- **BTExtrasChat** - Integrated secure chat application for internal communication

Version: 4.7.3

## Development Commands

### Setting Up Development Environment

```bash
# Create virtual environment
py -m venv venv            # Windows
python3 -m venv venv       # Linux/macOS

# Activate virtual environment
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

Before running the application, create a MariaDB/MySQL database:

```sql
CREATE DATABASE btextras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

On first launch, the application will prompt for database credentials (host, port, database name, user, password) which are saved to a local `config.ini` file. The database schema is created automatically on first connection.

### Dependency Management

The project uses `pip-compile` for dependency management:
- `requirements.in` - Lists top-level dependencies
- `requirements.txt` - Auto-generated locked dependencies

**Note:** `requirements.txt` uses `PyMySQL` as the MySQL connector (not `mysql-connector-python` from requirements.in). This is intentional as PyMySQL is a pure-Python implementation that's easier to package with PyInstaller.

To update dependencies:
```bash
pip-compile requirements.in
```

### Running the Application

```bash
# Launch the full suite (starts Session Manager)
python src/session_manager.py

# Run individual applications directly (for testing)
python src/BTExtrasViewer/btextrasviewer_main.py
python src/BTExtrasChat/chat_main.py
```

### Testing

```bash
# Run tests with pytest
pytest tests/

# Run specific test file
pytest tests/test_auth_handler.py

# Run with verbose output
pytest -v tests/
```

### Building Executables

The project uses PyInstaller to create executables and Inno Setup for the installer:

1. **Build executables with PyInstaller** (create .spec files as needed):
   ```bash
   # Build Session Manager
   pyinstaller --name "BTExtras Suite" --windowed --icon=src/assets/BT_logo.ico src/session_manager.py

   # Build Viewer
   pyinstaller --name "BTExtrasViewer" --windowed --icon=src/assets/BT_logo.ico src/BTExtrasViewer/btextrasviewer_main.py

   # Build Chat
   pyinstaller --name "BTExtrasChat" --windowed --icon=src/assets/BTExtrasChat.ico src/BTExtrasChat/chat_main.py
   ```

2. **Create installer** - The Inno Setup script `BTExtras_Suite_Installer.iss` expects executables in:
   - `dist/BTExtras Suite/` - Session Manager executable
   - `dist/BTExtrasViewer/` - Viewer executable
   - `dist/BTExtrasChat/` - Chat executable

   The installer includes three components:
   - **Core** (Session Manager) - Required, cannot be deselected
   - **Viewer** - Optional
   - **Chat** - Optional

   Compile with Inno Setup to generate the installer in `Installer/` directory.
   Output filename: `BTExtras_Suite_Setup_v4.7.3.exe`

## Architecture

### Multi-Process Design

The suite uses a **multi-process architecture** with inter-process communication (IPC) via TCP sockets:

1. **Session Manager** (`src/session_manager.py`) - Central orchestrator
   - Runs persistently in system tray
   - Launches and manages child applications
   - Listens on port 12343 for session commands
   - Registers global hotkeys: `Ctrl+Alt+B` (Viewer), `Ctrl+Alt+C` (Chat)
   - Tracks current authenticated user across all applications

2. **BTExtrasViewer** (`src/BTExtrasViewer/btextrasviewer_main.py`) - Main application
   - Listens on port 12344 for window commands (SHOW_WINDOW)
   - Handles bank statement imports (MT940 format)
   - Provides filtering, search, and reporting capabilities
   - Uses port 54322 as instance lock (prevents multiple instances)

3. **BTExtrasChat** (`src/BTExtrasChat/chat_main.py`) - Chat application
   - Listens on port 12345 for window commands
   - Multi-user chat with group conversations
   - Uses port 54323 as instance lock

### Data Access Layer

**`common/db_handler.py`** (1400+ lines) is the single point of contact with the database. Key responsibilities:
- Database connection management
- Schema creation and migration
- All SQL queries (accounts, transactions, users, roles, permissions, chat messages)
- User settings persistence (JSON format in database)

### Configuration Management

Hybrid approach (`common/config_management.py`):
1. **Local file** (`config.ini` in `%LOCALAPPDATA%\BTExtrasViewer\` on Windows): Stores ONLY database credentials (host, port, database, user, password)
2. **Database** (`utilizatori.setari_ui` column): Stores all UI settings as JSON (filters, window geometry, column widths, SMTP config, active account)

**Important:** Database credentials are stored in plaintext in the local config file. Ensure appropriate file system permissions are set.

### Security Architecture

**Two-level security system:**

#### Level 1: UI Permissions
- Controlled by `roluri_permisiuni` table with permission keys (e.g., `manage_users`, `import_files`)
- Method: `has_permission(permission_key)` checks user's roles
- Special role "Administrator" has `all_permissions` flag

#### Level 2: Data-Level Access Control (Row-Level Security)
1. **Account-based filtering**: `utilizatori_conturi_permise` table restricts which bank accounts a user can view
2. **Transaction type filtering**: `utilizatori.tranzactie_acces` column ('toate', 'credit', 'debit') dynamically adds WHERE clauses to all transaction queries

### Database Schema

Key tables:
- `utilizatori` - User accounts with password hashes (using PBKDF2 with salt), settings JSON, transaction access level
- `parola_reset_tokens` - Password reset tokens with expiration
- `roluri`, `utilizatori_roluri`, `roluri_permisiuni` - Role-based access control
- `utilizatori_conturi_permise` - User-to-account permissions (data-level security)
- `conturi_bancare` - Bank accounts with IBAN, currency, color coding
- `tranzactii` - Transactions linked to accounts with various metadata (CIF, factura, beneficiar, TID, RRN, PAN)
- `tipuri_tranzactii` - Transaction type codes and descriptions
- `swift_code_descriptions` - SWIFT code lookup
- `istoric_importuri` - Import history tracking
- `mesaje` - Chat messages (in Chat application)

### Module Structure

**Common modules** (`src/common/`):
- `app_constants.py` - Application constants (ports, hotkeys, version, display columns)
- `auth_handler.py` - Password hashing and verification (PBKDF2)
- `config_management.py` - Configuration file I/O
- `db_handler.py` - **Core data access layer** (all database operations)

**BTExtrasViewer modules** (`src/BTExtrasViewer/`):
- `btextrasviewer_main.py` - Main application class (4500+ lines, handles UI, state, filters, navigation)
- `ui_dialogs.py` - All dialog windows (account manager, user manager, role manager, login, etc.)
- `ui_reports.py` - Report dialogs (cash flow, balance evolution, transaction analysis)
- `ui_help.py` - Help dialog system
- `ui_utils.py` - UI utility functions
- `file_processing.py` - MT940 import/export logic, Excel/PDF generation
- `email_handler.py` - SMTP email sending
- `email_composer.py` - Email composition dialog

**BTExtrasChat modules** (`src/BTExtrasChat/`):
- `chat_main.py` - Chat entry point
- `chat_ui.py` - Chat UI implementation (2000+ lines)

## Important Implementation Details

### MT940 File Import

The `file_processing.py` module handles bank statement imports:
- Extracts IBAN from `:25:` field using regex
- Auto-detects account or prompts for selection
- Prevents duplicate imports by checking existing transactions
- Supports batch import with progress tracking
- Parses transaction metadata: CIF, Factura, Beneficiar, TID, RRN, PAN

### User Settings Persistence

Settings are stored as JSON in `utilizatori.setari_ui`:
- Window geometry and state (normal/zoomed)
- Active account ID
- Filter states (date range mode, type filter, search terms)
- Column widths for TreeView
- SMTP configuration
- Navigation state (selected year/month/day)

Saved via `save_app_config()` in `config_management.py`, which calls `db_handler.save_user_settings()`.

### Authentication Flow

1. Application starts, reads DB credentials from local `config.ini` (located in `%LOCALAPPDATA%\BTExtrasViewer\` on Windows)
2. If database connection fails or config doesn't exist, shows database configuration dialog
3. Shows `LoginDialog` (from `ui_dialogs.py`)
4. On first run, auto-creates admin user (username: `admin`, password: `admin123`)
5. `auth_handler.verifica_parola()` validates password using stored salt and hash (PBKDF2 with 100,000 iterations)
6. `db_handler.get_user_with_full_context()` loads user data with roles, permissions, and allowed accounts
7. Session Manager is notified of authenticated user via socket on port 12343

### Password Reset Flow (v4.7.3+)

The application supports password reset functionality:
- Reset tokens are stored in `parola_reset_tokens` table with expiration timestamps
- Tokens are generated using secure random methods
- Users can request password reset through the login dialog
- Reset process includes token validation and expiration checks

### Default Admin User

On first database initialization, if no users exist:
- Username: `admin`
- Password: `admin123` (MUST be changed on first login via `parola_schimbata_necesar` flag)
- Role: Administrator (created with `all_permissions` flag)

### Preventing Multiple Instances

Each application binds to a "lock port" on startup:
- Session Manager: 54321
- Viewer: 54322
- Chat: 54323

If port is already in use, the application refuses to start (preventing duplicate instances).

### Auto-Start Configuration

When installed via the Inno Setup installer, Session Manager is configured to auto-start with Windows:
- Registry key: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Value name: `BTExtras Suite`
- This ensures the system tray icon and IPC infrastructure are always available

## Common Development Tasks

### Adding New Database Tables

1. Add `CREATE TABLE` SQL in `common/db_handler.py` (follow naming pattern `DB_STRUCTURE_*`)
2. Add table name to `DatabaseHandler.create_tables_if_not_exist()` method
3. Add CRUD methods to `DatabaseHandler` class

### Adding New UI Permissions

1. Insert permission key into `roluri_permisiuni` table for appropriate roles
2. Check permission in UI code using `self.current_user.has_permission('your_permission_key')`
3. Conditionally enable/disable menu items or buttons

### Adding New Report Types

1. Create report dialog class in `ui_reports.py` (inherit from `tk.Toplevel`)
2. Use `matplotlib` for charts or `reportlab` for PDF generation
3. Add menu item in `btextrasviewer_main.py` with permission check
4. Use `threaded_export_worker` for async PDF/Excel generation

### Working with Filters

The main application (`btextrasviewer_main.py`) maintains filter state:
- `date_range_mode_var` - Boolean for date range vs. hierarchical navigation
- `type_var` - Transaction type filter ('toate', 'credit', 'debit')
- `search_var` - Search term
- `search_column_var` - Column to search in
- Navigation state: `nav_selected_year`, `nav_selected_month_index`, `nav_selected_day`

Filters are applied in `_generate_where_clause()` method and affect all SQL queries for transactions.

## Testing Notes

- Tests are in `tests/` directory
- Tests must add `src/` to `sys.path` to import modules: `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))`
- Current tests cover `auth_handler.py` password hashing
- Use pytest for test execution

## Localization

The application is in Romanian:
- UI labels, messages, and dialogs are in Romanian
- Uses Romanian locale for date/month formatting (see `app_constants.py`)
- Month names are dynamically generated based on system locale

## Key Files to Review

- `src/common/db_handler.py` - All database operations, schema definitions
- `src/BTExtrasViewer/btextrasviewer_main.py` - Main UI application logic
- `src/session_manager.py` - Multi-application orchestration
- `src/common/config_management.py` - Settings persistence strategy
- `src/BTExtrasViewer/file_processing.py` - MT940 import/export logic
- `README.md` - Detailed feature list and setup instructions (in Romanian)
