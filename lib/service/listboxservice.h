#ifndef __lib_service_listboxservice_h
#define __lib_service_listboxservice_h

#include <lib/gdi/gpixmap.h>
#include <lib/gui/elistbox.h>
#include <lib/service/iservice.h>
#include <lib/service/event.h>
#include <lib/python/python.h>
#include <map>
#include <memory>
#include <set>
#include <vector>

#ifndef SWIG
// Optional paint timing for A/B comparing the renderers, enabled by the environment variable
// E2_SERVICELIST_PROFILE (results are logged every two seconds of painting).
class eServiceListPaintTimer
{
public:
	enum { statLegacy, statTemplate, statTemplateBuild, statCount };
	eServiceListPaintTimer(int stat);
	~eServiceListPaintTimer();
	void setMiss() { m_miss = true; }
private:
	int m_stat;
	bool m_miss;
	long long m_start;
};
#endif

class eListboxServiceContent: public virtual iListboxContent
{
	DECLARE_REF(eListboxServiceContent);
protected:
	static ePyObject m_GetPiconNameFunc;
public:
	eListboxServiceContent();

	void addService(const eServiceReference &ref, bool beforeCurrent=false);
	void removeCurrent();
	void FillFinished();

	void setIgnoreService( const eServiceReference &service );
	void setRoot(const eServiceReference &ref, bool justSet=false);
	void getCurrent(eServiceReference &ref);
	void getPrev(eServiceReference &ref);
	void getNext(eServiceReference &ref);
	PyObject *getList();

	int getNextBeginningWithChar(char c);
	int getPrevMarkerPos();
	int getNextMarkerPos();
	int getCurrentSelectionIndex() { return cursorResolve(m_cursor_number); }
	eSize getItemSize() { return m_itemsize; }
	int getListSize() { return m_size_visible; }

		/* support for marked services */
	void initMarked();
	void addMarked(const eServiceReference &ref);
	void removeMarked(const eServiceReference &ref);
	int isMarked(const eServiceReference &ref);

		/* this is NOT thread safe! */
	void markedQueryStart();
	int markedQueryNext(eServiceReference &ref);

	int lookupService(const eServiceReference &ref);
	bool setCurrent(const eServiceReference &ref);

	enum {
		visModeSimple,
		visModeComplex,
		visSkinDefined
	};

	void setVisualMode(int mode);

		/* only in complex mode: */
	enum {
		celServiceNumber,
		celMarkerPixmap,
		celFolderPixmap,
		celServiceEventProgressbar,
		celServiceName,
		celServiceInfo, // "now" event
		celServiceNextInfo, // "next" event
		celServiceTypePixmap,
		celServiceInfoRemainingTime,
		celElements
	};

	enum {
		picDVB_S,
		picDVB_T,
		picDVB_C,
		picStream,
		picServiceGroup,
		picFolder,
		picMarker,
		picServiceEventProgressbar,
		picCrypto,
		picRecord,
		pic4K,
		picHD,
		picSD,
		picBackup,
		picCatchup,
		picElements
	};

	void setElementPosition(int element, eRect where);
	void setElementFont(int element, gFont *font);
	void setPixmap(int type, ePtr<gPixmap> &pic);

	void sort();

	int setCurrentMarked(bool);

	int getItemHeight() { return m_itemheight; }
	void setItemHeight(int height);
	void setHideNumberMarker(bool doHide) { m_hide_number_marker = doHide; m_visible_prefix_valid = false; }
	void setServiceTypeIconMode(int mode) { m_servicetype_icon_mode = mode; }
	void setCryptoIconMode(int mode) { m_crypto_icon_mode = mode; }
	void setRecordIndicatorMode(int mode) { m_record_indicator_mode = mode; }
	void setColumnWidth(int value) { m_column_width = value; }
	void setProgressbarHeight(int value) {	m_progressbar_height = value; }
	void setProgressbarBorderWidth(int value) { m_progressbar_border_width = value; }
	void setNonplayableMargins(int value) { m_nonplayable_margins = value; }
	void setItemsDistances(int value) { m_items_distances = value; }
	void setPiconMargin(int value) { m_picon_margin = value; }
	void setSidesMargin(int value) { m_sides_margin = value; }
	void setMarkerAsLine(int value) { m_marker_as_line = value; }
	void setChannelNumbersVisible(bool visible) { m_chanel_number_visible = visible; }
	void setAlternativeNumberingMode(bool b) { m_alternative_numbering = b; }
	void setProgressBarMode(std::string s) { m_progress_mode = s; }
	void setAlternativeRecordMatching(bool b) { m_alternative_record_match = b; }
	void setHasNextEvent(bool b) { m_has_next_event = b; }

