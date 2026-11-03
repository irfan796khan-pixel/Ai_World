@echo off
cd /d "%~dp0"
title AI World - starting
rem ONE CLICK: VoiceStudio (her voice) + Brain.py (her brain, port 5005) + page_server.py (the room, port 8081), then opens her.

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

rem ---- 1. VoiceStudio: open it if it is not running yet
set VS_EXE=C:\Program Files\VoiceStudio\voicestudio.exe
tasklist /fi "imagename eq voicestudio.exe" | find /i "voicestudio.exe" >nul
if errorlevel 1 (
  if exist "%VS_EXE%" (
    echo Opening VoiceStudio...
    start "" "%VS_EXE%"
  ) else (
    echo VoiceStudio is not installed at "%VS_EXE%" - she will use the browser voice.
  )
) else (
  echo VoiceStudio is already open.
)

rem ---- 2. wait until her voice is ready (port 3900), at most 90 seconds
echo Waiting for her voice (VoiceStudio on port 3900)...
"%PY%" wait_for.py http://127.0.0.1:3900/health 90
if errorlevel 1 (echo Voice not ready yet - she uses the browser voice until VoiceStudio is up.) else (echo Voice ready.)

rem ---- 3. brain (Steven's Brain.py) in its own window, unless it is already running
"%PY%" wait_for.py http://127.0.0.1:5005/health 0
if errorlevel 1 (
  start "AI World - brain" "%PY%" "Brain.py" --serve --port 5005
) else (
  echo Brain is already running.
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
