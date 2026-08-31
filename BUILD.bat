@echo off
if not exist "Detail plugin languages" mkdir "Detail plugin languages"
if not exist "languages" if exist "AYA_data\languages" xcopy /e /i /q "AYA_data\languages" "languages" >nul
if not exist "languages" mkdir "languages"
pyinstaller --noconsole --onefile --clean --icon="server.ico" ^
  --add-data "web;web" ^
  --add-data "Detail plugin;Detail plugin" ^
  --add-data "Detail plugin languages;Detail plugin languages" ^
  --add-data "languages;languages" ^
  --add-data "server.ico;." ^
  --hidden-import core.state ^
  --hidden-import core.security ^
  --hidden-import core.common ^
  --hidden-import core.config ^
  --hidden-import core.java ^
  --hidden-import core.players ^
  --hidden-import core.backup ^
  --hidden-import core.plugins ^
  --hidden-import core.servers ^
  --hidden-import core.remote ^
  --hidden-import core.tray ^
  --hidden-import core.tunnel ^
  --hidden-import core.tunnel_api ^
  --hidden-import core.updater ^
  --hidden-import tkinter ^
  --hidden-import webview ^
  --collect-submodules webview ^
  --hidden-import shared ^
  --hidden-import shared.protocol ^
  --hidden-import shared.relay ^
  --name="Server Launcher" launcher.py
