#include <lib/gui/elistbox.h>
#include <lib/gui/elistboxcontent.h>
#include <lib/gui/eslider.h>
#include <lib/actions/action.h>

int eListbox::defaultItemRadius[2] = {0,0}; 
int eListbox::defaultItemRadiusEdges[2] = {0,0};

eListbox::eListbox(eWidget *parent) :
	eWidget(parent), m_scrollbar_mode(showNever), m_prev_scrollbar_page(-1),
	m_content_changed(false), m_enabled_wrap_around(false), m_scrollbar_width(10), m_scrollbar_height(10),
	m_top(0), m_left(0), m_max_columns(0), m_max_rows(0), m_selected(0), m_itemheight(25), m_itemwidth(25), m_orientation(orVertical),
	m_items_per_page(0), m_items_per_page_with_partials(0), m_selection_enabled(1), m_ellipsis(true), m_native_keys_bound(false), m_scrollbar(nullptr),
	m_grid_dirty(true), m_grid_spans(false), m_grid_spanheight(0)
{
	memset(static_cast<void*>(&m_style), 0, sizeof(m_style));
	m_style.m_text_offset = ePoint(1,1);
	m_style.m_header_valign = alignCenter;
	m_style.m_header_halign = alignLeft;
	m_style.m_header_line_thickness = 1;
	m_style.m_header_line_margin = 10;

	for (int x = 0; x < 4; x++) 
	{
		m_style.m_gradient_set[x] = false;
		if (eListbox::defaultItemRadius[x] && eListbox::defaultItemRadiusEdges[x])
			setItemCornerRadiusInternal(eListbox::defaultItemRadius[x], eListbox::defaultItemRadiusEdges[x], x);
		else
			setItemCornerRadiusInternal(0, 0, x);
	}

	allowNativeKeys(true);
}

eListbox::~eListbox()
{
	if (m_scrollbar)
		delete m_scrollbar;

	allowNativeKeys(false);
}

void eListbox::setOrientation(int orientation)
{
	const bool wasVerticalBar = (m_orientation == orVertical || m_orientation == orGrid);
	m_orientation = orientation;
	m_grid_dirty = true;
	const bool verticalBar = (m_orientation == orVertical || m_orientation == orGrid);
	if (m_scrollbar && verticalBar != wasVerticalBar)
		m_scrollbar->setOrientation(verticalBar ? eSlider::orVertical : eSlider::orHorizontal);
}

void eListbox::setScrollbarMode(int mode)
{
	m_scrollbar_mode = mode;

	if (mode == showNever)
	{
		delete m_scrollbar;
		m_scrollbar = nullptr;
		return;
	}

	if (m_scrollbar)
		return;

	m_scrollbar = new eSlider(this);
	m_scrollbar->hide();

	if (m_orientation == orVertical || m_orientation == orGrid)
	{
		m_scrollbar->setOrientation(eSlider::orVertical);
	}
	else
	{
		m_scrollbar->setOrientation(eSlider::orHorizontal);
	}

	m_scrollbar->setRange(0, 100);

	if (m_scrollbarbackgroundpixmap)
		m_scrollbar->setBackgroundPixmap(m_scrollbarbackgroundpixmap);

	if (m_scrollbarpixmap)
		m_scrollbar->setPixmap(m_scrollbarpixmap);

	if (m_style.m_scrollbarforeground_color_set)
		m_scrollbar->setForegroundColor(m_style.m_scrollbarforeground_color);

	if (m_style.m_scrollbarbackground_color_set)
		m_scrollbar->setBackgroundColor(m_style.m_scrollbarbackground_color);

	if (m_style.m_scrollbarborder_width_set)
		m_scrollbar->setBorderWidth(m_style.m_scrollbarborder_width);
	else
		m_scrollbar->setBorderWidth(1);

	if (m_style.m_scrollbarborder_color_set)
		m_scrollbar->setBorderColor(m_style.m_scrollbarborder_color);
}

void eListbox::setWrapAround(bool state)
{
	m_enabled_wrap_around = state;
}

void eListbox::setSelectionZoom(int percent)
{
	m_w_selection_zoom = std::max(100, std::min(percent, 300));
	applyContentSpacing();
}

/* paints entry `index` enlarged by m_selection_zoom, centred on its cell and kept inside the widget. The content is
   given the larger cell size for this one paint and the normal size is restored afterwards. A horizontal list only
   grows along its scroll axis (the cell already is as high as the widget); a grid grows in both directions. */
void eListbox::paintZoomedSelection(gPainter &painter, eWindowStyle &style, int index, ePoint pos, bool bothAxes)
{
	(void)bothAxes; // the whole item is scaled uniformly now (content included), so both axes always grow
	paintZoomed(painter, style, index, pos, m_selection_zoom);
}

/* scales the whole entry (cell, and for contents that support it the positions, sizes and fonts inside it) around
   the centre of its cell, keeps it inside the widget and paints it as selected. It overlaps the neighbours. */
void eListbox::paintZoomed(gPainter &painter, eWindowStyle &style, int index, ePoint pos, int percent)
{
	const eSize cell = m_content->getItemSize();
	eSize zoomed = cell;
	ePoint origin(0, 0);
	bool resized = false;
	m_content->cursorSet(index);
	if (percent > 100 && cell.width() > 0 && cell.height() > 0)
	{
		// The zoom is a maximum: an entry larger than the widget would have its rounded corners (and the bottom of
		// its content) cut off by the widget's edge, so it is reduced until the whole entry fits. Cross axis of a
		// horizontal list, both axes of a grid; a vertical list's rows span the full width by design.
		eRect fit = m_content->getContentBounds();
		if (!fit.valid() || fit.width() <= 0 || fit.height() <= 0)
			fit = eRect(0, 0, cell.width(), cell.height());
		int limit = percent;
		if (m_orientation != orVertical)
			limit = std::min(limit, size().height() * 100 / fit.height());
		if (m_orientation == orGrid)
			limit = std::min(limit, size().width() * 100 / fit.width());
		if (limit < percent)
		{
			static int s_warned = 0;
			if (s_warned != percent)
			{
				s_warned = percent;
				eDebug("[eListbox] zoom %d%% reduced to %d%%: the zoomed entry would not fit the widget (%dx%d), make the widget at least %d px high", percent, std::max(limit, 100), size().width(), size().height(), fit.height() * percent / 100);
			}
			percent = std::max(limit, 100);
		}
	}
	if (percent > 100 && cell.width() > 0 && cell.height() > 0)
	{
		resized = true;
		zoomed = eSize(cell.width() * percent / 100, cell.height() * percent / 100);
		eRect bounds = m_content->getContentBounds();
		if (!bounds.valid() || bounds.width() <= 0 || bounds.height() <= 0)
			bounds = eRect(0, 0, cell.width(), cell.height());
		const int cx = bounds.x() * 2 + bounds.width(), cy = bounds.y() * 2 + bounds.height(); // doubled centre
		// the point (cx/2, cy/2) of the cell stays where it is
		int x = pos.x() + cx * (100 - percent) / 200;
		int y = pos.y() + cy * (100 - percent) / 200;
		// keep the enlarged content (not the whole cell) inside the widget
		const int bw = bounds.width() * percent / 100, bh = bounds.height() * percent / 100;
		const int bx = x + bounds.x() * percent / 100, by = y + bounds.y() * percent / 100;
		int dx = 0, dy = 0;
		if (bx + bw > size().width())
			dx = size().width() - (bx + bw);
		if (bx + dx < 0)
			dx = -bx;
		if (by + bh > size().height())
			dy = size().height() - (by + bh);
		if (by + dy < 0)
			dy = -by;
		// The zoomed "cell" (its rounded background, selection, clip) is exactly the enlarged content: a cell
		// larger than what it draws (margins around a tile) would hang out of the widget and lose its rounded
		// corners. The content keeps its place through the origin.
		origin = ePoint(bounds.x() * percent / 100, bounds.y() * percent / 100);
		zoomed = eSize(bw, bh);
		pos = ePoint(x + dx + origin.x(), y + dy + origin.y());
	}
	if (resized)
	{
		// zoom first, so a content that keeps per-size caches knows the size change is only temporary
		m_content->setZoom(percent);
		m_content->setZoomOrigin(origin.x(), origin.y());
		m_content->setSize(zoomed);
	}
	m_content->paint(painter, style, pos, 1);
	if (resized)
	{
		m_content->setSize(cell);
		m_content->setZoomOrigin(0, 0);
		m_content->setZoom(100);
	}
}

void eListbox::setScrollType(int type)
{
	type = (type == scrollByItem) ? scrollByItem : scrollByPage;
	if (m_scroll_type == type)
		return;
	m_scroll_type = type;
	m_prev_scrollbar_page = -1;
	m_content_changed = true;
	if (m_content)
	{
		moveSelection(justCheck);
		invalidate();
	}
}

/* first visible entry when scrolling item by item: the list only moves as far as needed to show `sel` */
int eListbox::itemScrollStart(int sel, int cur, int visible, int total) const
{
	visible = std::max(1, visible);
	cur = std::max(0, std::min(cur, std::max(0, total - visible))); // the list may have shrunk
	if (sel < cur)
		return sel;
	if (sel >= cur + visible)
		return sel - visible + 1;
	return cur;
}

