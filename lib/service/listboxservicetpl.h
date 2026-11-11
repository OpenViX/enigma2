#ifndef __lib_service_listboxservicetpl_h
#define __lib_service_listboxservicetpl_h

#include <lib/service/listboxservice.h>
#include <vector>
#include <map>
#include <set>
#include <string>
#include <memory>

/*
 * Service list whose row design comes from skin defined templates.
 * See doc/SERVICELIST_TEMPLATES.md. The data model (cursor, marks, sort, movemode ...)
 * is inherited from eListboxServiceContent, only layout and painting differ.
 */
class eListboxServiceTemplateContent: public eListboxServiceContent
{
	DECLARE_REF(eListboxServiceTemplateContent);
public:
	eListboxServiceTemplateContent();

	enum {
		fontGroupName,
		fontGroupNumber,
		fontGroupInfo,
		fontGroupNext,
		fontGroupRemaining,
		fontGroupCustom1,
		fontGroupCustom2,
		fontGroupCustom3,
		fontGroups
	};

	void clearTemplates();
	// dict: name + colour entries (see doc), returns style index
	int setStyle(SWIG_PYOBJECT(ePyObject) dict);
	// dict describing a template (rows/items), returns template index or -1
	int addTemplate(SWIG_PYOBJECT(ePyObject) dict);
	bool setTemplate(const std::string &name);
	int getTemplateItemHeight(const std::string &name);
	int getTemplateRows(const std::string &name);
	// vertical list (1), horizontal list (0) or grid (2), see eListbox::orXXX, and the cell width for the latter two
	int getTemplateOrientation(const std::string &name);
	int getTemplateItemWidth(const std::string &name);
	std::string getTemplateName() { return m_current; }

	// config derived conditions, usable as visible="cfg.<name>" in a template
	void setFlag(const std::string &name, bool on);
	void setFontDelta(int group, int delta);
	// numeric runtime parameter, usable as width="@<name>" in a template
	void setParam(const std::string &name, int value);
	void invalidateRows();

#ifndef SWIG
protected:
	void setSize(const eSize &size);
	void setZoom(int percent) { m_zoom = percent > 0 ? percent : 100; }
	bool gridSpanList(std::vector<char> &out);
	bool entryHeightList(std::vector<int> &out);
	void setSpanWidth(int width);
	int gridSpanHeight();
	void paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected);
	int getItemWidth();
	int getOrientation();

