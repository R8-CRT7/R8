; Inno Setup script -> 360SmartSetup.exe
; Build (after PyInstaller):  iscc packaging\installer.iss
#define AppName "360 SMART"
#define AppVersion "0.5.0-alpha.3"
#define AppExe "360Smart.exe"

[Setup]
AppId={{9C1D6B3E-3F0B-4B8E-9D55-360A15A7E001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=360 SMART
DefaultDirName={autopf}\360 SMART
DefaultGroupName=360 SMART
DisableProgramGroupPage=yes
; per-user install by default (no admin needed); admins may choose all users
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=360SmartSetup
SetupIconFile=..\smart360\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\360Smart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\360 SMART"; Filename: "{app}\{#AppExe}"
Name: "{group}\360 SMART (Demo)"; Filename: "{app}\{#AppExe}"; Parameters: "--demo"
Name: "{group}\360 SMART - Diagnose erstellen"; Filename: "{app}\{#AppExe}"; Parameters: "--diagnose"
Name: "{group}\{cm:UninstallProgram,360 SMART}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\360 SMART"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,360 SMART}"; Flags: nowait postinstall skipifsilent

; User data (%APPDATA%\360Smart: settings, history, cache) and the API key in the Windows
; Credential Manager are intentionally kept on uninstall so a reinstall keeps your setup.
