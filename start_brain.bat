@echo off
cd /d "%~dp0"
title AI World - brain (keep this window open)
set PY=
for /f "delims=" %%p in ('where python 2^>nul') do if not defined PY set "PY=%%p"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (echo Python not found. & pause & exit /b)
rem COUNCIL_V1 (Imran, 27 Nov): no Ollama any more. Her brain is AI Council Chat (start it from the Desktop) with free OpenRouter as backup.
"%PY%" wait_for.py http://127.0.0.1:8765/ 0
if errorlevel 1 (echo AI Council Chat is not running - she uses free OpenRouter until you start it.)
"%PY%" wait_for.py http://127.0.0.1:5005/health 0
if not errorlevel 1 (echo Brain is already running on port 5005. & pause & exit /b)
echo Starting the brain on port 5005...
"%PY%" Brain.py --serve --port 5005
echo.
echo The brain stopped. The error is above.
pause
