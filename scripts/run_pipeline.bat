@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0.."
if errorlevel 1 exit /b 1

if not exist "logs" mkdir "logs" >nul 2>&1

>> "logs\scheduled_run.log" echo [START] %date% %time%

call ".venv\Scripts\activate.bat" >> "logs\scheduled_run.log" 2>&1
set "pipeline_exit_code=!errorlevel!"
if not "!pipeline_exit_code!"=="0" goto :finish

python -m src.main >> "logs\scheduled_run.log" 2>&1
set "pipeline_exit_code=!errorlevel!"

:finish
>> "logs\scheduled_run.log" echo [END] %date% %time% exit_code=!pipeline_exit_code!
exit /b !pipeline_exit_code!