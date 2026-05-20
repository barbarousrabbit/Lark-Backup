@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   Lark Backup - Autostart Installer
echo ========================================
echo.

REM Get the full path of the exe in the same directory as this script
set "EXE_PATH=%~dp0LarkBackup.exe"

REM Check whether the exe file exists
if not exist "%EXE_PATH%" (
    echo [Error] Cannot find LarkBackup.exe
    echo Please make sure this script and LarkBackup.exe are in the same directory.
    echo.
    pause
    exit /b 1
)

echo Current program path: %EXE_PATH%
echo.

REM Add to autostart registry key
echo [1/3] Adding to autostart...
echo Registry path: HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
echo Program name:  LarkBackup
echo Program path:  "%EXE_PATH%"
echo.

reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" /t REG_SZ /d "\"%EXE_PATH%\"" /f

if %errorlevel% equ 0 (
    echo     [+] Successfully added to autostart
    echo.
    echo [2/3] Verifying registry entry...
    reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup"
    if %errorlevel% equ 0 (
        echo     [+] Registry entry verified successfully
    ) else (
        echo     [!] Registry entry verification failed, but the add operation reported success
    )
) else (
    echo     [x] Failed to add autostart entry, error code: %errorlevel%
    echo     Possible causes:
    echo     - Insufficient permissions (try running as Administrator)
    echo     - Registry access blocked
    echo     - Blocked by security software
    echo.
    pause
    exit /b 1
)

echo.
echo [3/3] Launching program for first run...
start "" "%EXE_PATH%"

if %errorlevel% equ 0 (
    echo     [+] Program launch command executed successfully
    echo.
    echo Waiting 3 seconds to verify the program is running...
    timeout /t 3 /nobreak >nul

    REM Check whether the program is running
    tasklist | find /i "LarkBackup.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo     [+] Program is running
    ) else (
        echo     [!] Program may have failed to start or exited immediately
        echo     Recommend running the program manually to check for errors
    )
) else (
    echo     [x] Failed to launch program, error code: %errorlevel%
)

echo.
echo ========================================
echo Installation complete!
echo.
echo Program has been added to autostart and will run automatically on system startup.
echo Program is now running in the background and will back up data at the configured schedule time.
echo.
echo To remove autostart, run: uninstall_autostart.bat
echo ========================================
echo.
pause
