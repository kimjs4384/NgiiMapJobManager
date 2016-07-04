# -*- coding: utf-8 -*-

from PyQt4.QtGui import *
from PyQt4.QtCore import *


class WidgetContainer(object):

    def __init__(self, iface, classTemplet, dockType=Qt.RightDockWidgetArea, parent=None):
        self.__iface = iface
        self.__dockwidget = None
        self.__oloWidget = None
        self.__classTemplet = classTemplet
        self.__title = classTemplet.title
        self.__objectName = classTemplet.objectName
        self.__dockType = dockType
        self.parent = parent

    # Private
    def __setDocWidget(self):
        self.__dockwidget = QDockWidget(self.__title, self.__iface.mainWindow() )
        self.__dockwidget.setObjectName(self.__objectName)
        self.__oloWidget = self.__classTemplet(self.__iface, self.__dockwidget, self.parent)
        self.__dockwidget.setWidget(self.__oloWidget)
        # self.__oloWidget.updateGuiLayerList()

    def __initGui(self):
        self.__setDocWidget()
        self.__iface.addDockWidget(self.__dockType, self.__dockwidget)

    def __unload(self):
        self.__dockwidget.close()
        self.__iface.removeDockWidget( self.__dockwidget )
        del self.__oloWidget
        self.__dockwidget = None

    # Public
    def setVisible(self, visible):
        if visible:
            if self.__dockwidget is None:
                self.__initGui()
        else:
            if not self.__dockwidget is None:
                self.__unload()
    # TODO: reflash
    def repaint(self):
        if self.__dockwidget:
            self.__dockwidget.update()
            self.__dockwidget.repaint()
