# Security Audit Report — BTExtras Suite v4.7.6

**Date:** 2026-02-21
**Scope:** Full source code review of all Python modules under `src/`
**Methodology:** Manual static analysis of authentication, authorization, data access, IPC, cryptography, input validation, and credential management

---

## Executive Summary

The BTExtras Suite has a solid foundation in several areas — parameterized SQL queries are used consistently, password hashing uses PBKDF2 with proper iteration count, and timing-safe comparison prevents timing attacks on password verification. However, the audit identified **22 findings** across 5 severity levels that should be addressed. The most critical issues involve plaintext credential storage, unauthenticated IPC channels, and missing brute-force protections.

| Severity | Count |
|----------|-------|
| CRITICAL | 4     |
| HIGH     | 7     |
| MEDIUM   | 7     |
| LOW      | 4     |

---

## Findings

### CRITICAL-01: Database credentials stored in plaintext on disk

**Files:** `src/common/config_management.py:40-61`
**OWASP:** A02:2021 — Cryptographic Failures

Database credentials (host, port, user, **password**) are written to `config.ini` in plaintext using `configparser`. Any local user or malware with file read access can extract full database credentials.

```python
config.set('Database', 'db_password', db_creds_to_save.get('password', ''))
with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
    config.write(configfile)
```

**Recommendation:**
- Encrypt the password at rest using OS-level credential storage (`keyring` library on Windows/macOS/Linux) or at minimum use DPAPI on Windows.
- Set restrictive file permissions on `config.ini` (e.g., `0o600`).
- Currently, no `os.chmod()` or `os.umask()` call is made after writing the file.

---

### CRITICAL-02: SMTP credentials stored and transmitted in plaintext

**Files:** `src/BTExtrasViewer/ui_dialogs.py:515,664-671,1405`, `src/common/db_handler.py` (setari_sistem table)
**OWASP:** A02:2021 — Cryptographic Failures

SMTP passwords are stored in the `setari_sistem` database table as plaintext and passed through dictionaries in memory without any encryption:

```python
# ui_dialogs.py:515
'password': self.password_entry.get()

# ui_dialogs.py:668
'password': system_smtp_config['smtp_parola'],  # plaintext from DB
```

**Recommendation:**
- Encrypt SMTP passwords before storing in the database (e.g., using `cryptography.fernet` with a key derived from a machine-specific secret).
- Clear password strings from memory after use where possible.

---

### CRITICAL-03: No brute-force protection on login

**Files:** `src/BTExtrasViewer/ui_dialogs.py` (LoginDialog class)
**OWASP:** A07:2021 — Identification and Authentication Failures

There is no account lockout, rate limiting, or progressive delay on failed login attempts. The help documentation at `help_content.py:204` states *"After 3 consecutive failed login attempts, the account may be temporarily locked"* — but **this feature is not implemented**. An attacker with network access to the database can attempt unlimited password guesses.

**Recommendation:**
- Track failed login attempts per user in the `utilizatori` table (e.g., `failed_login_count`, `locked_until` columns).
- Lock accounts after N consecutive failures (e.g., 5) for a configurable duration.
- Add progressive delay (exponential backoff) between failed attempts.
- Remove or correct the misleading help documentation.

---

### CRITICAL-04: Unauthenticated IPC sockets accept commands from any local process

**Files:** `src/session_manager.py:63-79`, `src/BTExtrasChat/chat_ui.py:85-116`, `src/BTExtrasViewer/btextrasviewer_main.py` (command listener)
**OWASP:** A01:2021 — Broken Access Control

All three applications listen on fixed TCP ports (`12343`, `12344`, `12345`) on `127.0.0.1` and accept commands without any authentication:

```python
# session_manager.py:74-77
data_bytes = conn.recv(4096)
command, *payload = data_bytes.decode('utf-8').split(' ', 1)
if command == 'SET_USER' and payload:
    self.current_session_user = json.loads(payload[0])  # No auth!
```

The Session Manager's `SET_USER` command is particularly dangerous — any local process can set the "authenticated user" to arbitrary data, which is then passed to child applications via base64-encoded command-line arguments (also unauthenticated).

