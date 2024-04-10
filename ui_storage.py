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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QWidget)

class Ui_Storage(object):
    def setupUi(self, Storage):
        if not Storage.objectName():
            Storage.setObjectName(u"Storage")
        Storage.resize(651, 438)
        self.buttonBox = QDialogButtonBox(Storage)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setGeometry(QRect(250, 380, 341, 32))
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.widget = QWidget(Storage)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(10, 20, 561, 26))
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.label_patch = QLabel(self.widget)
        self.label_patch.setObjectName(u"label_patch")

        self.horizontalLayout.addWidget(self.label_patch)

        self.patchPath = QLineEdit(self.widget)
        self.patchPath.setObjectName(u"patchPath")
        self.patchPath.setMinimumSize(QSize(400, 0))

        self.horizontalLayout.addWidget(self.patchPath)

        self.patchBtn = QPushButton(self.widget)
        self.patchBtn.setObjectName(u"patchBtn")
        self.patchBtn.setMaximumSize(QSize(40, 40))

        self.horizontalLayout.addWidget(self.patchBtn)


        self.retranslateUi(Storage)
        self.buttonBox.accepted.connect(Storage.accept)
        self.buttonBox.rejected.connect(Storage.reject)

        QMetaObject.connectSlotsByName(Storage)
    # setupUi

    def retranslateUi(self, Storage):
        Storage.setWindowTitle(QCoreApplication.translate("Storage", u"\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0430", None))
        self.label_patch.setText(QCoreApplication.translate("Storage", u"\u041f\u0443\u0442\u044c \u0434\u043e patch.pck:", None))
        self.patchBtn.setText(QCoreApplication.translate("Storage", u"...", None))
    # retranslateUi

