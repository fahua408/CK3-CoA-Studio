; Inno Setup Script for CK3 CoA Studio (used when ISCC.exe is installed / in GitHub Actions)
#define MyAppName "CK3 CoA Studio"
#define MyAppNameCN "十字军之王3纹章生成工坊"
#define MyAppVersion "1.0.0"
#define MyAppExeName "CK3-CoA-Studio.exe"

[Setup]
AppId={{8E74A2C1-5F3B-4D19-9A0B-3B7D52C4E102}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=CK3 CoA Studio
DefaultDirName={localappdata}\Programs\CK3-CoA-Studio
DefaultGroupName={#MyAppNameCN}
AllowNoIcons=yes
OutputDir=..\release
OutputBaseFilename=CK3-CoA-Studio-Setup-v{#MyAppVersion}-inno
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\CK3-CoA-Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppNameCN}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppNameCN}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameCN}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppNameCN, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
