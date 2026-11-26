@echo off
cd /d "%~dp0"
title AI World - set up her ears (Whisper large-v3-turbo)
rem ONE TIME: makes ears_env (its own Python box, so nothing else breaks), installs PyTorch for NVIDIA (CUDA 12.8)
rem and transformers, then downloads Whisper large-v3-turbo (about 1.6 GB) and tests it. HER_EARS_V1
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
set EMINOR=
if not exist ears_env goto venv_ok
if exist ears_env\Scripts\python.exe for /f "delims=" %%m in ('ears_env\Scripts\python.exe -c "import sys;print(sys.version_info[1])" 2^>nul') do set "EMINOR=%%m"
if not defined EMINOR goto venv_bad
if %EMINOR% GTR 13 goto venv_bad
if %EMINOR% LSS 10 goto venv_bad
goto venv_ok
:venv_bad
echo The old ears_env is broken or uses a Python that is too new. Removing it...
rmdir /s /q ears_env
if exist ears_env (
  echo Windows would not remove the folder ears_env. Close other black windows, delete the folder ears_env by hand, then run this file again.
  pause
  exit /b
)
:venv_ok
if not exist ears_env\Scripts\python.exe (
  echo Making ears_env...
  "%PY%" -m venv ears_env
  if errorlevel 1 (echo Could not make ears_env. & pause & exit /b)
)
set EP=ears_env\Scripts\python.exe
"%EP%" -m pip install --upgrade pip
echo Installing PyTorch for NVIDIA (CUDA 12.8, works with RTX 50 cards)...
"%EP%" -m pip install torch==2.8.0+cu128 --extra-index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (echo PyTorch did not install. The error is above. & pause & exit /b)
echo Installing transformers...
"%EP%" -m pip install transformers numpy
if errorlevel 1 (echo transformers did not install. The error is above. & pause & exit /b)
"%EP%" -c "import torch;print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
echo Downloading Whisper large-v3-turbo and testing it (first time takes a few minutes)...
if exist her_voice\test.wav (
  "%EP%" her_ears.py --test her_voice\test.wav
) else (
  "%EP%" her_ears.py --test
)
if errorlevel 1 (echo Her ears could not start. The error is above. Send a photo of this window. & pause & exit /b)
echo.
echo Done. Start AI World as always. Her ears start by themselves. Then click Live chat.
pause
