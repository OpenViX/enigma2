# Embedded file name: /usr/lib/enigma2/python/Plugins/Extensions/SoftcamSetup/plugin.py
from . import _
from Plugins.Plugin import PluginDescriptor
from Components.config import config, ConfigSubsection, ConfigYesNo
from Tools.BoundFunction import boundFunction
config.misc.softcam_setup = ConfigSubsection()
config.misc.softcam_setup.extension_menu = ConfigYesNo(default=True)

def main(session, showExtentionMenuOption = False, **kwargs):
    import SoftcamSetup
    session.open(SoftcamSetup.SoftcamSetup, showExtentionMenuOption)


def menu(menuid, **kwargs):
    if menuid == 'cam':
        return [(_('EMU...'),
          boundFunction(main, showExtentionMenuOption=True),
          'softcam_setup',
          -1)]
    return []


def Plugins(**kwargs):
    name = _('EMU')
    description = _('Lets you configure your softcams')
    list = [PluginDescriptor(name=name, description=description, where=PluginDescriptor.WHERE_MENU, fnc=menu)]
    if config.misc.softcam_setup.extension_menu.value:
        list.append(PluginDescriptor(name=name, description=description, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main))
    return list