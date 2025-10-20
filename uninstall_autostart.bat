@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   飞书备份程序 - 自启动卸载工具
echo ========================================
echo.

echo [1/3] 检查当前自启动状态...
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" >nul 2>&1
if %errorlevel% equ 0 (
    echo     ℹ 发现自启动项，准备移除
    echo.
    echo [2/3] 正在从开机自启动中移除...
    reg delete "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" /f 2>nul
    
    if %errorlevel% equ 0 (
        echo     ✓ 成功从开机自启动中移除
        echo.
        echo 验证移除结果...
        reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "LarkBackup" >nul 2>&1
        if %errorlevel% equ 0 (
            echo     ⚠ 注册表项仍然存在，可能需要管理员权限
        ) else (
            echo     ✓ 注册表项已成功移除
        )
    ) else (
        echo     ✗ 移除失败，错误代码: %errorlevel%
    )
) else (
    echo     ℹ 未在开机自启动中找到程序项（已经移除或从未添加）
)

echo.
echo [3/3] 正在结束运行中的程序...
tasklist | find /i "LarkBackup.exe" >nul 2>&1
if %errorlevel% equ 0 (
    taskkill /f /im "LarkBackup.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo     ✓ 成功结束运行中的程序
    ) else (
        echo     ⚠ 程序结束失败，请手动关闭
    )
) else (
    echo     ℹ 程序当前未在运行
)

echo.
echo ========================================
echo 卸载完成！
echo.
echo 程序已从开机自启动中移除
echo 如需重新安装自启动，请运行: install_autostart.bat
echo ========================================
echo.
pause
