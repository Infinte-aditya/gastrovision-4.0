; Inno Setup 6 script - open in Inno Setup and press Compile (after packaging\build_windows.bat).
#define AppVer "4.0.0"
[Setup]
AppId={{4B2A5C4B-63C0-4A37-BED1-1A68F2726F46}
AppName=GastroVision
AppVersion={#AppVer}
AppPublisher=Aditya Verma, Aaditya Raj and Gyanam Shah
AppPublisherURL=https://infinte-aditya.github.io/gastrovision-4.0/
DefaultDirName={localappdata}\Programs\GastroVision
DefaultGroupName=GastroVision
PrivilegesRequired=lowest
InfoBeforeFile=disclaimer.txt
OutputDir=..\release
OutputBaseFilename=GastroVision-Setup-{#AppVer}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\GastroVision.exe
UninstallDisplayName=GastroVision {#AppVer}
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\GastroVision\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\packaging\ffmpeg\LICENSE*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
[Icons]
Name: "{group}\GastroVision"; Filename: "{app}\GastroVision.exe"
Name: "{userdesktop}\GastroVision"; Filename: "{app}\GastroVision.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\GastroVision.exe"; Description: "Start GastroVision"; Flags: nowait postinstall skipifsilent
