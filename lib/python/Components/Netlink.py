# Listen to hotplug events. Can be used to listen for hotplug events and
# similar things, like network connections being (un)plugged.
from __future__ import print_function
import os
import socket
import six


class NetlinkSocket(socket.socket):
	def __init__(self):
		NETLINK_KOBJECT_UEVENT = 15 # hasn't landed in socket yet, see linux/netlink.h
		socket.socket.__init__(self, socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT)
		self.bind((os.getpid(), -1))

	def parse(self):
		data = self.recv(512)
# Some items from libudev contain a 32-byte binary structure that is
# not parseable by this code. So remove it.
#
		if data.startswith(b'libudev\x00'):
			data = data[0:8] + data[40:]

# If we can't handle the data, report it then ignore it.
		try:
			data = six.ensure_str(data, errors='ignore')
		except UnicodeError:
			print("[Netlink::NetlinkSocket] couldn't parse:", data)
			return  # Just ignore this one
		event = {}
		for item in data.split('\x00'):
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
