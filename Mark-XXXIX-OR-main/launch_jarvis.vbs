Set objShell = CreateObject("WScript.Shell")
strPython = "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
strScript = Chr(34) & "C:\Users\user\Downloads\Mark-XXXIX-OR-main (1)\Mark-XXXIX-OR-main\main.py" & Chr(34)
strDir    = "C:\Users\user\Downloads\Mark-XXXIX-OR-main (1)\Mark-XXXIX-OR-main"

' Set working directory first
objShell.CurrentDirectory = strDir

' Run python.exe directly with WindowStyle=1 (normal — lets Qt window appear)
' The console window is hidden by passing CREATE_NO_WINDOW via PowerShell
strPS = "powershell.exe -WindowStyle Hidden -Command " & Chr(34) & _
        "Start-Process -FilePath '" & strPython & "' " & _
        "-ArgumentList " & Chr(34) & Chr(34) & strScript & Chr(34) & Chr(34) & " " & _
        "-WorkingDirectory '" & strDir & "' " & _
        "-WindowStyle Normal -NoNewWindow" & Chr(34)

objShell.Run strPS, 0, False
