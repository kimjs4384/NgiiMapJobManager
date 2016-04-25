# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NgiiMapJobManagerDialog
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
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import psycopg2
import time

from ui.receive_dialog_base import Ui_Dialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/receive.ui'))


# class DlgReceive(QtGui.QDialog, FORM_CLASS):
class DlgReceive(QtGui.QDialog, Ui_Dialog):
    def __init__(self,
                 plugin  # type: NgiiMapJobManager
                 ):
        """Constructor."""
        parent = plugin.iface.mainWindow()
        super(DlgReceive, self).__init__(parent)
        self.plugin = plugin
        self.conn = plugin.conn

        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setInitValue()
        self.connectFct()

    def connectFct(self):
        self.btn_search.clicked.connect(self.hdrClickBtnSearch)
        self.btn_select_folder.clicked.connect(self.hdrClickBtnSelectFolder)
        self.btn_upload.clicked.connect(self.hdrClickBtnUpload)
        self.btn_inspect.clicked.connect(self.hdrClickBtnInspect)

    def setInitValue(self):
        self.fillWorkerList()

        crrDate = QDate.currentDate()
        self.date_mapext_dttm.setDate(crrDate)
        self.date_mapext_dttm_2 .setDate(crrDate)
        self.progressBar.hide()
        self.lbl_progress.hide()

        self.btn_upload.setDisabled(False)
        self.btn_inspect.setDisabled(True)

    def hdrClickBtnSearch(self):
        workerName = self.cmb_worker_nm.currentText()
        startDate = self.date_mapext_dttm.date()
        endDate = self.date_mapext_dttm_2.date()
        self.searchExtjob(workerName, startDate, endDate)

    def hdrClickBtnSelectFolder(self):
        folderPath = QFileDialog.getExistingDirectory(self.plugin.iface.mainWindow(), u'납품받은 데이터가 있는 폴더를 선택해 주십시오.')
        if folderPath:
            self.dataFolder = folderPath
            self.edt_data_folder.setText(folderPath)

    def hdrClickBtnUpload(self):
        self.progressBar.show()
        self.lbl_progress.show()

        # TODO: 실제로 데이터 올리는 루틴 작성 필요
        for i in range(10):
            progress = i * 10
            self.progressBar.setValue(progress)
            self.lbl_progress.setText(u"납품 데이터 올리기 진행중...{}%".format(progress))
            time.sleep(1)
        self.progressBar.hide()
        self.lbl_progress.hide()

        self.btn_upload.setDisabled(True)
        self.btn_inspect.setDisabled(False)

    def hdrClickBtnInspect(self):
        rc = QMessageBox.question(self, u"확인", u"납품받은 데이터의 검수를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc == QMessageBox.Yes:
            self.plugin.showWidgetInspect()
            self.close()

    def fillWorkerList(self):
        # TODO: 실제로 DB에서 자료 불러오게 수정
        self.cmb_worker_nm.clear()
        self.cmb_worker_nm.addItem(u'중앙항업')
        self.cmb_worker_nm.addItem(u'한진항업')
        self.cmb_worker_nm.addItem(u'범아항업')
        self.cmb_worker_nm.addItem(u'삼아항업')
        self.cmb_worker_nm.setCurrentIndex(0)

    def searchExtjob(self, workerName, startDate, endDate):
        try:
            # TODO: 날짜 조건이 잘 안맞는 문제 해결
            cur = self.plugin.conn.cursor()
            sql = u"SELECT extjob_id, extjob_nm FROM extjob.extjob_main " \
                  u"WHERE worker_nm = %s and mapext_dttm BETWEEN %s and %s"
            cur.execute(sql, (workerName,
                        u"{} 00:00:00".format(startDate.toString('yyyy-M-d')),
                        u"{} 23:59:59.9999".format(endDate.toString('yyyy-M-d'))))
            results = cur.fetchall()
            self.cmb_extjob_nm.clear()
            if not results or len(results) <= 0:
                QMessageBox.warning(self, u"검색실패", u"조건에 맞는 작업이 없습니다.")
                return

            for result in results:
                extjob_id = result[0]
                extjob_nm = result[1]
                self.cmb_extjob_nm.addItem(extjob_nm)
                self.cmb_extjob_nm.setItemData(self.cmb_extjob_nm.count(), extjob_id)
        except Exception as e:
            QMessageBox.warning(self, "SQL ERROR", str(e))
