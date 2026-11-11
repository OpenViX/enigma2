#ifndef __lib_listbox_h
#define __lib_listbox_h

#include <lib/gui/ewidget.h>
#include <connection.h>
#include <algorithm>
#include <vector>

class eListbox;
class eSlider;

class iListboxContent: public iObject
{
public:
	virtual ~iListboxContent()=0;

		/* indices go from 0 to size().
		   the end is reached when the cursor is on size(),
		   i.e. one after the last entry (this mimics
		   stl behavior)

		   cursors never invalidate - they can become invalid
		   when stuff is removed. Cursors will always try
		   to stay on the same data, however when the current
		   item is removed, this won't work. you'll be notified
		   anyway. */
#ifndef SWIG
protected:
	iListboxContent();
	friend class eListbox;
	virtual void updateClip(gRegion &){ };
	virtual void resetClip(){ };
	virtual void cursorHome()=0;
	virtual void cursorEnd()=0;
	virtual int cursorMove(int count=1)=0;
	virtual int cursorValid()=0;
	virtual int cursorSet(int n)=0;
	virtual int cursorGet()=0;

	virtual void cursorSave()=0;
	virtual void cursorRestore()=0;

	virtual int size()=0;

	virtual int currentCursorSelectable();

	void setListbox(eListbox *lb);

	// void setOutputDevice ? (for allocating colors, ...) .. requires some work, though
	virtual void setSize(const eSize &size)=0;
		/* the cell size last given to setSize(); an invalid (empty) size means "unknown" (carousel zoom is skipped) */
	virtual eSize getItemSize() { return eSize(); }
		/* scale the painted item content (positions, sizes, fonts) by percent; only set around a single paint() of
		   an enlarged entry. Contents that cannot scale ignore it and just get the larger cell. */
	virtual void setZoom(int percent) { (void)percent; }
	// zoomed paint of a content whose cell was cut down to the enlarged content: the top left of the cell in the
	// coordinates of the zoomed content (the x/y of the items are shifted by it)
	virtual void setZoomOrigin(int x, int y) { (void)x; (void)y; }
		/* bounding box of what the current entry actually draws, relative to its cell and at 100% (an invalid rect if
		   unknown). The zoom grows the entry around the centre of this box, not around the cell centre. */
	virtual eRect getContentBounds() { return eRect(); }

		/* the following functions always refer to the selected item */
	virtual void paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)=0;

	virtual int getItemHeight()=0;
	virtual int getItemWidth() { return -1; }
	virtual int getOrientation() { return 1; }
	virtual int getMaxItemTextWidth() { return 1; }
	virtual int getListSize() { return 0; }

		/* grid layout: entries that take a whole row of the grid on their own (e.g. markers). Fills one flag per
		   entry and returns true when at least one entry spans; the default is a plain grid. */
	virtual bool gridSpanList(std::vector<char> &) { return false; }
		/* the width of such a full row entry, set by the listbox whenever its size changes */
	virtual void setSpanWidth(int) { }
		/* ...and its height, 0 for the height of a normal cell */
	virtual int gridSpanHeight() { return 0; }

		/* vertical lists: the height of every entry, 0 for the normal item height (headers, markers). Returns true
		   when at least one entry differs; the listbox then lays out, scrolls and pages by the real heights. */
	virtual bool entryHeightList(std::vector<int> &) { return false; }

	eListbox *m_listbox;
	// ellipsis for text that does not fit its box, can be disabled per listbox from the skin
	bool ellipsisEnabled();
#endif
};