/* same for the rows of a grid (rows can have different heights) */
int eListbox::gridRowTopFor(int row)
{
	const int rows = gridRows();
	if (rows <= 0)
		return 0;
	row = std::min(std::max(row, 0), rows - 1);
	int top = std::min(std::max(m_top, 0), rows - 1);
	if (row < top)
		return row;
	const int height = size().height();
	while (top < row && gridRowTop(row + 1) - m_gap_y - gridRowTop(top) > height)
		++top;
	return top;
}

void eListbox::setCarouselZoom(int percent)
{
	m_w_carousel_zoom = std::max(100, std::min(percent, 300));
	applyContentSpacing();
}

void eListbox::setCarousel(bool state)
{
	m_w_carousel = state;
	applyContentSpacing();
}

void eListbox::setCarouselCenterSize(int width, int height)
{
	m_w_carousel_cw = std::max(0, width);
	m_w_carousel_ch = std::max(0, height);
	applyContentSpacing();
}

void eListbox::setCarouselFocus(int slot)
{
	m_w_carousel_focus = std::max(-1, slot);
	applyContentSpacing();
}

void eListbox::setItemSpacing(int x, int y)
{
	m_widget_gap_x = std::max(0, x);
	m_widget_gap_y = std::max(0, y);
	applyContentSpacing();
}

/* works out the settings in effect: the ones of the widget (skin), unless the content (a service list template, a
   TemplatedMultiContent style) gives its own. Called whenever one of them or the content changes. */
void eListbox::applyContentSpacing()
{
	int x = -1, y = -1;
	eListboxOverrides ov;
	if (m_content)
	{
		m_content->getItemSpacing(x, y);
		m_content->getListboxOverrides(ov);
	}
	x = x >= 0 ? x : m_widget_gap_x;
	y = y >= 0 ? y : m_widget_gap_y;
	auto pick = [](int over, int widget) { return over != -2 ? over : widget; };
	const bool carousel = pick(ov.carousel, m_w_carousel ? 1 : 0) != 0;
	const int cw = std::max(0, pick(ov.carouselCenterWidth, m_w_carousel_cw));
	const int ch = std::max(0, pick(ov.carouselCenterHeight, m_w_carousel_ch));
	const int focus = std::max(-1, pick(ov.carouselFocus, m_w_carousel_focus));
	const int czoom = std::max(100, std::min(pick(ov.carouselZoom, m_w_carousel_zoom), 300));
	const int szoom = std::max(100, std::min(pick(ov.selectionZoom, m_w_selection_zoom), 300));

	const bool layout = m_gap_x != x || m_gap_y != y || m_carousel != carousel || m_carousel_cw != cw || m_carousel_ch != ch;
	if (!layout && m_carousel_focus == focus && m_carousel_zoom == czoom && m_selection_zoom == szoom)
		return;
	m_gap_x = x;
	m_gap_y = y;
	m_carousel = carousel;
	m_carousel_cw = cw;
	m_carousel_ch = ch;
	m_carousel_focus = focus;
	m_carousel_zoom = czoom;
	m_selection_zoom = szoom;
	m_prev_scrollbar_page = -1;
	if (layout)
		recalcSize(); // the number of tiles depends on the gap and the focus size
	else if (m_content)
		moveSelection(justCheck);
	if (m_content)
		m_content->resetClip();
	invalidate();
}

/* position of a carousel slot along the scroll axis. The focused slot may be larger or smaller than the others, the
   slots after it follow it with the normal gap */
int eListbox::carouselSlotPos(int slot) const
{
	const int step = carouselNormalExtent() + carouselGap();
	const int focus = carouselCenter();
	if (slot <= focus)
		return slot * step;
	return focus * step + carouselFocusExtent() + carouselGap() + (slot - focus - 1) * step;
}

/* cell of the focused slot: the dedicated size, whatever is not given stays as large as the other tiles. The cell never
   gets larger than the widget. */
eSize eListbox::carouselFocusCell(const eSize &base) const
{
	int w = m_carousel_cw > 0 ? m_carousel_cw : base.width();
	int h = m_carousel_ch > 0 ? m_carousel_ch : base.height();
	// along the scroll axis the cell is exactly what the layout reserved, the cross axis must fit the widget
	if (m_orientation == orVertical)
		w = std::min(w, size().width());
	else
		h = std::min(h, size().height());
	return eSize(w, h);
}

/* ---- grid rows ------------------------------------------------------------------------------------------ */

void eListbox::gridUpdate()
{
	if (!m_grid_dirty)
		return;
	m_grid_dirty = false;
	m_grid_spans = false;
	m_grid_first.clear();
	m_grid_rowof.clear();
	m_grid_spanflag.clear();
	m_grid_ytop.clear();
	m_grid_pagefirst.clear();
	if (!m_content)
		return;
	const int n = m_content->size();
	int rows = 0;
	if (m_orientation == orVertical)
	{
		// every entry is a row, an entry (header, marker) may be higher or lower than a normal one
		std::vector<int> heights;
		if (m_itemheight <= 0 || !m_content->entryHeightList(heights))
			return;
		m_grid_spans = true;
		rows = n;
		m_grid_ytop.assign(rows + 1, 0);
		for (int r = 0; r < rows; ++r)
			m_grid_ytop[r + 1] = m_grid_ytop[r] + ((r < (int)heights.size() && heights[r] > 0) ? heights[r] : m_itemheight) + m_gap_y;
	}
	else
	{
		if (m_orientation != orGrid || m_max_columns <= 0)
			return;
		std::vector<char> spans;
		if (!m_content->gridSpanList(spans))
			return;
		m_grid_spans = true;
		bool open = false;
		int count = 0;
		for (int i = 0; i < n; ++i)
		{
			const bool span = i < (int)spans.size() && spans[i];
			if (span)
			{
				m_grid_first.push_back(i);
				open = false;
			}
			else if (!open || count >= m_max_columns)
			{
				m_grid_first.push_back(i);
				count = 1;
				open = true;
			}
			else
				++count;
			m_grid_rowof.push_back((int)m_grid_first.size() - 1);
			m_grid_spanflag.push_back(span ? 1 : 0);
		}

		// row heights (a spanning entry may be shorter than a cell) as running tops
		m_grid_spanheight = m_content->gridSpanHeight();
		rows = (int)m_grid_first.size();
		m_grid_ytop.assign(rows + 1, 0);
		for (int r = 0; r < rows; ++r)
		{
			const int cnt = (r + 1 < rows ? m_grid_first[r + 1] : n) - m_grid_first[r];
			const bool spanned = cnt == 1 && m_grid_spanflag[m_grid_first[r]];
			m_grid_ytop[r + 1] = m_grid_ytop[r] + ((spanned && m_grid_spanheight > 0) ? m_grid_spanheight : m_itemheight) + m_gap_y;
		}
	}

	// the pages: as many rows as fit the listbox, at least one
	const int listHeight = size().height();
	for (int r = 0; r < rows;)
	{
		m_grid_pagefirst.push_back(r);
		const int top = m_grid_ytop[r];
		++r;
		while (r < rows && m_grid_ytop[r + 1] - m_gap_y - top <= listHeight) // no gap after the last row of a page
			++r;
	}
}

int eListbox::gridRowHeight(int row)
{
	gridUpdate();
	if (m_grid_spans && row >= 0 && row < (int)m_grid_ytop.size() - 1)
		return m_grid_ytop[row + 1] - m_grid_ytop[row] - m_gap_y; // the cell, without the gap below it
	return m_itemheight;
}

/* y of the top of a row, counted from the top of the list (not of the page) */
int eListbox::gridRowTop(int row)
{
	gridUpdate();
	if (m_grid_spans)
	{
		const int rows = (int)m_grid_ytop.size() - 1;
		if (row <= 0)
			return row * pitchY();
		if (row <= rows)
			return m_grid_ytop[row];
		return m_grid_ytop[rows] + (row - rows) * pitchY();
	}
	return row * pitchY();
}

int eListbox::gridPageCount()
{
	gridUpdate();
	if (m_grid_spans)
		return (int)m_grid_pagefirst.size();
	return m_max_rows ? (gridRows() + m_max_rows - 1) / m_max_rows : 0;
}

int eListbox::gridPageOfRow(int row)
{
	gridUpdate();
	if (m_grid_spans)
	{
		const int page = (int)(std::upper_bound(m_grid_pagefirst.begin(), m_grid_pagefirst.end(), row) - m_grid_pagefirst.begin()) - 1;
		return std::max(0, page);
	}
	return row / std::max(1, m_max_rows);
}

/* first row of a page; one past the last page it is the number of rows */
int eListbox::gridPageStartRow(int page)
{
	gridUpdate();
	if (m_grid_spans)
	{
		if (page < 0)
			return 0;
		return page < (int)m_grid_pagefirst.size() ? m_grid_pagefirst[page] : (int)m_grid_ytop.size() - 1;
	}
	return page * m_max_rows;
}

int eListbox::getPageCount()
{
	if (!m_content || !m_items_per_page)
		return 0;
	if (carouselActive())
		return m_content->size(); // no pages in a carousel: every entry is a position
	if (m_orientation == orGrid)
		return gridPageCount();
	if (m_orientation == orVertical && gridHasSpans())
	{
		if (m_scroll_type == scrollByPage)
			return gridPageCount();
		return (m_content->size() + verticalVisible(m_top) - 1) / verticalVisible(m_top);
	}
	return (m_content->size() + m_items_per_page - 1) / m_items_per_page;
}

