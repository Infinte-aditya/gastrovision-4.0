; Inno Setup 6 script - open in Inno Setup and press Compile (after packaging\build_windows.bat).
#define AppVer "4.0.0"
[Setup]
AppName=GastroVision
AppVersion={#AppVer}
AppPublisher=Aditya Verma
DefaultDirName={localappdata}\Programs\GastroVision
DefaultGroupName=GastroVision
PrivilegesRequired=lowest
InfoBeforeFile=disclaimer.txt
OutputDir=..\release
OutputBaseFilename=GastroVision-Setup-{#AppVer}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=GastroVision {#AppVer}
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\GastroVision\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\GastroVision"; Filename: "{app}\GastroVision.exe"
Name: "{userdesktop}\GastroVision"; Filename: "{app}\GastroVision.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\GastroVision.exe"; Description: "Start GastroVision"; Flags: nowait postinstall skipifsilent
