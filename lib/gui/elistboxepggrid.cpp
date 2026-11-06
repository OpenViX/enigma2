#include <lib/gui/elistboxepggrid.h>
#include <lib/gdi/epng.h>
#include <lib/gdi/font.h>
#include <lib/gui/ewindowstyle.h>
#include <lib/base/eerror.h>
#include <time.h>
#include <stdio.h>
#include <strings.h>
#include <stdlib.h>
#include <string.h>

extern RESULT SwigFromPython(ePtr<gPixmap> &res, PyObject *obj);

ePyObject eListboxEpgGridContent::m_GetPiconNameFunc;

/* ---- small helpers -------------------------------------------------------- */

// python style floor division (b > 0)
static inline long long floorDiv(long long a, long long b)
{
	long long q = a / b;
	if ((a % b != 0) && (a < 0))
		--q;
	return q;
}

static inline long long pyLong(PyObject *o, long long def = 0)
{
	if (!o || o == Py_None)
		return def;
	if (PyLong_Check(o))
		return PyLong_AsLongLong(o);
	if (PyFloat_Check(o))
		return (long long)PyFloat_AsDouble(o);
	return def;
}

static inline std::string pyStr(PyObject *o)
{
	if (o && PyUnicode_Check(o))
	{
		const char *s = PyUnicode_AsUTF8(o);
		if (s)
			return s;
	}
	return std::string();
}

static int dictInt(PyObject *d, const char *key, int def)
{
	PyObject *o = PyDict_GetItemString(d, key); // borrowed
	if (!o || o == Py_None)
		return def;
	if (PyBool_Check(o))
		return o == Py_True ? 1 : 0;
	return (int)pyLong(o, def);
}

/* ---- config ----------------------------------------------------------------- */

eListboxEpgGridContent::Config::Config()
	: graphic(false), highlightNow(true), showName(true), showNumber(false), showPicon(false)
	, timeBase(0), timeEpochSecs(7200), serviceWidth(0)
	, serviceBorderWidth(1), serviceNamePadding(3), serviceNumberPadding(9)
	, eventBorderWidth(1), eventNamePadding(3), eventTextSidesMargin(0)
	, serviceNumberWidth(0), piconWidth(0), infoWidth(0)
	, serviceNameAlign(gPainter::RT_HALIGN_LEFT | gPainter::RT_VALIGN_CENTER)
	, serviceNumberAlign(gPainter::RT_HALIGN_LEFT | gPainter::RT_VALIGN_CENTER)
	, eventAlign(gPainter::RT_HALIGN_LEFT | gPainter::RT_VALIGN_CENTER)
	, recIconPos(1)
{
}

eListboxEpgGridContent::eListboxEpgGridContent()
	: m_selected_event(-1), m_has_extension(false), m_overjump(false)
{
	for (int i = 0; i < colElements; ++i)
		m_col[i] = gRGB(0xffffff);
}

eListboxEpgGridContent::~eListboxEpgGridContent()
{
}

void eListboxEpgGridContent::setPixmap(int type, ePtr<gPixmap> &pic)
{
	if (type >= 0 && type < pixElements)
		m_pix[type] = pic;
	if (m_listbox && m_listbox->isVisible())
		m_listbox->invalidate();
}

void eListboxEpgGridContent::setColor(int type, unsigned int argb)
{
	if (type >= 0 && type < colElements)
		m_col[type] = gRGB(argb);
}

void eListboxEpgGridContent::setFont(int type, gFont *font)
{
	if (type >= 0 && type < fontElements)
		m_fonts[type] = font;
	eListboxPythonMultiContent::setFont(type, font); // fonts for the extension entries
}

void eListboxEpgGridContent::setExtensionFunc(ePyObject func)
{
	m_has_extension = func && func != Py_None && PyCallable_Check(func);
	setBuildFunc(m_has_extension ? func : ePyObject());
	if (m_listbox && m_listbox->isVisible())
		m_listbox->invalidate();
}

