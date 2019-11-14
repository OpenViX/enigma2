# Embedded file name: /usr/lib/enigma2/python/Plugins/Extensions/SoftcamSetup/SoftcamSetup.py
from . import _
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.FileList import FileEntryComponent, FileList
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Button import Button
from Components.Label import Label
from Components.config import config, ConfigElement, ConfigSubsection, ConfigSelection, ConfigSubList, getConfigListEntry, KEY_LEFT, KEY_RIGHT, KEY_OK
from Components.ConfigList import ConfigList
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Tools.GetEcmInfo import GetEcmInfo
import os
from camcontrol import CamControl
from enigma import eTimer, eDVBCI_UI, eListboxPythonStringContent, eListboxPythonConfigContent

class ConfigAction(ConfigElement):

    def __init__(self, action, *args):
        ConfigElement.__init__(self)
        self.value = '(OK)'
        self.action = action
        self.actionargs = args

    def handleKey(self, key):
        if key == KEY_OK:
            self.action(*self.actionargs)

    def getMulti(self, dummy):
        pass


class SoftcamSetup(Screen, ConfigListScreen):
    skin = '\n\t<screen name="SoftcamSetup" position="center,center" size="560,450" >\n\t\t<widget name="config" position="5,10" size="550,90" />\n\t\t<widget name="info" position="5,100" size="550,300" font="Fixed;18" />\n\t\t<ePixmap name="red" position="0,410" zPosition="1" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />\n\t\t<ePixmap name="green" position="140,410" zPosition="1" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />\n\t\t<ePixmap name="blue" position="420,410" zPosition="1" size="140,40" pixmap="skin_default/buttons/blue.png" transparent="1" alphatest="on" />\n\t\t<widget name="key_red" position="0,410" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />\n\t\t<widget name="key_green" position="140,410" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />\n\t\t<widget name="key_blue" position="420,410" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />\n\t</screen>'

    def __init__(self, session, showExtentionMenuOption):
        Screen.__init__(self, session)
        self.setup_title = _('EMU')
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'CiSelectionActions'], {'cancel': self.cancel,
         'green': self.save,
         'red': self.cancel}, -1)
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session)
        self.softcam = CamControl('softcam')
        self.cardserver = CamControl('cardserver')
        self.ecminfo = GetEcmInfo()
        newEcmFound, ecmInfo = self.ecminfo.getEcm()
        self['info'] = ScrollLabel(''.join(ecmInfo))
        self.EcmInfoPollTimer = eTimer()
        self.EcmInfoPollTimer.callback.append(self.setEcmInfo)
        self.EcmInfoPollTimer.start(1000)
        softcams = self.softcam.getList()
        cardservers = self.cardserver.getList()
        self.softcams = ConfigSelection(choices=softcams)
        self.softcams.value = self.softcam.current()
        self.list.append(getConfigListEntry(_('Seleccionar Softcam'), self.softcams))
        if cardservers:
            self.cardservers = ConfigSelection(choices=cardservers)
            self.cardservers.value = self.cardserver.current()
            self.list.append(getConfigListEntry(_('Seleccionar Cardserver'), self.cardservers))
        self.list.append(getConfigListEntry(_('Reiniciar softcam'), ConfigAction(self.restart, 's')))
        if cardservers:
            self.list.append(getConfigListEntry(_('Reiniciar cardserver'), ConfigAction(self.restart, 'c')))
            self.list.append(getConfigListEntry(_('Reiniciar softcam||cardserver'), ConfigAction(self.restart, 'sc')))
        if showExtentionMenuOption:
            self.list.append(getConfigListEntry(_('Mostrar EMU en menu extensiones'), config.misc.softcam_setup.extension_menu))
        self['key_red'] = Label(_('Cancel'))
        self['key_green'] = Label(_('OK'))
        self.onLayoutFinish.append(self.layoutFinished)

    def setEcmInfo(self):
        newEcmFound, ecmInfo = self.ecminfo.getEcm()
        if newEcmFound:
            self['info'].setText(''.join(ecmInfo))

    def layoutFinished(self):
        self.setTitle(self.setup_title)

    def restart(self, what):
        self.what = what
        if 's' in what:
            if 'c' in what:
                msg = _('Espere por favor, Reiniciando cardserver y softcam.')
            else:
                msg = _('Espere por favor, Reiniciando softcam.')
        elif 'c' in what:
            msg = _('Espere por favor, Reiniciando cardserver.')
        self.mbox = self.session.open(MessageBox, msg, MessageBox.TYPE_INFO)
        self.activityTimer = eTimer()
        self.activityTimer.timeout.get().append(self.doStop)
        self.activityTimer.start(100, False)

    def doStop(self):
        self.activityTimer.stop()
        if 'c' in self.what:
            self.cardserver.command('stop')
        if 's' in self.what:
            self.softcam.command('stop')
        self.oldref = self.session.nav.getCurrentlyPlayingServiceReference()
        self.session.nav.stopService()
        self.activityTimer = eTimer()
        self.activityTimer.timeout.get().append(self.doStart)
        self.activityTimer.start(1000, False)

    def doStart(self):
        self.activityTimer.stop()
        del self.activityTimer
        if 'c' in self.what:
            self.cardserver.select(self.cardservers.value)
            self.cardserver.command('start')
        if 's' in self.what:
            self.softcam.select(self.softcams.value)
            self.softcam.command('start')
        if self.mbox:
            self.mbox.close()
        self.close()
        self.session.nav.playService(self.oldref)
        del self.oldref

    def restartCardServer(self):
        if hasattr(self, 'cardservers'):
            self.restart('c')

    def restartSoftcam(self):
        self.restart('s')

    def save(self):
        what = ''
        if hasattr(self, 'cardservers') and self.cardservers.value != self.cardserver.current():
            what = 'sc'
        elif self.softcams.value != self.softcam.current():
            what = 's'
        if what:
            self.restart(what)
        else:
            from Components.PluginComponent import plugins
            plugins.reloadPlugins()
            config.misc.softcam_setup.extension_menu.save()
            self.close()

    def cancel(self):
        self.close()