int eListbox::getCurrentPage()
{
	if (!m_content || !m_items_per_page)
		return 0;
	if (carouselActive())
		return m_selected;
	if (m_orientation == orGrid)
		return gridPageOfRow(gridRowOf(m_selected));
	if (m_orientation == orVertical && gridHasSpans())
		return m_scroll_type == scrollByPage ? gridPageOfRow(m_selected) : m_selected / verticalVisible(m_top);
	return m_selected / m_items_per_page;
}

int eListbox::gridRows()
{
	gridUpdate();
	if (m_grid_spans)
		return (int)m_grid_ytop.size() - 1;
	return (m_content && m_max_columns) ? (m_content->size() + m_max_columns - 1) / m_max_columns : 0;
}

int eListbox::gridRowOf(int index)
{
	gridUpdate();
	if (m_grid_spans && m_orientation == orVertical)
		return index;
	if (m_grid_spans)
		return (index >= 0 && index < (int)m_grid_rowof.size()) ? m_grid_rowof[index] : (int)m_grid_first.size();
	return m_max_columns ? index / m_max_columns : 0;
}

int eListbox::gridRowFirst(int row)
{
	gridUpdate();
	if (m_grid_spans && m_orientation == orVertical)
		return row;
	if (m_grid_spans)
		return (row >= 0 && row < (int)m_grid_first.size()) ? m_grid_first[row] : (m_content ? m_content->size() : 0);
	return row * m_max_columns;
}

int eListbox::gridRowCount(int row)
{
	gridUpdate();
	const int total = m_content ? m_content->size() : 0;
	if (m_grid_spans && m_orientation == orVertical)
		return (row >= 0 && row < total) ? 1 : 0;
	if (m_grid_spans)
	{
		if (row < 0 || row >= (int)m_grid_first.size())
			return 0;
		return (row + 1 < (int)m_grid_first.size() ? m_grid_first[row + 1] : total) - m_grid_first[row];
	}
	const int first = row * m_max_columns;
	return std::max(0, std::min(m_max_columns, total - first));
}

bool eListbox::gridSpanAt(int index)
{
	gridUpdate();
	return m_grid_spans && index >= 0 && index < (int)m_grid_spanflag.size() && m_grid_spanflag[index];
}

/* size of the cell of an entry: a spanning entry covers the whole row */
/* vertical list with entries of different heights: scrolls entry by entry, the list only moves as far as needed to
   keep the selected entry fully visible */
int eListbox::verticalTopFor(int index)
{
	const int total = (int)m_grid_ytop.size() - 1;
	if (total <= 0)
		return 0;
	index = std::min(std::max(index, 0), total - 1);
	int top = std::min(std::max(m_top, 0), total - 1);
	if (index < top)
		return index;
	const int height = size().height();
	while (top < index && gridRowTop(index + 1) - m_gap_y - gridRowTop(top) > height)
		++top;
	return top;
}

/* how many entries fit the list when it starts at entry `top` (at least one) */
int eListbox::verticalVisible(int top)
{
	const int total = (int)m_grid_ytop.size() - 1;
	if (total <= 0)
		return 1;
	top = std::min(std::max(top, 0), total - 1);
	const int height = size().height();
	int count = 1;
	while (top + count < total && gridRowTop(top + count + 1) - m_gap_y - gridRowTop(top) <= height)
		++count;
	return count;
}

/* rectangle of an entry of a vertical list, relative to the top of the page */
eRect eListbox::verticalRect(int index)
{
	if (gridHasSpans())
		return eRect(0, gridRowTop(index) - gridRowTop(m_top), size().width(), gridRowHeight(index));
	return eRect(0, pitchY() * (index - m_top), size().width(), m_itemheight);
}

eSize eListbox::gridItemSize(int index)
{
	return eSize(gridSpanAt(index) ? gridSpanWidth() : m_itemwidth, gridRowHeight(gridRowOf(index)));
}

void eListbox::setContent(iListboxContent *content)
{
	m_content = content;
	if (content)
	{
		m_content->setListbox(this);
		if (m_orientation == orGrid)
			m_content->setSpanWidth(gridSpanWidth());
	}
	entryReset();
}

void eListbox::allowNativeKeys(bool allow)
{
	if (m_native_keys_bound != allow)
	{
		ePtr<eActionMap> ptr;
		eActionMap::getInstance(ptr);
		if (allow)
			ptr->bindAction("ListboxActions", 0, 0, this);
		else
			ptr->unbindAction(this, 0);
		m_native_keys_bound = allow;
	}
}

bool eListbox::atBegin()
{
	if (m_content && !m_selected)
		return true;
	return false;
}

bool eListbox::atEnd()
{
	if (m_content && m_content->size() == m_selected+1)
		return true;
	return false;
}

void eListbox::moveToEnd()
{
	if (!m_content)
		return;
	/* move to last existing one ("end" is already invalid) */
	m_content->cursorEnd(); m_content->cursorMove(-1);
	/* current selection invisible? */
	if (m_orientation == orVertical && gridHasSpans())
	{
		m_top = m_scroll_type == scrollByItem ? verticalTopFor(m_content->cursorGet()) : gridPageStartRow(gridPageOfRow(m_content->cursorGet()));
	}
	else if (m_scroll_type == scrollByItem && (m_orientation == orVertical || m_orientation == orHorizontal))
	{
		int &first = m_orientation == orVertical ? m_top : m_left;
		first = itemScrollStart(m_content->cursorGet(), first, m_items_per_page, m_content->size());
	}
	else if (m_orientation == orVertical)
	{
		if (m_top + m_items_per_page <= m_content->cursorGet())
		{
			int rest = m_content->size() % m_items_per_page;
			if (rest)
				m_top = m_content->cursorGet() - rest + 1;
			else
				m_top = m_content->cursorGet() - m_items_per_page + 1;
			if (m_top < 0)
				m_top = 0;
		}
	}
	else
	{
		if (m_left + m_items_per_page <= m_content->cursorGet())
		{
			int rest = m_content->size() % m_items_per_page;
			if (rest)
				m_left = m_content->cursorGet() - rest + 1;
			else
				m_left = m_content->cursorGet() - m_items_per_page + 1;
			if (m_left < 0)
				m_left = 0;
		}
	}
}

