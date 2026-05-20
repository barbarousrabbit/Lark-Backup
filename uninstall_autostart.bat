@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   Lark Backup - Autostart Uninstaller
echo ========================================
echo.

echo [1/3] Checking current autostart status...
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" >nul 2>&1
if %errorlevel% equ 0 (
    echo     [i] Autostart entry found - preparing to remove
    echo.
    echo [2/3] Removing from autostart...
    reg delete "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" /f 2>nul

    if %errorlevel% equ 0 (
        echo     [+] Successfully removed from autostart
        echo.
        echo Verifying removal...
        reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" >nul 2>&1
        if %errorlevel% equ 0 (
            echo     [!] Registry entry still exists - administrator privileges may be required
        ) else (
            echo     [+] Registry entry removed successfully
        )
    ) else (
        echo     [x] Removal failed, error code: %errorlevel%
    )
) else (
    echo     [i] No autostart entry found (already removed or never installed)
)

echo.
echo [3/3] Stopping any running instance of the program...
tasklist | find /i "LarkBackup.exe" >nul 2>&1
if %errorlevel% equ 0 (
    taskkill /f /im "LarkBackup.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo     [+] Program stopped successfully
    ) else (
        echo     [!] Failed to stop the program - please close it manually
    )
) else (
    echo     [i] Program is not currently running
)

echo.
echo ========================================
echo Uninstall complete!
echo.
echo Program has been removed from autostart.
echo To re-enable autostart, run: install_autostart.bat
echo ========================================
echo.
pause
