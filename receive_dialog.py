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
import ConfigParser

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
        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        folderPath = QFileDialog.getExistingDirectory(self.plugin.iface.mainWindow(),
                                            u'납품받은 데이터가 있는 폴더를 선택해 주십시오.',conf.get('Dir_Info','receive_dir'))

        if folderPath:
            self.dataFolder = folderPath
            self.edt_data_folder.setText(folderPath)

            with open(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"), "w") as confFile:
                conf.set("Dir_Info", "receive_dir", folderPath)
                conf.write(confFile)


    def hdrClickBtnUpload(self):
        self.progressBar.show()
        self.lbl_progress.show()

        # 수령 데이터 import
        receive_id = self.importRecData()
        if  receive_id != None and receive_id != '':
            # TODO: 시연을 위한 코드이므로 제거 필요
            for i in range(10):
                progress = i * 10
                self.progressBar.setValue(progress)
                self.lbl_progress.setText(u"납품 데이터 올리기 진행중...{}%".format(progress))
                time.sleep(1)
            self.btn_upload.setDisabled(True)
            self.btn_inspect.setDisabled(False)

            msg = u'납품 데이터 올리기가 완료되었습니다.\n' \
                  u'수령 ID : {}'.format(receive_id)
            QMessageBox.information(self, u"작업완료", msg)

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
                return

            if self.edt_data_folder.text() == "":
                QMessageBox.warning(self, u"오류", u"폴더를 선택해 주시기 바랍니다")
                return

            if self.checkColumns():

                # 수령ID, 수령 날짜 생성
                cur = self.conn.cursor()
                sql = "SELECT nextid('RD') as receive_id, current_timestamp as mapext_dttm"
                cur.execute(sql)
                result = cur.fetchone()
                if not result:
                    QMessageBox.error(self, u"오류", u"선택한 작업에 해당되는 데이터를 찾지 못했습니다. 관리자에게 문의해 주세요.")
                    return
                receive_id = result[0]
                receive_dttm = result[1]

                for fileName in os.listdir(self.edt_data_folder.text()):
                    # shp 파일을 찾고, import 수령ID_레이어명
                    if os.path.splitext(fileName)[1]=='.shp':
                        layer_nm = os.path.splitext(fileName)[0]
                        table_nm = receive_id + "_" + layer_nm
                        shp_path = os.path.join(self.edt_data_folder.text(),fileName)

                        # TODO: 파일 내에 여러 extjob_id 가 있는 경우 대비하여 코딩 수정 필요
                        # 파일과 선택한 extjob_id 일치여부
                        extjob_id_list = []
                        check_extjob_id = True

                        ogr_drive = ogr.GetDriverByName('ESRI Shapefile')
                        shp_file = ogr_drive.Open(shp_path)

                        shp_layer = shp_file.GetLayer()
                        shp_layer_def = shp_layer.GetLayerDefn()

                        shp_fields = []
                        for i in range(shp_layer_def.GetFieldCount()):
                            shp_fields.append(shp_layer_def.GetFieldDefn(i).GetName())


                        # extjob_id field를 가지고 있는 경우에만 실행
                        if 'extjob_id' in shp_fields:
                            # NULL 값은 필터링
                            shp_data = shp_file.ExecuteSQL(
                                        'select DISTINCT extjob_id from {} where extjob_id is not NULL'.format(layer_nm))

                            for row in shp_data:
                                extjob_id_list.append(row.GetField('extjob_id'))

                        # extjob_id 값의 수에 따라서 분류류
                        if len(extjob_id_list) == 0: # extjob_id 가 없는 경우
                            rc = QMessageBox.question(self,u'경고',u'{} 파일에 외주ID가 존재하지 않습니다.\n'
                                                           u'선택한 외주ID({})로 계속 하시겠습니까?'
                                                            .format(layer_nm,extjob_id),QMessageBox.Yes, QMessageBox.No)
                            if rc != QMessageBox.Yes:
                                continue  # 다음 레이어 처리로

                            check_extjob_id = False

                        elif len(extjob_id_list) == 1: # extjob_id 가 하나만 존재하는 경우
                            file_extjob_id = extjob_id_list[0]

                            # 사용자가 선택한 extjob_id와 파일의 그것이 다를 때 대응
                            if extjob_id != file_extjob_id:

                                rc = QMessageBox.question(self, u"경고",
                                                          u"{} 파일의 외주ID({})가 선택한 작업의 외주ID({})와 다릅니다.\n"
                                                          u"그래도 계속 하시겠습니까?".format(layer_nm,file_extjob_id,
                                                          extjob_id),QMessageBox.Yes, QMessageBox.No)
                                if rc != QMessageBox.Yes:
                                    continue  # 다음 레이어 처리로

                                check_extjob_id = False

                        else: # extjob_id 가 여러 개인 경우
                            extjob_id_str = ','.join(extjob_id_list)
                            rc = QMessageBox.question(self, u"경고",
                                                      u"{} 파일에 여러 외주ID가 존재합니다.\n"
                                                      u"외주ID : {}\n"
                                                      u"선택한 외주ID : {}\n"
                                                      u"그래도 계속 하시겠습니까?".format(layer_nm, extjob_id_str,
                                                       extjob_id), QMessageBox.Yes, QMessageBox.No)
                            if rc != QMessageBox.Yes:
                                continue  # 다음 레이어 처리로

                            check_extjob_id = False

                        # 윈도우가 아닌 경우 PATH 추가
                        ogr2ogrPath = None
                        if sys.platform == "win32":
                            ogr2ogrPath = ""
                        else:
                            ogr2ogrPath = "/Library/Frameworks/GDAL.framework/Versions/1.11/Programs/"

                        # 만들려는 테이블이 이미 있는지 확인하여 있으면 확 지워버림
                        sql = u"SELECT count(table_name) FROM information_schema.tables " \
                              u"WHERE table_schema='extjob' and table_name = '{}'".format(table_nm)
                        cur.execute(sql)
                        res = cur.fetchone()

                        if res[0] > 0:
                            sql = "drop table extjob.{} ".format(table_nm)
                            cur.execute(sql)
                            self.plugin.conn.commit()

                        # 수정된 테이블 생성
                        # TODO: dbf 파일의 인코딩 확인하여 결정하게 해야 함

                        command = u'{}ogr2ogr ' \
                                  u'--config SHAPE_ENCODING UTF-8 -append -a_srs EPSG:5179 ' \
                                  u'-f PostgreSQL PG:"host=localhost user=postgres dbname=sdmc password=postgres" ' \
                                  u'{} -nln extjob.{} -nlt PROMOTE_TO_MULTI '\
                                  .format(ogr2ogrPath, shp_path, table_nm)
                        rc = check_output(command.encode(), shell=True)

                        sql = u"alter table extjob.{0}_{1} rename basedata_n to basedata_nm; " \
                              u"alter table extjob.{0}_{1} rename mapext_dtt to mapext_dttm; " \
                              u"alter table extjob.{0}_{1} rename basedata_d to basedata_dt"\
                            .format(receive_id, layer_nm)

                        cur.execute(sql)

                        if not check_extjob_id:
                            # extjob_id field 검사
                            sql = u"select count(column_name) from information_schema.columns " \
                                  u"where table_schema = 'extjob' and table_name = '{}_{}' " \
                                  u"and column_name = 'extjob_id'".format(receive_id.lower(),layer_nm)
                            cur.execute(sql)
                            exist_col = cur.fetchone()

                            # extjob_id 가 아예 없는 경우 생성해 줌
                            if exist_col[0] <= 0:
                                sql = u"alter table extjob.{0}_{1} add column extjob_id character varying(80)"\
                                    .format(receive_id,layer_nm)
                                cur.execute(sql)

                            sql = u"UPDATE extjob.{0}_{1} set extjob_id = '{2}'"\
                                .format(receive_id,layer_nm,extjob_id)
                            cur.execute(sql)

                        sql = u"ALTER TABLE extjob.{0} ADD COLUMN receive_id character varying(16); " \
                              u"UPDATE extjob.{0} SET receive_id = '{1}';  " \
                              .format(table_nm, receive_id)
                        cur.execute(sql)

                        # receive_main import
                        sql = u'INSERT INTO extjob.receive_main VALUES(%s, %s, %s, %s)'
                        cur.execute(sql,(receive_id, extjob_id, layer_nm, receive_dttm))

                        # receive_layer import
                        sql = u'INSERT INTO extjob.receive_layer VALUES (%s, %s, %s)'
                        cur.execute(sql,(receive_id, layer_nm, table_nm))

                sql = u"SELECT count(*) FROM extjob.receive_main where receive_id = '{}'".format(receive_id)
                cur.execute(sql)
                res = cur.fetchone()

                if res[0] <= 0:
                    QMessageBox.information(self,u'작업완료',u'납품된 데이터가 없습니다.')
                    return

                self.conn.commit()
                return receive_id
            else:
                return

        except Exception as e:
            # TODO: 에러 발생시 테이블 삭제하고 진행을 멈춤
            self.conn.rollback()
            QMessageBox.warning(self, u"오류", str(e))

            return

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
                      u"where table_schema = 'nfsd' and table_name = '{}' order by ordinal_position asc".format(layer_nm)
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

            QMessageBox.error(self, u"오류", msg)

            return False

        return True
