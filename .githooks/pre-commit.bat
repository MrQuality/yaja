@echo off
python .githooks/pre_commit.py
exit /b %errorlevel%
