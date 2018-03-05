#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

  QGis-Plugin
  ===========

  Definition der Formularklasse

  | Dateiname            : application.py
  | Date                 : Februar 2017
  | Copyright            : (C) 2016 by Joerg Hoettges
  | Email                : hoettges@fh-aachen.de
  | git sha              : $Format:%H$

  This program is free software; you can redistribute it and/or modify  
  it under the terms of the GNU General Public License as published by  
  the Free Software Foundation; either version 2 of the License, or     
  (at your option) any later version.                                  

"""
# Ergaenzt (jh, 08.02.2017) -------------------------------------------------
import json
import logging
import os.path
import site

from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QFileDialog, QListWidgetItem
from qgis.core import QgsProject, QgsMessageLog
from qgis.gui import QgsMessageBar
from qgis.utils import iface, pluginDirectory

# noinspection PyUnresolvedReferences
import resources
# Initialize Qt resources from file resources.py
# Import the code for the dialog
from application_dialog import ExportToKPDialog
from k_qkkp import exportKanaldaten
from qkan import Dummy
from qkan.database.dbfunc import DBConnection
from qkan.database.qgis_utils import get_database_QKan, get_editable_layers, fortschritt, fehlermeldung

# Anbindung an Logging-System (Initialisierung in __init__)
logger = logging.getLogger('QKan')

progress_bar = None

class ExportToKP:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

        self.templatepath = os.path.join(pluginDirectory('qkan'), u"database/templates")

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ExportToKP_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = ExportToKPDialog()

        # Anfang Eigene Funktionen -------------------------------------------------
        # (jh, 08.02.2017)

        logger.info('\n\nQKan_ExportKP initialisiert...')

        # --------------------------------------------------------------------------
        # Pfad zum Arbeitsverzeichnis sicherstellen
        wordir = os.path.join(site.getuserbase(), 'qkan')

        if not os.path.isdir(wordir):
            os.makedirs(wordir)

        # --------------------------------------------------------------------------
        # Konfigurationsdatei qkan.json lesen
        #

        self.configfil = os.path.join(wordir, 'qkan.json')
        if os.path.exists(self.configfil):
            with open(self.configfil, 'r') as fileconfig:
                self.config = json.loads(fileconfig.read())
        else:
            self.config['dynafile'] = ''
            # Vorlagedatenbank nur für den Fall, dass der Anwender keine eigene Vorlage erstellen will
            self.config['template_dyna'] = os.path.join(os.path.dirname(__file__), "templates", "dyna.ein")
            self.config['database_QKan'] = ''
            with open(self.configfil, 'w') as fileconfig:
                fileconfig.write(json.dumps(self.config))

        # Standard für Suchverzeichnis festlegen
        project = QgsProject.instance()
        self.default_dir = os.path.dirname(project.fileName())

        if 'database_QKan' in self.config:
            database_QKan = self.config['database_QKan']
        else:
            database_QKan = ''
        self.dlg.tf_QKanDB.setText(database_QKan)
        self.dlg.pb_selectQKanDB.clicked.connect(self.selectFile_QKanDB)

        if 'dynafile' in self.config:
            dynafile = self.config['dynafile']
        else:
            dynafile = ''
        self.dlg.tf_KP_dest.setText(dynafile)
        self.dlg.pb_select_KP_dest.clicked.connect(self.selectFile_kpDB_dest)

        if 'template_dyna' in self.config:
            template_dyna = self.config['template_dyna']
        else:
            template_dyna = ''
        self.dlg.tf_KP_template.setText(template_dyna)
        self.dlg.pb_select_KP_template.clicked.connect(self.selectFile_kpDB_template)
        self.dlg.pb_select_KP_emptytemplate.clicked.connect(self.selectFile_kpDB_emptytemplate)

        if 'datenbanktyp' in self.config:
            datenbanktyp = self.config['datenbanktyp']
        else:
            datenbanktyp = 'spatialite'
            pass  # Es gibt noch keine Wahlmöglichkeit

        self.dlg.pb_exportall.clicked.connect(self.exportall)
        self.dlg.pb_exportnone.clicked.connect(self.exportnone)

        # Auswahl der zu exportierenden Tabellen ----------------------------------------------

        # Eigene Funktion für die zahlreichen Checkboxen

        def cb_set(name, cbox, default):
            if name in self.config:
                checked = self.config[name]
            else:
                checked = default
            cbox.setChecked(checked)
            return checked

        export_schaechte = cb_set('export_schaechte', self.dlg.cb_export_schaechte, True)
        export_auslaesse = cb_set('export_auslaesse', self.dlg.cb_export_auslaesse, True)
        export_speicher = cb_set('export_speicher', self.dlg.cb_export_speicher, True)
        export_haltungen = cb_set('export_haltungen', self.dlg.cb_export_haltungen, True)
        export_pumpen = cb_set('export_pumpen', self.dlg.cb_export_pumpen, False)
        export_wehre = cb_set('export_wehre', self.dlg.cb_export_wehre, False)
        export_flaechenrw = cb_set('export_flaechenrw', self.dlg.cb_export_flaechenrw, True)
        export_einleitdirekt = cb_set('export_einleitdirekt', self.dlg.cb_export_einleitdirekt, True)
        export_abflussparameter = cb_set('export_abflussparameter', self.dlg.cb_export_abflussparameter, True)
        export_regenschreiber = cb_set('export_regenschreiber', self.dlg.cb_export_regenschreiber, False)
        export_rohrprofile = cb_set('export_rohrprofile', self.dlg.cb_export_rohrprofile, False)
        export_speicherkennlinien = cb_set('export_speicherkennlinien', self.dlg.cb_export_speicherkennlinien, False)
        export_bodenklassen = cb_set('export_bodenklassen', self.dlg.cb_export_bodenklassen, False)

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
        return QCoreApplication.translate('ExportToKP', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/qkan/exportdyna/res/icon_qk2kp.png'
        Dummy.instance.add_action(icon_path,
                                  text=self.tr(u'Export in DYNA-Datei...'),
                                  callback=self.run,
                                  parent=self.iface.mainWindow())

    def unload(self):
        pass

    # Anfang Eigene Funktionen -------------------------------------------------
    # (jh, 08.02.2017)


    def selectFile_kpDB_dest(self):
        """Zu erstellende DYNA-Datei eingeben"""

        filename = QFileDialog.getSaveFileName(self.dlg, "Dateinamen der zu schreibenden DYNA-Datei eingeben",
                                               self.default_dir, "*.ein")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_KP_dest.setText(filename)

    def selectFile_kpDB_template(self):
        """Vorlage-DYNA-Datei auswaehlen."""

        filename = QFileDialog.getOpenFileName(self.dlg, u"Vorlage-DYNA-Datei auswählen",
                                               self.default_dir, "*.ein")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_KP_template.setText(filename)

    def selectFile_kpDB_emptytemplate(self):
        """Vorlage-DYNA-Datei auswaehlen."""

        filename = QFileDialog.getOpenFileName(self.dlg, u"Leere Vorlage-DYNA-Datei auswählen",
                                               self.templatepath, "*.ein")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_KP_template.setText(filename)

    def selectFile_QKanDB(self):
        """Datenbankverbindung zur QKan-Datenbank (SpatiLite) auswaehlen."""

        filename = QFileDialog.getOpenFileName(self.dlg, u"QKan-Datenbank auswählen",
                                               self.default_dir, "*.sqlite")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_QKanDB.setText(filename)

    def exportall(self):
        """Aktiviert alle Checkboxen zm Export"""

        self.dlg.cb_export_schaechte.setChecked(True)
        self.dlg.cb_export_auslaesse.setChecked(True)
        self.dlg.cb_export_speicher.setChecked(True)
        self.dlg.cb_export_haltungen.setChecked(True)
        self.dlg.cb_export_pumpen.setChecked(True)
        self.dlg.cb_export_wehre.setChecked(True)
        self.dlg.cb_export_flaechenrw.setChecked(True)
        self.dlg.cb_export_einleitdirekt.setChecked(True)
        self.dlg.cb_export_abflussparameter.setChecked(True)
        self.dlg.cb_export_regenschreiber.setChecked(True)
        self.dlg.cb_export_rohrprofile.setChecked(True)
        self.dlg.cb_export_speicherkennlinien.setChecked(True)
        self.dlg.cb_export_bodenklassen.setChecked(True)

    def exportnone(self):
        """Deaktiviert alle Checkboxen zm Export"""

        self.dlg.cb_export_schaechte.setChecked(False)
        self.dlg.cb_export_auslaesse.setChecked(False)
        self.dlg.cb_export_speicher.setChecked(False)
        self.dlg.cb_export_haltungen.setChecked(False)
        self.dlg.cb_export_pumpen.setChecked(False)
        self.dlg.cb_export_wehre.setChecked(False)
        self.dlg.cb_export_flaechenrw.setChecked(False)
        self.dlg.cb_export_einleitdirekt.setChecked(False)
        self.dlg.cb_export_abflussparameter.setChecked(False)
        self.dlg.cb_export_regenschreiber.setChecked(False)
        self.dlg.cb_export_rohrprofile.setChecked(False)
        self.dlg.cb_export_speicherkennlinien.setChecked(False)
        self.dlg.cb_export_bodenklassen.setChecked(False)

    # -------------------------------------------------------------------------
    # Formularfunktionen

    def countselection(self):
        """Zählt nach Änderung der Auswahlen in den Listen im Formular die Anzahl
        der betroffenen Flächen und Haltungen"""
        liste_teilgebiete = self.listselecteditems(self.dlg.lw_teilgebiete)

        # Zu berücksichtigende Flächen zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE flaechen.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM flaechen{auswahl}""".format(auswahl=auswahl)

        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (1)"):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_flaechen.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_flaechen.setText('0')

        # Zu berücksichtigende Schächte zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE schaechte.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM schaechte{auswahl}""".format(auswahl=auswahl)
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (2) "):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_schaechte.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_schaechte.setText('0')

        # Zu berücksichtigende Haltungen zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE haltungen.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM haltungen{auswahl}""".format(auswahl=auswahl)
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (3) "):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_haltungen.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_haltungen.setText('0')

    # -------------------------------------------------------------------------
    # Funktion zur Zusammenstellung einer Auswahlliste für eine SQL-Abfrage

    def listselecteditems(self, listWidget):
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

    # Ende Eigene Funktionen ---------------------------------------------------


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog

        # Check, ob die relevanten Layer nicht editable sind.
        if len({'flaechen', 'haltungen', 'linkfl', 'tezg', 'schaechte'} & get_editable_layers()) > 0:
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
            fehlermeldung(u"Fehler in k_link", u"database_QKan konnte nicht aus den Layern ermittelt werden. Abbruch!")
            logger.error("k_link: database_QKan konnte nicht aus den Layern ermittelt werden. Abbruch!")
            return False

        if database_QKan != '':
            self.dlg.tf_QKanDB.setText(database_QKan)

        # Datenbankverbindung für Abfragen
        self.dbQK = DBConnection(dbname=database_QKan)  # Datenbankobjekt der QKan-Datenbank zum Lesen
        if self.dbQK is None:
            fehlermeldung("Fehler in QKan_CreateUnbefFl",
                          u'QKan-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format(database_QKan))
            iface.messageBar().pushMessage("Fehler in QKan_Import_from_HE",
                                           u'QKan-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format( \
                                               database_QKan), level=QgsMessageBar.CRITICAL)
            return None

        # Check, ob alle Teilgebiete in Flächen, Schächten und Haltungen auch in Tabelle "teilgebiete" enthalten

        sql = u"""INSERT INTO teilgebiete (tgnam)
                SELECT teilgebiet FROM flaechen 
                WHERE teilgebiet IS NOT NULL AND
                teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                GROUP BY teilgebiet"""
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (1) "):
            return False

        sql = u"""INSERT INTO teilgebiete (tgnam)
                SELECT teilgebiet FROM haltungen 
                WHERE teilgebiet IS NOT NULL AND
                teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                GROUP BY teilgebiet"""
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (2) "):
            return False

        sql = u"""INSERT INTO teilgebiete (tgnam)
                SELECT teilgebiet FROM schaechte 
                WHERE teilgebiet IS NOT NULL AND
                teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                GROUP BY teilgebiet"""
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (3) "):
            return False

        self.dbQK.commit()

        # Anlegen der Tabelle zur Auswahl der Teilgebiete

        # Zunächst wird die Liste der beim letzten Mal gewählten Teilgebiete aus config gelesen
        liste_teilgebiete = []
        if 'liste_teilgebiete' in self.config:
            liste_teilgebiete = self.config['liste_teilgebiete']

        # Abfragen der Tabelle teilgebiete nach Teilgebieten
        sql = 'SELECT "tgnam" FROM "teilgebiete" GROUP BY "tgnam"'
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (4) "):
            return False
        daten = self.dbQK.fetchall()
        self.dlg.lw_teilgebiete.clear()

        for ielem, elem in enumerate(daten):
            self.dlg.lw_teilgebiete.addItem(QListWidgetItem(elem[0]))
            try:
                if elem[0] in liste_teilgebiete:
                    self.dlg.lw_teilgebiete.setCurrentRow(ielem)
            except BaseException as err:
                fehlermeldung(u'QKan_ExportDYNA (6), Fehler in elem = {}\n'.format(elem), repr(err))
                # if len(daten) == 1:
                # self.dlg.lw_teilgebiete.setCurrentRow(0)

        # Ereignis bei Auswahländerung in Liste Teilgebiete

        self.dlg.lw_teilgebiete.itemClicked.connect(self.countselection)
        self.countselection()

        # Autokorrektur

        if 'autokorrektur' in self.config:
            autokorrektur = self.config['autokorrektur']
        else:
            autokorrektur = True
        self.dlg.cb_autokorrektur.setChecked(autokorrektur)

        # Festlegung des Fangradius
        if 'fangradius' in self.config:
            fangradius = self.config['fangradius']
        else:
            fangradius = u'0.1'

        # Formular anzeigen

        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            # Abrufen der ausgewählten Elemente in beiden Listen
            liste_teilgebiete = self.listselecteditems(self.dlg.lw_teilgebiete)

            # Eingaben aus Formular übernehmen
            database_Qkan = self.dlg.tf_QKanDB.text()
            dynafile = self.dlg.tf_KP_dest.text()
            template_dyna = self.dlg.tf_KP_template.text()
            datenbanktyp = 'spatialite'
            autokorrektur = self.dlg.cb_autokorrektur.isChecked()

            check_export = {}
            check_export['export_schaechte'] = self.dlg.cb_export_schaechte.isChecked()
            check_export['export_auslaesse'] = self.dlg.cb_export_auslaesse.isChecked()
            check_export['export_speicher'] = self.dlg.cb_export_speicher.isChecked()
            check_export['export_haltungen'] = self.dlg.cb_export_haltungen.isChecked()
            check_export['export_pumpen'] = self.dlg.cb_export_pumpen.isChecked()
            check_export['export_wehre'] = self.dlg.cb_export_wehre.isChecked()
            check_export['export_flaechenrw'] = self.dlg.cb_export_flaechenrw.isChecked()
            check_export['export_einleitdirekt'] = self.dlg.cb_export_einleitdirekt.isChecked()
            check_export['export_abflussparameter'] = self.dlg.cb_export_abflussparameter.isChecked()
            check_export['export_regenschreiber'] = self.dlg.cb_export_regenschreiber.isChecked()
            check_export['export_rohrprofile'] = self.dlg.cb_export_rohrprofile.isChecked()
            check_export['export_speicherkennlinien'] = self.dlg.cb_export_speicherkennlinien.isChecked()
            check_export['export_bodenklassen'] = self.dlg.cb_export_bodenklassen.isChecked()

            # Konfigurationsdaten schreiben
            self.config['dynafile'] = dynafile
            self.config['template_dyna'] = template_dyna
            self.config['database_Qkan'] = database_Qkan
            self.config['datenbanktyp'] = datenbanktyp
            self.config['liste_teilgebiete'] = liste_teilgebiete
            self.config['autokorrektur'] = autokorrektur
            self.config['fangradius'] = fangradius
            for el in check_export:
                self.config[el] = check_export[el]

            with open(self.configfil, 'w') as fileconfig:
                # logger.debug(u"Config-Dictionary: {}".format(self.config))
                fileconfig.write(json.dumps(self.config))

            exportKanaldaten(iface, dynafile, template_dyna, self.dbQK, liste_teilgebiete, autokorrektur, 
                             fangradius, datenbanktyp, check_export)
