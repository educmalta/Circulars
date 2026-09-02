@echo off
REM Launch the Flask dashboard and open the default browser automatically
SETLOCAL
python -c "import webbrowser; webbrowser.open('http://127.0.0.1:5000/dashboard')" || start "" "http://127.0.0.1:5000/dashboard"
python app.py
ENDLOCAL
pause
