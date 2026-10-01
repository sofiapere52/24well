Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run Chr(34) & folder & "\run_local.bat" & Chr(34), 1, False
