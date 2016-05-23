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
import zipfile

from qgis.core import *

from ui.inspect_dialog_base import Ui_Dialog as Ui_Form

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/inspect.ui'))


# class WidgetInspect(QtGui.QDialog, FORM_CLASS):
class WidgetInspect(QWidget, Ui_Form):
    title = u"납품 데이터 검수"
    objectName = "objWidgetInspect"
    plugin = None  # type: NgiiMapJobManager
    crrIndex = None
    numTotal = -1
    numProcessed = 0

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

        if self.plugin.dlgReceive != None and self.plugin.dlgReceive.isVisible():
            extjob_id = self.plugin.dlgReceive.cmb_extjob_nm.itemData(self.plugin.dlgReceive.cmb_extjob_nm.currentIndex())
            if extjob_id != None and extjob_id != "":
                self.setDefaultInfo(extjob_id)

    def connectFct(self):
        self.cmb_worker_nm.currentIndexChanged.connect(self.hdrCmbWorkerIndexChange)
        self.date_mapext_dttm.dateChanged.connect(self.hdrCmbWorkerIndexChange)
        self.cmb_receive_id.currentIndexChanged.connect(self.addLayerList)
        self.cmb_extjob_nm.currentIndexChanged.connect(self.hdrCmbExtjobNmIndexChange)
        self.cmb_layer_nm.currentIndexChanged.connect(self.refreshUI)
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

            sql = u"select workarea_txt from extjob.extjob_main where extjob_id = '{}'".format(sel_extjob_id)
            cur.execute(sql)
            result = cur.fetchone()
            self.workarea_txt = result[0]

            # for result in results:
            #     self.cmb_layer_nm.addItem(result[2])

        except Exception as e:
            QMessageBox.warning(self, "SQL ERROR", str(e))

    def refreshUI(self):
        if self.btn_start_inspect.isVisible() == False:
            # TODO: 이전에 변경 탐지에 대한 정보는 어떻게
            self.btn_start_inspect.setVisible(True)
            self.btn_accept.setDisabled(True)
            self.btn_next.setDisabled(True)
            self.btn_prev.setDisabled(True)
            self.btn_reject.setDisabled(True)
            self.btn_make_report.setDisabled(True)

            self.progressBar.hide()
            self.lbl_progress.hide()

    def hdrCmbExtjobNmIndexChange(self):
        self.addLayerList()

    def addLayerList(self):
        self.cmb_layer_nm.clear()

        self.receive_id = self.cmb_receive_id.currentText()

        cur = self.plugin.conn.cursor()
        sel_extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
        sql = u"select layer_nm, receive_dttm from extjob.receive_main where extjob_id = '{}' and " \
              u"receive_id = '{}'".format(sel_extjob_id, self.receive_id)

        cur.execute(sql)
        results = cur.fetchall()

        self.cmb_layer_nm.addItem('')
        for result in results:
            self.cmb_layer_nm.addItem(result[0])
            self.receive_dttm = result[1]

    def hdrClickBtnStartInspect(self):
        if self.cmb_layer_nm.currentText() == "":
            QMessageBox.warning(self, u"오류", u"검수할 레이어를 선택하셔야합니다.")
            return

        if self.edt_inpector.text() == "":
            QMessageBox.warning(self, u"오류", u"검수자가 기록되어야합니다.")
            return

        rc = QMessageBox.question(self, u"확인", u"변경탐지를 시작하시겠습니까?",
                                  QMessageBox.Yes, QMessageBox.No)
        if rc != QMessageBox.Yes:
            return

        # 변경된 데이터가 하나도 없을 경우 불필요함으로 변경 유무를 판단하는 곳으로 이동
        # self.btn_start_inspect.setDisabled(True)
        # self.btn_start_inspect.setVisible(False)  # 자리가 좁아 안보이게 하는 것으로 수정
        # self.btn_accept.setDisabled(False)
        # self.btn_next.setDisabled(False)
        # self.btn_prev.setDisabled(False)
        # self.btn_reject.setDisabled(False)
        # self.btn_make_report.setDisabled(False)

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

        if self.numTotal > 0:
            self.btn_start_inspect.setVisible(False)  # 자리가 좁아 안보이게 하는 것으로 수정
            self.btn_accept.setDisabled(False)
            self.btn_next.setDisabled(False)
            self.btn_prev.setDisabled(False)
            self.btn_reject.setDisabled(False)
            self.btn_make_report.setDisabled(False)
            # 변화정보 양을 세서 보여줌
            self.countDiffFeature()
        else:
            QMessageBox.information(self, u"탐지결과", u"변경된 데이터가 없습니다.")
            self.lbl_progress.setText(u"변경 사항 없음")

    def hdrClickBtnNext(self):
        self.iterCurrentObj(True)

    def hdrClickBtnPrev(self):
        self.iterCurrentObj(False)

    def iterCurrentObj(self, forward=True):
        # 초기화 되지 않으면 동작 안되게
        if self.crrIndex is None:
            return

        if forward:
            self.crrIndex += 1
            if self.crrIndex >= len(self.inspectList):
                self.crrIndex = 0
        else:
            self.crrIndex -= 1
            if self.crrIndex < 0:
                self.crrIndex = len(self.inspectList)-1

        crrFeature = self.inspectList[self.crrIndex]
        mod_type = crrFeature['mod_type']
        res = crrFeature['inspect_res']
        self.edt_reject_reason.clear()

        mod_type_txt = ""
        if mod_type == "a":
            mod_type_txt = u"추가"
        elif mod_type == "r":
            mod_type_txt = u"삭제"
        elif mod_type == "eg":
            mod_type_txt = u"도형변경"
        elif mod_type == "ef":
            mod_type_txt = u"속성변경"

        insp_stat_txt = ""
        if res == "accept":
            insp_stat_txt = u"승인됨"
        elif res == "reject":
            insp_stat_txt = u"거부됨"
            self.edt_reject_reason.setPlainText(crrFeature['reject_reason'])
        else:
            insp_stat_txt = u"미검수"

        message = u"{}/{}(미검수 {}개) : {}({})".format(self.crrIndex+1, self.numTotal, self.numTotal-self.numProcessed,
                                                    mod_type_txt, insp_stat_txt)
        self.lbl_progress.setText(message)

        geom = self.inspectList[self.crrIndex].geometry()
        bound = geom.boundingBox()
        canvas = self.plugin.iface.mapCanvas()
        canvas.setExtent(bound)
        canvas.zoomOut()
        canvas.refresh()

    def hdrClickBtnAccept(self):
        # 초기화 되지 않으면 동작 안되게
        if self.crrIndex < 0:
            return

        if self.edt_reject_reason.toPlainText() != "":
            rc = QMessageBox.question(self, u"주의", u"거부사유가 입력되어 있습니다.\n"
                                              u"정말 승인하시겠습니까?"
                                 , QMessageBox.Yes, QMessageBox.No)
            if rc != QMessageBox.Yes:
                return

        crrFeature = self.inspectList[self.crrIndex]
        origin_ogc_fid = crrFeature['origin_ogc_fid']
        receive_ogc_fid = crrFeature['receive_ogc_fid']
        res = crrFeature['inspect_res']
        if res:
            rc = QMessageBox.question(self, u"주의", u"이미 처리한 객체입니다. \n"
                                              u"승인상태를 변경하시겠습니까?"
                                 , QMessageBox.Yes, QMessageBox.No)
            if rc != QMessageBox.Yes:
                return
            self.numProcessed -= 1

        crrFeature['inspect_res'] = 'accept'
        crrFeature['reject_reason'] = ''

        cur = self.plugin.conn.cursor()
        sql = u"update extjob.inspect_objlist set inspect_res = 'accept', inspect_dttm = CURRENT_TIMESTAMP  " \
              u"where inspect_id = '{}' and layer_nm = '{}' " \
              u"and origin_ogc_fid = {} and receive_ogc_fid = {}"\
            .format(self.inspect_id, self.layer_nm, origin_ogc_fid, receive_ogc_fid)
        cur.execute(sql)

        self.plugin.conn.commit()

        self.edt_reject_reason.setPlainText("")
        self.numProcessed += 1
        self.iterCurrentObj()

    def hdrClickBtnReject(self):
        # 초기화 되지 않으면 동작 안되게
        if self.crrIndex < 0:
            return

        rejectReason = self.edt_reject_reason.toPlainText()
        if rejectReason == "":
            QMessageBox.warning(self, u"주의", u"거부사유를 입력하셔야 합니다.")
            return

        crrFeature = self.inspectList[self.crrIndex]
        origin_ogc_fid = crrFeature['origin_ogc_fid']
        receive_ogc_fid = crrFeature['receive_ogc_fid']
        res = crrFeature['inspect_res']
        if res:
            rc = QMessageBox.question(self, u"주의", u"이미 처리한 객체입니다. \n"
                                                   u"승인상태를 변경하시겠습니까?"
                                      , QMessageBox.Yes, QMessageBox.No)
            if rc != QMessageBox.Yes:
                return
            self.numProcessed -= 1

        crrFeature['inspect_res'] = 'reject'
        crrFeature['reject_reason'] = rejectReason

        cur = self.plugin.conn.cursor()
        sql = u"update extjob.inspect_objlist set inspect_res = 'reject', inspect_dttm = CURRENT_TIMESTAMP, " \
              u"reject_reason = '{}' " \
              u"where inspect_id = '{}' and layer_nm = '{}' " \
              u"and origin_ogc_fid = {} and receive_ogc_fid = {}" \
            .format(rejectReason, self.inspect_id, self.layer_nm, origin_ogc_fid, receive_ogc_fid)
        cur.execute(sql)

        self.plugin.conn.commit()

        # 거부시 화면 저장
        obj_id = crrFeature['id']
        image_path = os.path.join(self.plugin.plugin_dir, u"report_template", "word/media/image{}.png".format(100 + obj_id))
        canvas = self.plugin.iface.mapCanvas()
        canvas.saveAsImage(image_path)

        self.edt_reject_reason.setPlainText("")
        self.numProcessed += 1
        self.iterCurrentObj()

    def findDiff(self):
        try:
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
                  "where table_schema = 'nfsd' and table_name = '{}' order by ordinal_position asc".format(self.layer_nm)
            cur.execute(sql)
            column_nm = []
            results = cur.fetchall()

            for list in results:
                column_nm.append(list[0])

            column_nm.remove('ogc_fid')
            column_nm.remove('wkb_geometry')

            self.column_sql = ','.join(column_nm)

            self.id_column = column_nm[0]

            # 테이블의 geometry를 가져옴
            sql = u"select GeometryType(wkb_geometry) from nfsd.{} limit 1".format(self.layer_nm)
            cur.execute(sql)
            result = cur.fetchone()

            self.geom_type = result[0]

            if self.geom_type == 'MULTIPOLYGON': # 폴리곤 일때는 GeoHash 와 면적 생성
                self.geohash_sql = u'st_geohash(ST_Transform(st_centroid(st_envelope(wkb_geometry)), 4326), ' \
                                   u'12) as mbr_hash_12, round( CAST(st_area(wkb_geometry) as numeric), 1) as geom_area'
            elif self.geom_type == 'MULTILINESTRING': # 선 일때는 GeoHash 와 길이 생성
                self.geohash_sql = u'st_geohash(ST_Transform(st_centroid(st_envelope(wkb_geometry)), 4326), 12) ' \
                                   u'as mbr_hash_12, round( CAST(st_length(wkb_geometry) as numeric), 1) as geom_length'
            else: # 점 일때는 GeoHash 만 생성
                self.geohash_sql = u'st_geohash(ST_Transform(wkb_geometry, 4326), 12) as mbr_hash_12'

            # 속성, 지오메트리 까지 같은 데이터
            self.findSame()
            # 속성은 같고 지오메트리만 바뀐 데이터
            self.findEditOnlyGeomety()
            # 속성만 바뀐 데이터
            self.findEditAttr()
            # 삭제된 데이터
            self.findDel()
            # 추가된 데이터
            self.findAdd()

            self.sql_rep.write('\n')
            self.sql_rep.close()

            sql = "drop view extjob.{}_view ".format(self.layer_nm)
            cur.execute(sql)

            self.plugin.conn.commit()

        except Exception as e:
            self.plugin.conn.rollback()

            # view를 생성한후 에러가 발생했을 경우 view를 삭제
            sql = u"SELECT count(table_name) FROM information_schema.tables " \
                  u"WHERE table_schema='extjob' and table_name = '{}_view'".format(self.layer_nm)
            cur.execute(sql)
            res = cur.fetchone()

            if res[0] > 0:
                sql = "drop view extjob.{}_view ".format(self.layer_nm)
                cur.execute(sql)
                self.plugin.conn.commit()

            QMessageBox.warning(self, u"오류", str(e))

    def findSame(self):
        cur = self.plugin.conn.cursor()

        add_sql = ''
        if self.geom_type == 'MULTIPOLYGON':  # 폴리곤 일때는 면적 비교 추가
            add_sql = u'and e.geom_area between o.geom_area*0.95 and o.geom_area*1.05'
        elif self.geom_type == 'MULTILINESTRING':  # 선 일때는 길이 비교 추가
            add_sql = u'and e.geom_length between o.geom_length*0.95 and o.geom_length*1.05'
        else:  # 점 일때는 PK 비교 추가
            add_sql = u'and o.{0} = e.{0}'.format(self.id_column)

        sql = u"with geom_same_data as ( select o.* from (select {0},{1} from extjob.{2}_view) as o " \
              u"inner join (select {0},{1} from extjob.{3}_{2}) as e " \
              u"on o.mbr_hash_12 = e.mbr_hash_12 {6} )," \
              u"same_data as (select o.* from (select {0} from geom_same_data) as o " \
              u"inner join (select {0} from extjob.{3}_{2}) as e on (o.*) = (e.*))," \
              u"origin as ( select o.ogc_fid as origin_ogc_fid, a.{4} from same_data as a " \
              u"inner join extjob.{2}_view as o on a.{4} = o.{4} )," \
              u"receive as (select o.ogc_fid as receive_ogc_fid, a.{4} from same_data as a " \
              u"inner join extjob.{3}_{2} as o on a.{4} = o.{4} ) " \
              u"insert into extjob.inspect_objlist( inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type )" \
              u"select '{5}' as inspect_id, '{2}' as layer_nm, origin_ogc_fid, receive_ogc_fid, " \
              u"'s' as mod_type from origin, receive where origin.{4} = receive.{4}"\
            .format(self.column_sql,self.geohash_sql,self.layer_nm,
                    self.receive_id,self.id_column,self.inspect_id,add_sql)
        self.sql_rep.write("same_data : " + sql + "\n")
        cur.execute(sql)

    def findEditOnlyGeomety(self):
        cur = self.plugin.conn.cursor()

        sql = u"with attr_same_data as (select o.* from (select {0} from extjob.{1}_view) as o " \
              u"inner join (select {0} from extjob.{2}_{1}) as e on (o.*) = (e.*) ), " \
              u"same_data as( select wkb_geometry,{0} from " \
              u"(select origin_ogc_fid from extjob.inspect_objlist where mod_type = 's' and inspect_id = '{3}') as s " \
              u"inner join extjob.{1}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
              u"join_geom as ( select o.wkb_geometry, a.* from attr_same_data as a " \
              u"inner join extjob.{1}_view as o on a.{4} = o.{4} ), " \
              u"geo_edit as ( select * from join_geom except select * from same_data) " \
              u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
              u"select '{3}' as inspect_id, '{1}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'eg' as mod_type " \
              u"from (select ogc_fid as origin_ogc_fid,e.{4} from geo_edit as e " \
              u"inner join extjob.{1}_view as o on e.{4} = o.{4}) as origin, " \
              u"(select ogc_fid as receive_ogc_fid,e.{4} from geo_edit as e " \
              u"inner join extjob.{2}_{1} as o on e.{4} = o.{4}) as edit where origin.{4} = edit.{4}"\
            .format(self.column_sql, self.layer_nm, self.receive_id, self.inspect_id, self.id_column)
        self.sql_rep.write("edit_geom_data : " + sql + "\n")
        cur.execute(sql)

    def findEditAttr(self):
        cur = self.plugin.conn.cursor()

        if self.geom_type == 'MULTIPOLYGON':  # 폴리곤 일때는 GeoHash 와 면적 생성
            sql = u"with same as (select {0}, {1} from (select origin_ogc_fid from extjob.inspect_objlist " \
                  u"where mod_type = 's' and inspect_id = '{2}') as s " \
                  u"inner join extjob.{3}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
                  u"om as (select {0}, {1} from extjob.{3}_view except select * from same ), " \
                  u"em as (select {0}, {1} from extjob.{4}_{3} except select * from same ), " \
                  u"geometry as ( select mbr_hash_12,geom_area from ( select om.* from om " \
                  u"inner join em on em.mbr_hash_12 = om.mbr_hash_12 and em.geom_area = om.geom_area) as t) " \
                  u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
                  u"select '{2}' as inspect_id, '{3}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'ef' as mod_type " \
                  u"from (select ogc_fid as origin_ogc_fid, o.mbr_hash_12, o.geom_area from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{3}_view ) as o " \
                  u"on (geometry.mbr_hash_12,geometry.geom_area)=(o.mbr_hash_12,o.geom_area)) as origin, " \
                  u"(select ogc_fid as receive_ogc_fid, o.mbr_hash_12, o.geom_area from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{4}_{3} ) as o " \
                  u"on (geometry.mbr_hash_12,geometry.geom_area)=(o.mbr_hash_12,o.geom_area)) as receive " \
                  u"where (origin.mbr_hash_12,origin.geom_area) = (receive.mbr_hash_12,receive.geom_area)" \
                .format(self.column_sql, self.geohash_sql, self.inspect_id,
                        self.layer_nm, self.receive_id)
        elif self.geom_type == 'MULTILINESTRING':  # 선 일때는 GeoHash 와 길이 생성
            sql = u"with same as (select {0}, {1} from (select origin_ogc_fid from extjob.inspect_objlist " \
                  u"where mod_type = 's' and inspect_id = '{2}') as s " \
                  u"inner join extjob.{3}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
                  u"om as (select {0}, {1} from extjob.{3}_view except select * from same ), " \
                  u"em as (select {0}, {1} from extjob.{4}_{3} except select * from same ), " \
                  u"geometry as ( select mbr_hash_12,geom_length from ( select om.* from om " \
                  u"inner join em on em.mbr_hash_12 = om.mbr_hash_12 and em.geom_length = om.geom_length) as t) " \
                  u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
                  u"select '{2}' as inspect_id, '{3}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'ef' as mod_type " \
                  u"from (select ogc_fid as origin_ogc_fid, o.mbr_hash_12, o.geom_length from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{3}_view ) as o " \
                  u"on (geometry.mbr_hash_12,geometry.geom_length)=(o.mbr_hash_12,o.geom_length)) as origin, " \
                  u"(select ogc_fid as receive_ogc_fid, o.mbr_hash_12, o.geom_length from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{4}_{3} ) as o " \
                  u"on (geometry.mbr_hash_12,geometry.geom_length)=(o.mbr_hash_12,o.geom_length)) as receive " \
                  u"where (origin.mbr_hash_12,origin.geom_length) = (receive.mbr_hash_12,receive.geom_length)" \
                .format(self.column_sql, self.geohash_sql, self.inspect_id,
                        self.layer_nm, self.receive_id)
        else:  # 점 일때는 GeoHash 만 생성
            sql = u"with same as (select {0}, {1} from (select origin_ogc_fid from extjob.inspect_objlist " \
                  u"where mod_type = 's' and inspect_id = '{2}') as s " \
                  u"inner join extjob.{3}_view as o on s.origin_ogc_fid = o.ogc_fid), " \
                  u"om as (select {0}, {1} from extjob.{3}_view except select * from same ), " \
                  u"em as (select {0}, {1} from extjob.{4}_{3} except select * from same ), " \
                  u"geometry as ( select mbr_hash_12 from ( select om.* from om " \
                  u"inner join em on em.mbr_hash_12 = om.mbr_hash_12 ) as t) " \
                  u"insert into extjob.inspect_objlist(inspect_id, layer_nm, origin_ogc_fid, receive_ogc_fid, mod_type) " \
                  u"select '{2}' as inspect_id, '{3}' as layer_nm, origin_ogc_fid, receive_ogc_fid, 'ef' as mod_type " \
                  u"from (select ogc_fid as origin_ogc_fid, o.mbr_hash_12 from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{3}_view ) as o " \
                  u"on geometry.mbr_hash_12= o.mbr_hash_12) as origin, " \
                  u"(select ogc_fid as receive_ogc_fid, o.mbr_hash_12 from geometry " \
                  u"inner join (select ogc_fid, {1} from extjob.{4}_{3} ) as o " \
                  u"on geometry.mbr_hash_12 = o.mbr_hash_12) as receive " \
                  u"where origin.mbr_hash_12 = receive.mbr_hash_12" \
                .format(self.column_sql, self.geohash_sql, self.inspect_id,
                        self.layer_nm, self.receive_id)

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

        symbol = None
        if maintain_data.wkbType() == QGis.WKBMultiPolygon:
            symbol = QgsFillSymbolV2().createSimple({'color_border': 'gray', 'width_border': '0.5',
                                                     'style': 'no', 'style_border': 'solid'})
        elif maintain_data.wkbType() == QGis.WKBMultiLineString:
            symbol = QgsLineSymbolV2().createSimple({'color': 'gray', 'width': '0.5',
                                                     'style': 'solid'})
        else:
            symbol = QgsMarkerSymbolV2.createSimple({'name': 'circle', 'color': 'gray', 'size': '2',
                                                     'outline_style': 'no'})

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
                symbol = QgsFillSymbolV2().createSimple({'color_border': color, 'width_border': '1',
                                                      'style': 'no', 'style_border': 'solid'})
            elif diff_data_type == QGis.WKBMultiLineString:
                symbol = QgsLineSymbolV2().createSimple({'color': color, 'width': '1',
                                                         'style': 'solid'})
            else:
                symbol = QgsMarkerSymbolV2.createSimple({'name': 'circle', 'color': color , 'size': '2',
                                                         'outline_style': 'no'})
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

        self.numTotal = len(self.inspectList)
        self.numProcessed = 0

        # 변경된 데이터가 없을 경우
        if self.numTotal <= 0:
            return

        # 첫번째 객체로 가기
        self.iterCurrentObj(True)

    def insertInspectInfo(self):
        # 검수ID, 검수 날짜 생성
        cur = self.plugin.conn.cursor()
        sql = u"SELECT nextid('AD') as extjob_id, current_timestamp as mapext_dttm"
        cur.execute(sql)
        result = cur.fetchone()
        self.inspect_id = result[0]
        self.inspect_dttm = result[1]

        self.receive_id =  self.cmb_receive_id.currentText()
        self.extjob_id = self.cmb_extjob_nm.itemData(self.cmb_extjob_nm.currentIndex())
        self.inspecter = self.edt_inpector.text()

        # TODO: Secure Coding
        # sql = u"INSERT INTO extjob.inspect_main(inspect_id, extjob_id, receive_id, start_dttm, inspecter_nm) " \
        #       u"VALUES ('{}','{}','{}','{}','{}')"\
        #     .format(self.inspect_id, self.extjob_id, self.receive_id, inspect_dttm, self.inspecter)
        # cur.execute(sql)
        sql = u"INSERT INTO extjob.inspect_main(inspect_id, extjob_id, receive_id, start_dttm, inspecter_nm) " \
              u"VALUES (%s, %s, %s, %s, %s)"
        cur.execute(sql, (self.inspect_id, self.extjob_id, self.receive_id, self.inspect_dttm, self.inspecter))

        self.plugin.conn.commit()

    def countDiffFeature(self):
        cur = self.plugin.conn.cursor()
        # TODO: Secure Coding
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

        self.num_add = diff_count['a']
        self.num_remove = diff_count['r']
        self.num_edit_geom = diff_count['eg']
        self.num_edit_attr = diff_count['ef']
        self.num_stay = diff_count['s']

        QMessageBox.information(self, u"탐지결과", info)

        # self.lbl_progress.setText(info)

    # http://etienned.github.io/posts/extract-text-from-word-docx-simply/
    def hdrClickBtnMakeReport(self):
        if self.numTotal != self.numProcessed:
            rc = QMessageBox.question(self, u"확인", u"아직 검수하지 않은 객체가 {}개 있습니다.\n"
                                                   u"그래도 검수 리포트를 작성하시겠습니까?".format(self.numTotal-self.numProcessed)
                                      , QMessageBox.Yes, QMessageBox.No)
            if rc != QMessageBox.Yes:
                return

        # 결과 탐지 수행
        numAccept = 0
        numReject = 0
        numMiss = 0
        for obj in self.inspectList:
            # 변경탐지 결과 요약
            insp_res = obj['inspect_res']

            # 검수결과 요약 (승인, 거부, 미검수)
            if insp_res == "accept":
                numAccept += 1
            elif insp_res == "reject":
                numReject += 1
            else:
                numMiss += 1

        # WORD 문서 생성
        extjob_nm = self.cmb_extjob_nm.currentText()
        extjob_id = self.extjob_id
        inspector_name = self.edt_inpector.text()
        layer_nm = self.cmb_layer_nm.currentText()
        worker_nm = self.cmb_worker_nm.currentText()
        order_dt = self.date_mapext_dttm.date().toString(u'yyyy년 M월 d일')
        basedata_dt = self.date_basedata_dt.date().toString(u'yyyy년 M월 d일')
        area_list = self.workarea_txt
        receive_dt = self.receive_dttm.strftime(u'%Y년 %m월 %d일'.encode('UTF-8')).decode('UTF-8')
        receive_id = self.receive_id
        num_add = self.num_add
        num_remove = self.num_remove
        num_edit_geom = self.num_edit_geom
        num_edit_attr = self.num_edit_attr
        num_stay = self.num_stay
        inspect_dt = self.inspect_dttm.strftime(u'%Y년 %m월 %d일'.encode('UTF-8')).decode('UTF-8')
        num_accept = numAccept
        num_reject = numReject
        num_miss = numMiss
        final_result = u"검수통과" if (num_reject<=0 and num_miss<=0) else u"보완후 재검수"
        fileFilter = "MS Word Files (*.docx)"
        crrTime = time.localtime()
        # TODO: 레포트 경로 저장되게 수정
        defFileName = u"/temp/{}_{}.docx".format(extjob_nm, time.strftime("%Y%m%d", crrTime))
        fileName = QFileDialog.getSaveFileName(self.plugin.iface.mainWindow(),
            u'레포트 파일명을 입력해 주세요.', defFileName, fileFilter)
        if not fileName:
            return

        try:
            os.chdir(os.path.join(self.plugin.plugin_dir, u"report_template"))
            with zipfile.ZipFile(fileName, 'w') as zf:
                # 고정 파일들
                zf.write("[Content_Types].xml")
                zf.write("_rels/.rels")
                zf.write("customXml/item1.xml")
                zf.write("customXml/item2.xml")
                zf.write("customXml/item3.xml")
                zf.write("customXml/itemProps1.xml")
                zf.write("customXml/itemProps2.xml")
                zf.write("customXml/itemProps3.xml")
                zf.write("customXml/_rels/item1.xml.rels")
                zf.write("customXml/_rels/item2.xml.rels")
                zf.write("customXml/_rels/item3.xml.rels")
                zf.write("docProps/app.xml")
                zf.write("docProps/core.xml")
                zf.write("docProps/custom.xml")
                zf.write("word/endnotes.xml")
                zf.write("word/fontTable.xml")
                zf.write("word/footnotes.xml")
                zf.write("word/header1.xml")
                zf.write("word/header2.xml")
                zf.write("word/numbering.xml")
                zf.write("word/settings.xml")
                zf.write("word/styles.xml")
                zf.write("word/webSettings.xml")
                zf.write("word/_rels/settings.xml.rels")
                zf.write("word/glossary/document.xml")
                zf.write("word/glossary/fontTable.xml")
                zf.write("word/glossary/numbering.xml")
                zf.write("word/glossary/settings.xml")
                zf.write("word/glossary/styles.xml")
                zf.write("word/glossary/webSettings.xml")
                zf.write("word/glossary/_rels/document.xml.rels")
                zf.write("word/theme/theme1.xml")

                # 주 문서부분
                word_document = u''
                with open("word/document.xml.tmpl", "r") as f:
                    data = f.read()
                    word_document = data.decode('UTF-8')
                word_document = word_document.replace(u'<!--{{extjob_nm}}-->', extjob_nm)
                word_document = word_document.replace(u'<!--{{extjob_id}}-->', extjob_id)
                word_document = word_document.replace(u'<!--{{inspector_name}}-->', inspector_name)
                word_document = word_document.replace(u'<!--{{layer_nm}}-->', layer_nm)
                word_document = word_document.replace(u'<!--{{worker_nm}}-->', worker_nm)
                word_document = word_document.replace(u'<!--{{order_dt}}-->', order_dt)
                word_document = word_document.replace(u'<!--{{basedata_dt}}-->', basedata_dt)
                word_document = word_document.replace(u'<!--{{area_list}}-->', area_list)
                word_document = word_document.replace(u'<!--{{receive_dt}}-->', receive_dt)
                word_document = word_document.replace(u'<!--{{receive_id}}-->', receive_id)
                word_document = word_document.replace(u'<!--{{num_add}}-->', str(num_add))
                word_document = word_document.replace(u'<!--{{num_remove}}-->', str(num_remove))
                word_document = word_document.replace(u'<!--{{num_edit_geom}}-->', str(num_edit_geom))
                word_document = word_document.replace(u'<!--{{num_edit_attr}}-->', str(num_edit_attr))
                word_document = word_document.replace(u'<!--{{num_stay}}-->', str(num_stay))
                word_document = word_document.replace(u'<!--{{inspect_dt}}-->', inspect_dt)
                word_document = word_document.replace(u'<!--{{num_accept}}-->', str(num_accept))
                word_document = word_document.replace(u'<!--{{num_reject}}-->', str(num_reject))
                word_document = word_document.replace(u'<!--{{num_miss}}-->', str(num_miss))
                word_document = word_document.replace(u'<!--{{final_result}}-->', final_result)

                # 거부 객체 리포트
                img_id_list = []
                i_rg_start = word_document.find('<!--%start for rejects%-->')
                i_rg_end = word_document.find('<!--%end for rejects%-->', i_rg_start) + len('<!--%end for rejects%-->')

                if num_reject <= 0:  # 거부된 객체가 없는 경우
                    message = u'<w:p w:rsidR="00361A42" w:rsidRDefault="00D92755" w:rsidP="008A6D62"><w:pPr><w:pStyle w:val="20"/><w:rPr><w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕" w:cstheme="minorBidi"/><w:sz w:val="18"/><w:szCs w:val="22"/></w:rPr></w:pPr><w:r><w:rPr><w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕"/><w:sz w:val="22"/></w:rPr><w:t>거부된 객체가 없습니다.</w:t></w:r></w:p>'
                    word_document = word_document[:i_rg_start-1] + message + word_document[i_rg_end+1:]
                else: # 거부된 객체가 있는 경우
                    reject_rpt_tmpl = word_document[i_rg_start:i_rg_end]
                    i_row_start = reject_rpt_tmpl.find('<!--%start for row%-->')
                    i_row_end = reject_rpt_tmpl.find('<!--%end for row%-->', i_row_start) + len('<!--%end for row%-->')
                    table_row_tmpl = reject_rpt_tmpl[i_row_start:i_row_end]

                    obj_no = 0
                    detail_doc = u''
                    for obj in self.inspectList:
                        insp_res = obj['inspect_res']
                        if insp_res  == "reject":
                            obj_no += 1
                            img_id = obj['id']
                            detail_doc +=  reject_rpt_tmpl[:i_row_start-1]

                            # 객체의 속성과 값을 기록
                            for field in obj.fields():
                                key = field.name()
                                val = obj[key]
                                temp = table_row_tmpl.replace("<!--{{key}}-->", key)
                                temp = temp.replace("<!--{{value}}-->", unicode(val))
                                detail_doc += temp

                            detail_doc +=  reject_rpt_tmpl[i_row_end+1:]

                            detail_doc = detail_doc.replace("<!--{{reject_index}-->", str(obj_no))
                            detail_doc = detail_doc.replace("<!--{{reject_region}}-->", obj['reject_reason'])
                            detail_doc = detail_doc.replace("<!--{{image_id}}-->", str(100+img_id))
                            img_id_list.append(img_id)

                    word_document = word_document[:i_rg_start - 1] + detail_doc + word_document[i_rg_end + 1:]

                # 기록하고 압축파일에 포함
                with open("word/document.xml", "w") as f:
                    f.write(word_document.encode('UTF-8'))
                zf.write("word/document.xml")

                # Resource List
                rels_doc = u""
                with open("word/_rels/document.xml.rels.tmpl", "r") as f:
                    data = f.read()
                    rels_tmpl = data.decode('UTF-8')
                    i_start = rels_tmpl.find('<!--%start for images%-->')
                    i_end = rels_tmpl.find('<!--%end for images%-->', i_start) + len('<!--%end for images%-->')

                    rels_doc = rels_tmpl[:i_start-1]
                    if num_reject > 0:  # 거부된 객체가 있는 경우
                        image_rel_tmpl = rels_tmpl[i_start:i_end]
                        for img_id in img_id_list:
                            image_name = "word/media/image{}.png".format(100 + img_id)
                            zf.write(image_name)
                            rels_doc += image_rel_tmpl.replace('<!--{{image_id}}-->', str(img_id+100))
                    rels_doc += rels_tmpl[i_end+1:]

                with open("word/_rels/document.xml.rels", "w") as f:
                    f.write(rels_doc.encode('UTF-8'))
                zf.write("word/_rels/document.xml.rels")

            QMessageBox.information(self, u"작업완료", u"검수 레포트 작성이 완료되었습니다.")
        except Exception as e:
            QMessageBox.warning(self, u"오류", u"레포트 작성중 오류가 발생하였습니다.\n{}".format(e))
