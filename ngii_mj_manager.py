# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NgiiMapJobManager
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
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from WidgetContainer import WidgetContainer

import os.path
import ConfigParser
import psycopg2
from qgis.core import *
from qgis.gui import QgsRubberBand
from subprocess import check_output
import sys
from glob import glob
import tempfile
from osgeo import ogr
from osgeo import osr

# Initialize Qt resources from file resources.py
# Import the code for the dialog
from extjob_dialog import DlgExtjob
from receive_dialog import DlgReceive
from inspect_widget import WidgetInspect

# Make safe String for PostgreSQL
def postgres_escape_string(s):
    if not isinstance(s, basestring):
        raise TypeError("%r must be a str or unicode" % (s, ))
    escaped = repr(s)
    if isinstance(s, unicode):
        # assert escaped[:1] == 'u'
        # escaped = escaped[1:]
        escaped = repr(s.encode("UTF-8"))  # Collect UTF-8 problem
    if escaped[:1] == '"':
        escaped = escaped.replace("'", "\\'")
    elif escaped[:1] != "'":
        raise AssertionError("unexpected repr: %s", escaped)
    return "E'%s'" % (escaped[1:-1], )


class NgiiMapJobManager:
    """QGIS Plugin Implementation."""
    pluginName = u'NgiiMapJobManager'
    mainMenuTitle = u"NGII"
    menuIcons = []
    menuTexts = []
    menuActions = []

    mainMenu = None
    menuBar = None

    dlgExtjob = None
    dlgReceive = None
    crrWidget = None

    conn = None

    rubberLayer = None  # type: QgsRubberBand
    rbList = []

    extjobArea = None  # type: QgsGeometry

    def __init__(self, iface):
        """Constructor.
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'NgiiMapJobManager_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.mainMenuTitle

        self.toolbar = self.iface.addToolBar(self.pluginName)
        self.toolbar.setObjectName(self.pluginName)

        self.initRubberLayer()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.
        We implement this ourselves since we do not inherit QObject.
        :param message: String for translation.
        :type message: str, QString
        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('NgiiMapJobManager', message)

    def initGui(self):
        # 메뉴 인스턴스 생성
        self.mainMenu = QMenu(self.iface.mainWindow())
        self.mainMenu.setTitle(self.mainMenuTitle)

        # 메뉴 등록하기 : Configuration
        menuBar = self.iface.mainWindow().menuBar()
        menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.mainMenu)

        # 메뉴 생성하기 : Configuration
        self.menuIcons = ['extjob.png', 'receive.png', 'inspect.png']
        self.menuTexts = [u'작업용 수치지도 제공', u'납품 데이터 수령', u'납품 데이터 검수']
        self.menuActions = [self.showDlgExtjob, self.showDlgReceive, self.showWidgetInspect]

        # ==== For DEBUG
        # self.menuIcons.append('bug.png')
        # self.menuTexts.append(u'디버깅 연결')
        # self.menuActions.append(self.attachPyDev)
        # ==== For DEBUG

        self.toolbar = self.iface.addToolBar(self.mainMenuTitle)

        assert (len(self.menuIcons) == len(self.menuTexts))
        assert (len(self.menuTexts) == len(self.menuActions))

        for i in range(0, len(self.menuTexts)):
            icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', self.menuIcons[i]))
            text = self.menuTexts[i]
            action = QAction(icon, text, self.iface.mainWindow())
            self.mainMenu.addAction(action)
            action.triggered.connect(self.menuActions[i])
            self.toolbar.addAction(icon, text, self.menuActions[i])

        self.connectDB()

    def unload(self):
        self.mainMenu.deleteLater()
        self.toolbar.deleteLater()
        if self.crrWidget:
            self.crrWidget.setVisible(False)
            del self.crrWidget
            self.crrWidget = None
        self.clearRb()

    # === for PyCharm Debugging
    def attachPyDev(self):
        import pydevd
        if not pydevd.connected:
            pydevd.settrace('localhost',
                            port=9999,
                            stdoutToServer=True,
                            stderrToServer=True)
    # === for PyCharm Debugging

    def showDlgExtjob(self):
        self.dlgExtjob = DlgExtjob(self)
        self.dlgExtjob.show()
        result = self.dlgExtjob.exec_()
        if result:
            pass

    def showDlgReceive(self):
        self.dlgReceive = DlgReceive(self)
        self.dlgReceive.show()
        result = self.dlgReceive.exec_()
        if result:
            pass

    def showWidgetInspect(self):
        if self.crrWidget:
            self.crrWidget.setVisible(False)
            del self.crrWidget
            self.crrWidget = None
        self.crrWidget = WidgetContainer(self.iface, WidgetInspect, Qt.RightDockWidgetArea, self)
        self.crrWidget.setVisible(True)
        # TODO: UI reflash
        self.crrWidget.repaint()
        pass

    def getConnetionInfo(self):
        try:
            conf = ConfigParser.SafeConfigParser()

            conf.read(os.path.join(os.path.dirname(__file__),"conf", "NgiiMapJobManager.conf"))

            self.ip_address = conf.get("Connection_Info", "pgIp")
            self.port = conf.get("Connection_Info", "pgPort")
            self.database = conf.get("Connection_Info", "pgDb")
            self.account = conf.get("Connection_Info", "pgAccount")
            self.password = conf.get("Connection_Info", "pgPw")

        except Exception as e:
            print e

    def connectDB(self):
        self.getConnetionInfo()
        try:
            self.conn = psycopg2.connect(database=self.database, user=self.account, password=self.password,
                                    host=self.ip_address, port=self.port)
        except psycopg2.Error as e:
            QMessageBox.critical(self, "Connect Error", str(e))

    def disconnectDB(self):
        if self.conn:
            self.conn.close()

    def drawGeometry(self):
        g = QgsGeometry()
        pass

    def initRubberLayer(self):
        if self.rubberLayer:
            rb = self.rubberLayer
            rb.reset(True)
        else:
            rb = QgsRubberBand(self.iface.mapCanvas(), True)
        rb.setColor(QColor(255, 0, 255, 255))
        rb.setWidth(3)
        rb.setFillColor(QColor(255, 0, 255, 50))
        self.rubberLayer = rb

    # 마커를 지도 화면에 표시
    def drawRbGeometry(self, geom, moveTo = False):
        # self.rubberLayer.addGeometry(geom, None)
        self.rubberLayer.setToGeometry(geom, None)
        if moveTo:
            bound = self.extjobArea.boundingBox()
            canvas = self.iface.mapCanvas()
            canvas.setExtent(bound)
            canvas.refresh()

    def clearRb(self):
        self.extjobArea = None
        self.initRubberLayer()


    def addExtjobArea(self, wkt, moveTo = False):
        geom = QgsGeometry.fromWkt(wkt)
        if not self.extjobArea:
            self.extjobArea = geom
        else:
            self.extjobArea = self.extjobArea.combine(geom)

        self.drawRbGeometry(self.extjobArea, moveTo)

    def generateDataFiles(self, folderPath):
        # DB에 정보 넣고
        try:
            cur = self.conn.cursor()
            sql = "SELECT nextid('EJ') as extjob_id, current_timestamp as mapext_dttm"
            cur.execute(sql)
            result = cur.fetchone()
            extjob_id = result[0]
            mapext_dttm = result[1]
            timestemp = "{}-{}-{} {}:{}:{}.{}"\
                        .format(mapext_dttm.year, mapext_dttm.month, mapext_dttm.day,
                                mapext_dttm.hour, mapext_dttm.minute, mapext_dttm.second, mapext_dttm.microsecond)

            sql = u"""INSERT INTO extjob.extjob_main
                        (extjob_id, extjob_nm, mapext_dttm, basedata_nm, basedata_dt, worker_nm,
                        workarea_geom, workarea_txt)
                        values
                        (%s, %s, %s, %s, %s, %s, ST_Multi(ST_GeomFromText(%s, 5179)),%s)"""
            extjob_nm = self.dlgExtjob.edt_extjob_nm.text()
            basedata_nm = self.dlgExtjob.edt_basedata_nm.text()
            basedata_dt = self.dlgExtjob.date_basedata_dt.date().toString('yyyy-M-d')
            worker_nm = self.dlgExtjob.cmb_worker_nm.currentText()
            workarea_geom = self.extjobArea.exportToWkt()
            items_list = []
            for i in range(self.dlgExtjob.lst_workarea.count()):
                items_list.append(self.dlgExtjob.lst_workarea.item(i).text())
            workarea_txt = ','.join(items_list)
            cur.execute(sql, (extjob_id, extjob_nm, timestemp, basedata_nm, basedata_dt, worker_nm, workarea_geom,workarea_txt))

            # 데이터 추출 시간
            sql = u"select tablename from pg_tables where schemaname = 'nfsd'"
            cur.execute(sql)
            results = cur.fetchall()

            extFile_list = []
            for result in results:
                temp_name = next(tempfile._get_candidate_names())
                temp_dir = tempfile.gettempdir()
                layer_nm = result[0]
                sql = "select column_name from information_schema.columns " \
                      "where table_schema = 'nfsd' and table_name = '{}' and ordinal_position = 3".format(layer_nm)
                cur.execute(sql)
                col = cur.fetchone()
                column_nm = col[0]

                #겹치는 데이터가 없을경우 건너 뜀
                sql = u"SELECT count(ogc_fid) FROM nfsd.{} " \
                      u"WHERE ST_Intersects(wkb_geometry, ST_GeomFromText('{}', 5179))" \
                      u"and {} is not NULL" \
                      .format(layer_nm, workarea_geom, column_nm)
                cur.execute(sql)
                count = cur.fetchone()

                if count[0] == 0:
                    continue

                # ogc_fid 를 저장
                sql = u"INSERT INTO extjob.extjob_objlist (extjob_id, layer_nm, ogc_fid) " \
                      u"(SELECT '{}', '{}', ogc_fid FROM nfsd.{} " \
                      u"WHERE ST_Intersects(wkb_geometry, ST_GeomFromText('{}', 5179))" \
                      u"and {} is not NULL)" \
                    .format(extjob_id, layer_nm, layer_nm, workarea_geom, column_nm)
                cur.execute(sql)

                self.conn.commit()

                sql = u"SELECT {}.*, '{}' as extjob_id, " \
                      u"'{}' as mapext_dttm, {} as basedata_nm, '{}' as basedata_dt,{} as worker_nm FROM nfsd.{}" \
                      u" WHERE ogc_fid in (SELECT ogc_fid from extjob.extjob_objlist WHERE extjob_id = '{}' " \
                      u"and layer_nm = '{}') " \
                    .format(layer_nm, extjob_id, timestemp, postgres_escape_string(basedata_nm), basedata_dt,
                            postgres_escape_string(worker_nm), layer_nm, extjob_id, layer_nm)

                # ogr2ogr을 이용해 DB를 Shape으로 내보내기
                shapeFileName = os.path.join(temp_dir, temp_name)
                # 윈도우가 아닌 경우 PATH 추가
                ogr2ogrPath = None
                if sys.platform == "win32":
                    ogr2ogrPath = ""
                else:
                    ogr2ogrPath = "/Library/Frameworks/GDAL.framework/Versions/1.11/Programs/"

                for f in glob(shapeFileName + '.*'):
                    os.remove(f)

                command = u'{}ogr2ogr ' \
                          u' --config SHAPE_ENCODING UTF-8 -f "ESRI Shapefile" {}.shp ' \
                          u'-t_srs EPSG:5179 PG:"host={} user={} dbname={} password={}" -sql "{}"'\
                    .format(ogr2ogrPath, shapeFileName, self.ip_address,
                            self.account, self.database, self.password, sql)
                rc = check_output(command.decode(), shell=True)

                with open(os.path.join(temp_dir, '{}.cpg'.format(temp_name)), "w") as confFile:
                    confFile.write('UTF-8')

                for temp_file in glob(os.path.join(temp_dir,u"{}.*".format(temp_name))):
                    file_ext = os.path.splitext(temp_file)[1]
                    ext_file = os.path.join(folderPath,layer_nm + file_ext)
                    os.rename(temp_file,ext_file)

                extFile_list.append(layer_nm)

            # 만들지 않았는데 있는 데이터 처리
            # notExtFile = []
            # for file in glob(os.path.join(folderPath,"*.shp")):
            #     file_nm = os.path.splitext(os.path.basename(file))[0]
            #
            #     if not file_nm in extFile_list:
            #         notExtFile.append(file_nm)
            #
            # if len(notExtFile) != 0:
            #     msg = '\n - '.join(notExtFile)
            #     rc = QMessageBox.question(self.dlgExtjob, u"확인", u"이전에 생성된 데이터가 있습니다.\n"
            #                                                      u" - {}\n"
            #                                            u"지우시겠습니까 ?".format(msg),
            #                               QMessageBox.Yes, QMessageBox.No)
            #     if rc == QMessageBox.Yes:
            #         for f in notExtFile:
            #             for rmFile in glob(os.path.join(folderPath , '{}.*'.format(f))):
            #                 os.remove(rmFile)

            for extFile in os.listdir(folderPath):
                if os.path.splitext(extFile)[1] == '.shp':
                    extFile_nm = os.path.splitext(extFile)[0]
                    if extFile_nm in extFile_list:
                        extFile_list.remove(extFile_nm)

            if len(extFile_list) == 0 :
                QMessageBox.information(self.dlgExtjob, u"작업 완료", u"작업용 수치지도 생성이 완료되었습니다.")
            else:
                layer_list = ','.join(extFile_list)
                QMessageBox.information(self.dlgExtjob, u"작업 오류", u"{}\n 위 데이터는 생성되지 않았습니다.")

        except Exception as e:
            self.conn.rollback()
            QMessageBox.warning(self.dlgExtjob, u"오류", str(e))

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
        base_lon = 130+i_lon if i_lon<=2 else 120+i_lon

        y_idx_50k = int((idx_50k-1) / 4)
        x_idx_50k = (idx_50k-1) % 4

        base_50k_lat = base_lat + 1 - 0.25 * y_idx_50k
        base_50k_lon = base_lon + 0.25 * x_idx_50k

        # 5만 도엽 기준위치 예외 처리
        # 제주
        if dycd_50k >= '33605' and dycd_50k <= '33608':
            base_50k_lat += -0.1
        # 서귀포
        elif dycd_50k >= '33609' and dycd_50k <= '33612':
            base_50k_lat += -0.1
            base_50k_lon += -5.0/60.0
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
            y_idx_25k = int((idx_25k-1) / 2)
            x_idx_25k = (idx_25k-1) % 2
            max_lat = base_50k_lat - y_idx_25k * 0.125
            min_lat = max_lat - 0.125
            min_lon = base_50k_lon + x_idx_25k * 0.125
            max_lon = min_lon + 0.125
        elif scale == 10000 or scale == 1000:
            idx_10k = int(dycd[5:7])
            if idx_10k > 25:  # 25 이상의 인덱스면 오류
                return None
            y_idx_10k = int((idx_10k-1) / 5)
            x_idx_10k = (idx_10k-1) % 5

            if scale == 10000:
                max_lat = base_50k_lat - y_idx_10k * 0.05
                min_lat = max_lat - 0.05
                min_lon = base_50k_lon + x_idx_10k * 0.05
                max_lon = min_lon + 0.05
            else:  # 1000 축척
                idx_1k = int(dycd[7:9])
                if idx_1k > 100:  # 100 이상 인덱스면 오류
                    return None
                y_idx_1k = int((idx_1k-1) / 10)
                x_idx_1k = (idx_1k-1) % 10
                max_lat = base_50k_lat - y_idx_10k * 0.05 - y_idx_1k * 0.005
                min_lat = max_lat - 0.005
                min_lon = base_50k_lon + x_idx_10k * 0.05 + x_idx_1k * 0.005
                max_lon = min_lon + 0.005
        elif scale == 5000:
            idx_5k = int(dycd[5:8])
            if idx_5k > 100:  # 100 이상의 인덱스면 오류
                return None
            y_idx_5k = int((idx_5k-1) / 10)
            x_idx_5k = (idx_5k-1) % 10
            max_lat = base_50k_lat - y_idx_5k * 0.025
            min_lat = max_lat - 0.025
            min_lon = base_50k_lon + x_idx_5k * 0.025
            max_lon = min_lon + 0.025

        # WKT 리턴
        str_res = "POLYGON (({min_x} {min_y}, {max_x} {min_y}, {max_x} {max_y}, {min_x} {max_y}, {min_x} {min_y}))"\
            .format(min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat)

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