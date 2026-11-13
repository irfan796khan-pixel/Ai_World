@echo off
cd /d "%~dp0"
title AI World - set up her HD voice (OmniVoice)
rem ONE TIME: makes voice_env (its own Python box, so nothing else breaks), installs PyTorch for NVIDIA (CUDA 12.8)
rem and OmniVoice (the voice engine inside VoiceStudio, without the VoiceStudio app), then makes her voice and a test line.
rem Downloads a few GB the first time. Run it again any time to repair.
set PY=
for /f "delims=" %%p in ('where python 2^>nul ^| findstr /v /i WindowsApps') do if not defined PY set "PY=%%p"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PY (echo Python not found. Take a photo of this window. & pause & exit /b)
echo Using Python: %PY%
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