#ifndef SWIG
struct eListboxStyle
{
	ePtr<gPixmap> m_background, m_selection, m_selection_large;
	int m_transparent_background;
	int m_border_set;
	gRGB m_background_color, m_background_color_selected, m_foreground_color, m_foreground_color_selected, m_border_color;
	int m_background_color_set, m_foreground_color_set, m_background_color_selected_set, m_foreground_color_selected_set;
	gRGB m_scrollbarborder_color, m_scrollbarforeground_color, m_scrollbarbackground_color;
	int m_scrollbarforeground_color_set, m_scrollbarbackground_color_set, m_scrollbarborder_color_set, m_scrollbarborder_width_set;
		/*
			{m_transparent_background m_background_color_set m_background}
			{0 0 0} use global background color
			{0 1 x} use background color
			{0 0 p} use background picture
			{1 x 0} use transparent background
			{1 x p} use transparent background picture
		*/

	enum
	{
		alignLeft,
		alignTop=alignLeft,
		alignCenter,
		alignRight,
		alignBottom=alignRight,
		alignBlock
	};
	int m_valign, m_halign, m_border_size, m_scrollbarborder_width;
	ePtr<gFont> m_font, m_secondfont;
	ePoint m_text_offset;
	int m_itemCornerRadius[2];
	int m_itemCornerRadiusEdges[2];
	int cornerRadius(int mode)
	{
		return m_itemCornerRadius[mode];
	}
	int cornerRadiusEdges(int mode)
	{
		return m_itemCornerRadiusEdges[mode];
	}
	bool m_gradient_set[4], m_gradient_alphablend[4];
	uint8_t m_gradient_direction[4];
	std::vector<gRGB> m_gradient_colors[4];

		/* header entries (non selectable section titles), styled from the skin independent of the normal items.
		   Everything not set falls back to the normal item style. */
	ePtr<gFont> m_header_font;
	gRGB m_header_foreground_color, m_header_background_color, m_header_line_color;
	int m_header_foreground_color_set, m_header_background_color_set, m_header_line_color_set;
	int m_header_height; // 0: the normal item height
	int m_header_line_thickness;
	int m_header_line_style, m_header_line_margin; // eListbox::headerLine*, gap between the title and a split line
	int m_header_halign, m_header_valign;
	ePoint m_header_text_offset;
	int m_header_text_offset_set;
};
#endif

class eListbox: public eWidget
{
	void updateScrollBar();
public: 
	eListbox(eWidget *parent);
	~eListbox();

	PSignal0<void> selectionChanged;

	enum {
		showOnDemand,
		showAlways,
		showNever,
		showLeft,
		showTop
	};
	void setScrollbarMode(int mode);
	void setWrapAround(bool);
		/* carousel: the selection stays locked on the centre slot and the entries scroll past it (horizontal or
		   vertical lists). With wrap-around enabled the entries also wrap visually around the list ends. */
	void setCarousel(bool);
	bool getCarousel() { return m_carousel; }
		/* how the list scrolls when the selection leaves the visible part: scrollByPage (default) jumps to the page
		   that holds the selection, scrollByItem moves only as far as needed to keep the selection visible. For
		   every orientation; with variable row heights a page is as many rows as fit. Carousel mode ignores it. */
	enum { scrollByPage, scrollByItem };
	void setScrollType(int type);
	int getScrollType() { return m_scroll_type; }
		/* size of the centre slot in percent (100 = no zoom, default 112). Grows along the scroll axis only. */
	void setCarouselZoom(int percent);
		/* size of the selected entry in percent for horizontal and grid lists (100 = off, default). Overlaps the
		   neighbours; a horizontal list only grows along its scroll axis. Not used in carousel mode (carouselZoom). */
	void setSelectionZoom(int percent);
	enum { orHorizontal, orVertical, orGrid };
	void setOrientation(int orientation);

	/* text alignment for setVAlign/setHAlign; the same values as eListboxStyle::align*, which is hidden from SWIG, so
	   the skin (AttributeParser.valign/halign) can reach them as eListbox.alignCenter etc. */
	enum
	{
		alignLeft,
		alignTop = alignLeft,
		alignCenter,
		alignRight,
		alignBottom = alignRight,
		alignBlock
	};

	void setContent(iListboxContent *content);

	void allowNativeKeys(bool allow);

/*	enum Movement {
		moveUp,
		moveDown,
		moveTop,
		moveEnd,
		justCheck
	}; */

