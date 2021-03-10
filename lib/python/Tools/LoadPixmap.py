from enigma import loadPNG, loadJPG, loadSVG

def LoadPixmap(path, desktop = None, cached = False):
	if path[-4:] == ".png":
		ptr = loadPNG(path)
	elif path[-4:] == ".jpg":
		# don't cache unless caller explicity requests caching
		ptr = loadJPG(path, 1 if cached == True else 0)
	elif path[-4:] == ".svg":
		ptr = loadSVG(path, 0, 0 if cached == False else 1)
	elif path[-1:] == ".":
		alpha = loadPNG(path + "a.png")
		ptr = loadJPG(path + "rgb.jpg", alpha)
	else:
		raise Exception("Neither .png nor .jpg nor .svg, please fix file extension")
	if ptr and desktop:
		desktop.makeCompatiblePixmap(ptr)
	return ptr
