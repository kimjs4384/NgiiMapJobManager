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
        self.plugin = parent
        self.setupUi(self)
        self.setInitValue()
        self.connectFct()

    def connectFct(self):
        self.cmb_worker_nm.currentIndexChanged.connect(self.hdrCmbWorkerIndexChange)
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
        # TODO: 실제로 DB에서 자료 불러오게 수정
        self.cmb_worker_nm.clear()
        self.cmb_worker_nm.addItem(u'중앙항업')
        self.cmb_worker_nm.addItem(u'한진항업')
        self.cmb_worker_nm.addItem(u'범아항업')
        self.cmb_worker_nm.addItem(u'삼아항업')
        self.cmb_worker_nm.setCurrentIndex(-1)

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
            if not results or len(results) <= 0:
                # QMessageBox.warning(self, u"검색실패", u"조건에 맞는 작업이 없습니다.")
                return

            for result in results:
                extjob_id = result[0]
                extjob_nm = result[1]
                basedata_dt = result[2]
                self.cmb_extjob_nm.addItem(extjob_nm)
                self.cmb_extjob_nm.setItemData(self.cmb_extjob_nm.count(), extjob_id)
                self.date_basedata_dt.setDate(basedata_dt)
        except Exception as e:
            QMessageBox.warning(self, "SQL ERROR", str(e))

        # TODO: 진짜로 조회해 넣기
        self.cmb_receive_id.clear()
        self.cmb_receive_id.addItem("RD20160525_00001")
        self.cmb_layer_nm.clear()
        self.cmb_layer_nm.addItem("nf_a_b01000")

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
        #     QMessageBox.warning(self, "SQL ERROR", str(e))

        legend = self.plugin.iface.legendInterface()
        layers = legend.layers()
        for layer in layers:
            layerType = layer.type()
            if layerType == QgsMapLayer.VectorLayer:
                layerName = layer.name()
                if layerName == "same_data":
                    self.same_data = layer
                elif layerName == "attr_e_edit":
                    self.attr_e_edit = layer
                elif layerName == "move_o_data":
                    self.move_o_data = layer
                elif layerName == "move_e_data":
                    self.move_e_data = layer
                elif layerName == "rm_data":
                    self.rm_data = layer
                elif layerName == "add_data":
                    self.add_data = layer

        legend.setLayerVisible(self.same_data, True)
        time.sleep(1)
        legend.setLayerVisible(self.attr_e_edit, True)
        time.sleep(1)
        legend.setLayerVisible(self.move_o_data, True)
        time.sleep(1)
        legend.setLayerVisible(self.move_e_data, True)
        time.sleep(1)
        legend.setLayerVisible(self.rm_data, True)
        time.sleep(1)
        legend.setLayerVisible(self.add_data, True)
        time.sleep(1)

        sameCount = self.same_data.featureCount()

        info = u"변경탐지결과\n" \
        u"- 신규: {}개\n" \
        u"- 삭제: {}개\n" \
        u"- 도형변경: {}개\n" \
        u"- 속성변경: {}개\n" \
        u"- 유지: {}개".format(
            self.add_data.featureCount(),
            self.rm_data.featureCount(),
            self.move_e_data.featureCount(),
            self.attr_e_edit.featureCount(),
            self.same_data.featureCount()
        )
        self.lbl_progress.setText(info)

        self.inspectList = []
        self.crrIndex = -1
        iter = self.add_data.getFeatures()
        for feature in iter:
            self.inspectList.append(feature)
        iter = self.rm_data.getFeatures()
        for feature in iter:
            self.inspectList.append(feature)
        iter = self.move_e_data.getFeatures()
        for feature in iter:
            self.inspectList.append(feature)
        iter = self.attr_e_edit.getFeatures()
        for feature in iter:
            self.inspectList.append(feature)

        QMessageBox.information(self, u"탐지결과", info)

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