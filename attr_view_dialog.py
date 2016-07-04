# -*- coding: utf-8 -*-
"""
/***************************************************************************
 attr_view_dialog
                                 A QGIS plugin
 Plugin for Manage NGII map jobs
                             -------------------
        begin                : 2016-04-21
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Gaia3D
        email                : jangbi882@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic
from ui.attr_view_dialog_base import Ui_Form
# FORM_CLASS, _ = uic.loadUiType(os.path.join(
#     os.path.dirname(__file__), 'test_ui_dialog_base.ui'))


class DiaAttrView(QtGui.QDialog, Ui_Form):
    def __init__(self,
                 plugin  # type: NgiiMapJobManager
                 ):
        """Constructor."""
        parent = plugin.iface.mainWindow()
        super(DiaAttrView, self).__init__(parent)
        self.plugin = plugin
        self.setupUi(self)
        self.connectFct()

    def connectFct(self):
        self.btn_ok.clicked.connect(self.closeWindow)

    def closeWindow(self):
        self.close()
