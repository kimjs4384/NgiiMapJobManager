# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NgiiMapJobManager
                                 A QGIS plugin
 Plugin for Manage NGII map jobs
                             -------------------
        begin                : 2016-04-21
        copyright            : (C) 2016 by Gaia3D
        email                : jangbi882@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load NgiiMapJobManager class from file NgiiMapJobManager.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .ngii_mj_manager import NgiiMapJobManager
    return NgiiMapJobManager(iface)
