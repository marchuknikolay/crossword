@echo off
chcp 65001 >nul 2>&1
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║    Crossword Generator — First-Time Setup ║
echo  ╚══════════════════════════════════════════╝
echo.

REM ── Step 1: Check Python ──────────────────────────────────
echo [1/4] Checking for Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  *** ERROR: Python is NOT installed! ***
    echo.
    echo  Please follow these steps:
    echo.
    echo    1. Open your browser and go to:
    echo       https://www.python.org/downloads/
    echo.
    echo    2. Click the big yellow "Download Python" button.
    echo.
    echo    3. Run the downloaded installer.
    echo       IMPORTANT: On the very first screen, check the box:
    echo       [x] "Add Python to PATH"
    echo       Then click "Install Now".
    echo.
    echo    4. After installation finishes, CLOSE this window
    echo       and double-click setup.bat again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo        Found: %%v
echo.

REM ── Step 2: Create virtual environment ────────────────────
echo [2/4] Creating isolated environment...

if exist "%~dp0venv" (
    echo        Environment already exists, skipping.
) else (
    python -m venv "%~dp0venv"
    if errorlevel 1 (
        echo.
        echo  *** ERROR: Could not create environment. ***
        echo  Try reinstalling Python with the "Add to PATH" option.
        echo.
        pause
        exit /b 1
    )
    echo        Done.
)
echo.

REM ── Step 3: Install dependencies ──────────────────────────
echo [3/4] Installing required packages...

call "%~dp0venv\Scripts\activate.bat"

pip install --quiet openpyxl>=3.1.0 reportlab>=4.0 blacksquare nltk
if errorlevel 1 (
    echo.
    echo  *** ERROR: Package installation failed. ***
    echo  Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo        Done.
echo.

REM ── Step 4: Download language data ─────────────────────────
echo [4/4] Downloading word dictionary data...

python -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)"
if errorlevel 1 (
    echo.
    echo  *** WARNING: Could not download language data. ***
    echo  The "generate" mode may not work, but Excel mode will.
    echo.
) else (
    echo        Done.
)
echo.

REM ── Finished ──────────────────────────────────────────────
echo  ╔══════════════════════════════════════════╗
echo  ║         Setup completed successfully!     ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Next steps:
echo    - run.bat          Crossword from your Excel file
echo                       (drag .xlsx onto it, or double-click for help)
echo    - generate.bat     Crossword from built-in word bank
echo                       (double-click to run)
echo    - See INSTRUCTIONS.txt for the full guide.
echo.
pause