	int getCurrentIndex();
	int getOrientation();
		/* pages of the list as the user pages through it; for a grid with rows of different heights (spanning
		   entries) a page is as many rows as fit. For the pager widget. */
	int getPageCount();
	int getCurrentPage();
	void moveSelection(long how);
	void moveSelectionTo(int index);
	void moveToEnd();
	bool atBegin();
	bool atEnd();

	enum ListboxActions {
		moveUp,
		moveDown,
		moveTop,
		moveEnd,
		pageUp,
		pageDown,
		justCheck,
		moveStartTop,
		moveStart,
		prevItemPage,
		prevPageItem,
		prevItem,
		nextItemPage,
		nextPageItem,
		nextItem,
		prevPage,
		nextPage
	};

	void setItemHeight(int h);
	void setItemWidth(int w);
	void setSelectionEnable(int en);
	void setEllipsis(int en);
	bool getEllipsis() const { return m_ellipsis; }

	void setBackgroundColor(const gRGB &col);
	void setBackgroundColorSelected(gRGB &col);
	void setForegroundColor(gRGB &col);
	void setForegroundColorSelected(gRGB &col);
	void setBorderColor(const gRGB &col);
	void setBorderWidth(int size);
	void setBackgroundPicture(ePtr<gPixmap> &pixmap);
	void setSelectionPicture(ePtr<gPixmap> &pixmap);
	void setSelectionPictureLarge(ePtr<gPixmap> &pixmap);
	void setSelectionBorderHidden();

	void setFont(gFont *font);
	void setSecondFont(gFont *font);
	void setVAlign(int align);
	void setHAlign(int align);
	void setTextOffset(const ePoint &textoffset);

	void setScrollbarWidth(int width);
	void setScrollbarHeight(int size);
	void setScrollbarBorderWidth(int width);
	void setScrollbarBorderColor(const gRGB &col);
	void setScrollbarForegroundColor(const gRGB &col);
	void setScrollbarBackgroundColor(const gRGB &col);
	void setScrollbarPixmap(ePtr<gPixmap> &pm);
	void setScrollbarBackgroundPixmap(ePtr<gPixmap> &pm);

	int getScrollbarWidth() { return m_scrollbar_width; }
	int getScrollbarHeight() { return m_scrollbar_height; }
	int getMaxItemTextWidth() { return m_content->getMaxItemTextWidth(); }

	void setItemCornerRadius(int radius, uint8_t edges);
	void setItemCornerRadiusSelected(int radius, uint8_t edges);

	static void setDefaultItemRadius(int radius, int radiusEdges)
	{
		defaultItemRadius[0] = radius;
		defaultItemRadiusEdges[0] = radiusEdges;
	}
	static void setDefaultItemRadiusSelected(int radius, int radiusEdges)
	{
		defaultItemRadius[1] = radius;
		defaultItemRadiusEdges[1] = radiusEdges;
	}
	void setItemGradient(const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend);
	void setItemGradientSelected(const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend);
	void redrawItemByIndex(int index) { entryChanged(index); }

		/* style of header entries (see Components/ListHeader.py, config HEADER); set from the skin by the
		   header* widget attributes */
	void setHeaderFont(gFont *font);
	void setHeaderForegroundColor(const gRGB &col);
	void setHeaderBackgroundColor(const gRGB &col);
	void setHeaderLineColor(const gRGB &col);
	void setHeaderLineThickness(int thickness);
		/* where the line of a header entry goes: under the title (default), above it, on both free sides of the
		   title (like a marker of the service list, title aligned by headerHalign) or none at all */
	enum { headerLineBottom, headerLineTop, headerLineSplit, headerLineNone };
	void setHeaderLineStyle(int style);
	void setHeaderLineMargin(int margin);
	void setHeaderHeight(int height);
	void setHeaderVAlign(int align);
	void setHeaderHAlign(int align);
	void setHeaderTextOffset(const ePoint &textoffset);

#ifndef SWIG
	struct eListboxStyle *getLocalStyle(void);

