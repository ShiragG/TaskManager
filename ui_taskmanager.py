# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_taskmanager.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpacerItem, QStackedWidget, QTabWidget, QVBoxLayout,
    QWidget)
import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(940, 450)
        icon = QIcon()
        icon.addFile(u":/icons/src/icons/ico/light/paw.ico", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        MainWindow.setStyleSheet(u"*{\n"
"	\n"
"}\n"
"#leftMenuSubContainer{\n"
"	background-color:rgb(65, 87, 122)\n"
"}\n"
"#leftMenu{\n"
"	background-color: rgb(100, 135, 188)\n"
"}\n"
"#headerContainer{\n"
"	background-color: rgb(65, 87, 122);\n"
"}\n"
"#notificationContent{\n"
"	background-color: rgb(192, 220, 255);\n"
"	border-radius:10px;\n"
"	\n"
"}\n"
"\n"
"QToolTip { \n"
"	background-color: white; \n"
"	color: black; \n"
"	border: black solid 1px\n"
"}")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.leftMenuContainer = QWidget(self.centralwidget)
        self.leftMenuContainer.setObjectName(u"leftMenuContainer")
        self.leftMenuContainer.setStyleSheet(u"QPushButton{\n"
"	padding: 2px 5px;\n"
"\n"
"	\n"
"	background-color:transparent;\n"
"	padding: 0;\n"
"	margin:0;\n"
"	\n"
"}\n"
"QPushButton:hover{\n"
"	background-color: rgb(235, 235, 235);\n"
"	left: -2px;\n"
"}\n"
"")
        self.horizontalLayout_2 = QHBoxLayout(self.leftMenuContainer)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.leftMenuSubContainer = QWidget(self.leftMenuContainer)
        self.leftMenuSubContainer.setObjectName(u"leftMenuSubContainer")
        self.verticalLayout = QVBoxLayout(self.leftMenuSubContainer)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.leftMenuSubContainer)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(6, 6, 6, 6)
        self.menuBtn = QPushButton(self.frame)
        self.menuBtn.setObjectName(u"menuBtn")
        self.menuBtn.setMinimumSize(QSize(40, 40))
        self.menuBtn.setMaximumSize(QSize(40, 40))
        icon1 = QIcon()
        icon1.addFile(u":/icons/src/icons/png/light/menu.png", QSize(), QIcon.Normal, QIcon.Off)
        self.menuBtn.setIcon(icon1)
        self.menuBtn.setIconSize(QSize(24, 24))

        self.verticalLayout_2.addWidget(self.menuBtn)


        self.verticalLayout.addWidget(self.frame, 0, Qt.AlignTop)

        self.frame_6 = QFrame(self.leftMenuSubContainer)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.StyledPanel)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_8 = QVBoxLayout(self.frame_6)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.settingsBtn = QPushButton(self.frame_6)
        self.settingsBtn.setObjectName(u"settingsBtn")
        self.settingsBtn.setMinimumSize(QSize(40, 40))
        self.settingsBtn.setMaximumSize(QSize(40, 40))
        icon2 = QIcon()
        icon2.addFile(u":/icons/src/icons/png/light/gear.png", QSize(), QIcon.Normal, QIcon.Off)
        self.settingsBtn.setIcon(icon2)
        self.settingsBtn.setIconSize(QSize(24, 24))

        self.verticalLayout_8.addWidget(self.settingsBtn)

        self.infoBtn = QPushButton(self.frame_6)
        self.infoBtn.setObjectName(u"infoBtn")
        self.infoBtn.setMinimumSize(QSize(40, 40))
        self.infoBtn.setMaximumSize(QSize(40, 40))
        icon3 = QIcon()
        icon3.addFile(u":/icons/src/icons/png/light/info.png", QSize(), QIcon.Normal, QIcon.Off)
        self.infoBtn.setIcon(icon3)
        self.infoBtn.setIconSize(QSize(24, 24))

        self.verticalLayout_8.addWidget(self.infoBtn)


        self.verticalLayout.addWidget(self.frame_6, 0, Qt.AlignBottom)


        self.horizontalLayout_2.addWidget(self.leftMenuSubContainer, 0, Qt.AlignLeft)

        self.leftMenu = QWidget(self.leftMenuContainer)
        self.leftMenu.setObjectName(u"leftMenu")
        self.verticalLayout_3 = QVBoxLayout(self.leftMenu)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(6, 6, 6, 6)
        self.frame_2 = QFrame(self.leftMenu)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_2)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.menuContents = QStackedWidget(self.frame_2)
        self.menuContents.setObjectName(u"menuContents")
        self.menuContents.setLayoutDirection(Qt.LeftToRight)
        self.modulesPage = QWidget()
        self.modulesPage.setObjectName(u"modulesPage")
        self.modulesPage.setLayoutDirection(Qt.LeftToRight)
        self.verticalLayout_10 = QVBoxLayout(self.modulesPage)
        self.verticalLayout_10.setSpacing(0)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.verticalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_16 = QVBoxLayout()
        self.verticalLayout_16.setSpacing(10)
        self.verticalLayout_16.setObjectName(u"verticalLayout_16")
        self.verticalLayout_16.setContentsMargins(-1, 0, -1, -1)
        self.label = QLabel(self.modulesPage)
        self.label.setObjectName(u"label")
        self.label.setMaximumSize(QSize(16777215, 40))
        font = QFont()
        font.setPointSize(14)
        self.label.setFont(font)

        self.verticalLayout_16.addWidget(self.label)

        self.showTasksBtn = QPushButton(self.modulesPage)
        self.showTasksBtn.setObjectName(u"showTasksBtn")
        self.showTasksBtn.setMinimumSize(QSize(0, 30))
        font1 = QFont()
        font1.setPointSize(12)
        self.showTasksBtn.setFont(font1)

        self.verticalLayout_16.addWidget(self.showTasksBtn)

        self.showActiveTasksBtn = QPushButton(self.modulesPage)
        self.showActiveTasksBtn.setObjectName(u"showActiveTasksBtn")
        self.showActiveTasksBtn.setMinimumSize(QSize(0, 30))
        self.showActiveTasksBtn.setFont(font1)

        self.verticalLayout_16.addWidget(self.showActiveTasksBtn)

        self.showPotBtn = QPushButton(self.modulesPage)
        self.showPotBtn.setObjectName(u"showPotBtn")
        self.showPotBtn.setMinimumSize(QSize(0, 30))
        self.showPotBtn.setFont(font1)

        self.verticalLayout_16.addWidget(self.showPotBtn)


        self.verticalLayout_10.addLayout(self.verticalLayout_16)

        self.menuContents.addWidget(self.modulesPage)
        self.settingsPage = QWidget()
        self.settingsPage.setObjectName(u"settingsPage")
        self.verticalLayout_14 = QVBoxLayout(self.settingsPage)
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")
        self.label_6 = QLabel(self.settingsPage)
        self.label_6.setObjectName(u"label_6")

        self.verticalLayout_14.addWidget(self.label_6)

        self.generalBtn = QPushButton(self.settingsPage)
        self.generalBtn.setObjectName(u"generalBtn")

        self.verticalLayout_14.addWidget(self.generalBtn)

        self.connectionBtn = QPushButton(self.settingsPage)
        self.connectionBtn.setObjectName(u"connectionBtn")

        self.verticalLayout_14.addWidget(self.connectionBtn)

        self.otherBtn = QPushButton(self.settingsPage)
        self.otherBtn.setObjectName(u"otherBtn")

        self.verticalLayout_14.addWidget(self.otherBtn)

        self.menuContents.addWidget(self.settingsPage)
        self.page = QWidget()
        self.page.setObjectName(u"page")
        self.verticalLayout_15 = QVBoxLayout(self.page)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.label_7 = QLabel(self.page)
        self.label_7.setObjectName(u"label_7")

        self.verticalLayout_15.addWidget(self.label_7)

        self.plainTextEdit = QPlainTextEdit(self.page)
        self.plainTextEdit.setObjectName(u"plainTextEdit")
        self.plainTextEdit.setEnabled(False)

        self.verticalLayout_15.addWidget(self.plainTextEdit)

        self.menuContents.addWidget(self.page)

        self.verticalLayout_4.addWidget(self.menuContents, 0, Qt.AlignHCenter|Qt.AlignTop)


        self.verticalLayout_3.addWidget(self.frame_2)


        self.horizontalLayout_2.addWidget(self.leftMenu)


        self.horizontalLayout.addWidget(self.leftMenuContainer, 0, Qt.AlignLeft)

        self.mainBodyContainer = QWidget(self.centralwidget)
        self.mainBodyContainer.setObjectName(u"mainBodyContainer")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.mainBodyContainer.sizePolicy().hasHeightForWidth())
        self.mainBodyContainer.setSizePolicy(sizePolicy)
        self.verticalLayout_5 = QVBoxLayout(self.mainBodyContainer)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 3)
        self.headerContainer = QWidget(self.mainBodyContainer)
        self.headerContainer.setObjectName(u"headerContainer")
        self.headerContainer.setStyleSheet(u"QPushButton{\n"
"	padding: 2px 5px;\n"
"\n"
"	background-color:transparent;\n"
"	padding: 0;\n"
"	margin:0;\n"
"	\n"
"}\n"
"QPushButton:hover{\n"
"	background-color: rgb(235, 235, 235);\n"
"	left: -2px;\n"
"}\n"
"QPushButton::menu-indicator {\n"
"	 image: none;\n"
"}")
        self.horizontalLayout_5 = QHBoxLayout(self.headerContainer)
        self.horizontalLayout_5.setSpacing(0)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.frame_4 = QFrame(self.headerContainer)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(6, 6, 6, 6)
        self.actionBtn = QPushButton(self.frame_4)
        self.actionBtn.setObjectName(u"actionBtn")
        self.actionBtn.setMinimumSize(QSize(40, 40))
        self.actionBtn.setMaximumSize(QSize(40, 40))
        icon4 = QIcon()
        icon4.addFile(u":/icons/src/icons/png/light/action.png", QSize(), QIcon.Normal, QIcon.Off)
        self.actionBtn.setIcon(icon4)
        self.actionBtn.setIconSize(QSize(24, 24))

        self.horizontalLayout_3.addWidget(self.actionBtn)

        self.addBtn = QPushButton(self.frame_4)
        self.addBtn.setObjectName(u"addBtn")
        self.addBtn.setMinimumSize(QSize(40, 40))
        self.addBtn.setMaximumSize(QSize(40, 40))
        icon5 = QIcon()
        icon5.addFile(u":/icons/src/icons/png/light/add.png", QSize(), QIcon.Normal, QIcon.Off)
        self.addBtn.setIcon(icon5)
        self.addBtn.setIconSize(QSize(24, 24))

        self.horizontalLayout_3.addWidget(self.addBtn)

        self.removeBtn = QPushButton(self.frame_4)
        self.removeBtn.setObjectName(u"removeBtn")
        self.removeBtn.setMinimumSize(QSize(40, 40))
        self.removeBtn.setMaximumSize(QSize(40, 40))
        icon6 = QIcon()
        icon6.addFile(u":/icons/src/icons/png/light/remove.png", QSize(), QIcon.Normal, QIcon.Off)
        self.removeBtn.setIcon(icon6)
        self.removeBtn.setIconSize(QSize(24, 24))

        self.horizontalLayout_3.addWidget(self.removeBtn)

        self.editBtn = QPushButton(self.frame_4)
        self.editBtn.setObjectName(u"editBtn")
        self.editBtn.setMinimumSize(QSize(40, 40))
        self.editBtn.setMaximumSize(QSize(40, 40))
        icon7 = QIcon()
        icon7.addFile(u":/icons/src/icons/png/light/edit.png", QSize(), QIcon.Normal, QIcon.Off)
        self.editBtn.setIcon(icon7)
        self.editBtn.setIconSize(QSize(24, 24))

        self.horizontalLayout_3.addWidget(self.editBtn)


        self.horizontalLayout_5.addWidget(self.frame_4)

        self.horizontalSpacer = QSpacerItem(100, 20, QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer)

        self.frame_5 = QFrame(self.headerContainer)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.StyledPanel)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_5)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.notificationBtn = QPushButton(self.frame_5)
        self.notificationBtn.setObjectName(u"notificationBtn")
        self.notificationBtn.setMinimumSize(QSize(40, 40))
        self.notificationBtn.setMaximumSize(QSize(40, 40))
        icon8 = QIcon()
        icon8.addFile(u":/icons/src/icons/png/light/bell.png", QSize(), QIcon.Normal, QIcon.Off)
        self.notificationBtn.setIcon(icon8)
        self.notificationBtn.setIconSize(QSize(24, 24))

        self.horizontalLayout_4.addWidget(self.notificationBtn)


        self.horizontalLayout_5.addWidget(self.frame_5)


        self.verticalLayout_5.addWidget(self.headerContainer)

        self.notificationContent = QWidget(self.mainBodyContainer)
        self.notificationContent.setObjectName(u"notificationContent")
        font2 = QFont()
        font2.setPointSize(10)
        self.notificationContent.setFont(font2)
        self.verticalLayout_6 = QVBoxLayout(self.notificationContent)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.frame_3 = QFrame(self.notificationContent)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.frame_3)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.label_2 = QLabel(self.frame_3)
        self.label_2.setObjectName(u"label_2")

        self.verticalLayout_7.addWidget(self.label_2)


        self.verticalLayout_6.addWidget(self.frame_3)


        self.verticalLayout_5.addWidget(self.notificationContent)

        self.mainBodyContent = QWidget(self.mainBodyContainer)
        self.mainBodyContent.setObjectName(u"mainBodyContent")
        self.verticalLayout_9 = QVBoxLayout(self.mainBodyContent)
        self.verticalLayout_9.setSpacing(0)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(0, 0, 0, 0)
        self.mainContents = QStackedWidget(self.mainBodyContent)
        self.mainContents.setObjectName(u"mainContents")
        self.taskManagerPage = QWidget()
        self.taskManagerPage.setObjectName(u"taskManagerPage")
        self.verticalLayout_11 = QVBoxLayout(self.taskManagerPage)
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.horizontalLayout_7 = QHBoxLayout()
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.label_4 = QLabel(self.taskManagerPage)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setFont(font1)

        self.horizontalLayout_7.addWidget(self.label_4)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_2)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_9 = QLabel(self.taskManagerPage)
        self.label_9.setObjectName(u"label_9")

        self.horizontalLayout_6.addWidget(self.label_9)

        self.task_status = QComboBox(self.taskManagerPage)
        self.task_status.addItem("")
        self.task_status.addItem("")
        self.task_status.addItem("")
        self.task_status.setObjectName(u"task_status")

        self.horizontalLayout_6.addWidget(self.task_status)


        self.horizontalLayout_7.addLayout(self.horizontalLayout_6)


        self.verticalLayout_11.addLayout(self.horizontalLayout_7)

        self.taskManagerTab = QTabWidget(self.taskManagerPage)
        self.taskManagerTab.setObjectName(u"taskManagerTab")

        self.verticalLayout_11.addWidget(self.taskManagerTab)

        self.mainContents.addWidget(self.taskManagerPage)
        self.activeTaskPage = QWidget()
        self.activeTaskPage.setObjectName(u"activeTaskPage")
        self.verticalLayout_12 = QVBoxLayout(self.activeTaskPage)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.label_3 = QLabel(self.activeTaskPage)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font1)

        self.verticalLayout_12.addWidget(self.label_3)

        self.activeTaskTab = QTabWidget(self.activeTaskPage)
        self.activeTaskTab.setObjectName(u"activeTaskTab")

        self.verticalLayout_12.addWidget(self.activeTaskTab)

        self.mainContents.addWidget(self.activeTaskPage)
        self.potPage = QWidget()
        self.potPage.setObjectName(u"potPage")
        self.verticalLayout_13 = QVBoxLayout(self.potPage)
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.label_5 = QLabel(self.potPage)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setFont(font1)

        self.verticalLayout_13.addWidget(self.label_5)

        self.potTab = QTabWidget(self.potPage)
        self.potTab.setObjectName(u"potTab")

        self.verticalLayout_13.addWidget(self.potTab)

        self.mainContents.addWidget(self.potPage)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.verticalLayout_17 = QVBoxLayout(self.page_2)
        self.verticalLayout_17.setObjectName(u"verticalLayout_17")
        self.label_8 = QLabel(self.page_2)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFont(font1)

        self.verticalLayout_17.addWidget(self.label_8)

        self.listWidget = QListWidget(self.page_2)
        self.listWidget.setObjectName(u"listWidget")

        self.verticalLayout_17.addWidget(self.listWidget)

        self.mainContents.addWidget(self.page_2)

        self.verticalLayout_9.addWidget(self.mainContents)


        self.verticalLayout_5.addWidget(self.mainBodyContent)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setSpacing(6)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(-1, -1, -1, 5)
        self.label_action_now = QLabel(self.mainBodyContainer)
        self.label_action_now.setObjectName(u"label_action_now")
        self.label_action_now.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_8.addWidget(self.label_action_now)

        self.progressBar = QProgressBar(self.mainBodyContainer)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setMaximumSize(QSize(150, 16777215))
        self.progressBar.setValue(24)

        self.horizontalLayout_8.addWidget(self.progressBar)


        self.verticalLayout_5.addLayout(self.horizontalLayout_8)


        self.horizontalLayout.addWidget(self.mainBodyContainer)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.menuContents.setCurrentIndex(0)
        self.mainContents.setCurrentIndex(0)
        self.taskManagerTab.setCurrentIndex(-1)
        self.activeTaskTab.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Task Manager", None))
