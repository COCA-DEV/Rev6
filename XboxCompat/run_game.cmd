@echo off
rem Runs the retail executable through the Leonida runtime in this window and shows the log live (also saved to run_live.log).
chcp 65001 >nul
set LEONIDA_D3D12=vulkan
set LEONIDA_UNIMPLEMENTED=log
set LEONIDA_SHADERS=D:\tools\leonida\work\shaders\spirv
set LEONIDA_PC_TAIL_UBO=1
set LEONIDA_PAUSE_WATCHDOG=1
rem optional: set LEONIDA_HACK_PROGRAM=1   set LEONIDA_BP=140122630,140032520   set LEONIDA_SAMPLE_THREADS=10
cd /d D:\tools\leonida\runs
powershell -NoProfile -Command "& 'D:\tools\leonida\build\gta6rt.exe' --run 'D:\tools\work\exe\game_scarlett_master.exe' --game-dir 'D:\xbox series dump\GTA6.Xbox.v1.0.2.1' 2>&1 | Tee-Object -FilePath 'D:\tools\leonida\runs\run_live.log'"
echo.
echo Exit code: %ERRORLEVEL%
pause
