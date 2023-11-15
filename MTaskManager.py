import os
import sys
import shutil
import datetime
import json
import subprocess
import webbrowser

from ui_mtaskmanager import Ui_TaskManager
from ui_task import Ui_Task
from PySide6.QtWidgets import (QApplication, QFrame, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QAbstractItemView,
                               QInputDialog, QDialog, QWidget, QPushButton, QMenu, QSizePolicy)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QAction, QColor


class MTaskManager(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_TaskManager()
        self.ui.setupUi(self)

        # Загрузка и проверка настроек
        self.settings = self.readJson('taskManagerSettings.json')
        if not self.settings:
            self.setDefaultSettings()
        if not self.checkSettings():
            sys.exit()

        # Инициализируем переменные
        self.cur_task_data = {}
        # Инициализируем кнопки и события
        self.initBtnsAndActions()
        # Заполняем таблицу данными
        self.fillTabWidget()

    def setDefaultSettings(self):
        '''Создаёт стандартный файл настроек'''
        self.settings = {
            'work_dir': 'Рабочая директория',
            'template_name': '.template',
            'archive_name': '.archive',
            'explorer': 'explorer',
            'color_range': {'min': 5, 'max': 25}
        }
        # Если не создана папка с рабочей директорий
        if not os.path.isdir(self.settings.get('work_dir')):
            os.mkdir(self.settings.get('work_dir'))

        self.writeJson('taskManagerSettings.json', self.settings)

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

    def initBtnsAndActions(self):
        '''Связывает кнопки с обработчиками'''
        # Связываем клавиши с методами
        self.ui.btn_create_dir.clicked.connect(self.createDir)
        self.ui.btn_del_dir.clicked.connect(self.delDir)
        self.ui.btn_create_task.clicked.connect(self.openTaskWindow)
        self.ui.btn_edit_task.clicked.connect(self.openTaskWindow)
        self.ui.btn_move_to_arch.clicked.connect(self.moveTask2Arch)
        self.ui.btn_del_task.clicked.connect(self.delTask)

        # Делаем кнопки неактивными
        self.setEnableTaskButtons(False)

        # Задаём обработчик сигналов
        self.ui.tabWidget.currentChanged.connect(self.changedTab)
        # !Обработчик изменения выбраной ячейки задаётся при создании таблицы в addDir2Widget

    def fillTabWidget(self):
        '''Заполняет таблицу директориями и задачами из dir_task_list'''
        # Получаем список директорий и задач
        self.dir_task_list = self.readWorkDir()
        # Очищаем список директорий с задачами
        self.ui.tabWidget.clear()

        # Читаем словарь с папками рабочей директории и заполняем таблицу
        tab_index = 0
        for dir_name in self.dir_task_list.keys():
            self.addDir2Widget(dir_name)
            for task_number in self.dir_task_list[dir_name]:
                # Исключаем папки
                if task_number in (self.settings.get('template_name'),self.settings.get('archive_name')):
                    continue

                # Получаем файл с информацией по задаче
                task_data_path = self.getTaskPath(dir_name, task_number, True)
                # Проверяем что в папке есть файл с настройками
                if not os.path.isfile(task_data_path):
                    continue

                task_data = self.readJson(task_data_path)
                if not task_data:
                    task_data = {}
                    task_data['tab_index'] = tab_index
                    task_data['task_number'] = task_number
                    task_data['task_priority'] = None
                    task_data['task_description'] = None
                    task_data['task_date_end'] = None
                    task_data['task_text_links'] = None

                self.task2Tab(task_data=task_data,
                              tab_index=tab_index, add_new=True)
            tab_index += 1

    def openURL(self, url: str = None):
        '''Открывает URL в браузере'''
        webbrowser.open(url)

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

    def setEnableTaskButtons(self, enabled: bool):
        '''Включает и отключает кнопки для работы с задачами'''
        self.ui.btn_open.setEnabled(enabled)
        self.ui.btn_edit_task.setEnabled(enabled)
        self.ui.btn_actions.setEnabled(enabled)
        self.ui.btn_additional_info.setEnabled(enabled)
        self.ui.btn_move_to_arch.setEnabled(enabled)
        self.ui.btn_del_task.setEnabled(enabled)

    def changedTab(self):
        '''Действия при изменении вкладки с директориями'''
        self.setEnableTaskButtons(False)

        # Если есть директории
        if self.ui.tabWidget.count() > 0:
            self.ui.tabWidget.currentWidget().selectionModel().clear()

    def changedTask(self, task_data_new: dict = None):
        '''Действия при выделении другой ячейки'''
        self.cur_task_data = self.getCurrentTaskData()
        self.createTaskOpenMenu()

    def calcDateDifference(self, date1: str, date2: str) -> int:
        '''Расчитывает разницу в днях между датами'''
        date1 = datetime.datetime.strptime(date1, '%d.%m.%Y')
        date2 = datetime.datetime.strptime(date2, '%d.%m.%Y')
        return (date2 - date1).days
################################################################################
# Работа с директориями
################################################################################

    def getDirPath(self, dir: str) -> str:
        '''Возвращает полный путь до рабочей директории'''
        return os.path.join(self.settings.get('work_dir'), dir)

    def readWorkDir(self) -> dict:
        '''Читает рабочую директорию, создаёт словарь директория-задачи'''
        # Строим список директорий и их список задач
        dir_task_list = {}
        for dir_name in os.listdir(self.settings.get('work_dir')):
            # Записываем название директории в которую помещяем список задач
            dir_task_list[dir_name] = os.listdir(
                self.getDirPath(dir_name))
        return dir_task_list

    def openDirWindow(self) -> tuple:
        '''Создаёт окно для получения информации о новой директории'''
        # Окно заполнения новой задачи
        return QInputDialog.getText(self, 'Новая директория', 'Название директории:')

    def createDir(self, dir_name:str=None, by_ui: bool = True):
        '''Создаёт новую директорию'''
        if by_ui:
            dir_name, ok = self.openDirWindow()
            if not ok:
                return
        if dir_name.strip() == '':
            self.printInfo('Уведомление','Название не может быть пустым.',by_ui=by_ui)
            return
        
        dir_path = self.getDirPath(dir_name)

        # Проверка на существование директории
        if os.path.isdir(dir_path):
            self.printInfo(
                title='Уведомление', text=f'Директория {dir_name} уже существует!', by_ui=by_ui)
            return

        # Создаём директорию
        try:
            os.mkdir(dir_path)
            # Добавляем в список директорий
            self.dir_task_list[dir_name] = []
            if by_ui:
                self.addDir2Widget(dir_name)
        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось создать директорию.\n{e}')
            return

    def addDir2Widget(self, dir_name):
        '''Добавляет директорию на экран'''
        # Создаём таблицу
        tasks_table = QTableWidget(0, 4)
        tasks_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        tasks_table.setHorizontalHeaderLabels(
            ('Номер', 'Приоритет', 'Описание', 'Срок окончания'))
        # Задаём растягивание
        tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # tasks_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)s
        # Добавялем обработку сигнала выделения ячейки
        tasks_table.currentItemChanged.connect(self.changedTask)
        self.ui.tabWidget.addTab(tasks_table, dir_name)

    def delDir(self, dir_name=None, by_ui: bool = True):
        '''Удаляет директорию'''
        # Если в таблице нету вкладок
        if self.ui.tabWidget.count() < 1:
            return

        if by_ui:
            # Получаем параметры с эк.формы
            current_tab_index = self.ui.tabWidget.currentIndex()
            dir_name = self.ui.tabWidget.tabText(current_tab_index)
            answer = QMessageBox.question(self, 'Предупреждение',
                                          f'Вы уверены, что хотите удалить {dir_name}?\nТакже будет удалён архив.',
                                          QMessageBox.StandardButton.Yes,
                                          QMessageBox.StandardButton.No
                                          )
            if answer == QMessageBox.StandardButton.No:
                return

        dir_path = self.getDirPath(dir_name)

        # Рекурсивно удаляем директорию
        if os.path.isdir(dir_path):
            shutil.rmtree(dir_path)
            # Удаляем директорию из списка
            del self.dir_task_list[dir_name]

            if by_ui:
                self.ui.tabWidget.removeTab(current_tab_index)
                self.setEnableTaskButtons(False)

        else:
            self.printInfo(title='Уведомление',
                           text=f'Директория: {dir_name} не найдена')

################################################################################
# Работа с задачами
################################################################################

    def getTaskPath(self, dir_name: str, task_number: str, getTaskDataPath: bool = False) -> str:
        '''Возвращает путь до задачи или до taskData.json'''
        if getTaskDataPath:
            path = os.path.join(self.getDirPath(
                dir_name), task_number, '.taskData.json')
        else:
            path = os.path.join(self.getDirPath(dir_name), task_number)
        return path

    def openTaskWindow(self, task_data: dict = None, action: str = None):
        '''Вызывает окно с задачей
        action ='Create'|'Edit'
        '''
        # Проверяем, что есть созданная директория
        if not self.ui.tabWidget.currentWidget():
            return
        
        # Создаём окно с задачей
        self.task_window = QDialog()
        self.ui_task_window = Ui_Task()
        self.ui_task_window.setupUi(self.task_window)

        # Задаём формат
        self.ui_task_window.task_date_end.setDisplayFormat('dd.MM.yyyy')

        # Узнаём кто вызвал метод и ставим обработчик
        sender = self.sender()
        sender_text = ''
        # Если нет источника
        if sender:
            sender_text = sender.text()

        if sender_text == 'Создать задачу' or action == 'Create':
            self.ui_task_window.buttonBox.accepted.connect(self.createTask)

            # Если нет данных для заполнения формы
            if not task_data:
                # Подставляем стандартные значения
                task_data = {}
                task_data['task_number'] = 'RP'
                task_data['task_priority'] = 3
                task_data['task_description'] = '*Описание*'
                task_data['task_date_end'] = datetime.datetime.now().strftime(
                    '%d.%m.%Y')
                task_data['task_text_links'] = ''
                self.fillTaskWindow(task_data)
            else:
                # Заполняем входными парамметрами
                self.fillTaskWindow(task_data)

        elif sender_text == 'Изменить' or action == 'Edit':
            self.ui_task_window.buttonBox.accepted.connect(self.editTaskInfo)
            # Если нет данных для заполнения формы
            if not task_data:
                # Получаем информацию по выделенной задаче
                self.fillTaskWindow(self.cur_task_data)
            else:
                # Заполняем входными парамметрами
                self.fillTaskWindow(task_data)

        self.task_window.show()

    def fillTaskWindow(self, task_data: dict):
        '''Заполняет данными окно с задачей'''

        self.ui_task_window.task_number.setText(
            task_data.get('task_number'))
        self.ui_task_window.task_priority.setValue(
            int(task_data.get('task_priority')))
        self.ui_task_window.task_description.setText(
            task_data.get('task_description'))
        dt = datetime.datetime.strptime(
            task_data.get('task_date_end'), '%d.%m.%Y')
        self.ui_task_window.task_date_end.setDate(
            QDate(dt.year, dt.month, dt.day))
        self.ui_task_window.task_text_links.setPlainText(
            task_data.get('task_text_links'))

    def openTaskDir(self):
        '''Открываем директорию задачи в заданном проводнике'''
        # Получаем параметры с эк.формы
        tab_index = self.ui.tabWidget.currentIndex()
        dir_name = self.ui.tabWidget.tabText(tab_index)
        row = self.ui.tabWidget.currentWidget().selectionModel().currentIndex().row()
        task_number = self.ui.tabWidget.currentWidget().item(row, 0).text()
        task_path = self.getTaskPath(dir_name, task_number)
        try:
            subprocess.Popen(self.settings.get('explorer') + ' ' + task_path, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось открыть директорию.\n{e}')

            return

    def createTask(self, task_data: dict = {},
                   by_ui: bool = True,
                   by_template: bool = False):
        '''Создаёт задачу в директории'''
        if by_ui:
            # Получаем параметры с эк.формы
            task_data['tab_index'] = self.ui.tabWidget.currentIndex()
            task_data['dir_name'] = self.ui.tabWidget.tabText(
                task_data['tab_index'])
            # Если нету директорий
            if task_data['dir_name'] == '':
                return
            task_data['task_number'] = self.ui_task_window.task_number.text()
            task_data['task_priority'] = str(
                self.ui_task_window.task_priority.value())
            task_data['task_description'] = self.ui_task_window.task_description.text()
            task_data['task_date_end'] = self.ui_task_window.task_date_end.text()
            task_data['task_text_links'] = self.ui_task_window.task_text_links.toPlainText()
            dt = datetime.datetime.now()
            task_data['task_date_create'] = dt.strftime('%d.%m.%Y')
            by_template = self.ui.checkBox_by_template.isChecked()

        # Проверяем корректность введённых данных
        if not self.checkTaskInfo(task_data, check_new=True):
            self.openTaskWindow(task_data, 'Create')
            return

        template_path = self.getTaskPath(
            task_data['dir_name'], self.settings.get('template_name'))
        task_path = self.getTaskPath(
            task_data['dir_name'], task_data['task_number'])
        task_data_path = self.getTaskPath(
            task_data['dir_name'], task_data['task_number'], True)

        try:
            # Создаём по шаблонну
            if by_template:
                if not os.path.isdir(template_path):
                    self.printInfo(title='Уведомление',
                                text=f'Не найдена шаблонная директория!', by_ui=by_ui)
                    return

                shutil.copytree(
                    template_path, task_path)
                # Добавляем файл с информацией по задаче
                self.writeJson(file_path=task_data_path, data=task_data)
                # Добавляем задачу в список
                self.dir_task_list[task_data['dir_name']].append(
                    task_data['task_number'])
            else:
                # Создаём директорию
                os.mkdir(task_path)
                # Добавляем файл с информацией по задаче
                self.writeJson(file_path=task_data_path, data=task_data)
                # Добавляем задачу в список
                self.dir_task_list[task_data['dir_name']].append(
                    task_data['task_number'])
        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось создать задачу.\n{e}')
            return

        # Добавляем задачу в список на экране
        if by_ui:
            self.task2Tab(task_data=task_data, add_new=True)

    def task2Tab(self, task_data: dict, tab_index: int = None, add_new: bool = False):
        ''' Добавляет или изменяет задачу в списке на эк. форме'''
        # Проверяем есть ли номер строки в task_data
        row = task_data.get('row')
        # Если не передали индекс таблицы
        if not tab_index:
            tab_index = task_data.get('tab_index')

        if add_new:
            # Задача новая, получаем номер новой последней строки
            row = self.ui.tabWidget.widget(tab_index).rowCount()
            # Добавляем строку в таблицу
            self.ui.tabWidget.widget(tab_index).insertRow(row)

        # Записываем данные задачи в таблицу
        self.ui.tabWidget.widget(tab_index).setItem(
            row, 0, QTableWidgetItem(task_data.get('task_number')))
        self.ui.tabWidget.widget(tab_index).setItem(
            row, 1, QTableWidgetItem(task_data.get('task_priority')))
        self.ui.tabWidget.widget(tab_index).setItem(
            row, 2, QTableWidgetItem(task_data.get('task_description')))

        # Задаём дату окончания и цвет
        task_date_end_item = QTableWidgetItem(task_data.get('task_date_end'))

        # Разница в днях
        days = self.calcDateDifference(datetime.datetime.now().strftime(
            '%d.%m.%Y'), task_data.get('task_date_end'))
        # Рассчитываем цвет
        if days <= self.settings['color_range'].get('min'):
            color = QColor("red")
        elif days <= self.settings['color_range'].get('max')//2:
            color = QColor("yellow")
        elif days >= self.settings['color_range'].get('max')//2:
            color = QColor("green")

        task_date_end_item.setBackground(color)
        self.ui.tabWidget.widget(tab_index).setItem(
            row, 3, task_date_end_item)

    def getCurrentTaskData(self) -> dict:
        '''Возвращает список информации по выделенной задаче'''
        # Получаем параметры с эк.формы
        tab_index = self.ui.tabWidget.currentIndex()
        dir_name = self.ui.tabWidget.tabText(tab_index)
        row = self.ui.tabWidget.currentWidget().selectionModel().currentIndex().row()
        if row == -1:
            return None
        task_number = self.ui.tabWidget.currentWidget().item(row, 0).text()

        # Получаем информацию из файла
        task_data_path = self.getTaskPath(dir_name, task_number, True)

        task_data = {}
        task_data = self.readJson(task_data_path)
        task_data['tab_index'] = tab_index
        task_data['dir_name'] = dir_name
        task_data['row'] = row
        
        return task_data

    def delTask(self, dir_name=None, task_number=None, by_ui: bool = True):
        '''Удаляет задачу из директории'''
        # Если нету вкладок или нету задач
        if self.ui.tabWidget.count() < 1 or self.ui.tabWidget.currentWidget().rowCount() < 1:
            return

        if by_ui:
            # Получаем параметры с эк.формы
            tab_index = self.ui.tabWidget.currentIndex()
            dir_name = self.ui.tabWidget.tabText(tab_index)
            row = self.ui.tabWidget.currentWidget().selectionModel().currentIndex().row()
            # Если не выбрана задача
            if row == -1:
                return
            task_number = self.ui.tabWidget.currentWidget().item(row, 0).text()

            answer = QMessageBox.question(self, 'Предупреждение',
                                          f'Вы уверены, что хотите удалить {task_number}?',
                                          QMessageBox.StandardButton.Yes,
                                          QMessageBox.StandardButton.No
                                          )
            if answer == QMessageBox.StandardButton.No:
                return

        task_path = self.getTaskPath(dir_name, task_number)

        # Рекурсивно удаляем директорию
        try:
            shutil.rmtree(task_path)

            # Удаляем задачу из списка
            self.dir_task_list[dir_name].remove(task_number)

            if by_ui:
                self.delTask4Tab(tab_index,row)
        except Exception as e:
            self.printInfo(title='Предупреждение',
                           text=f'Не удалось удалить задачу.\n{e}')
            return
    
    def delTask4Tab(self, tab_index:int, row:int):
        '''Удаляет задачу с таблицы'''
        # Удаляем элемент
        self.ui.tabWidget.widget(tab_index).removeRow(row)
        # Делаем кнопки неактивными
        self.setEnableTaskButtons(False)

    def moveTask2Arch(self):
        '''Переносит задачу в архив'''

        task_data = self.getCurrentTaskData()
        if not task_data:
            return

        try:
            arch_path = os.path.join(self.getDirPath(task_data.get('dir_name')),self.settings.get('archive_name'))
            # Если нету папки с архивом
            if not os.path.isdir(arch_path):
                os.mkdir(arch_path)
            
            current_month = datetime.datetime.now().strftime('%Y_%m')
            arch_path_current_month = os.path.join(arch_path,current_month)

            # Если в архиве нету папки с текущим месяцом
            if not os.path.isdir(arch_path_current_month):
                os.mkdir(arch_path_current_month)

            task_path = self.getTaskPath(task_data.get('dir_name'), task_data.get('task_number'))
            # Переносим задачу в архив в нужный месяц
            
            shutil.move(task_path,arch_path_current_month)
        except Exception as e:
            self.printInfo(title='Предупреждение',text=f'Не удалось перенести задачу.\n{e}')
            return

        # Удаляем задачу из таблицы
        self.delTask4Tab(task_data.get('tab_index'),task_data.get('row'))

    def editTaskInfo(self, by_ui: bool = True):
        '''Редактирует информацию по задаче'''

        # Получаем информацию по выделенной задаче
        task_data = self.cur_task_data
        # Если нет основной задачи
        if not task_data:
            self.printInfo('Предупреждение', 'Не выбрана задача')
            return

        # Получаем параметры с эк.формы
        task_data_new = task_data.copy()
        task_data_new['tab_index'] = int(self.ui.tabWidget.currentIndex())
        task_data_new['dir_name'] = self.ui.tabWidget.tabText(
            task_data_new['tab_index'])
        task_data_new['task_number'] = self.ui_task_window.task_number.text()
        task_data_new['task_priority'] = str(
            self.ui_task_window.task_priority.value())
        task_data_new['task_description'] = self.ui_task_window.task_description.text()
        task_data_new['task_date_end'] = self.ui_task_window.task_date_end.text()
        task_data_new['task_text_links'] = self.ui_task_window.task_text_links.toPlainText()

        # Проверяем корректность введённых данных
        if not self.checkTaskInfo(task_data_new):
            self.openTaskWindow(task_data_new, 'Edit')
            return

        # Получаем путь до задачи
        task_path = self.getTaskPath(task_data.get(
            'dir_name'), task_data.get('task_number'))

        task_path_new = self.getTaskPath(task_data_new.get(
            'dir_name'), task_data_new.get('task_number'))

        # Если изменился номер задачи, то переименовываем папку
        if task_data.get('task_number') != task_data_new.get('task_number'):
            try:
                os.rename(task_path, task_path_new)
            except Exception as e:
                self.printInfo(
                    title='Предупреждение',
                    text=f'Не удалось переименовать {task_data.get("task_number")} в {task_path_new.get("task_number")}.\n{e}',
                    by_ui=by_ui)
                return

        # Записываем новую информацию
        task_data_path = self.getTaskPath(task_data_new.get(
            'dir_name'), task_data_new.get('task_number'), True)
        self.writeJson(task_data_path, task_data_new)

        # Изменяем данные задачи на форме
        self.task2Tab(task_data_new)
        self.changedTask(task_data_new)

    def checkTaskInfo(self, task_data: dict, check_new: bool = False, by_ui: bool = True) -> bool:
        '''Проверяем введённые данные по задаче'''

        if task_data['task_number'].strip() == '':
            self.printInfo(title='Предупреждение',
                           text='Номер задачи не может быть пустым!', by_ui=by_ui)
            return False

        # Получаем путь до задачи
        task_path = self.getTaskPath(task_data.get(
            'dir_name'), task_data.get('task_number'))

        # Если директория существует
        if check_new and os.path.isdir(task_path):
            self.printInfo(
                title='Уведомление', text=f'Задача: {task_data["task_number"]} уже существует!', by_ui=by_ui)
            return False

        # Проверяем корректность введённых ссылок
        task_text_links = task_data.get('task_text_links').strip()
        if task_text_links != '' and not self.getDictLinks(task_data.get('task_text_links'), by_ui):
            return False

        return True

    def createTaskOpenMenu(self, task_data_new: dict = None):
        '''Создаёт меню на вкладке открыть для выбранной задачи'''

        # Получеам информацию по выделенной задаче
        # Если нет новой информации по задаче
        if not task_data_new:
            # Получеам информацию по выделенной задаче
            task_data = self.cur_task_data
        else:
            task_data = task_data_new

        # Если снято выделение с задачи или задача не выбрана
        if not task_data or task_data.get('row') < 0:
            return
        # Делаем кнопки активными
        self.setEnableTaskButtons(True)

        # Создаём выпадающее меню
        self.menu_open = QMenu()
        # Создаём вкладки

        # Созданные автоматически
        self.menu_open.addAction('Открыть дир.', self.openTaskDir)

        # Заданные пользователем
        # Если есть ссылки
        if task_data.get('task_text_links'):
            links = self.getDictLinks(task_data.get('task_text_links'))
            # Если удалось распарсить ссылки
            if links:
                # Добавляем названия ссылок в список
                for link_name in links:
                    action = QAction(link_name, self)
                    action.triggered.connect(self.openLink)
                    self.menu_open.addAction(action)

        self.ui.btn_open.setMenu(self.menu_open)

    def getDictLinks(self, task_text_links: str, by_ui: bool = True) -> dict:
        '''Создаёт список'''
        links = {}
        # Разбиваем на строки
        try:
            for line in task_text_links.split(';'):

                # Разбиваем на ключ:значение
                link = line.split('>')
                # Выходим если пустая строка
                if line.strip() == '':
                    break
                links[link[0].strip()] = link[1]
            return links
        except Exception as e:
            self.printInfo('Предупреждение',
                           f'Не удалось прочитать ссылки, проверьте правильность заполнения.\n{e}', by_ui=by_ui)
            return None

    def openLink(self):
        '''Открывает ссылки'''
        # Получаем имя ссылки
        sender = self.sender()
        link_name = sender.text()

        # Получем ссылку из задачи
        task_data = self.cur_task_data
        dict_links = self.getDictLinks(task_data.get('task_text_links'))
        link = ''
        link = dict_links[link_name]

        # Проверка ссылок
        if link.startswith('http'):
            webbrowser.open(link)
        elif os.path.isdir(link):
            os.startfile(link)
        else:
            self.printInfo(title='Предупреждение',
                           text=f'Не удаётся открыть ссылку: {link}')


################################################################################
# Запуск в отдельном окне
################################################################################
if __name__ == '__main__':
    print('run MTaskManager')
    app = QApplication()
    window = MTaskManager()
    window.show()
    sys.exit(app.exec())
