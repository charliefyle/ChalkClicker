# ChalkClicker
--------------------
A 1 Million CPS Autoclicker
--------------------

## IMPORTANT: on Windows, the keyboard/mouse global-hook libraries usually
need elevated permissions. Right-click Command Prompt/PowerShell and
choose "Run as administrator" before running this script.

--------------------

## Requirements (install once):
```python
pip install mouse keyboard pystray pillow
```

## To Run it (no need to build an exe while you're testing):
```python
python chalk_autoclicker.py
```

## Turn it into a Windows .exe later (run ON WINDOWS, as Administrator):
```python
pip install pyinstaller
pyinstaller --onefile --noconsole --name chalks_autoclicker chalk_autoclicker.py
```


