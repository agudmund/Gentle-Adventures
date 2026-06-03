' Gentle Adventures - headless launcher (no console window).
'
' GA isn't broken, so it doesn't need an engine-hood console open on the desktop.
' This runs the app through the windowed Python launcher (pyw) so nothing clutters
' the screen; all logs go to the family Rust logger's files. Double-click to play.
'
' Portable: pyw resolves the default Python from PATH (no hardcoded per-user path),
' and the working directory is pinned to this script's folder so "main.py" is found
' wherever the repo lives. The app's own relaunch-on-close inherits pythonw via
' sys.executable, so vaporise -> reopen stays headless too.

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "pyw " & Chr(34) & "main.py" & Chr(34), 0, False