void eListbox::moveSelection(long dir)
{
	long r_dir = dir;
	// For compatability reasons we add this so to support current listbox actions in horizontal listboxes
	if (m_orientation == orHorizontal) {
		switch (dir) {
			case moveUp:
				r_dir = prevPage;
				break;
			case moveDown:
				r_dir = nextPage;
				break;
			case pageUp:
				r_dir = prevItem;
				break;
			case pageDown:
				r_dir = nextItem;
				break;
		}
	}

	// Map universal actions to the corresponding action for Horizontal and vertical eListbox
	switch (dir) {
		case prevItemPage:
			if (m_orientation == orHorizontal){
				r_dir = prevPage;
			} else if (m_orientation == orVertical) {
				r_dir = prevItem;
			} else {
				r_dir = moveUp;
			}
			break;
		case nextItemPage:
			if (m_orientation == orHorizontal){
				r_dir = nextPage;
			} else if (m_orientation == orVertical) {
				r_dir = nextItem;
			} else {
				r_dir = moveDown;
			}
			break;
		case prevPageItem:
			if (m_orientation == orVertical){
				r_dir = prevPage;
			} else {
				r_dir = prevItem;
			}
			break;
		case nextPageItem:
			if (m_orientation == orVertical){
				r_dir = nextPage;
			} else {
				r_dir = nextItem;
			}
			break;
	}
	/* refuse to do anything without a valid list. */
	if (!m_content)
		return;
	/* if our list does not have one entry, don't do anything. */
	if (!m_items_per_page)
		return;

	bool isGrid = m_orientation == orGrid;
	/* we need the old top/sel to see what we have to redraw */
	int oldtop = m_top;
	int oldleft = m_left;
	int oldsel = m_selected;
	int prevsel = oldsel;
	int newsel;
	int oldRow = (isGrid && m_max_columns != 0) ? gridRowOf(oldsel) : ((m_orientation == orVertical && gridHasSpans()) ? oldsel : 0);
	int oldColumn = (isGrid && m_max_columns != 0) ? gridColOf(oldsel) : 0;

	switch (r_dir) {
		case moveEnd:
			if (isGrid)
			{
				int newRow = oldRow;
				do
				{
					m_content->cursorMove(1);
					newsel = m_content->cursorGet();
					newRow = gridRowOf(newsel);
					if (newRow != oldRow || !m_content->currentCursorSelectable())
					{
						m_content->cursorSet(prevsel);
						break;
					}
					if (newsel == prevsel)
					{
						break;
					}
					prevsel = newsel;
				} while (true);
			}
			else
				m_content->cursorEnd();
			[[fallthrough]];
		case moveUp:
		case prevItem:
			if (isGrid)
			{
				if (r_dir == moveUp)
				{
					// previous row, same column (or the last entry of a shorter row); wraps to the last row if enabled
					int row = oldRow;
					bool found = false;
					for (int tries = gridRows(); tries > 0; --tries)
					{
						--row;
						if (row < 0)
						{
							if (!m_enabled_wrap_around)
								break;
							row = gridRows() - 1;
						}
						const int count = gridRowCount(row);
						if (count <= 0)
							break;
						m_content->cursorSet(gridRowFirst(row) + std::min(oldColumn, count - 1));
						if (m_content->cursorValid() && m_content->currentCursorSelectable())
						{
							found = true;
							break;
						}
						if (row == oldRow)
							break;
					}
					if (!found)
						m_content->cursorSet(oldsel);

					// Final selection
					newsel = m_content->cursorGet();
				}
				else
				{
					// Move left: previous entry, flowing onto the last entry of the previous row; wraps to the very last entry if enabled
					const int total = m_content->size();
					int current = oldsel;
					bool found = false;
					for (int tries = total; tries > 1; --tries)
					{
						--current;
						if (current < 0)
						{
							if (!m_enabled_wrap_around)
								break;
							current = total - 1;
						}
						m_content->cursorSet(current);
						if (m_content->cursorValid() && m_content->currentCursorSelectable())
						{
							found = true;
							break;
						}
					}
					if (!found)
						m_content->cursorSet(oldsel);

					newsel = m_content->cursorGet();
				}
			}
			else
			{
				do
				{
					m_content->cursorMove(-1);
					newsel = m_content->cursorGet();
					if (newsel == prevsel) {  // cursorMove reached top and left cursor position the same. Must wrap around ?
						if (m_enabled_wrap_around)
						{
							m_content->cursorEnd();
							m_content->cursorMove(-1);
							newsel = m_content->cursorGet();
						}
						else
						{
							m_content->cursorSet(oldsel);
							break;
						}
					}
					prevsel = newsel;
				}
				while (newsel != oldsel && !m_content->currentCursorSelectable());
			}
			break;
		case moveTop:
		case moveStart:
			if (isGrid)
			{
				int newRow = oldRow;
				do
				{
					m_content->cursorMove(-1);
					newsel = m_content->cursorGet();
					newRow = gridRowOf(newsel);
					if (newRow != oldRow || !m_content->currentCursorSelectable())
					{
						m_content->cursorSet(prevsel);
						break;
					}
					if (newsel == prevsel)
					{
						break;
					}
					prevsel = newsel;

				} while (true);
			}
			else
				m_content->cursorHome();
			[[fallthrough]];
		case justCheck:
			if (m_content->cursorValid() && m_content->currentCursorSelectable())
				break;
			[[fallthrough]];
		case moveDown:
		case nextItem:
			if (isGrid)
			{
				if (r_dir == moveDown)
				{
					// next row, same column (or the last entry of a shorter row); wraps to the first row if enabled
					int row = oldRow;
					bool found = false;
					for (int tries = gridRows(); tries > 0; --tries)
					{
						++row;
						if (row >= gridRows())
						{
							if (!m_enabled_wrap_around)
								break;
							row = 0;
						}
						const int count = gridRowCount(row);
						if (count <= 0)
							break;
						m_content->cursorSet(gridRowFirst(row) + std::min(oldColumn, count - 1));
						if (m_content->cursorValid() && m_content->currentCursorSelectable())
						{
							found = true;
							break;
						}
						if (row == oldRow)
							break;
					}
					if (!found)
						m_content->cursorSet(oldsel);

					// Final selection
					newsel = m_content->cursorGet();
				}
				else
				{
					// Move right: next entry, flowing onto the first entry of the next row; wraps to the very first entry if enabled
					const int total = m_content->size();
					int current = oldsel;
					bool found = false;
					for (int tries = total; tries > 1; --tries)
					{
						++current;
						if (current >= total)
						{
							if (!m_enabled_wrap_around)
								break;
							current = 0;
						}
						m_content->cursorSet(current);
						if (m_content->cursorValid() && m_content->currentCursorSelectable())
						{
							found = true;
							break;
						}
					}
					if (!found)
						m_content->cursorSet(oldsel);

					newsel = m_content->cursorGet();
				}

			}
			else
			{
				do
				{
					m_content->cursorMove(1);
					if (!m_content->cursorValid()) { //cursorMove reached end and left cursor position past the list. Must wrap around ?
						if (m_enabled_wrap_around)
							m_content->cursorHome();
						else
							m_content->cursorSet(oldsel);
					}
					newsel = m_content->cursorGet();
				}
				while (newsel != oldsel && !m_content->currentCursorSelectable());
			}
			break;
		case pageUp:
		case prevPage: {
			if (m_orientation == orVertical && gridHasSpans())
			{
				// as many entries up as fit the list
				int target = std::max(0, oldsel - verticalVisible(m_top));
				m_content->cursorSet(target);
				while (target > 0 && !m_content->currentCursorSelectable())
					m_content->cursorSet(--target);
				while (m_content->cursorValid() && !m_content->currentCursorSelectable())
					m_content->cursorMove(1);
				if (!m_content->cursorValid())
					m_content->cursorSet(oldsel);
				newsel = m_content->cursorGet();
				break;
			}
			if (isGrid && gridHasSpans())
			{
				// rows are not a fixed number of entries here: move a page of rows, keep the column
				const int page = gridPageOfRow(oldRow);
				const int tpage = std::max(0, page - 1);
				int row = gridPageStartRow(tpage) + std::min(oldRow - gridPageStartRow(page), std::max(0, gridPageStartRow(tpage + 1) - gridPageStartRow(tpage) - 1));
				m_content->cursorSet(gridRowFirst(row) + std::min(oldColumn, std::max(0, gridRowCount(row) - 1)));
				while (m_content->cursorValid() && !m_content->currentCursorSelectable())
					m_content->cursorMove(-1);
				if (!m_content->cursorValid() || !m_content->currentCursorSelectable())
					m_content->cursorSet(oldsel);
				newsel = m_content->cursorGet();
				break;
			}
			if (m_orientation == orHorizontal && m_enabled_wrap_around && oldsel == 0)
			{
				// already at the first entry, wrap around to the last selectable entry
				m_content->cursorEnd();
				m_content->cursorMove(-1);
				newsel = m_content->cursorGet();
				while (newsel != oldsel && !m_content->currentCursorSelectable())
				{
					m_content->cursorMove(-1);
					newsel = m_content->cursorGet();
				}
				break;
			}
			int pageind;
			do
			{
				m_content->cursorMove(-m_items_per_page);
				newsel = m_content->cursorGet();
				pageind = newsel % m_items_per_page; // rememer were we land in thsi page (could be different on topmost page)
				prevsel = newsel - pageind; // get top of page index
				// find first selectable entry in new page. First check bottom part, than upper part
				while (newsel != prevsel + m_items_per_page && m_content->cursorValid() && !m_content->currentCursorSelectable())
				{
					m_content->cursorMove(1);
					newsel = m_content->cursorGet();
				}
				if (!m_content->currentCursorSelectable()) // no selectable found in bottom part of page
				{
					m_content->cursorSet(prevsel + pageind);
					while (newsel != prevsel && !m_content->currentCursorSelectable())
					{
						m_content->cursorMove(-1);
						newsel = m_content->cursorGet();
					}
				}
				if (m_content->currentCursorSelectable())
					break;
				if (newsel == 0) // at top and nothing found . Go down till something selectable or old location
				{
					while (newsel != oldsel && !m_content->currentCursorSelectable())
					{
						m_content->cursorMove(1);
						newsel = m_content->cursorGet();
					}
					break;
				}
				m_content->cursorSet(prevsel + pageind);
			}
			while (newsel == prevsel);
			break;
		}
		case pageDown:
		case nextPage: {
			if (m_orientation == orVertical && gridHasSpans())
			{
				// as many entries down as fit the list
				const int last = m_content->size() - 1;
				int target = std::min(last, oldsel + verticalVisible(m_top));
				m_content->cursorSet(target);
				while (target < last && !m_content->currentCursorSelectable())
					m_content->cursorSet(++target);
				while (m_content->cursorValid() && !m_content->currentCursorSelectable())
					m_content->cursorMove(-1);
				if (!m_content->cursorValid())
					m_content->cursorSet(oldsel);
				newsel = m_content->cursorGet();
				break;
			}
			if (isGrid && gridHasSpans())
			{
				const int page = gridPageOfRow(oldRow);
				const int tpage = std::min(gridPageCount() - 1, page + 1);
				int row = gridPageStartRow(tpage) + std::min(oldRow - gridPageStartRow(page), std::max(0, gridPageStartRow(tpage + 1) - gridPageStartRow(tpage) - 1));
				row = std::min(row, gridRows() - 1);
				m_content->cursorSet(gridRowFirst(row) + std::min(oldColumn, std::max(0, gridRowCount(row) - 1)));
				while (m_content->cursorValid() && !m_content->currentCursorSelectable())
					m_content->cursorMove(1);
				if (!m_content->cursorValid() || !m_content->currentCursorSelectable())
					m_content->cursorSet(oldsel);
				newsel = m_content->cursorGet();
				break;
			}
			if (m_orientation == orHorizontal && m_enabled_wrap_around && oldsel == m_content->size() - 1)
			{
				// already at the last entry, wrap around to the first selectable entry
				m_content->cursorHome();
				newsel = m_content->cursorGet();
				while (newsel != oldsel && !m_content->currentCursorSelectable())
				{
					m_content->cursorMove(1);
					newsel = m_content->cursorGet();
				}
				break;
			}
			int pageind;
			do
			{
				m_content->cursorMove(m_items_per_page);
				if (!m_content->cursorValid())
					m_content->cursorMove(-1);
				newsel = m_content->cursorGet();
				pageind = newsel % m_items_per_page;
				prevsel = newsel - pageind; // get top of page index
				// find a selectable entry in the new page. first look up then down from current screenlocation on the page
				while (newsel != prevsel && !m_content->currentCursorSelectable())
				{
					m_content->cursorMove(-1);
					newsel = m_content->cursorGet();
				}
				if (!m_content->currentCursorSelectable()) // no selectable found in top part of page
				{
					m_content->cursorSet(prevsel + pageind);
					do {
						m_content->cursorMove(1);
						newsel = m_content->cursorGet();
					}
						while (newsel != prevsel + m_items_per_page && m_content->cursorValid() && !m_content->currentCursorSelectable());
				}
				if (!m_content->cursorValid())
				{
					// we reached the end of the list
					// Back up till something selectable or we reach oldsel again
					// E.g this should bring us back to the last selectable item on the original page
					do
					{
						m_content->cursorMove(-1);
						newsel = m_content->cursorGet();
					}
					while (newsel != oldsel && !m_content->currentCursorSelectable());
					break;
				}
				if (newsel != prevsel + m_items_per_page)
					break;
				m_content->cursorSet(prevsel + pageind); // prepare for next page down
			}
			while (newsel == prevsel + m_items_per_page);
			break;
		}
	}

	/* now, look wether the current selection is out of screen */
	m_selected = m_content->cursorGet();
	const bool carousel = carouselActive();
	if (carousel)
	{
		// the selection stays on the centre slot, the entries scroll past it
		if (m_orientation == orHorizontal)
			m_left = m_selected - carouselCenter();
		else
			m_top = m_selected - carouselCenter();
	}
	else if (m_orientation == orHorizontal)
		m_left = m_scroll_type == scrollByItem ? itemScrollStart(m_selected, m_left, m_items_per_page, m_content->size()) : m_selected - (m_selected % m_items_per_page);
	else if (m_orientation == orVertical)
	{
		if (gridHasSpans())
			m_top = m_scroll_type == scrollByItem ? verticalTopFor(m_selected) : gridPageStartRow(gridPageOfRow(m_selected));
		else
			m_top = m_scroll_type == scrollByItem ? itemScrollStart(m_selected, m_top, m_items_per_page, m_content->size()) : m_selected - (m_selected % m_items_per_page);
	}
	else
		m_top = m_scroll_type == scrollByItem ? gridRowTopFor(gridRowOf(m_selected)) : gridPageStartRow(gridPageOfRow(gridRowOf(m_selected)));

	// if it is, then the old selection clip is irrelevant, clear it or we'll get artifacts
	if (m_orientation == orVertical || m_orientation == orGrid)
	{
		if (m_top != oldtop && m_content)
			m_content->resetClip();
	}
	else
	{
		if (m_left != oldleft && m_content)
			m_content->resetClip();
	}

	if (oldsel != m_selected)
		/* emit */ selectionChanged();

	updateScrollBar();

	if (carousel)
	{
		// every entry moves when the selection moves
		if (m_selected != oldsel || m_top != oldtop || m_left != oldleft)
		{
			if (m_content)
				m_content->resetClip();
			invalidate();
		}
	}
	else if (selectionZoomActive())
	{
		// the enlarged selection overlaps its neighbours: redraw everything
		if (m_selected != oldsel || m_top != oldtop || m_left != oldleft)
		{
			if (m_content)
				m_content->resetClip();
			invalidate();
		}
	}
	else if (m_orientation == orVertical)
	{
		if (m_top != oldtop){
			invalidate();
		}
		else if (m_selected != oldsel)
		{
			/* redraw the old and newly selected */
			gRegion inv = verticalRect(m_selected);
			inv |= verticalRect(oldsel);
			invalidate(inv);
		}
	}
	else if (m_orientation == orGrid)
	{
		if (m_top != oldtop){
			invalidate();
		}
		else if (m_selected != oldsel)
		{
			/* redraw the old and newly selected */
			gRegion inv = eRect(getItemPostion(m_selected), gridItemSize(m_selected));
			inv |= eRect(getItemPostion(oldsel), gridItemSize(oldsel));
			invalidate(inv);
		}
	}
	else
	{
		if (m_left != oldleft){
			invalidate();
		}
		else if (m_selected != oldsel)
		{
			/* redraw the old and newly selected */
			gRegion inv = eRect(pitchX() * (m_selected-m_left), 0, m_itemwidth, size().height());
			inv |= eRect(pitchX() * (oldsel-m_left), 0, m_itemwidth, size().height());
			invalidate(inv);
		}
	}
}