#if QT_CONFIG(tooltip)
        self.menuBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0421\u043f\u0438\u0441\u043e\u043a \u043c\u043e\u0434\u0443\u043b\u0435\u0439", None))
#endif // QT_CONFIG(tooltip)
        self.menuBtn.setText("")
#if QT_CONFIG(tooltip)
        self.settingsBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", None))
#endif // QT_CONFIG(tooltip)
        self.settingsBtn.setText("")
#if QT_CONFIG(tooltip)
        self.infoBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043e \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435", None))
#endif // QT_CONFIG(tooltip)
        self.infoBtn.setText("")
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u041c\u043e\u0434\u0443\u043b\u0438", None))
        self.showTasksBtn.setText(QCoreApplication.translate("MainWindow", u"\u0412\u0435\u0434\u0435\u043d\u0438\u0435 \u0437\u0430\u044f\u0432\u043e\u043a", None))
        self.showActiveTasksBtn.setText(QCoreApplication.translate("MainWindow", u"\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0437\u0430\u044f\u0432\u043a\u0438", None))
        self.showPotBtn.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u0442\u0451\u043b", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"\u0420\u0430\u0437\u0434\u0435\u043b\u044b \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043a", None))
        self.generalBtn.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435", None))
        self.connectionBtn.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043e\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u0435", None))
        self.otherBtn.setText(QCoreApplication.translate("MainWindow", u"\u0414\u0440\u0443\u0433\u043e\u0435", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"\u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043e \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0438", None))
        self.plainTextEdit.setPlainText(QCoreApplication.translate("MainWindow", u"\u0412\u0435\u0440\u0441\u0438\u044f \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f: 2024_04_10", None))
