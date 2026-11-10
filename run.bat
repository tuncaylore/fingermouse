@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto :error
title FingerMouse - Otomatik Kurulum

if not exist "requirements.txt" goto :missing_files
if not exist "fingermouse.py" goto :missing_files
set "PYTHON_EXE="
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
  "%VENV_PYTHON%" -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32" >nul 2>&1
  if errorlevel 1 goto :invalid_venv
  goto :packages
)
if exist ".venv" goto :invalid_venv

call :find_python
if not defined PYTHON_EXE (
  echo [1/4] Python 3.12 64-bit yukleniyor. Internet gerekli...
  where winget >nul 2>&1
  if errorlevel 1 goto :no_python
  winget install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --accept-package-agreements --accept-source-agreements --disable-interactivity
  if errorlevel 1 goto :no_python
  call :find_python
  if not defined PYTHON_EXE goto :no_python
)

echo [1/4] Python hazir.
echo [2/4] Yerel sanal ortam olusturuluyor...
%PYTHON_EXE% -m venv "%~dp0.venv"
if errorlevel 1 goto :error

:packages
echo [2/4] Sanal ortam hazir.
set "PIP_REINSTALL="
"%VENV_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
  "%VENV_PYTHON%" -m ensurepip --upgrade
  if errorlevel 1 goto :error
)
"%VENV_PYTHON%" -c "from importlib.metadata import distributions; names={d.metadata['Name'].lower() for d in distributions()}; assert not names.intersection({'opencv-python', 'opencv-python-headless', 'opencv-contrib-python-headless'})" >nul 2>&1
if errorlevel 1 goto :repair_opencv
if not exist ".venv\requirements.installed.txt" goto :install_packages
fc /b "requirements.txt" ".venv\requirements.installed.txt" >nul 2>&1
if errorlevel 1 goto :install_packages
"%VENV_PYTHON%" -c "import cv2, mediapipe, pyautogui, numpy; assert hasattr(mediapipe.tasks.vision, 'HandLandmarker')" >nul 2>&1
if errorlevel 1 goto :repair_packages
"%VENV_PYTHON%" -m pip check
if errorlevel 1 goto :repair_packages
echo [3/4] Paketler hazir. Yeniden indirme gerekmiyor.
goto :launch

:repair_opencv
echo [3/4] Cakisan OpenCV paketleri bulundu. Yerel ortam onariliyor...
"%VENV_PYTHON%" -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python-headless
if errorlevel 1 goto :error

:repair_packages
echo [3/4] Paket kurulumu onariliyor. Internet gerekli...
set "PIP_REINSTALL=--force-reinstall"

:install_packages
echo [3/4] Gerekli paketler yukleniyor. Internet gerekli...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check --only-binary=mediapipe,opencv-contrib-python,numpy %PIP_REINSTALL% -r "requirements.txt"
if errorlevel 1 goto :error
"%VENV_PYTHON%" -m pip check
if errorlevel 1 goto :error
"%VENV_PYTHON%" -c "import cv2, mediapipe, pyautogui, numpy; assert hasattr(mediapipe.tasks.vision, 'HandLandmarker')"
if errorlevel 1 goto :error
copy /y "requirements.txt" ".venv\requirements.installed.txt" >nul
if errorlevel 1 goto :error

:launch
echo [4/4] FingerMouse aciliyor... ESC: cikis, SPACE: duraklat, T: egitim.
if "%~1"=="" (
  "%VENV_PYTHON%" "fingermouse.py"
) else if "%~1"=="--help" (
  "%VENV_PYTHON%" "fingermouse.py" --help
) else (
  "%VENV_PYTHON%" "fingermouse.py" --camera "%~1"
)
if errorlevel 1 goto :error
exit /b 0

:find_python
if not defined PYTHON_EXE (
  python -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python"
)

:: 1. Windows Py Launcher Kontrolü (En baştan dene)
for %%V in (3.12 3.11 3.13 3.10) do (
  if not defined PYTHON_EXE (
    py -%%V -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 set PYTHON_EXE=py -%%V
  )
)

:: 2. Yeni ve Farklı Kurulum Yolları Kontrolü (AppData, Program Files, Python312-64)
for %%V in (312 311 313 310) do (
  if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
  )
  if not defined PYTHON_EXE if exist "%ProgramFiles%\Python%%V\python.exe" (
    set PYTHON_EXE="%ProgramFiles%\Python%%V\python.exe"
  )
  if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V-64\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python%%V-64\python.exe"
  )
)
exit /b 0

:missing_files
echo HATA: Proje dosyalari eksik. ZIP'i tamamen bir klasore cikarin.
goto :error

:invalid_venv
echo HATA: .venv gecersiz veya Python surumu desteklenmiyor.
echo Yalnizca bu proje icindeki .venv klasorunu silip run.bat dosyasini tekrar acin.
goto :error

:no_python
echo HATA: Python otomatik yuklenemedi.
echo https://www.python.org/downloads/windows/ adresinden Python 3.12 64-bit kurun.
echo Kurulumda "Add python.exe to PATH" secenegini isaretleyip run.bat dosyasini tekrar acin.
goto :error

:error
echo.
echo Hata nedeniyle durduruldu. Yukaridaki mesaji kontrol edin.
pause
exit /b 1
