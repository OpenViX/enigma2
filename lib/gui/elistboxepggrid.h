#ifndef __lib_gui_elistboxepggrid_h
#define __lib_gui_elistboxepggrid_h

#include <lib/gui/elistboxcontent.h>
#include <lib/gdi/gpixmap.h>
#include <lib/python/python.h>
#include <map>
#include <string>
#include <vector>

/*
 * Native renderer for the grid EPG ("Graphical EPG") list.
 *
 * The Python side (Components/EpgListGrid.py) only supplies data and configuration;
 * (Optional extension entries are painted on top via the multi content machinery.)
 * all geometry, colour selection and drawing is done here, directly through the painter,
 * so painting a row no longer builds ~50 Python tuples (and no longer needs a Python
 * callback per row, nor a Python-side row cache).
 *
 * Every list entry is a tuple:
 *   (serviceRef:str, serviceName:str, events:list|None, channelNumber:int|None, decor:list|None, playing:int)
 * events: [(eventId, title, begin, duration), ...] sorted by begin time
 * decor:  None or a list parallel to events with (clockIcon, autoIcon, timerKind, fullMatch):
 *           clockIcon: index 0..5 into the clock pixmaps or -1
 *           autoIcon : 0 none, 1 autotimer, 2 icetv
 *           timerKind: 0 none, 1 record, 2 zap   (timer touching the event, selects the background)
 *           fullMatch: 1 if the timer spans the entire event (selects the record/zap colours)
 */
class eListboxEpgGridContent: public eListboxPythonMultiContent
{
public:
	eListboxEpgGridContent();
	~eListboxEpgGridContent();

	enum {
		pixNowEvent, pixNowSelEvent, pixOtherEvent, pixSelEvent,
		pixOtherService, pixNowService,
		pixRecEvent, pixRecSelEvent, pixZapEvent, pixZapSelEvent,
		pixBorderTop, pixBorderBottom, pixBorderLeft, pixBorderRight,
		pixBorderSelTop, pixBorderSelBottom, pixBorderSelLeft, pixBorderSelRight,
		pixInfo, pixSelInfo,
		pixAutoTimer, pixIceTV, pixCatchup,
		pixClock0, pixClock1, pixClock2, pixClock3, pixClock4, pixClock5,
		pixSelClock0, pixSelClock1, pixSelClock2, pixSelClock3, pixSelClock4, pixSelClock5,
		pixElements
	};

	enum {
		colFore, colForeSel, colBack, colBackSel,
		colForeNow, colForeNowSel, colBackNow, colBackNowSel,
		colForeRec, colForeRecSel, colBackRec, colBackRecSel,
		colForeZap, colForeZapSel, colBackZap, colBackZapSel,
		colBorder,
		colServiceFore, colServiceBack, colServiceForeNow, colServiceBackNow, colServiceBorder,
		colElements
	};

	enum { fontService, fontEvent, fontElements };

	void setPixmap(int type, ePtr<gPixmap> &pic);
	void setColor(int type, unsigned int argb);
	void setFont(int type, gFont *font);
	// dict with integer/bool/list-of-str settings; see applyConfig() for the keys
	void setConfig(SWIG_PYOBJECT(ePyObject) config);
	// index of the highlighted event inside the selected row, -1 for none
	void setSelectedEvent(int index);
	// Optional python hook (called with the unpacked row tuple) returning a multi content list
	// ([None, (TYPE_TEXT, ...), ...]) that is painted on top of the native row; None disables it.
	void setExtensionFunc(SWIG_PYOBJECT(ePyObject) func);
	// rows without events cannot be selected (skip them when moving the cursor)
	void setOverjump(bool overjump) { m_overjump = overjump; }
	void clearPiconCache();

	static void setGetPiconNameFunc(SWIG_PYOBJECT(ePyObject) func);

#ifndef SWIG
protected:
	void paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected);
	int currentCursorSelectable();

private:
	struct Config
	{
		bool graphic;
		bool highlightNow;
		bool showName, showNumber, showPicon;
		std::vector<int> titleOrder; // 0 picon, 1 number, 2 name
		int timeBase, timeEpochSecs;
		int serviceWidth;
		int serviceBorderWidth, serviceNamePadding, serviceNumberPadding;
		int eventBorderWidth, eventNamePadding, eventTextSidesMargin;
		int serviceNumberWidth, piconWidth, infoWidth;
		int serviceNameAlign, serviceNumberAlign, eventAlign;
		int recIconPos; // 0 hide, 1 middle, 2 top, 3 bottom
		Config();
	} m_cfg;

	ePtr<gPixmap> m_pix[pixElements];
	gRGB m_col[colElements];
	ePtr<gFont> m_fonts[fontElements];
	int m_selected_event;
	bool m_has_extension;
	bool m_overjump;

	struct PiconEntry { ePtr<gPixmap> pixmap; };
	std::map<std::string, PiconEntry> m_picon_cache;
	static ePyObject m_GetPiconNameFunc;
	gPixmap *getPicon(const std::string &ref);

	void paintBackground(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected);
	void paintService(gPainter &painter, const eRect &r1, const ePoint &offset, const std::string &ref, const std::string &name, int channel, bool playing, int ellipsis);
	void paintEvents(gPainter &painter, const eRect &r2, const ePoint &offset, PyObject *events, PyObject *decor, const std::string &ref, bool rowSelected, int ellipsis);
	void blitPix(gPainter &painter, gPixmap *pix, const eRect &rect, int flags);
	void fillRect(gPainter &painter, const eRect &rect, const gRGB &color);
	void drawBox(gPainter &painter, const eRect &rect, const gRGB &back, const gRGB &border, int bw);
#endif
};

#endif
