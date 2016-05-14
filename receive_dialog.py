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
from subprocess import check_output
import sys

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

        # 수령 데이터 import
        self.importRecData()
            # TODO: 실제로 데이터 올리는 루틴 작성 필요
        for i in range(10):
            progress = i * 10
            self.progressBar.setValue(progress)
            self.lbl_progress.setText(u"납품 데이터 올리기 진행중...{}%".format(progress))
            time.sleep(1)
        self.btn_upload.setDisabled(True)
        self.btn_inspect.setDisabled(False)

        self.progressBar.hide()
        self.lbl_progress.hide()

    def hdrClickBtnInspect(self):
        rc = QMessageBox.question(self, u"확인", u"납품받은 데이터의 검수를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc == QMessageBox.Yes:
            #self.findDiff()
            self.plugin.showWidgetInspect()
            self.close()

    def fillWorkerList(self):
        # TODO: 실제로 DB에서 자료 불러오게 수정 (수정_JS)
        self.cmb_worker_nm.clear()
        self.cmb_worker_nm.addItem('')
        cur = self.plugin.conn.cursor()
        sql = u'SELECT worker_nm FROM extjob.extjob_main group by worker_nm order by worker_nm asc'
        cur.execute(sql)
        workers = cur.fetchall()
        for worker in workers:
            self.cmb_worker_nm.addItem(worker[0])
        self.cmb_worker_nm.setCurrentIndex(0)

        # self.cmb_worker_nm.clear()
        # self.cmb_worker_nm.addItem(u'중앙항업')
        # self.cmb_worker_nm.addItem(u'한진항업')
        # self.cmb_worker_nm.addItem(u'범아항업')
        # self.cmb_worker_nm.addItem(u'삼아항업')
        # self.cmb_worker_nm.setCurrentIndex(0)

    def searchExtjob(self, workerName, startDate, endDate):
        try:
            # TODO: 날짜 조건이 잘 안맞는 문제 해결 ( column type 변경_JS )
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
            QMessageBox.warning(self, u'SQL ERROR', str(e))

    def importRecData(self):
        try:
            # 수령ID, 수령 날짜 생성
            cur = self.conn.cursor()
            sql = "SELECT nextid('RD') as extjob_id, current_timestamp as mapext_dttm"
            cur.execute(sql)
            result = cur.fetchone()
            receive_id = result[0]
            receive_dttm = result[1]
            timestemp = "{}-{}-{} {}:{}:{}.{}" \
                .format(receive_dttm.year, receive_dttm.month, receive_dttm.day,
                        receive_dttm.hour, receive_dttm.minute, receive_dttm.second, receive_dttm.microsecond)

            layer_nm = None

            # TODO: 기본 유휴성 검사?!
            for fileName in os.listdir(self.edt_data_folder.text()):
                # shp 파일을 찾아서 import 수령ID_레이어명
                if os.path.splitext(fileName)[1]=='.shp':
                    layer_nm = os.path.splitext(fileName)[0]
                    table_nm = receive_id + "_" + layer_nm

                    # 윈도우가 아닌 경우 PATH 추가
                    ogr2ogrPath = None
                    if sys.platform == "win32":
                        ogr2ogrPath = ""
                    else:
                        ogr2ogrPath = "/Library/Frameworks/GDAL.framework/Versions/1.11/Programs/"

                    # 수정된 테이블 생성
                    command = u'{}ogr2ogr ' \
                              u'--config SHAPE_ENCODING UTF-8 -append -a_srs EPSG:5179 ' \
                              u'-f PostgreSQL PG:"host=localhost user=postgres dbname=sdmc password=postgres" ' \
                              u'{} -nln extjob.{} -nlt PROMOTE_TO_MULTI '\
                              .format(ogr2ogrPath, os.path.join(self.edt_data_folder.text(),fileName),table_nm)
                    rc = check_output(command.encode(), shell=True)

                    sql = u"alter table extjob.{}_{} rename shape_leng to shape_length; " \
                          u"alter table extjob.{}_{} rename basedata_n to basedata_nm; " \
                          u"alter table extjob.{}_{} rename mapext_dtt to mapext_dttm; " \
                          u"alter table extjob.{}_{} rename basedata_d to basedata_dt"\
                        .format(receive_id,layer_nm,receive_id,layer_nm,
                                receive_id, layer_nm,receive_id,layer_nm)

                    cur.execute(sql)

                    sql = u"ALTER TABLE extjob.{} ADD COLUMN receive_id character varying(16); " \
                          u"UPDATE extjob.{} SET receive_id = '{}';  " \
                          .format(table_nm,table_nm,receive_id)
                    cur.execute(sql)

                    # receive_main import
                    sql = u'SELECT extjob_id FROM extjob.{} ' \
                          u'group by extjob_id having extjob_id is not NULL'.format(table_nm)
                    cur.execute(sql)
                    result_gruop = cur.fetchone()
                    extjob_id = result_gruop[0]

                    sql = u'INSERT INTO extjob.receive_main VALUES(%s, %s, %s, %s)'
                    cur.execute(sql,(receive_id, extjob_id, layer_nm, receive_dttm))

                    # receive_layer import
                    sql = u'INSERT INTO extjob.receive_layer VALUES (%s, %s, %s)'
                    cur.execute(sql,(receive_id, layer_nm, table_nm))

            self.conn.commit()

            return True

        except Exception as e:
            # TODO: 에러 발생시 테이블 삭제하고 진행을 멈춤
            self.conn.rollback()
            QMessageBox.warning(self, u"오류", str(e))

            return False