**Recommendation:**
- Use a shared secret (generated at Session Manager startup and passed to child processes via environment variable) to authenticate IPC messages.
- Consider switching to named pipes or Unix domain sockets with file permission-based access control.
- Validate received user data against the database before trusting it.

---

### HIGH-01: SQL injection in schema migration queries

**File:** `src/common/db_handler.py:471,484,490,497`
**OWASP:** A03:2021 — Injection

The database name from user-provided configuration is interpolated directly into SQL queries using f-strings:

```python
query_check_email_col = f"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = '{db_name}' AND TABLE_NAME = 'utilizatori' AND COLUMN_NAME = 'email'"
```

While `db_name` comes from the config dialog (not typical end-user input), a malicious database name like `'; DROP TABLE utilizatori; --` could execute arbitrary SQL.

**Recommendation:**
- Use parameterized queries: `WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s`.
- This is a straightforward fix on 4 lines.

---

### HIGH-02: SQLAlchemy connection URI constructed with unescaped credentials

**File:** `src/BTExtrasViewer/file_processing.py:231-234,336-339`
**OWASP:** A03:2021 — Injection

Database credentials are interpolated directly into the SQLAlchemy connection URI:

```python
db_uri = (
    f"mysql+pymysql://{db_creds['user']}:{db_creds['password']}"
    f"@{db_creds['host']}:{db_creds['port']}/{db_creds['database']}?charset=utf8mb4"
)
```

If the password contains special characters (`@`, `:`, `/`, `%`), the URI will be malformed or misinterpreted. More importantly, the password is exposed in the URI string in memory and could appear in tracebacks.

**Recommendation:**
- Use `urllib.parse.quote_plus()` to escape credentials, or pass credentials via `create_engine()` kwargs:
  ```python
  from sqlalchemy import create_engine
  engine = create_engine("mysql+pymysql://", connect_args={...})
  ```

---

### HIGH-03: Password reset token comparison is not timing-safe

**File:** `src/BTExtrasViewer/ui_dialogs.py:1541`
**OWASP:** A02:2021 — Cryptographic Failures

The password reset token hash is compared using Python's `!=` operator, which is vulnerable to timing attacks:

```python
if hash_to_check != token_data['token_hash']:
```

The application correctly uses `hmac.compare_digest()` for password verification in `auth_handler.py:54`, but this pattern is not applied to token verification.

**Recommendation:**
- Replace with `hmac.compare_digest(hash_to_check, token_data['token_hash'])`.

---

### HIGH-04: No password complexity policy

**Files:** `src/BTExtrasViewer/ui_dialogs.py` (user creation, password change, password reset)
**OWASP:** A07:2021 — Identification and Authentication Failures

There is no minimum password length, complexity requirement, or dictionary check. The only validation is that the field is non-empty (`ui_dialogs.py:855`). The default admin password is `admin123`.

**Recommendation:**
- Enforce minimum length (e.g., 8 characters).
- Require mixed character classes (uppercase, lowercase, digits).
- Reject common passwords from a blocklist.
- Apply these rules in both user creation and password change dialogs.

---

### HIGH-05: Chat user identity can be forged via command-line argument

**Files:** `src/BTExtrasChat/chat_main.py:21-31`, `src/session_manager.py:134-137`
**OWASP:** A01:2021 — Broken Access Control

User identity is passed to the Chat application as a base64-encoded JSON command-line argument. This data is accepted without database verification:

```python
user_data_json = base64.b64decode(args.user_data).decode('utf-8')
pre_authenticated_user = json.loads(user_data_json)
```

Any local user can craft a command-line invocation with an arbitrary user ID and username, gaining full chat access as that user.

**Recommendation:**
- After decoding, validate the user against the database (check user exists, is active, and credentials match).
- Alternatively, pass only a session token that the Chat app verifies against the database.

---

### HIGH-06: Default admin password logged to console

**File:** `src/common/db_handler.py:563`
**OWASP:** A09:2021 — Security Logging and Monitoring Failures

The default admin password is logged in a warning message:

```python
logging.warning(f"Utilizator 'admin' creat cu parola temporară: '{admin_pass}'")
```

Log files may be accessible to other users or persisted to log management systems.

**Recommendation:**
- Remove the password from the log message. Log only the username creation event.

