VER2
REM Список элементов
REM ibs@57_TEST_REP_NSK2
REM CFT-Platform-IDE: 2.36.270

REM ERR RP0674201

REM Включена валидация для даты на экранной форме;
REM В функции GetRegNumClient, в цикле изменён способ обращения к таблице SOC_FOUNDS;
REM Добавлены условия: 
REM - x%collection = P_FONDS_AR
REM - Условие по дате снятия с регистрации
REM В функции GetInfoClient добавлено условие по дате снятия с регистрации
METH AC_FIN PFR_ACC_LIST

REM В функциях GetRegNumClient и GetInfoClient, добавлены условия по дате снятия с регистрации
METH AC_FIN PFR_ACC_MOVE

REM Включена валидация для даты на экранной форме;
REM В функции GetRegNumClient, в цикле изменён способ обращения к таблице SOC_FOUNDS;
REM Добавлены условия: 
REM - x%collection = P_FONDS_AR
REM - Условие по дате снятия с регистрации
REM В функции GetInfoClient добавлено условие по дате снятия с регистрации
METH AC_FIN PFR_ACC_SALDO