	void setNextTitle(const std::string &string) { m_next_title = string; }
	void setTextTime(const std::string &string) { m_text_time = string; }
	void setTextSeparator(const std::string &string) { m_separator = string; }
	// leading blanks are dropped, the items distance already separates the event title from the service name
	void setServiceEventSeparator(const std::string &string) {
		size_t pos = string.find_first_not_of(" \t");
		m_service_event_separator = pos == std::string::npos ? string : string.substr(pos);
	}
	void setMarkerTextAlignment(const std::string &string) { m_marker_alignment = string; } // currently supports left and center
	void setMarkerLineColor(const gRGB &col) {
		m_markerline_color = col;
		m_markerline_color_set = 1;
	}

	static void setGetPiconNameFunc(SWIG_PYOBJECT(ePyObject) func);
	// Drop the cached picons of all service lists (picon source, path or lookup priority changed), re-resolved on the next paint.
	static void invalidatePiconCaches();

	enum {
		markedForeground,
		markedForegroundSelected,
		markedBackground,
		markedBackgroundSelected,
		serviceNotAvail,
		eventForeground,
		eventForegroundSelected,
		eventborderForeground,
		eventborderForegroundSelected,
		eventForegroundFallback,
		eventForegroundSelectedFallback,
		eventNextForeground,
		eventNextForegroundSelected,
		eventNextForegroundFallback,
		eventNextForegroundSelectedFallback,
		serviceItemFallback,
		serviceSelectedFallback,
		serviceEventProgressbarColor,
		serviceEventProgressbarColorSelected,
		serviceEventProgressbarBorderColor,
		serviceEventProgressbarBorderColorSelected,
		serviceRecorded,
		eventRemainingForeground,
		eventRemainingForegroundSelected,
		eventRemainingForegroundFallback,
		eventRemainingForegroundSelectedFallback,
		colorElements
	};

	void setColor(int color, gRGB &col);
	bool checkServiceIsRecorded(eServiceReference ref);
protected:
	void cursorHome();
	void cursorEnd();
	int cursorMove(int count=1);
	int cursorValid();
	int cursorSet(int n);
	int cursorResolve(int);
	int cursorGet();
	int currentCursorSelectable();

	void cursorSave();
	void cursorRestore();
	int size();

	// void setOutputDevice ? (for allocating colors, ...) .. requires some work, though
	void setSize(const eSize &size);

		/* zoomed entry (templated renderer): percent, and the corner radius of its background grows with it */
	int m_zoom = 100;
	int zoomedRadius(int r) const { return m_zoom == 100 ? r : (r * m_zoom + 50) / 100; }

		/* shared row decoration, used by the legacy and the templated renderer */
	int getMarkedState(int selected);
	void applyBaseColors(gPainter &painter, eWindowStyle &style, int selected, int marked);
	void paintBackground(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected, int marked);
	void paintSelection(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected, bool large);

