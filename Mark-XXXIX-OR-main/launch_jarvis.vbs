Dim oShell, scriptDir, cmd
Set oShell = CreateObject("WScript.Shell")

' Get the folder this VBS lives in (no trailing backslash issues)
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1)

cmd = """C:\Users\user\AppData\Local\Programs\Python\Python312\pythonw.exe"" """ & _
      """" & scriptDir & "\main.py"""

oShell.CurrentDirectory = scriptDir
oShell.Run cmd, 0, False
