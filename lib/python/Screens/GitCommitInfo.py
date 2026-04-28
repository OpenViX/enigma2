from Components.ActionMap import ActionMap
from Components.config import config, ConfigSelectionNumber
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.Screen import Screen, ScreenSummary
from Screens.Setup import Setup

from enigma import eTimer, getEnigmaLastCommitDate
from datetime import datetime
import requests


config.misc.gcimaxpages = ConfigSelectionNumber(min=1, max=5, stepwidth=1, default=1, wraparound=True)


class GithubCommitLogs:
	def __init__(self, parent):
		self.parent = parent
		self.APIs = [
			("https://api.github.com/repos/oe-alliance/oe-alliance-core/commits", "OE-A Core"),  # expand later
			("https://api.github.com/repos/OpenViX/enigma2/commits", "Enigma2"),  # expand later
			("https://api.github.com/repos/OpenViX/skins/commits", "ViX Skins"),
			("https://api.github.com/repos/oe-alliance/oe-alliance-plugins/commits", "OE-A Plugins"),
			("https://api.github.com/repos/oe-alliance/AutoBouquetsMaker/commits", "AutoBouquetsMaker"),
			("https://api.github.com/repos/oe-mirrors/branding-module/commits", "Branding Module"),
		]
		self.index = 0
		self.page = 1
		self.APIcache = {}  # just for the life of the instance otherwise this data will go stale and block new data being loaded
		self.queryPattern = "?sha=%s&page=%s"
		self.compileTimstamp = int(datetime.strptime(getEnigmaLastCommitDate(), '%Y-%m-%d').timestamp())
		self.userAgent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
		self.defaultBranch = "master"  # for non OE-A Core / non Enigma2
		self.readGithubCommitLogsTimer = eTimer()  # for receiving multiple pages
		self.readGithubCommitLogsTimer.callback.append(self.readGithubCommitLogsTask)
		self.readGithubCommitLogsSoftwareUpdateTimer = eTimer()  # for receiving multiple pages
		self.readGithubCommitLogsSoftwareUpdateTimer.callback.append(self.readGithubCommitLogsSoftwareUpdateTask)
		self.skipCommits = ("openbh:", "openvix:", "PEP8 double aggressive")  # Stop showing changelog markers, these will be dropped in 6.9. Or PEP8 bot commits.

	def fetchLog(self, url):
		if url in self.APIcache:
			log = self.APIcache[url]
		else:
			response = requests.get(url, headers={"user-agent": self.userAgent}, timeout=5, verify=False)
			response.raise_for_status()
			log = response.json()
			self.APIcache[url] = log
		return log

	def fetchFailMsg(self, err):
		if "403" in str(err):
			print('[GitCommitLog] It seems you have hit your API limit - please try again later.', err)
			msg = _("It seems you have hit your API limit - please try again later.\n")
		else:
			print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
			msg = _("The commit log cannot be retrieved at the moment - please try again later.\n")
		return msg

	def readGithubCommitLogsSoftwareUpdate(self):
		self.readGithubCommitLogsSoftwareUpdateTimer.stop()
		self.page = 1
		self.readGithubCommitLogsSoftwareUpdateTask()

	def readGithubCommitLogsSoftwareUpdateTask(self):
		# this is supposed to only show commits not contained in the image
		forced_stop = False
		if self.getScreenTitle() == "OE-A Core":
			url = self.APIs[self.index][0] + self.queryPattern % (SystemInfo["oea-branch"], self.page)  # branch
		elif self.getScreenTitle() == "Enigma2":
			url = self.APIs[self.index][0] + self.queryPattern % (SystemInfo["e2-branch"], self.page)  # branch
		else:
			url = self.APIs[self.index][0] + self.queryPattern % (self.defaultBranch, self.page)
		commitlog = []
		try:
			for c in self.fetchLog(url):
				creator = c['commit']['author']['name']
				title = c['commit']['message']
				date = (date_obj := datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ')).strftime('%x %X')
				if (self.getScreenTitle() not in ("OE-A Core", "Enigma2") and self.compileTimstamp > int(date_obj.timestamp()) or
						self.getScreenTitle() in ("OE-A Core", "Enigma2") and c["sha"].startswith(SystemInfo["e2-sha"] if self.getScreenTitle() == "Enigma2" else SystemInfo["oea-sha"])):
					forced_stop = True
					break  # we are only supposed to be showing commits newer than the image
				if self.getScreenTitle() != "Enigma2" and title.startswith(self.skipCommits) or title.startswith("openvix:") and not title.startswith(f"openvix: {SystemInfo['imagetype']} {SystemInfo['imageversion']}."):
					continue
				commitlog.append(f"{date} {creator}\n{title}\n\n")
		except Exception as err:
			commitlog.append(self.fetchFailMsg(err))
			forced_stop = True
		if self.page == 1:
			if not commitlog:
				commitlog.append(_("No new commits found on this repository."))
				forced_stop = True
			self.parent.setText("".join(commitlog))
		else:
			self.parent.appendText("".join(commitlog))
		if not forced_stop and self.page < config.misc.gcimaxpages.value:
			self.page += 1
			self.readGithubCommitLogsSoftwareUpdateTimer.start(10, True)

	def readGithubCommitLogs(self):
		self.readGithubCommitLogsTimer.stop()
		self.page = 1
		self.readGithubCommitLogsTask()

	def readGithubCommitLogsTask(self):
		# this is supposed to only show commits contained in the image
		forced_stop = False
		if self.getScreenTitle() == "OE-A Core":
			url = self.APIs[self.index][0] + self.queryPattern % (SystemInfo["oea-sha"], self.page)  # commit hash
		elif self.getScreenTitle() == "Enigma2":
			url = self.APIs[self.index][0] + self.queryPattern % (SystemInfo["e2-sha"], self.page)  # commit hash
		else:
			url = self.APIs[self.index][0] + self.queryPattern % (self.defaultBranch, self.page)
		commitlog = []
		try:
			for c in self.fetchLog(url):
				creator = c['commit']['author']['name']
				title = c['commit']['message']
				date = (date_obj := datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ')).strftime('%x %X')
				# sha = c['commit']['tree']["sha"]
				if self.getScreenTitle() not in ("OE-A Core", "Enigma2") and (self.compileTimstamp + 24 * 60 * 60) < int(date_obj.timestamp()):
					continue  # when using a url without the hash avoid commits that are newer than the image, continue not break because the commits we want are later
				if self.getScreenTitle() != "Enigma2" and title.startswith(self.skipCommits) or title.startswith("openvix:") and not title.startswith(f"openvix: {SystemInfo['imagetype']} {SystemInfo['imageversion']}."):
					continue
				commitlog.append(f"{date} {creator}\n{title}\n\n")
		except Exception as err:
			commitlog.append(self.fetchFailMsg(err))
			forced_stop = True
		if self.page == 1:
			self.parent.setText("".join(commitlog))
		else:
			self.parent.appendText("".join(commitlog))
		if not forced_stop and self.page < config.misc.gcimaxpages.value:
			self.page += 1
			self.readGithubCommitLogsTimer.start(10, True)

	def getScreenTitle(self):
		return self.APIs[self.index][1]

	def updateIndex(self, n):
		self.index = (self.index + n) % len(self.APIs)


class CommitInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = ["CommitInfo", "AboutOE"]
		self["AboutScrollLabel"] = ScrollLabel(_("Please wait"))
		self.gitcommitinfo = GithubCommitLogs(self)
		self["HintText"] = Label(_("Press up/down to scroll through the selected log\n\nPress left/right to see different log types"))

		self["actions"] = ActionMap(["SetupActions", "DirectionActions", "MenuActions"],
			{
				"cancel": self.close,
				"ok": self.close,
				"up": self["AboutScrollLabel"].pageUp,
				"down": self["AboutScrollLabel"].pageDown,
				"left": self.left,
				"right": self.right,
				"menu": self.setup,
			}  # noqa: E123
		)

		self["key_red"] = StaticText(_("Close"))
		self["key_left"] = StaticText(_("LEFT"))
		self["key_right"] = StaticText(_("RIGHT"))
		self["key_menu"] = StaticText(_("MENU"))
		self.onUpdate = []

		self.Timer = eTimer()
		self.Timer.callback.append(self.readGithubCommitLogs)
		self.startTimer()

	def startTimer(self):
		self.Timer.start(10, True)

	def readGithubCommitLogs(self):
		self.setTitle(self.gitcommitinfo.getScreenTitle())
		self.gitcommitinfo.readGithubCommitLogs()

	def setText(self, msg):
		self["AboutScrollLabel"].setText(msg)
		self.update()

	def appendText(self, msg):
		self["AboutScrollLabel"].appendText(msg, showBottom=False)
		self.update()

	def updateCommitLogs(self):
		self["AboutScrollLabel"].setText(_("Please wait"))
		self.Timer.start(50, True)

	def update(self):
		for x in self.onUpdate:
			x()

	def left(self):
		self.gitcommitinfo.updateIndex(-1)
		self.updateCommitLogs()

	def right(self):
		self.gitcommitinfo.updateIndex(+1)
		self.updateCommitLogs()

	def createSummary(self):
		return CommitInfoSummary

	def setup(self):
		self.session.openWithCallback(self.startTimer, CommitInfoSetup)


class CommitInfoSetup(Setup):
	def __init__(self, session):
		Setup.__init__(self, session)

	def createSetup(self):
		self["config"].list = [(_("Max pages to retrieve"), config.misc.gcimaxpages, _("This is the number of pages to download per repository being interogated. More pages shows more commits, but, bear in mind that Github API has a limit of 60 pages per hour."))]


class CommitInfoSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.commitText = []
		self["commitText"] = StaticText()
		self.timer = eTimer()
		self.timer.callback.append(self.update)
		if self.changed not in parent.onUpdate:
			parent.onUpdate.append(self.changed)
		self.changed()

	def update(self):
		self.timer.stop()
		if self.commitText:
			self.commitText.append(self.commitText.pop(0))
			self["commitText"].text = "\n\n".join(self.commitText)
			self.timer.start(2000, 1)

	def changed(self):
		self.timer.stop()
		self["Title"].text = self.parent.getTitle()
		if self.parent["AboutScrollLabel"].getText():
			self.commitText = self.parent["AboutScrollLabel"].getText().split("\n\n")
			self["commitText"].text = "\n\n".join(self.commitText)
			self.timer.start(3000, 1)
