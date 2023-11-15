VER2

REM ERR RP0674410


REM Имена типов заменены по требованиям стиля, табличные типы заменены по требованиям стиля.
REM Удалены неиспользуемые переменные recAnCashe, nTmp, aData, is_reval_cb, recNS, nSumm, iErr, и неиспользуемый тип arrTab.
REM Добавлены all в запросы.
REM В InitCorrAccTable удалено использование member of - проверка реализована через новую переменную vAnalytic.
REM Длинные строки разбиты на несколько.
REM Добавлены fetch в запросы.
REM Исправлены ошибки несоответствия типов для C_ANALYTIC, при необходимости через новую переменную rAC.
METH F_110_DATA CLC_ACCOUNTS_006

REM Установлен архивный тэг, установлен признак java=false
METH F_110_DATA CLC_CB_004
METH F_110_TUNING COPY_TUNES_F110


