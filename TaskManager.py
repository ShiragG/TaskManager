import os
import sys

from PySide6.QtWidgets import (QApplication, QFrame, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QAbstractItemView,
                               QInputDialog, QDialog, QWidget, QPushButton, QMenu, QSizePolicy)

class TaskManager():
    pass


################################################################################
# Запуск в окне
################################################################################
if __name__ == '__main__':
    print('run MTaskManager')
    app = QApplication()
    window = TaskManager()
    window.show()
    sys.exit(app.exec())