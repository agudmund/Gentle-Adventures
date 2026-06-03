' Gentle Adventures - headless launcher (no console window).
'
' GA isn't broken, so it doesn't need an engine-hood console open on the desktop.
' Runs the app through the windowed Python launcher (pyw) so nothing clutters the
' screen; all logs go to the family Rust logger's files. Double-click to play.
'
' It also carries the ledger creds (and family keys) from the User environment
' scope into this process, so GA's live Sheet connection works even when the
' launching desktop session's environment is stale (e.g. the vars were set after
' the session started). Without this, GA silently falls back to the bundled quest
' (LEDGER OFF) and the realtime Sheet loop never runs.
'
' Portable: pyw resolves the default Python from PATH; the working directory is
' pinned to this script's folder so "main.py" is found wherever the repo lives.
' The app's own relaunch-on-close inherits pythonw via sys.executable, so
' vaporise -> reopen stays headless and credentialled too.

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set userEnv = sh.Environment("USER")
Set procEnv = sh.Environment("PROCESS")

Dim k
For Each k In Array("GA_WebApp", "GA_Ledger", _
                    "SingleSharedBraincell_ApiKey", "SingleSharedBraincell_SettingsFile", _
                    "SingleSharedBraincell_AssetVault", "SingleSharedBraincell_ChatHistory", _
                    "GEMINI_API_KEY")
    If userEnv.Item(k) <> "" Then procEnv.Item(k) = userEnv.Item(k)
Next

sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "pyw " & Chr(34) & "main.py" & Chr(34), 0, False
