@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   Lark Backup - Autostart Status Check
echo ========================================
echo.

echo [Check] Querying autostart registry entry...
echo.

REM Query registry key
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" 2>nul

if %errorlevel% equ 0 (
    echo [+] Program is registered for autostart
    echo.
    echo [Details]
    for /f "tokens=3*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" ^| find "LarkBackup"') do (
        echo Startup path: %%a %%b
        set "START_PATH=%%a %%b"
    )

    REM Strip quotes and check whether the file exists
    set START_PATH=%START_PATH:"=%
    if exist "%START_PATH%" (
        echo [+] Startup file exists
    ) else (
        echo [x] Startup file not found - program may fail to launch
        echo   Path: %START_PATH%
    )
) else (
    echo [x] Program is NOT registered for autostart
    echo.
    echo To enable autostart, run: install_autostart.bat
)

echo.
echo [Process Check] Checking whether the program is currently running...
tasklist | find /i "LarkBackup.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo [+] Program is currently running

    REM Show process details
    echo.
    echo [Process Details]
    tasklist | find /i "LarkBackup.exe"
) else (
    echo [x] Program is not currently running
)

echo.
echo [Windows Startup Check] Querying via system tool...
REM Attempt to query startup items using wmic
wmic startup where "name='LarkBackup'" get name,command 2>nul | find /i "LarkBackup" >nul
if %errorlevel% equ 0 (
    echo [+] Program found in Windows startup items
    wmic startup where "name='LarkBackup'" get name,command
) else (
    echo [i] Program not found in Windows startup items (this is normal - it uses the registry method)
)

echo.
echo ========================================
echo Check complete!
echo.
echo If issues are found:
echo - Reinstall autostart: install_autostart.bat
echo - Remove autostart:    uninstall_autostart.bat
echo - Run program manually: LarkBackup.exe
echo ========================================
echo.
pause
