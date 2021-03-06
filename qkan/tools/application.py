# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Flaechenzuordnungen
                                 A QGIS plugin
 Diverse Tools zur QKan-Datenbank
                              -------------------
        begin                : 2017-06-12
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Jörg Höttges/FH Aachen
        email                : hoettges@fh-aachen.de
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

import json
import logging
import os.path
import site

from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QFileDialog, QListWidgetItem, QTableWidgetItem
from qgis.core import QgsDataSourceURI, QgsVectorLayer, QgsMapLayerRegistry, QgsMessageLog
from qgis.gui import QgsMessageBar
from qgis.utils import iface, pluginDirectory
from qgis.gui import QgsGenericProjectionSelector

# Initialize Qt resources from file resources.py
# noinspection PyUnresolvedReferences 
import resources
# Import the code for the dialog
from application_dialog import QgsadaptDialog, QKanOptionsDialog, RunoffParamsDialog
from k_tools import qgsadapt
from k_runoffparams import setRunoffparams
from qkan import Dummy
from qkan.database.dbfunc import DBConnection
from qkan.database.qkan_utils import get_database_QKan, get_editable_layers, fehlermeldung, sqlconditions

# Anbindung an Logging-System (Initialisierung in __init__)
logger = logging.getLogger(u'QKan')


