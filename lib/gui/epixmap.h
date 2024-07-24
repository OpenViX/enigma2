#ifndef __lib_gui_epixmap_h
#define __lib_gui_epixmap_h

#include <lib/gui/ewidget.h>
#include <lib/base/nconfig.h> // access to python config

class ePixmap: public eWidget
{
	int m_alphatest;
	int m_scale;
public:
	ePixmap(eWidget *parent);

	void setPixmap(gPixmap *pixmap);
	void setPixmap(ePtr<gPixmap> &pixmap);
	void setPixmapFromFile(const char *filename);
	void setAlphatest(int alphatest); /* 1 for alphatest, 2 for alphablend */
	void setScale(int scale);
	void setBorderWidth(int pixel);
	void setBorderColor(const gRGB &color);
protected:
	ePtr<gPixmap> m_pixmap;
	int event(int event, void *data=0, void *data2=0);
	void checkSize();
private:
	enum eLabelEvent
	{
		evtChangedPixmap = evtUserWidget,
	};
	bool m_have_border_color;
	int m_force_blending = eConfigManager::getConfigIntValue("config.skin.pixmap_force_alphablending", 0);
	int m_border_width;
	gRGB m_border_color;
};

#endif
