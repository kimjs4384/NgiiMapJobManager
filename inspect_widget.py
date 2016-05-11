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


    def connectFct(self):
        self.cmb_worker_nm.currentIndexChanged.connect(self.hdrCmbWorkerIndexChange)
        self.date_mapext_dttm.dateChanged.connect(self.hdrCmbWorkerIndexChange)
        self.btn_start_inspect.clicked.connect(self.hdrClickBtnStartInspect)
        self.btn_next.clicked.connect(self.hdrClickBtnNext)
        self.btn_prev.clicked.connect(self.hdrClickBtnPrev)
        self.btn_accept.clicked.connect(self.hdrClickBtnAccept)
        self.btn_reject.clicked.connect(self.hdrClickBtnReject)

    def setInitValue(self):
        self.fillWorkerList()

        crrDate = QDate.currentDate()
        self.date_mapext_dttm.setDate(crrDate)

        self.btn_start_inspect.setDisabled(True)
        self.btn_accept.setDisabled(True)
        self.btn_next.setDisabled(True)
        self.btn_prev.setDisabled(True)
        self.btn_reject.setDisabled(True)

        self.progressBar.hide()
        self.lbl_progress.hide()

    def fillWorkerList(self):
        # TODO: 실제로 DB에서 자료 불러오게 수정(수정_JS)
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
        # self.cmb_worker_nm.setCurrentIndex(-1)

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
                  u"WHERE worker_nm = %s and mapext_dttm BETWEEN %s and %s"
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
            sql = u"select * from extjob.receive_main where extjob_id = '{}'".format(sel_extjob_id)
            cur.execute(sql)
            results = cur.fetchall()

            for result in results:
                self.cmb_receive_id.addItem(result[0])
            for result in results:
                self.cmb_layer_nm.addItem(result[2])

        except Exception as e:
            QMessageBox.warning(self, "SQL ERROR", str(e))

        # TODO: 진짜로 조회해 넣기(수정_JS)
        # self.cmb_receive_id.clear()
        # self.cmb_receive_id.addItem("RD20160525_00001")
        # self.cmb_layer_nm.clear()
        # self.cmb_layer_nm.addItem("nf_a_b01000")

    def hdrClickBtnStartInspect(self):
        rc = QMessageBox.question(self, u"확인", u"변경탐지를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc != QMessageBox.Yes:
            return

        self.btn_start_inspect.setDisabled(True)
        self.btn_accept.setDisabled(False)
        self.btn_next.setDisabled(False)
        self.btn_prev.setDisabled(False)
        self.btn_reject.setDisabled(False)

        self.findChange()

    def findChange(self):
        self.lbl_progress.setText(u"변경 탐지중...")
        self.lbl_progress.show()

        # try:
        #     cur = self.plugin.conn.cursor()
        #     cur.execute(self.sqlFindEdited)
        #     cur.execute(self.sqlFindSame)
        #     cur.execute(self.sqlFindAttrChanged)
        #     cur.execute(self.sqlFindAdd)
        #     cur.execute(self.sqlFindDel)
        #     self.plugin.conn.commit()
        # except Exception as e:
        #     self.plugin.conn.rollback()
        #     QMessageBox.warning(self, "SQL ERROR", str(e)

        self.insertInspectInfo()

        self.findDiff()

        self.addLayers()

        self.countDiffFeature()

        # legend = self.plugin.iface.legendInterface()
        # layers = legend.layers()
        # for layer in layers:
        #     layerType = layer.type()
        #     if layerType == QgsMapLayer.VectorLayer:
        #         layerName = layer.name()
        #         if layerName == u'변화없음':
        #             self.same_data = layer
        #         elif layerName == u'속성변경':
        #             self.attr_edit_post = layer
        #         elif layerName == u'도형변경':
        #             self.geo_edit_post = layer
        #         elif layerName == u'삭제':
        #             self.rm_data = layer
        #         elif layerName == u'추가':
        #             self.add_data = layer
        #
        # legend.setLayerVisible(self.same_data, True)
        # time.sleep(1)
        # legend.setLayerVisible(self.attr_edit_post, True)
        # time.sleep(1)
        # legend.setLayerVisible(self.geo_edit_post, True)
        # time.sleep(1)
        # legend.setLayerVisible(self.rm_data, True)
        # time.sleep(1)
        # legend.setLayerVisible(self.add_data, True)
        # time.sleep(1)

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
        
        self.hdrClickBtnNext()

    def hdrClickBtnReject(self):
        rejectReason = self.edt_reject_reason.getPaintContext()
        if rejectReason == "":
            QMessageBox.warning(self, u"주의", u"거부사유를 입력하셔야 합니다.")
            return

        self.hdrClickBtnNext()

    def findDiff(self):
        try:
            # TODO: 테이블 비교를 통해서 차이 분석
            # 외주 정보를 통해서 view를 만듦
            self.layer_nm = self.cmb_layer_nm.currentText()

            cur = self.plugin.conn.cursor()

            # sql = u"create view extjob.{}_view as SELECT origin.* " \
            #       u"FROM ( select * from extjob.extjob_objlist where extjob_objlist.extjob_id = '{}' " \
            #       u"and layer_nm = '{}') " \
            #       u"as ext left join nfsd.{} as origin on ext.ogc_fid = origin.ogc_fid"\
            #     .format(self.layer_nm,self.extjob_id,self.layer_nm,self.layer_nm)
            # cur.execute(sql)

            self.plugin.conn.commit()

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
            # self.findSame()
            # time.sleep(1)
            # 속성은 같고 지오메트리만 바뀐 데이터
            # self.findEditOnlyGeomety()
            # time.sleep(1)
            # 속성만 바뀐 데이터
            # self.findEditAttr()
            # time.sleep(1)
            # 삭제된 데이터
            # self.findDel()
            # time.sleep(1)
            # 추가된 데이터
            # self.findAdd()

            #sql = "drop view extjob.{}_view ".format(self.layer_nm)
            #cur.execute(sql)

            self.plugin.conn.commit()

        except Exception as e:
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

        # sql = u"with same_data as ( select o.* from (select wkb_geometry,{} from extjob.{}_view) as o " \
        #       u"inner join (select wkb_geometry,{} from extjob.{}_{}) as e on (o.*) = (e.*) )," \
        #       u"join_geom as ( select a.* from same_data as a " \
        #       u"inner join extjob.{}_view as o on a.{} = o.{} ) select * into temp.same_data from join_geom"\
        #     .format(self.column_sql,self.layer_nm,self.column_sql,self.receive_id,self.layer_nm,self.layer_nm,
        #             self.id_column, self.id_column)
        cur.execute(sql)

        self.plugin.conn.commit()

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
        cur.execute(sql)

        # sql = u"with attr_same_data as (select o.* from (select {} from extjob.{}_view) as o " \
        #       u"inner join (select {} from extjob.{}_{}) as e on (o.*) = (e.*) ), " \
        #       u"join_geom as ( select o.wkb_geometry, a.* " \
        #       u"from attr_same_data as a inner join extjob.{}_view as o on a.{} = o.{} ), " \
        #       u"geo_edit as ( select * from join_geom except select * from temp.same_data) " \
        #       u"select * into temp.geo_edit_prev from geo_edit " \
        #     .format(self.column_sql, self.layer_nm, self.column_sql, self.receive_id, self.layer_nm, self.layer_nm,
        #             self.id_column,self.id_column)
        # cur.execute(sql)
        #
        # sql = u"with attr_same_data as ( select e.* from (select {} from extjob.{}_view) as o " \
        #       u"inner join (select {} from extjob.{}_{}) as e on (o.*) = (e.*) ), " \
        #       u"join_geom as ( select o.wkb_geometry, a.* from attr_same_data as a " \
        #       u"inner join extjob.{}_{} as o on a.{} = o.{} ), " \
        #       u"geo_edit as ( select * from join_geom " \
        #       u"except select wkb_geometry,{} from temp.same_data ) " \
        #       u"select t.* into temp.geo_edit_post " \
        #       u"from ( select a.* from geo_edit as a " \
        #       u"inner join extjob.{}_{} as o on a.{} = o.{} ) as t"\
        #     .format(self.column_sql, self.layer_nm, self.column_sql, self.receive_id, self.layer_nm,
        #             self.receive_id,self.layer_nm,self.id_column,self.id_column,self.column_sql,
        #             self.receive_id,self.layer_nm,self.id_column,self.id_column)
        # cur.execute(sql)

        self.plugin.conn.commit()

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
        cur.execute(sql)

        # sql = u"with same as (select wkb_geometry, {}, {} " \
        #       u"from temp.same_data ), " \
        #       u"om as ( select wkb_geometry,{}, {} " \
        #       u"from extjob.{}_view except select * from same ), " \
        #       u"em as (select wkb_geometry, {}, {} " \
        #       u"from extjob.{}_{} except select * from same ) " \
        #       u"select t.* into temp.attr_edit_prev " \
        #       u"from ( select om.* from om inner join em " \
        #       u"on em.mbr_hash_12 = om.mbr_hash_12 " \
        #       u"and em.geom_area between om.geom_area*0.95 and om.geom_area*1.05) as t " \
        #       u"inner join extjob.{}_view as o on t.{} = o.{}"\
        #     .format(self.column_sql, geohash_sql, self.column_sql, geohash_sql, self.layer_nm,
        #             self.column_sql,geohash_sql, self.receive_id, self.layer_nm, self.layer_nm,
        #             self.id_column,self.id_column)
        # cur.execute(sql)
        #
        # sql = u"with same as (select wkb_geometry, {}, {} " \
        #       u"from temp.same_data ), " \
        #       u"om as ( select wkb_geometry,{}, {} " \
        #       u"from extjob.{}_view except select * from same ), " \
        #       u"em as (select wkb_geometry, {}, {} " \
        #       u"from extjob.{}_{} except select * from same ) " \
        #       u"select t.* into temp.attr_edit_post " \
        #       u"from ( select em.* from em inner join om " \
        #       u"on em.mbr_hash_12 = om.mbr_hash_12 " \
        #       u"and em.geom_area between om.geom_area*0.95 and om.geom_area*1.05) as t " \
        #       u"inner join extjob.{}_{} as o on t.{} = o.{}" \
        #     .format(self.column_sql, geohash_sql, self.column_sql, geohash_sql, self.layer_nm,
        #             self.column_sql, geohash_sql, self.receive_id, self.layer_nm, self.receive_id,self.layer_nm,
        #             self.id_column,self.id_column)
        #
        # cur.execute(sql)

        self.plugin.conn.commit()

    def findDel(self):
        cur = self.plugin.conn.cursor()

        sql = u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, origin_ogc_fid, 0 as receive_ogc_fid, 'r' as mod_type " \
              u"from (select ogc_fid as origin_ogc_fid from extjob.{}_view " \
              u"except select origin_ogc_fid from extjob.inspect_objlist) as rm"\
            .format(self.inspect_id, self.layer_nm, self.layer_nm)

        # sql = u"with rm_same as( select wkb_geometry, {} from extjob.{}_view " \
        #       u"except select * from temp.same_data), " \
        #       u"rm_edit_geo as ( select * from rm_same except select * from temp.geo_edit_prev ), " \
        #       u"re_edit_attr as ( select * from rm_edit_geo except " \
        #       u"select wkb_geometry, {} from temp.attr_edit_prev) " \
        #       u"select * into temp.rm_data from re_edit_attr"\
        #     .format(self.column_sql, self.layer_nm, self.column_sql)
        cur.execute(sql)

        self.plugin.conn.commit()

    def findAdd(self):
        cur = self.plugin.conn.cursor()
        sql = u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type ) " \
              u"select '{}' as inspect_id, '{}' as layer_nm, 0 as origin_ogc_fid, receive_ogc_fid, 'a' as mod_type " \
              u"from (select ogc_fid as receive_ogc_fid from extjob.{}_{} " \
              u"except select receive_ogc_fid from extjob.inspect_objlist) as add"\
            .format(self.inspect_id, self.layer_nm, self.receive_id, self.layer_nm)

        # sql = u"with rm_same as (SELECT wkb_geometry, {} FROM extjob.{}_{} " \
        #       u"except select * from temp.same_data)," \
        #       u"rm_edit_geo as ( select * from rm_same except select * from temp.geo_edit_post )," \
        #       u"rm_edit_attr as ( select * from rm_edit_geo except " \
        #       u"select wkb_geometry, {} from temp.attr_edit_post ) " \
        #       u"select * into temp.add_data from rm_edit_attr"\
        #     .format(self.column_sql, self.receive_id, self.layer_nm, self.column_sql)
        cur.execute(sql)

        self.plugin.conn.commit()

    def addLayers(self):
        uri = QgsDataSourceURI()

        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        ip_address = conf.get("Connection_Info", "pgIp")
        port = conf.get("Connection_Info", "pgPort")
        database = conf.get("Connection_Info", "pgDb")
        account = conf.get("Connection_Info", "pgAccount")
        password = conf.get("Connection_Info", "pgPw")

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

        uri.setConnection(ip_address, port, database, account, password)
        uri.setDataSource("",sql, "wkb_geometry", "" , "id")
        diff_data = QgsVectorLayer(uri.uri(), u'변화정보', "postgres")

        mod_type_symbol = {
            'a' : ('green',u'추가'),
            'r' : ('red',u'삭제'),
            'eg' : ('orange',u'도형변경'),
            'ef' : ('blue',u'속성변경')
        }

        categories = []
        for mod_type, (color, label) in mod_type_symbol.items():
            # symbol = QgsSymbolV2.defaultSymbol(diff_data.geometryType())
            # symbol.setColor(QColor(color))

            symbol = QgsFillSymbolV2().createSimple({'color_border': color, 'width_border': '0.25',
                                                  'style': 'no', 'style_border': 'solid', 'unit': 'MapUnit'})

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

        QMessageBox.information(self, u"탐지결과", str(self.inspectList))

    def insertInspectInfo(self):
        # 검수ID, 검수 날짜 생성
        # cur = self.plugin.conn.cursor()
        # sql = "SELECT nextid('AD') as extjob_id, current_timestamp as mapext_dttm"
        # cur.execute(sql)
        # result = cur.fetchone()
        self.inspect_id = "AD20160510_00009" # result[0]
        # inspect_dttm = result[1]

        self.receive_id = 'RD20160504_00001' # self.cmb_receive_id.currentText()
        self.extjob_id = 'EJ20160504_00001' # self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())

        # sql = u"INSERT INTO extjob.inspect_main(inspect_id, extjob_id, receive_id, start_dttm) " \
        #       u"VALUES ('{}','{}','{}','{}')"\
        #     .format(self.inspect_id,self.extjob_id,self.receive_id,inspect_dttm)
        # cur.execute(sql)
        #
        # self.plugin.conn.commit()

    def countDiffFeature(self):
        cur = self.plugin.conn.cursor()
        sql = u"select mod_type, count(mod_type) as count " \
              u"from ( select * from extjob.inspect_objlist " \
              u"where layer_nm = 'nf_a_b01000' and inspect_id = 'AD20160510_00009') as ext " \
              u"group by mod_type order by mod_type asc ;"
        cur.execute(sql)
        results = cur.fetchall()
        diff_count = {}
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