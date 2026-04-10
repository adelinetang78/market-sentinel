@echo off
:: ══════════════════════════════════════════════════════
::  MarketSentinel — Auto-push live data to GitHub Pages
::  Runs every hour via Windows Task Scheduler
::  Set up once, runs silently in the background
:: ══════════════════════════════════════════════════════

:: ── EDIT THIS LINE: path to your market_sentinel folder ──
set REPO_DIR=C:\Users\Think\OneDrive\Claude\market_sentinel

:: ─────────────────────────────────────────────────────────
cd /d "%REPO_DIR%"

:: Check live_data.js exists (scan may not have run yet)
if not exist "data\live_data.js" (
    echo [%date% %time%] No live_data.js found yet. Skipping push.
    exit /b 0
)

:: Stage only the data files (not the whole repo each time)
git add data\live_data.js
git add data\hourly_scan_results.json

:: Check if there's anything new to commit
git diff --cached --quiet
if %errorlevel% == 0 (
    echo [%date% %time%] No changes to push.
    exit /b 0
)

:: Commit with timestamp
git commit -m "Live scan update: %date% %time%"

:: Push to GitHub
git push origin main

echo [%date% %time%] Successfully pushed live data to GitHub Pages.
exit /b 0