class QKanTools:
    """QGIS Plugin Implementation."""

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
            'Flaechenzuordnungen_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlgpr = QgsadaptDialog()
        self.dlgop = QKanOptionsDialog()
        self.dlgro = RunoffParamsDialog()

        # Anfang Eigene Funktionen -------------------------------------------------
        # (jh, 12.06.2017)

        logger.info(u'\n\nQKan_Tools initialisiert...')

        # --------------------------------------------------------------------------
        # Pfad zum Arbeitsverzeichnis sicherstellen
        wordir = os.path.join(site.getuserbase(), 'qkan')

        if not os.path.isdir(wordir):
            os.makedirs(wordir)

        # --------------------------------------------------------------------------------------------------
        # Konfigurationsdatei qkan.json lesen
        #

        self.configfil = os.path.join(wordir, 'qkan.json')
        if os.path.exists(self.configfil):
            with open(self.configfil, 'r') as fileconfig:
                self.config = json.loads(fileconfig.read())
        else:
            self.config = {'epsg': '25832'}  # Projektionssystem
            with open(self.configfil, 'w') as fileconfig:
                fileconfig.write(json.dumps(self.config))

        # Formularereignisse anbinden ----------------------------------------------

        # Formular dlgpr
        self.dlgpr.pb_selectProjectFile.clicked.connect(self.dlgpr_selectFileProjectfile)
        self.dlgpr.pb_selectQKanDB.clicked.connect(self.dlgpr_selectFile_qkanDB)
        self.dlgpr.pb_selectProjectTemplate.clicked.connect(self.dlgpr_selectFileProjectTemplate)

        # Formular dlgop
        self.dlgop.pb_fangradiusDefault.clicked.connect(self.dlgop_fangradiusDefault)
        self.dlgop.pb_mindestflaecheDefault.clicked.connect(self.dlgop_mindestflaecheDefault)
        self.dlgop.pb_max_loopsDefault.clicked.connect(self.dlgop_maxLoopsDefault)
        self.dlgop.pb_selectKBS.clicked.connect(self.dlgop_selectKBS)

        # Formular dlgro
        self.dlgro.lw_teilgebiete.itemClicked.connect(self.dlgro_lwTeilgebieteClick)
        self.dlgro.lw_abflussparameter.itemClicked.connect(self.dlgro_lwAbflussparamsClick)
        self.dlgro.cb_selTgbActive.stateChanged.connect(self.dlgro_selTgbActiveClick)
        self.dlgro.cb_selParActive.stateChanged.connect(self.dlgro_selParActiveClick)
        self.dlgro.button_box.helpRequested.connect(self.dlgro_helpClick)
        self.dlgro.pb_selectQKanDB.clicked.connect(self.dlgro_selectFile_qkanDB)
        self.dlgro.rb_itwh.toggled.connect(self.dlgro_activateitwh)
        # self.dlgop.rb_itwh.toggled.connect(self.dlgro_activatedyna)


        # Ende Eigene Funktionen ---------------------------------------------------

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
        return QCoreApplication.translate('Flaechenzuordnungen', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_qgsadapt_path = ':/plugins/qkan/tools/res/icon_qgsadapt.png'
        Dummy.instance.add_action(
            icon_qgsadapt_path, 
            text=self.tr(u'Projektdatei auf bestehende QKan-Datenbank übertragen'), 
            callback=self.run_qgsadapt, 
            parent=self.iface.mainWindow())

        icon_qkanoptions_path = ':/plugins/qkan/tools/res/icon_qkanoptions.png'
        Dummy.instance.add_action(
            icon_qkanoptions_path, 
            text=self.tr(u'Allgemeine Optionen'), 
            callback=self.run_qkanoptions, 
            parent=self.iface.mainWindow())

        icon_runoffparams_path = ':/plugins/qkan/tools/res/icon_runoffparams.png'
        Dummy.instance.add_action(
            icon_runoffparams_path, 
            text=self.tr(u'Oberflächenabflussparameter eintragen'), 
            callback=self.run_runoffparams, 
            parent=self.iface.mainWindow())

    def unload(self):
        pass

    # -----------------------------------------------------------------------------------------------------
    # Erstellen einer Projektdatei aus einer Vorlage

    # 1. Formularfunktionen

    def dlgpr_selectFileProjectfile(self):
        """Zu erstellende Projektdatei festlegen"""

        filename = QFileDialog.getSaveFileName(self.dlgpr,
                                               "Dateinamen der zu erstellenden Projektdatei eingeben",
                                               self.default_dir,
                                               "*.qgs")
        # logger.info('Dateiname wurde erkannt zu:\n{}'.format(filename))
        
        if os.path.dirname(filename) != '':
            os.chdir(os.path.dirname(filename))
            self.dlgpr.tf_projectFile.setText(filename)


    def dlgpr_selectFile_qkanDB(self):
        """Anzubindende QKan-Datenbank festlegen"""

        filename = QFileDialog.getOpenFileName(self.dlgpr,
                                               "QKan-Datenbank auswählen",
                                               self.default_dir,
                                               "*.sqlite")
        if os.path.dirname(filename) != '':
            os.chdir(os.path.dirname(filename))
            self.dlgpr.tf_qkanDB.setText(filename)


    def dlgpr_selectFileProjectTemplate(self):
        """Vorlage-Projektdatei auswählen"""

        self.setPathToTemplateDir = self.dlgpr.cb_setPathToTemplateDir.isChecked()
        if self.setPathToTemplateDir:
            self.templateDir = os.path.join(pluginDirectory('qkan'), u"database/templates")
        else:
            try:
                self.templateDir = os.path.dirname(self.database_QKan)
            except:
                logger.error('Programmfehler in tools.run_qgsadapt:\nPfad konnte nicht auf ' + \
                             'database_QKan gesetzt werden.\n database_QKan = {}'.format(
                               self.database_QKan))
                self.templateDir = ''

        filename = QFileDialog.getOpenFileName(self.dlgpr,
                                               "Vorlage für zu erstellende Projektdatei auswählen",
                                               self.templateDir,
                                               "*.qgs")
        if os.path.dirname(filename) != '':
            os.chdir(os.path.dirname(filename))
            self.dlgpr.tf_projectTemplate.setText(filename)

    # -----------------------------------------------------------------------------------------------------
    # 2. Aufruf des Formulars

    def run_qgsadapt(self):
        '''Erstellen einer Projektdatei aus einer Vorlage'''

        # Formularfelder setzen -------------------------------------------------------------------------

        # Formularfeld Datenbank

        # Falls eine Datenbank angebunden ist, wird diese zunächst in das Formular eingetragen.
        self.database_QKan, epsg = get_database_QKan(silent = True)

        if self.database_QKan:
            self.default_dir = os.path.dirname(self.database_QKan)       # bereits geladene QKan-Datenbank übernehmen
        elif 'database_QKan' in self.config:
            self.database_QKan = self.config['database_QKan']
            self.dlgpr.tf_qkanDB.setText(self.database_QKan)
            self.default_dir = os.path.dirname(self.database_QKan)
        else:
            self.database_QKan = ''
            self.default_dir = '.'
        self.dlgpr.tf_qkanDB.setText(self.database_QKan)

        # Formularfeld Vorlagedatei
        if 'projectTemplate' in self.config:
            projectTemplate = self.config['projectTemplate']
        else:
            projectTemplate = ''

        # Formularfeld Projektdatei
        if 'projectfile' in self.config:
            projectfile = self.config['projectfile']
        else:
            projectfile = ''

        # Option: Suchpfad für Vorlagedatei auf template-Verzeichnis setzen 
        if 'setPathToTemplateDir' in self.config:
            self.setPathToTemplateDir = self.config['setPathToTemplateDir']
        else:
            self.setPathToTemplateDir = True
        self.dlgpr.cb_setPathToTemplateDir.setChecked(self.setPathToTemplateDir)

        # Option: QKan-Datenbank aktualisieren
        if 'qkanDBUpdate' in self.config:
            qkanDBUpdate = self.config['qkanDBUpdate']
        else:
            qkanDBUpdate = True
        self.dlgpr.cb_qkanDBUpdate.setChecked(qkanDBUpdate)

        # show the dialog
        self.dlgpr.show()
        # Run the dialog event loop
        result = self.dlgpr.exec_()

        # See if OK was pressed
        if result:

            # Inhalte aus Formular lesen --------------------------------------------------------------

            projectTemplate = self.dlgpr.tf_projectTemplate.text()
            self.database_QKan = self.dlgpr.tf_qkanDB.text()
            projectfile = self.dlgpr.tf_projectFile.text()
            self.setPathToTemplateDir = self.dlgpr.cb_setPathToTemplateDir.isChecked()
            qkanDBUpdate = self.dlgpr.cb_qkanDBUpdate.isChecked()


            # Konfigurationsdaten schreiben -----------------------------------------------------------

            self.config['projectTemplate'] = projectTemplate
            self.config['database_QKan'] = self.database_QKan
            self.config['projectfile'] = projectfile
            self.config['setPathToTemplateDir'] = self.setPathToTemplateDir
            self.config['qkanDBUpdate'] = qkanDBUpdate

            with open(self.configfil, 'w') as fileconfig:
                fileconfig.write(json.dumps(self.config))

            qgsadapt(projectTemplate, self.database_QKan, epsg, projectfile, self.setPathToTemplateDir, 
                     u'SpatiaLite')

    # ----------------------------------------------------------------------------------------------------
    # Allgemeine QKan-Optionen bearbeiten

    # 1. Formularfunktionen

    def dlgop_selectKBS(self):
        """KBS auswählen. Setzt das KBS für die weiteren Funktionen

        :returns: void
        """
        projSelector = QgsGenericProjectionSelector()
        projSelector.exec_()
        erg = projSelector.selectedAuthId()
        if len(erg.split(u':')) == 2:
            self.dlgop.tf_epsg.setText(erg.split(u':')[1])
        else:
            self.dlgop.tf_epsg.setText(erg)

    def dlgop_fangradiusDefault(self):
        self.dlgop.tf_fangradius.setText('0.1')

    def dlgop_mindestflaecheDefault(self):
        self.dlgop.tf_mindestflaeche.setText('0.5')

    def dlgop_maxLoopsDefault(self):
        self.dlgop.tf_max_loops.setText('1000')

    # -----------------------------------------------------------------------------------------
    # 2. Aufruf des Formulars

    def run_qkanoptions(self):
        '''Bearbeitung allgemeiner QKan-Optionen'''

        # Formularfelder setzen -------------------------------------------------------------------------

        # Fangradius für Anfang der Anbindungslinie
        if 'fangradius' in self.config:
            fangradius = self.config['fangradius']
        else:
            fangradius = u'0.1'
        self.dlgop.tf_fangradius.setText(str(fangradius))

        # Mindestflächengröße
        if 'mindestflaeche' in self.config:
            mindestflaeche = self.config['mindestflaeche']
        else:
            mindestflaeche = u'0.5'
        self.dlgop.tf_mindestflaeche.setText(str(mindestflaeche))

        # Maximalzahl Schleifendurchläufe
        if 'max_loops' in self.config:
            max_loops = self.config['max_loops']
        else:
            max_loops = '1000'
        self.dlgop.tf_max_loops.setText(str(max_loops))

        # Optionen zum Typ der QKan-Datenbank
        if 'datenbanktyp' in self.config:
            datenbanktyp = self.config['datenbanktyp']
        else:
            datenbanktyp = u'spatialite'

        if datenbanktyp == u'spatialite':
            self.dlgop.rb_spatialite.setChecked(True)
        # elif datenbanktyp == u'postgis':
            # self.dlgop.rb_postgis.setChecked(True)

        if 'epsg' in self.config:
            self.epsg = self.config['epsg']
        else:
            self.epsg = u'25832'
        self.dlgop.tf_epsg.setText(self.epsg)


        # show the dialog
        self.dlgop.show()
        # Run the dialog event loop
        result = self.dlgop.exec_()

        # See if OK was pressed
        if result:

            # Inhalte aus Formular lesen --------------------------------------------------------------

            fangradius = self.dlgop.tf_fangradius.text()
            mindestflaeche = self.dlgop.tf_mindestflaeche.text()
            max_loops = self.dlgop.tf_max_loops.text()
            if self.dlgop.rb_spatialite.isChecked():
                datenbanktyp = u'spatialite'
            # elif self.dlgop.rb_postgis.isChecked():
                # datenbanktyp = u'postgis'
            else:
                fehlermeldung(u"tools.application.run", 
                              u"Fehlerhafte Option: \ndatenbanktyp = {}".format(repr(datenbanktyp)))
            epsg = self.dlgop.tf_epsg.text()

            self.config['fangradius'] = fangradius
            self.config['mindestflaeche'] = mindestflaeche
            self.config['max_loops'] = max_loops
            self.config['datenbanktyp'] = datenbanktyp
            self.config['epsg'] = epsg

            with open(self.configfil, 'w') as fileconfig:
                # logger.debug(u"Config-Dictionary: {}".format(self.config))
                fileconfig.write(json.dumps(self.config))


    # ----------------------------------------------------------------------------------------------------
    # Oberflächenabflussparameter in QKan-Tabellen eintragen, ggfs. nur für ausgewählte Teilgebiete

    # 1. Formularfunktionen

    def dlgro_selectFile_qkanDB(self):
        """Datenbankverbindung zur QKan-Datenbank (SpatiLite) auswaehlen."""

        filename = QFileDialog.getOpenFileName(self.dlgro, u"QKan-Datenbank auswählen",
                                               self.default_dir, "*.sqlite")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlgro.tf_QKanDB.setText(filename)

    def dlgro_helpClick(self):
        """Reaktion auf Klick auf Help-Schaltfläche"""
        helpfile = os.path.join(self.plugin_dir, '../doc/sphinx/build/html/Qkan_Formulare.html#berechnung-von-oberflachenabflussparametern')
        webbrowser.open_new_tab(helpfile)

    def dlgro_lwTeilgebieteClick(self):
        """Reaktion auf Klick in Tabelle"""

        self.dlgro.cb_selTgbActive.setChecked(True)
        self.dlgro_countselection()

    def dlgro_lwAbflussparamsClick(self):
        """Reaktion auf Klick in Tabelle"""

        self.dlgro.cb_selParActive.setChecked(True)
        self.dlgro_countselection()

    def dlgro_selTgbActiveClick(self):
        """Reagiert auf Checkbox zur Aktivierung der Auswahl"""

        # Checkbox hat den Status nach dem Klick
        if self.dlgro.cb_selTgbActive.isChecked():
            # Nix tun ...
            logger.debug('\nChecked = True')
        else:
            # Auswahl deaktivieren und Liste zurücksetzen
            anz = self.dlgro.lw_teilgebiete.count()
            for i in range(anz):
                item = self.dlgro.lw_teilgebiete.item(i)
                self.dlgro.lw_teilgebiete.setItemSelected(item, False)

            # Anzahl in der Anzeige aktualisieren
            self.dlgro_countselection()

    def dlgro_selParActiveClick(self):
        """Reagiert auf Checkbox zur Aktivierung der Auswahl"""

        # Checkbox hat den Status nach dem Klick
        if self.dlgro.cb_selParActive.isChecked():
            # Nix tun ...
            logger.debug('\nChecked = True')
        else:
            # Auswahl deaktivieren und Liste zurücksetzen
            anz = self.dlgro.lw_abflussparameter.count()
            for i in range(anz):
                item = self.dlgro.lw_abflussparameter.item(i)
                self.dlgro.lw_abflussparameter.setItemSelected(item, False)

            # Anzahl in der Anzeige aktualisieren
            self.dlgro_countselection()

    def dlgro_activateitwh(self):
        """Reagiert auf Auswahl itwh und deaktiviert entsprechend die Option Fließzeiten"""

        if self.dlgro.rb_itwh.isChecked():
            if self.dlgro.rb_fliesszeiten.isChecked():
                self.dlgro.rb_kaskade.setChecked(True)
            self.dlgro.rb_fliesszeiten.setEnabled(False)
        else:
            self.dlgro.rb_fliesszeiten.setEnabled(True)
            

    def dlgro_countselection(self):
        """Zählt nach Änderung der Auswahlen in den Listen im Formular die Anzahl
        der betroffenen Flächen und Haltungen"""
        liste_teilgebiete = self.dlgro_listselecteditems(self.dlgro.lw_teilgebiete)
        liste_abflussparameter = self.dlgro_listselecteditems(self.dlgro.lw_abflussparameter)

        # Auswahl der zu bearbeitenden Flächen
        auswahl = sqlconditions('WHERE', ('teilgebiet', 'abflussparameter'), (liste_teilgebiete, liste_abflussparameter))

        sql = u"""SELECT count(*) AS anzahl FROM flaechen{auswahl}""".format(auswahl=auswahl)

        if not self.dbQK.sql(sql, u"QKan_Tools.application.dlgro_countselection (1)"):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlgro.lf_anzahl_flaechen.setText(str(daten[0]))
        else:
            self.dlgro.lf_anzahl_flaechen.setText('0')


    # -------------------------------------------------------------------------
    # Funktion zur Zusammenstellung einer Auswahlliste für eine SQL-Abfrage

    def dlgro_listselecteditems(self, listWidget):
        """Erstellt eine Liste aus den in einem Auswahllisten-Widget angeklickten Objektnamen

        :param listWidget: String for translation.
        :type listWidget: QListWidgetItem

        :returns: Tuple containing selected teilgebiete
        :rtype: tuple
        """
        items = listWidget.selectedItems()
        liste = []
        for elem in items:
            liste.append(elem.text())
        return liste

    def run_runoffparams(self):
        """Berechnen und Eintragen der Oberflächenabflussparameter in die Tabelle flaechen"""

        # Check, ob die relevanten Layer nicht editable sind.
        if len({'flaechen'} & get_editable_layers()) > 0:
            iface.messageBar().pushMessage(u"Bedienerfehler: ",
                                           u'Die zu verarbeitenden Layer dürfen nicht im Status "bearbeitbar" sein. Abbruch!',
                                           level=QgsMessageBar.CRITICAL)
            return False

        # Übernahme der Quelldatenbank:
        # Wenn ein Projekt geladen ist, wird die Quelldatenbank daraus übernommen.
        # Wenn dies nicht der Fall ist, wird die Quelldatenbank aus der
        # json-Datei übernommen.

        database_QKan = ''

        database_QKan, epsg = get_database_QKan()
        if not database_QKan:
            logger.error(u"tools.application: database_QKan konnte nicht aus den Layern ermittelt werden. Abbruch!")
            return False
        self.dlgro.tf_QKanDB.setText(database_QKan)

        if 'manningrauheit_bef' in self.config:
            manningrauheit_bef = self.config['manningrauheit_bef']
        else:
            manningrauheit_bef = 0.02
            self.config['manningrauheit_bef'] = manningrauheit_bef
        if 'manningrauheit_dur' in self.config:
            manningrauheit_dur = self.config['manningrauheit_dur']
        else:
            manningrauheit_dur = 0.10
            self.config['manningrauheit_dur'] = manningrauheit_dur

        # Datenbankverbindung für Abfragen
        self.dbQK = DBConnection(dbname=database_QKan)  # Datenbankobjekt der QKan-Datenbank zum Lesen
        if self.dbQK is None or self.dbQK == False:
            fehlermeldung("Fehler in tools.runoffparams",
                          u'QKan-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format(database_QKan))
            iface.messageBar().pushMessage("Fehler in tools.runoffparams",
                                           u'QKan-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format( \
                                               database_QKan), level=QgsMessageBar.CRITICAL)
            return None
        elif not self.dbQK.status:
            # Datenbank wurde geändert
            return None

        # Check, ob alle Teilgebiete in Flächen auch in Tabelle "teilgebiete" enthalten

        sql = u"""INSERT INTO teilgebiete (tgnam)
                SELECT teilgebiet FROM flaechen 
                WHERE teilgebiet IS NOT NULL AND
                teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                GROUP BY teilgebiet"""
        if not self.dbQK.sql(sql, u"QKan_Tools.application.run (1) "):
            return False

        # Check, ob alle Abflussparameter in Flächen auch in Tabelle "abflussparameter" enthalten

        sql = u"""INSERT INTO abflussparameter (apnam)
                SELECT abflussparameter FROM flaechen 
                WHERE abflussparameter IS NOT NULL AND
                abflussparameter NOT IN (SELECT apnam FROM abflussparameter)
                GROUP BY abflussparameter"""
        if not self.dbQK.sql(sql, u"QKan_Tools.application.run (2) "):
            return False

        self.dbQK.commit()


        # Anlegen der Tabelle zur Auswahl der Teilgebiete

        # Zunächst wird die Liste der beim letzten Mal gewählten Teilgebiete aus config gelesen
        liste_teilgebiete = []
        if 'liste_teilgebiete' in self.config:
            liste_teilgebiete = self.config['liste_teilgebiete']

        # Abfragen der Tabelle teilgebiete nach Teilgebieten
        sql = '''SELECT "tgnam" FROM "teilgebiete" GROUP BY "tgnam"'''
        if not self.dbQK.sql(sql, u"QKan_Tools.application.run (4) "):
            return False
        daten = self.dbQK.fetchall()
        self.dlgro.lw_teilgebiete.clear()

        for ielem, elem in enumerate(daten):
            self.dlgro.lw_teilgebiete.addItem(QListWidgetItem(elem[0]))
            try:
                if elem[0] in liste_teilgebiete:
                    self.dlgro.lw_teilgebiete.setCurrentRow(ielem)
                    self.dlgro.cb_selTgbActive.setChecked(True)
            except BaseException as err:
                fehlermeldung(u'QKan_Tools (6), Fehler in elem = {}\n'.format(elem), repr(err))
                # if len(daten) == 1:
                # self.dlgro.lw_teilgebiete.setCurrentRow(0)


        # Anlegen der Tabelle zur Auswahl der Abflussparameter

        # Zunächst wird die Liste der beim letzten Mal gewählten Abflussparameter aus config gelesen
        liste_abflussparameter = []
        if 'liste_abflussparameter' in self.config:
            liste_abflussparameter = self.config['liste_abflussparameter']

        # Abfragen der Tabelle abflussparameter nach Abflussparametern
        sql = '''SELECT "apnam" FROM "abflussparameter" GROUP BY "apnam"'''
        if not self.dbQK.sql(sql, u"QKan_Tools.application.run (4) "):
            return False
        daten = self.dbQK.fetchall()
        self.dlgro.lw_abflussparameter.clear()

        for ielem, elem in enumerate(daten):
            self.dlgro.lw_abflussparameter.addItem(QListWidgetItem(elem[0]))
            try:
                if elem[0] in liste_abflussparameter:
                    self.dlgro.lw_abflussparameter.setCurrentRow(ielem)
                    self.dlgro.cb_selParActive.setChecked(True)
            except BaseException as err:
                fehlermeldung(u'QKan_Tools (6), Fehler in elem = {}\n'.format(elem), repr(err))
                # if len(daten) == 1:
                # self.dlgro.lw_abflussparameter.setCurrentRow(0)

        self.dlgro_countselection()

        # Funktionen zur Berechnung des Oberflächenabflusses
        # Werden nur gelesen
        if 'runoffparamsfunctions' in self.config:
            runoffparamsfunctions = self.config['runoffparamsfunctions']
        else:
            runoffparamsfunctions = {
                'itwh': [
                    '0.8693*log(area(geom))+ 5.6317', 
                    'pow(18.904*pow(neigkl,0.686)*area(geom), 0.2535*pow(neigkl,0.244))'], 
                'dyna': [
                    '0.02 * pow(abstand, 0.77) * pow(neigung, -0.385) + pow(2*{rauheit_bef} * (abstand + fliesslaenge) / SQRT(neigung), 0.467)'.format(rauheit_bef=manningrauheit_bef), 
                    'pow(2*{rauheit_dur} * (abstand + fliesslaenge) / SQRT(neigung), 0.467)'.format(rauheit_dur=manningrauheit_dur)], 
                'Maniak': [
                    '0.02 * pow(abstand, 0.77) * pow(neigung, -0.385) + pow(2*{rauheit_bef} * (abstand + fliesslaenge) / SQRT(neigung), 0.467)'.format(rauheit_bef=manningrauheit_bef), 
                    'pow(2*{rauheit_dur} * (abstand + fliesslaenge) / SQRT(neigung), 0.467)'.format(rauheit_dur=manningrauheit_dur),
                    '0.02 * pow(abstand, 0.77) * pow(neigung, -0.385) + pow(2*{rauheit_bef} * abstand / SQRT(neigung), 0.467)'.format(rauheit_bef=manningrauheit_bef), 
                    'pow(2*{rauheit_dur} * abstand / SQRT(neigung), 0.467)'.format(rauheit_dur=manningrauheit_dur),
                    '0.02 * pow(abstand, 0.77) * pow(neigung, -0.385) + pow(2*{rauheit_bef} * fliesslaenge / SQRT(neigung), 0.467)'.format(rauheit_bef=manningrauheit_bef), 
                    'pow(2*{rauheit_dur} * fliesslaenge / SQRT(neigung), 0.467)'.format(rauheit_dur=manningrauheit_dur)]
                }
            self.config['runoffparamsfunctions'] = runoffparamsfunctions
        
        # Optionen zur Berechnung des Oberflächenabflusses
        if 'runoffparamstype_choice' in self.config:
            runoffparamstype_choice = self.config['runoffparamstype_choice']
        else:
            runoffparamstype_choice = u'Maniak'

        if runoffparamstype_choice == u'itwh':
            self.dlgro.rb_itwh.setChecked(True)
        elif runoffparamstype_choice == u'dyna':
            self.dlgro.rb_dyna.setChecked(True)
        elif runoffparamstype_choice == u'Maniak':
            self.dlgro.rb_maniak.setChecked(True)

        if 'runoffmodelltype_choice' in self.config:
            runoffmodelltype_choice = self.config['runoffmodelltype_choice']
        else:
            runoffmodelltype_choice = u'Speicherkaskade'

        if runoffmodelltype_choice == u'Speicherkaskade':
            self.dlgro.rb_kaskade.setChecked(True)
        elif runoffmodelltype_choice == u'Fliesszeiten':
            self.dlgro.rb_fliesszeiten.setChecked(True)
        elif runoffmodelltype_choice == u'Schwerpunktlaufzeit':
            self.dlgro.rb_schwerpunktlaufzeit.setChecked(True)

        # Status Radiobuttons initialisieren
        self.dlgro_activateitwh()
        # Datenbanktyp
        if 'datenbanktyp' in self.config:
            datenbanktyp = self.config['datenbanktyp']
        else:
            datenbanktyp = 'spatialite'

        # Formular anzeigen

        self.dlgro.show()
        # Run the dialog event loop
        result = self.dlgro.exec_()
        # See if OK was pressed
        if result:

            # Abrufen der ausgewählten Elemente in den Listen
            liste_teilgebiete = self.dlgro_listselecteditems(self.dlgro.lw_teilgebiete)
            liste_abflussparameter = self.dlgro_listselecteditems(self.dlgro.lw_abflussparameter)

            # Eingaben aus Formular übernehmen
            database_QKan = self.dlgro.tf_QKanDB.text()
            if self.dlgro.rb_itwh.isChecked():
                runoffparamstype_choice = u'itwh'
            elif self.dlgro.rb_dyna.isChecked():
                runoffparamstype_choice = u'dyna'
            elif self.dlgro.rb_maniak.isChecked():
                runoffparamstype_choice = u'Maniak'
            else:
                fehlermeldung(u"tools.runoffparams.run_runoffparams", 
                              u"Fehlerhafte Option: \nrunoffparamstype_choice = {}".format(repr(runoffparamstype_choice)))
            if self.dlgro.rb_kaskade.isChecked():
                runoffmodelltype_choice = u'Speicherkaskade'
            elif self.dlgro.rb_fliesszeiten.isChecked():
                runoffmodelltype_choice = u'Fliesszeiten'
            elif self.dlgro.rb_schwerpunktlaufzeit.isChecked():
                runoffmodelltype_choice = u'Schwerpunktlaufzeit'
            else:
                fehlermeldung(u"tools.runoffparams.run_runoffparams", 
                              u"Fehlerhafte Option: \nrunoffmodelltype_choice = {}".format(repr(runoffmodelltype_choice)))

            # Konfigurationsdaten schreiben
            self.config['database_QKan'] = database_QKan
            self.config['liste_teilgebiete'] = liste_teilgebiete
            self.config['liste_abflussparameter'] = liste_abflussparameter
            self.config['runoffparamstype_choice'] = runoffparamstype_choice
            self.config['runoffmodelltype_choice'] = runoffmodelltype_choice

            with open(self.configfil, 'w') as fileconfig:
                # logger.debug(u"Config-Dictionary: {}".format(self.config))
                fileconfig.write(json.dumps(self.config))

            setRunoffparams(self.dbQK, runoffparamstype_choice, runoffmodelltype_choice, runoffparamsfunctions, 
                liste_teilgebiete, liste_abflussparameter, datenbanktyp)
