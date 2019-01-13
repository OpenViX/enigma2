from enigma import eLabel

# Note that calling this function will result in a call to invalidate() 
# on the instance object. This can be detrimental to UI performance, 
# particularly in a complex screen like the graph EPG
def getTextBoundarySize(instance, font, targetSize, text):
	dummy = eLabel(instance)
	dummy.setFont(font)
	dummy.resize(targetSize)
	dummy.setText(text)
	return dummy.calculateSize()