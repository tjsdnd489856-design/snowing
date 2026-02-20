$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = [System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "렌즈 관리 시스템.lnk")
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = [System.IO.Path]::Combine($PSScriptRoot, "run.bat")
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "콘택트렌즈 유통기한 관리 시스템"
# 윈도우 기본 아이콘 중 안경/돋보기 모양과 비슷한 것을 지정합니다.
$Shortcut.IconLocation = "shell32.dll, 22" 
$Shortcut.Save()

Write-Host "바탕화면에 '렌즈 관리 시스템' 아이콘이 생성되었습니다!" -ForegroundColor Green
