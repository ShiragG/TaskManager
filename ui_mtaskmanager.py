# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_mtaskmanager.ui'
##
## Created by: Qt User Interface Compiler version 6.5.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QGridLayout, QHBoxLayout,
    QPushButton, QSizePolicy, QSpacerItem, QTabWidget,
    QVBoxLayout, QWidget)
import resources_rc

class Ui_TaskManager(object):
    def setupUi(self, TaskManager):
        if not TaskManager.objectName():
            TaskManager.setObjectName(u"TaskManager")
        TaskManager.resize(907, 498)
        icon = QIcon()
        icon.addFile(u":/icons/src/icons/paw.ico", QSize(), QIcon.Normal, QIcon.Off)
        TaskManager.setWindowIcon(icon)
        self.horizontalLayout_2 = QHBoxLayout(TaskManager)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.btn_create_dir = QPushButton(TaskManager)
        self.btn_create_dir.setObjectName(u"btn_create_dir")
        self.btn_create_dir.setMaximumSize(QSize(80, 30))

        self.horizontalLayout.addWidget(self.btn_create_dir)

        self.btn_del_dir = QPushButton(TaskManager)
        self.btn_del_dir.setObjectName(u"btn_del_dir")
        self.btn_del_dir.setMaximumSize(QSize(80, 30))

        self.horizontalLayout.addWidget(self.btn_del_dir)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.tabWidget = QTabWidget(TaskManager)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setMinimumSize(QSize(620, 340))
        self.tabWidget.setStyleSheet(u".qtable {\n"
"background-color: white;\n"
"border: 1px solid #333;\n"
"width: 100%;\n"
"max-width: 700px;\n"
"margin: 20px auto;\n"
"}\n"
"\n"
".qheader, .qbody {\n"
"padding: 12px;\n"
"}")

        self.verticalLayout.addWidget(self.tabWidget)


        self.horizontalLayout_2.addLayout(self.verticalLayout)

        self.gridLayoutTask = QGridLayout()
        self.gridLayoutTask.setObjectName(u"gridLayoutTask")
        self.btn_move_to_arch = QPushButton(TaskManager)
        self.btn_move_to_arch.setObjectName(u"btn_move_to_arch")

        self.gridLayoutTask.addWidget(self.btn_move_to_arch, 4, 0, 1, 2)

        self.btn_actions = QPushButton(TaskManager)
        self.btn_actions.setObjectName(u"btn_actions")

        self.gridLayoutTask.addWidget(self.btn_actions, 2, 0, 1, 1)

        self.btn_additional_info = QPushButton(TaskManager)
        self.btn_additional_info.setObjectName(u"btn_additional_info")

        self.gridLayoutTask.addWidget(self.btn_additional_info, 2, 1, 1, 1)

        self.btn_del_task = QPushButton(TaskManager)
        self.btn_del_task.setObjectName(u"btn_del_task")

        self.gridLayoutTask.addWidget(self.btn_del_task, 5, 0, 1, 1)

        self.btn_edit_task = QPushButton(TaskManager)
        self.btn_edit_task.setObjectName(u"btn_edit_task")

        self.gridLayoutTask.addWidget(self.btn_edit_task, 1, 1, 1, 1)

        self.btn_open = QPushButton(TaskManager)
        self.btn_open.setObjectName(u"btn_open")

        self.gridLayoutTask.addWidget(self.btn_open, 1, 0, 1, 1)

        self.btn_create_task = QPushButton(TaskManager)
        self.btn_create_task.setObjectName(u"btn_create_task")

        self.gridLayoutTask.addWidget(self.btn_create_task, 0, 0, 1, 1)

        self.checkBox_by_template = QCheckBox(TaskManager)
        self.checkBox_by_template.setObjectName(u"checkBox_by_template")

        self.gridLayoutTask.addWidget(self.checkBox_by_template, 0, 1, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayoutTask.addItem(self.verticalSpacer, 6, 0, 1, 1)


        self.horizontalLayout_2.addLayout(self.gridLayoutTask)


        self.retranslateUi(TaskManager)

        self.tabWidget.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(TaskManager)
    # setupUi

    def retranslateUi(self, TaskManager):
        TaskManager.setWindowTitle(QCoreApplication.translate("TaskManager", u"\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u0437\u0430\u0434\u0430\u0447", None))
        self.btn_create_dir.setText(QCoreApplication.translate("TaskManager", u"\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0414\u0438\u0440.", None))
        self.btn_del_dir.setText(QCoreApplication.translate("TaskManager", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0414\u0438\u0440.", None))
        self.btn_move_to_arch.setText(QCoreApplication.translate("TaskManager", u"\u041f\u0435\u0440\u0435\u043d\u0435\u0441\u0442\u0438 \u0432 \u0430\u0440\u0445\u0438\u0432", None))
        self.btn_actions.setText(QCoreApplication.translate("TaskManager", u"\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u044f", None))
        self.btn_additional_info.setText(QCoreApplication.translate("TaskManager", u"\u0414\u043e\u043f. \u0438\u043d\u0444\u043e", None))
        self.btn_del_task.setText(QCoreApplication.translate("TaskManager", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0437\u0430\u0434\u0430\u0447\u0443", None))
        self.btn_edit_task.setText(QCoreApplication.translate("TaskManager", u"\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", None))
        self.btn_open.setText(QCoreApplication.translate("TaskManager", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c...", None))
        self.btn_create_task.setText(QCoreApplication.translate("TaskManager", u"\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0437\u0430\u0434\u0430\u0447\u0443", None))
        self.checkBox_by_template.setText(QCoreApplication.translate("TaskManager", u"\u041f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443", None))
    # retranslateUi

