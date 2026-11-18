@echo off
title Push kaggle-llm-server to GitHub
cd /d "%~dp0"

echo ============================================================
echo   Push to https://github.com/piost/kaggle-llm-server
echo ============================================================
echo.
echo  A GitHub Personal Access Token (PAT) is required.
echo  Create one at: https://github.com/settings/tokens
echo  Generate new token (classic), check the "repo" scope, copy it.
echo.
set /p TOKEN="Paste your PAT here: "

if "%TOKEN%"=="" (
  echo [ERROR] No token entered.
  pause
  exit /b 1
)

echo.
echo [*] Setting remote with token...
git remote set-url origin "https://%TOKEN%@github.com/piost/kaggle-llm-server.git"

echo [*] Pushing to main...
git -c http.sslVerify=false push -u origin main
set RC=%ERRORLEVEL%

echo.
if %RC%==0 (
  echo [OK] Pushed successfully!
  echo      https://github.com/piost/kaggle-llm-server
) else (
  echo [FAIL] Push failed (code %RC%). Make sure token has "repo" scope.
)

echo.
echo [*] Removing token from remote URL for safety...
git remote set-url origin "https://github.com/piost/kaggle-llm-server.git"
echo.
pause