void eListbox::moveSelectionTo(int index)
{
	if (m_content)
	{
		m_content->cursorSet(index);
		moveSelection(justCheck);
	}
}

int eListbox::getCurrentIndex()
{
	if (m_content && m_content->cursorValid())
		return m_content->cursorGet();
	return 0;
}

int eListbox::getOrientation()
{
	return m_orientation;
}

void eListbox::updateScrollBar()
{
	if (!m_content)
		return;

	int width = size().width();
	int height = size().height();

	if (m_scrollbar_mode == showNever) {
		if (m_orientation == orVertical) {
			m_content->setSize(eSize(width, m_itemheight));
		} else if (m_orientation == orHorizontal) {
			m_content->setSize(eSize(m_itemwidth, height));
		} else {
			m_content->setSize(eSize(m_itemwidth, m_itemheight));
		}
		return;
	}

	int entries = m_content->size();
	if ((m_orientation == orGrid) && m_max_columns)
		entries = gridRows();

	int maxItems = (m_orientation == orGrid) ? m_max_rows : m_items_per_page;
	const bool paged = m_orientation == orGrid && m_max_columns && gridHasSpans() && m_scroll_type == scrollByPage;
	if (paged)
	{
		entries = gridPageCount();
		maxItems = 1;
	}
	else if (m_orientation == orVertical && gridHasSpans())
		maxItems = verticalVisible(m_top); // entries of different heights: as many as fit

	if (m_content_changed)
	{
		m_content_changed = false;
		if (m_scrollbar_mode == showLeft || m_scrollbar_mode == showTop)
		{
			if (m_orientation == orVertical) {
				m_content->setSize(eSize(width-m_scrollbar_width-5, m_itemheight));
				m_scrollbar->move(ePoint(0, 0));
				m_scrollbar->resize(eSize(m_scrollbar_width, height));
			} else if (m_orientation == orHorizontal) {
				m_content->setSize(eSize(m_itemwidth, height-m_scrollbar_height-5));
				m_scrollbar->move(ePoint(0, 0));
				m_scrollbar->resize(eSize(width, m_scrollbar_height));
			} else {
				m_content->setSize(eSize(m_itemwidth, m_itemheight));
				m_scrollbar->move(ePoint(0, 0));
				m_scrollbar->resize(eSize(m_scrollbar_width, height));
			}
			if (entries > (paged ? maxItems : m_items_per_page))
			{
				m_scrollbar->show();
			}
			else
			{
				m_scrollbar->hide();
			}
		}
		else if (entries > maxItems || m_scrollbar_mode == showAlways)
		{
			if (m_orientation == orVertical) {
				if (m_scrollbar_mode != showNever) {
					m_scrollbar->move(ePoint(width-m_scrollbar_width, 0));
					m_scrollbar->resize(eSize(m_scrollbar_width, height));
					m_content->setSize(eSize(width-m_scrollbar_width-5, m_itemheight));
				} else {
					m_content->setSize(eSize(width, m_itemheight));
				}
			} else if (m_orientation == orHorizontal) {
				if (m_scrollbar_mode != showNever) {
					m_scrollbar->move(ePoint(0, height-m_scrollbar_height));
					m_scrollbar->resize(eSize(width, m_scrollbar_height));
					m_content->setSize(eSize(m_itemwidth, height-m_scrollbar_height-5));
				} else {
					m_content->setSize(eSize(m_itemwidth, height));
				}
			} else {
				if (m_scrollbar_mode != showNever) {
					m_scrollbar->move(ePoint(width-m_scrollbar_width, 0));
					m_scrollbar->resize(eSize(m_scrollbar_width, height));
					m_content->setSize(eSize(m_itemwidth, m_itemheight));
				} else {
					m_content->setSize(eSize(m_itemwidth, m_itemheight));
				}
			}
			if (m_scrollbar_mode != showNever) {
				m_scrollbar->show();
			} else {
				m_scrollbar->hide();
			}
		}
		else
		{
			if (m_orientation == orVertical)
				m_content->setSize(eSize(width, m_itemheight));
			else if (m_orientation == orHorizontal)
				m_content->setSize(eSize(m_itemwidth, height));
			else
				m_content->setSize(eSize(m_itemwidth, m_itemheight));

			m_scrollbar->hide();
		}
	}
	if (maxItems && entries)
	{
		int topleft = paged ? gridPageOfRow(m_top) : (m_orientation == orVertical || m_orientation == orGrid ? m_top : m_left);
		if (carouselActive())
			topleft = std::max(0, std::min(m_selected, entries - 1));

		const bool byItem = m_scroll_type == scrollByItem && !carouselActive();
		int curVisiblePage = byItem ? topleft : topleft / maxItems;
		if (m_prev_scrollbar_page != curVisiblePage)
		{
			m_prev_scrollbar_page = curVisiblePage;
			int pages = entries / maxItems;
			if ((pages*maxItems) < entries)
				++pages;
			int start=(topleft*100)/(pages*maxItems);
			int vis=(maxItems*100+pages*maxItems-1)/(pages*maxItems);
			if (byItem)
			{
				// the thumb moves item by item
				start = (topleft * 100) / entries;
				vis = (maxItems * 100 + entries - 1) / entries;
			}
			if (vis < 3)
				vis=3;
			m_scrollbar->setStartEnd(start,start+vis);
		}
	}
}

