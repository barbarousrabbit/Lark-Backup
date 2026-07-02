Set fso = CreateObject("Scripting.FileSystemObject")
exePath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "LarkBackup.exe")
If Not fso.FileExists(exePath) Then
    MsgBox "LarkBackup.exe was not found next to this script." & vbCrLf & _
           "Please extract the full LarkBackup.zip to a folder first, then run this script again.", _
           vbExclamation, "Lark Backup"
    WScript.Quit 1
End If
CreateObject("WScript.Shell").Run """" & exePath & """ --install", 0, True
