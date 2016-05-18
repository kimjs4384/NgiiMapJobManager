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
        self.menuIcons.append('bug.png')
        self.menuTexts.append(u'디버깅 연결')
        self.menuActions.append(self.attachPyDev)
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
            for result in results:
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
                shapeFileName = os.path.join(folderPath, layer_nm)
                # 윈도우가 아닌 경우 PATH 추가
                ogr2ogrPath = None
                if sys.platform == "win32":
                    ogr2ogrPath = ""
                else:
                    ogr2ogrPath = "/Library/Frameworks/GDAL.framework/Versions/1.11/Programs/"

                # TODO: 생산 대상 파일이 이미 있는지 확인

                command = u'{}ogr2ogr ' \
                          u' --config SHAPE_ENCODING UTF-8 -f "ESRI Shapefile" {}.shp ' \
                          u'-t_srs EPSG:5179 PG:"host={} user={} dbname={} password={}" ' \
                          u'-sql "{}"'.format(ogr2ogrPath, shapeFileName, self.ip_address, self.account, self.database, self.password, sql)
                rc = check_output(command.decode(), shell=True)
                # TODO: 각 파일에 해당하는 *.cpg 파일이 생성되게 보완

            # 모든 작업이 정상적일 때만 커밋하게 수정됨
            self.conn.commit()
            # TODO: 모든 레이어가 문제 없을 때만 메시지 보이게 보완
            QMessageBox.information(self.dlgExtjob, u"작업 완료", u"작업용 수치지도 생성이 완료되었습니다.")

        except Exception as e:
            self.conn.rollback()
            QMessageBox.warning(self.dlgExtjob, u"오류", str(e))
