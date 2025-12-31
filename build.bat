@echo off
echo ========================================
echo Building Accessible Space Atlas
echo ========================================
echo.

:: Check if Nuitka is installed
python -c "import nuitka" 2>nul
if errorlevel 1 (
    echo Nuitka not found. Installing...
    pip install nuitka
)

:: Check for ordered-set (improves Nuitka performance)
python -c "import ordered_set" 2>nul
if errorlevel 1 (
    echo Installing ordered-set for better performance...
    pip install ordered-set
)

echo.
echo Starting Nuitka compilation...
echo This may take several minutes...
echo.

:: Build with Nuitka
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=attach ^
    --include-data-dir=data=data ^
    --include-data-files=nvdaControllerClient64.dll=nvdaControllerClient64.dll ^
    --include-data-files=SAAPI64.dll=SAAPI64.dll ^
    --include-data-files=config.json=config.json ^
    --output-filename=AccessibleSpaceAtlas.exe ^
    --output-dir=dist ^
    --company-name="Thomas Leonard" ^
    --product-name="Accessible Space Atlas" ^
    --product-version=1.0.0 ^
    --file-description="Accessible audio space exploration app" ^
    --copyright="Copyright 2025 Thomas Leonard. MIT License." ^
    SpaceAtless.py

echo.
if exist "dist\AccessibleSpaceAtlas.exe" (
    echo ========================================
    echo Build successful!
    echo Output: dist\AccessibleSpaceAtlas.exe
    echo ========================================
) else (
    echo ========================================
    echo Build may have failed. Check output above.
    echo ========================================
)

pause
