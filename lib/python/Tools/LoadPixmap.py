from enigma import loadPNG, loadJPG, loadSVG, getDesktop

# Return a scaling factor (float) that can be used to rescale images
# to suit the current resolution of the skin.
# The scales are based on a default screen resolution of HD (720p).
# That is the scale factor for a HD screen will be 1.
SKIN_FACTOR = getDesktop(0).size().height() / 720.0

# If cached is not supplied, LoadPixmap defaults to caching PNGs and not caching JPGs
# Split alpha channel JPGs are never cached as the C++ layer's caching is based on
# a single file per image in the cache
def LoadPixmap(path, desktop=None, cached=None, width=0, height=0):
	if path[-4:] == ".png":
		# cache unless caller explicity requests to not cache
		ptr = loadPNG(path, 0, 0 if cached is False else 1)
	elif path[-4:] == ".jpg":
		# don't cache unless caller explicity requests caching
		ptr = loadJPG(path, 1 if cached is True else 0)
	elif path[-4:] == ".svg":
		ptr = loadSVG(path, 0 if cached is False else 1, width, height, SKIN_FACTOR)
	elif path[-1:] == ".":
		# caching mechanism isn't suitable for multi file images, so it's explicitly disabled
		alpha = loadPNG(path + "a.png", 0, 0)
		ptr = loadJPG(path + "rgb.jpg", alpha, 0)
	else:
		raise Exception("Neither .png nor .jpg nor .svg, please fix file extension")
	if ptr and desktop:
		desktop.makeCompatiblePixmap(ptr)
	return ptr
