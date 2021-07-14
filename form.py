#!/usr/bin/python
#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.core import QgsCoordinateReferenceSystem,  QgsCoordinateTransform
from qgis.PyQt import uic
from qgis.PyQt import QtNetwork
from qgis.PyQt.QtCore import pyqtSlot,  Qt,  QUrl,  QFileInfo
from qgis.PyQt.QtGui import QIntValidator
from qgis.PyQt.QtWidgets import QDialog,  QMessageBox,  QTableWidgetItem,  QProgressBar,  QApplication,  QFileDialog

import math
import os
import tempfile
import threading
from osgeo import gdal
from pathlib import Path
from os.path import expanduser

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'form.ui'))

        
class SRTMtoDTEDDialog(QDialog, FORM_CLASS):
    """
    Class documentation goes here.
    """
    
    def __init__(self, iface,  parent=None):
        """
        Constructor

        @param parent reference to the parent widget
        @type QWidget
        """
        super(SRTMtoDTEDDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.success = False
        self.cancelled = False
        self.dir = tempfile.gettempdir()
                
        self.lne_east.valueChanged.connect(self.eastBoundChanged)
        self.lne_west.valueChanged.connect(self.westBoundChanged)
        self.lne_north.valueChanged.connect(self.northBoundChanged)
        self.lne_south.valueChanged.connect(self.southBoundChanged)
        
        self.overall_progressBar.setValue(0)
        self.row_count = 0
                
    @pyqtSlot()
    def on_button_box_rejected(self):
        """
        Slot documentation goes here.
        """
        self.close()

    @pyqtSlot()
    def on_btn_extent_clicked(self):
        """
        Slot documentation goes here.
        """
        crsDest = QgsCoordinateReferenceSystem(4326)  # WGS84
        crsSrc =self.iface.mapCanvas().mapSettings().destinationCrs()
        xform = QgsCoordinateTransform()
        xform.setSourceCrs(crsSrc)
        xform.setDestinationCrs(crsDest)
            
        extent = xform.transform(self.iface.mapCanvas().extent())        

        self.lne_west.setText(str(int(math.floor(extent.xMinimum()))))
        self.lne_east.setText(str(math.ceil(extent.xMaximum())))
        self.lne_south.setText(str(int(math.floor(extent.yMinimum()))))
        self.lne_north.setText(str(math.ceil(extent.yMaximum())))

    def southBoundChanged(self, value):
        if self.lne_north.value() <= value:
            self.lne_north.setValue(value + 1)
        
    def northBoundChanged(self, value):
        if self.lne_south.value() >= value:
            self.lne_south.setValue(value - 1)
    
    def eastBoundChanged(self, value):
        if self.lne_west.value() >= value:
            self.lne_west.setValue(value - 1)
        
    def westBoundChanged(self, value):
        if self.lne_east.value() <= value:
            self.lne_east.setValue(value + 1)

    # Delete This at some point
    def get_tiles(self):
            lat_diff = abs(int(self.lne_north.text()) - int(self.lne_south.text()))
            lon_diff = abs(int(self.lne_east.text()) - int(self.lne_west.text()))
            self.n_tiles = lat_diff * lon_diff
            self.image_counter = 0
            self.init_progress()
            self.is_error = None

            self.overall_progressBar.setMaximum(self.n_tiles)
            self.overall_progressBar.setValue(0)
            
            for lat in range(int(self.lne_south.text()), int(self.lne_north.text())):
                for lon in range(int(self.lne_west.text()), int(self.lne_east.text())):
                        if lon < 10 and lon >= 0:
                            lon_tx = "E00%s" % lon
                        elif lon >= 10 and lon < 100:
                            lon_tx = "E0%s" % lon
                        elif lon >= 100:
                            lon_tx = "E%s" % lon
                        elif lon > -10 and lon < 0:
                            lon_tx = "W00%s" % abs(lon)
                        elif lon <= -10 and lon > -100:
                            lon_tx = "W0%s" % abs(lon)
                        elif lon <= -100:
                            lon_tx = "W%s" % abs(lon)
    
                        if lat < 10 and lat >= 0:
                            lat_tx = "N0%s" % lat
                        elif lat >= 10 and lat < 100:
                            lat_tx = "N%s" % lat
                        elif lat > -10 and lat < 0:
                            lat_tx = "S0%s" % abs(lat)
                        elif lat <= -10 and lat > -100:
                            lat_tx = "S%s" % abs(lat)
                        
                        try:
                            self.set_progress()
                            self.download_finished(False)
                        except:
                            QMessageBox.warning(None,  self.tr("Error"),  self.tr("Wrong definition of coordinates"))
                            return False
            
            return True
            
            
    def download_finished(self,  show_message=True,  abort=False):
        if self.n_tiles == self.overall_progressBar.value() or abort:
            if show_message:
                if self.is_error != None:
                    QMessageBox.information(None, 'Error',  self.is_error)
                else:
                    QMessageBox.information(None,  self.tr("Result"),  self.tr("Download completed"))
                
            self.button_box.setEnabled(True)
            self.n_tiles = 0
            self.image_counter = 0
        
        QApplication.restoreOverrideCursor()
            
    def lockUI(self):
        self.button_box.setEnabled(False)
        self.btnConvert.setEnabled(False)
        self.btnInputDataset.setEnabled(False)
        self.btnOutputFolder.setEnabled(False)
        self.lneInputDataset.setEnabled(False)
        self.lneOutputFolder.setEnabled(False)
    
    # Writes validation errors to self.validationErrors[]
    def valid(self):
        self.validationErrors = []
        inputDataSet = self.lneInputDataset.text()
        outputFolder = self.lneOutputFolder.text()
    
        if not os.path.isdir(inputDataSet):
            self.validationErrors.append("'Input Dataset' is not an existing directory")
    
        if len(self.validationErrors) != 0:
            return False
        return True
         
    @pyqtSlot()
    def on_btnConvert_clicked(self):
        """
        Slot documentation goes here.
        """        
        if self.valid():
            self.lockUI()
            
            self.workerThread = threading.Thread(target=self.convert)
            self.workerThread.start()

    @pyqtSlot()
    def on_btnInputDataset_clicked(self):
        """
        Slot documentation goes here.
        """
        home = expanduser("~")
        self.dir = QFileDialog.getExistingDirectory(None, self.tr("Open Directory"),
                                                 home,
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)

        self.lneInputDataset.setText(self.dir)
        
    @pyqtSlot()
    def on_btnOutputFolder_clicked(self):
        """
        Slot documentation goes here.
        """
        home = expanduser("~")
        self.dir = QFileDialog.getExistingDirectory(None, self.tr("Open Directory"),
                                                 home,
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)

        self.lneOutputFolder.setText(self.dir)  
            
    def init_progress(self):
        self.overall_progressBar.setMaximum(self.n_tiles)
        self.overall_progressBar.setValue(0)
        self.lbl_file_download.setText((self.tr("Download-Progress: %s of %s images") % (0,  self.n_tiles)))
                
    def set_progress(self,  akt_val=None,  all_val=None):
        if all_val == None:
            progress_value = self.overall_progressBar.value() + 1
            self.overall_progressBar.setValue(progress_value)
            self.lbl_file_download.setText((self.tr("Download-Progress: %s of %s images") % (progress_value,  self.n_tiles)))
                    
            if progress_value == self.n_tiles:
                self.lbl_file_download.setText((self.tr("Download-Progress: %s of %s images") % (progress_value,  self.n_tiles)))
                self.download_finished(show_message=True)
        else:
            self.overall_progressBar.setMaximum(all_val)
            self.overall_progressBar.setValue(akt_val)
    
    # This will be called as a thread!
    def convert(self):
        inDir = self.lneInputDataset.text()
        outDir = 'G:/Data/02_Geographical/01_Maps/03_DTED/'
        level = 0
        n = 20
        e = 20
        s = 0
        w = 0

        TILE_NAME = 0
        TILE_EXISTS = 1
        TILE_LAT = 2
        TILE_LON = 3
        TILE_PATH = 4

        kwargs0 = {
            'format': 'DTED',
            'width': 121,
            'height': 121
        }

        kwargs1 = {
            'format': 'DTED',
            'width': 601,
            'height': 1201
        }

        kwargs2 = {
            'format': 'DTED',
            'width': 1801,
            'height': 3601
        }

        if level == 0:
            kwargs = kwargs0
        elif level == 1:
            kwargs = kwargs1
        else:
            kwargs = kwargs2

        def getLongitudeString(lon):
            if lon < 10 and lon >= 0:
                return "E00%s" % lon
            elif lon >= 10 and lon < 100:
                return "E0%s" % lon
            elif lon >= 100:
                return "E%s" % lon
            elif lon > -10 and lon < 0:
                return "W00%s" % abs(lon)
            elif lon <= -10 and lon > -100:
                return "W0%s" % abs(lon)
            elif lon <= -100:
                return "W%s" % abs(lon)

        def getLatitudeString(lat):
            if lat < 10 and lat >= 0:
                return "N0%s" % lat
            elif lat >= 10 and lat < 100:
                return "N%s" % lat
            elif lat > -10 and lat < 0:
                return "S0%s" % abs(lat)
            elif lat <= -10 and lat > -100:
                return "S%s" % abs(lat)

        def getCoordinateString(lat, lon):
            return getLatitudeString(lat) + getLongitudeString(lon)

        print('Preparing metadata')
        tiles = []
        for lat in range(s, n):
            for lon in range(w, e):
                tile = {}
                tile[TILE_NAME] = getCoordinateString(lat, lon)
                tile[TILE_PATH] = inDir + tile[TILE_NAME] + '.hgt'
                tile[TILE_EXISTS] = os.path.isfile(tile[TILE_PATH])
                tile[TILE_LAT] = lat
                tile[TILE_LON] = lon
                if tile[TILE_EXISTS]:
                    tiles.append(tile)

        print('Converting tiles')
        count = 0
        for tile in tiles:
            if tile[TILE_EXISTS]:
                destinationPath = outDir + 'DTED' + str(level) + '/DTED/' + getLongitudeString(tile[TILE_LON]) + '/'
                destination = destinationPath + getLatitudeString(tile[TILE_LAT]) + '.dt' + str(level)
                Path(destinationPath).mkdir(parents=True, exist_ok=True)
                if not os.path.isfile(destination):
                    gdal.Translate(destination, tile[TILE_PATH], **kwargs) != None
                count += 1
                if count % 10 == 0:
                    print(str(count))

        print('Cleanup')
        for root, dirs, files in os.walk(outDir):
            for currentFile in files:
                exts = ('.xml')
                if currentFile.lower().endswith(exts):
                    os.remove(os.path.join(root, currentFile))

        print('Done')
