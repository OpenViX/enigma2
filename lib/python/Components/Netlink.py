# Listen to hotplug events. Can be used to listen for hotplug events and
# similar things, like network connections being (un)plugged.
from os import getpid
import socket
import six


class NetlinkSocket(socket.socket):
	def __init__(self):
		NETLINK_KOBJECT_UEVENT = 15  # hasn't landed in socket yet, see linux/netlink.h
		socket.socket.__init__(self, socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT)
		self.bind((getpid(), -1))

	def parse(self):
		data = six.ensure_str(self.recv(512), encoding="ascii", errors='ignore')
		data = [x for x in data.split('\x00') if x] + [""]  # avoid empty strings in the output except the final one
		event = {}
		for item in data:
			if not item:
				# terminator
				yield event
				event = {}
			else:
				try:
					k, v = item.split('=', 1)
					event[k] = v
				except:
					event[None] = item


# Quick unit test (you can run this on any Linux machine)
if __name__ == '__main__':
	nls = NetlinkSocket()
	print("socket no:", nls.fileno())
	while 1:
		for item in nls.parse():
			print(repr(item))
