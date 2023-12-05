import os
import sys
import json

from ui_taskmanager import *

from PySide6.QtWidgets import (QMessageBox,QTableWidget,QAbstractItemView, QHeaderView)


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

        # Инициализируем обработчик и модули
        self.initHandler()
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
        jsonData = json.dumps(data)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(jsonData)

    def setDefaultSettings(self):
        '''Создаёт стандартный файл настроек'''
        self.settings = {
            'work_dir': 'Working directory',
            'template_name': '.template',
            'archive_name': '.archive',
            'explorer': 'explorer',
            'color_range': {'min': 5, 'max': 25},
            'task_manager_columns':{
                'other':[]
            },
            'active_task_columns':{
                'support':['№ заявки','Тип',],
                'project':[],
                'other':[],
                'code_review':[]
            },
            'pot_columns':{
                'code_review':[],
                'support':[],
                'project':[]
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

    def writeSettingsApp(self, settings:dict):
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

    def printInfo(self, title: str = None, text: str = None, by_ui: bool = True):
        '''Выводит информацию на экран и в консоль'''
        if by_ui:
            QMessageBox.information(self, title, text)
        print(title + ': '+text)

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
            if not self.setDir2Tab(dir_name):
                continue
            for task_number in dir_list[dir_name]:
                # Исключаем папки
                if task_number in (self.settings.get('template_name'), self.settings.get('archive_name')):
                    continue

                # Получаем файл с информацией по задаче
                task_data_path = self.getTaskPath(dir_name, task_number, True)
                # Проверяем что в папке есть файл с настройками
                if not os.path.isfile(task_data_path):
                    continue

                task_data = self.readJson(task_data_path)
                self.setTask2Tab(task_data,tab_index)

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

    def getDirPath(self, dir_name: str) -> str:
        '''
        Возвращает полный путь до рабочей директории
        '''
        return os.path.join(self.settings.get('work_dir'), dir_name)

    def getTaskPath(self, dir_name: str, task_number: str, getTaskDataPath: bool = False) -> str:
        '''Возвращает путь до задачи или до taskData.json'''
        if getTaskDataPath:
            path = os.path.join(self.getDirPath(
                dir_name), task_number, '.taskData.json')
        else:
            path = os.path.join(self.getDirPath(dir_name), task_number)
        return path

    def setDir2Tab(self, dir_name: str) -> bool:
        '''
        Добавляет или изменяет директорию в таблице
        '''
        # Получаем информацию директории
        dir_data_path = self.getDirPath(dir_name, True)
        if not dir_data:
            return False
        dir_data = self.readJson(dir_data_path)

        # Создаём таблицу
        columns_list = []
        columns_list = dir_data.get('columns')
        tab = QTableWidget(0,len(columns_list))

        # Тригер на редактирование таблицы
        #tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Задаём названия колонок
        tab.setHorizontalHeaderLabels(columns_list)

        # Задаём растягивание для таблцы
        tab.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Передаём таблицу на форму
        self.ui.taskManagerTab.addTab(tab, dir_name)

    def setTask2Tab(self, task_data: dict, tab_index: int) -> bool:
        '''
        Добавляет или изменяет задачу в таблице
        '''
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
