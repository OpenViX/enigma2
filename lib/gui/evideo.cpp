#include <lib/base/cfile.h>
#include <lib/gui/evideo.h>
#include <lib/gui/ewidgetdesktop.h>
#include <fstream>

ePtr<eTimer> eVideoWidget::fullsizeTimer;
int eVideoWidget::pendingFullsize = 0;
int eVideoWidget::posFullsizeLeft = 0;
int eVideoWidget::posFullsizeTop = 0;
int eVideoWidget::posFullsizeWidth = 0;
int eVideoWidget::posFullsizeHeight = 0;
int eVideoWidget::lastPigLeft[2]   = {0, 0};
int eVideoWidget::lastPigTop[2]    = {0, 0};
int eVideoWidget::lastPigWidth[2]  = {0, 0};
int eVideoWidget::lastPigHeight[2] = {0, 0};

static int s_bounceFixEnabled = -1; /* -1=uninitialised, 0=off, 1=on */

static bool bounceFixEnabled()
{
	if (s_bounceFixEnabled < 0)
	{
		std::ifstream f("/proc/stb/info/model");
		std::string boxtype;
		if (f && std::getline(f, boxtype))
		{
			s_bounceFixEnabled = (boxtype == "dm900" || boxtype == "dm920") ? 1 : 0;
		}
		else
		{
			s_bounceFixEnabled = 0;
		}
	}
	return s_bounceFixEnabled == 1;
}

eVideoWidget::eVideoWidget(eWidget *parent)
	:eLabel(parent), m_fb_size(720, 576), m_state(0), m_decoder(1)
{
	if (!fullsizeTimer)
	{
		fullsizeTimer = eTimer::create(eApp);
		fullsizeTimer->timeout.connect(sigc::bind(sigc::ptr_fun(&eVideoWidget::setFullsize), false));
		if (bounceFixEnabled() && posFullsizeWidth == 0)
		{
			posFullsizeWidth = 720;
			posFullsizeHeight = 576;
		}
	}
	parent->setPositionNotifyChild(1);
}

int eVideoWidget::event(int event, void *data, void *data2)
{
	switch (event)
	{
	case evtChangedPosition:
	case evtParentChangedPosition:
		m_state &= ~1;
		updatePosition(!isVisible());
		break;
	case evtChangedSize:
		m_state |= 2;
		updatePosition(!isVisible());
		break;
	case evtParentVisibilityChanged:
		updatePosition(!isVisible());
		break;
	}
	return eLabel::event(event, data, data2);
}

eVideoWidget::~eVideoWidget()
{
	updatePosition(1);
}

void eVideoWidget::setFBSize(eSize size)
{
	m_fb_size = size;
}

void eVideoWidget::setFullScreenPosition(eRect pos)
{
	posFullsizeLeft = pos.left();
	posFullsizeTop = pos.top();
	posFullsizeWidth = pos.width();
	posFullsizeHeight = pos.height();
	setPosition(0, posFullsizeLeft, posFullsizeTop, posFullsizeWidth, posFullsizeHeight);
}

void eVideoWidget::writeProc(const std::string &filename, int value)
{
	CFile f(filename.c_str(), "w");
	if (f)
		fprintf(f, "%08x\n", value);
}

void eVideoWidget::setPosition(int index, int left, int top, int width, int height)
{
	char filenamebase[128];
	snprintf(filenamebase, sizeof(filenamebase), "/proc/stb/vmpeg/%d/dst_", index);
	std::string filename = filenamebase;
	writeProc(filename + "left", left);
	writeProc(filename + "top", top);
	writeProc(filename + "width", width);
	writeProc(filename + "height", height);
	writeProc(filename + "apply", 1);
}

void eVideoWidget::setFullsize(bool force)
{
	for (int decoder=0; decoder < 2; ++decoder)
	{
		if (force || (pendingFullsize & (1 << decoder)))
		{
			if (bounceFixEnabled() && lastPigWidth[decoder] > 0 && lastPigHeight[decoder] > 0)
			{
				eVideoWidget::setPosition(decoder, posFullsizeLeft, posFullsizeTop, posFullsizeWidth, posFullsizeHeight);
				eVideoWidget::setPosition(decoder, lastPigLeft[decoder], lastPigTop[decoder], lastPigWidth[decoder], lastPigHeight[decoder]);
			}
			eVideoWidget::setPosition(decoder, posFullsizeLeft, posFullsizeTop, posFullsizeWidth, posFullsizeHeight);
			pendingFullsize &= ~(1 << decoder);
		}
	}
}

void eVideoWidget::updatePosition(int disable)
{
	if (!disable)
		m_state |= 4;

	if (disable && !(m_state & 4))
	{
		return;
	}

	if ((m_state & 2) != 2)
	{
		return;
	}

	eRect pos(0,0,0,0);
	if (!disable)
		pos = eRect(getAbsolutePosition(), size());
	else
		m_state &= ~4;

	if (!disable && m_state & 8 && pos == m_user_rect)
	{
		return;
	}

	if (!(m_state & 1))
	{
		m_user_rect = pos;
		m_state |= 1;
	}

	int left = pos.left() * 720 / m_fb_size.width();
	int top = pos.top() * 576 / m_fb_size.height();
	int width = pos.width() * 720 / m_fb_size.width();
	int height = pos.height() * 576 / m_fb_size.height();

	if (!disable)
	{
		if (bounceFixEnabled()
			&& left == posFullsizeLeft && top == posFullsizeTop
			&& width == posFullsizeWidth && height == posFullsizeHeight
			&& lastPigWidth[m_decoder] > 0 && lastPigHeight[m_decoder] > 0
			&& (lastPigWidth[m_decoder] != posFullsizeWidth || lastPigHeight[m_decoder] != posFullsizeHeight))
		{
			/* dm9xx: decoder may be in a reset/fullscreen state and ignore a direct
			 * fullscreen command. Bounce via the stored PIG position to force the
			 * driver to acknowledge the transition (same trick as setFullsize). */
			setPosition(m_decoder, posFullsizeLeft, posFullsizeTop, posFullsizeWidth, posFullsizeHeight);
			setPosition(m_decoder, lastPigLeft[m_decoder], lastPigTop[m_decoder], lastPigWidth[m_decoder], lastPigHeight[m_decoder]);
		}
		setPosition(m_decoder, left, top, width, height);
		lastPigLeft[m_decoder]   = left;
		lastPigTop[m_decoder]    = top;
		lastPigWidth[m_decoder]  = width;
		lastPigHeight[m_decoder] = height;
		pendingFullsize &= ~(1 << m_decoder);
		m_state |= 8;
	}
	else
	{
		m_state &= ~8;
		pendingFullsize |= (1 << m_decoder);
		fullsizeTimer->start(100, true);
	}
}

void eVideoWidget::setDecoder(int decoder)
{
	m_decoder = decoder;
}

