@echo off
rem Builds dist\LabSimulator.exe (needs Python 3.10+).
rem Temporary build files go to %TEMP% so OneDrive does not lock them.
cd /d "%~dp0"
python -m pip install --user pygame-ce numpy pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name LabSimulator --exclude-module tkinter --exclude-module PIL ^
  --icon "%~dp0game\icon.ico" --add-data "%~dp0game\icon.png;." --add-data "%~dp0game\logo.png;." --add-data "%~dp0game\juanlab.png;." ^
  --paths "%~dp0game" --distpath "%~dp0dist" ^
  --workpath "%TEMP%\labsimbuild" --specpath "%TEMP%\labsimbuild" "%~dp0game\main.py"
pause
