@echo off
chcp 1251 > nul
set ZIPFILE=patch.zip
set DISTRPATH=C:\Users\aguljaev\Documents\workspace\REL234\REL23_4
if exist ZG\workspace (
	del ZG\workspace /S /Q > nul
	rmdir ZG\workspace /S /Q > nul
)
mkdir ZG\workspace
call "C:\Program Files\7-Zip\7z.exe" x "%ZIPFILE%" -y -oZG\workspace > nul

rem копирование шаблонов, если есть
if exist "DATA\*.*" copy /Y "DATA\*.*" "%DISTRPATH%\DEPLOY\DATA\*.*"

rem копирование репортов, если есть
if exist "REPORTS\*.*" copy /Y "REPORTS\*.*" "%DISTRPATH%\DEPLOY\REPORTS\*.*"

rem копирование скриптов, если есть
if exist "SCRIPTS\*.*" copy /Y "SCRIPTS\*.*" "%DISTRPATH%\DEPLOY\SCRIPTS\*.*"

rem копирование gradle-файла
copy /Y "build.gradle.*" "%DISTRPATH%\DEPLOY\GRADLE\*.*"

set ZIPPATH=ZG\workspace\src

rem перенос объекта/версии в проект RP_OPER_PRJ
copy /Y "%ZIPPATH%\ENTITY\ACCOUNT\AC_FIN\PFR_ACC_LIST.*" "%DISTRPATH%\RP_OPER_PRJ\src\ENTITY\ACCOUNT\AC_FIN\*.*"

rem перенос объекта/версии в проект RP_OPER_PRJ
copy /Y "%ZIPPATH%\ENTITY\ACCOUNT\AC_FIN\PFR_ACC_MOVE.*" "%DISTRPATH%\RP_OPER_PRJ\src\ENTITY\ACCOUNT\AC_FIN\*.*"

rem перенос объекта/версии в проект RP_OPER_PRJ
copy /Y "%ZIPPATH%\ENTITY\ACCOUNT\AC_FIN\PFR_ACC_SALDO.*" "%DISTRPATH%\RP_OPER_PRJ\src\ENTITY\ACCOUNT\AC_FIN\*.*"

