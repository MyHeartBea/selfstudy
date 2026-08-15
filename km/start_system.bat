@echo off
rem Launch backend + frontend hidden (no console windows). Pure ASCII.
rem Delegates to start_system_hidden.vbs which starts services detached.
start "" wscript.exe "%~dp0start_system_hidden.vbs"
