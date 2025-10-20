@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   飞书备份程序 - 自启动状态检查
echo ========================================
echo.

echo [检查] 正在查询开机自启动状态...
echo.

REM 查询注册表项
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" 2>nul

if %errorlevel% equ 0 (
    echo ✓ 程序已添加到开机自启动
    echo.
    echo [详细信息]
    for /f "tokens=3*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" ^| find "LarkBackup"') do (
        echo 启动路径: %%a %%b
        set "START_PATH=%%a %%b"
    )
    
    REM 移除引号并检查文件是否存在
    set START_PATH=%START_PATH:"=%
    if exist "%START_PATH%" (
        echo ✓ 启动文件存在
    ) else (
        echo ✗ 启动文件不存在，可能导致启动失败
        echo   路径: %START_PATH%
    )
) else (
    echo ✗ 程序未添加到开机自启动
    echo.
    echo 如需添加自启动，请运行: install_autostart.bat
)

echo.
echo [进程检查] 正在检查程序是否运行中...
tasklist | find /i "LarkBackup.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ 程序正在运行中
    
    REM 显示进程详细信息
    echo.
    echo [进程详情]
    tasklist | find /i "LarkBackup.exe"
) else (
    echo ✗ 程序当前未运行
)

echo.
echo [Windows启动项检查] 使用系统工具查询...
REM 尝试使用wmic查询启动项
wmic startup where "name='LarkBackup'" get name,command 2>nul | find /i "LarkBackup" >nul
if %errorlevel% equ 0 (
    echo ✓ 在Windows启动项中发现程序
    wmic startup where "name='LarkBackup'" get name,command
) else (
    echo ℹ Windows启动项中未找到程序（这是正常的，因为程序使用注册表方式）
)

echo.
echo ========================================
echo 检查完成！
echo.
echo 如果发现问题：
echo - 重新安装自启动: install_autostart.bat
echo - 卸载自启动: uninstall_autostart.bat  
echo - 手动运行程序: LarkBackup.exe
echo ========================================
echo.
pause