private:
	// ePtr can not be copy assigned from a const object (its operator= takes a non-const
	// reference), which std::vector of the structs below requires.
	template<class T> struct Ref
	{
		ePtr<T> p;
		Ref() {}
		Ref(const Ref &o): p(o.p) {}
		Ref &operator=(const Ref &o) { p = (T*)o.p; return *this; }
		Ref &operator=(T *c) { p = c; return *this; }
		operator T*() const { return p; }
		T *operator->() const { return p; }
	};

	enum {
		sPlayable, sMarker, sDirectory, sGroup, sStream, sEvent, sNextEvent, sCrypted,
		sRecorded, sFallback, sUnavail, sCatchup, sBackup, sSD, sHD, sUHD, sHasNumber, sHasPicon,
		sBuiltin,
		sCfgBase = 32
	};
	enum { itText, itPicon, itServiceType, itCrypto, itRecord, itResolution, itBackup, itCatchup,
		itKind, itProgress, itLine, itRect, itSpacer, itPixmap };
	enum { tokLiteral, tokNumber, tokName, tokEvent, tokNext, tokRemaining, tokPercent, tokStart, tokEnd, tokDuration };
	enum { wFixed, wAuto, wFlex, wParam };
	enum { cFg, cFgSel, cFgFallback, cFgSelFallback, cNotAvail, cRecorded, cMarked, cMarkedSel, cBorder, cBorderSel, cCount };
	enum { rowService, rowMarker, rowDirectory };
	enum { opText, opBlit, opBlitScale, opBlitSVG, opFill, opProgress, opRect };
	enum { dynRecorded = 1, dynFallback = 2, dynUnavail = 4 };

	struct Style {
		std::string name;
		gRGB c[cCount];
		bool set[cCount];
	};
	struct Token {
		int kind;
		std::string lit;
	};
	struct Item {
		int type;
		uint64_t req, forbid;
		std::string param;
		int wmode, width, weight, minw, height, margin, lineH;
		int align, valign; // align: -1 unset, 0 left, 1 center, 2 right; valign: 0 top, 1 center, 2 bottom
		bool absolute;
		eRect absRect;
		std::vector<Token> tokens;
		std::string family;
		int fontSize, fontGroup;
		Ref<gFont> font;
		int style;
		bool ellipsis, reserve, keepAspect;
		int border;
		// rect: own colours (fill / border, normal and selected) and rounded corners; any item: draw order
		bool colSet[2], bcolSet[2];
		gRGB col[2], bcol[2];
		int radius, edges, z;
		// pixmap: static image (skin path) and an optional variant for the selected row
		std::string src, srcSel;
		bool isSvg;
		Ref<gPixmap> pix, pixSel;
		// member of a <stack> of its row (index into Row::stacks, -1: plain row item), placed like an eStack child:
		// stackAlign 0 start (left/top), 1 end (right/bottom), 2 centre; stackCross -1 item's own, 0/1/2 start/centre/end
		// across the stack; stackFill takes the space the other members leave over
		int stackId, stackAlign, stackCross;
		bool stackFill;
	};
	// a group of items laid out along one axis inside a box (the row's content area, or an absolute rect)
	struct Stack {
		bool horizontal;
		int spacing;
		bool absolute;
		eRect rect;
		uint64_t req, forbid;
	};
	struct Row {
		int kind, height, weight, gap, padLeft, padRight, padTop, padBottom;
		int align; // alignment of the whole flow when it does not fill the row: 0 left, 1 center, 2 right
		uint64_t req, forbid; // row is skipped unless these conditions hold
		std::vector<Item> items;
		std::vector<Stack> stacks;
	};
	struct Template {
		std::string name;
		int itemHeight, itemWidth, orientation;
		bool large;
		bool usesNext, timeDependent, usesPicon;
		bool spanMarkers; // grid: a marker is a row of its own, as wide as the whole grid
		int markerHeight; // ...and this high (0: like a cell)
		uint64_t usedBits; // every state/config bit the template tests, expensive ones are only computed when used
		std::vector<Row> rows;
	};
	struct Op {
		int kind;
		int style;
		eRect rect;
		int flags;
		int border;
		time_t begin;
		int duration;
		Ref<eTextPara> para;
		Ref<gPixmap> pixmap, pixmapSel;
		int z, radius, edges;
		bool colSet[2], bcolSet[2];
		gRGB col[2], bcol[2];
	};
	struct RowCache {
		unsigned int gen;
		int dyn;
		int width;
		time_t validUntil;
		int dynState;
		std::vector<Op> ops;
	};

	std::vector<Style> m_styles;
	std::vector<Template> m_templates;
	std::map<std::string, int> m_flag_bits;
	std::map<std::string, int> m_params;
	std::string m_current;
	int m_cur_index;
	int m_span_width; // width of a full row (marker) entry of a grid, 0 until the listbox told us
	uint64_t m_flags;
	int m_font_delta[fontGroups];
	unsigned int m_gen;
	std::map<eServiceReference, RowCache> m_rows;

	// zoomed entry (carousel centre / selection zoom): the whole template, geometry and fonts, scaled by m_zoom percent
	Template m_zoom_tpl;
	int m_zoom_tpl_idx = -1, m_zoom_tpl_zoom = 100;
	unsigned int m_zoom_tpl_gen = 0;
	std::map<eServiceReference, RowCache> m_zoom_rows;
	void prepareZoomTemplate();

	std::set<eServiceReference> m_rec_refs;
	time_t m_rec_time;

	// SVG picon read-ahead: while scrolling, the SVG picons of the rows beyond the visible page (in the direction of travel)
	// are rasterised on a worker thread and filed in m_picon_cache (SVGs only; PNG picons are not cached).
	friend struct TplPrefetch;
	std::shared_ptr<void> m_prefetch;
	int m_prefetch_last, m_prefetch_dir;
	void prefetchKick();
	void prefetchTick();
	void picon(const eServiceReference &ref, int width, ePtr<gPixmap> &pixmap, bool &isSVG);

	int styleIndex(const std::string &name);
	bool parseCondition(const std::string &cond, uint64_t &req, uint64_t &forbid);
	void parseTokens(const std::string &text, std::vector<Token> &out);
	void rebuildFonts();
	void loadPixmaps(Template &t);
	bool isRecordedCached(const eServiceReference &ref, time_t now);
	bool resolveColor(const Style &st, int selected, int marked, int dyn, bool border, gRGB &out) const;
	void buildRow(const Template &tpl, const eServiceReference &ref, iStaticServiceInformation *info, int dyn, time_t now, RowCache &out);
	std::string tokenText(int kind, const eServiceReference &ref, const std::string &name, eServiceEvent *evt, eServiceEvent *next, time_t now);
	void paintOps(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected, int marked, const RowCache &rc, time_t now);
#endif
};

#endif
