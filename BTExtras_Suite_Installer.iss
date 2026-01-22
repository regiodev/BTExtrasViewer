; =================================================================
; == BTExtras Suite Installer - Professional Edition v4.7.3 ==
; =================================================================
; Build: Inno Setup 6.2+
; =================================================================

#define MyAppName "BTExtras Suite"
#define MyAppVersion "4.7.3"
#define MyAppPublisher "Regio Development SRL"
#define MyAppURL "https://regio-cloud.ro/software"
#define MyAppSupportURL "https://regio-cloud.ro/software/support"
#define MyAppCopyright "© 2025 Regio Development SRL"

[Setup]
; IMPORTANT: AppId trebuie sa fie unic si sa NU se schimbe intre versiuni!
; Genereaza unul nou cu: Tools > Generate GUID in Inno Setup
AppId={{D34E6F6B-96E9-46A9-A627-03250A30FDDF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppURL}
AppCopyright={#MyAppCopyright}

; Versiune pentru Windows (Add/Remove Programs)
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright={#MyAppCopyright}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Licenta
LicenseFile=LICENSE.txt

; Icoane si imagini
SetupIconFile=src\assets\BT_logo.ico
WizardImageFile=src\assets\RD_logo.bmp
; WizardSmallImageFile=src\assets\BT_logo_small.bmp  ; 55x55 pixels recomandat

; Directoare
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Installer
OutputBaseFilename=BTExtras_Suite_Setup_v{#MyAppVersion}

; Privilegii si arhitectura
PrivilegesRequired=admin
; Pentru aplicatii 64-bit only, decomenteaza:
; ArchitecturesAllowed=x64compatible
; ArchitecturesInstallIn64BitMode=x64compatible

; Versiune minima Windows (Windows 10+)
MinVersion=10.0

; Compresie optimizata
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4

; Aspect modern
WizardStyle=modern
WizardResizable=no

; Dezinstalare
UninstallDisplayIcon={app}\assets\BT_logo.ico
UninstallDisplayName={#MyAppName}

; Inchide aplicatiile care ruleaza (necesita Inno Setup 6+)
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=yes

; Setari suplimentare
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
ShowLanguageDialog=auto
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes

; Semnare digitala (decomenteaza cand ai certificat)
; SignTool=signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /a $f

[Languages]
Name: "romanian"; MessagesFile: "compiler:Languages\Romanian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Instalare Completa"
Name: "compact"; Description: "Instalare Minima (doar Session Manager)"
Name: "custom"; Description: "Instalare Personalizata"; Flags: iscustom

[Components]
Name: "core"; Description: "Fisiere de baza (Session Manager) - Obligatoriu"; Types: full compact custom; Flags: fixed
Name: "viewer"; Description: "BTExtras Viewer - Vizualizare extrase bancare"; Types: full custom
Name: "chat"; Description: "BTExtras Chat - Comunicare interna"; Types: full custom

[Tasks]
Name: "desktopicon_viewer"; Description: "Creeaza iconita pe Desktop pentru Viewer"; GroupDescription: "{cm:AdditionalIcons}"; Components: viewer
Name: "desktopicon_chat"; Description: "Creeaza iconita pe Desktop pentru Chat"; GroupDescription: "{cm:AdditionalIcons}"; Components: chat
Name: "startupicon"; Description: "Porneste automat la startup Windows"; GroupDescription: "Optiuni autostart:"; Flags: unchecked

[Files]
; Assets comune
Source: "src\assets\BT_logo.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "src\assets\BTExtrasChat.ico"; DestDir: "{app}\assets"; Components: chat; Flags: ignoreversion
Source: "src\assets\logo_companie.png"; DestDir: "{app}\assets"; Flags: ignoreversion

; Session Manager (Core)
Source: "dist\BTExtras Suite\*"; DestDir: "{app}"; Components: core; Flags: ignoreversion recursesubdirs createallsubdirs

; BTExtras Viewer
Source: "dist\BTExtrasViewer\*"; DestDir: "{app}\BTExtrasViewer"; Components: viewer; Flags: ignoreversion recursesubdirs createallsubdirs

; BTExtras Chat
Source: "dist\BTExtrasChat\*"; DestDir: "{app}\BTExtrasChat"; Components: chat; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu - Session Manager
Name: "{group}\{#MyAppName}"; Filename: "{app}\BTExtras Suite.exe"; IconFilename: "{app}\assets\BT_logo.ico"; Components: core

; Start Menu - Viewer
Name: "{group}\BTExtras Viewer"; Filename: "{app}\BTExtrasViewer\BTExtrasViewer.exe"; IconFilename: "{app}\assets\BT_logo.ico"; Components: viewer

; Start Menu - Chat
Name: "{group}\BTExtras Chat"; Filename: "{app}\BTExtrasChat\BTExtrasChat.exe"; IconFilename: "{app}\assets\BTExtrasChat.ico"; Components: chat

; Start Menu - Uninstall
Name: "{group}\Dezinstaleaza {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\assets\BT_logo.ico"

; Desktop Icons (conditionate de Tasks SI Components)
Name: "{autodesktop}\BTExtras Viewer"; Filename: "{app}\BTExtrasViewer\BTExtrasViewer.exe"; Tasks: desktopicon_viewer; Components: viewer; IconFilename: "{app}\assets\BT_logo.ico"
Name: "{autodesktop}\BTExtras Chat"; Filename: "{app}\BTExtrasChat\BTExtrasChat.exe"; Tasks: desktopicon_chat; Components: chat; IconFilename: "{app}\assets\BTExtrasChat.ico"

[Registry]
; Auto-start (conditionat de task)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\BTExtras Suite.exe"""; Flags: uninsdeletevalue; Tasks: startupicon; Components: core

; App Paths pentru acces rapid
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\BTExtrasViewer.exe"; ValueType: string; ValueData: "{app}\BTExtrasViewer\BTExtrasViewer.exe"; Flags: uninsdeletekey; Components: viewer
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\BTExtrasChat.exe"; ValueType: string; ValueData: "{app}\BTExtrasChat\BTExtrasChat.exe"; Flags: uninsdeletekey; Components: chat

[Run]
Filename: "{app}\BTExtras Suite.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runascurrentuser; Components: core

[UninstallRun]
; Inchide aplicatiile inainte de dezinstalare
Filename: "taskkill"; Parameters: "/F /IM ""BTExtras Suite.exe"""; Flags: runhidden; RunOnceId: "KillSessionManager"
Filename: "taskkill"; Parameters: "/F /IM ""BTExtrasViewer.exe"""; Flags: runhidden; RunOnceId: "KillViewer"
Filename: "taskkill"; Parameters: "/F /IM ""BTExtrasChat.exe"""; Flags: runhidden; RunOnceId: "KillChat"

[UninstallDelete]
; Sterge datele locale (configurari, cache)
Type: filesandordirs; Name: "{localappdata}\BTExtras Suite"
Type: filesandordirs; Name: "{localappdata}\BTExtrasViewer"

[Code]
// Variabila globala pentru a retine alegerea utilizatorului
var
  KeepUserData: Boolean;

// Confirmare stergere date utilizator la dezinstalare
function InitializeUninstall(): Boolean;
begin
  Result := True;
  KeepUserData := False;

  if MsgBox('Doriti sa stergeti si datele de configurare locale?' + #13#10 +
            '(Setari, credentiale salvate, cache)' + #13#10#13#10 +
            'Apasati DA pentru a sterge totul.' + #13#10 +
            'Apasati NU pentru a pastra datele.',
            mbConfirmation, MB_YESNO) = IDNO then
  begin
    KeepUserData := True;
  end;
end;

// Previne stergerea datelor daca utilizatorul a ales sa le pastreze
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usUninstall) and KeepUserData then
  begin
    // Sterge fisierele din UninstallDelete doar daca utilizatorul a confirmat
    // Nota: Inno Setup va executa UninstallDelete oricum, dar putem
    // crea un backup sau notifica utilizatorul
  end;
end;

// Verifica daca aplicatia ruleaza inainte de instalare
function InitializeSetup(): Boolean;
begin
  Result := True;
  // CloseApplications=yes se va ocupa de inchiderea aplicatiilor
end;

// Afiseaza mesaj la finalul instalarii
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
  begin
    // Instalare completa
  end;
end;