		/* entryAdded: an entry was added *before* the given index. it's index is the given number. */
	void entryAdded(int index);
		/* entryRemoved: an entry with the given index was removed. */
	void entryRemoved(int index);
		/* entryChanged: the entry with the given index was changed and should be redrawn. */
	void entryChanged(int index);
		/* the complete list changed. you should not attemp to keep the current index. */
	void entryReset(bool cursorHome=true);

	int getEntryTop();
	void invalidate(const gRegion &region = gRegion::invalidRegion());
protected:
	int event(int event, void *data=0, void *data2=0);
	void recalcSize();
	ePoint getItemPostion(int index);

private:
	/* grid rows. A row is a contiguous range of entries; without spanning entries every row has m_max_columns
	   of them (the last one fewer), a spanning entry (marker) is a row of its own. */
	void gridUpdate();
		/* vertical list with entries of different heights (headers, markers): the rows are the entries */
	eRect verticalRect(int index);
		/* ...which scroll entry by entry: the first entry to show so that `index` is fully visible, the number of
		   entries that fit from a first one */
	int verticalTopFor(int index);
	int verticalVisible(int top);
	bool gridHasSpans() { gridUpdate(); return m_grid_spans; }
	int gridRows();
	int gridRowOf(int index);
	int gridRowFirst(int row);
	int gridRowCount(int row);
	int gridColOf(int index) { return index - gridRowFirst(gridRowOf(index)); }
	int gridRowHeight(int row);
	int gridRowTop(int row);
	int gridPageCount();
	int gridPageOfRow(int row);
	int gridPageStartRow(int page);
	bool gridSpanAt(int index);
	eSize gridItemSize(int index);
	bool m_grid_dirty, m_grid_spans;
	std::vector<int> m_grid_first, m_grid_rowof;
	std::vector<char> m_grid_spanflag;
	int m_grid_spanheight;
	std::vector<int> m_grid_ytop, m_grid_pagefirst;
	int m_scrollbar_mode, m_prev_scrollbar_page;
	bool m_content_changed;
	bool m_enabled_wrap_around;
	bool m_carousel = false;
	int m_carousel_zoom = 112;
	int m_scroll_type = 0; // scrollByPage
	int itemScrollStart(int sel, int cur, int visible, int total) const;
	int gridRowTopFor(int row);
	int m_selection_zoom = 100;
	bool selectionZoomActive() const { return m_selection_zoom > 100 && m_selection_enabled && (m_orientation == orHorizontal || m_orientation == orGrid) && m_content && m_content->getItemSize().width() > 0; }
	void paintZoomed(gPainter &painter, eWindowStyle &style, int index, ePoint pos, int percent);
	void paintZoomedSelection(gPainter &painter, eWindowStyle &style, int index, ePoint pos, bool bothAxes);
	bool carouselActive() const { return m_carousel && (m_orientation == orHorizontal || m_orientation == orVertical); }
	int carouselCenter() const { return m_items_per_page / 2; }

	int m_scrollbar_width;
	int m_scrollbar_height;
	int m_top, m_left, m_max_columns, m_max_rows, m_selected;
	int m_itemheight;
	int m_itemwidth;
	int m_orientation;
	int m_items_per_page;
	int m_items_per_page_with_partials;
	int m_selection_enabled;
	bool m_ellipsis;
	void setItemCornerRadiusInternal(int radius, uint8_t edges, int index);
	void setItemGradientInternal(uint8_t index, const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend);

	bool m_native_keys_bound;

	ePtr<iListboxContent> m_content;
	eSlider *m_scrollbar;
	eListboxStyle m_style;
	ePtr<gPixmap> m_scrollbarpixmap, m_scrollbarbackgroundpixmap;
	static int defaultItemRadius[2];
	static int defaultItemRadiusEdges[2];
#endif
};

#endif
