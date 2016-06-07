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
from osgeo import ogr
from osgeo import osr

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
        dycd = self.edt_mapbox.text()
        if dycd == '':
            QMessageBox.warning(self, u'경고', u'도엽명을 입력하셔야 합니다.')
            return

        wkt = self.dycdToGeom(dycd, 5179)
        if not wkt:
            QMessageBox.warning(self, u'경고', u'{} 코드를 가진 도엽이 없습니다.'.format(dycd))
            return

        self.edt_mapbox.clear()
        # 선택된 영역 리스트에 넣는다.
        areaItems = self.lst_workarea.findItems(dycd, Qt.MatchExactly)
        if len(areaItems) == 0:
            self.lst_workarea.addItem(dycd)

            # 기존 영역과 합치고 이동한다.
            self.plugin.addExtjobArea(wkt, True)

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

    def dycdToGeom(self, dycd, epsg_cd=4326):
        # 숫자로만 되어 있지 않으면 오류
        try:
            int(dycd)
        except ValueError:
            return None

        # 도엽코드가 5자보다 짧으면 오류
        if len(dycd) < 5:
            return None

        # 도엽코드 길이에 따라
        if len(dycd) == 5:
            scale = 50000
        elif len(dycd) == 6:
            scale = 25000
        elif len(dycd) == 7:
            scale = 10000
        elif len(dycd) == 8:
            scale = 5000
        elif len(dycd) == 9:
            scale = 1000
        else:  # 9자보다 긴 경우 오류
            return None

        # 5만 도엽코드
        dycd_50k = dycd[:5]

        # 없는 5만 도엽인 경우 오류
        if DYCD_50K_LIST.count(dycd_50k) < 1:
            return None

        i_lat = int(dycd[:2])
        i_lon = int(dycd[2:3])
        idx_50k = int(dycd[3:5])

        base_lat = i_lat
        base_lon = 130 + i_lon if i_lon <= 2 else 120 + i_lon

        y_idx_50k = int((idx_50k - 1) / 4)
        x_idx_50k = (idx_50k - 1) % 4

        base_50k_lat = base_lat + 1 - 0.25 * y_idx_50k
        base_50k_lon = base_lon + 0.25 * x_idx_50k

        # 5만 도엽 기준위치 예외 처리
        # 제주
        if dycd_50k >= '33605' and dycd_50k <= '33608':
            base_50k_lat += -0.1
        # 서귀포
        elif dycd_50k >= '33609' and dycd_50k <= '33612':
            base_50k_lat += -0.1
            base_50k_lon += -5.0 / 60.0
        # 마라도
        elif dycd_50k == '33614':
            base_50k_lat += -0.1
            base_50k_lon += -0.075
        # 울릉도
        elif dycd_50k == '37012':
            base_50k_lat += 0.075

        # 스케일별 영역 확정
        if scale == 50000:
            max_lat = base_50k_lat
            min_lat = max_lat - 0.25
            min_lon = base_50k_lon
            max_lon = min_lon + 0.25
        elif scale == 25000:
            idx_25k = int(dycd[5:6])
            if idx_25k > 4:  # 4 이상의 인덱스면 오류
                return None
            y_idx_25k = int((idx_25k - 1) / 2)
            x_idx_25k = (idx_25k - 1) % 2
            max_lat = base_50k_lat - y_idx_25k * 0.125
            min_lat = max_lat - 0.125
            min_lon = base_50k_lon + x_idx_25k * 0.125
            max_lon = min_lon + 0.125
        elif scale == 10000 or scale == 1000:
            idx_10k = int(dycd[5:7])
            if idx_10k > 25:  # 25 이상의 인덱스면 오류
                return None
            y_idx_10k = int((idx_10k - 1) / 5)
            x_idx_10k = (idx_10k - 1) % 5

            if scale == 10000:
                max_lat = base_50k_lat - y_idx_10k * 0.05
                min_lat = max_lat - 0.05
                min_lon = base_50k_lon + x_idx_10k * 0.05
                max_lon = min_lon + 0.05
            else:  # 1000 축척
                idx_1k = int(dycd[7:9])
                if idx_1k > 100:  # 100 이상 인덱스면 오류
                    return None
                y_idx_1k = int((idx_1k - 1) / 10)
                x_idx_1k = (idx_1k - 1) % 10
                max_lat = base_50k_lat - y_idx_10k * 0.05 - y_idx_1k * 0.005
                min_lat = max_lat - 0.005
                min_lon = base_50k_lon + x_idx_10k * 0.05 + x_idx_1k * 0.005
                max_lon = min_lon + 0.005
        elif scale == 5000:
            idx_5k = int(dycd[5:8])
            if idx_5k > 100:  # 100 이상의 인덱스면 오류
                return None
            y_idx_5k = int((idx_5k - 1) / 10)
            x_idx_5k = (idx_5k - 1) % 10
            max_lat = base_50k_lat - y_idx_5k * 0.025
            min_lat = max_lat - 0.025
            min_lon = base_50k_lon + x_idx_5k * 0.025
            max_lon = min_lon + 0.025

        # WKT 생성
        str_res = "POLYGON (({min_x} {min_y}, {max_x} {min_y}, {max_x} {max_y}, {min_x} {max_y}, {min_x} {min_y}))" \
            .format(min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat)
        if epsg_cd == 4326:
            return str_res

        # 좌표계 변환
        # https://pcjericks.github.io/py-gdalogr-cookbook/projection.html
        source = osr.SpatialReference()
        source.ImportFromEPSG(4326)

        target = osr.SpatialReference()
        target.ImportFromEPSG(epsg_cd)

        transform = osr.CoordinateTransformation(source, target)

        geom = ogr.CreateGeometryFromWkt(str_res)
        geom.Transform(transform)

        res = geom.ExportToWkt()
        return res


