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
from qgis.core import *
from qgis.PyQt import uic
from qgis.PyQt import QtNetwork
from qgis.PyQt.QtCore import pyqtSlot,  Qt,  QUrl,  QFileInfo, QSettings, QRunnable, QThreadPool
from qgis.PyQt.QtGui import QIntValidator
from qgis.PyQt.QtWidgets import QDialog,  QMessageBox,  QTableWidgetItem,  QProgressBar,  QApplication,  QFileDialog

import math
import os
import tempfile
import threading
from osgeo import gdal
from pathlib import Path
from os.path import expanduser

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'form.ui'), resource_suffix='')
    
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
        
        self.settings = QSettings()
        if self.settings.value("InputFolder"):
            self.lneInputDataset.setText(self.settings.value("InputFolder"))
        if self.settings.value("OutputFolder"):
            self.lneOutputFolder.setText(self.settings.value("OutputFolder"))        
        #if self.settings.value("Level0"):
        #    self.cbxLevel0.setCheckState(self.settings.value("Level0"))   
        #if self.settings.value("Level1"):
        #    self.cbxLevel1.setCheckState(self.settings.value("Level1"))   
        #if self.settings.value("Level2"):
        #    self.cbxLevel2.setCheckState(self.settings.value("Level2"))   
        
        self.success = False
        self.cancelled = False
        self.dir = tempfile.gettempdir()
                
        self.lne_east.valueChanged.connect(self.eastBoundChanged)
        self.lne_west.valueChanged.connect(self.westBoundChanged)
        self.lne_north.valueChanged.connect(self.northBoundChanged)
        self.lne_south.valueChanged.connect(self.southBoundChanged)
                
        self.lneInputDataset.textChanged.connect(self.inputFolderChanged)
        self.lneOutputFolder.textChanged.connect(self.outputFolderChanged)
        
        self.cbxLevel0.stateChanged.connect(self.levelsChanged)
        self.cbxLevel1.stateChanged.connect(self.levelsChanged)
        self.cbxLevel2.stateChanged.connect(self.levelsChanged)
        
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
            
    def lockUI(self):
        self.button_box.setEnabled(False)
        self.btnConvert.setEnabled(False)
        self.btnInputDataset.setEnabled(False)
        self.btnOutputFolder.setEnabled(False)
        self.lneInputDataset.setEnabled(False)
        self.lneOutputFolder.setEnabled(False)
        self.lne_west.setEnabled(False)
        self.lne_east.setEnabled(False)
        self.lne_south.setEnabled(False)
        self.lne_north.setEnabled(False)
        self.btn_extent.setEnabled(False)
        self.cbxLevel0.setEnabled(False)
        self.cbxLevel1.setEnabled(False)
        self.cbxLevel2.setEnabled(False)
        
    def unlockUI(self):
        self.button_box.setEnabled(True)
        self.btnConvert.setEnabled(True)
        self.btnInputDataset.setEnabled(True)
        self.btnOutputFolder.setEnabled(True)
        self.lneInputDataset.setEnabled(True)
        self.lneOutputFolder.setEnabled(True)
        self.lne_west.setEnabled(True)
        self.lne_east.setEnabled(True)
        self.lne_south.setEnabled(True)
        self.lne_north.setEnabled(True)
        self.btn_extent.setEnabled(True)
        self.cbxLevel0.setEnabled(True)
        self.cbxLevel1.setEnabled(True)
        self.cbxLevel2.setEnabled(True)
        
    def valid(self):
        validationErrors = []
        inputDataSet = self.lneInputDataset.text()
        outputFolder = self.lneOutputFolder.text()
    
        if not os.path.isdir(inputDataSet):
            validationErrors.append("'Input Dataset' is not an existing directory")
        
        if not os.path.isdir(outputFolder):
            validationErrors.append("'Output Folder' is not an existing directory")
    
        if not self.cbxLevel0.isChecked() and not self.cbxLevel1.isChecked() and not self.cbxLevel2.isChecked():
            validationErrors.append("At least one export level must be selected")
    
        if len(validationErrors) != 0:
            QMessageBox.warning(self, "Invalid Input", 'The following issues were found:\n\n- ' + '\n- '.join(validationErrors)) 
            return False
        return True
        
    def validForDMED(self):
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
    def on_btnGenerateDMED_clicked(self):
        if self.validForDMED():
            self.lockUI()
            
            pool = QThreadPool.globalInstance()
            runnable = GenerateDMEDTask(self.lneOutputFolder.text(), self)
            pool.start(runnable)

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
    
    def inputFolderChanged(self, path):
        self.settings.setValue("InputFolder", path)
        
    def outputFolderChanged(self, path):
        self.settings.setValue("OutputFolder", path)
    
    def levelsChanged(self, value):
        self.settings.setValue("Level0", self.cbxLevel0.checkState())
        self.settings.setValue("Level1", self.cbxLevel1.checkState())
        self.settings.setValue("Level2", self.cbxLevel2.checkState())
    
    def convertClosed(self):
        self.unlockUI()

    def getKwargs(self, level, lat, lon):
        kwargs = {
            'format': 'DTED'
        }
        if lat >= 50 or lat <= -50:
            if level == 0:
                kwargs['width'] = 61
                kwargs['height'] = 121
            elif level == 1:
                kwargs['width'] = 601
                kwargs['height'] = 1201
            elif level == 2:
                kwargs['width'] = 1801
                kwargs['height'] = 3601
        else:
            if level == 0:
                kwargs['width'] = 121
                kwargs['height'] = 121
            elif level == 1:
                kwargs['width'] = 1201
                kwargs['height'] = 1201
            elif level == 2:
                kwargs['width'] = 3601
                kwargs['height'] = 3601
        return kwargs

    # This will be called as a thread!
    def convert(self):
        inDir = self.lneInputDataset.text()
        outDir = self.lneOutputFolder.text()
        
        TILE_NAME = 0
        TILE_EXISTS = 1
        TILE_LAT = 2
        TILE_LON = 3
        TILE_PATH = 4       

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

        # print('Preparing metadata')
        tiles = []
        for lat in range(self.lne_south.value(), self.lne_north.value()):
            for lon in range(self.lne_west.value(), self.lne_east.value()):
                tile = {}
                tile[TILE_NAME] = getCoordinateString(lat, lon)
                tile[TILE_PATH] = inDir + '/' + tile[TILE_NAME] + '.hgt'
                tile[TILE_EXISTS] = os.path.isfile(tile[TILE_PATH])
                tile[TILE_LAT] = lat
                tile[TILE_LON] = lon
                if tile[TILE_EXISTS]:
                    tiles.append(tile)
        
        levels = []
        if self.cbxLevel0.isChecked():
            levels.append(0)
        if self.cbxLevel1.isChecked():
            levels.append(1)
        if self.cbxLevel2.isChecked():
            levels.append(2)
        
        # print('Converting tiles')
        
        ## README: http://osgeo-org.1560.x6.nabble.com/Converting-USGSDEM-into-GTOP30-DEM-or-DTED-td3754489.html
        
        
        self.overall_progressBar.setMaximum(len(tiles) * len(levels))
        self.overall_progressBar.setValue(0)
        for level in levels:
            for tile in tiles:
                if tile[TILE_EXISTS]:
                    destinationPath = outDir + '/DTED/' + getLongitudeString(tile[TILE_LON]) + '/'
                    destination = destinationPath + getLatitudeString(tile[TILE_LAT]) + '.dt' + str(level)
                    Path(destinationPath).mkdir(parents=True, exist_ok=True)
                    if not os.path.isfile(destination):
                        gdal.Translate(destination, tile[TILE_PATH], **self.getKwargs(level, tile[TILE_LAT], tile[TILE_LON])) != None
                self.overall_progressBar.setValue(self.overall_progressBar.value() + 1)

        # print('Cleanup')
        for root, dirs, files in os.walk(outDir):
            for currentFile in files:
                exts = ('.xml')
                if currentFile.lower().endswith(exts):
                    os.remove(os.path.join(root, currentFile))
        
        self.unlockUI()


