@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ==============================================
echo 正在启动 PostgreSQL、Redis、Weaviate 全套服务
echo ==============================================

:: 检查管理员权限，WinNAT 操作需要管理员
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未以管理员身份运行，尝试处理 WinNAT 端口冲突...
    echo         如遇 PostgreSQL Permission denied 错误，请右键以管理员运行此脚本。
    echo.
)

:: 检查 Docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker Desktop 未启动，请先打开 Docker 再运行此脚本！
    pause
    exit /b 1
)

:: 路径定义
set "PG_PATH=D:\app\PostgreSQL\16\bin"
set "PG_DATA=D:\app\PostgreSQL\16\data"

echo.
echo [0/4] 处理 WinNAT 端口占用（解决重启后 5432 Permission denied）...

:: 检查 5432 是否在 WinNAT 排除范围中
set NEED_WINNAT_FIX=0
for /f "tokens=1,2" %%a in ('netsh int ipv4 show excludedportrange tcp ^| findstr /r "[0-9]"') do (
    if %%a leq 5432 if %%b geq 5432 (
        set NEED_WINNAT_FIX=1
    )
)

if !NEED_WINNAT_FIX! equ 1 (
    echo       检测到 5432 端口被 WinNAT 占用，正在释放...
    net stop winnat /y >nul 2>&1
    if %errorlevel% neq 0 (
        echo       [警告] 无法停止 WinNAT（可能需要管理员权限），跳过此步骤...
    ) else (
        echo       WinNAT 已停止，5432 端口已释放
    )
    timeout /t 2 /nobreak >nul
) else (
    echo       5432 端口未被 WinNAT 占用，跳过
)

echo.
echo [1/4] 启动 PostgreSQL...

"%PG_PATH%\pg_ctl.exe" start -D "%PG_DATA%"
timeout /t 3 /nobreak >nul

"D:\app\PostgreSQL\16\bin\pg_ctl.exe" status -D "D:\app\PostgreSQL\16\data" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ##########################
    echo 严重错误：PostgreSQL 启动失败！
    echo 请查看日志目录：D:\app\PostgreSQL\16\data\log
    echo ##########################
    if !NEED_WINNAT_FIX! equ 1 (
        net start winnat >nul 2>&1
        echo WinNAT 已恢复
    )
    pause
    exit /b 1
)
echo PostgreSQL 启动成功！

:: 恢复 WinNAT（PostgreSQL 已抢占 5432，WinNAT 不会再占用它）
if !NEED_WINNAT_FIX! equ 1 (
    net start winnat >nul 2>&1
    if %errorlevel% equ 0 (
        echo WinNAT 已恢复，5432 端口安全
    ) else (
        echo [警告] WinNAT 恢复失败，Docker 网络可能受影响
    )
)

echo.
echo [2/4] 启动 Docker Redis-dev...
docker start redis-dev
timeout /t 2 /nobreak >nul

echo.
echo [3/4] 启动 Docker Weaviate-dev...
docker start weaviate-dev
timeout /t 2 /nobreak >nul

:: 验证服务状态
echo.
echo [4/4] 验证服务状态...
echo --------------------------------------
netstat -ano | findstr ":5432" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL  : localhost:5432
) else (
    echo [--] PostgreSQL  : 端口未检测到（可能正在启动中）
)

netstat -ano | findstr ":6379" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Redis       : localhost:6379
) else (
    echo [--] Redis       : 端口未检测到
)

netstat -ano | findstr ":8080" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Weaviate    : http://localhost:8080
) else (
    echo [--] Weaviate    : 端口未检测到
)

echo ==============================================
echo 全部服务启动完成！
echo ==============================================
pause
endlocal
