@echo off
title 콘택트렌즈 관리 시스템 실행 중...
cd /d "%~dp0"
python -m src.main
if %errorlevel% neq 0 (
    echo.
    echo 프로그램 실행 중 오류가 발생했습니다.
    pause
)
