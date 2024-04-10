import os
import sys
import json
import shutil
import datetime as dt
import webbrowser

from ui_taskmanager import *
from ui_task import *
from ui_dir import *
from ui_storage import *
from DatabaseConnector import DatabaseConnector

from PySide6.QtWidgets import (
    QMessageBox, QTableWidget, QAbstractItemView, QHeaderView, QMenu, QTableWidgetItem, QFileDialog)
from PySide6.QtGui import (QAction, QColor, QMouseEvent)
from PySide6 import QtGui


class TaskManager(QMainWindow):
    def __init__(self) -> None:
        super(TaskManager, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Чтение настроек
        self.readSettingsApp()

        # Инициализируем класс для соединения с БД
        self.initDB()

        # Скрываем окна и элементы
        self.ui.leftMenu.hide()
        self.ui.notificationContent.hide()
        self.ui.label_action_now.hide()
        self.ui.progressBar.hide()

        # Инициализация элементов приложения
        self.initHandler()
        self.initSignals()

        # Инициализируем первый раз меню кнопок
        self.changeBtnMenu()

        self.initMTaskManager()
        self.initMActiveTask()
        self.initMPow()


###########################################################
# Основные методы
###########################################################

    def testAction(self):
        '''
        Тестовое действие
        '''

    def readJson(self, file_path: str) -> dict:
        '''Читает json файл и возвращает словарь'''
        json_data = []
        # Если не найден файл, возвращает пустой словарь
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            jsonData = f.read()

        json_data = json.loads(jsonData)
        return json_data

    def writeJson(self, file_path, data: dict):
        '''Записывает json файл'''
        json_string = json.dumps(data, ensure_ascii=False)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(json_string)

    def setDefaultSettings(self):
        '''Создаёт стандартный файл настроек'''
        self.settings = {
            'work_dir': 'Working directory',
            'template_name': '.template',
            'archive_name': '.archive',
            'user_name': '',
            'oracle_config_dir': '',
            'dsn': '',
            'user_to_db': '',
            'password_to_db': '',
            'colors': {'Белый': '#ffffff', 'Красный': '#ff0000', 'Зелёный': '#99ff66', 'Жёлтый': '#ffff00'}
        }
        # Если не создана папка с рабочей директорий
        if not os.path.isdir(self.settings.get('work_dir')):
            os.mkdir(self.settings.get('work_dir'))

        self.writeSettingsApp(self.settings)

    def readSettingsApp(self) -> bool:
        '''
        Читает настройки приложения
        '''
        self.settings = self.readJson('settings.json')
        if not self.settings:
            self.setDefaultSettings()
        if not self.checkSettings():
            sys.exit()

    def writeSettingsApp(self, settings: dict):
        '''
        Записывает настройки приложения
        '''
        self.writeJson('settings.json', self.settings)

    def checkSettings(self) -> bool:
        '''Проверяем настройки'''
        if not os.path.isdir(self.settings.get('work_dir')):
            self.printInfo('Ошибка', 'Укажите корректную, рабочую директорию')
            return False
        # TODO Добавить проверки
        return True

    def printInfo(self, title: str = None, text: str = None):
        '''Выводит информацию на экран и в консоль'''
        QMessageBox.information(self, title, text)

    def initHandler(self):
        '''
        Инициализация обработчика нажатий клавиш
        '''
        # Основные кнопки
        self.ui.menuBtn.clicked.connect(self.handler)
        self.ui.notificationBtn.clicked.connect(self.handler)
        self.ui.settingsBtn.clicked.connect(self.handler)
        self.ui.infoBtn.clicked.connect(self.handler)

        # Внутренние кнопки
        self.ui.showTasksBtn.clicked.connect(self.handler)
        self.ui.showActiveTasksBtn.clicked.connect(self.handler)
        self.ui.showPotBtn.clicked.connect(self.handler)

        # Изменение состояния
        self.ui.task_status.currentIndexChanged.connect(self.handler)

        # Модульные кнопки
        # TODO

    def handler(self):
        '''
        Обработчик нажатий кнопок
        '''
        sender = self.sender()

        match sender.objectName():
            # Основные кнопки
            case 'menuBtn':
                self.showLeftMenu(0)
            case 'settingsBtn':
                self.showLeftMenu(1)
                self.ui.mainContents.setCurrentIndex(3)
            case 'infoBtn':
                self.showLeftMenu(2)
            case 'notificationBtn':
                if self.ui.notificationContent.isHidden():
                    self.ui.notificationContent.show()
                else:
                    self.ui.notificationContent.hide()

            # Внутренние кнопки
            case 'showTasksBtn':
                self.ui.mainContents.setCurrentIndex(0)
            case 'showActiveTasksBtn':
                self.ui.mainContents.setCurrentIndex(1)
            case 'showPotBtn':
                self.ui.mainContents.setCurrentIndex(2)

            # Кнопки создания заявки
            case 'addLinksBtn':
                row_count = self.ui_task.tabLinks.rowCount()
                self.ui_task.tabLinks.insertRow(row_count)
            case 'delLinksBtn':
                row_index = self.ui_task.tabLinks.currentRow()
                if row_index > -1:
                    self.ui_task.tabLinks.removeRow(row_index)

            # Состояние заявок
            case 'task_status':

                self.fillTaskManagerTab()

            # Прочее
            case _:
                # Модульные кнопки
                match sender.text():
                    case 'Тестовое действие':
                        self.testAction()
                    # Модуль Ведение заявок
                    case 'Открыть директорию':
                        dir_data = self.getCurrentDirData()
                        if not dir_data:
                            return
                        dir_name = dir_data.get('dir_name')
                        task_number = ''
                        # Если выбрана заявка иначе открываем общую
                        if self.selectedRow() != -1:
                            task_data = self.getCurrentTaskData()
                            link = self.getTaskPath(dir_name, task_data.get(
                                'task_number'), task_data.get('description'))
                        else:
                            link = self.getDirPath(dir_name)
                        self.openLink(link)
                    case 'Обновить хранилище':
                        self.openStorageWindow()
                    case 'Обновить информацию по заявкам':
                        self.updateTasksInfo()
                    case 'Создать директорию':
                        self.openDirWindow()
                    case 'Создать заявку':
                        self.openTaskWindow()
                    case 'Перенести выбранную заявку в архив':
                        task_data = self.getCurrentTaskData()
                        if not task_data:
                            return
                        self.moveTask2Arch(task_data.get(
                            'dir_name'), task_data.get('task_number'))
                    case 'Удалить текущую директорию':
                        self.removeDir()
                    case 'Удалить выбранную заявку':
                        self.removeTask()
                    case 'Редактировать текущую директорию':
                        dir_data = self.getCurrentDirData()
                        if dir_data:
                            self.openDirWindow(dir_data)
                    case 'Редактировать выбранную заявку':
                        task_data = self.getCurrentTaskData()
                        if task_data:
                            self.openTaskWindow(task_data)
                    case _:
                        print('Неизвестное нажатие')

    def showLeftMenu(self, index: int):
        '''
        Отображает нужную вкладку в меню слева
        '''
        if self.ui.leftMenu.isHidden():
            self.ui.leftMenu.show()
            self.ui.menuContents.setCurrentIndex(index)
        else:
            if self.ui.menuContents.currentIndex() == index:
                self.ui.leftMenu.hide()
            else:
                self.ui.menuContents.setCurrentIndex(index)

    def initMTaskManager(self):
        '''
        Инициализирует модуль "Ведение заявок"
        '''
        self.fillTaskManagerTab(first_fill=True)

    def initMActiveTask(self):
        '''
        Инициализирует модуль "Активные заявки"
        '''

    def initMPow(self):
        '''
        Инициализирует модуль "Котёл"
        '''

    def initSignals(self):
        '''
        Инициализирует сигналы
        '''
        self.ui.mainContents.currentChanged.connect(self.changeBtnMenu)
        self.ui.taskManagerTab.currentChanged.connect(self.changedDir)

    def initDB(self):
        '''Инициализируем подключение к БД'''
        db_settings = dict()
        self.db_con = DatabaseConnector()

    def checkDBSetting(self) -> bool:
        '''Проверка настроек БД'''
        if not self.settings.get('user_name'):
            self.printInfo('Предупреждение', 'Не задано имя пользователя')
            return False

        if not self.settings.get('oracle_config_dir'):
            self.printInfo('Предупреждение', 'Не задана директория с Oracle')
            return False
        elif not os.path.isdir(self.settings.get('oracle_config_dir')):
            self.printInfo('Предупреждение', 'Не найдена директория с Oracle')
            return False

        if not self.settings.get('dsn'):
            self.printInfo('Предупреждение', 'Не задан сервер')
            return False

        if not self.settings.get('user_to_db'):
            self.printInfo('Предупреждение',
                           'Не задано имя пользователя базы данных')
            return False

        if not self.settings.get('password_to_db'):
            self.printInfo('Предупреждение',
                           'Не задан пароль пользователя базы данных')
            return False

        return True

    def getDBSetting(self) -> dict:
        '''Возвращает словарь настроек'''
        settings = dict()

        settings['user_name'] = self.settings.get('user_name')
        settings['oracle_config_dir'] = self.settings.get('oracle_config_dir')
        settings['dsn'] = self.settings.get('dsn')
        settings['user_to_db'] = self.settings.get('user_to_db')
        settings['password_to_db'] = self.settings.get('password_to_db')

        return settings

    def changeBtnMenu(self):
        '''
        Создаёт меню для кнопок взависимости от текущего модуля
        '''
        current_module = self.ui.mainContents.currentIndex()

        self.btns_menu = {}
        # ?
        self.btns_menu['action'] = QMenu()
        self.btns_menu['add'] = QMenu()
        self.btns_menu['remove'] = QMenu()
        self.btns_menu['edit'] = QMenu()

        # Получаем меню каждого модуля
        match current_module:
            case 0:
                self.btns_menu = self.getTaskManagerBtnsMenu(self.btns_menu)
            case 1:
                self.btns_menu = self.getAcitveTaskBtnsMenu(self.btns_menu)
            case 2:
                self.btns_menu = self.getPotBtnsMenu(self.btns_menu)
            case 3:
                # TODO Реализовать меню для настроек
                pass
            case _:
                print(f'Неизвестный модуль: {current_module}')

        # Задаём полученные меню для кнопок
        self.ui.actionBtn.setMenu(self.btns_menu.get('action'))
        self.ui.addBtn.setMenu(self.btns_menu.get('add'))
        self.ui.removeBtn.setMenu(self.btns_menu.get('remove'))
        self.ui.editBtn.setMenu(self.btns_menu.get('edit'))

    def changeBtnMenu4Mouse(self):
        '''
        Изменяет выпадающее меню по нажатию правой кнопки мыши для каждого случая
        '''
        current_module = self.ui.mainContents.currentIndex()

        self.mouse_menu = QMenu()

        # Получаем меню каждого модуля
        match current_module:
            case 0:
                self.mouse_menu = self.getTaskManagerMouseMenu()
            case 1:
                self.mouse_menu = self.getAcitveTaskMouseMenu()
            case 2:
                self.mouse_menu = self.getPotMouseMenu()
            case 3:
                # TODO Реализовать меню для настроек
                pass
            case _:
                print(f'Неизвестный модуль: {current_module}')

        # Задаём полученное меню для

    def getTaskManagerBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Ведение заявок" 
        '''
        # Тестовое действие
        # btns_menu['action'].addAction('Тестовое действие', self.handler)

        # Меню действия
        btns_menu['action'].addAction('Открыть директорию', self.handler)

        # Меню для данного действия реализуется в updateTaskLinksMenu
        self.task_links_menu = btns_menu['action'].addMenu('Открыть ссылку')
        btns_menu['action'].addAction('Обновить хранилище', self.handler)
        btns_menu['action'].addSeparator()
        btns_menu['action'].addAction(
            'Обновить информацию по заявкам', self.handler)
        # Меню добавить
        btns_menu['add'].addAction('Создать директорию', self.handler)
        btns_menu['add'].addAction('Создать заявку', self.handler)
        # Меню убрать
        btns_menu['remove'].addAction(
            'Перенести выбранную заявку в архив', self.handler)
        btns_menu['remove'].addSeparator()
        btns_menu['remove'].addAction(
            'Удалить текущую директорию', self.handler)
        btns_menu['remove'].addAction(
            'Удалить выбранную заявку', self.handler)
        # Меню изменить
        btns_menu['edit'].addAction(
            'Редактировать выбранную заявку', self.handler)
        btns_menu['edit'].addAction(
            'Редактировать текущую директорию', self.handler)

        return btns_menu

    def getAcitveTaskBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Активные заявки" 
        '''
        # TODO
        # Меню действие
        # Меню добавить
        # Меню убрать
        # Меню изменить

        return btns_menu

    def getPotBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Котел" 
        '''
        # TODO
        # Меню действие
        # Меню добавить
        # Меню убрать
        # Меню изменить

        return btns_menu

    def getTaskManagerMouseMenu(self) -> QMenu:
        '''
        Задаёт меню правой кнопки для модуля "Ведение заявок" 
        '''

        menu = QMenu()

        menu.addAction('Открыть директорию', self.handler)

        return menu

    def getAcitveTaskMouseMenu(self) -> QMenu:
        '''
        Задаёт меню правой кнопки для модуля "Ведение заявок" 
        '''
        pass

    def getPotMouseMenu(self) -> QMenu:
        '''
        Задаёт меню правой кнопки для модуля "Ведение заявок" 
        '''
        pass

    def clearTable(self, tab_index, clear_headers: bool = False):
        '''
        Очищает содержимое таблицы
        '''
        # Удаляем строки
        for row_num in range(self.ui.taskManagerTab.widget(tab_index).rowCount(), -1, -1):
            self.ui.taskManagerTab.widget(tab_index).removeRow(row_num)

        if clear_headers:
            for column_num in range(self.ui.taskManagerTab.widget(tab_index).columnCount(), -1, -1):
                self.ui.taskManagerTab.widget(
                    tab_index).removeColumn(column_num)

    def countElementsInDir(self, path: str) -> int:
        '''
        Считает количество элементов в директории
        '''
        # count_elements = len(os.listdir(path))
        # for elements in os.listdir(path):
        #     # Если есть вложенные директории, то рекурсивно считаем
        #     if os.path.isdir(self.createPath(path, elements)):
        count_elements = 0
        for root, dirs, files in os.walk(path):
            for name in files:
                count_elements += 1

        return count_elements

    def progressBar(self, state_now: int, stat_last: int, text):
        '''
        Задаёт состояние для прогресс бара
        '''
        # Инициализируем если скрыты
        if self.ui.label_action_now.isHidden() or self.ui.progressBar.isHidden():
            self.ui.label_action_now.show()
            self.ui.progressBar.show()
            self.ui.progressBar.setMinimum(0)
            self.ui.progressBar.setMaximum(stat_last)

        # Записываем значения
        self.ui.label_action_now.setText(text)
        self.ui.progressBar.setValue(state_now)

        # Скрываем если всё выполнилось
        if state_now >= stat_last:
            self.ui.label_action_now.hide()
            self.ui.progressBar.hide()

###########################################################
###########################################################
# Модуль "Ведение заявок"
###########################################################

    def fillTaskManagerTab(self, current_dir_name: str = None, first_fill: bool = False):
        '''
        Заполняет таблицу на основании рабочей директории
        Если указана текущая директория то обновляет её содержимое
        '''
        # Получаем список директорий и заявок
        dir_list = self.readWorkDir()

        # Смотрим какие заявки надо отображать Не скрытые, Скрытые, Все
        status_text = self.ui.task_status.currentText()

        # Читаем словарь с папками в рабочей директории и заполняем таблицу
        for dir_name in dir_list.keys():
            # Проверяем что есть файл .dirData.json
            if not os.path.isfile(self.getDirPath(dir_name, True)):
                continue

            # Если необходимо заполнить только одну диреткорию, не создавая таблицу
            if current_dir_name != None and current_dir_name != dir_name:
                continue

            if current_dir_name == None and first_fill:
                # Получаем информацию по директории и создаём таблицу
                dir_data = self.getDirData(dir_name)
                self.putDir2Tab(dir_data)

            if not first_fill:
                # Очищаем таблицу
                tab_index = self.getIndexTabByName(dir_name)
                self.clearTable(tab_index)

            # Создаём заявки в таблице
            for task_path in dir_list[dir_name]:
                task_number = task_path.split('_(', 1)[0]
                task_data = self.getTaskData(dir_name, task_number)

                # Проверка статуса
                if (task_data.get('hidden') and status_text == 'Скрытые') or (
                    not task_data.get('hidden') and status_text == 'Не скрытые') or (
                    status_text == 'Все'
                ):
                    self.putTask2Tab(task_data)

    def readWorkDir(self, current_dir_name: str = None) -> dict:
        '''
        Читает рабочую директорию, создаёт словарь директория-заявки
        Если передать название директории с заявками, то составит список заявок только с выбранной директорией
        '''
        dir_task_list = {}
        for dir_name in os.listdir(self.settings.get('work_dir')):

            # Проверяем что есть файл .dirData.json
            if not os.path.isfile(self.getDirPath(dir_name, True)):
                continue

            # Если нужна конкретная директория, то пропускаем все остальные
            if current_dir_name != None and dir_name != current_dir_name:
                continue

            # Записываем название директории в которую помещяем список заявок
            list_tasks = []
            for task_path in os.listdir(self.getDirPath(dir_name)):
                task_number = task_path.split('_(', 1)[0]
                # Исключаем зарезервированные папки
                if task_number in (self.settings.get('template_name'), self.settings.get('archive_name')):
                    continue

                # Получаем файл с информацией по заявке
                task_data_path = self.createPath(self.createPath(
                    self.getDirPath(dir_name), task_path), '.taskData.json')
                # Проверяем что в папке есть файл с настройками
                if not os.path.isfile(task_data_path):
                    continue

                # Если всё хорошо, то записываем заявку
                list_tasks.append(task_number)

            dir_task_list[dir_name] = list_tasks.copy()

        return dir_task_list

    def updateTasksInfo(self):
        '''
        Обновляет информацию по заявкам
        '''
        if not self.checkDBSetting():
            return

        self.progressBar(1, 6, 'Обновление информации по заявкам')

        # Собираем список заявок
        work_dir_dict = self.readWorkDir()
        tasks_numbers = []
        dict_to_update = []
        answer = []

        for dir_name in work_dir_dict.keys():
            for task_path in work_dir_dict[dir_name]:
                task_number = task_path.split('_(', 1)[0]

                # Получаем файл с информацией по заявке
                task_data = self.getTaskData(dir_name, task_number)

                # Проверяем какой статус у заявки
                status_text = self.ui.task_status.currentText()
                if (task_data.get('hidden') and status_text == 'Скрытые') or (
                    not task_data.get('hidden') and status_text == 'Не скрытые') or (
                        status_text == 'Все'
                ):
                    # Выбираем только те заявки которые начинаются с RP или SUP
                    task_number = task_data.get('task_number')
                    if task_number.startswith('RP') or task_number.startswith('SUP'):
                        tasks_numbers.append(task_number)
                        dict_to_update.append(f'{dir_name}:{task_number}')

        self.progressBar(2, 6, 'Обновление информации по заявкам')

        if len(tasks_numbers) > 0:
            self.progressBar(3, 6, 'Запрос к серверу')
            # Получаем ответ от сервера
            answer = self.db_con.getTasksInfo(
                tasks_numbers, self.getDBSetting())

            self.progressBar(4, 6, 'Разбираем ответ')

            # Подставляем значения
            # TODO придумать более производительный алгоритм обхода
            set_dir = set()
            for dir_task in dict_to_update:
                dir_name = dir_task.split(':')[0]
                set_dir.add(dir_name)
                task_number = dir_task.split(':')[1]

                # Находим данные заявки
                task_data_path = self.getTaskPath(
                    dir_name, task_number, get_task_data_path=True)
                task_data = self.getTaskData(dir_name, task_number)

                # Заполняем информаицию из ответа
                for task_info in answer:
                    # Если не та заявка
                    if task_number != task_info.get('task_number'):
                        continue

                    # Записываем новую информацию
                    task_data['labor_costs'] = task_info.get('labor_costs')
                    task_data['all_labor_costs'] = task_info.get(
                        'all_labor_costs')
                    task_data['plane_labor_costs'] = task_info.get(
                        'plane_labor_costs')
                    task_data['deadline'] = task_info.get('deadline')
                    self.writeJson(task_data_path, task_data)

            self.progressBar(5, 6, 'Заполняем таблицы')
            for dir_name in set_dir:
                self.fillTaskManagerTab(dir_name)

            self.progressBar(6, 6, 'Выполнено')

########################
# Работа с директорией
########################
    def changedDir(self):
        '''Действия при смене директории'''
        # Если директория не последняя
        if self.ui.taskManagerTab.currentWidget() != None:
            self.ui.taskManagerTab.currentWidget().setCurrentCell(-1, -1)

    def createPath(self, path_one: str, path_two: str) -> str:
        return os.path.join(path_one, path_two)

    def getDirPath(self, dir_name: str, get_dir_data_path: bool = False) -> str:
        '''
        Возвращает полный путь до рабочей директории
        '''
        if get_dir_data_path:
            path = self.createPath(self.getDirPath(dir_name), '.dirData.json')
        else:
            work_dir = self.settings.get('work_dir')
            path = self.createPath(work_dir, dir_name)
        return path

    def getDirData(self, dir_name) -> dict:
        '''
        Возвращает информацию по директории
        '''
        dir_data_path = self.getDirPath(dir_name, True)
        # Проверяем есть файл с настройками
        if not os.path.isfile(dir_data_path):
            self.printInfo(
                'Ошибка!', f'В папке {dir_name}, не найден настроечный файл .dirData.json')
            return None

        return self.readJson(dir_data_path)

    def getIndexTabByName(self, tab_name) -> int:
        '''
        Возвращает index в tab
        '''
        index = None
        for index in range(self.ui.taskManagerTab.count()):
            if self.ui.taskManagerTab.tabText(index) == tab_name:
                return index

        return None

    def getCurrentDirData(self) -> dict:
        '''
        Возвращает информацию по текущей директории
        '''
        tab_index = self.ui.taskManagerTab.currentIndex()
        if tab_index == -1:
            self.printInfo('Уведомление', 'Необходимо выбрать директорию')
            return None

        dir_name = self.ui.taskManagerTab.tabText(tab_index)

        return self.getDirData(dir_name)

    def createDir(self, dir_data: dict) -> bool:
        '''
        Создаёт новую директорию
        '''
        dir_path = self.getDirPath(dir_data.get('dir_name'))
        dir_data_path = self.getDirPath(dir_data.get('dir_name'), True)

        # Проверка на существование директории
        if os.path.isdir(dir_path):
            self.printInfo(
                title='Уведомление', text=f'Директория {dir_data.get("dir_name")} уже существует!')
            return False

        # Создаём директорию
        try:
            os.mkdir(dir_path)
            # Создаём .dirData.json
            self.writeJson(dir_data_path, dir_data)
            return True
        except Exception as e:
            self.printInfo(title='Ошибка!',
                           text=f'Не удалось создать директорию.\n{e}')
            return False

    def editDir(self, dir_data_old: dict, dir_data_new: dict) -> bool:
        '''
        Редактирует директорию
        '''
        dir_name_old = dir_data_old.get('dir_name')
        dir_name_new = dir_data_new.get('dir_name')
        dir_path_old = self.getDirPath(dir_name_old)
        dir_path_new = self.getDirPath(dir_name_new)

        # Если изменилось название директории

        if dir_path_old != dir_path_new:
            try:
                os.rename(dir_path_old, dir_path_new)

            except Exception as e:
                self.printInfo(
                    title='Предупреждение',
                    text=f'''Не удалось переименовать {dir_data_old.get("dir_name")} в {dir_data_new.get("dir_name")}.
                    \nПеред переименованием необходимо закрыть все файлы, если таковые имеются.
                    \n{e}''')
                return

            # Заменяем имя директории во всех вложенных заявках
            task_list = self.readWorkDir(dir_name_new)[dir_name_new].copy()
            for task_path in task_list:
                task_number = task_path.split('_(', 1)[0]
                task_data_path = self.getTaskPath(
                    dir_name_new, task_number, get_task_data_path=True)
                task_data = self.readJson(task_data_path)
                task_data['dir_name'] = dir_name_new
                self.writeJson(task_data_path, task_data)

        # Перезаписываем .dirData.json
        dir_data_path = self.getDirPath(dir_name_new, True)
        self.writeJson(dir_data_path, dir_data_new)

        # Добавляем в таблицу
        self.putDir2Tab(dir_data_new, dir_data_old)

    def putDir2Tab(self, dir_data: dict, dir_data_old: dict = False):
        '''
        Создаёт таблицу с названием директории и с заданными столбцами
        '''
        # Заполняем названия колонок
        labels = []
        if dir_data.get('task_number'):
            labels.append('№ Заявки')
        if dir_data.get('description'):
            labels.append('Описание')
        if dir_data.get('date_end'):
            labels.append('План. срок')
        if dir_data.get('deadline'):
            labels.append('Конечный. срок')
        if dir_data.get('my_plane_labor_costs'):
            labels.append('План. ТЗ')
        if dir_data.get('labor_costs'):
            labels.append('Тек. ТЗ')
        if dir_data.get('all_labor_costs'):
            labels.append('Все ТЗ')
        if dir_data.get('plane_labor_costs'):
            labels.append('Общ. план. ТЗ')

        # Если мы создаём новую таблицу
        if not dir_data_old:
            # Создаём таблицу
            table = QTableWidget(0, len(labels))
            # Запрещаем редактирование
            table.setEditTriggers(
                QAbstractItemView.EditTrigger.NoEditTriggers)
            # Задаём названия колонок
            table.setHorizontalHeaderLabels(labels)
            # Добавялем обработку сигнала выделения ячейки
            table.currentItemChanged.connect(self.changedTask)
            # Выделение всей строки одновременно
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            # Добавляем таблицу
            self.ui.taskManagerTab.addTab(table, dir_data.get('dir_name'))
        else:
            # Иначе изменяем таблицу и данные в ней
            tab_index = self.getIndexTabByName(dir_data_old.get('dir_name'))
            self.ui.taskManagerTab.setTabText(
                tab_index, dir_data.get('dir_name'))
            self.ui.taskManagerTab.widget(
                tab_index).setColumnCount(len(labels))
            self.ui.taskManagerTab.widget(
                tab_index).setHorizontalHeaderLabels(labels)
            self.fillTaskManagerTab(dir_data.get('dir_name'))

    def removeDir(self):
        '''
        Удаляет директорию
        '''
        current_tab_index = self.ui.taskManagerTab.currentIndex()

        if current_tab_index == -1:
            self.printInfo('Уведомление', 'Не выбрана директория')
            return

        dir_name = self.ui.taskManagerTab.tabText(current_tab_index)

        # Вопрос об удалении директории
        answer = QMessageBox.question(self, 'Предупреждение',
                                      f'Перед удалением директории: "{dir_name}", убедитесь, что все файлы закрыты.\nПродолжить?',
                                      QMessageBox.StandardButton.Yes,
                                      QMessageBox.StandardButton.No
                                      )
        if answer == QMessageBox.StandardButton.No:
            return

        # Рекурсивно удаляем директорию
        dir_path = self.getDirPath(dir_name)

        if os.path.isdir(dir_path):
            shutil.rmtree(dir_path)

            self.ui.taskManagerTab.removeTab(current_tab_index)

        else:
            self.printInfo(title='Уведомление',
                           text=f'Директория: {dir_name} не найдена')

    def openDirWindow(self, dir_data_old: dict = False):
        '''
        Открывает окно с параметрами директории
        '''
        self.dir_window = QDialog()
        self.ui_dir = Ui_Dir()
        self.ui_dir.setupUi(self.dir_window)
        confirmed = False

        if dir_data_old:
            dir_data_new = dir_data_old.copy()
            # Заполняем форму
            self.ui_dir.dir_name.setText(dir_data_old.get('dir_name'))
            self.ui_dir.date_end.setChecked(bool(dir_data_old.get('date_end')))
            self.ui_dir.deadline.setChecked(bool(dir_data_old.get('deadline')))
            self.ui_dir.my_plane_labor_costs.setChecked(
                bool(dir_data_old.get('my_plane_labor_costs')))
            self.ui_dir.labor_costs.setChecked(
                bool(dir_data_old.get('labor_costs')))
            self.ui_dir.all_labor_costs.setChecked(bool(
                dir_data_old.get('all_labor_costs')))
            self.ui_dir.plane_labor_costs.setChecked(bool(
                dir_data_old.get('plane_labor_costs')))
        else:
            dir_data_new = {}

        while True:
            self.dir_window.exec()
            # Нажата кнопка отмена
            if self.dir_window.result() == 0:
                break
            # Проверяем входные данные
            if self.checkDirData(dir_data_old):
                confirmed = True
                break

        if confirmed:
            # Заполняем данные
            dir_data_new['dir_name'] = self.ui_dir.dir_name.text().strip()
            dir_data_new['task_number'] = True
            dir_data_new['description'] = True
            dir_data_new['date_end'] = self.ui_dir.date_end.isChecked()
            dir_data_new['deadline'] = self.ui_dir.deadline.isChecked()
            dir_data_new['my_plane_labor_costs'] = self.ui_dir.my_plane_labor_costs.isChecked(
            )
            dir_data_new['labor_costs'] = self.ui_dir.labor_costs.isChecked()
            dir_data_new['all_labor_costs'] = self.ui_dir.all_labor_costs.isChecked()
            dir_data_new['plane_labor_costs'] = self.ui_dir.plane_labor_costs.isChecked()

            # Редактируем директорию или создаём новую
            confirmed = False
            if dir_data_old:
                confirmed = self.editDir(dir_data_old, dir_data_new)
            else:
                confirmed = self.createDir(dir_data_new)

            # Добавляем директорию в таблицу
            if confirmed:
                self.putDir2Tab(dir_data_new)

    def checkDirData(self, dir_data_old: dict = False) -> bool:
        '''
        Проверяет правильность введённых данных
        '''
        dir_name = self.ui_dir.dir_name.text()

        if dir_name.strip() == '':
            self.printInfo('Предупреждение',
                           'Название директории не может быть пустым')
            return False

        symbols = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        for symbol in symbols:
            if symbol in dir_name:
                self.printInfo(
                    'Предупреждение', f'Название директории не может содержать символы\n{" ".join(symbols)}')
                return False

        # Проверка на существование директории
        dir_path = self.getDirPath(dir_name)

        # Проверяем наличие директории с введённым именем в случае создания новой
        # директории или при изменении имени старой
        if (not dir_data_old and os.path.isdir(dir_path)) or (
                dir_data_old and dir_data_old.get('dir_name') != dir_name and os.path.isdir(dir_path)):
            self.printInfo(
                title='Уведомление', text=f'Директория {dir_name} уже существует!')
            return False

        return True

    def getDirList(self) -> list:
        '''
        Возвращает список директорий в таблице
        '''
        dir_list = []

        # Получаем количество вкладок и проходимся по всем названиям
        count_tabs = self.ui.taskManagerTab.count()
        for index in range(count_tabs):
            dir_list.append(self.ui.taskManagerTab.tabText(index))

        return dir_list
########################
# Работа с заявкой
########################

    def isThereTask(self, dir_name: str, task_number: str) -> bool:
        '''
        Возвращает True Если существует папка с заявкой
        '''
        dir_path = self.getDirPath(dir_name)

        for task_path in os.listdir(dir_path):
            if task_path.split('_(')[0] == task_number:
                return True

        return False

    def findColorByName(self, name) -> str:
        '''
        Возвращает цвет по имени
        '''
        color = ''
        color_dict = {}
        color_dict = self.settings.get('colors')
        if color_dict:
            color = color_dict.get(name)

        # Если не нашли или длина меньше или больше 7 или текст не начинается с символа #, то возвращаем белый
        if not color or len(str(color)) != 7 or color[0] != '#':
            color = '#ffffff'

        return color

    def findNameByColor(self, color) -> str:
        '''
        Возвращает имя по цвету
        '''
        color_dict = {}
        color_dict = self.settings.get('colors')
        name_color = None
        if color_dict:
            for name in color_dict.keys():
                if color_dict[name] == color:
                    name_color = name
                    break
        return name_color

    def selectedRow(self) -> int:
        '''Возвращает номер выбранной строки'''
        return self.ui.taskManagerTab.currentWidget().selectionModel().currentIndex().row()

    def changedTask(self):
        '''Действия при выделении заявки'''
        self.updateTaskLinksMenu()

    def updateTaskLinksMenu(self):
        '''Обновляет меню ссылок для заявки'''
        self.task_links_menu.clear()

        if self.selectedRow() == -1:
            return
        current_task_data = self.getCurrentTaskData()
        if current_task_data is None:
            return

        # Берём ссылки из заявки
        links = current_task_data.get('links')
        if not links:
            return

        for link_name in links:
            action = QAction(link_name, self)
            action.triggered.connect(self.openLinkFromMenu)
            self.task_links_menu.addAction(action)

    def openLink(self, link: str):
        '''Открывает передаваемые ссылки'''

        # Проверка ссылок
        if link.startswith('http'):
            webbrowser.open(link)
        elif os.path.isdir(link):
            os.startfile(link)
        else:
            self.printInfo(title='Предупреждение',
                           text=f'Не удаётся открыть ссылку: {link}')

    def openLinkFromMenu(self):
        '''Открываем выбранную ссылку'''
        # Получаем имя ссылки
        sender = self.sender()
        link_name = sender.text()

        # Получем ссылку из задачи
        current_task_data = self.getCurrentTaskData()
        dict_links = current_task_data.get('links')
        link = dict_links.get(link_name)
        self.openLink(link=link)

    def getTaskPath(self, dir_name: str, task_number: str, description: str = None, get_task_data_path: bool = False) -> str:
        '''
        Возвращает путь до заявки или до taskData.json
        '''
        path = None
        dir_path = self.getDirPath(dir_name)

        # Если есть описание то объединяем или ищем в директории
        if description:
            task_dir_name = task_number + self.shortDescription(description)
            # Если нужен путь до данных
            if get_task_data_path:
                path = self.createPath(self.createPath(
                    dir_path, task_dir_name), '.taskData.json')
            else:
                path = self.createPath(dir_path, task_dir_name)
        else:
            # Ищем путь до заявки по номеру
            for task_dir_name in os.listdir(dir_path):
                # Разделяем наименование на две части: номер заявки и описание
                part = task_dir_name.split('_(', 1)[0]
                # Если нашли
                if part == task_number:
                    # Если нужен путь до данных
                    if get_task_data_path:
                        path = self.createPath(self.createPath(
                            dir_path, task_dir_name), '.taskData.json')
                        break
                    else:
                        path = self.createPath(dir_path, task_dir_name)
                        break
            if path == None:
                if get_task_data_path:
                    self.printInfo(
                        'Ошибка!', f'Не удалось получить путь до заявки:{task_number}')
                else:
                    self.printInfo(
                        'Ошибка!', f'Не удалось получить путь до данных заявки:{task_number}')

        return path

    def createTaskPath(self, dir_name: str, task_name_full: str, get_task_data_path: bool = False) -> str:
        '''
        Создаёт путь для заявки или до taskData.json
        '''
        dir_path = self.getDirPath(dir_name)

        if get_task_data_path:
            path = os.path.join(dir_path, task_name_full, '.taskData.json')
        else:
            path = os.path.join(dir_path, task_name_full)

        return path

    def getTaskData(self, dir_name, task_number):
        '''
        Возвращает информацию по заявке
        '''
        return self.readJson(self.getTaskPath(dir_name, task_number, get_task_data_path=True))

    def getCurrentTaskData(self) -> dict:
        '''
        Возвращает информацию по текущей заявке
        '''
        tab_index = self.ui.taskManagerTab.currentIndex()
        if tab_index == -1:
            self.printInfo('Уведомление', 'Не выбрана директория')
            return None
        dir_name = self.ui.taskManagerTab.tabText(tab_index)
        row = self.selectedRow()
        if row == -1:
            self.printInfo('Уведомление', 'Необходимо выбрать заявку')
            return None
        task_number = self.ui.taskManagerTab.currentWidget().item(row, 0).text()

        return self.getTaskData(dir_name, task_number)

    def putTask2Tab(self, task_data: dict, task_data_old: dict = False) -> bool:
        '''
        Добавляет или изменяет заявку в таблице
        '''

        # Получаем информацию в какой таблице и под каким номером всталять запись
        dir_name = task_data.get('dir_name')

        tab_index = self.getIndexTabByName(dir_name)
        if tab_index == None:
            self.printInfo(
                'Уведомление', f'Не удалось найти таблицу "{dir_name}" и добавить заявку "{task_data.get("task_number")}"')
            return

        # Если не редактируем заявку
        if not task_data_old:
            # Проверяем статус
            # Смотрим какие заявки надо отображать Не скрытые, Скрытые, Все
            status_text = self.ui.task_status.currentText()
            if (not task_data.get('hidden') and status_text == 'Скрытые') or (
                    task_data.get('hidden') and status_text == 'Не скрытые'):
                return

            # Получаем номер новой строки
            row = self.ui.taskManagerTab.widget(tab_index).rowCount()
            self.ui.taskManagerTab.widget(tab_index).insertRow(row)

            # Вставляем строки в зависимости от настроек полей директории
            column = 0
            dir_data = self.getDirData(task_data.get('dir_name'))
            color = task_data.get('color')
            found_color_name = bool(self.findNameByColor(color))

            for column_name in dir_data.keys():
                if column_name == 'dir_name':
                    continue

                if dir_data.get(column_name):
                    content = task_data.get(column_name)
                    if content != None:
                        item = QTableWidgetItem(str(content))
                    else:
                        item = QTableWidgetItem(str(''))

                    # Смотрим какие заявки надо отображать Не скрытые, Скрытые, Все
                    status_text = self.ui.task_status.currentText()
                    # Проверка статуса и добавление в таблицу
                    if task_data.get('hidden') and status_text == 'Скрытые' or status_text == 'Все':
                        self.ui.taskManagerTab.widget(tab_index).setItem(
                            row, column, item)
                    elif not task_data.get('hidden') and status_text == 'Не скрытые':
                        self.ui.taskManagerTab.widget(tab_index).setItem(
                            row, column, item)

                    if color and found_color_name:
                        # Устанавливаем цвет
                        item.setBackground(QColor(color))
                    column += 1
        else:
            # Обновляем таблицу
            self.fillTaskManagerTab(dir_name)
            dir_name_old = task_data_old.get('dir_name')
            # Если поменялась директория, то обновляем и её
            if dir_name_old != dir_name:
                self.fillTaskManagerTab(dir_name_old)

    def shortDescription(self, description: str) -> str:
        '''
        Возвращает сокращённое описание для наименования папок с заявками
        '''
        if type(description) != str:
            description = ''

        # Если описание больше 50 символов, то берём только первые 50
        if len(description) > 50:
            description = description[0:49]
            description += '...'
        # Оборачиваем в специальную конструкцию
        description = '_(' + description + ')'

        return description

    def createTask(self, task_data: dict) -> bool:
        '''
        Создаёт заявку
        '''
        dir_name = task_data.get('dir_name')
        task_number = task_data.get('task_number')

        # Создаём суфикс из описания
        description = self.shortDescription(task_data.get('description'))

        # Получаем необходимые пути к файлам и папкам
        template_path = self.createPath(self.getDirPath(
            dir_name), self.settings.get('template_name'))

        # Добавляем описание к номеру заявки
        task_path = task_number + description
        task_dir_name = self.createPath(self.getDirPath(dir_name), task_path)
        task_data_path = self.createPath(task_dir_name, '.taskData.json')

        try:
            if task_data.get('by_template'):
                # Создаём заявку по шаблону
                if not os.path.isdir(template_path):
                    self.printInfo(title='Уведомление',
                                   text=f'''Не найдена шаблонная директория.
                                   \nСоздайте в директории папку с названием {self.settings.get("template_name")}.
                                   \nВы можете задать своё название шаблонной директории в настройках программы
                                   ''')
                    return

                shutil.copytree(
                    template_path, task_dir_name)
            else:
                # Создаём директорию
                os.mkdir(task_dir_name)

            # Создаём файл с информацией по заявке
            self.writeJson(file_path=task_data_path, data=task_data)

        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось создать заявку.\n{e}')
            return False

        return True

    def editTask(self, task_data_old: dict, task_data_new: dict):
        '''
        Редактирует заявку
        '''

        task_number_old = task_data_old.get('task_number')
        task_number_new = task_data_new.get('task_number')
        dir_name_old = task_data_old.get('dir_name')
        dir_name_new = task_data_new.get('dir_name')
        description_new = task_data_new.get('description')
        description_new_short = self.shortDescription(description_new)
        task_number_path_old = self.getTaskPath(dir_name_old, task_number_old)
        task_number_path_new = self.createTaskPath(
            dir_name_new, task_number_new + description_new_short)

        # Если переименовали заявку
        if task_number_path_old != task_number_path_new:
            try:
                os.rename(task_number_path_old, task_number_path_new)

            except Exception as e:
                self.printInfo(
                    title='Предупреждение',
                    text=f'''Не удалось переименовать {task_number_path_old} в {task_number_path_new}.
                    \nПеред переименованием необходимо закрыть все файлы, если таковые имеются.
                    \n{e}''')
                return

        # Перезаписываем .taskData.json
        task_data_path = self.getTaskPath(
            dir_name_new, task_number_new, description_new, True)
        self.writeJson(task_data_path, task_data_new)

        self.putTask2Tab(task_data_new, task_data_old)

    def removeTask(self):
        '''
        Удаляет заявку
        '''
        tab_index = self.ui.taskManagerTab.currentIndex()
        dir_name = self.ui.taskManagerTab.tabText(tab_index)
        row = self.ui.taskManagerTab.widget(
            tab_index).selectionModel().currentIndex().row()
        # Если строка не выбрана
        if row == -1:
            self.printInfo('Уведомление', 'Сначала выберите заявку')
            return

        # Вопрос, подтверждающий удаление
        task_number = self.ui.taskManagerTab.widget(
            tab_index).item(row, 0).text()
        answer = QMessageBox.question(self, 'Предупреждение',
                                      f'Перед удалением заявки: "{task_number}", убедитесь, что все файлы закрыты.\nПродолжить?',
                                      QMessageBox.StandardButton.Yes,
                                      QMessageBox.StandardButton.No
                                      )
        if answer == QMessageBox.StandardButton.No:
            return

        # Рекурсивно удаляем директорию
        task_path = self.getTaskPath(dir_name, task_number)
        try:
            shutil.rmtree(task_path)
            self.delTask4Tab(tab_index, row)
        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось удалить заявку.\n{e}')
            return

    def delTask4Tab(self, tab_index, row):
        '''
        Убирает заявку из таблицы
        '''
        self.ui.taskManagerTab.widget(tab_index).removeRow(row)

    def openTaskWindow(self, task_data_old: dict = False):
        '''
        Открывает окно с параметрами заявки
        '''

        self.task_window = QDialog(parent=self)
        self.ui_task = Ui_Task()
        self.ui_task.setupUi(self.task_window)

        # Кнопки создания заявки
        self.ui_task.addLinksBtn.clicked.connect(self.handler)
        self.ui_task.delLinksBtn.clicked.connect(self.handler)

        confirmed = False

        # Получаем список директорий и заполняем выпадающий список
        dir_list = []
        dir_list = self.getDirList()

        # Если не создано ни одной директории
        if dir_list == []:
            self.printInfo(
                'Уведомление', 'Для начала необходимо создать директорию')
            return
        self.ui_task.dir_name.addItems(dir_list)

        # Получаем цвета из настроек и заполняем список
        color_dict = self.settings.get('colors')
        color_list = []
        if color_dict:
            color_list = color_dict.keys()
        # Если есть цвета иначе ставим белый
        if color_list:
            self.ui_task.color.addItems(color_list)
        else:
            self.ui_task.color.addItem('Белый')

        # Устанавливаем директорию в которой находится пользователь
        index_current_dir = self.ui.taskManagerTab.currentIndex()
        self.ui_task.dir_name.setCurrentText(
            self.ui.taskManagerTab.tabText(index_current_dir))

        # Установка текущей даты и формата
        date = dt.datetime.today()
        self.ui_task.date_end.setDate(
            QDate(date.year, date.month, date.day))
        self.ui_task.date_end.setDisplayFormat('dd.MM.yyyy')

        # Заполняем окно данными, если имеются
        if task_data_old:
            # Переносим старые данные
            task_data_new = task_data_old.copy()

            # Поиск директории в выпадающем списке
            dir_index = self.ui_task.dir_name.findText(
                task_data_old.get('dir_name'))
            if dir_index == -1:
                self.printInfo(
                    'Уведомление', f'Не найдена директория {task_data_old.get("dir_name")}')
            self.ui_task.dir_name.setCurrentIndex(dir_index)

            self.ui_task.task_number.setText(task_data_old.get('task_number'))
            self.ui_task.description.setText(
                task_data_old.get('description'))
            # Парсим дату
            date = dt.datetime.strptime(
                task_data_old.get('date_end'), '%d.%m.%Y')
            self.ui_task.date_end.setDate(
                QDate(date.year, date.month, date.day))
            self.ui_task.my_plane_labor_costs.setValue(
                task_data_old.get('my_plane_labor_costs'))

            self.ui_task.by_template.setChecked(bool(
                task_data_old.get('by_template')))

            # Заполняем таблицу ссылок
            links_dict = {}
            links_dict = task_data_old.get('links')
            if links_dict:
                # Устанавливаем растяжение для стоблцов таблицы
                self.ui_task.tabLinks.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
                self.ui_task.tabLinks.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
                # Записываем данные
                row = 0
                for name_link in links_dict:
                    self.ui_task.tabLinks.insertRow(row)
                    self.ui_task.tabLinks.setItem(
                        row, 0, QTableWidgetItem(name_link))
                    self.ui_task.tabLinks.setItem(
                        row, 1, QTableWidgetItem(links_dict.get(name_link)))
                    row += 1

            # Ищем цвет в настройках
            color_name = self.findNameByColor(task_data_old.get('color'))
            color_index = -1
            if color_name:
                # Ищем цвет в выпадающем списке
                color_index = self.ui_task.color.findText(color_name)

            # Если найден цвет
            if color_index > -1:
                self.ui_task.color.setCurrentIndex(color_index)
            else:
                # Инчае ставим белый
                self.ui_task.color.setCurrentText('Белый')

            # Задаём состояние заявки
            self.ui_task.hidden.setChecked(bool(task_data_old.get('hidden')))

            self.ui_task.date_create_local.setText(
                task_data_old.get('date_create_local'))

            # При редактировании отключаем возможность выбрать элементы
            self.ui_task.by_template.setDisabled(True)
        else:
            task_data_new = {}

            date_create_local = dt.datetime.today().strftime('%d.%m.%Y')
            # Дата локального создания
            self.ui_task.date_create_local.setText(date_create_local)

        # Запускаем окно
        while True:
            self.task_window.exec()
            # Нажата кнопка отмена
            if self.task_window.result() == 0:
                break
            # Проверяем входные данные
            if self.checkTaskData(task_data_old):
                confirmed = True
                break

        if confirmed:
            # Заполняем данные заявки
            task_data_new['task_number'] = self.ui_task.task_number.text()
            task_data_new['dir_name'] = self.ui_task.dir_name.currentText()
            # Записываем описание и заменяем символ " на '
            task_data_new['description'] = self.ui_task.description.text().replace(
                '"', "'")
            task_data_new['date_end'] = self.ui_task.date_end.text()
            task_data_new['my_plane_labor_costs'] = self.ui_task.my_plane_labor_costs.value(
            )
            task_data_new['by_template'] = self.ui_task.by_template.isChecked()

            # Получаем словарь ссылок и заполняем данные
            links_dict = {}
            for row in range(0, self.ui_task.tabLinks.rowCount()):
                # Получаем название и ссылку и убираем пустые символы по бокам
                name_link = QTableWidgetItem(
                    self.ui_task.tabLinks.item(row, 0)).text().strip()
                link = QTableWidgetItem(
                    self.ui_task.tabLinks.item(row, 1)).text().strip()
                # Если заполнено наименование и ссылка
                if name_link and link:
                    links_dict[name_link] = link
            task_data_new['links'] = links_dict

            task_data_new['color'] = self.findColorByName(
                self.ui_task.color.currentText())

            task_data_new['hidden'] = self.ui_task.hidden.isChecked()
            task_data_new['date_create_local'] = self.ui_task.date_create_local.text()

            confirmed = False
            if task_data_old:
                # Редактируем заявку
                confirmed = self.editTask(task_data_old, task_data_new)
            else:
                # Создаём заявку
                confirmed = self.createTask(task_data_new)

            if confirmed:
                self.putTask2Tab(task_data_new)

    def checkTaskData(self, task_data_old: dict = False) -> bool:
        '''
        Проверяет заполненные данные по заявке
        '''
        dir_name = self.ui_task.dir_name.currentText()
        task_number = self.ui_task.task_number.text().strip()
        description = self.ui_task.description.text().strip()
        description_short = self.shortDescription(description)

        task_path = self.createTaskPath(
            dir_name, task_number+description_short)

        # Проверка на зарезервированные символы
        symbols = ['\\', '/', ':', '*', '?', '<', '>', '|', '_(']
        for symbol in symbols:
            if symbol in task_number + description:
                text_error = "'" + "',  '".join(str(element)
                                                for element in symbols) + "'"

                self.printInfo(
                    'Предупреждение', f'Название заявки не может содержать символы\n{text_error}')
                return False

        if task_data_old:
            dir_name_old = task_data_old.get('dir_name')
            task_number_old = task_data_old.get('task_number')
            task_path_old = self.getTaskPath(dir_name_old, task_number_old)

        if task_number == '':
            self.printInfo(title='Предупреждение',
                           text='Номер заявки не может быть пустым!')
            return False

        # Если заявка существует или при редактировании указали имя существующей заявки

        if (  # Если нету старых данных (не редактирование)
            not task_data_old
            and self.isThereTask(dir_name, task_number)) or (
            # Если есть старые данные, меняется название папки и уже есть такая папка или такая заявка
            task_data_old and
            task_path_old != task_path and
            (os.path.isdir(task_path) or
             task_number_old != task_number and
             self.isThereTask(dir_name, task_number))
        ):
            self.printInfo(
                title='Уведомление', text=f'Заявка: {task_number} или директория {task_path} уже существует!')
            return False

        return True

    def moveTask2Arch(self, dir_name, task_number):
        '''
        Переносит заявку в архив
        '''
        task_data = self.getTaskData(dir_name, task_number)
        if not task_data:
            return

        answer = QMessageBox.question(self, 'Предупреждение',
                                      f'Перед переносом заявки: "{task_number}", убедитесь, что все файлы закрыты.\nПродолжить?',
                                      QMessageBox.StandardButton.Yes,
                                      QMessageBox.StandardButton.No
                                      )
        if answer == QMessageBox.StandardButton.No:
            return

        try:
            arch_path = self.createPath(self.settings.get(
                'work_dir'), self.settings.get('archive_name'))

            # Если нету папки с архивом
            if not os.path.isdir(arch_path):
                os.mkdir(arch_path)

            # Получаем текущий месяц для создания подпапок
            current_month = dt.datetime.now().strftime('%Y_%m')
            arch_path_current_month = os.path.join(arch_path, current_month)

            # Если в архиве нету папки с текущим месяцом
            if not os.path.isdir(arch_path_current_month):
                os.mkdir(arch_path_current_month)

            task_path = self.getTaskPath(task_data.get(
                'dir_name'), task_data.get('task_number'))

            # Переносим задачу в архив в нужный месяц
            shutil.move(task_path, arch_path_current_month)

        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось перенести заявку.\n{e}')
            return

        # Обновляем таблицу
        self.fillTaskManagerTab(dir_name)


########################
# Работа с хранилищем
########################


    def openStorageWindow(self, storage_data_old: dict = False):
        '''
        Открывает окно с параметрами обновления хранилища
        '''
        self.storage_window = QDialog(parent=self)
        self.ui_storage = Ui_Storage()
        self.ui_storage.setupUi(self.storage_window)
        confirmed = False

        # Соединяем сигналы кнопок с обработчиком
        self.ui_storage.patchBtn.clicked.connect(self.storageHandler)

        # Получаем данные выделенной заявки
        task_data = self.getCurrentTaskData()
        if not task_data:
            return

        # Заполняем входными данными если имеются
        if storage_data_old:
            pass
        else:
            # Ищем путь до patch.pck
            pass

        while True:
            self.storage_window.exec()
            # Нажата кнопка отмена
            if self.storage_window.result() == 0:
                break
            # Проверяем входные данные
            if self.checkStorageData(storage_data_old):
                confirmed = True
                break

    def storageHandler(self):
        '''
        Обрабатывает запросы от окна с хранилищем
        '''
        # Получаем путь выбранной заявки
        task_data = self.getCurrentTaskData()
        task_path = self.getTaskPath(task_data.get(
            'dir_name'), task_data.get('task_number'))

        dialog = QFileDialog(parent=self, directory=task_path)
        dialogSuccesful = dialog.exec()

        if dialogSuccesful:
            selectedFiles = dialog.selectedFiles()
            if selectedFiles:
                self.ui_storage.patchPath.setText(selectedFiles[0])

    def checkStorageData(self, storage_data: dict) -> bool:
        '''
        Проверяет данные хранилища
        '''
        return True

    def findPatchPckFile(self, path) -> str:
        '''
        Ищет путь до patch.pck в переданной директории
        '''
        path = None

        return path
###########################################################
###########################################################
# Модуль "Активные заявки"
###########################################################

    def fillActiveTaskTab(self):
        '''
        Заполняет таблицу на основании запроса по активным заявкам
        '''

    def getActiveTasks(self) -> list:
        '''Получает информацию по активным заявкам'''
        user_name = self.settings.get('user_name')

        if not user_name:
            self.printInfo(
                'Предупреждение', 'Не задано имя пользовалтеля. Укажите его в настройках')
            return

        list_active_tasks = self.db_con.getActiveTasks(user_name)

        if not list_active_tasks:
            return


###########################################################
###########################################################
# Модуль "Котёл"
###########################################################


    def fillPowTab(self):
        '''
        Заполняет таблицу на основании запроса по заявкам в котле
        '''

    def getPow(self) -> list:
        '''Возвращает котёл с заявками'''


############################################################
# Запуск в окне
############################################################
if __name__ == '__main__':
    app = QApplication()

    window = TaskManager()
    window.show()
    sys.exit(app.exec())