---

### HIGH-07: Debug print statement exposes permission data

**File:** `src/BTExtrasViewer/ui_dialogs.py:725`
**OWASP:** A09:2021 — Security Logging and Monitoring Failures

A debug `print()` statement outputs all loaded permissions for authenticated users to stdout:

```python
print(f"DEBUG: Permisiuni încărcate pentru user ID {user_id}: {permissions}")
```

**Recommendation:**
- Remove this debug statement or gate it behind a `logging.debug()` call that is disabled in production.

---

### MEDIUM-01: User enumeration in password reset flow

**File:** `src/BTExtrasViewer/ui_dialogs.py:634-637,676`
**OWASP:** A07:2021 — Identification and Authentication Failures

The password reset flow reveals whether a username/email exists in the system:

```python
if not user_data:
    messagebox.showwarning("Utilizator Inexistent", "Niciun cont nu a fost găsit...", parent=self)
    return
```

And subsequently reveals the full email address:

```python
messagebox.showinfo("Verificați Emailul", f"Un cod de verificare a fost trimis la adresa {user_data['email']}.", parent=self)
```

**Recommendation:**
- Return a generic message regardless of whether the user exists: *"If an account with this identifier exists, a reset email has been sent."*
- Mask the email address (e.g., `u***@example.com`).

---

### MEDIUM-02: Password reset token hashed without salt (SHA-256)

**File:** `src/BTExtrasViewer/ui_dialogs.py:644-646`
**OWASP:** A02:2021 — Cryptographic Failures

Reset tokens are hashed with plain SHA-256, making them vulnerable to rainbow table lookups:

```python
token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
```

**Recommendation:**
- Use HMAC-SHA256 with a server-side secret key, or use the existing `auth_handler.hash_parola()` with PBKDF2.

---

### MEDIUM-03: No rate limiting on password reset requests

**File:** `src/BTExtrasViewer/ui_dialogs.py:617-688`
**OWASP:** A07:2021 — Identification and Authentication Failures

There is no limit on how many password reset requests can be sent. An attacker can flood a user's inbox with reset emails.

**Recommendation:**
- Limit reset requests to 1 per user per 15 minutes (matching the token expiration).
- Track the last request timestamp per user.

---

### MEDIUM-04: Exception details exposed in UI error dialogs

**File:** `src/BTExtrasViewer/ui_dialogs.py:741-743`
**OWASP:** A09:2021 — Security Logging and Monitoring Failures

Full exception type and message are displayed to the user in error dialogs:

```python
messagebox.showerror("Eroare Necunoscută la Autentificare",
    f"A apărut o problemă neașteptată:\n\n{type(e).__name__}: {e}", parent=self)
```

This may leak database structure, file paths, or connection details.

**Recommendation:**
- Show a generic error message to users. Log the full exception server-side.

---

### MEDIUM-05: No file permission restrictions on config.ini

**File:** `src/common/config_management.py:55-57`
**OWASP:** A01:2021 — Broken Access Control

The config file containing database credentials is created with default permissions (typically `0644` on Linux, world-readable). No `os.chmod()` is applied.

**Recommendation:**
- After writing, set permissions: `os.chmod(CONFIG_FILE, 0o600)`.

---

### MEDIUM-06: Temporary PDF files written to shared temp directory

**File:** `src/BTExtrasViewer/ui_reports.py:247,780,1376`
**OWASP:** A01:2021 — Broken Access Control

Report PDFs are written to the system temp directory with predictable names:

```python
temp_pdf_path = os.path.join(tempfile.gettempdir(), report_name)
```

Other local users can read these files or pre-create them to mount a symlink attack.

**Recommendation:**
- Use `tempfile.mkstemp()` or `tempfile.NamedTemporaryFile()` which create files with restrictive permissions and unpredictable names.

---

### MEDIUM-07: Default admin user created with `parola_schimbata_necesar = False`

**File:** `src/common/db_handler.py:553`
**OWASP:** A07:2021 — Identification and Authentication Failures

The seed admin user is created with the force-password-change flag set to `False`:

```python
cursor.execute(query_user, (admin_user, pass_hash, salt, 'Administrator Sistem', True, False))
```

