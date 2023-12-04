import os
import sys

from ui_taskmanager import *


class TaskManager(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Скрываем лишние окна
        self.ui.leftMenu.hide()
        self.ui.notificationContent.hide()

        self.initHandler()

###########################################################
# Основные методы
###########################################################

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

###########################################################
# Модуль "Ведение задач"
###########################################################

###########################################################
# Модуль "Активные задачи"
###########################################################

###########################################################
# Модуль "Котёл"
###########################################################

############################################################
# Запуск в окне
############################################################
if __name__ == '__main__':
    print('run MTaskManager')
    app = QApplication()

    window = TaskManager()
    window.show()
    sys.exit(app.exec())
