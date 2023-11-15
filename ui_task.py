# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_task.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QDateEdit,
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget)

class Ui_Task(object):
    def setupUi(self, Task):
        if not Task.objectName():
            Task.setObjectName(u"Task")
        Task.resize(477, 617)
        self.verticalLayout_2 = QVBoxLayout(Task)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label__task_number = QLabel(Task)
        self.label__task_number.setObjectName(u"label__task_number")

        self.horizontalLayout.addWidget(self.label__task_number)

        self.task_number = QLineEdit(Task)
        self.task_number.setObjectName(u"task_number")

        self.horizontalLayout.addWidget(self.task_number)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label_task_priority = QLabel(Task)
        self.label_task_priority.setObjectName(u"label_task_priority")

        self.horizontalLayout_2.addWidget(self.label_task_priority)

        self.task_priority = QSpinBox(Task)
        self.task_priority.setObjectName(u"task_priority")
        self.task_priority.setMinimumSize(QSize(0, 0))
        self.task_priority.setMaximumSize(QSize(16777215, 16777215))
        self.task_priority.setWrapping(False)
        self.task_priority.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.task_priority.setAccelerated(False)
        self.task_priority.setKeyboardTracking(True)
        self.task_priority.setProperty("showGroupSeparator", False)

        self.horizontalLayout_2.addWidget(self.task_priority)


        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_task_description = QLabel(Task)
        self.label_task_description.setObjectName(u"label_task_description")

        self.horizontalLayout_3.addWidget(self.label_task_description)

        self.task_description = QLineEdit(Task)
        self.task_description.setObjectName(u"task_description")

        self.horizontalLayout_3.addWidget(self.task_description)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_date_end = QLabel(Task)
        self.label_date_end.setObjectName(u"label_date_end")

        self.horizontalLayout_4.addWidget(self.label_date_end)

        self.task_date_end = QDateEdit(Task)
        self.task_date_end.setObjectName(u"task_date_end")
        self.task_date_end.setDateTime(QDateTime(QDate(2023, 1, 1), QTime(0, 0, 0)))
        self.task_date_end.setCalendarPopup(True)
        self.task_date_end.setTimeSpec(Qt.LocalTime)

        self.horizontalLayout_4.addWidget(self.task_date_end)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.label_ref = QLabel(Task)
        self.label_ref.setObjectName(u"label_ref")

        self.verticalLayout.addWidget(self.label_ref)

        self.label_ref_example = QLabel(Task)
        self.label_ref_example.setObjectName(u"label_ref_example")

        self.verticalLayout.addWidget(self.label_ref_example)

        self.task_text_links = QPlainTextEdit(Task)
        self.task_text_links.setObjectName(u"task_text_links")

        self.verticalLayout.addWidget(self.task_text_links)

        self.buttonBox = QDialogButtonBox(Task)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.verticalLayout_2.addLayout(self.verticalLayout)


        self.retranslateUi(Task)
        self.buttonBox.accepted.connect(Task.accept)
        self.buttonBox.rejected.connect(Task.reject)

        QMetaObject.connectSlotsByName(Task)
    # setupUi

    def retranslateUi(self, Task):
        Task.setWindowTitle(QCoreApplication.translate("Task", u"\u0417\u0430\u0434\u0430\u0447\u0430", None))
        self.label__task_number.setText(QCoreApplication.translate("Task", u"\u041d\u043e\u043c\u0435\u0440 \u0437\u0430\u0434\u0430\u0447\u0438", None))
        self.label_task_priority.setText(QCoreApplication.translate("Task", u"\u041f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442", None))
        self.label_task_description.setText(QCoreApplication.translate("Task", u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435", None))
        self.label_date_end.setText(QCoreApplication.translate("Task", u"\u0421\u0440\u043e\u043a \u043e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u044f", None))
        self.label_ref.setText(QCoreApplication.translate("Task", u"\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0441\u0441\u044b\u043b\u043a\u0438:", None))
        self.label_ref_example.setText(QCoreApplication.translate("Task", u"\u041f\u0440\u0438\u043c\u0435\u0440 \u0437\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f -  \u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 (>) \u0421\u0441\u044b\u043b\u043a\u0430 (;)", None))
    # retranslateUi