		/* the following functions always refer to the selected item */
	void paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected);

	// paint() re-resolves and reloads every visible row's picon on every
	// repaint (e.g. once per scrolled step, for every row still on screen,
	// not just the one that changed) - the Python getPiconName() round-trip
	// and loadImage() lookup are both redone even for rows whose service
	// hasn't changed since the last paint. This cache makes that a single
	// lookup by service reference after the first paint of a given row.
	//
	// An entry is not valid forever: it remembers the file it came from and is re-checked (stat) every few seconds, so a
	// replaced picon shows up without a restart; a service without picon is looked up again after a while (a picon may
	// have been added); and invalidatePiconCaches() drops all of them at once (picon source / lookup priority changed).
	struct PiconCacheEntry {
		PiconCacheEntry(): isSVG(false), fileSize(0), fileTime(0), fileCTime(0), checkedMs(0), preloadedMs(0) {}
		ePtr<gPixmap> pixmap;
		bool isSVG;
		std::string file;      // "" = no picon found
		off_t fileSize;
		time_t fileTime;
		time_t fileCTime;      // a copy or extract that keeps the old mtime still changes this
		long long checkedMs;  // last time the file was verified (or the lookup was made)
		long long preloadedMs; // last time a GPU texture preload was queued for the pixmap
	};
	std::map<eServiceReference, PiconCacheEntry> m_picon_cache;
	size_t m_picon_cache_limit = 400; // entries kept before trimWarmCaches() drops the ones far from the cursor
	int m_picon_gen = 0;
	bool m_picon_downscale = false; // PNG picons are decoded down to twice the cell width (set by the template list)
	static long long nowMs();
	static void statPiconEntry(PiconCacheEntry &entry); // fills fileSize/fileTime/checkedMs from entry.file
	bool syncPiconGeneration(); // drops m_picon_cache after invalidatePiconCaches(); true if it did
	void getPiconPixmap(const eServiceReference &ref, int width, ePtr<gPixmap> &pixmap, bool &isSVG);
	std::string getPiconFilename(const eServiceReference &ref); // "" when there is none
	void loadPiconPixmap(const eServiceReference &ref, int width, PiconCacheEntry &entry); // uncached
	// EGL: textures are created lazily by the first draw of a pixmap, i.e. in the middle of a paint. For the picons of
	// the rows about to scroll in, have the render thread create them ahead of time (cheap to queue, a few per tick).
	bool piconNeedsTexture(const eServiceReference &ref);
	bool preloadPiconTexture(const eServiceReference &ref);
	int warmAheadRows(); // rows scanned each way by the idle warm-up: a few pages, never the whole list
	bool trimWarmCaches(); // drop picon / event cache entries far from the cursor, a few per call; true if more remain
	int textureAheadRows(); // how many rows beyond the cursor get their texture preloaded (about two pages)

	// Same story as the picon cache above, for the per-row "now"/"next" event
	// lookup (service_info->getEvent()): every repaint re-queries and
	// re-parses the EPG event for every visible row, even though the result
	// can only actually change when the "now" event ends. Cached per service
	// reference and revalidated against the cached event's own begin/end
	// time (not a fixed poll interval) - a repaint mid-event is a pure map
	// lookup, and the moment the cached event's end time is reached, the
	// next repaint naturally re-queries and picks up the new one.
	struct EventCacheEntry {
		bool hasEvent;
		ePtr<eServiceEvent> evt;
		ePtr<eServiceEvent> evt_next;
		time_t validUntil;
	};
	std::map<eServiceReference, EventCacheEntry> m_event_cache;
	bool getCachedEvent(const eServiceReference &ref, iStaticServiceInformation *service_info, time_t now, ePtr<eServiceEvent> &evt, ePtr<eServiceEvent> &evt_next);
	// Fill the event cache of the rows around the cursor (the cursor row and the visible page included) with one
	// batched EPG lookup instead of two lock round-trips per row. Rows that had no event and now have one are appended
	// to *gotLate (the template list rebuilds those). Only plain DVB services are batched, the rest keeps the per-row path.
	void warmEventsBatch(int ahead, std::vector<eServiceReference> *gotLate);

	// Idle-time warm-up of the picon / event caches around the cursor (legacy renderer): on a fresh list (restart,
	// skin change) every row of the first scrolled pages otherwise pays the cold picon read + EPG lookup in paint().
	// prefix[i] = number of visible rows among the first i entries of m_list, see cursorResolve()
	std::vector<int> m_visible_prefix;
	bool m_visible_prefix_valid = false;
	// iterator of every list entry, parallel to m_visible_prefix: cursorSet() (called for every painted row) was a walk from the
	// list start, so painting got slower the further down a long list the cursor was
	std::vector<std::list<eServiceReference>::iterator> m_iter_index;
	void invalidateVisibleCache() { m_visible_prefix_valid = false; }
	void buildVisiblePrefix();
	bool isHiddenEntry(const eServiceReference &ref) const;
	std::shared_ptr<void> m_warm;
	void warmKick();
	virtual void kickWarmup() { warmKick(); }
	// hooks of warmTick(): whether the rows have a picon, its width, and a repaint when an event turned up late
	virtual bool warmUsesPicons() { return m_visual_mode != visModeSimple; }
	virtual int warmPiconWidth() { return m_visual_mode == visSkinDefined ? (int)(m_itemheight * 1.67) : 125; }
	virtual void warmEventArrived(const eServiceReference &) {}
	// build the renderer's own per-row data around the cursor (idle time, within budgetMs); true if more is left
	virtual bool warmRows(int ahead, int dir, double budgetMs) { return false; }
	long long m_warm_kick_ms = 0; // last time a selected row was painted / the warm-up was asked for
	// Whole-list warm-up (set by the template list): while nobody scrolls, events / picons / rows of the entire list are prepared,
	// nearest to the cursor first, up to the cache limits. After a restart or skin change every cache is empty and the first pages
	// scrolled otherwise pay for all of it themselves.
	bool m_warm_whole_list = false;
	bool m_warm_complete = false;
	int m_no_event_retry_s = 5; // how long a service without an event is believed to have none before it is looked up again
	int m_event_retries = 0; // slow re-checks of services that had no event yet (EPG still loading)
	size_t m_event_cache_limit = 800;
	size_t m_warm_sig_size = 0;
	int m_warm_sig_gen = -1;
	eServiceReference m_warm_sig_front, m_warm_sig_back;
	int m_warm_last_cursor = -1, m_warm_dir = 0; // direction of the last cursor move: 1 down, -1 up, 0 unknown
