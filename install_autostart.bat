@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   飞书备份程序 - 自启动安装工具
echo ========================================
echo.

REM 获取当前exe文件的完整路径
set "EXE_PATH=%~dp0LarkBackup.exe"

REM 检查exe文件是否存在
if not exist "%EXE_PATH%" (
    echo [错误] 找不到 LarkBackup.exe 文件
    echo 请确保此脚本与 LarkBackup.exe 在同一目录下
    echo.
    pause
    exit /b 1
)

echo 当前程序路径: %EXE_PATH%
echo.

REM 添加到开机自启动
echo [1/3] 正在添加到开机自启动...
echo 注册表路径: HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
echo 程序名称: LarkBackup
echo 程序路径: "%EXE_PATH%"
echo.

reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" /t REG_SZ /d "\"%EXE_PATH%\"" /f

if %errorlevel% equ 0 (
    echo     ✓ 成功添加到开机自启动
    echo.
    echo [2/3] 验证注册表项是否正确添加...
    reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup"
    if %errorlevel% equ 0 (
        echo     ✓ 注册表项验证成功
    ) else (
        echo     ⚠ 注册表项验证失败，但添加操作报告成功
    )
) else (
    echo     ✗ 添加开机自启动失败，错误代码: %errorlevel%
    echo     可能的原因：
    echo     - 权限不足（尝试以管理员身份运行）
    echo     - 注册表访问被阻止
    echo     - 系统安全软件拦截
    echo.
    pause
    exit /b 1
)

echo.
echo [3/3] 启动程序进行首次运行...
start "" "%EXE_PATH%"

if %errorlevel% equ 0 (
    echo     ✓ 程序启动命令执行成功
    echo.
    echo 等待3秒检查程序是否正常运行...
    timeout /t 3 /nobreak >nul
    
    REM 检查程序是否在运行
    tasklist | find /i "LarkBackup.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo     ✓ 程序正在运行中
    ) else (
        echo     ⚠ 程序可能启动失败或立即退出
        echo     建议手动运行程序检查是否有错误
    )
) else (
    echo     ✗ 程序启动失败，错误代码: %errorlevel%
)

echo.
echo ========================================
echo 安装完成！
echo.
echo 程序已添加到开机自启动，将在系统启动时自动运行
echo 程序已在后台运行，每天早上9点自动备份数据
echo.
echo 如需卸载自启动，请运行: uninstall_autostart.bat
echo ========================================
echo.
pause
