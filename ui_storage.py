# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_storage.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QCheckBox,
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_Storage(object):
    def setupUi(self, Storage):
        if not Storage.objectName():
            Storage.setObjectName(u"Storage")
        Storage.resize(622, 473)
        self.verticalLayout_7 = QVBoxLayout(Storage)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_5 = QVBoxLayout()
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_patch = QLabel(Storage)
        self.label_patch.setObjectName(u"label_patch")

        self.horizontalLayout.addWidget(self.label_patch)

        self.pckPath = QLineEdit(Storage)
        self.pckPath.setObjectName(u"pckPath")
        self.pckPath.setMinimumSize(QSize(400, 0))

        self.horizontalLayout.addWidget(self.pckPath)

        self.patchBtn = QPushButton(Storage)
        self.patchBtn.setObjectName(u"patchBtn")
        self.patchBtn.setMaximumSize(QSize(40, 24))

        self.horizontalLayout.addWidget(self.patchBtn)


        self.verticalLayout_5.addLayout(self.horizontalLayout)

        self.insertTwoWhitespace = QCheckBox(Storage)
        self.insertTwoWhitespace.setObjectName(u"insertTwoWhitespace")

        self.verticalLayout_5.addWidget(self.insertTwoWhitespace)


        self.verticalLayout_7.addLayout(self.verticalLayout_5)

        self.verticalLayout_4 = QVBoxLayout()
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label_scheme_one = QLabel(Storage)
        self.label_scheme_one.setObjectName(u"label_scheme_one")
        self.label_scheme_one.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_2.addWidget(self.label_scheme_one)

        self.schemeOne_text = QComboBox(Storage)
        self.schemeOne_text.addItem("")
        self.schemeOne_text.setObjectName(u"schemeOne_text")
        self.schemeOne_text.setMinimumSize(QSize(300, 0))
        self.schemeOne_text.setEditable(True)

        self.horizontalLayout_2.addWidget(self.schemeOne_text)


        self.verticalLayout_4.addLayout(self.horizontalLayout_2)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.schemeTwo = QCheckBox(Storage)
        self.schemeTwo.setObjectName(u"schemeTwo")
        self.schemeTwo.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_3.addWidget(self.schemeTwo)

        self.schemeTwo_text = QComboBox(Storage)
        self.schemeTwo_text.addItem("")
        self.schemeTwo_text.setObjectName(u"schemeTwo_text")
        self.schemeTwo_text.setEnabled(False)
        self.schemeTwo_text.setMinimumSize(QSize(300, 0))
        self.schemeTwo_text.setEditable(True)

        self.horizontalLayout_3.addWidget(self.schemeTwo_text)


        self.verticalLayout_4.addLayout(self.horizontalLayout_3)


        self.verticalLayout_7.addLayout(self.verticalLayout_4)

        self.runCompare = QCheckBox(Storage)
        self.runCompare.setObjectName(u"runCompare")

        self.verticalLayout_7.addWidget(self.runCompare)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.rename = QCheckBox(Storage)
        self.rename.setObjectName(u"rename")

        self.horizontalLayout_4.addWidget(self.rename)

        self.rename_text = QLineEdit(Storage)
        self.rename_text.setObjectName(u"rename_text")
        self.rename_text.setEnabled(False)

        self.horizontalLayout_4.addWidget(self.rename_text)


        self.verticalLayout_7.addLayout(self.horizontalLayout_4)

        self.verticalLayout_6 = QVBoxLayout()
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.moveToDirCompare = QCheckBox(Storage)
        self.moveToDirCompare.setObjectName(u"moveToDirCompare")

        self.verticalLayout_6.addWidget(self.moveToDirCompare)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.moveToDirCompareOld = QCheckBox(Storage)
        self.moveToDirCompareOld.setObjectName(u"moveToDirCompareOld")

        self.horizontalLayout_5.addWidget(self.moveToDirCompareOld)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.putDownSerialNum = QRadioButton(Storage)
        self.buttonGroup = QButtonGroup(Storage)
        self.buttonGroup.setObjectName(u"buttonGroup")
        self.buttonGroup.addButton(self.putDownSerialNum)
        self.putDownSerialNum.setObjectName(u"putDownSerialNum")
        self.putDownSerialNum.setEnabled(False)
        self.putDownSerialNum.setChecked(True)

        self.verticalLayout.addWidget(self.putDownSerialNum)

        self.putDownDateTime = QRadioButton(Storage)
        self.buttonGroup.addButton(self.putDownDateTime)
        self.putDownDateTime.setObjectName(u"putDownDateTime")
        self.putDownDateTime.setEnabled(False)

        self.verticalLayout.addWidget(self.putDownDateTime)


        self.horizontalLayout_5.addLayout(self.verticalLayout)


        self.verticalLayout_6.addLayout(self.horizontalLayout_5)


        self.verticalLayout_7.addLayout(self.verticalLayout_6)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.moveLog = QRadioButton(Storage)
        self.buttonGroup_2 = QButtonGroup(Storage)
        self.buttonGroup_2.setObjectName(u"buttonGroup_2")
        self.buttonGroup_2.addButton(self.moveLog)
        self.moveLog.setObjectName(u"moveLog")
        self.moveLog.setChecked(True)

        self.verticalLayout_2.addWidget(self.moveLog)

        self.dontTouchLog = QRadioButton(Storage)
        self.buttonGroup_2.addButton(self.dontTouchLog)
        self.dontTouchLog.setObjectName(u"dontTouchLog")

        self.verticalLayout_2.addWidget(self.dontTouchLog)

        self.removeLog = QRadioButton(Storage)
        self.buttonGroup_2.addButton(self.removeLog)
        self.removeLog.setObjectName(u"removeLog")

        self.verticalLayout_2.addWidget(self.removeLog)


        self.verticalLayout_7.addLayout(self.verticalLayout_2)

        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.copyFilesTo = QCheckBox(Storage)
        self.copyFilesTo.setObjectName(u"copyFilesTo")

        self.verticalLayout_3.addWidget(self.copyFilesTo)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_toCopyPath = QLabel(Storage)
        self.label_toCopyPath.setObjectName(u"label_toCopyPath")
        self.label_toCopyPath.setEnabled(False)

        self.horizontalLayout_6.addWidget(self.label_toCopyPath)

        self.toCopyPath = QComboBox(Storage)
        self.toCopyPath.addItem("")
        self.toCopyPath.setObjectName(u"toCopyPath")
        self.toCopyPath.setEnabled(False)
        self.toCopyPath.setMinimumSize(QSize(420, 0))
        self.toCopyPath.setEditable(True)

        self.horizontalLayout_6.addWidget(self.toCopyPath)

        self.toPathBtn = QPushButton(Storage)
        self.toPathBtn.setObjectName(u"toPathBtn")
        self.toPathBtn.setEnabled(False)
        self.toPathBtn.setMaximumSize(QSize(40, 24))

        self.horizontalLayout_6.addWidget(self.toPathBtn)


        self.verticalLayout_3.addLayout(self.horizontalLayout_6)


        self.verticalLayout_7.addLayout(self.verticalLayout_3)

        self.saveInputData = QCheckBox(Storage)
        self.saveInputData.setObjectName(u"saveInputData")
        self.saveInputData.setChecked(True)

        self.verticalLayout_7.addWidget(self.saveInputData)

        self.buttonBox = QDialogButtonBox(Storage)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout_7.addWidget(self.buttonBox)


        self.retranslateUi(Storage)
        self.buttonBox.accepted.connect(Storage.accept)
        self.buttonBox.rejected.connect(Storage.reject)

        QMetaObject.connectSlotsByName(Storage)
    # setupUi

    def retranslateUi(self, Storage):
        Storage.setWindowTitle(QCoreApplication.translate("Storage", u"\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0430", None))
        self.label_patch.setText(QCoreApplication.translate("Storage", u"\u041f\u0443\u0442\u044c \u0434\u043e patch.pck:", None))
        self.patchBtn.setText(QCoreApplication.translate("Storage", u"...", None))
        self.insertTwoWhitespace.setText(QCoreApplication.translate("Storage", u"\u041f\u0440\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u044e\u0449\u0438\u0435 \u0434\u0432\u0430 \u043f\u0440\u043e\u0431\u0435\u043b\u0430 \u0432 patch.pck", None))
        self.label_scheme_one.setText(QCoreApplication.translate("Storage", u"\u041e\u0441\u043d\u043e\u0432\u043d\u0430\u044f \u0441\u0445\u0435\u043c\u0430 \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u043a\u0438:", None))
        self.schemeOne_text.setItemText(0, "")

        self.schemeTwo.setText(QCoreApplication.translate("Storage", u"\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u0430\u044f \u0441\u0445\u0435\u043c\u0430:", None))
        self.schemeTwo_text.setItemText(0, "")

        self.runCompare.setText(QCoreApplication.translate("Storage", u"\u0417\u0430\u043f\u0443\u0441\u043a\u0430\u0442\u044c \u0441\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449, \u0441 \u043f\u043e\u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u043c \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u043c \u043e \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u0438 \u0440\u0430\u0431\u043e\u0442\u044b", None))
        self.rename.setText(QCoreApplication.translate("Storage", u"\u041f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u044b\u0432\u0430\u0442\u044c \u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0435 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0435 \u0432:", None))
        self.rename_text.setText(QCoreApplication.translate("Storage", u"patch.zip", None))
        self.moveToDirCompare.setText(QCoreApplication.translate("Storage", u"\u041f\u0435\u0440\u0435\u043c\u0435c\u0442\u0438\u0442\u044c \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0435(-\u0430) \u0432 \u043f\u0430\u043f\u043a\u0443 \"\u0441ompare\"", None))
        self.moveToDirCompareOld.setText(QCoreApplication.translate("Storage", u"\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0435 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0435(-\u0430) \u043f\u0435\u0440\u0435\u043c\u0435\u0449\u0430\u0442\u044c \u0432 \"compare_old\"", None))
        self.putDownSerialNum.setText(QCoreApplication.translate("Storage", u"\u041f\u0440\u043e\u0441\u0442\u0430\u0432\u043b\u044f\u0442\u044c \u043f\u043e\u0440\u044f\u0434\u043a\u043e\u0432\u044b\u0439 \u043d\u043e\u043c\u0435\u0440", None))
        self.putDownDateTime.setText(QCoreApplication.translate("Storage", u"\u041f\u0440\u043e\u0441\u0442\u0430\u0432\u043b\u044f\u0442\u044c \u0434\u0430\u0442\u0443 \u0438 \u0432\u0440\u0435\u043c\u044f", None))
        self.moveLog.setText(QCoreApplication.translate("Storage", u"\u041f\u0435\u0440\u0435\u043d\u043e\u0441\u0438\u0442\u044c *.log \u0432 \u043f\u0430\u043f\u043a\u0443 log", None))
        self.dontTouchLog.setText(QCoreApplication.translate("Storage", u"\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u0434\u0435\u043b\u0430\u0442\u044c \u0441 *.log", None))
        self.removeLog.setText(QCoreApplication.translate("Storage", u"\u0423\u0434\u0430\u043b\u044f\u0442\u044c *.log", None))
        self.copyFilesTo.setText(QCoreApplication.translate("Storage", u"\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c compare, compare_old, patch.zip, patch.pck, delete.pck (\u0435\u0441\u043b\u0438 \u0435\u0441\u0442\u044c \u0444\u0430\u0439\u043b\u044b)", None))
        self.label_toCopyPath.setText(QCoreApplication.translate("Storage", u"\u041f\u0443\u0442\u044c \u0434\u043b\u044f \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f:", None))
        self.toCopyPath.setItemText(0, "")

        self.toPathBtn.setText(QCoreApplication.translate("Storage", u"...", None))
        self.saveInputData.setText(QCoreApplication.translate("Storage", u"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0432\u0432\u0435\u0434\u0451\u043d\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0434\u043b\u044f \u0434\u0430\u043d\u043d\u043e\u0439 \u0437\u0430\u044f\u0432\u043a\u0438. (\u0415\u0441\u043b\u0438 \u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043e, \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u044e\u0442\u0441\u044f \u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0435)", None))
    # retranslateUi

