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
from osgeo import ogr

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
        self.cmb_extjob_nm.currentIndexChanged.connect(self.getWorkArea)

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
        self.cmb_extjob_nm.clear()
        workerName = self.cmb_worker_nm.currentText()
        startDate = self.date_mapext_dttm.date()
        endDate = self.date_mapext_dttm_2.date()
        self.searchExtjob(workerName, startDate, endDate)

    def hdrClickBtnSelectFolder(self):
        # TODO: 폴더가 기억되게 수정
        folderPath = QFileDialog.getExistingDirectory(self.plugin.iface.mainWindow(),
                                                      u'납품받은 데이터가 있는 폴더를 선택해 주십시오.')
        if folderPath:
            self.dataFolder = folderPath
            self.edt_data_folder.setText(folderPath)

    def hdrClickBtnUpload(self):
        self.progressBar.show()
        self.lbl_progress.show()

        # 수령 데이터 import
        if self.importRecData():
            # TODO: 시연을 위한 코드이므로 제거 필요
            for i in range(10):
                progress = i * 10
                self.progressBar.setValue(progress)
                self.lbl_progress.setText(u"납품 데이터 올리기 진행중...{}%".format(progress))
                time.sleep(1)
            self.btn_upload.setDisabled(True)
            self.btn_inspect.setDisabled(False)
            # TODO: 수령 ID 보여주는 로직 추가
            QMessageBox.information(self, u"작업완료", u"납품 데이터 올리기가 완료되었습니다.")

        self.progressBar.hide()
        self.lbl_progress.hide()

    def hdrClickBtnInspect(self):
        rc = QMessageBox.question(self, u"확인", u"납품받은 데이터의 검수를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc == QMessageBox.Yes:
            self.plugin.showWidgetInspect()
            self.close()

    def fillWorkerList(self):
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
            cur = self.plugin.conn.cursor()
            sql = u"SELECT extjob_id, extjob_nm FROM extjob.extjob_main " \
                  u"WHERE worker_nm = %s and mapext_dttm BETWEEN %s and %s"
            cur.execute(sql, (workerName,
                        u"{} 00:00:00".format(startDate.toString('yyyy-M-d')),
                        u"{} 23:59:59.9999".format(endDate.toString('yyyy-M-d'))))
            results = cur.fetchall()
            self.cmb_extjob_nm.clear()
            self.cmb_extjob_nm.addItem(u"작업명을 선택하세요")
            if not results or len(results) <= 0:
                QMessageBox.warning(self, u"검색실패", u"조건에 맞는 작업이 없습니다.")
                return

            for result in results:
                extjob_id = result[0]
                extjob_nm = result[1]
                self.cmb_extjob_nm.addItem(extjob_nm)
                self.cmb_extjob_nm.setItemData(self.cmb_extjob_nm.count()-1, extjob_id)
        except Exception as e:
            QMessageBox.warning(self, u'SQL ERROR', str(e))

    def getWorkArea(self):
        st_model = QStandardItemModel()
        self.lst_workarea.setModel(st_model)

        if self.cmb_extjob_nm.currentIndex() <= 0:
            return

        cur = self.plugin.conn.cursor()
        sql = u"select workarea_txt from extjob.extjob_main where extjob_id = '{}' ;"\
            .format(self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex()))

        cur.execute(sql)
        result = cur.fetchone()

        if result[0] == None or result[0] == '':
            return

        item_list = result[0].split(',')

        for item in item_list:
            str = QStandardItem(item)
            st_model.appendRow(str)

        self.lst_workarea.setModel(st_model)

    def importRecData(self):
        try:
            # 선택된 extjob_id 확보
            extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
            if extjob_id == "":
                QMessageBox.warning(self, u"오류", u"적절한 작업명이 선택되지 않았습니다.")
                return False

            if self.edt_data_folder.text() == "":
                QMessageBox.warning(self, u"오류", u"폴더를 선택해 주시기 바랍니다")
                return False

            # TODO: 기본 칼럼 검사 필요
            if self.checkColumns():

                # 수령ID, 수령 날짜 생성
                cur = self.conn.cursor()
                sql = "SELECT nextid('RD') as receive_id, current_timestamp as mapext_dttm"
                cur.execute(sql)
                result = cur.fetchone()
                if not result:
                    QMessageBox.error(self, u"오류", u"선택한 작업에 해당되는 데이터를 찾지 못했습니다. 관리자에게 문의해 주세요.")
                    return False
                receive_id = result[0]
                receive_dttm = result[1]

                for fileName in os.listdir(self.edt_data_folder.text()):
                    # shp 파일을 찾고, import 수령ID_레이어명
                    if os.path.splitext(fileName)[1]=='.shp':
                        layer_nm = os.path.splitext(fileName)[0]
                        table_nm = receive_id + "_" + layer_nm


                        # 윈도우가 아닌 경우 PATH 추가
                        ogr2ogrPath = None
                        if sys.platform == "win32":
                            ogr2ogrPath = ""
                        else:
                            ogr2ogrPath = "/Library/Frameworks/GDAL.framework/Versions/1.11/Programs/"

                        # TODO: 만들려는 테이블이 이미 있는지 확인하여 있으면 확 지워버림

                        # 수정된 테이블 생성
                        # TODO: dbf 파일의 인코딩 확인하여 결정하게 해야 함
                        command = u'{}ogr2ogr ' \
                                  u'--config SHAPE_ENCODING UTF-8 -append -a_srs EPSG:5179 ' \
                                  u'-f PostgreSQL PG:"host=localhost user=postgres dbname=sdmc password=postgres" ' \
                                  u'{} -nln extjob.{} -nlt PROMOTE_TO_MULTI '\
                                  .format(ogr2ogrPath, os.path.join(self.edt_data_folder.text(),fileName),table_nm)
                        rc = check_output(command.encode(), shell=True)

                        sql = u"alter table extjob.{0}_{1} rename basedata_n to basedata_nm; " \
                              u"alter table extjob.{0}_{1} rename mapext_dtt to mapext_dttm; " \
                              u"alter table extjob.{0}_{1} rename basedata_d to basedata_dt"\
                            .format(receive_id, layer_nm)

                        cur.execute(sql)

                        sql = u"ALTER TABLE extjob.{0} ADD COLUMN receive_id character varying(16); " \
                              u"UPDATE extjob.{0} SET receive_id = '{1}';  " \
                              .format(table_nm, receive_id)
                        cur.execute(sql)

                        # TODO: 파일 내에 여러 extjob_id 가 있는 경우 대비하여 코딩 수정 필요
                        # receive_main import
                        sql = u'SELECT extjob_id FROM extjob.{} ' \
                              u'group by extjob_id having extjob_id is not NULL'.format(table_nm)
                        cur.execute(sql)
                        result_gruop = cur.fetchone()

                        # 사용자가 선택한 extjob_id와 파일의 그것이 다를 때 대응
                        # extjob_id = result_gruop[0]
                        file_extjob_id = result_gruop[0]
                        if extjob_id != file_extjob_id:
                            rc = QMessageBox.question(self, u"경고", u"{} 파일의 외주ID({})가 선택한 작업의 외주ID({})와 다릅니다.\n"
                                                      u"그래도 계속 하시겠습니까?".format(layer_nm, file_extjob_id, extjob_id),
                                                      QMessageBox.Yes, QMessageBox.No)
                            if rc != QMessageBox.Yes:
                                continue  # 다음 레이어 처리로

                        sql = u'INSERT INTO extjob.receive_main VALUES(%s, %s, %s, %s)'
                        cur.execute(sql,(receive_id, extjob_id, layer_nm, receive_dttm))

                        # receive_layer import
                        sql = u'INSERT INTO extjob.receive_layer VALUES (%s, %s, %s)'
                        cur.execute(sql,(receive_id, layer_nm, table_nm))

                self.conn.commit()

                return True
            else:
                return False

        except Exception as e:
            # TODO: 에러 발생시 테이블 삭제하고 진행을 멈춤
            self.conn.rollback()
            QMessageBox.warning(self, u"오류", str(e))

            return False

    def checkColumns(self):
        cur = self.plugin.conn.cursor()
        sql = u''
        check_res = []

        for fileName in os.listdir(self.edt_data_folder.text()):
            if os.path.splitext(fileName)[1] == '.shp':
                field_list = set([])
                column_list = set([])
                layer_nm = os.path.splitext(fileName)[0]

                # 기본 칼럼 ( 마스터 디비에 있는 칼럼 ) 가져오기
                sql = u"select column_name from information_schema.columns " \
                      u"where table_schema = 'nfsd' and table_name = '{}'".format(layer_nm)
                cur.execute(sql)
                results = cur.fetchall()
                for result in results:
                    column_list.add(result[0])

                column_list.remove('ogc_fid')
                column_list.remove('wkb_geometry')

                # shp의 필드명 가져오기
                shp = os.path.join(self.edt_data_folder.text(), fileName)
                data = ogr.Open(shp)
                layer = data.GetLayer(0)
                layer_de = layer.GetLayerDefn()

                for i in range(layer_de.GetFieldCount()):
                    field_list.add(layer_de.GetFieldDefn(i).GetName())

                # 칼럼 체크하기
                check = column_list.difference(field_list)

                if len(check) != 0:
                    print list(check)
                    check_res.append({'file_nm': layer_nm, 'fields': list(check)})

        if len(check_res) != 0:
            msg = u''
            for res in check_res:
                file_nm = res['file_nm']
                fields = []
                for col in res['fields']:
                    fields.append(col)
                omit_field = ','.join(fields)
                msg += u'파일명 : {}\n- 누락된 칼럼 : {}\n\n'.format(file_nm, omit_field)

            QMessageBox.warning(self, u"오류", msg)

            return False

        return True