void eListboxEpgGridContent::setSelectedEvent(int index)
{
	m_selected_event = index;
}

void eListboxEpgGridContent::clearPiconCache()
{
	m_picon_cache.clear();
}

void eListboxEpgGridContent::setConfig(ePyObject config)
{
	if (!config || !PyDict_Check(config))
		return;
	Config c;
	c.graphic = dictInt(config, "graphic", 0) != 0;
	c.highlightNow = dictInt(config, "highlightNow", 1) != 0;
	c.timeBase = dictInt(config, "timeBase", m_cfg.timeBase);
	c.timeEpochSecs = dictInt(config, "timeEpochSecs", 7200);
	if (c.timeEpochSecs <= 0)
		c.timeEpochSecs = 7200;
	c.serviceWidth = dictInt(config, "serviceWidth", 0);
	c.serviceBorderWidth = dictInt(config, "serviceBorderWidth", 1);
	c.serviceNamePadding = dictInt(config, "serviceNamePadding", 3);
	c.serviceNumberPadding = dictInt(config, "serviceNumberPadding", 9);
	c.eventBorderWidth = dictInt(config, "eventBorderWidth", 1);
	c.eventNamePadding = dictInt(config, "eventNamePadding", 3);
	c.eventTextSidesMargin = dictInt(config, "eventTextSidesMargin", 0);
	c.serviceNumberWidth = dictInt(config, "serviceNumberWidth", 0);
	c.piconWidth = dictInt(config, "piconWidth", 0);
	c.infoWidth = dictInt(config, "infoWidth", 0);
	c.serviceNameAlign = dictInt(config, "serviceNameAlign", c.serviceNameAlign);
	c.serviceNumberAlign = dictInt(config, "serviceNumberAlign", c.serviceNumberAlign);
	c.eventAlign = dictInt(config, "eventAlign", c.eventAlign);
	c.recIconPos = dictInt(config, "recIconPos", 1);

	PyObject *order = PyDict_GetItemString(config, "titleOrder"); // borrowed
	if (order && PyList_Check(order))
	{
		Py_ssize_t n = PyList_Size(order);
		for (Py_ssize_t i = 0; i < n; ++i)
		{
			std::string item = pyStr(PyList_GET_ITEM(order, i));
			if (item == "picon") { c.titleOrder.push_back(0); c.showPicon = true; }
			else if (item == "servicenumber") { c.titleOrder.push_back(1); c.showNumber = true; }
			else if (item == "servicename") { c.titleOrder.push_back(2); c.showName = true; }
		}
		// showName defaults to true above, make it reflect the actual mode
		bool hasName = false;
		for (size_t i = 0; i < c.titleOrder.size(); ++i)
			if (c.titleOrder[i] == 2)
				hasName = true;
		c.showName = hasName;
	}

	if (c.piconWidth != m_cfg.piconWidth)
		m_picon_cache.clear();
	m_cfg = c;
	if (m_listbox && m_listbox->isVisible())
		m_listbox->invalidate();
}

void eListboxEpgGridContent::setGetPiconNameFunc(ePyObject func)
{
	if (m_GetPiconNameFunc)
		Py_DECREF(m_GetPiconNameFunc);
	m_GetPiconNameFunc = func;
	if (m_GetPiconNameFunc)
		Py_INCREF(m_GetPiconNameFunc);
}

/* ---- picons ------------------------------------------------------------------ */

