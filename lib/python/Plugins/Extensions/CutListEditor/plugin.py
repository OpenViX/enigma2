from Plugins.Plugin import PluginDescriptor


def main(session, service, **kwargs):
	from .ui import CutListEditor
	session.open(CutListEditor, service)


def Plugins(**kwargs):
	return PluginDescriptor(name="Cutlist Editor", description=_("Cutlist editor..."),
		where=PluginDescriptor.WHERE_MOVIELIST, needsRestart=False, fnc=main)
