from __future__ import absolute_import
from Plugins.Plugin import PluginDescriptor
from .SocketMMI import SocketMMIMessageHandler

socketHandler = None


def main(session, **kwargs):
	socketHandler.startMMI()


def menu(menuid, **kwargs):
	if menuid == "setup" and socketHandler and socketHandler.connected():
		return [(socketHandler.getName(), main, "socket_mmi", 0)]
	return []


def sessionstart(reason, session):
	global socketHandler
	if socketHandler is None:
		socketHandler = SocketMMIMessageHandler()
	socketHandler.setSession(session)


def autostart(reason, **kwargs):
	global socketHandler
	if reason == 1:
		socketHandler = None


def Plugins(**kwargs):
	return [PluginDescriptor(name="SocketMMI", description=_("Python frontend for /tmp/mmi.socket"), where=PluginDescriptor.WHERE_MENU, needsRestart=True, fnc=menu),
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, needsRestart=True, fnc=sessionstart),
		PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, needsRestart=True, fnc=autostart)]