public:
	void warmTick();
protected:

	int m_visual_mode;
		/* for complex mode */
	eRect m_element_position[celElements];
	ePtr<gFont> m_element_font[celElements];
	ePtr<gPixmap> m_pixmaps[picElements];
	gRGB m_color[colorElements];
	bool m_color_set[colorElements];
protected:
	typedef std::list<eServiceReference> list;

	list m_list;
	list::iterator m_cursor, m_saved_cursor;

	int m_cursor_number, m_saved_cursor_number;
	int m_size, m_size_visible;

	eSize m_itemsize;
	ePtr<iServiceHandler> m_service_center;
	ePtr<iListableService> m_lst;

	eServiceReference m_root;

		/* support for marked services */
	std::set<eServiceReference> m_marked;
	std::set<eServiceReference>::const_iterator m_marked_iterator;

		/* support for movemode */
	bool m_current_marked;
	void swapServices(list::iterator, list::iterator);

	eServiceReference m_is_playable_ignore;

	int m_itemheight;
	bool m_hide_number_marker;
	bool m_chanel_number_visible;
	bool m_alternative_numbering;
	int m_servicetype_icon_mode;
	int m_crypto_icon_mode;
	int m_record_indicator_mode;
	int m_column_width;
	int m_progressbar_height;
	int m_progressbar_border_width;
	int m_nonplayable_margins;
	int m_items_distances;
	int m_picon_margin;
	int m_sides_margin;
	int m_marker_as_line;
	gRGB m_markerline_color;
	int m_markerline_color_set;
	bool m_alternative_record_match;
	bool m_has_next_event;

	std::string m_text_time;
	std::string m_next_title;
	std::string m_separator;
	std::string m_service_event_separator;
	std::string m_marker_alignment;
	std::string m_progress_mode;
};

#endif