This means the default `admin` / `admin123` credentials can be used indefinitely without the system prompting for a password change.

**Recommendation:**
- Set `parola_schimbata_necesar` to `True` for the seeded admin user.

---

### LOW-01: Chat messages not sanitized before display

**File:** `src/BTExtrasChat/chat_ui.py` (message display logic)
**OWASP:** A03:2021 — Injection

Messages are inserted directly into the Tkinter Text widget without sanitization. While Tkinter is not vulnerable to XSS like HTML, control characters or extremely long messages could degrade the UI experience.

**Recommendation:**
- Strip control characters from messages before display.
- Enforce a maximum message length at the database and UI level.

---

### LOW-02: No conversation membership check when loading chat history

**File:** `src/BTExtrasChat/chat_ui.py:598-615`
**OWASP:** A01:2021 — Broken Access Control

When loading conversation history, the query fetches all messages for a given `conversation_id` without verifying the current user is a participant. While the conversation list is properly filtered, the actual message fetch does not enforce membership.

**Recommendation:**
- Add a `WHERE` clause or pre-check that verifies `chat_participanti` membership for the current user before fetching messages.

---

### LOW-03: `os._exit(0)` used for shutdown bypasses cleanup

**File:** `src/session_manager.py:197`
**OWASP:** N/A — Reliability

`os._exit(0)` bypasses Python's cleanup handlers (atexit, finally blocks, destructors). While used intentionally to avoid pystray hanging, it could leave database connections open or temp files undeleted.

**Recommendation:**
- Ensure all critical cleanup (DB connections, temp files) happens before `os._exit()` is called.

---

### LOW-04: Admin user protected by hardcoded ID check (`user_id == 1`)

**Files:** `src/common/db_handler.py:842,859,957,1022`
**OWASP:** A04:2021 — Insecure Design

The admin user is protected by assuming it always has `id = 1`. If the database is restored or migrated with different auto-increment values, the protection fails:

```python
if user_id == 1:
    return False, "Utilizatorul administrator principal nu poate fi dezactivat."
```

**Recommendation:**
- Check for the `Administrator` role membership instead of hardcoding `id == 1`.

---

## Positive Findings (Things Done Well)

1. **Parameterized SQL queries** — The vast majority of SQL queries across `db_handler.py`, `file_processing.py`, `ui_dialogs.py`, and `ui_reports.py` use `%s` placeholders with proper parameter passing. This is effective SQL injection prevention.

2. **PBKDF2 password hashing** — `auth_handler.py` uses `hashlib.pbkdf2_hmac` with SHA-256, 390,000 iterations, and a 16-byte random salt. This meets current OWASP recommendations.

3. **Timing-safe password comparison** — `hmac.compare_digest()` is used for password hash comparison in `auth_handler.py:54`, preventing timing attacks.

4. **Separate salt storage** — Password salt and hash are stored in separate database columns, following best practices.

5. **Instance locking via ports** — Prevents multiple instances of the same application from running simultaneously.

6. **Audit logging** — The `jurnal_actiuni` table and `log_action()` method provide an audit trail for user actions.

7. **Row-level security** — The `utilizatori_conturi_permise` table and `tranzactie_acces` enum provide data-level access control for bank account visibility.

---

## Recommended Priority Order

| Priority | Finding | Effort |
|----------|---------|--------|
| 1 | CRITICAL-03: Add brute-force protection | Medium |
| 2 | CRITICAL-04: Authenticate IPC sockets | Medium |
| 3 | HIGH-01: Fix SQL injection in schema migration | Low |
| 4 | HIGH-03: Use timing-safe token comparison | Low |
| 5 | HIGH-04: Add password complexity policy | Low |
| 6 | MEDIUM-07: Fix admin seed flag | Low |
| 7 | HIGH-06 & HIGH-07: Remove sensitive data from logs | Low |
| 8 | CRITICAL-01: Encrypt DB credentials at rest | Medium |
| 9 | CRITICAL-02: Encrypt SMTP credentials | Medium |
| 10 | HIGH-02: Fix SQLAlchemy URI construction | Low |
| 11 | HIGH-05: Validate chat user identity | Medium |
| 12 | MEDIUM-01 to MEDIUM-06: Remaining medium items | Varies |
