; Mağazalar Arası Transfer — kurulum betiği (Inno Setup 6)
; Derleme: installer\build.ps1

#define AppName "Mağazalar Arası Transfer"
#define AppExe "MagazaTransfer.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define Root ".."

[Setup]
AppId={{9E3C1B52-7D4A-4E0B-8F61-2C5A9D7E3B14}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Mağazalar Arası Transfer
DefaultDirName={localappdata}\Programs\MagazaTransfer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Yönetici yetkisi istemeden kullanıcının kendi klasörüne kurar (config.json program klasöründe yazılabilir kalır).
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=MagazaTransfer_Setup_{#AppVersion}
SetupIconFile={#Root}\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Kısayollar:"

[Files]
Source: "{#Root}\build\dist\MagazaTransfer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\KULLANIM.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Programı başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\config.json"
