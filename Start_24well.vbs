Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run Chr(34) & folder & "\run_local.bat" & Chr(34), 1, False
WScript.Sleep 2000
shell.Run "http://127.0.0.1:8002", 1, False