gPixmap *eListboxEpgGridContent::getPicon(const std::string &ref)
{
	std::map<std::string, PiconEntry>::iterator it = m_picon_cache.find(ref);
	if (it != m_picon_cache.end())
		return it->second.pixmap;

	PiconEntry entry;
	if (m_GetPiconNameFunc)
	{
		ePyObject args = PyTuple_New(1);
		PyTuple_SET_ITEM(args, 0, PyUnicode_FromString(ref.c_str()));
		ePyObject ret = PyObject_CallObject(m_GetPiconNameFunc, args);
		Py_DECREF(args);
		if (ret)
		{
			std::string file = pyStr(ret);
			Py_DECREF(ret);
			if (!file.empty())
			{
				bool svg = file.size() > 4 && !strcasecmp(file.c_str() + file.size() - 4, ".svg");
				loadImage(entry.pixmap, file.c_str(), 0, svg ? m_cfg.piconWidth : 0);
			}
		}
		else
			PyErr_Print();
	}
	if (m_picon_cache.size() > 1024) // keep it bounded, rows get re-resolved on demand
		m_picon_cache.clear();
	return (m_picon_cache[ref] = entry).pixmap;
}

/* ---- primitive drawing -------------------------------------------------------- */

void eListboxEpgGridContent::fillRect(gPainter &painter, const eRect &rect, const gRGB &color)
{
	painter.clip(rect);
	painter.setBackgroundColor(color);
	painter.clear();
	painter.clippop();
}

// filled box with a frame of width bw drawn inside of it
void eListboxEpgGridContent::drawBox(gPainter &painter, const eRect &rect, const gRGB &back, const gRGB &border, int bw)
{
	fillRect(painter, rect, back);
	if (bw > 0)
	{
		const int x = rect.left(), y = rect.top(), w = rect.width(), h = rect.height();
		painter.clip(rect);
		painter.setForegroundColor(border);
		painter.fill(eRect(x, y, w, bw));
		painter.fill(eRect(x, y + bw, bw, h - bw));
		painter.fill(eRect(x + bw, y + h - bw, w - bw, bw));
		painter.fill(eRect(x + w - bw, y + bw, bw, h - bw));
		painter.clippop();
	}
}

void eListboxEpgGridContent::blitPix(gPainter &painter, gPixmap *pix, const eRect &rect, int flags)
{
	if (!pix || rect.width() <= 0 || rect.height() <= 0)
		return;
	painter.blit(pix, rect, rect, flags | gPainter::BT_ALPHABLEND);
}

/* ---- row painting -------------------------------------------------------------- */

