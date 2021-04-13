from Screens.About import CommitInfo
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.TextBox import TextBox
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Opkg import OpkgComponent
from Components.Sources.StaticText import StaticText
from Components.Slider import Slider
from Tools.BoundFunction import boundFunction
from enigma import eTimer, eDVBDB
from boxbranding import getBoxType, getImageVersion, getMachineBuild, getImageType
from Tools.Directories import fileExists
from urllib2 import urlopen

class UpdatePlugin(Screen, ProtectedScreen):
	skin = """
		<screen name="UpdatePlugin" position="center,center" size="550,300">
			<widget name="activityslider" position="0,0" size="550,5"  />
			<widget name="slider" position="0,150" size="550,30"  />
			<widget source="package" render="Label" position="10,30" size="540,20" font="Regular;18" halign="center" valign="center" backgroundColor="#25062748" transparent="1" />
			<widget source="status" render="Label" position="10,180" size="540,100" font="Regular;20" halign="center" valign="center" backgroundColor="#25062748" transparent="1" />
		</screen>"""

	def __init__(self, session, *args):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)

		self.sliderPackages = {"gigablue-": 1, "enigma2": 2, "teamblue-": 3}

		self.setTitle(_("Software update"))
		self.slider = Slider(0, 4)
		self["slider"] = self.slider
		self.activityslider = Slider(0, 100)
		self["activityslider"] = self.activityslider
		self.status = StaticText(_("Please wait..."))
		self["status"] = self.status
		self.package = StaticText(_("Package list update"))
		self["package"] = self.package
		self.oktext = _("Press OK on your remote control to continue.")

		self.packages = 0
		self.error = 0
		self.processed_packages = []
		self.total_packages = None

		self.channellist_only = 0
		self.channellist_name = ''
		self.updating = False
		self.opkg = OpkgComponent()
		self.opkg.addCallback(self.opkgCallback)
		self.onClose.append(self.__close)

		self["actions"] = ActionMap(["WizardActions"],
		{
			"ok": self.exit,
			"back": self.exit
		}, -1)

		self.activity = 0
		self.activityTimer = eTimer()
		self.activityTimer.callback.append(self.checkTraficLight)
		self.activityTimer.callback.append(self.doActivityTimer)
		self.activityTimer.start(100, True)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and\
			(not config.ParentalControl.config_sections.main_menu.value and not config.ParentalControl.config_sections.configuration.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and\
			config.ParentalControl.config_sections.software_update.value

	def checkTraficLight(self):
		self.activityTimer.callback.remove(self.checkTraficLight)
		self.activityTimer.start(100, False)
		message = ""
		picon = None
		default = True
		url = "http://images.teamblue.tech/status/%s-%s/" % (getImageVersion(), getImageType())
		# print "[SoftwareUpdate] url status: ", url
		try:
			# TODO: Use Twisted's URL fetcher, urlopen is evil. And it can
			# run in parallel to the package update.
			try:
				status = urlopen(url, timeout=5).read().split('!', 1)
				print status
			except:
				# bypass the certificate check
				from ssl import _create_unverified_context
				status = urlopen(url, timeout=5, context=_create_unverified_context()).read().split('!', 1)
				print status
			# prefer getMachineBuild
			if getMachineBuild() in status[0].split(','):
				message = len(status) > 1 and status[1] or _("The current software might not be stable.\nFor more information see %s.") % ("http://images.teamblue.tech")
				picon = MessageBox.TYPE_ERROR
				default = False
			# only use getBoxType if no getMachineBuild
			elif getBoxType() in status[0].split(','):
				message = len(status) > 1 and status[1] or _("The current software might not be stable.\nFor more information see %s.") % ("http://images.teamblue.tech")
				picon = MessageBox.TYPE_ERROR
				default = False
		except:
			message = _("The status of the current software could not be checked because %s can not be reached.") % ("http://images.teamblue.tech")
			picon = MessageBox.TYPE_ERROR
			default = False
		if default:
			self.showDisclaimer()
		else:
			message += "\n" + _("Do you want to update your receiver?")
			self.session.openWithCallback(self.startActualUpdate, MessageBox, message, default=default, picon=picon)

	def showDisclaimer(self, justShow=False):
		if config.usage.show_update_disclaimer.value or justShow:
			message = _("With this disclaimer the teamBlue team is informing you that we are working with nightly builds and it might be that after the upgrades your set top box \
is not anymore working as expected. Therefore it is recommended to create backups. If something went wrong you can easily and quickly restore. \
If you discover 'bugs' please keep them reported on www.teamblue.tech.\n\nDo you understand this?")
			list = not justShow and [(_("no"), False), (_("yes"), True), (_("yes") + " " + _("and never show this message again"), "never")] or []
			self.session.openWithCallback(boundFunction(self.disclaimerCallback, justShow), MessageBox, message, list=list, title=_("Disclaimer"))
		else:
			self.startActualUpdate(True)

	def disclaimerCallback(self, justShow, answer):
		if answer == "never":
			config.usage.show_update_disclaimer.value = False
			config.usage.show_update_disclaimer.save()
		if justShow and answer:
			self.opkgCallback(OpkgComponent.EVENT_DONE, None)
		else:
			self.startActualUpdate(answer)

	def getLatestImageTimestamp(self):
		url = "http://images.teamblue.tech/status/%s-%s/buildtimestamp-%s" % (getImageVersion(), getImageType(), getBoxType())
		# print "[SoftwareUpdate] url buildtimestamp: ", url
		try:
			# TODO: Use Twisted's URL fetcher, urlopen is evil. And it can
			# run in parallel to the package update.
			from time import strftime
			from datetime import datetime
			try:
				latestImageTimestamp = datetime.fromtimestamp(int(urlopen(url, timeout=5).read())).strftime(_("%Y-%m-%d %H:%M"))
			except:
				# bypass the certificate check
				from ssl import _create_unverified_context
				latestImageTimestamp = datetime.fromtimestamp(int(urlopen(url, timeout=5, context=_create_unverified_context()).read())).strftime(_("%Y-%m-%d %H:%M"))
		except:
			latestImageTimestamp = ""
		print "[SoftwareUpdate] latestImageTimestamp:", latestImageTimestamp
		return latestImageTimestamp

	def startActualUpdate(self, answer):
		if answer:
			self.updating = True
			self.opkg.startCmd(OpkgComponent.CMD_UPDATE)
		else:
			self.close()

	def doActivityTimer(self):
		self.activity += 1
		if self.activity == 100:
			self.activity = 0
		self.activityslider.setValue(self.activity)

	def showUpdateCompletedMessage(self):
		self.setEndMessage(ngettext("Update completed, %d package was installed.", "Update completed, %d packages were installed.", self.packages) % self.packages)

	def opkgCallback(self, event, param):
		if event == OpkgComponent.EVENT_DOWNLOAD:
			self.status.setText(_("Downloading"))
		elif event == OpkgComponent.EVENT_UPGRADE:
			if param in self.sliderPackages:
				self.slider.setValue(self.sliderPackages[param])
			self.package.setText(param)
			self.status.setText(_("Updating") + ": %s/%s" % (self.packages, self.total_packages))
			if not param in self.processed_packages:
				self.processed_packages.append(param)
				self.packages += 1
		elif event == OpkgComponent.EVENT_INSTALL:
			self.package.setText(param)
			self.status.setText(_("Installing"))
			if not param in self.processed_packages:
				self.processed_packages.append(param)
				self.packages += 1
		elif event == OpkgComponent.EVENT_REMOVE:
			self.package.setText(param)
			self.status.setText(_("Removing"))
			if not param in self.processed_packages:
				self.processed_packages.append(param)
				self.packages += 1
		elif event == OpkgComponent.EVENT_CONFIGURING:
			self.package.setText(param)
			self.status.setText(_("Configuring"))
		elif event == OpkgComponent.EVENT_MODIFIED:
			if config.plugins.softwaremanager.overwriteConfigFiles.value in ("N", "Y"):
				self.opkg.write(True and config.plugins.softwaremanager.overwriteConfigFiles.value)
			else:
				self.session.openWithCallback(
					self.modificationCallback,
					MessageBox,
					_("A configuration file (%s) has been modified since it was installed.\nDo you want to keep your modifications?") % (param)
				)
		elif event == OpkgComponent.EVENT_ERROR:
			self.error += 1
		elif event == OpkgComponent.EVENT_DONE:
			if self.updating:
				self.updating = False
				self.opkg.startCmd(OpkgComponent.CMD_UPGRADE_LIST)
			elif self.opkg.currentCommand == OpkgComponent.CMD_UPGRADE_LIST:
				self.total_packages = len(self.opkg.getFetchedList())
				if self.total_packages:
					latestImageTimestamp = self.getLatestImageTimestamp()
					if latestImageTimestamp:
						message = _("Latest available teamBlue %s build is from: %s") % (getImageVersion(), self.getLatestImageTimestamp()) + "\n"
						message += _("Do you want to update your receiver?") + "\n"
					else:
						message = _("Do you want to update your receiver?") + "\n"
					message += "(" + (ngettext("%s updated package available", "%s updated packages available", self.total_packages) % self.total_packages) + ")"
					if self.total_packages > 150:
						message += " " + _("Reflash recommended!")
					choices = [(_("Update and reboot (recommended)"), "cold"),
						(_("Update and ask to reboot"), "hot"),
						#(_("Update channel list only"), "channels"),
						(_("Show packages to be updated"), "showlist")]
				else:
					message = _("No updates available")
					choices = []
				if fileExists("/home/root/opkgupgrade.log"):
					choices.append((_("Show latest update log"), "log"))
				choices.append((_("Show latest commits"), "commits"))
				if not config.usage.show_update_disclaimer.value:
					choices.append((_("Show disclaimer"), "disclaimer"))
				choices.append((_("Cancel"), ""))
				self.session.openWithCallback(self.startActualUpgrade, ChoiceBox, title=message, list=choices, windowTitle=self.title)
			elif self.channellist_only > 0:
				if self.channellist_only == 1:
					self.setEndMessage(_("Could not find installed channel list."))
				elif self.channellist_only == 2:
					self.slider.setValue(2)
					self.opkg.startCmd(OpkgComponent.CMD_REMOVE, {'package': self.channellist_name})
					self.channellist_only += 1
				elif self.channellist_only == 3:
					self.slider.setValue(3)
					self.opkg.startCmd(OpkgComponent.CMD_INSTALL, {'package': self.channellist_name})
					self.channellist_only += 1
				elif self.channellist_only == 4:
					self.showUpdateCompletedMessage()
					eDVBDB.getInstance().reloadBouquets()
					eDVBDB.getInstance().reloadServicelist()
			elif self.error == 0:
				self.showUpdateCompletedMessage()
			else:
				self.activityTimer.stop()
				self.activityslider.setValue(0)
				error = _("Your receiver might be unusable now. Please consult the manual for further assistance before rebooting your receiver.")
				if self.packages == 0:
					error = _("No updates available. Please try again later.")
				if self.updating:
					error = _("Update failed. Your receiver does not have a working internet connection.")
				self.status.setText(_("Error") + " - " + error)
		elif event == OpkgComponent.EVENT_LISTITEM:
			if 'enigma2-plugin-settings-' in param[0] and self.channellist_only > 0:
				self.channellist_name = param[0]
				self.channellist_only = 2
		#print event, "-", param
		pass

	def setEndMessage(self, txt):
		self.slider.setValue(4)
		self.activityTimer.stop()
		self.activityslider.setValue(0)
		self.package.setText(txt)
		self.status.setText(self.oktext)

	def startActualUpgrade(self, answer):
		if not answer or not answer[1]:
			self.close()
			return
		if answer[1] == "cold":
			self.session.open(TryQuitMainloop, retvalue=42)
			self.close()
		elif answer[1] == "channels":
			self.channellist_only = 1
			self.slider.setValue(1)
			self.opkg.startCmd(OpkgComponent.CMD_LIST, args={'installed_only': True})
		elif answer[1] == "commits":
			self.session.openWithCallback(boundFunction(self.opkgCallback, OpkgComponent.EVENT_DONE, None), CommitInfo)
		elif answer[1] == "disclaimer":
			self.showDisclaimer(justShow=True)
		elif answer[1] == "showlist":
			text = "\n".join([x[0] for x in sorted(self.opkg.getFetchedList(), key=lambda d: d[0])])
			self.session.openWithCallback(boundFunction(self.opkgCallback, OpkgComponent.EVENT_DONE, None), TextBox, text, _("Packages to update"), True)
		elif answer[1] == "log":
			text = open("/home/root/opkgupgrade.log", "r").read()
			self.session.openWithCallback(boundFunction(self.opkgCallback, OpkgComponent.EVENT_DONE, None), TextBox, text, _("Latest update log"), True)
		else:
			self.opkg.startCmd(OpkgComponent.CMD_UPGRADE, args={'test_only': False})

	def modificationCallback(self, res):
		self.opkg.write(res and "N" or "Y")

	def exit(self):
		if not self.opkg.isRunning():
			if self.packages != 0 and self.error == 0 and self.channellist_only == 0:
				self.session.openWithCallback(self.exitAnswer, MessageBox, _("Update completed. Do you want to reboot your receiver?"))
			else:
				self.close()
		else:
			if not self.updating:
				self.close()

	def exitAnswer(self, result):
		if result is not None and result:
			self.session.open(TryQuitMainloop, retvalue=2)
		self.close()

	def __close(self):
		self.opkg.removeCallback(self.opkgCallback)
