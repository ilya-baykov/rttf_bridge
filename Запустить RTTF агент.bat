@echo off
setlocal

cd /d "%~dp0"

echo Запуск RTTF агента...
echo Лог пишется в: %cd%\logs\rttf-agent.log
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo Не найден uv в PATH.
  echo Установите uv или запускайте из окружения, где команда uv доступна.
  echo.
  pause
  exit /b 1
)

uv run python main.py
set "status=%errorlevel%"

echo.
if "%status%"=="0" (
  echo Готово.
) else (
  echo Завершено с ошибкой. Код: %status%
)

echo.
pause
exit /b %status%
