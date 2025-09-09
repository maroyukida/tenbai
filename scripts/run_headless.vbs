' Invisible launcher for headless scheduler
On Error Resume Next
Dim fso, sh, root, vbs
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

' Project root
root = "C:\Users\mouda\ytanalyzer_v3\ytanalyzer_v3"

sh.CurrentDirectory = root
cmd = Chr(34) & root & "\scripts\start_headless.cmd" & Chr(34)
'
' 0 = hidden window, do not wait
sh.Run cmd, 0, False
