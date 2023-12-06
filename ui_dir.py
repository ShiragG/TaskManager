# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_dir.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QVBoxLayout, QWidget)
import resources_rc

class Ui_Dir(object):
    def setupUi(self, Dir):
        if not Dir.objectName():
            Dir.setObjectName(u"Dir")
        Dir.resize(400, 230)
        Dir.setMinimumSize(QSize(400, 230))
        Dir.setMaximumSize(QSize(400, 230))
        icon = QIcon()
        icon.addFile(u":/icons/src/icons/ico/light/paw.ico", QSize(), QIcon.Normal, QIcon.Off)
        Dir.setWindowIcon(icon)
        self.verticalLayout_2 = QVBoxLayout(Dir)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_dir_name = QLabel(Dir)
        self.label_dir_name.setObjectName(u"label_dir_name")
        font = QFont()
        font.setPointSize(10)
        self.label_dir_name.setFont(font)

        self.horizontalLayout.addWidget(self.label_dir_name)

        self.dir_name = QLineEdit(Dir)
        self.dir_name.setObjectName(u"dir_name")
        self.dir_name.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout.addWidget(self.dir_name)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_show_columns = QLabel(Dir)
        self.label_show_columns.setObjectName(u"label_show_columns")
        font1 = QFont()
        font1.setBold(True)
        font1.setItalic(True)
        self.label_show_columns.setFont(font1)

        self.verticalLayout.addWidget(self.label_show_columns)

        self.period = QCheckBox(Dir)
        self.period.setObjectName(u"period")

        self.verticalLayout.addWidget(self.period)

        self.deadline = QCheckBox(Dir)
        self.deadline.setObjectName(u"deadline")

        self.verticalLayout.addWidget(self.deadline)

        self.labor_costs = QCheckBox(Dir)
        self.labor_costs.setObjectName(u"labor_costs")

        self.verticalLayout.addWidget(self.labor_costs)

        self.all_labor_costs = QCheckBox(Dir)
        self.all_labor_costs.setObjectName(u"all_labor_costs")

        self.verticalLayout.addWidget(self.all_labor_costs)

        self.plane_labor_costs = QCheckBox(Dir)
        self.plane_labor_costs.setObjectName(u"plane_labor_costs")

        self.verticalLayout.addWidget(self.plane_labor_costs)


        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.answer = QDialogButtonBox(Dir)
        self.answer.setObjectName(u"answer")
        self.answer.setOrientation(Qt.Horizontal)
        self.answer.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout_2.addWidget(self.answer)


        self.retranslateUi(Dir)
        self.answer.accepted.connect(Dir.accept)
        self.answer.rejected.connect(Dir.reject)

        QMetaObject.connectSlotsByName(Dir)
    # setupUi

    def retranslateUi(self, Dir):
        Dir.setWindowTitle(QCoreApplication.translate("Dir", u"\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044f", None))
        self.label_dir_name.setText(QCoreApplication.translate("Dir", u"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u0438:", None))
        self.label_show_columns.setText(QCoreApplication.translate("Dir", u"\u041e\u0442\u043e\u0431\u0440\u0430\u0436\u0430\u0442\u044c \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u043f\u043e\u043b\u044f:", None))
        self.period.setText(QCoreApplication.translate("Dir", u"\u0421\u0440\u043e\u043a", None))
        self.deadline.setText(QCoreApplication.translate("Dir", u"\u041a\u043e\u043d\u0435\u0447\u043d\u044b\u0439 \u0441\u0440\u043e\u043a", None))
        self.labor_costs.setText(QCoreApplication.translate("Dir", u"\u0422\u0417", None))
        self.all_labor_costs.setText(QCoreApplication.translate("Dir", u"\u0412\u0441\u0435 \u0422\u0417", None))
        self.plane_labor_costs.setText(QCoreApplication.translate("Dir", u"\u041f\u043b\u0430\u043d\u043e\u0432\u044b\u0435 \u0422\u0417", None))
    # retranslateUi