int eListbox::getEntryTop()
{
	if (carouselActive())
		return carouselSlotPos(carouselCenter());
	if (m_orientation == orVertical && gridHasSpans())
	{
		return gridRowTop(m_selected) - gridRowTop(m_top);
	}
	else if (m_orientation == orGrid)
	{
		return (m_selected - m_top) * pitchY();
	}
	else if (m_orientation == orVertical)
	{
		return (m_selected - m_top) * pitchY();
	}
	else
	{
		return (m_selected - m_left) * pitchX();
	}
}

ePoint eListbox::getItemPostion(int index)
{
	int posx = 0, posy = 0;

	if (m_orientation == orGrid || m_orientation == orHorizontal)
	{
		posx = (m_orientation == orGrid) ? pitchX() * gridColOf(index) : pitchX() * (index - m_left);
		posy = (m_orientation == orGrid) ? gridRowTop(gridRowOf(index)) - gridRowTop(m_top) : 0;
	}
	else if (gridHasSpans())
		posy = gridRowTop(index) - gridRowTop(m_top);
	else
		posy = pitchY() * (index - m_top);

	return ePoint(posx, posy);
}

int eListbox::event(int event, void *data, void *data2)
{
	switch (event)
	{
		case evtPaint:
		{
			ePtr<eWindowStyle> style;

			if (!m_content)
				return eWidget::event(event, data, data2);
			ASSERT(m_content);

			getStyle(style);

			if (!m_content)
				return 0;

			gPainter &painter = *(gPainter*)data2;

			m_content->cursorSave();
			const bool carousel = carouselActive();
			if (carousel)
			{
				// positioned per slot with cursorSet() below
			}
			else if (m_orientation == orVertical)
			{
				m_content->cursorMove(m_top - m_selected);
			}
			else if (m_orientation == orHorizontal)
			{
				m_content->cursorMove(m_left - m_selected);
			}
			else
			{
				m_content->cursorMove(gridRowFirst(m_top) - m_selected);
			}

			gRegion entryrect = m_orientation == orVertical ? eRect(0, 0, size().width(), m_itemheight) : eRect(0, 0, m_itemwidth, size().height());
			const gRegion &paint_region = *(gRegion*)data;

			if (!isTransparent())
			{
				int cornerRadius = getCornerRadius();
				int cornerRadiusEdges = getCornerRadiusEdges();
				painter.clip(paint_region);
				style->setStyle(painter, eWindowStyle::styleListboxNormal);
				if (m_style.m_background_color_set)
					painter.setBackgroundColor(m_style.m_background_color);

				if (cornerRadius && cornerRadiusEdges)
				{
					painter.setRadius(cornerRadius, cornerRadiusEdges);
					// A listbox's own panel background is never a
					// video-reveal widget - under GLES this must use the
					// "over" blend formula regardless of the style's fill
					// color, same as lib/gui/elistboxcontent.cpp's item
					// backgrounds (see gEGLDC::executeRectangle()'s
					// comment); other backends are unaffected either way.
					painter.drawRectangle(eRect(ePoint(0, 0), size()), painter.usingGLES());
				}
				else
					painter.clear();
				painter.clippop();
			}

			int xoffset = 0;
			int yoffset = 0;
			if (m_scrollbar && m_scrollbar_mode == showLeft)
			{
				xoffset = m_scrollbar->size().width() + 5;
			}

			if (m_scrollbar && m_scrollbar_mode == showTop)
			{
				yoffset = m_scrollbar->size().height() + 5;
			}

			if (carousel)
			{
				const int n = m_content->size();
				const int center = carouselCenter();
				const bool vert = m_orientation == orVertical;
				// a horizontal carousel row is centred vertically in the widget, so the enlarged focus tile can grow
				// evenly to both sides instead of being pushed down by the clamp at the widget edge
				const int rowTop = yoffset; // top of the area below the scrollbar
				if (!vert)
					yoffset += std::max(0, (size().height() - yoffset - m_itemheight) / 2);
				// the centre slot is painted last (and enlarged) so it overlaps its neighbours
				for (int pass = 0; pass < 2; ++pass)
				for (int i = 0; i < m_items_per_page && n; ++i)
				{
					if ((i == center) != (pass == 1))
						continue;
					int idx = m_selected - center + i;
					if (m_enabled_wrap_around)
						idx = ((idx % n) + n) % n;
					else if (idx < 0 || idx >= n)
						continue;
					const int slotPos = carouselSlotPos(i);
					ePoint pos = vert ? ePoint(xoffset, slotPos) : ePoint(slotPos, yoffset);
					if (i == center)
					{
						// the focused slot: its own size if one is given (centred across the scroll direction), scaled
						// with its content around its centre, overlapping the neighbours
						const eSize base = m_content->getItemSize();
						const bool dedicated = (m_carousel_cw > 0 || m_carousel_ch > 0) && base.width() > 0 && base.height() > 0;
						eSize cell = base;
						if (dedicated)
						{
							cell = carouselFocusCell(base);
							if (vert)
								pos.setX(std::max(xoffset, std::min(pos.x() + (base.width() - cell.width()) / 2, size().width() - cell.width())));
							else
								pos.setY(std::max(rowTop, std::min(pos.y() + (base.height() - cell.height()) / 2, size().height() - cell.height())));
							m_content->setCellOverride(true);
							m_content->setSize(cell);
						}
						if (m_selection_enabled && m_carousel_zoom > 100)
							paintZoomed(painter, *style, idx, pos, m_carousel_zoom);
						else if (!(paint_region & gRegion(eRect(pos, cell))).empty())
						{
							m_content->cursorSet(idx);
							m_content->paint(painter, *style, pos, m_selection_enabled);
						}
						if (dedicated)
						{
							m_content->setSize(base);
							m_content->setCellOverride(false);
						}
						continue;
					}
					gRegion slot = eRect(pos, vert ? eSize(size().width(), m_itemheight) : eSize(m_itemwidth, size().height()));
					if ((paint_region & slot).empty())
						continue;
					m_content->cursorSet(idx);
					m_content->paint(painter, *style, pos, 0);
				}
				m_content->cursorRestore();
			}
			else if (m_orientation == orVertical && gridHasSpans())
			{
				// entries of different heights: fill the list entry by entry
				const int n = m_content->size();
				const int listHeight = size().height();
				int posy = 0;
				for (int row = m_top; posy < listHeight; ++row)
				{
					const int rowHeight = row < n ? gridRowHeight(row) : m_itemheight;
					entryrect = eRect(0, posy, size().width(), rowHeight);
					gRegion entry_clip_rect = paint_region & entryrect;
					if (!entry_clip_rect.empty())
						m_content->paint(painter, *style, ePoint(xoffset, posy), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
					m_content->cursorMove(+1);
					posy += rowHeight + m_gap_y;
				}
				m_content->cursorRestore();
			}
			else if (m_orientation == orVertical)
			{
				// A content that can paint in layers (shapes, images, text) gets every visible entry once per layer: the GPU backend
				// then needs a few batches for the whole page instead of a handful per entry. Only when the entries do not touch.
				const int layers = (pitchY() >= m_itemheight) ? m_content->paintPasses() : 1;
				for (int pass = 0; pass < (layers > 1 ? layers : 1); ++pass)
				{
					if (layers > 1)
					{
						m_content->setPaintPass(pass);
						if (pass > 0)
						{
							m_content->cursorSet(m_top); // back to the first visible entry
							entryrect = eRect(0, 0, size().width(), m_itemheight);
						}
					}
					for (int y = 0, i = 0; i <= m_items_per_page; y += pitchY(), ++i)
					{
						gRegion entry_clip_rect = paint_region & entryrect;

						if (!entry_clip_rect.empty())
							m_content->paint(painter, *style, ePoint(xoffset, y), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);

							/* (we could clip with entry_clip_rect, but
							this shouldn't change the behavior of any
							well behaving content, so it would just
							degrade performance without any gain.) */

						m_content->cursorMove(+1);
						entryrect.moveBy(ePoint(0, pitchY()));
					}
				}
				if (layers > 1)
					m_content->setPaintPass(-1);
				m_content->cursorRestore();
			}
			else if (m_orientation == orHorizontal)
			{
				const bool deferSel = selectionZoomActive();
				bool haveSel = false;
				ePoint selPos;
				for (int x = 0, i = 0; i <= m_items_per_page; x += pitchX(), ++i)
				{
					gRegion entry_clip_rect = paint_region & entryrect;

					if (!entry_clip_rect.empty())
					{
						const bool sel = m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled;
						if (sel && deferSel)
						{
							haveSel = true;
							selPos = ePoint(x, yoffset);
						}
						else
							m_content->paint(painter, *style, ePoint(x, yoffset), sel);
					}

						/* (we could clip with entry_clip_rect, but
						this shouldn't change the behavior of any
						well behaving content, so it would just
						degrade performance without any gain.) */

					m_content->cursorMove(+1);
					entryrect.moveBy(ePoint(pitchX(), 0));
				}
				if (haveSel)
					paintZoomedSelection(painter, *style, m_selected, selPos, false);
				m_content->cursorRestore();
			}
			else
			{
				// row by row: a row is a range of entries (a spanning entry, e.g. a marker, is a row of its own
				// as wide as the whole grid and may be lower than a cell). Empty cells are painted only once the cursor is past the
				// end of the list, so the content clears stale/selected pixels left over from a previous entry
				const int rows = gridRows();
				const int listHeight = size().height();
				const bool deferSel = selectionZoomActive() && !gridSpanAt(m_selected);
				bool haveSel = false;
				ePoint selPos;
				int posy = 0;
				for (int row = m_top; posy < listHeight; ++row)
				{
					const int rowHeight = gridRowHeight(row);
					const int count = row < rows ? gridRowCount(row) : 0;
					const bool spanned = count == 1 && gridSpanAt(gridRowFirst(row));
					for (int c = 0; c < m_max_columns; ++c)
					{
						const int posx = c * pitchX();
						const bool real = c < count;
						if (real || !m_content->cursorValid())
						{
							entryrect = eRect(posx, posy, spanned ? gridSpanWidth() : m_itemwidth, rowHeight);
							gRegion entry_clip_rect = paint_region & entryrect;
							if (!entry_clip_rect.empty())
							{
								const bool sel = m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled;
								if (sel && deferSel && real)
								{
									haveSel = true;
									selPos = ePoint(posx, posy);
								}
								else
									m_content->paint(painter, *style, ePoint(posx, posy), sel);
							}
						}
						if (real)
							m_content->cursorMove(+1);
						if (spanned)
							break;
					}
					posy += rowHeight + m_gap_y;
				}
				if (haveSel)
					paintZoomedSelection(painter, *style, m_selected, selPos, true);

				m_content->cursorRestore();

			}

			// clear/repaint empty/unused space between scrollbar and listboxentrys
			// (showLeft/showTop always reserve the gap; on the default side it only exists while the scrollbar is shown)
			if (m_scrollbar && !isTransparent() && (m_scrollbar_mode == showLeft || m_scrollbar_mode == showTop || m_scrollbar->isVisible()))
			{
				style->setStyle(painter, eWindowStyle::styleListboxNormal);
				if (m_scrollbar_mode == showLeft)
				{
					if (m_scrollbar->isVisible())
					{
						painter.clip(eRect(m_scrollbar->position() + ePoint(m_scrollbar->size().width(), 0), eSize(5,m_scrollbar->size().height())));
					}
					else
					{
						painter.clip(eRect(m_scrollbar->position(), eSize(m_scrollbar->size().width() + 5, m_scrollbar->size().height())));
					}
				}
				else if (m_scrollbar_mode == showTop)
				{
					if (m_scrollbar->isVisible())
					{
						painter.clip(eRect(m_scrollbar->position() + ePoint(0, m_scrollbar->size().height()), eSize(m_scrollbar->size().width(), 5)));
					}
					else
					{
						painter.clip(eRect(m_scrollbar->position(), eSize(m_scrollbar->size().width(), m_scrollbar->size().height() + 5)));
					}
				}
				else if (m_orientation == orVertical)
				{
					painter.clip(eRect(m_scrollbar->position() - ePoint(5,0), eSize(5,m_scrollbar->size().height())));
				}
				else
				{
					painter.clip(eRect(m_scrollbar->position() - ePoint(0,5), eSize(m_scrollbar->size().width(), 5)));
				}
				painter.clear();
				painter.clippop();
			}

			return 0;
		}

		case evtChangedSize:
			recalcSize();
			return eWidget::event(event, data, data2);

		case evtAction:
			if (isVisible() && !isLowered())
			{
				moveSelection((long)data2);
				return 1;
			}
			return 0;
		default:
			return eWidget::event(event, data, data2);
	}
}

void eListbox::recalcSize()
{
	m_content_changed=true;
	m_prev_scrollbar_page=-1;
	if (m_orientation == orVertical)
	{
		if (m_content)
			m_content->setSize(eSize(size().width(), m_itemheight));
		// with gaps only the tiles need a gap in between, the last one may end at the edge; the focused slot of a
		// carousel may be larger than the others
		const int ext = carouselActive() ? carouselFocusExtent() : m_itemheight;
		m_items_per_page = size().height() >= ext ? 1 + (size().height() - ext) / pitchY() : 0;
	}
	else if (m_orientation == orHorizontal)
	{
		if (m_content)
			m_content->setSize(eSize(m_itemwidth, size().height()));
		const int ext = carouselActive() ? carouselFocusExtent() : m_itemwidth;
		m_items_per_page = size().width() >= ext ? 1 + (size().width() - ext) / pitchX() : 0;
	}
	else
	{
		if (m_content)
			m_content->setSize(eSize(m_itemwidth, m_itemheight));

		int w = size().width();
		int h = size().height();

		m_max_columns = (w + m_gap_x) / pitchX();
		m_max_rows = (h + m_gap_y) / pitchY();
		m_items_per_page = m_max_columns * m_max_rows;
		m_items_per_page_with_partials = m_max_columns * ((h + pitchY() - 1) / pitchY());
		if (m_content)
			m_content->setSpanWidth(gridSpanWidth());
	}
	m_grid_dirty = true;

	if (m_items_per_page < 0) /* TODO: whyever - our size could be invalid, or itemheigh could be wrongly specified. */
		m_items_per_page = 0;

	if (m_max_columns < 0)
		m_max_columns = 0;
	if (m_max_rows < 0)
		m_max_rows = 0;

	moveSelection(justCheck);
}

bool iListboxContent::ellipsisEnabled()
{
	return !m_listbox || m_listbox->getEllipsis();
}

void eListbox::setEllipsis(int en)
{
	if (m_ellipsis != (en != 0))
	{
		m_ellipsis = en != 0;
		invalidate();
	}
}

void eListbox::setItemHeight(int h)
{
	if (h)
		m_itemheight = h;
	else
		m_itemheight = 20;
	recalcSize();
}
void eListbox::setItemWidth(int w)
{
	if (w)
		m_itemwidth = w;
	else
		m_itemwidth = 20;
	recalcSize();
}

void eListbox::setSelectionEnable(int en)
{
	if (m_selection_enabled == en)
		return;
	m_selection_enabled = en;
	/* an enlarged selection reaches over its neighbours: the old (or new) enlarged area is wider than the entry's own
	   cell, so redrawing just the cell would leave artefacts when the selection is switched off/on */
	const bool zoomConfigured = (carouselActive() && m_carousel_zoom > 100) ||
		(m_selection_zoom > 100 && (m_orientation == orHorizontal || m_orientation == orGrid));
	if (zoomConfigured)
	{
		if (m_content)
			m_content->resetClip();
		invalidate();
		return;
	}
	entryChanged(m_selected); /* redraw current entry */
}

void eListbox::entryAdded(int index)
{
	m_grid_dirty = true;
	if (carouselActive())
	{
		if (index <= m_selected)
			++m_selected;
		moveSelection(justCheck);
		invalidate();
		return;
	}
	if (m_content && m_items_per_page && (m_content->size() % m_items_per_page) == 1)
		m_content_changed=true;
	/* manage our local pointers. when the entry was added before the current position, we have to advance. */

		/* we need to check <= - when the new entry has the (old) index of the cursor, the cursor was just moved down. */
	if (index <= m_selected)
		++m_selected;
	if (m_orientation == orVertical)
	{
		if (index <= m_top)
			++m_top;
	}
	else
	{
		if (index <= m_left)
			++m_left;
	}

		/* we have to check wether our current cursor is gone out of the screen. */
		/* moveSelection will check for this case */
	moveSelection(justCheck);

		/* now, check if the new index is visible. */
	if (m_orientation == orVertical)
	{
		if ((m_top <= index) && (gridHasSpans() || index < (m_top + m_items_per_page)))
		{
				/* todo, calc exact invalidation... */
			invalidate();
		}
	}
	else
	{
		if ((m_left <= index) && (index < (m_left + m_items_per_page)))
		{
				/* todo, calc exact invalidation... */
			invalidate();
		}
	}
}

void eListbox::entryRemoved(int index)
{
	m_grid_dirty = true;
	if (m_content && m_items_per_page && (m_content->size() % m_items_per_page) == 1)
		m_content_changed=true;

	if (index == m_selected && m_content)
		m_selected = m_content->cursorGet();

	if (m_content && m_content->cursorGet() >= m_content->size())
		moveSelection(moveUp);
	else
		moveSelection(justCheck);

	if (carouselActive())
	{
		invalidate();
		return;
	}
	if (m_orientation == orVertical)
	{
		if ((m_top <= index) && (gridHasSpans() || index < (m_top + m_items_per_page)))
		{
				/* todo, calc exact invalidation... */
			invalidate();
		}
	}
	else
	{
		if ((m_left <= index) && (index < (m_left + m_items_per_page)))
		{
				/* todo, calc exact invalidation... */
			invalidate();
		}
	}
}

void eListbox::entryChanged(int index)
{
	if (carouselActive() || (selectionZoomActive() && index == m_selected))
	{
		// with wrap-around an entry can appear in more than one slot, and a zoomed selection overlaps its neighbours: just redraw
		invalidate();
		return;
	}
	if (m_orientation == orVertical)
	{
		if ((m_top <= index) && (gridHasSpans() ? gridRowTop(index) - gridRowTop(m_top) < size().height() : index <= (m_top + m_items_per_page)))
		{
			gRegion inv = verticalRect(index);
			invalidate(inv);
		}
	}
	else if (m_orientation == orHorizontal)
	{
		if ((m_left <= index) && (index <= (m_left + m_items_per_page + 1)))
		{
			gRegion inv = eRect(pitchX() * (index-m_left), 0, m_itemwidth, size().height());
			invalidate(inv);
		}
	}
	else
	{
		// orGrid: unlike the orVertical/orHorizontal branches above, this had
		// no "is index actually part of the currently displayed page" check
		// before computing/invalidating a rect for it. A stale entryChanged()
		// for an index that has since scrolled off-page (e.g. a content
		// provider's async thumbnail-loaded callback firing for a row the
		// user has since scrolled past - see eListbox::redrawItemByIndex())
		// still fell into this branch, and getItemPostion() has no notion of
		// "off-page" either - it maps ANY index through the current page's
		// (m_top, m_max_columns) arithmetic regardless of how far off it
		// actually is, so a stale index some multiple of a page-width away
		// can alias right back onto a real, currently visible cell's
		// position. That invalidates and repaints a cell that was never
		// actually dirty, and each such repaint re-invokes the content
		// provider's build callback, which is exactly the kind of spurious,
		// unbounded extra work orVertical/orHorizontal already guard against
		// by simply not invalidating for an off-page index at all.
		int lastRow = m_top;
		for (int y = 0; y < size().height(); ++lastRow)
			y += gridRowHeight(lastRow) + m_gap_y;
		int gridStart = gridRowFirst(m_top);
		int gridEnd = gridRowFirst(lastRow);
		if ((index >= gridStart) && (index < gridEnd))
		{
			gRegion inv = eRect(getItemPostion(index), gridItemSize(index));
			invalidate(inv);
		}
	}
}

void eListbox::entryReset(bool selectionHome)
{
	m_grid_dirty = true;
	m_content_changed = true;
	m_prev_scrollbar_page = -1;
	int oldsel;

	if (selectionHome)
	{
		if (m_content)
			m_content->cursorHome();
		m_top = 0;
		m_left = 0;
		m_selected = 0;
	}

	if (m_content && (m_selected >= m_content->size()))
	{
		if (m_content->size())
			m_selected = m_content->size() - 1;
		else
			m_selected = 0;
		m_content->cursorSet(m_selected);
	}

	oldsel = m_selected;
	moveSelection(justCheck);
		/* if oldsel != m_selected, selectionChanged was already
		   emitted in moveSelection. we want it in any case, so otherwise,
		   emit it now. */
	if (oldsel == m_selected)
		/* emit */ selectionChanged();
	invalidate();
}

void eListbox::setFont(gFont *font)
{
	m_style.m_font = font;
}

void eListbox::setSecondFont(gFont *font)
{
	m_style.m_secondfont = font;
}

void eListbox::setVAlign(int align)
{
	m_style.m_valign = align;
}

void eListbox::setHAlign(int align)
{
	m_style.m_halign = align;
}

void eListbox::setTextOffset(const ePoint &textoffset)
{
	m_style.m_text_offset = textoffset;
}

void eListbox::setBackgroundColor(const gRGB &col)
{
	m_style.m_background_color = col;
	m_style.m_background_color_set = 1;
}

void eListbox::setBackgroundColorSelected(gRGB &col)
{
	m_style.m_background_color_selected = col;
	m_style.m_background_color_selected_set = 1;
}

void eListbox::setForegroundColor(gRGB &col)
{
	m_style.m_foreground_color = col;
	m_style.m_foreground_color_set = 1;
}

void eListbox::setForegroundColorSelected(gRGB &col)
{
	m_style.m_foreground_color_selected = col;
	m_style.m_foreground_color_selected_set = 1;
}

void eListbox::setBorderColor(const gRGB &col)
{
	m_style.m_border_color = col;
}

void eListbox::setBorderWidth(int size)
{
	m_style.m_border_size = size;
	if (m_scrollbar) m_scrollbar->setBorderWidth(size);
}

void eListbox::setBackgroundPicture(ePtr<gPixmap> &pm)
{
	m_style.m_background = pm;
}

void eListbox::setSelectionPicture(ePtr<gPixmap> &pm)
{
	m_style.m_selection = pm;
}

void eListbox::setSelectionPictureLarge(ePtr<gPixmap> &pm)
{
	m_style.m_selection_large = pm;
}

void eListbox::setSelectionBorderHidden()
{
	m_style.m_border_set = 1;
}

void eListbox::setScrollbarWidth(int size)
{
	m_scrollbar_width = size;
}

void eListbox::setScrollbarHeight(int size)
{
	m_scrollbar_height = size;
}

void eListbox::setScrollbarBorderWidth(int size)
{
	m_style.m_scrollbarborder_width = size;
	if (m_scrollbar) m_scrollbar->setBorderWidth(size);
}

void eListbox::setScrollbarBorderColor(const gRGB &col)
{
	m_style.m_scrollbarborder_color = col;
	m_style.m_scrollbarborder_color_set = 1;
	if (m_scrollbar) m_scrollbar->setBorderColor(col);
}

void eListbox::setScrollbarForegroundColor(const gRGB &col)
{
	m_style.m_scrollbarforeground_color = col;
	m_style.m_scrollbarforeground_color_set = 1;
	if (m_scrollbar) m_scrollbar->setForegroundColor(col);
}

void eListbox::setScrollbarBackgroundColor(const gRGB &col)
{
	m_style.m_scrollbarbackground_color = col;
	m_style.m_scrollbarbackground_color_set = 1;
	if (m_scrollbar) m_scrollbar->setBackgroundColor(col);
}

void eListbox::setScrollbarPixmap(ePtr<gPixmap> &pm)
{
	m_scrollbarpixmap = pm;
	if (m_scrollbar && m_scrollbarpixmap) m_scrollbar->setPixmap(pm);
}

void eListbox::setScrollbarBackgroundPixmap(ePtr<gPixmap> &pm)
{
	m_scrollbarbackgroundpixmap = pm;
	if (m_scrollbar && m_scrollbarbackgroundpixmap) m_scrollbar->setBackgroundPixmap(pm);
}

void eListbox::setHeaderFont(gFont *font)
{
	m_style.m_header_font = font;
}

void eListbox::setHeaderForegroundColor(const gRGB &col)
{
	m_style.m_header_foreground_color = col;
	m_style.m_header_foreground_color_set = 1;
}

void eListbox::setHeaderBackgroundColor(const gRGB &col)
{
	m_style.m_header_background_color = col;
	m_style.m_header_background_color_set = 1;
}

void eListbox::setHeaderLineColor(const gRGB &col)
{
	m_style.m_header_line_color = col;
	m_style.m_header_line_color_set = 1;
}

void eListbox::setHeaderLineThickness(int thickness)
{
	m_style.m_header_line_thickness = thickness;
}

void eListbox::setHeaderLineStyle(int style)
{
	m_style.m_header_line_style = style;
	invalidate();
}

void eListbox::setHeaderLineMargin(int margin)
{
	m_style.m_header_line_margin = std::max(0, margin);
	invalidate();
}

void eListbox::setHeaderVAlign(int align)
{
	m_style.m_header_valign = align;
}

void eListbox::setHeaderHAlign(int align)
{
	m_style.m_header_halign = align;
}

void eListbox::setHeaderTextOffset(const ePoint &textoffset)
{
	m_style.m_header_text_offset = textoffset;
	m_style.m_header_text_offset_set = 1;
}

/* the height of header entries: the rows are laid out again with it */
void eListbox::setHeaderHeight(int height)
{
	m_style.m_header_height = height > 0 ? height : 0;
	m_grid_dirty = true;
	m_content_changed = true;
	m_prev_scrollbar_page = -1;
	if (m_content)
		moveSelection(justCheck);
	invalidate();
}

void eListbox::invalidate(const gRegion &region)
{
	gRegion tmp(region);
	if (m_content)
		m_content->updateClip(tmp);
	eWidget::invalidate(tmp);
}

struct eListboxStyle *eListbox::getLocalStyle(void)
{
		/* transparency is set directly in the widget */
	m_style.m_transparent_background = isTransparent();
	return &m_style;
}

void eListbox::setItemCornerRadiusInternal(int radius, uint8_t edges, int index)
{
	m_style.m_itemCornerRadius[index] = radius;
	m_style.m_itemCornerRadiusEdges[index] = edges;

	// Per-item rounding lives entirely in m_style, never in this widget's own
	// m_cornerRadius, so eWidgetDesktop::calcWidgetClipRegion has no way to
	// know each row's antialiased corners need a real backdrop behind them -
	// see setNeedsBackdrop()'s comment (ewidget.h) for what goes wrong
	// without this.
	setNeedsBackdrop(m_style.m_itemCornerRadius[0] != 0 || m_style.m_itemCornerRadius[1] != 0);
}

void eListbox::setItemCornerRadius(int radius, uint8_t edges)
{
	for (int x = 0; x < 2; x++)
	{
		setItemCornerRadiusInternal(radius, edges, x);
	}
}

void eListbox::setItemCornerRadiusSelected(int radius, uint8_t edges)
{
	setItemCornerRadiusInternal(radius, edges, 1);
}

void eListbox::setItemGradientInternal(uint8_t index, const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend)
{
	m_style.m_gradient_colors[index] = {startcolor, midcolor, endcolor};
	m_style.m_gradient_direction[index] = direction;
	m_style.m_gradient_alphablend[index] = alphablend;
	m_style.m_gradient_set[index] = true;
	invalidate();
}

void eListbox::setItemGradient(const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend)
{
	setItemGradientInternal(0, startcolor, midcolor, endcolor, direction, alphablend);
}

void eListbox::setItemGradientSelected(const gRGB &startcolor, const gRGB &midcolor, const gRGB &endcolor, uint8_t direction, bool alphablend)
{
	setItemGradientInternal(1, startcolor, midcolor, endcolor, direction, alphablend);
}