DYCD_50K_LIST = ['33601', '33602', '33603', '33604', '33605', '33606', '33607', '33608', '33609', '33610',
                 '33611', '33612', '33614', '34502', '34504', '34505', '34506', '34507', '34508', '34509',
                 '34510', '34512', '34513', '34514', '34516', '34601', '34602', '34603', '34604', '34605',
                 '34606', '34607', '34608', '34609', '34610', '34611', '34612', '34613', '34614', '34615',
                 '34616', '34701', '34702', '34703', '34704', '34705', '34706', '34707', '34708', '34709',
                 '34710', '34711', '34712', '34713', '34714', '34715', '34801', '34802', '34803', '34804',
                 '34805', '34806', '34807', '34809', '34810', '35512', '35516', '35601', '35602', '35603',
                 '35604', '35605', '35606', '35607', '35608', '35609', '35610', '35611', '35612', '35613',
                 '35614', '35615', '35616', '35701', '35702', '35703', '35704', '35705', '35706', '35707',
                 '35708', '35709', '35710', '35711', '35712', '35713', '35714', '35715', '35716', '35801',
                 '35802', '35803', '35804', '35805', '35806', '35807', '35808', '35809', '35810', '35811',
                 '35812', '35813', '35814', '35815', '35816', '35901', '35902', '35903', '35905', '35906',
                 '35909', '35910', '35913', '35914', '36503', '36504', '36507', '36508', '36516', '36601',
                 '36602', '36603', '36604', '36605', '36606', '36607', '36608', '36609', '36610', '36611',
                 '36612', '36613', '36614', '36615', '36616', '36701', '36702', '36703', '36704', '36705',
                 '36706', '36707', '36708', '36709', '36710', '36711', '36712', '36713', '36714', '36715',
                 '36716', '36801', '36802', '36803', '36804', '36805', '36806', '36807', '36808', '36809',
                 '36810', '36811', '36812', '36813', '36814', '36815', '36816', '36901', '36902', '36905',
                 '36906', '36909', '36910', '36913', '36914', '36915', '37012', '37116', '37516', '37604',
                 '37606', '37607', '37608', '37609', '37610', '37611', '37612', '37613', '37614', '37615',
                 '37616', '37701', '37702', '37703', '37704', '37705', '37706', '37707', '37708', '37709',
                 '37710', '37711', '37712', '37713', '37714', '37715', '37716', '37801', '37802', '37803',
                 '37804', '37805', '37806', '37807', '37808', '37809', '37810', '37811', '37812', '37813',
                 '37814', '37815', '37816', '37905', '37909', '37910', '37913', '37914', '38713', '38714',
                 '38715', '38716', '38810', '38811', '38813', '38814', '38815']