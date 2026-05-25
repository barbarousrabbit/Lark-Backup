Set fso = CreateObject("Scripting.FileSystemObject")
exePath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "LarkBackup.exe")
CreateObject("WScript.Shell").Run """" & exePath & """ --install", 0, True
