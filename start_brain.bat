@echo off
cd /d "%~dp0"
title AI World - brain (keep this window open)
set PY=
for /f "delims=" %%p in ('where python 2^>nul') do if not defined PY set "PY=%%p"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (echo Python not found. & pause & exit /b)
echo Checking Ollama...
"%PY%" wait_for.py http://127.0.0.1:11434/api/tags 0
if errorlevel 1 (
  echo Ollama is not running - starting it...
  where ollama >nul 2>nul
  if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (start "Ollama" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve) else (echo Ollama not found. Install it from ollama.com & pause & exit /b)
  ) else (
    start "Ollama" /min ollama serve
  )
  "%PY%" wait_for.py http://127.0.0.1:11434/api/tags 30
  if errorlevel 1 (echo Ollama did not start. & pause & exit /b)
)
echo Ollama is ready.
"%PY%" wait_for.py http://127.0.0.1:5005/health 0
if not errorlevel 1 (echo Brain is already running on port 5005. & pause & exit /b)
echo Starting the brain on port 5005...
"%PY%" Brain.py --serve --port 5005
echo.
echo The brain stopped. The error is above.
pause
