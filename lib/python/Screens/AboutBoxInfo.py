from Components.SystemInfo import BoxInfo
from Screens.TextBox import TextBox

class AboutBoxInfo(TextBox):
	def __init__(self, session):
		TextBox.__init__(self, session, label="AboutScrollLabel")
		self.setTitle(_("BoxInfo"))
		self.skinName = "AboutOE"

		BIlist = []
		for item in BoxInfo.getEnigmaInfoList():
			value = str(BoxInfo.getItem(item))
			for x in ("http://", "https://"):  # Trim URLs to domain only
				if value.startswith(x):
					value = value.split(x)[1].split('/')[0] + " [...]"
					break
			BIlist.append("%s:\t %s\n" % (item, value))
		self["AboutScrollLabel"].setText(''.join(BIlist))
