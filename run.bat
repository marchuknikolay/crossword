@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ── Check setup ───────────────────────────────────────────
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo.
    echo  *** Setup required! ***
    echo  Please double-click setup.bat first.
    echo.
    pause
    exit /b 1
)

call "%~dp0venv\Scripts\activate.bat"
set "PYTHONPATH=%~dp0src"

REM ── Check for --generate flag anywhere in arguments ───────
set "IS_GENERATE=0"
for %%a in (%*) do (
    if /i "%%a"=="--generate" set "IS_GENERATE=1"
)
if "!IS_GENERATE!"=="1" goto generate_mode

REM ── No arguments: show interactive menu ───────────────────
if "%~1"=="" (
    echo.
    echo  ╔══════════════════════════════════════════╗
    echo  ║         Crossword Generator              ║
    echo  ╚══════════════════════════════════════════╝
    echo.
    echo  Choose a mode:
    echo.
    echo    [1]  Generate from Excel file
    echo         You provide words and clues in a .xlsx file.
    echo         (You can also drag a .xlsx file onto run.bat^)
    echo.
    echo    [2]  Auto-generate from built-in word bank
    echo         Creates a newspaper-style crossword automatically
    echo         using ~3,600 built-in words.
    echo.
    echo    [3]  Show help ^& all options
    echo.
    set /p "CHOICE=  Enter 1, 2, or 3: "
    echo.

    if "!CHOICE!"=="1" goto ask_for_file
    if "!CHOICE!"=="2" goto generate_mode
    if "!CHOICE!"=="3" goto show_help
    echo  Invalid choice.
    echo.
    pause
    exit /b 1
)

REM ── First argument is a file: XLSX mode ───────────────────
goto xlsx_mode

REM ═══════════════════════════════════════════════════════════
:ask_for_file
REM ═══════════════════════════════════════════════════════════
echo  Enter the full path to your .xlsx file
echo  (or drag the file into this window and press Enter^):
echo.
set /p "INPUT=  File: "
REM Remove surrounding quotes if present
set "INPUT=!INPUT:"=!"

if not exist "!INPUT!" (
    echo.
    echo  *** File not found: !INPUT! ***
    echo.
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       Generating crossword...            ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Input: !INPUT!
echo.

python "%~dp0src\crossword_generator.py" "!INPUT!" --retries 30
goto finish

REM ═══════════════════════════════════════════════════════════
:xlsx_mode
REM ═══════════════════════════════════════════════════════════
set "INPUT=%~f1"

if not exist "!INPUT!" (
    echo.
    echo  *** File not found: !INPUT! ***
    echo.
    pause
    exit /b 1
)

REM Collect extra arguments after the filename
set "EXTRA_ARGS="
shift
:parse_xlsx_args
if "%~1"=="" goto run_xlsx
set "EXTRA_ARGS=!EXTRA_ARGS! %1"
shift
goto parse_xlsx_args

:run_xlsx
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       Generating crossword...            ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Input: !INPUT!
echo.

python "%~dp0src\crossword_generator.py" "!INPUT!" --retries 30 !EXTRA_ARGS!
goto finish

REM ═══════════════════════════════════════════════════════════
:generate_mode
REM ═══════════════════════════════════════════════════════════

REM Collect all arguments except --generate
set "EXTRA_ARGS="
for %%a in (%*) do (
    if /i not "%%a"=="--generate" (
        set "EXTRA_ARGS=!EXTRA_ARGS! %%a"
    )
)

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  Auto-generating crossword...            ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Using built-in word bank (~3,600 words)
echo.

python "%~dp0src\crossword_generator.py" --generate --retries 30 !EXTRA_ARGS!
goto finish

REM ═══════════════════════════════════════════════════════════
:show_help
REM ═══════════════════════════════════════════════════════════
echo  ╔══════════════════════════════════════════╗
echo  ║       Crossword Generator — Help         ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  EXCEL MODE (your own words):
echo    run.bat  myfile.xlsx
echo    run.bat  myfile.xlsx  --title "My Puzzle"
echo    run.bat  myfile.xlsx  --grid-size 17
echo    run.bat  myfile.xlsx  --symmetry
echo    run.bat  myfile.xlsx  --title "Fun" --symmetry --grid-size 15
echo.
echo  GENERATE MODE (built-in words):
echo    run.bat  --generate
echo    run.bat  --generate  --title "Daily Puzzle"
echo    run.bat  --generate  --seed 42
echo    run.bat  --generate  --grid-size 17
echo.
echo  ALL OPTIONS:
echo    --title "TEXT"   Set the puzzle title    (default: CROSSWORD^)
echo    --grid-size N    Force grid to NxN       (default: 15 / auto^)
echo    --symmetry       180-degree symmetry     (Excel mode only^)
echo    --retries N      Placement attempts      (default: 30^)
echo    --seed N         Reproducible result
echo    --generate       Use built-in word bank
echo.
echo  TIP: You can also drag a .xlsx file onto run.bat directly.
echo.
pause
exit /b 0

REM ═══════════════════════════════════════════════════════════
:finish
REM ═══════════════════════════════════════════════════════════
echo.
if errorlevel 1 (
    echo  *** Something went wrong. See the error above. ***
) else (
    echo  ────────────────────────────────────────────
    echo  Done!  Check the "output" folder for:
    echo    • PDF crossword puzzle
    echo    • Excel clue list
    echo    • SVG puzzle image
    echo    • SVG answer key
    echo  ────────────────────────────────────────────
)
echo.
pause
