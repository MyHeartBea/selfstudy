' Kaoyan mistakes launcher - starts backend + frontend fully hidden.
' Uses shell.Run window mode 0 (hidden) - no console windows appear.
' Each service cmd hides itself via start /b.
' Logs progress to D:\temp\km-launch.log for debugging.
' NOTE: pure ASCII - VBS parses in the system codepage.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
km = "C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km"
logFile = "D:\temp\km-launch.log"

Function Log(msg)
    Dim f
    Set f = fso.OpenTextFile(logFile, 8, True)
    f.WriteLine Now() & " " & msg
    f.Close
End Function

Function PortListening(port)
    Dim p, output
    Set p = shell.Exec("powershell -NoProfile -Command ""$c = Get-NetTCPConnection -LocalPort " & port & " -State Listen -ErrorAction SilentlyContinue; if ($c) { '1' } else { '0' }""")
    output = LCase(p.StdOut.ReadAll())
    If InStr(output, "1") > 0 Then
        PortListening = True
    Else
        PortListening = False
    End If
End Function

Log "launcher started"

If Not PortListening(8000) Then
    shell.Run "cmd /c """ & km & "\start_backend_hidden.cmd""", 0, False
    Log "backend launch issued"
End If

If Not PortListening(5173) Then
    shell.Run "cmd /c """ & km & "\start_frontend_hidden.cmd""", 0, False
    Log "frontend launch issued"
End If

WScript.Sleep 12000
Log "done, opening browser"
shell.Run "http://localhost:5173", 1, False
