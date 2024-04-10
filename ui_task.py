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
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QCheckBox,
    QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel,
    QLayout, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)
import resources_rc

class Ui_Task(object):
    def setupUi(self, Task):
        if not Task.objectName():
            Task.setObjectName(u"Task")
        Task.resize(490, 636)
        icon = QIcon()
        icon.addFile(u":/icons/src/icons/ico/light/paw.ico", QSize(), QIcon.Normal, QIcon.Off)
        Task.setWindowIcon(icon)
        Task.setStyleSheet(u"*{\n"
"	border-width: 1px;\n"
"}\n"
"\n"
"#Task{\n"
"	background-color: rgb(216, 233, 255)\n"
"}\n"
"\n"
"QPushButton{\n"
"}\n"
"")
        self.verticalLayout = QVBoxLayout(Task)
        self.verticalLayout.setObjectName(u"verticalLayout")
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

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_task_description = QLabel(Task)
        self.label_task_description.setObjectName(u"label_task_description")
        self.label_task_description.setMinimumSize(QSize(80, 0))
        self.label_task_description.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_3.addWidget(self.label_task_description)

        self.description = QLineEdit(Task)
        self.description.setObjectName(u"description")
        self.description.setMinimumSize(QSize(0, 20))
        self.description.setInputMethodHints(Qt.ImhNone)
        self.description.setClearButtonEnabled(False)

        self.horizontalLayout_3.addWidget(self.description)


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

        self.date_end = QDateEdit(Task)
        self.date_end.setObjectName(u"date_end")
        self.date_end.setMaximumSize(QSize(100, 25))
        self.date_end.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.date_end.setDateTime(QDateTime(QDate(2023, 1, 1), QTime(0, 0, 0)))
        self.date_end.setCalendarPopup(True)
        self.date_end.setTimeSpec(Qt.LocalTime)

        self.horizontalLayout_4.addWidget(self.date_end, 0, Qt.AlignLeft)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label_my_plane_labor_costs = QLabel(Task)
        self.label_my_plane_labor_costs.setObjectName(u"label_my_plane_labor_costs")

        self.horizontalLayout_2.addWidget(self.label_my_plane_labor_costs)

        self.my_plane_labor_costs = QDoubleSpinBox(Task)
        self.my_plane_labor_costs.setObjectName(u"my_plane_labor_costs")
        self.my_plane_labor_costs.setMinimumSize(QSize(100, 0))
        self.my_plane_labor_costs.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.my_plane_labor_costs.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.my_plane_labor_costs.setKeyboardTracking(False)
        self.my_plane_labor_costs.setDecimals(1)
        self.my_plane_labor_costs.setMaximum(99999999.000000000000000)

        self.horizontalLayout_2.addWidget(self.my_plane_labor_costs)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.by_template = QCheckBox(Task)
        self.by_template.setObjectName(u"by_template")

        self.verticalLayout.addWidget(self.by_template)

        self.label_ref = QLabel(Task)
        self.label_ref.setObjectName(u"label_ref")
        font = QFont()
        font.setBold(True)
        font.setItalic(True)
        self.label_ref.setFont(font)

        self.verticalLayout.addWidget(self.label_ref)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.addLinksBtn = QPushButton(Task)
        self.addLinksBtn.setObjectName(u"addLinksBtn")

        self.horizontalLayout_8.addWidget(self.addLinksBtn)

        self.horizontalSpacer_4 = QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_4)

        self.delLinksBtn = QPushButton(Task)
        self.delLinksBtn.setObjectName(u"delLinksBtn")

        self.horizontalLayout_8.addWidget(self.delLinksBtn)


        self.verticalLayout.addLayout(self.horizontalLayout_8)

        self.tabLinks = QTableWidget(Task)
        if (self.tabLinks.columnCount() < 2):
            self.tabLinks.setColumnCount(2)
        __qtablewidgetitem = QTableWidgetItem()
        self.tabLinks.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tabLinks.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        self.tabLinks.setObjectName(u"tabLinks")

        self.verticalLayout.addWidget(self.tabLinks)

        self.horizontalLayout_7 = QHBoxLayout()
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.label_color = QLabel(Task)
        self.label_color.setObjectName(u"label_color")
        self.label_color.setMaximumSize(QSize(30, 16777215))

        self.horizontalLayout_7.addWidget(self.label_color)

        self.color = QComboBox(Task)
        self.color.setObjectName(u"color")
        self.color.setMinimumSize(QSize(100, 0))
        self.color.setMaximumSize(QSize(100, 16777215))

        self.horizontalLayout_7.addWidget(self.color)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addLayout(self.horizontalLayout_7)

        self.hidden = QCheckBox(Task)
        self.hidden.setObjectName(u"hidden")

        self.verticalLayout.addWidget(self.hidden)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_date_create_local = QLabel(Task)
        self.label_date_create_local.setObjectName(u"label_date_create_local")
        self.label_date_create_local.setMaximumSize(QSize(105, 200))

        self.horizontalLayout_6.addWidget(self.label_date_create_local)

        self.date_create_local = QLabel(Task)
        self.date_create_local.setObjectName(u"date_create_local")

        self.horizontalLayout_6.addWidget(self.date_create_local)


        self.verticalLayout.addLayout(self.horizontalLayout_6)

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
        Task.setWindowTitle(QCoreApplication.translate("Task", u"\u0417\u0430\u044f\u0432\u043a\u0430", None))
        self.label_task_description_2.setText(QCoreApplication.translate("Task", u"\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044f:", None))
        self.label_task_number.setText(QCoreApplication.translate("Task", u"\u041d\u043e\u043c\u0435\u0440 \u0437\u0430\u044f\u0432\u043a\u0438:", None))
        self.label_task_description.setText(QCoreApplication.translate("Task", u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435:", None))
        self.label_date_end.setText(QCoreApplication.translate("Task", u"\u0421\u0440\u043e\u043a \u0434\u043e:", None))
        self.label_my_plane_labor_costs.setText(QCoreApplication.translate("Task", u"\u041f\u043b\u0430\u043d\u0438\u0440\u0443\u0435\u043c\u044b\u0435 \u0422\u0417:", None))
        self.by_template.setText(QCoreApplication.translate("Task", u"\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u043f\u0440\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u0438", None))
        self.label_ref.setText(QCoreApplication.translate("Task", u"\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0441\u0441\u044b\u043b\u043a\u0438:", None))
        self.addLinksBtn.setText(QCoreApplication.translate("Task", u"\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c", None))
        self.delLinksBtn.setText(QCoreApplication.translate("Task", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c", None))
        ___qtablewidgetitem = self.tabLinks.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("Task", u"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435", None));
        ___qtablewidgetitem1 = self.tabLinks.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("Task", u"\u0421\u0441\u044b\u043b\u043a\u0430", None));
        self.label_color.setText(QCoreApplication.translate("Task", u"\u0426\u0432\u0435\u0442:", None))
        self.hidden.setText(QCoreApplication.translate("Task", u"\u0421\u043a\u0440\u044b\u0442\u044c \u0437\u0430\u044f\u0432\u043a\u0443", None))
        self.label_date_create_local.setText(QCoreApplication.translate("Task", u"\u0421\u043e\u0437\u0434\u0430\u043d\u0430 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e:", None))
        self.date_create_local.setText("")
    # retranslateUi

