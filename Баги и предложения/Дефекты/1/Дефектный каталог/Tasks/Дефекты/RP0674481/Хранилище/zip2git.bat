@echo off
chcp 1251 > nul
set ZIPFILE=patch.zip
set DISTRPATH=C:\Users\aguljaev\Documents\workspace\project_for_git\distr
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

rem В типе есть архивные файлы: пообъектный перенос
rem ...перенос в проект RP_INTEGR_PRJ
if not exist "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_128_DATA" mkdir "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_128_DATA"
copy /Y "%ZIPPATH%\TYPE\STRUCTURE\REPS_DATA\F_128_DATA\DEL_DATA_PARAM.*" "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_128_DATA\*.*"

rem В типе есть архивные файлы: пообъектный перенос
rem ...перенос в проект RP_INTEGR_PRJ
if not exist "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_129_DATA" mkdir "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_129_DATA"
copy /Y "%ZIPPATH%\TYPE\STRUCTURE\REPS_DATA\F_129_DATA\DEL_DATA_PARAM.*" "%DISTRPATH%\RP_INTEGR_PRJ\src\TYPE\STRUCTURE\REPS_DATA\F_129_DATA\*.*"

