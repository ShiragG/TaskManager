# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_task.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDateEdit,
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QPlainTextEdit, QSizePolicy,
    QVBoxLayout, QWidget)
import resources_rc

class Ui_Task(object):
    def setupUi(self, Task):
        if not Task.objectName():
            Task.setObjectName(u"Task")
        Task.resize(431, 617)
        icon = QIcon()
        icon.addFile(u":/icons/src/icons/ico/light/paw.ico", QSize(), QIcon.Normal, QIcon.Off)
        Task.setWindowIcon(icon)
        Task.setStyleSheet(u"*{\n"
"border-width: 1px;\n"
"}\n"
"#Task{\n"
"backgound-color: rgb(168, 168, 168)\n"
"}\n"
"")
        self.verticalLayout = QVBoxLayout(Task)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_task_number = QLabel(Task)
        self.label_task_number.setObjectName(u"label_task_number")
        self.label_task_number.setMinimumSize(QSize(80, 0))
        self.label_task_number.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout.addWidget(self.label_task_number)

        self.task_number = QLineEdit(Task)
        self.task_number.setObjectName(u"task_number")
        self.task_number.setMinimumSize(QSize(0, 20))
        self.task_number.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout.addWidget(self.task_number, 0, Qt.AlignLeft)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.label_task_description_2 = QLabel(Task)
        self.label_task_description_2.setObjectName(u"label_task_description_2")
        self.label_task_description_2.setMinimumSize(QSize(80, 0))
        self.label_task_description_2.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_5.addWidget(self.label_task_description_2)

        self.dir_name = QComboBox(Task)
        self.dir_name.setObjectName(u"dir_name")

        self.horizontalLayout_5.addWidget(self.dir_name)


        self.verticalLayout.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_task_description = QLabel(Task)
        self.label_task_description.setObjectName(u"label_task_description")
        self.label_task_description.setMinimumSize(QSize(80, 0))
        self.label_task_description.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_3.addWidget(self.label_task_description)

        self.task_description = QLineEdit(Task)
        self.task_description.setObjectName(u"task_description")
        self.task_description.setMinimumSize(QSize(0, 20))

        self.horizontalLayout_3.addWidget(self.task_description)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.label_date_end = QLabel(Task)
        self.label_date_end.setObjectName(u"label_date_end")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_date_end.sizePolicy().hasHeightForWidth())
        self.label_date_end.setSizePolicy(sizePolicy)
        self.label_date_end.setMinimumSize(QSize(80, 0))
        self.label_date_end.setMaximumSize(QSize(80, 16777215))
        self.label_date_end.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.horizontalLayout_4.addWidget(self.label_date_end)

        self.task_date_end = QDateEdit(Task)
        self.task_date_end.setObjectName(u"task_date_end")
        self.task_date_end.setMaximumSize(QSize(100, 25))
        self.task_date_end.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.task_date_end.setDateTime(QDateTime(QDate(2023, 1, 1), QTime(0, 0, 0)))
        self.task_date_end.setCalendarPopup(True)
        self.task_date_end.setTimeSpec(Qt.LocalTime)

        self.horizontalLayout_4.addWidget(self.task_date_end, 0, Qt.AlignLeft)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.label_ref = QLabel(Task)
        self.label_ref.setObjectName(u"label_ref")
        font = QFont()
        font.setBold(True)
        font.setItalic(True)
        self.label_ref.setFont(font)

        self.verticalLayout.addWidget(self.label_ref)

        self.label_ref_example = QLabel(Task)
        self.label_ref_example.setObjectName(u"label_ref_example")

        self.verticalLayout.addWidget(self.label_ref_example)

        self.task_text_links = QPlainTextEdit(Task)
        self.task_text_links.setObjectName(u"task_text_links")

        self.verticalLayout.addWidget(self.task_text_links)

        self.answer = QDialogButtonBox(Task)
        self.answer.setObjectName(u"answer")
        self.answer.setOrientation(Qt.Horizontal)
        self.answer.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.answer)


        self.retranslateUi(Task)
        self.answer.accepted.connect(Task.accept)
        self.answer.rejected.connect(Task.reject)

        QMetaObject.connectSlotsByName(Task)
    # setupUi

    def retranslateUi(self, Task):
        Task.setWindowTitle(QCoreApplication.translate("Task", u"\u0417\u0430\u0434\u0430\u0447\u0430", None))
        self.label_task_number.setText(QCoreApplication.translate("Task", u"\u041d\u043e\u043c\u0435\u0440 \u0437\u0430\u0434\u0430\u0447\u0438:", None))
        self.label_task_description_2.setText(QCoreApplication.translate("Task", u"\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044f:", None))
        self.label_task_description.setText(QCoreApplication.translate("Task", u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435:", None))
        self.label_date_end.setText(QCoreApplication.translate("Task", u"\u0421\u0440\u043e\u043a \u0434\u043e:", None))
        self.label_ref.setText(QCoreApplication.translate("Task", u"\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0441\u0441\u044b\u043b\u043a\u0438:", None))
        self.label_ref_example.setText(QCoreApplication.translate("Task", u"\u041f\u0440\u0438\u043c\u0435\u0440 \u0437\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f -  \u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 (>) \u0421\u0441\u044b\u043b\u043a\u0430 (;)", None))
    # retranslateUi