void eListboxEpgGridContent::paintBackground(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{
	eListboxStyle *local_style = m_listbox ? m_listbox->getLocalStyle() : 0;
	style.setStyle(painter, eWindowStyle::styleListboxNormal);
	if (local_style)
	{
		if (local_style->m_background_color_set)
			painter.setBackgroundColor(local_style->m_background_color);
		if (local_style->m_transparent_background)
			return;
	}
	painter.clear();
}

void eListboxEpgGridContent::paintService(gPainter &painter, const eRect &r1, const ePoint &offset, const std::string &ref, const std::string &name, int channel, bool playing, int ellipsis)
{
	const Config &c = m_cfg;
	const int sbw = c.serviceBorderWidth;
	const gRGB fore = m_col[playing ? colServiceForeNow : colServiceFore];
	const gRGB back = m_col[playing ? colServiceBackNow : colServiceBack];
	gPixmap *bgpng = m_pix[playing ? pixNowService : pixOtherService];

	if (bgpng && c.graphic)
	{
		blitPix(painter, bgpng, eRect(r1.left() + sbw, r1.top() + sbw, r1.width() - 2 * sbw, r1.height() - 2 * sbw), gPainter::BT_SCALE);
	}
	else
	{
		drawBox(painter, eRect(r1.left(), r1.top(), r1.width() + sbw, r1.height() + sbw), back, m_col[colServiceBorder], sbw);
	}

	int colX = r1.left() + sbw;
	const int textY = r1.top() + sbw;
	const int textH = r1.height() - 2 * sbw;

	for (size_t i = 0; i < c.titleOrder.size(); ++i)
	{
		switch (c.titleOrder[i])
		{
		case 0: // picon
		{
			int pw = c.piconWidth;
			if (pw > c.serviceWidth - 2 * sbw)
				pw = c.serviceWidth - 2 * sbw;
			gPixmap *picon = getPicon(ref);
			if (picon)
			{
				blitPix(painter, picon, eRect(colX, textY, pw, textH),
					gPainter::BT_SCALE | gPainter::BT_KEEP_ASPECT_RATIO | gPainter::BT_HALIGN_CENTER | gPainter::BT_VALIGN_CENTER);
			}
			else if (!c.showName && m_fonts[fontEvent])
			{
				// No picon so show the service name in the picon space anyway.
				eRect rect(colX, textY, pw, textH);
				painter.clip(rect);
				painter.setFont(m_fonts[fontEvent]);
				painter.setForegroundColor(fore);
				painter.renderText(rect, name, c.serviceNameAlign | ellipsis);
				painter.clippop();
			}
			colX += pw;
			break;
		}
		case 1: // service number
		{
			int w = c.serviceNumberWidth;
			if (channel >= 10000) // the cached width was measured for four digits
			{
				int digits = 0;
				for (int n = channel; n; n /= 10)
					++digits;
				w = c.serviceNumberWidth * digits / 4;
			}
			if (channel > 0 && m_fonts[fontService])
			{
				eRect rect(colX + c.serviceNumberPadding, textY, w, textH);
				painter.clip(rect);
				painter.setFont(m_fonts[fontService]);
				painter.setForegroundColor(fore);
				char buf[16];
				snprintf(buf, sizeof(buf), "%d", channel);
				painter.renderText(rect, buf, c.serviceNumberAlign | ellipsis);
				painter.clippop();
			}
			colX += w + 2 * c.serviceNumberPadding;
			break;
		}
		case 2: // service name
		{
			int w = r1.width() - (colX - r1.left()) - 2 * c.serviceNamePadding - sbw;
			if (w > 0 && m_fonts[fontService])
			{
				eRect rect(colX + c.serviceNamePadding, textY, w, textH);
				painter.clip(rect);
				painter.setFont(m_fonts[fontService]);
				painter.setForegroundColor(fore);
				painter.renderText(rect, name, c.serviceNameAlign | ellipsis);
				painter.clippop();
			}
			colX += w + 2 * c.serviceNamePadding;
			break;
		}
		}
	}

	// service cell borders (graphic skins), these are the separator lines between the rows
	if (c.graphic)
	{
		if (m_pix[pixBorderTop])
			blitPix(painter, m_pix[pixBorderTop], eRect(r1.left(), r1.top(), r1.width(), sbw), gPainter::BT_SCALE);
		if (m_pix[pixBorderBottom])
			blitPix(painter, m_pix[pixBorderBottom], eRect(r1.left(), r1.top() + r1.height() - sbw, r1.width(), sbw), gPainter::BT_SCALE);
		if (m_pix[pixBorderLeft])
			blitPix(painter, m_pix[pixBorderLeft], eRect(r1.left(), r1.top(), sbw, r1.height()), gPainter::BT_SCALE);
		if (m_pix[pixBorderRight])
			blitPix(painter, m_pix[pixBorderRight], eRect(r1.left() + r1.width() - sbw, r1.top(), sbw, r1.height()), gPainter::BT_SCALE);
	}
}

void eListboxEpgGridContent::paintEvents(gPainter &painter, const eRect &r2, const ePoint &offset, PyObject *events, PyObject *decor, const std::string &ref, bool rowSelected, int ellipsis)
{
	const Config &c = m_cfg;
	const int left = r2.left();
	const int top = r2.top();
	const int width = r2.width();
	const int height = r2.height();
	const int ebw = c.eventBorderWidth;
	const bool hasEvents = events && PySequence_Check(events) && PySequence_Size(events) > 0;

	/* ---- row (empty area) background and borders ---- */
	if (c.graphic)
	{
		if (m_pix[pixBorderTop])
		{
			blitPix(painter, m_pix[pixBorderTop], eRect(left, top, width, ebw), gPainter::BT_SCALE);
		}
		if (m_pix[pixBorderBottom])
			blitPix(painter, m_pix[pixBorderBottom], eRect(left, top + height - ebw, width, ebw), gPainter::BT_SCALE);
		if (m_pix[pixBorderLeft])
			blitPix(painter, m_pix[pixBorderLeft], eRect(left, top, ebw, height), gPainter::BT_SCALE);
		if (m_pix[pixBorderRight])
			blitPix(painter, m_pix[pixBorderRight], eRect(left + width - ebw, top, ebw, height), gPainter::BT_SCALE);

		// Only the selected graphic when there is nothing to fill with, avoids lingering highlights.
		gPixmap *png = (rowSelected && !hasEvents && m_pix[pixSelEvent]) ? (gPixmap *)m_pix[pixSelEvent] : (gPixmap *)m_pix[pixOtherEvent];
		blitPix(painter, png, eRect(left + ebw, top + ebw, width - 2 * ebw, height - 2 * ebw), gPainter::BT_SCALE);
	}
	else
	{
		const bool wholeSelected = rowSelected && !hasEvents;
		drawBox(painter, eRect(left, top, width + ebw, height + ebw),
			m_col[wholeSelected ? colBackSel : colBack], m_col[colBorder], ebw);
	}

	if (!hasEvents || !m_fonts[fontEvent])
		return;

	/* ---- events ---- */
	const long long start = c.timeBase;
	const long long span = c.timeEpochSecs;
	const long long end = start + span;
	const long long now = time(NULL);

	// catchup availability only depends on the service and the event begin time
	long long catchupSecs = -1;
	{
		size_t p = ref.find("catchupdays=");
		if (p != std::string::npos && m_pix[pixCatchup])
			catchupSecs = atoll(ref.c_str() + p + 12) * 86400LL;
	}

	const bool haveDecor = decor && PySequence_Check(decor);
	const Py_ssize_t count = PySequence_Size(events);
	PyObject *evSeq = PySequence_Fast(events, "events");
	PyObject *decSeq = haveDecor ? PySequence_Fast(decor, "decor") : NULL;
	if (!evSeq)
	{
		PyErr_Clear();
		Py_XDECREF(decSeq);
		return;
	}

	for (Py_ssize_t i = 0; i < count; ++i)
	{
		PyObject *ev = PySequence_Fast_GET_ITEM(evSeq, i);
		if (!PyTuple_Check(ev) || PyTuple_Size(ev) < 4)
			continue;
		const long long stime = pyLong(PyTuple_GET_ITEM(ev, 2));
		const long long duration = pyLong(PyTuple_GET_ITEM(ev, 3));

		// position, clipped to the grid
		long long xpos = floorDiv((stime - start) * width, span);
		long long ewidth = floorDiv((stime + duration - start) * width, span) - xpos;
		if (xpos < 0)
		{
			ewidth += xpos;
			xpos = 0;
		}
		if (xpos + ewidth > width)
			ewidth = width - xpos;
		if (ewidth <= 0 || xpos >= width)
			continue;

		int clockIcon = -1, autoIcon = 0, timerKind = 0, fullMatch = 0;
		if (decSeq && i < PySequence_Fast_GET_SIZE(decSeq))
		{
			PyObject *d = PySequence_Fast_GET_ITEM(decSeq, i);
			if (PyTuple_Check(d) && PyTuple_Size(d) >= 4)
			{
				clockIcon = (int)pyLong(PyTuple_GET_ITEM(d, 0), -1);
				autoIcon = (int)pyLong(PyTuple_GET_ITEM(d, 1));
				timerKind = (int)pyLong(PyTuple_GET_ITEM(d, 2));
				fullMatch = (int)pyLong(PyTuple_GET_ITEM(d, 3));
			}
		}

		const bool selected = rowSelected && (int)i == m_selected_event;
		const bool isNow = c.highlightNow && stime <= now && now < stime + duration;

		gRGB foreColor, backColor;
		int colBase;
		if (timerKind && fullMatch)
			colBase = (timerKind == 1) ? colForeRec : colForeZap;
		else if (isNow)
			colBase = colForeNow;
		else
			colBase = colFore;
		// each group is ordered fore, foreSel, back, backSel
		foreColor = m_col[colBase + (selected ? 1 : 0)];
		backColor = m_col[colBase + 2 + (selected ? 1 : 0)];

		gPixmap *bgpng;
		gPixmap *infoPix;
		gPixmap *bTop, *bBottom, *bLeft, *bRight;
		if (selected)
		{
			bTop = m_pix[pixBorderSelTop]; bBottom = m_pix[pixBorderSelBottom];
			bLeft = m_pix[pixBorderSelLeft]; bRight = m_pix[pixBorderSelRight];
			infoPix = m_pix[pixSelInfo];
			bgpng = m_pix[isNow ? pixNowSelEvent : pixSelEvent];
			if (timerKind)
				bgpng = m_pix[timerKind == 1 ? pixRecSelEvent : pixZapSelEvent];
		}
		else
		{
			bTop = m_pix[pixBorderTop]; bBottom = m_pix[pixBorderBottom];
			bLeft = m_pix[pixBorderLeft]; bRight = m_pix[pixBorderRight];
			infoPix = m_pix[pixInfo];
			bgpng = m_pix[pixOtherEvent];
			if (timerKind)
				bgpng = m_pix[timerKind == 1 ? pixRecEvent : pixZapEvent];
			else if (isNow)
				bgpng = m_pix[pixNowEvent];
		}

		const int x = left + (int)xpos;
		const int w = (int)ewidth;

		// box background
		if (bgpng && c.graphic)
			blitPix(painter, bgpng, eRect(x + ebw, top + ebw, w - 2 * ebw, height - 2 * ebw), gPainter::BT_SCALE);
		else
			drawBox(painter, eRect(x, top, w + ebw, height + ebw), backColor, m_col[colBorder], ebw);

		// text or the "information" glyph for boxes that are too narrow to show a title
		const int evX = x + ebw + c.eventNamePadding;
		const int evY = top + ebw;
		const int evW = w - 2 * (ebw + c.eventNamePadding);
		const int evH = height - 2 * ebw;
		if (c.infoWidth > 0 && evW < c.infoWidth && infoPix)
		{
			painter.blit(infoPix, eRect(x + ebw, evY, w - 2 * ebw, evH), eRect(x + ebw, evY, w - 2 * ebw, evH),
				gPainter::BT_ALPHABLEND | gPainter::BT_HALIGN_CENTER | gPainter::BT_VALIGN_CENTER);
		}
		else
		{
			eRect trect(evX + c.eventTextSidesMargin, evY, evW - c.eventTextSidesMargin * 2, evH);
			if (trect.width() > 0 && trect.height() > 0)
			{
				const std::string title = pyStr(PyTuple_GET_ITEM(ev, 1));
				painter.clip(trect);
				painter.setFont(m_fonts[fontEvent]);
				painter.setForegroundColor(foreColor);
				painter.renderText(trect, title, c.eventAlign | ellipsis);
				painter.clippop();
			}
		}

		// graphic borders
		if (c.graphic)
		{
			if (bTop) blitPix(painter, bTop, eRect(x, top, w, ebw), gPainter::BT_SCALE);
			if (bBottom) blitPix(painter, bBottom, eRect(x, top + height - ebw, w, ebw), gPainter::BT_SCALE);
			if (bLeft) blitPix(painter, bLeft, eRect(x, top, ebw, height), gPainter::BT_SCALE);
			if (bRight) blitPix(painter, bRight, eRect(x + w - ebw, top, ebw, height), gPainter::BT_SCALE);
		}

		// timer icons
		int iconX = x + w - 5;
		gPixmap *clockPix = NULL;
		if (clockIcon >= 0 && clockIcon < 6)
			clockPix = m_pix[(rowSelected ? pixSelClock0 : pixClock0) + clockIcon];
		gPixmap *autoPix = autoIcon == 1 ? (gPixmap *)m_pix[pixAutoTimer] : autoIcon == 2 ? (gPixmap *)m_pix[pixIceTV] : NULL;

		if (clockPix && c.recIconPos != 0)
		{
			const int clockW = clockPix->size().width();
			const int autoW = autoPix ? autoPix->size().width() : 0;
			if (w > clockW + autoW)
			{
				const int ph = clockPix->size().height();
				int iy;
				if (c.recIconPos == 1)
					iy = top + (height - ph) / 2;
				else if (c.recIconPos == 2)
					iy = top + 3;
				else
					iy = top + height - ph - 10;
				const int ix = x + w - clockW - 10;
				blitPix(painter, clockPix, eRect(ix, iy, clockW, ph), 0);
				iconX = ix;
				if (autoPix)
					blitPix(painter, autoPix, eRect(ix - autoPix->size().width() - 5, iy, autoPix->size().width(), autoPix->size().height()), 0);
			}
		}

		if (catchupSecs >= 0 && stime && stime < now && now - stime <= catchupSecs)
		{
			gPixmap *cp = m_pix[pixCatchup];
			const int cw = cp->size().width();
			const int ch = cp->size().height();
			int iy;
			if (c.recIconPos == 1)
				iy = top + (height - ch) / 2;
			else if (c.recIconPos == 2)
				iy = top + 3;
			else
				iy = top + height - ch - 10;
			blitPix(painter, cp, eRect(iconX - cw - 6, iy, cw, ch), 0);
		}
	}

	Py_XDECREF(decSeq);
	Py_DECREF(evSeq);
}

void eListboxEpgGridContent::paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{
	const Config &c = m_cfg;
	const eRect itemRect(offset, m_itemsize);
	const int ellipsis = ellipsisEnabled() ? gPainter::RT_ELLIPSIS : 0;

	painter.clip(itemRect);
	paintBackground(painter, style, offset, selected);

	if (m_list && cursorValid())
	{
		PyObject *row = PyList_GET_ITEM(m_list, m_cursor); // borrowed
		if (PyTuple_Check(row) && PyTuple_Size(row) >= 6)
		{
			const std::string ref = pyStr(PyTuple_GET_ITEM(row, 0));
			const std::string name = pyStr(PyTuple_GET_ITEM(row, 1));
			PyObject *events = PyTuple_GET_ITEM(row, 2);
			const int channel = (int)pyLong(PyTuple_GET_ITEM(row, 3));
			PyObject *decor = PyTuple_GET_ITEM(row, 4);
			const bool playing = pyLong(PyTuple_GET_ITEM(row, 5)) != 0;

			const int sw = c.serviceWidth;
			const eRect r1(offset.x(), offset.y(), sw, m_itemsize.height());
			const eRect r2(offset.x() + sw, offset.y(), m_itemsize.width() - sw, m_itemsize.height());

			paintService(painter, r1, offset, ref, name, channel, playing, ellipsis);
			paintEvents(painter, r2, offset, events == Py_None ? NULL : events, decor == Py_None ? NULL : decor, ref, selected != 0, ellipsis);
		}
		else
			eDebug("[eListboxEpgGridContent] malformed row %d", m_cursor);
	}

	painter.clippop();

	if (m_has_extension)
	{
		m_overlay = true;
		eListboxPythonMultiContent::paint(painter, style, offset, selected);
		m_overlay = false;
	}
}

int eListboxEpgGridContent::currentCursorSelectable()
{
	if (!m_list || !cursorValid())
		return 0;
	if (!m_overjump)
		return 1;
	PyObject *row = PyList_GET_ITEM(m_list, m_cursor);
	if (!PyTuple_Check(row) || PyTuple_Size(row) < 3)
		return 0;
	PyObject *events = PyTuple_GET_ITEM(row, 2);
	return (events && events != Py_None && PySequence_Check(events) && PySequence_Size(events) > 0) ? 1 : 0;
}
