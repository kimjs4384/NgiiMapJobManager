# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WidgetInspect
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
import ConfigParser

from qgis.core import *

from ui.inspect_dialog_base import Ui_Dialog as Ui_Form

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/inspect.ui'))


# class WidgetInspect(QtGui.QDialog, FORM_CLASS):
class WidgetInspect(QWidget, Ui_Form):
    title = u"납품 데이터 검수"
    objectName = "objWidgetInspect"
    plugin = None  # type: NgiiMapJobManager
    crrIndex = 0

    def __init__(self, iface, dockwidget, parent):
        QWidget.__init__(self)
        Ui_Form.__init__(self)
        self.setupUi(self)
        self.plugin = parent

        self.inspect_id = None
        self.layer_nm = None
        self.receive_id = None
        self.extjob_id = None
        self.id_column = None
        self.column_sql = None

        self.setInitValue()
        self.connectFct()

        if self.plugin.dlgReceive != None:
            extjob_id = self.plugin.dlgReceive.cmb_extjob_nm.itemData(self.plugin.dlgReceive.cmb_extjob_nm.currentIndex())
            if extjob_id != None and extjob_id != "":
                self.setDefaultInfo(extjob_id)

    def connectFct(self):
        self.cmb_worker_nm.currentIndexChanged.connect(self.hdrCmbWorkerIndexChange)
        self.date_mapext_dttm.dateChanged.connect(self.hdrCmbWorkerIndexChange)
        self.cmb_receive_id.currentIndexChanged.connect(self.addLayerList)
        self.cmb_extjob_nm.currentIndexChanged.connect(self.hdrCmbExtjobNmIndexChange)
        self.btn_start_inspect.clicked.connect(self.hdrClickBtnStartInspect)
        self.btn_next.clicked.connect(self.hdrClickBtnNext)
        self.btn_prev.clicked.connect(self.hdrClickBtnPrev)
        self.btn_accept.clicked.connect(self.hdrClickBtnAccept)
        self.btn_reject.clicked.connect(self.hdrClickBtnReject)
        self.btn_make_report.clicked.connect(self.hdrClickBtnMakeReport)

    def setInitValue(self):
        self.fillWorkerList()

        crrDate = QDate.currentDate()
        self.date_mapext_dttm.setDate(crrDate)

        self.btn_start_inspect.setDisabled(True)
        self.btn_accept.setDisabled(True)
        self.btn_next.setDisabled(True)
        self.btn_prev.setDisabled(True)
        self.btn_reject.setDisabled(True)
        self.btn_make_report.setDisabled(True)

        self.progressBar.hide()
        self.lbl_progress.hide()

    def setDefaultInfo(self,extjob_id):
        try:
            cur = self.plugin.conn.cursor()
            sql = u"select worker_nm, to_char(mapext_dttm,'yyyy-mm-dd'), extjob_nm " \
                  u"from extjob.extjob_main where extjob_id = '{}'".format(extjob_id)
            cur.execute(sql)
            result = cur.fetchone()

            worker_index = self.cmb_worker_nm.findText(result[0])
            self.cmb_worker_nm.setCurrentIndex(worker_index)

            self.date_mapext_dttm.setDate(QDate.fromString(result[1],'yyyy-MM-dd'))

            extjob_nm_index = self.cmb_extjob_nm.findText(result[2])
            self.cmb_extjob_nm.setCurrentIndex(extjob_nm_index)

        except Exception as e:
            QMessageBox.warning(self, u"오류", str(e))

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

    def hdrCmbWorkerIndexChange(self):
        workerName = self.cmb_worker_nm.currentText()
        startDate = self.date_mapext_dttm.date()
        endDate = startDate
        self.searchExtjob(workerName, startDate, endDate)
        self.btn_start_inspect.setDisabled(False)

    def searchExtjob(self, workerName, startDate, endDate):
        try:
            cur = self.plugin.conn.cursor()
            sql = u"SELECT extjob_id, extjob_nm, basedata_dt FROM extjob.extjob_main " \
                  u"WHERE worker_nm = %s and mapext_dttm BETWEEN %s and %s order by basedata_dt desc"
            cur.execute(sql, (workerName,
                              u"{} 00:00:00".format(startDate.toString('yyyy-M-d')),
                              u"{} 23:59:59.9999".format(endDate.toString('yyyy-M-d'))))
            results = cur.fetchall()
            self.cmb_extjob_nm.clear()
            self.cmb_receive_id.clear()
            self.cmb_layer_nm.clear()

            if not results or len(results) <= 0:
                # QMessageBox.warning(self, u"검색실패", u"조건에 맞는 작업이 없습니다.")
                return

            for result in results:
                extjob_id = result[0]
                extjob_nm = result[1]
                basedata_dt = result[2]
                self.cmb_extjob_nm.addItem(extjob_nm)
                self.cmb_extjob_nm.setItemData(self.cmb_extjob_nm.count()-1, extjob_id)
                self.date_basedata_dt.setDate(basedata_dt)

            sel_extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
            sql = u"select receive_id from (select * from extjob.receive_main where extjob_id = '{}') as ext " \
                  u"group by receive_id".format(sel_extjob_id)
            cur.execute(sql)
            results = cur.fetchall()

            for result in results:
                self.cmb_receive_id.addItem(result[0])

            # for result in results:
            #     self.cmb_layer_nm.addItem(result[2])

        except Exception as e:
            QMessageBox.warning(self, "SQL ERROR", str(e))

    def hdrCmbExtjobNmIndexChange(self):
        self.addLayerList()

    def addLayerList(self):
        self.cmb_layer_nm.clear()

        cur = self.plugin.conn.cursor()
        sel_extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
        sql = u"select layer_nm from extjob.receive_main where extjob_id = '{}' and " \
              u"receive_id = '{}'".format(sel_extjob_id, self.cmb_receive_id.currentText())

        cur.execute(sql)
        results = cur.fetchall()

        self.cmb_layer_nm.addItem('')
        for result in results:
            self.cmb_layer_nm.addItem(result[0])

    def hdrClickBtnStartInspect(self):
        if self.cmb_layer_nm.currentText() == "":
            QMessageBox.warning(self, u"오류", u"검수할 레이러를 선택하셔야합니다.")
            return

        if self.edt_inpector.text() == "":
            QMessageBox.warning(self, u"오류", u"검수자가 기록되어야합니다.")
            return

        rc = QMessageBox.question(self, u"확인", u"변경탐지를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc != QMessageBox.Yes:
            return

        # self.btn_start_inspect.setDisabled(True)
        self.btn_start_inspect.setVisible(False)  # 자리가 좁아 안보이게 하는 것으로 수정
        self.btn_accept.setDisabled(False)
        self.btn_next.setDisabled(False)
        self.btn_prev.setDisabled(False)
        self.btn_reject.setDisabled(False)
        self.btn_make_report.setDisabled(False)

        self.findChange()

    def findChange(self):
        self.lbl_progress.setText(u"변경 탐지중...")
        self.lbl_progress.show()

        # 검수 메인 테이블에 데이터 저장
        self.insertInspectInfo()

        # 변화정보 탐색
        self.findDiff()

        # 변화정보를 QGIS에 띄움
        self.addLayers()

        # 변화정보 양을 세서 보여줌
        self.countDiffFeature()

    def hdrClickBtnNext(self):
        self.crrIndex += 1
        if self.crrIndex >= len(self.inspectList):
            self.crrIndex = 0

        self.lbl_progress.setText(u"{} / {} 처리중".format(self.crrIndex+1, len(self.inspectList)))

        geom = self.inspectList[self.crrIndex].geometry()
        bound = geom.boundingBox()
        canvas = self.plugin.iface.mapCanvas()
        canvas.setExtent(bound)
        canvas.refresh()

    def hdrClickBtnPrev(self):
        self.crrIndex -= 1
        if self.crrIndex < 0:
            self.crrIndex = len(self.inspectList)-1

        self.lbl_progress.setText(u"{} / {} 처리중".format(self.crrIndex+1, len(self.inspectList)))

        geom = self.inspectList[self.crrIndex].geometry()
        bound = geom.boundingBox()
        canvas = self.plugin.iface.mapCanvas()
        canvas.setExtent(bound)
        canvas.refresh()

    def hdrClickBtnAccept(self):
        if self.crrIndex >= 0:
            crrFeature = self.inspectList[self.crrIndex]
            origin_ogc_fid = crrFeature['origin_ogc_fid']
            receive_ogc_fid = crrFeature['receive_ogc_fid']

            cur = self.plugin.conn.cursor()
            sql = u"update extjob.inspect_objlist set inspect_res = 'accept', inspect_dttm = CURRENT_TIMESTAMP  " \
                  u"where inspect_id = '{}' and layer_nm = '{}' " \
                  u"and origin_ogc_fid = {} and receive_ogc_fid = {}"\
                .format(self.inspect_id, self.layer_nm, origin_ogc_fid, receive_ogc_fid)
            cur.execute(sql)

            self.plugin.conn.commit()

        self.edt_reject_reason.setPlainText("")
        self.hdrClickBtnNext()


    def hdrClickBtnReject(self):
        rejectReason = self.edt_reject_reason.toPlainText()
        if rejectReason == "":
            QMessageBox.warning(self, u"주의", u"거부사유를 입력하셔야 합니다.")
            return

        if self.crrIndex >= 0:
            crrFeature = self.inspectList[self.crrIndex]
            origin_ogc_fid = crrFeature['origin_ogc_fid']
            receive_ogc_fid = crrFeature['receive_ogc_fid']

            cur = self.plugin.conn.cursor()
            sql = u"update extjob.inspect_objlist set inspect_res = 'reject', inspect_dttm = CURRENT_TIMESTAMP, " \
                  u"reject_reason = '{}' " \
                  u"where inspect_id = '{}' and layer_nm = '{}' " \
                  u"and origin_ogc_fid = {} and receive_ogc_fid = {}" \
                .format(rejectReason, self.inspect_id, self.layer_nm, origin_ogc_fid, receive_ogc_fid)
            cur.execute(sql)

            self.plugin.conn.commit()

        self.edt_reject_reason.setPlainText("")
        self.hdrClickBtnNext()

    def findDiff(self):
        try:
            # TODO: 테이블 비교를 통해서 차이 분석
            # 외주 정보를 통해서 view를 만듦
            self.layer_nm = self.cmb_layer_nm.currentText()

            self.sql_rep = open(os.path.join(os.path.dirname(__file__), "conf", "sql_rep.txt"), 'a')
            self.sql_rep.write(u'data : {} , inspect_id : {} , layer_nm : {} \n\n'
                               .format(str(QDate.currentDate()), self.inspect_id, self.layer_nm))

            cur = self.plugin.conn.cursor()

            sql = u"create view extjob.{}_view as SELECT origin.* " \
                  u"FROM ( select * from extjob.extjob_objlist where extjob_objlist.extjob_id = '{}' " \
                  u"and layer_nm = '{}') " \
                  u"as ext left join nfsd.{} as origin on ext.ogc_fid = origin.ogc_fid"\
                .format(self.layer_nm,self.extjob_id,self.layer_nm,self.layer_nm)
            self.sql_rep.write("view :" + sql + "\n")
            cur.execute(sql)

            # 검사하려는 테이블의 칼럼을 shp list로 만듦
            sql = "select column_name from information_schema.columns " \
                  "where table_schema = 'nfsd' and table_name = '{}'".format(self.layer_nm)
            cur.execute(sql)
            column_nm = []
            results = cur.fetchall()

            for list in results:
                column_nm.append(list[0])

            column_nm.remove('ogc_fid')
            column_nm.remove('wkb_geometry')

            self.column_sql = ','.join(column_nm)
            self.id_column = column_nm[0]

            # 속성, 지오메트리 까지 같은 데이터
            self.findSame()
            time.sleep(1)
            # 속성은 같고 지오메트리만 바뀐 데이터
            self.findEditOnlyGeomety()
            time.sleep(1)
            # 속성만 바뀐 데이터
            self.findEditAttr()
            time.sleep(1)
            # 삭제된 데이터
            self.findDel()
            time.sleep(1)
            # 추가된 데이터
            self.findAdd()

            self.sql_rep.write('\n')
            self.sql_rep.close()

            sql = "drop view extjob.{}_view ".format(self.layer_nm)
            cur.execute(sql)

            self.plugin.conn.commit()

        except Exception as e:
            self.plugin.conn.rollback()
            QMessageBox.warning(self, u"오류", str(e))

    def findSame(self):
        cur = self.plugin.conn.cursor()
        sql = u"with same_data as ( select o.* from (select wkb_geometry,{} from extjob.{}_view) as o " \
              u"inner join (select wkb_geometry,{} from extjob.{}_{}) as e on (o.*) = (e.*) )," \
              u"origin as ( select o.ogc_fid as origin_ogc_fid, a.{} from same_data as a " \
              u"inner join extjob.{}_view as o on a.wkb_geometry = o.wkb_geometry )," \
              u"receive as (select o.ogc_fid as receive_ogc_fid, a.{} from same_data as a " \
              u"inner join extjob.{}_{} as o on a.wkb_geometry = o.wkb_geometry) " \
              u"insert into extjob.inspect_objlist( inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type )" \
              u"select '{}' as inspect_id, '{}' as layer_nm, origin_ogc_fid, receive_ogc_fid, " \
              u"'s' as mod_type from origin, receive where origin.{} = receive.{}"\
            .format(self.column_sql,self.layer_nm,self.column_sql,self.receive_id,self.layer_nm, self.id_column,
                    self.layer_nm, self.id_column, self.receive_id, self.layer_nm, self.inspect_id,self.layer_nm,
                    self.id_column,self.id_column)
        self.sql_rep.write("same_data : " + sql + "\n")
        cur.execute(sql)

    def findEditOnlyGeomety(self):
        cur = self.plugin.conn.cursor()

        sql = u"with attr_same_data as (select o.* from (select {} from extjob.{}_view) as o " \
              u"inner join (select {} from extjob.{}_{}) as e on (o.*) = (e.*) ), " \
              u"same_data as( select wkb_geometry,{} from " \
              u"(select origin_ogc_fid from extjob.inspect_objlist where mod_type = 's' and inspect_id = '{}') as s " \
              u"inner join extjob.{}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
              u"join_geom as ( select o.wkb_geometry, a.* from attr_same_data as a " \
              u"inner join extjob.{}_view as o on a.{} = o.{} ), " \
              u"geo_edit as ( select * from join_geom except select * from same_data) " \
              u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'eg' as mod_type " \
              u"from (select ogc_fid as origin_ogc_fid,e.{} from geo_edit as e " \
              u"inner join extjob.{}_view as o on e.{} = o.{}) as origin, " \
              u"(select ogc_fid as receive_ogc_fid,e.{} from geo_edit as e " \
              u"inner join extjob.{}_{} as o on e.{} = o.{}) as edit where origin.{} = edit.{}"\
            .format(self.column_sql, self.layer_nm, self.column_sql, self.receive_id, self.layer_nm, self.column_sql,
                    self.inspect_id, self.layer_nm, self.layer_nm, self.id_column, self.id_column, self.inspect_id,
                    self.layer_nm, self.id_column, self.layer_nm, self.id_column, self.id_column, self.id_column,
                    self.receive_id, self.layer_nm, self.id_column, self.id_column, self.id_column, self.id_column)
        self.sql_rep.write("edit_geom_data : " + sql + "\n")
        cur.execute(sql)

    def findEditAttr(self):
        cur = self.plugin.conn.cursor()
        geohash_sql = u'st_geohash(ST_Transform(st_centroid(st_boundary(wkb_geometry)), 4326), ' \
                      u'12) as mbr_hash_12, round( CAST(st_area(wkb_geometry) as numeric), 1) as geom_area'

        sql = u"with same as (select {}, {} from (select origin_ogc_fid from extjob.inspect_objlist " \
              u"where mod_type = 's' and inspect_id = '{}') as s " \
              u"inner join extjob.{}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
              u"om as (select {}, {} from extjob.{}_view except select * from same ), " \
              u"em as (select {}, {} from extjob.{}_{} except select * from same ), " \
              u"geometry as ( select mbr_hash_12,geom_area from ( select om.* from om " \
              u"inner join em on em.mbr_hash_12 = om.mbr_hash_12 and em.geom_area = om.geom_area) as t) " \
              u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'ef' as mod_type " \
              u"from (select ogc_fid as origin_ogc_fid, o.mbr_hash_12, o.geom_area from geometry " \
              u"inner join (select ogc_fid, {} from extjob.{}_view ) as o " \
              u"on (geometry.mbr_hash_12,geometry.geom_area)=(o.mbr_hash_12,o.geom_area)) as origin, " \
              u"(select ogc_fid as receive_ogc_fid, o.mbr_hash_12, o.geom_area from geometry " \
              u"inner join (select ogc_fid, {} from extjob.{}_{} ) as o " \
              u"on (geometry.mbr_hash_12,geometry.geom_area)=(o.mbr_hash_12,o.geom_area)) as receive " \
              u"where (origin.mbr_hash_12,origin.geom_area) = (receive.mbr_hash_12,receive.geom_area)"\
            .format(self.column_sql, geohash_sql, self.inspect_id, self.layer_nm, self.column_sql,
                    geohash_sql, self.layer_nm, self.column_sql, geohash_sql, self.receive_id,
                    self.layer_nm, self.inspect_id, self.layer_nm, geohash_sql, self.layer_nm,
                    geohash_sql, self.receive_id, self.layer_nm )
        self.sql_rep.write("edit_feature_data : " + sql + "\n")
        cur.execute(sql)

    def findDel(self):
        cur = self.plugin.conn.cursor()

        sql = u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, origin_ogc_fid, 0 as receive_ogc_fid, 'r' as mod_type " \
              u"from (select ogc_fid as origin_ogc_fid from extjob.{}_view " \
              u"except select origin_ogc_fid from extjob.inspect_objlist " \
              u"where inspect_id = '{}' and layer_nm = '{}' ) as rm"\
            .format(self.inspect_id, self.layer_nm, self.layer_nm,self.inspect_id, self.layer_nm)
        self.sql_rep.write("rm_data : " + sql + "\n")
        cur.execute(sql)

    def findAdd(self):
        cur = self.plugin.conn.cursor()
        sql = u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type ) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, 0 as origin_ogc_fid, receive_ogc_fid, 'a' as mod_type " \
              u"from (select ogc_fid as receive_ogc_fid from extjob.{}_{} " \
              u"except select receive_ogc_fid from extjob.inspect_objlist " \
              u"where inspect_id = '{}' and layer_nm = '{}' ) as add"\
            .format(self.inspect_id, self.layer_nm, self.receive_id, self.layer_nm,self.inspect_id, self.layer_nm)
        self.sql_rep.write("add_data : " + sql + "\n")
        cur.execute(sql)

    def addLayers(self):
        uri = QgsDataSourceURI()

        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        ip_address = conf.get("Connection_Info", "pgIp")
        port = conf.get("Connection_Info", "pgPort")
        database = conf.get("Connection_Info", "pgDb")
        account = conf.get("Connection_Info", "pgAccount")
        password = conf.get("Connection_Info", "pgPw")

        # 기존의 데이터 ( 변화없는 정보 )
        sql = u"(select row_number() over (order by mod_type asc) as id, ext.*, wkb_geometry, {} " \
              u"from (select * from extjob.inspect_objlist " \
              u"where layer_nm = '{}' and inspect_id = '{}' " \
              u"and mod_type != 'r' ) as ext " \
              u"inner join nfsd.{} as o on ext.origin_ogc_fid = o.ogc_fid)" \
            .format(self.column_sql, self.layer_nm, self.inspect_id, self.layer_nm)

        uri.setConnection(ip_address, port, database, account, password)
        uri.setDataSource("", sql, "wkb_geometry", "", "id")
        maintain_data = QgsVectorLayer(uri.uri(), u'변화없음', "postgres")

        # TODO: 지오메트리 타입에 따라서 심볼이 달라져야함
        symbol = None
        if maintain_data.wkbType() == QGis.WKBMultiPolygon:
            symbol = QgsFillSymbolV2().createSimple({'color_border': 'black', 'width_border': '0.25',
                                                     'style': 'no', 'style_border': 'solid', 'unit': 'MapUnit'})
        elif maintain_data.wkbType() == QGis.WKBMultiLineString:
            symbol = QgsLineSymbolV2().createSimple({'color_border': 'black', 'width_border': '0.25',
                                                     'style': 'no', 'style_border': 'solid', 'unit': 'MapUnit'})
        else:
            symbol = QgsMarkerSymbolV2.createSimple({'color': 'black', 'size': '0.25',
                                                     'style_border': 'no', 'unit': 'MapUnit'})

        maintain_data.rendererV2().setSymbol(symbol)
        QgsMapLayerRegistry.instance().addMapLayer(maintain_data)

        # 변화가 있는 정보
        sql = u"(select row_number() over (order by mod_type asc) as id, * from (select ext.*, wkb_geometry, {} from "\
                  u"(select * from extjob.inspect_objlist " \
                  u"where layer_nm = '{}' and inspect_id = '{}' and mod_type = 'r') as ext " \
                  u"inner join nfsd.{} as o on ext.origin_ogc_fid = o.ogc_fid " \
                  u"union select ext.*, wkb_geometry, {} from " \
                  u"(select * from extjob.inspect_objlist " \
                  u"where layer_nm = '{}' and inspect_id = '{}'and mod_type != 's') as ext " \
                  u"inner join extjob.{}_{} as e on ext.receive_ogc_fid = e.ogc_fid) as foo )"\
                .format(self.column_sql, self.layer_nm, self.inspect_id, self.layer_nm, self.column_sql,
                        self.layer_nm, self.inspect_id, self.receive_id, self.layer_nm)

        uri.setDataSource("",sql, "wkb_geometry", "" , "id")
        diff_data = QgsVectorLayer(uri.uri(), u'변화정보', "postgres")

        mod_type_symbol = {
            'a' : ('green',u'추가'),
            'r' : ('red',u'삭제'),
            'eg' : ('orange',u'도형변경'),
            'ef' : ('blue',u'속성변경')
        }

        diff_data_type = diff_data.wkbType()
        categories = []
        for mod_type, (color, label) in mod_type_symbol.items():
            if diff_data_type == QGis.WKBMultiPolygon:
                symbol = QgsFillSymbolV2().createSimple({'color_border': color, 'width_border': '0.25',
                                                      'style': 'no', 'style_border': 'solid', 'unit': 'MapUnit'})
            elif diff_data_type == QGis.WKBMultiLineString:
                symbol = QgsLineSymbolV2().createSimple({'color': color, 'width': '0.25',
                                                         'style': 'solid', 'unit': 'MapUnit'})
            else:
                symbol = QgsMarkerSymbolV2.createSimple({'color': 'black', 'size': '0.25',
                                                         'style_border': 'no', 'unit': 'MapUnit'})
            category = QgsRendererCategoryV2(mod_type, symbol, label)
            categories.append(category)

        expression = 'mod_type'  # field name
        renderer = QgsCategorizedSymbolRendererV2(expression, categories)
        diff_data.setRendererV2(renderer)

        QgsMapLayerRegistry.instance().addMapLayer(diff_data)

        self.inspectList = []
        self.crrIndex = -1
        iter = diff_data.getFeatures()
        for feature in iter:
            self.inspectList.append(feature)

    def insertInspectInfo(self):
        # 검수ID, 검수 날짜 생성
        cur = self.plugin.conn.cursor()
        sql = u"SELECT nextid('AD') as extjob_id, current_timestamp as mapext_dttm"
        cur.execute(sql)
        result = cur.fetchone()
        self.inspect_id = result[0]
        inspect_dttm = result[1]

        self.receive_id =  self.cmb_receive_id.currentText()
        self.extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
        self.inspecter = self.edt_inpector.text()

        # TODO: Secure Coding
        sql = u"INSERT INTO extjob.inspect_main(inspect_id, extjob_id, receive_id, start_dttm, inspecter_nm) " \
              u"VALUES ('{}','{}','{}','{}','{}')"\
            .format(self.inspect_id, self.extjob_id, self.receive_id, inspect_dttm, self.inspecter)
        cur.execute(sql)

        self.plugin.conn.commit()

    def countDiffFeature(self):
        cur = self.plugin.conn.cursor()
        sql = u"select mod_type, count(mod_type) as count " \
              u"from ( select * from extjob.inspect_objlist " \
              u"where layer_nm = '{}' and inspect_id = '{}') as ext " \
              u"group by mod_type order by mod_type asc".format(self.layer_nm, self.inspect_id)
        cur.execute(sql)
        results = cur.fetchall()
        diff_count = {'a':0, 'r':0, 'eg':0, 'ef':0, 's':0}
        for result in results:
            diff_count[result[0]] = result[1]

        info = u"변경탐지결과\n" \
        u"- 신규: {}개\n" \
        u"- 삭제: {}개\n" \
        u"- 도형변경: {}개\n" \
        u"- 속성변경: {}개\n" \
        u"- 유지: {}개".format(
            diff_count['a'],
            diff_count['r'],
            diff_count['eg'],
            diff_count['ef'],
            diff_count['s'] )

        QMessageBox.information(self, u"탐지결과", info)

        self.lbl_progress.setText(info)

    def hdrClickBtnMakeReport(self):
        pass