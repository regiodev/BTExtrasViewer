; =================================================================
; == Script Inno Setup Final (Versiune de Maximă Compatibilitate v2) ==
; =================================================================

[Setup]
AppName=BTExtras Suite
AppVersion=4.7.2
AppPublisher=Regio Development

; 1. Adaugă acordul de licență care trebuie acceptat
; Asigurați-vă că fișierul 'LICENSE.txt' se află în același folder cu scriptul .iss
LicenseFile=LICENSE.txt

; 2. Setează iconița pentru fișierul de instalare (setup.exe)
SetupIconFile=src\assets\BT_logo.ico

; 3. Setează imaginea care apare în partea stângă a ferestrelor de instalare
WizardImageFile=src\assets\RD_logo.bmp

; === SFÂRȘIT BLOC DE COD MODIFICAT ===

DefaultDirName={autopf}\BTExtras Suite
DefaultGroupName=BTExtras Suite
PrivilegesRequired=admin
OutputDir=Installer
OutputBaseFilename=BTExtras_Suite_Setup_v4.7.2
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\assets\BT_logo.ico

[Languages]
Name: "romanian"; MessagesFile: "compiler:Languages\Romanian.isl"

[Types]
; Definim un singur tip de instalare 'custom' pentru a forța afișarea listei de componente
Name: "custom"; Description: "Instalare Personalizată"; Flags: iscustom

[Components]
; Asociem toate componentele cu tipul 'custom'.
; 'core' este marcat ca 'fixed', deci nu va putea fi debifat.
Name: "core"; Description: "Fișiere de bază (Session Manager)"; Types: custom; Flags: fixed
Name: "viewer"; Description: "BTExtras Viewer"; Types: custom
Name: "chat"; Description: "BTExtras Chat"; Types: custom

[Tasks]
Name: "desktopicon_viewer"; Description: "Creează o iconiță pe Desktop pentru Viewer"; GroupDescription: "{cm:AdditionalIcons}"
Name: "desktopicon_chat"; Description: "Creează o iconiță pe Desktop pentru Chat"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "src\assets\BT_logo.ico"; DestDir: "{app}\assets"; Components: core or viewer
Source: "src\assets\BTExtrasChat.ico"; DestDir: "{app}\assets"; Components: chat
Source: "src\assets\logo_companie.png"; DestDir: "{app}\assets"; Components: core or viewer

Source: "dist\BTExtras Suite\*"; DestDir: "{app}"; Components: core; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\BTExtrasViewer\*"; DestDir: "{app}\BTExtrasViewer"; Components: viewer; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\BTExtrasChat\*"; DestDir: "{app}\BTExtrasChat"; Components: chat; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BTExtras Suite"; Filename: "{app}\BTExtras Suite.exe"; IconFilename: "{app}\assets\BT_logo.ico"; Components: core
Name: "{group}\BTExtras Viewer"; Filename: "{app}\BTExtrasViewer\BTExtrasViewer.exe"; IconFilename: "{app}\assets\BT_logo.ico"; Components: viewer
Name: "{group}\BTExtras Chat"; Filename: "{app}\BTExtrasChat\BTExtrasChat.exe"; IconFilename: "{app}\assets\BTExtrasChat.ico"; Components: chat
Name: "{group}\Dezinstalează BTExtras Suite"; Filename: "{uninstallexe}"; IconFilename: "{app}\assets\BT_logo.ico"

Name: "{autodesktop}\BTExtras Viewer"; Filename: "{app}\BTExtrasViewer\BTExtrasViewer.exe"; Tasks: desktopicon_viewer; Components: viewer; IconFilename: "{app}\assets\BT_logo.ico"
Name: "{autodesktop}\BTExtras Chat"; Filename: "{app}\BTExtrasChat\BTExtrasChat.exe"; Tasks: desktopicon_chat; Components: chat; IconFilename: "{app}\assets\BTExtrasChat.ico"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BTExtras Suite"; ValueData: """{app}\BTExtras Suite.exe"""; Flags: uninsdeletevalue; Components: core

[Run]
Filename: "{app}\BTExtras Suite.exe"; Description: "{cm:LaunchProgram,BTExtras Suite}"; Flags: nowait postinstall skipifsilent; Components: core

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\BTExtras Suite"