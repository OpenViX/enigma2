from enigma import loadPNG, loadJPG, loadSVG


# cached is completely ignored and we do not cache anything #Brian was here
# Split alpha channel JPGs are never cached as the C++ layer's caching is based on
# a single file per image in the cache
def LoadPixmap(path, desktop=None, cached=None, width=0, height=0):
	if path[-4:] == ".png":
		# don't cache unless caller explicity requests caching
		ptr = loadPNG(path, 0, 0)
	elif path[-4:] == ".jpg":
		# don't cache unless caller explicity requests caching
		ptr = loadJPG(path, 0)
	elif path[-4:] == ".svg":
		from skin import parameters, getSkinFactor # imported here to avoid circular import
		autoscale = int(parameters.get("AutoscaleSVG", -1)) # skin_default only == -1, disabled == 0 or enabled == 1
		scale = height == 0 and (autoscale == -1 and "/skin_default/" in path or autoscale == 1) and getSkinFactor() or 0
		# don't cache unless caller explicity requests caching
		ptr = loadSVG(path, 0, width, height, scale)
	elif path[-1:] == ".":
		# caching mechanism isn't suitable for multi file images, so it's explicitly disabled
		alpha = loadPNG(path + "a.png", 0, 0)
		ptr = loadJPG(path + "rgb.jpg", alpha, 0)
	else:
		raise Exception("Neither .png nor .jpg nor .svg, please fix file extension")
	if ptr and desktop:
		desktop.makeCompatiblePixmap(ptr)
	return ptr
