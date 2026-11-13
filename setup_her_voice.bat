@echo off
cd /d "%~dp0"
title AI World - set up her HD voice (OmniVoice)
rem ONE TIME: makes voice_env (its own Python box, so nothing else breaks), installs PyTorch for NVIDIA (CUDA 12.8)
rem and OmniVoice (the voice engine inside VoiceStudio, without the VoiceStudio app), then makes her voice and a test line.
rem PyTorch 2.8.0 only exists for Python 3.10, 3.11, 3.12 and 3.13. A newer Python (3.14) fails with "No matching distribution".
rem Downloads a few GB the first time. Run it again any time to repair.
set PY=
rem 1) the Windows "py" launcher, newest good version first
for %%v in (3.12 3.11 3.13 3.10) do if not defined PY (
  for /f "delims=" %%p in ('py -%%v -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%p"
)
rem 2) the usual install folders
for %%c in ("%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python311\python.exe" "%ProgramFiles%\Python313\python.exe") do if not defined PY if exist %%c set "PY=%%~c"
rem 3) whatever "python" is on the PATH, only if its version is 3.10 to 3.13 (skips the fake Windows Store one)
if not defined PY for /f "delims=" %%p in ('where python 2^>nul ^| findstr /v /i WindowsApps') do if not defined PY ("%%p" -c "import sys;sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)" 2>nul && set "PY=%%p")
if not defined PY (
  echo.
  echo No Python 3.10 to 3.13 was found. Your Python is probably too new for PyTorch 2.8.0.
  echo Install Python 3.12 from https://www.python.org/downloads/windows/ then run this file again.
  echo Pick "Install for me only" or leave the default folder.
  pause
  exit /b
)
echo Using Python: %PY%
"%PY%" --version
rem an old voice_env made with a wrong Python is thrown away and made again
if exist voice_env\Scripts\python.exe (
  voice_env\Scripts\python.exe -c "import sys;sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)" 2>nul
  if errorlevel 1 (
    echo The old voice_env uses a Python that is too new. Making it again...
    rmdir /s /q voice_env
  )
)
if not exist voice_env\Scripts\python.exe (
  echo Making voice_env...
  "%PY%" -m venv voice_env
  if errorlevel 1 (echo Could not make voice_env. & pause & exit /b)
)
set VP=voice_env\Scripts\python.exe
"%VP%" -m pip install --upgrade pip
echo Installing PyTorch for NVIDIA (CUDA 12.8)...
"%VP%" -m pip install torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --extra-index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (echo PyTorch did not install. The error is above. & pause & exit /b)
echo Installing OmniVoice...
"%VP%" -m pip install omnivoice soundfile numpy
if errorlevel 1 (echo OmniVoice did not install. The error is above. & pause & exit /b)
"%VP%" -c "import torch;print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
echo Making her voice and a test line (downloads the OmniVoice model the first time)...
"%VP%" her_voice.py --test "Hi. This is my new voice. Try not to fall in love with it."
if errorlevel 1 (echo Her voice could not be made. The error is above. & pause & exit /b)
echo.
echo Done. Listen to her_voice\test.wav. Then start AI World and pick "Voice: Her HD voice" in the voice menu.
start "" "her_voice\test.wav"
pause