#if QT_CONFIG(tooltip)
        self.actionBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u044f", None))
#endif // QT_CONFIG(tooltip)
        self.actionBtn.setText("")
#if QT_CONFIG(tooltip)
        self.addBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c", None))
#endif // QT_CONFIG(tooltip)
        self.addBtn.setText("")
#if QT_CONFIG(tooltip)
        self.removeBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0423\u0431\u0440\u0430\u0442\u044c", None))
#endif // QT_CONFIG(tooltip)
        self.removeBtn.setText("")
#if QT_CONFIG(tooltip)
        self.editBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", None))
#endif // QT_CONFIG(tooltip)
        self.editBtn.setText("")
#if QT_CONFIG(tooltip)
        self.notificationBtn.setToolTip(QCoreApplication.translate("MainWindow", u"\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f", None))
#endif // QT_CONFIG(tooltip)
        self.notificationBtn.setText("")
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"\u0412\u0435\u0434\u0435\u043d\u0438\u0435 \u0437\u0430\u044f\u0432\u043e\u043a", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c:", None))
        self.task_status.setItemText(0, QCoreApplication.translate("MainWindow", u"\u041d\u0435 \u0441\u043a\u0440\u044b\u0442\u044b\u0435", None))
        self.task_status.setItemText(1, QCoreApplication.translate("MainWindow", u"\u0421\u043a\u0440\u044b\u0442\u044b\u0435", None))
        self.task_status.setItemText(2, QCoreApplication.translate("MainWindow", u"\u0412\u0441\u0435", None))

        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0437\u0430\u044f\u0432\u043a\u0438", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u0442\u0451\u043b", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", None))
        self.label_action_now.setText(QCoreApplication.translate("MainWindow", u"\u0422\u0435\u043a\u0443\u0449\u0435\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435", None))
    # retranslateUi

