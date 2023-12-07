import os
import sys
import json

from ui_taskmanager import *
from ui_task import *
from ui_dir import *

from PySide6.QtWidgets import (
    QMessageBox, QTableWidget, QAbstractItemView, QHeaderView, QMenu)
from PySide6.QtGui import (QAction, QColor)
from PySide6 import QtGui


class TaskManager(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Чтение настроек
        self.readSettingsApp()

        # Скрываем лишние окна
        self.ui.leftMenu.hide()
        self.ui.notificationContent.hide()

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
            'explorer': 'explorer',
            'color_range': {'min': 5, 'max': 25},
            'task_manager_columns': [['№ заявки', True],
                                     ['Описание', True],
                                     ['Срок', True],
                                     ['Конечный срок', True],
                                     ['ТЗ', True],
                                     ['Все ТЗ', True],
                                     ['Плановые ТЗ', True]],
            'active_task_columns': {
                'support': [],
                'project': [],
                'other': [],
                'code_review': []
            },
            'pot_columns': {
                'code_review': [],
                'support': [],
                'project': []
            }
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

        # Модульные кнопки
        # TODO

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

    def handler(self):
        '''
        Обработчик нажатий клавиш
        '''
        sender = self.sender()

        match sender.objectName():
            # Основные кнопки
            case 'menuBtn':
                self.showLeftMenu(0)
            case 'settingsBtn':
                self.showLeftMenu(1)
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

            # Модульные кнопки
            # TODO

            # Прочее
            case _:
                print('Неизвестное нажатие')

    def initMTaskManager(self):
        '''
        Инициализирует модуль "Ведение задач"
        '''
        self.fillTaskManagerTab()

    def initMActiveTask(self):
        '''
        Инициализирует модуль "Активные задачи"
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
            case _:
                print(f'Не известный модуль: {current_module}')

        # Задаём полученные меню для кнопок
        self.ui.actionBtn.setMenu(self.btns_menu.get('action'))
        self.ui.addBtn.setMenu(self.btns_menu.get('add'))
        self.ui.removeBtn.setMenu(self.btns_menu.get('remove'))
        self.ui.editBtn.setMenu(self.btns_menu.get('edit'))

    def getTaskManagerBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Ведение задач" 
        '''

        # Меню действие
        # TODO
        # Меню добавить
        btns_menu['add'].addAction('Создать директорию', self.openDirWindow)
        btns_menu['add'].addAction('Создать задачу', self.openTaskWindow)
        # Меню убрать
        btns_menu['remove'].addAction('Удалить текущую директорию', self.removeDir)
        btns_menu['remove'].addAction('Убрать выбранную задачу', self.removeTask)
        # Меню изменить
        btns_menu['edit'].addAction('Редактировать текущую директорию', self.editDir)
        btns_menu['edit'].addAction('Редактировать выбранную задачу', self.editTask)

        return btns_menu

    def getAcitveTaskBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Ведение задач" 
        '''
        # TODO
        # Меню действие
        # Меню добавить
        # Меню убрать
        # Меню изменить

        return btns_menu

    def getPotBtnsMenu(self, btns_menu: dict) -> dict:
        '''
        Задаёт кнопкам меню модуля "Ведение задач" 
        '''
        # TODO
        # Меню действие
        # Меню добавить
        # Меню убрать
        # Меню изменить

        return btns_menu


###########################################################
###########################################################
# Модуль "Ведение задач"
###########################################################

    def fillTaskManagerTab(self):
        '''
        Заполняет таблицу на основании рабочей директории
        '''
        tab_index = 0
        # Получаем список директорий и задач
        dir_list = self.readWorkDir()

        # Читаем словарь с папками в рабочей директории и заполняем таблицу
        for dir_name in dir_list.keys():

            # Получаем информацию по директории и создаём таблицу
            dir_data = self.getDirData(dir_name)
            self.createDir2Tab(dir_data)

            for task_number in dir_list[dir_name]:
                # Исключаем папки
                if task_number in (self.settings.get('template_name'), self.settings.get('archive_name')):
                    continue

                # Получаем файл с информацией по задаче
                task_data_path = self.getTaskPath(dir_name, task_number, True)
                # Проверяем что в папке есть файл с настройками
                if not os.path.isfile(task_data_path):
                    continue

    def readWorkDir(self) -> dict:
        '''
        Читает рабочую директорию, создаёт словарь директория-задачи
        '''
        dir_task_list = {}
        for dir_name in os.listdir(self.settings.get('work_dir')):
            # Записываем название директории в которую помещяем список задач
            dir_task_list[dir_name] = os.listdir(
                self.getDirPath(dir_name))
        return dir_task_list

########################
# Работа с директорией
########################

    def getDirPath(self, dir_name: str, get_dir_data_path: bool = False) -> str:
        '''
        Возвращает полный путь до рабочей директории
        '''
        if get_dir_data_path:
            path = os.path.join(self.getDirPath(dir_name), '.dirData.json')
        else:
            path = os.path.join(self.settings.get('work_dir'), dir_name)
        return path
    
    def getDirData(self,dir_name) -> dict:
        '''
        Возвращает информацию по директории
        '''
        dir_data_path = self.getDirPath(dir_name,True)
        # Проверяем есть файл с настройками
        if not os.path.isfile(dir_data_path):
            self.printInfo('Ошибка!',f'В папке {dir_name}, не найден настроечный файл .dirData.json')
            return None
        
        return self.readJson(dir_data_path)


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

    def editDir(self):
        '''
        Редактирует директорию
        '''

    def createDir2Tab(self, dir_data: dict):
        '''
        Создаёт таблицу с названием директории и с заданными столбцами
        '''
        # Заполняем названия колонок
        labels = []
        if dir_data.get('task_number'):
            labels.append('№ Задачи')
        if dir_data.get('description'):
            labels.append('Описание')
        if dir_data.get('period'):
            labels.append('Срок до')
        if dir_data.get('deadline'):
            labels.append('Конечный срок')
        if dir_data.get('labor_costs'):
            labels.append('ТЗ')
        if dir_data.get('all_labor_costs'):
            labels.append('Все ТЗ')
        if dir_data.get('plane_labor_costs'):
            labels.append('Плановы ТЗ')

        # Создаём таблицу
        table = QTableWidget(0, len(labels))
        # Запрещаем редактирование
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)

        table.setHorizontalHeaderLabels(labels)
        self.ui.taskManagerTab.addTab(table, dir_data.get('dir_name'))

    def editDir2Tab(self, dir_data: dict):
        '''
        Редактирует таблицу
        '''

    def setDir(self, dir_data: dict):
        '''
        Добавляет или изменяет директорию
        '''
        found_name_in_tab = bool(self.ui.taskManagerTab.findChild(
            QWidget, dir_data.get('dir_name')))

        if not found_name_in_tab:
            if self.createDir(dir_data):
                self.createDir2Tab(dir_data)
        else:
            if self.editDir(dir_data):
                self.edi

    def removeDir(self):
        '''
        Удаляет директорию
        '''

    def openDirWindow(self, dir_data: dict = False):
        '''
        Открывает окно с параметрами директории
        '''
        self.dir_window = QDialog()
        # self.dir_window.setModal(True)
        self.ui_dir = Ui_Dir()
        self.ui_dir.setupUi(self.dir_window)
        confirmed = False

        sender_name = self.sender.text()
        # Если редактируется, то получаем данные текущей таблицы
        if sender_name == 'Редактировать текущую директорию':
            tab_index = self.ui.taskManagerTab.currentIndex()
            current_dir_name = self.ui.taskManagerTab.tabText(tab_index)
            dir_data = self.getDirData(current_dir_name)

        if dir_data:
            # Заполняем форму
            self.ui_dir.dir_name.setText(dir_data.get('dir_name'))
            self.ui_dir.period.setTristate(dir_data.get('period'))
            self.ui_dir.deadline.setTristate(dir_data.get('deadline'))
            self.ui_dir.labor_costs.setTristate(dir_data.get('labor_costs'))
            self.ui_dir.all_labor_costs.setTristate(
                dir_data.get('all_labor_costs'))
            self.ui_dir.plane_labor_costs.setTristate(
                dir_data.get('plane_labor_costs'))

        while True:
            self.dir_window.exec()
            # Нажата кнопка отмена
            if self.dir_window.result() == 0:
                break
            # Проверяем входные данные
            if self.checkDirData():
                confirmed = True
                break

        if confirmed:
            # Заполняем данные
            dir_data = {}
            dir_data['dir_name'] = self.ui_dir.dir_name.text().strip()
            dir_data['task_number'] = True
            dir_data['description'] = True
            dir_data['period'] = self.ui_dir.period.isChecked()
            dir_data['deadline'] = self.ui_dir.deadline.isChecked()
            dir_data['labor_costs'] = self.ui_dir.labor_costs.isChecked()
            dir_data['all_labor_costs'] = self.ui_dir.all_labor_costs.isChecked()
            dir_data['plane_labor_costs'] = self.ui_dir.plane_labor_costs.isChecked()
            self.setDir(dir_data)

    def checkDirData(self) -> bool:
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
        if os.path.isdir(dir_path):
            self.printInfo(
                title='Уведомление', text=f'Директория {dir_name} уже существует!')
            return False

        return True

########################
# Работа с задачей
########################

    def getTaskPath(self, dir_name: str, task_number: str, get_task_data_path: bool = False) -> str:
        '''Возвращает путь до задачи или до taskData.json'''
        if get_task_data_path:
            path = os.path.join(self.getDirPath(
                dir_name), task_number, '.taskData.json')
        else:
            path = os.path.join(self.getDirPath(dir_name), task_number)
        return path

    def setTask2Tab(self, task_data: dict, tab_index: int) -> bool:
        '''
        Добавляет или изменяет задачу в таблице
        '''

    def createTask(self):
        '''
        Создаёт задачу
        '''

    def editTask(self):
        '''
        Редактирует задачу
        '''

    def removeTask(self):
        '''
        Удаляет задачу
        '''

    def openTaskWindow(self):
        '''
        Открывает окно с параметрами задачи
        '''
        self.task_window = QDialog(parent=self)
        self.task_window.setModal(True)
        self.ui_dir = Ui_Task()
        self.ui_dir.setupUi(self.task_window)

        self.task_window.show()
###########################################################
###########################################################
# Модуль "Активные задачи"
###########################################################

    def fillActiveTaskTab():
        '''
        Заполняет таблицу на основании запроса по активным задачам
        '''

###########################################################
###########################################################
# Модуль "Котёл"
###########################################################

    def fillPowTab():
        '''
        Заполняет таблицу на основании запроса по задачам в котле
        '''


############################################################
# Запуск в окне
############################################################
if __name__ == '__main__':
    print('run MTaskManager')
    app = QApplication()

    window = TaskManager()
    window.show()
    sys.exit(app.exec())