class DMEDHelper:
    def __init__(self, northBound, southBound, eastBound, westBound):
        self.northBound = northBound
        self.southBound = southBound
        self.eastBound = eastBound
        self.westBound = westBound
        self.width = eastBound - westBound
        self.height = northBound - southBound
        self.size = self.width * self.height
        self.buffer = [' '] * (394 * self.size + 394)
        self.insert(0, self.getMBR())
    
    def insert(self, startIndex, value):
        valueString = str(value)
        count = 0
        for char in valueString:
            self.buffer[startIndex + count] = char
            count += 1
    
    def getMBR(self):
        return self.getLatitudeString(self.southBound) + self.getLatitudeString(self.northBound) + self.getLongitudeString(self.westBound) + self.getLongitudeString(self.eastBound)

    def getLongitudeString(self, lon):
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

    def getLatitudeString(self, lat):
        if lat < 10 and lat >= 0:
            return "N0%s" % lat
        elif lat >= 10 and lat < 100:
            return "N%s" % lat
        elif lat > -10 and lat < 0:
            return "S0%s" % abs(lat)
        elif lat <= -10 and lat > -100:
            return "S%s" % abs(lat)

    def getCoordinateString(self, lat, lon):
        return self.getLatitudeString(lat) + self.getLongitudeString(lon)
    
    # REturns the prefered tile resolution based on availability
    def getTile(self, lat, lon, directory):
        fileName = directory + 'DTED/' + self.getLongitudeString(lon) + '/' + self.getLatitudeString(lat)
        
        if(os.path.isfile(fileName + '.dt1')):
            return (fileName + '.dt1', gdal.Open(fileName + '.dt1'))
        elif(os.path.isfile(fileName + '.dt0')):
            return (fileName + '.dt0', gdal.Open(fileName + '.dt0'))
        elif(os.path.isfile(fileName + '.dt2')):
            return (fileName + '.dt2', gdal.Open(fileName + '.dt2'))
            
        return (None, None)

    def toString(self):
        return ''.join(self.buffer)
    
    def processTile(self, lat, lon, directory):
        byteOffset = ((((lon - self.westBound) * self.height) + (lat - self.southBound)) * 394) + 394
        latLonString = self.getCoordinateString(lat, lon)
        self.insert(byteOffset, latLonString)
        
        # Early out if no more info will be available
        tilePath, tile = self.getTile(lat, lon, directory)
        if tile == None:
            return
    
        tileWidth = tile.RasterXSize
        tileHeight = tile.RasterYSize
        subTileWidth = int(tileWidth / 4)
        subTileHeight = int(tileHeight / 4)
        
        kwargsSubTile = {
            'format': 'GTIFF',
            'srcWin': [0, 0, subTileWidth, subTileHeight]
        }
        
        print(tilePath)
    
        # Versioning Numbers, I dont calculate them at the moment
        self.insert(byteOffset + 7, '01A')
        
        # Stats per quadrant (4 x 4 per tile)
        statsOffset = byteOffset + 10
        for x in range(0, 4):
            for y in range(0, 4):
                
                kwargsSubTile['srcWin'] = [x * subTileWidth, (3 - y) * subTileHeight, subTileWidth, subTileHeight]
                subTile = gdal.Translate('G:/temp.dtx', tilePath, **kwargsSubTile)
                                
                subTileNo = (x * 4 + y)
                subTileOffset = statsOffset + subTileNo * 24
            
                rasterBand = subTile.GetRasterBand(1)
                stats = rasterBand.GetStatistics(True, True)
                
                min = int(stats[0])
                max = int(stats[1])
                mean = int(stats[2])
                stdDev = int(stats[3])
                
                self.insert(subTileOffset, str(min).rjust(6, ' '))
                self.insert(subTileOffset + 6, str(max).rjust(6, ' '))
                self.insert(subTileOffset + 12, str(mean).rjust(6, ' '))
                self.insert(subTileOffset + 19, str(stdDev).rjust(5, ' '))

    def saveAs(self, outFilePath):
        outString = self.toString()
        outStringAscii = outString.encode('ascii')
        with open(outFilePath, 'wb') as f:
            f.write(outStringAscii)

