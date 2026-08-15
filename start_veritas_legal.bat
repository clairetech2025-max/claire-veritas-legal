@echo off
setlocal
set "ROOT=%~dp0"
powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File "%ROOT%start_veritas_legal.ps1"
endlocal

