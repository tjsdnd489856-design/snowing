$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Home\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\LensManager.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\run_gui.bat"
$Shortcut.WorkingDirectory = "$PSScriptRoot"
$Shortcut.IconLocation = "$PSScriptRoot\icon.png"
$Shortcut.WindowStyle = 7 # Minimized
$Shortcut.Save()
Write-Host "시작 프로그램에 등록되었습니다!"