class GenerateDMEDTask(QRunnable):
    
    def __init__(self, targetDir, parentForm):
        super().__init__()
        self.targetDir = targetDir
        self.parentForm = parentForm
    
    def run(self):
        try:
            northBound = -1000
            southBound = 1000
            eastBound = -1000
            westBound = 1000

            #QgsMessageLog.logMessage(self.targetDir, 'DMED Tools', level=Qgis.Info)

            for root, dirs, files in os.walk(self.targetDir):
            
                for currentFile in files:
                                
                    exts = ('.dt0', '.dt1', '.dt2')
                    if currentFile.lower().endswith(exts):
                        northingStr = currentFile[0:3]
                        eastingStr = root[-4:]
                        
                        northing = int(northingStr[1:])
                        if(northingStr[0].lower() == 's'):
                            northing = 0 - northing
                        
                        easting = int(eastingStr[1:])
                        if(eastingStr[0].lower() == 'w'):
                            easting = 0 - easting
                        
                        # The +1 is because its bounds, and the position of a tile is based on the SW corner
                        if(northing + 1 > northBound):
                            northBound = northing + 1
                        if(northing < southBound):
                            southBound = northing
                        if(easting + 1 > eastBound):
                            eastBound = easting + 1
                        if(easting < westBound):
                            westBound = easting

            dmed = DMEDHelper(northBound, southBound, eastBound, westBound)
            self.parentForm.overall_progressBar.setMaximum((northBound - southBound) * (eastBound - westBound))
            self.parentForm.overall_progressBar.setValue(0)
        
            for lon in range(dmed.westBound, dmed.eastBound):
                for lat in range(dmed.southBound, dmed.northBound):
                    dmed.processTile(lat, lon, self.targetDir)
                    dmed.saveAs(self.targetDir + '/DMED')
                    self.parentForm.overall_progressBar.setValue(self.parentForm.overall_progressBar.value() + 1)
        except Exception as exception:
            raise exception
        finally:            
            self.parentForm.unlockUI()


