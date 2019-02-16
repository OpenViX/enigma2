from enigma import loadPNG, loadJPG
from Tools.LRUCache import lru_cache

def LoadPixmap(path, desktop=None, cached=None):
	# default to caching pngs, and not caching jpg (which tend not to be used by skins)
	# PNGs are also statically cached in the c++ loadPNG method with no ability to clear or refresh, so there's
	# currently no point adding file modified checking
	# but there is still overhead fetching them back to the Python layer proportional to their size
	# hence caching here which reduces load time to a constant <2ms
	if cached is None:
		cached = path[-4:] == ".png"
	if cached:
		ret = _cached_load(path, desktop)
	else:
		ret = _load(path, desktop)
	return ret

@lru_cache(maxsize=256)
def _cached_load(path, desktop):
	return _load(path, desktop)

def _load(path, desktop):
	if path[-4:] == ".png":
		ptr = loadPNG(path)
	elif path[-4:] == ".jpg":
		ptr = loadJPG(path)
	elif path[-1:] == ".":
		alpha = loadPNG(path + "a.png")
		ptr = loadJPG(path + "rgb.jpg", alpha)
	else:
		raise Exception("neither .png nor .jpg, please fix file extension")
	if ptr and desktop:
		desktop.makeCompatiblePixmap(ptr)
	return ptr
