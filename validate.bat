@echo off
REM Validate all JSON data files under data/ against schemas/*.schema.json
cd /d %~dp0
set PYTHONIOENCODING=utf-8
backend\venv\Scripts\python.exe -X utf8 scripts\validate_data.py %*
