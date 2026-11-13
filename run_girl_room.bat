@echo off
cd /d "%~dp0"
title AI World - starting
rem ONE CLICK: her voice (Piper, girl_voice.py) + Brain.py (her brain, port 5005) + page_server.py (the room, port 8081), then opens her.

rem ---- find Python
set PY=
for /f "delims=" %%p in ('where python 2^>nul') do if not defined PY set "PY=%%p"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY (
  echo Python not found. The girl file cannot load without a small local server.
  pause
  exit /b
)

rem ---- 1. her voice: Piper teen girl voice on this laptop (girl_voice.py). First time only: installs Piper + downloads the voice (about 63 MB).
echo Getting her voice ready...
"%PY%" girl_voice.py --setup
if errorlevel 1 (echo Her voice could not be set up - she uses the browser voice.)
rem VoiceStudio is no longer needed for her voice. If it is running, Live chat uses it for speech-to-text; if not, the browser does that.

rem ---- 3. brain (Steven's Brain.py) in its own window, unless it is already running
"%PY%" wait_for.py http://127.0.0.1:5005/health 0
if errorlevel 1 (
  rem BRAIN_START_V1: start_brain.bat also starts Ollama and stays open with the error if the brain stops
  start "AI World - brain" cmd /c start_brain.bat
  echo Waiting for the brain to wake up ^(up to 60 s^)...
  "%PY%" wait_for.py http://127.0.0.1:5005/health 60
) else (
  echo Brain is already running.
)

rem ---- her HD voice (OmniVoice, the engine inside VoiceStudio, without the app). Only if setup_her_voice.bat was run.
if exist voice_env\Scripts\python.exe (
  "%PY%" wait_for.py http://127.0.0.1:3901/health 0
  if errorlevel 1 start "AI World - her HD voice (keep open)" /min voice_env\Scripts\python.exe her_voice.py
)

rem ---- 4. the room + voice pass-through, then open her
"%PY%" wait_for.py http://127.0.0.1:8081/Girl_Room.html 0
if not errorlevel 1 (
  echo The room is already running - opening it.
  start "" http://localhost:8081/Girl_Room.html
  timeout /t 3 >nul
  exit /b
)
start "" http://localhost:8081/Girl_Room.html
title AI World - room (keep this window open)
rem page_server.py = the page + her VoiceStudio voice on the same address (the browser blocks port 3900 otherwise)
"%PY%" page_server.py 8081
