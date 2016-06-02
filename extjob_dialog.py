# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DlgExtjob
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
import ConfigParser
from glob import glob

from ui.extjob_dialog_base import Ui_Dialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/extjob.ui'))


# class DlgExtjob(QtGui.QDialog, FORM_CLASS):
class DlgExtjob(QtGui.QDialog, Ui_Dialog):
    conn = None,  # type: psycopg2._connect
    adminList = None,  # type: List

    def __init__(self,
                 plugin  # type: NgiiMapJobManager
                 ):
        """Constructor."""
        parent = plugin.iface.mainWindow()
        super(DlgExtjob, self).__init__(parent)
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
        plugin.clearRb()

    def setInitValue(self, defaultBjcd = '3611011100'):
        self.fillWorkerList()

        crrDate = QDate.currentDate()
        self.date_mapext_dttm.setDate(crrDate)
        self.date_basedata_dt.setDate(crrDate)

        self.getSidoList()
        self.fillCmbSido(defaultBjcd)
        crrSidoEnt = self.getSggList(defaultBjcd)
        if crrSidoEnt:
            self.fillCmbSgg(crrSidoEnt['sub'], defaultBjcd)
            crrSggEnt = self.getEmdList(defaultBjcd)
            if crrSggEnt:
                self.fillCmbEmd(crrSggEnt['sub'], defaultBjcd)
            else:
                self.cmb_emd.clear()
        else:
            self.cmb_sgg.clear()

    def connectFct(self):
        self.cmb_worker_nm.currentIndexChanged.connect(self.hdrCmbWorkerIndexChange)
        self.cmb_worker_nm.editTextChanged.connect(self.hdrCmbWorkerIndexChange)
        self.btn_selectfile.clicked.connect(self.hdrClickSelectFile)
        self.cmb_sido.currentIndexChanged.connect(self.hdrCmbSidoIndexChange)
        self.cmb_sgg.currentIndexChanged.connect(self.hdrCmbSggIndexChange)
        self.btn_add_admin.clicked.connect(self.hdrClickAddAdmin)
        self.btn_add_mapbox.clicked.connect(self.hdrClickAddMapbox)
        self.btn_gendata.clicked.connect(self.hdrClickGenData)
        # self.date_mapext_dttm.dateChanged.connect(self.checkMapextDate)
        self.date_basedata_dt.dateChanged.connect(self.checkBasedataDate)
        # self.close.connect(self.hdrClose)

    # 대화상자 닫히는 것은 그냥 이벤트 캐치로 안되고 부모 클래스 함수를 오버라이드 해야 한다.
    def closeEvent(self, evnt):
        # 켰다가 이름쓰고 그냥 닫기만 해도 저장됨 .. 위치 변경 파일 생성가 동등한 위치로 옮김
        # self.hdrClose()
        super(DlgExtjob, self).closeEvent(evnt)

    def fillWorkerList(self):
        self.cmb_worker_nm.clear()

        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))
        names = conf.options('Worker_nm')

        for name in names:
            worker_nm = conf.get('Worker_nm', name)
            self.cmb_worker_nm.addItem(worker_nm.decode('utf-8'))

        # self.cmb_worker_nm.addItem(u'중앙항업')
        # self.cmb_worker_nm.addItem(u'한진항업')
        # self.cmb_worker_nm.addItem(u'범아항업')
        # self.cmb_worker_nm.addItem(u'삼아항업')
        self.cmb_worker_nm.setCurrentIndex(-1)

    def hdrCmbWorkerIndexChange(self):
        # 작업지시일과 업체명 합쳐 작업명으로
        worker_nm = self.cmb_worker_nm.currentText()
        date = self.date_mapext_dttm.date()

        title = u"{}_{}".format(date.toString('yyyyMd'), worker_nm)
        self.edt_extjob_nm.setText(title)

    def hdrClickSelectFile(self):
        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        # 이미지 파일, 도면만 선택 가능
        fileFilter = "Image Files (*.jpg *.png *.gif *.tif);;DXF Files (*.dxf)"
        fileName = QFileDialog.getOpenFileName(self.plugin.iface.mainWindow(), u'배경 자료를 선택해 주십시오.',
                                               conf.get('Dir_Info','basemap_dir'),fileFilter)

        self.edt_basedata_nm.setText(fileName)

        base_fileName = os.path.basename(fileName)
        if os.path.splitext(base_fileName)[1] == '.dxf':
            self.rdo_basetype_map.setChecked(True)
        else:
            self.rdo_basetype_photo.setChecked(True)

        with open(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"), "w") as confFile:
            conf.set("Dir_Info", "basemap_dir", os.path.dirname(fileName))
            conf.write(confFile)

    def getSidoList(self):
        try:
            self.adminList = []
            sql = "select bjcd, name from nfsd.nf_a_g01102 order by bjcd"
            cur = self.conn.cursor()  # type: psycopg2.cursor
            cur.execute(sql)
            sidoList = cur.fetchall()
            for sido in sidoList:
                sidoEnt = {'bjcd': sido[0], 'name': sido[1], 'sub': []}
                self.adminList.append(sidoEnt)
        except Exception as e:
            QMessageBox.critical(self, "Connect Error", str(e))

    def fillCmbSido(self, defaultBjcd):
        selectIndex = 0
        self.cmb_sido.clear()
        sidoNameList = []
        i = 0
        for sidoEnt in self.adminList:
            name = sidoEnt['name']
            bjcd = sidoEnt['bjcd']
            self.cmb_sido.addItem(name)
            self.cmb_sido.setItemData(i, bjcd)
            if bjcd[:2] == defaultBjcd[:2]:
                selectIndex = i
            i += 1
        self.cmb_sido.setCurrentIndex(selectIndex)

    def getSggList(self, bjcd):
        try:
            for sidoEnt in self.adminList:
                if sidoEnt['bjcd'][:2] != bjcd[:2]:
                    continue
                if len(sidoEnt['sub']) == 0:
                    cur = self.conn.cursor()
                    sql = "select a.bjcd, a.name, b.name From nfsd.nf_a_g01103 as a " \
                          "left join ( select bjcd, name from nfsd.nf_a_g01103 except select bjcd, name " \
                          "from nfsd.nf_a_g01103 where substr(bjcd, 5, 1) != '0' and concat(left(bjcd, 4),'000000') " \
                          "in (select bjcd from nfsd.nf_a_g01103) ) as b on left(a.bjcd, 4) = left(b.bjcd, 4)" \
                          "where a.bjcd like '{}%' order by b.name,a.bjcd".format(bjcd[:2])
                    cur.execute(sql)
                    sggList = cur.fetchall()
                    for sgg in sggList:
                        sgg_name = sgg[1]
                        if sgg[1] != sgg[2]:
                            sgg_name = u'{} {}'.format(sgg[2],sgg[1])
                        sggEnt = {'bjcd': sgg[0], 'name': sgg_name, 'sub': []}
                        sidoEnt['sub'].append(sggEnt)
                return sidoEnt
        except Exception as e:
            QMessageBox.critical(self, "Connect Error", str(e))

    def fillCmbSgg(self, sggList, defaultBjcd):
        selectIndex = 0
        self.cmb_sgg.clear()
        self.cmb_sgg.addItem(u'*전체*')
        i = 1
        for sggEnt in sggList:
            name = sggEnt['name']
            bjcd = sggEnt['bjcd']
            self.cmb_sgg.addItem(name)
            self.cmb_sgg.setItemData(i, bjcd)
            if bjcd[:5] == defaultBjcd[:5]:
                selectIndex = i
            i += 1
        self.cmb_sgg.setCurrentIndex(selectIndex)

    def getEmdList(self, bjcd):
        try:
            for sidoEnt in self.adminList:
                if sidoEnt['bjcd'][:2] != bjcd[:2]:
                    continue
                sggList = sidoEnt['sub']
                if not sggList:
                    sggList = self.getSggList(bjcd)
                assert (sggList)

                for sggEnt in sggList:
                    if sggEnt['bjcd'][:5] != bjcd[:5]:
                        continue
                    if len(sggEnt['sub']) == 0:
                        cur = self.conn.cursor()
                        sql = "select bjcd, name from nfsd.nf_a_g01106 where bjcd like '{}%' order by name".format(bjcd[:5])
                        cur.execute(sql)
                        emdList = cur.fetchall()
                        for emd in emdList:
                            emdEnt = {'bjcd': emd[0], 'name': emd[1]}
                            sggEnt['sub'].append(emdEnt)
                    return sggEnt
        except Exception as e:
            QMessageBox.critical(self, "Connect Error", str(e))

    def fillCmbEmd(self, emdList, defalutBjcd):
        selectIndex = 0
        self.cmb_emd.clear()
        self.cmb_emd.addItem(u'*전체*')
        i = 1
        for emdEnt in emdList:
            name = emdEnt['name']
            bjcd = emdEnt['bjcd']
            self.cmb_emd.addItem(name)
            self.cmb_emd.setItemData(i, bjcd)
            if bjcd == defalutBjcd:
                selectIndex = i
            i += 1
        self.cmb_emd.setCurrentIndex(selectIndex)

    def hdrCmbSidoIndexChange(self):
        sidoIndex = self.cmb_sido.currentIndex()
        # bjcd = self.adminList[sidoIndex]['bjcd']
        bjcd = self.cmb_sido.itemData(sidoIndex)
        crrSidoEnt = self.getSggList(bjcd)
        if crrSidoEnt:
            self.fillCmbSgg(crrSidoEnt['sub'], bjcd)

    def hdrCmbSggIndexChange(self):
        sidoIndex = self.cmb_sido.currentIndex()
        sggIndex = self.cmb_sgg.currentIndex()

        if sggIndex < 1:
            self.cmb_sgg.setCurrentIndex(0)
            self.cmb_emd.clear()
            self.cmb_emd.addItem(u'*전체*')
            self.cmb_emd.setCurrentIndex(0)
            return

        sggList = self.adminList[sidoIndex]['sub']
        bjcd = self.cmb_sgg.itemData(sggIndex)
        crrSggEnt = self.getEmdList(bjcd)
        if crrSggEnt:
            self.fillCmbEmd(crrSggEnt['sub'], bjcd)

    def hdrClickAddAdmin(self):
        # 값을 알아낸다.
        bjcd = None
        name = None
        table = None

        if self.cmb_emd.currentIndex() != 0:
            bjcd = self.cmb_emd.itemData(self.cmb_emd.currentIndex())
            name = u'{} {} {}'.format(self.cmb_sido.currentText(), self.cmb_sgg.currentText(), self.cmb_emd.currentText())
            table = 'nf_a_g01106'
        elif self.cmb_sgg.currentIndex() != 0:
            bjcd = self.cmb_sgg.itemData(self.cmb_sgg.currentIndex())
            name = u'{} {}'.format(self.cmb_sido.currentText(), self.cmb_sgg.currentText())
            table = 'nf_a_g01103'
        else:
            bjcd = self.cmb_sido.itemData(self.cmb_sido.currentIndex())
            name = self.cmb_sido.currentText()
            table = 'nf_a_g01102'
        assert(bjcd)
        assert(name)
        assert(table)

        # 선택된 영역 리스트에 넣는다.
        areaItems = self.lst_workarea.findItems(name,Qt.MatchExactly)
        if len(areaItems) == 0:
            self.lst_workarea.addItem(name)

            # 도형을 불러온다.
            cur = self.conn.cursor()
            # TODO: WKB로 조회하는 것으로 바꿔아 한다. 계속 실패...
            sql = "select ST_AsText(ST_Transform(wkb_geometry, 5179)) as wkt from nfsd.{} where bjcd='{}'".format(table, bjcd)
            cur.execute(sql)
            row = cur.fetchone()
            wkt = row[0]

            # 기존 영역과 합치고 이동한다.
            self.plugin.addExtjobArea(wkt, True)

    def hdrClickAddMapbox(self):
        QMessageBox.warning(self, u'경고', u'개발중입니다.')

    def hdrClickGenData(self):
        # 필수요소 확인
        if self.edt_extjob_nm.text() == '':
            QMessageBox.warning(self, u'경고', u"작업명이 입력되어야 합니다.")
            return
        if self.lst_workarea.count() == 0:
            QMessageBox.warning(self, u'경고', u"선택된 영역이 없습니다.")
            return

        # 데이터 폴더 선택
        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        folderPath = QFileDialog.getExistingDirectory(self.plugin.iface.mainWindow(),
                                                 u'자료를 생성할 폴더를 선택해 주십시오.',conf.get("Dir_Info", "extjob_dir"))

        with open(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"), "w") as confFile:
            conf.set("Dir_Info", "extjob_dir", folderPath)
            conf.write(confFile)

        if folderPath:
            # 대화상자 닫고
            self.close()

            fileInFolder = glob(os.path.join(folderPath,'*.shp'))
            if len(fileInFolder) != 0:
                rc = QMessageBox.question(self, u"확인", u"폴더가 비어있지 않습니다\n"
                                                           u"파일(들)을 삭제하고 진행하시겠습니까?\n"
                                                            u"(폴더 내 모든 파일이 삭제 됩니다.)",
                                                            QMessageBox.Yes, QMessageBox.No)
                if rc == QMessageBox.Yes:
                    for rmFile in glob(os.path.join(folderPath,"*")):
                        os.remove(rmFile)
                else:
                    rc = QMessageBox.question(self, u"확인", u"그냥 진행하겠습니까??\n"
                                                                     u"외주 데이터에 문제가 발생할 수도 있습니다.",
                                              QMessageBox.Yes, QMessageBox.No)
                    if rc != QMessageBox.Yes:
                        return

            # 데이터 생산
            self.plugin.generateDataFiles(folderPath)
            self.plugin.clearRb()
            self.hdrClose()

    def hdrClose(self):
        conf = ConfigParser.SafeConfigParser()
        conf.read(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"))

        worker_nm = self.cmb_worker_nm.currentText()

        with open(os.path.join(os.path.dirname(__file__), "conf", "NgiiMapJobManager.conf"), "w") as confFile:
            conf.set("Worker_nm", worker_nm.encode('utf-8'), worker_nm.encode('utf-8'))
            conf.write(confFile)

    # def checkMapextDate(self):
    #     date = self.date_mapext_dttm.date()
    #     crr_date = QDate.currentDate()
    #     if date > crr_date:
    #         self.date_mapext_dttm.setDate(crr_date)

    def checkBasedataDate(self):
        date = self.date_basedata_dt.date()
        crr_date = QDate.currentDate()
        if date > crr_date:
            self.date_basedata_dt.setDate(crr_date)

