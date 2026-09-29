' Mandi-API auto-start (called from the Windows Startup folder once per logon).
' Portable: derives the .bat path from this file's own location,
' so the whole project folder can be moved anywhere.
Set sh = CreateObject("WScript.Shell")
batPath = Replace(WScript.ScriptFullName, ".vbs", ".bat")
' Run hidden (console-less) so no window flashes on each logon.
sh.Run """" & batPath & """", 0, False