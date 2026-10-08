#include <lib/gui/elistbox.h>
#include <lib/gui/elistboxcontent.h>
#include <lib/gui/eslider.h>
#include <lib/actions/action.h>
#include <algorithm>
#include <cstdlib>
#include <cmath>
#ifdef HAVE_EGL_ANIMATION
#include <lib/gdi/egl/ganimation.h>
#endif

int eListbox::defaultItemRadius[2] = {0,0};
int eListbox::defaultItemRadiusEdges[2] = {0,0};

eListbox::eListbox(eWidget *parent) :
	eWidget(parent), m_scrollbar_mode(showNever), m_prev_scrollbar_page(-1),
	m_content_changed(false), m_enabled_wrap_around(false), m_scrollbar_width(10), m_scrollbar_height(10),
	m_top(0), m_left(0), m_max_columns(0), m_max_rows(0), m_selected(0), m_itemheight(25), m_itemwidth(25), m_orientation(orVertical),
	m_items_per_page(0), m_items_per_page_with_partials(0), m_selection_enabled(1), m_native_keys_bound(false), m_scrollbar(nullptr)
{
	memset(static_cast<void*>(&m_style), 0, sizeof(m_style));
	m_style.m_text_offset = ePoint(1,1);

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
	m_orientation = orientation;
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

void eListbox::setContent(iListboxContent *content)
{
	m_content = content;
	if (content)
		m_content->setListbox(this);
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
	if (m_orientation == orVertical)
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
	int oldRow = (isGrid && m_max_columns != 0) ? oldsel / m_max_columns : 0;
	int oldColumn = (isGrid && m_max_columns != 0) ? oldsel % m_max_columns : 0;

	switch (r_dir) {
		case moveEnd:
			if (isGrid)
			{
				int newRow = oldRow;
				do
				{
					m_content->cursorMove(1);
					newsel = m_content->cursorGet();
					newRow = newsel / m_max_columns;
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
					int current = oldsel;

					do {
						// Move to previous row in same column
						current -= m_max_columns;

						if (current < 0) {
							// Wrap to bottom of same column if enabled
							if (m_enabled_wrap_around) {
								int lastRow = (m_content->size() - 1) / m_max_columns;
								current = lastRow * m_max_columns + oldColumn;

								// Clamp if out of bounds
								if (current >= m_content->size())
									current -= m_max_columns;
							} else {
								break;
							}
						}

						m_content->cursorSet(current);

						if (!m_content->cursorValid()) {
							// If cursor is invalid, reset or wrap
							if (m_enabled_wrap_around) {
								current = oldColumn;
							} else {
								m_content->cursorSet(oldsel);
								break;
							}
						}

						// Exit loop if item is selectable
						if (m_content->currentCursorSelectable())
							break;

					} while (current != oldsel);

					// Final selection
					newsel = m_content->cursorGet();
					
				}
				else
				{
					// Move left within the current row, wrapping to the row's last column if enabled
					int rowStart = oldsel - oldColumn;
					int rowEnd = rowStart + m_max_columns - 1;
					if (rowEnd > m_content->size() - 1)
						rowEnd = m_content->size() - 1;
					int current = oldsel;

					do
					{
						--current;
						if (current < rowStart)
						{
							if (!m_enabled_wrap_around)
							{
								current = oldsel;
								m_content->cursorSet(current);
								break;
							}
							current = rowEnd;
						}
						m_content->cursorSet(current);
					}
					while (current != oldsel && !m_content->currentCursorSelectable());

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
					newRow = newsel / m_max_columns;
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
					int current = oldsel;
					int totalRows = (m_content->size() + m_max_columns - 1) / m_max_columns;

					do {
						int itemRow = current / m_max_columns;
						bool isLastRow = itemRow == (totalRows - 1);
						current += m_max_columns;  // Move to next row in same column

						if (current >= m_content->size()) {
							// Wrap to top of same column if enabled
							if (m_enabled_wrap_around)
							{
								if (!isLastRow)
								{
									current = m_content->size() - 1;
								}
								else
									current = oldColumn;
							}
							else
								if (!isLastRow)
								{
									current = m_content->size() - 1;
								}
								else
									break;
						}

						m_content->cursorSet(current);

						if (!m_content->cursorValid()) {
							// If cursor is invalid, reset or wrap
							if (m_enabled_wrap_around)
								current = oldColumn;
							else {
								m_content->cursorSet(oldsel);
								break;
							}
						}

						// Exit loop if item is selectable
						if (m_content->currentCursorSelectable())
							break;

					} while (current != oldsel);

					// Final selection
					newsel = m_content->cursorGet();
				}
				else
				{
					// Move right within the current row, wrapping to the row's first column if enabled
					int rowStart = oldsel - oldColumn;
					int rowEnd = rowStart + m_max_columns - 1;
					if (rowEnd > m_content->size() - 1)
						rowEnd = m_content->size() - 1;
					int current = oldsel;

					do
					{
						++current;
						if (current > rowEnd)
						{
							if (!m_enabled_wrap_around)
							{
								current = oldsel;
								m_content->cursorSet(current);
								break;
							}
							current = rowStart;
						}
						m_content->cursorSet(current);
					}
					while (current != oldsel && !m_content->currentCursorSelectable());

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
	// Smooth scrolling (a skin.ani <scrolltime>): the list moves by single rows, just far enough to keep
	// the selection in view, instead of flipping a whole page.
	const bool smooth = m_smooth_scroll && m_content->size() > 0 && (m_orientation == orHorizontal || m_orientation == orVertical)
#ifdef HAVE_EGL_ANIMATION
		&& ganim::listsEnabled()
#endif
		;
	if (smooth)
	{
		int &first = m_orientation == orHorizontal ? m_left : m_top;
		if (m_selected < first)
			first = m_selected;
		else if (m_selected >= first + m_items_per_page)
			first = m_selected - m_items_per_page + 1;
		first = std::max(0, std::min(first, std::max(0, m_content->size() - m_items_per_page)));
	}
	else if (m_orientation == orHorizontal)
		m_left = m_selected - (m_selected % m_items_per_page);
	else if (m_orientation == orVertical)
		m_top = m_selected - (m_selected % m_items_per_page);
	else
		m_top = (m_selected / m_items_per_page) * m_max_rows;

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

#ifdef HAVE_EGL_ANIMATION
	if (oldsel != m_selected)
		startRowAnimation(oldsel);
#endif

	updateScrollBar();

	if (m_orientation == orVertical)
	{
		if (m_top != oldtop){
			sendPageAnimation(r_dir, m_top, oldtop, false);
			invalidate();
		}
		else if (m_selected != oldsel)
		{
#ifdef HAVE_EGL_ANIMATION
			if (m_scroll_run)
				invalidate(); // all rows are off their place while the scroll animation runs
			else
#endif
			{
				/* redraw the old and newly selected */
				gRegion inv = eRect(0, m_itemheight * (m_selected-m_top), size().width(), m_itemheight);
				inv |= eRect(0, m_itemheight * (oldsel-m_top), size().width(), m_itemheight);
				invalidate(inv);
			}
		}
	}
	else if (m_orientation == orGrid)
	{
		if (m_top != oldtop){
			sendPageAnimation(r_dir, m_top, oldtop, false);
			invalidate();
		}
		else if (m_selected != oldsel)
		{
			/* redraw the old and newly selected */
			gRegion inv = eRect(getItemPostion(m_selected), eSize(m_itemwidth, m_itemheight));
			inv |= eRect(getItemPostion(oldsel), eSize(m_itemwidth, m_itemheight));
			invalidate(inv);
		}
	}
	else
	{
		if (m_left != oldleft){
			sendPageAnimation(r_dir, m_left, oldleft, true);
			invalidate();
		}
		else if (m_selected != oldsel)
		{
			/* redraw the old and newly selected */
			gRegion inv = eRect(m_itemwidth * (m_selected-m_left), 0, m_itemwidth, size().height());
			inv |= eRect(m_itemwidth * (oldsel-m_left), 0, m_itemwidth, size().height());
			invalidate(inv);
		}
	}
}

void eListbox::setFocusAnimation(int focus_id, int unfocus_id)
{
#ifdef HAVE_EGL_ANIMATION
	m_focus_anim = focus_id;
	m_unfocus_anim = unfocus_id;
	if (!m_anim_timer)
	{
		m_anim_timer = eTimer::create(eApp);
		CONNECT(m_anim_timer->timeout, eListbox::animationTick);
	}
	invalidate();
#endif
}

#ifdef HAVE_EGL_ANIMATION
static float msSince(const std::chrono::steady_clock::time_point &t0, const std::chrono::steady_clock::time_point &now)
{
	return std::chrono::duration<float, std::milli>(now - t0).count();
}

// The selection moved from `oldsel` to m_selected: the new row starts its focus animation, the old row
// its unfocus animation (only visible while it is still on the page).
void eListbox::startRowAnimation(int oldsel)
{
	if (!m_anim_timer || !ganim::listsEnabled() || (!m_focus_anim && !m_unfocus_anim))
		return;
	const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
	m_anim_new_start = now;
	m_anim_old_row = (m_unfocus_anim && oldsel != m_selected) ? oldsel : -1;
	m_anim_old_start = now;
	m_anim_timer->start(16, true);
}

// Most rows a smooth scroll moves in one go (key repeats can pile up); bigger jumps are not animated.
static const int kMaxScrollRows = 3;

// The scroll animation of the skin (<scrolltime>): returns false when there is none.
static bool scrollAnimationParams(int anim_id, float &duration_ms, ganim::Tween &tween, ganim::Easing &easing)
{
	std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(anim_id);
	if (!a || a->effects.empty())
		return false;
	duration_ms = std::max(1.0f, a->durationMs());
	tween = a->effects[0].tween;
	easing = a->effects[0].easing;
	return true;
}

// Current vertical offset in pixels of all rows (0 when no scroll animation runs).
int eListbox::scrollOffset()
{
	if (!m_scroll_run)
		return 0;
	float ms;
	ganim::Tween tween;
	ganim::Easing easing;
	if (!scrollAnimationParams(m_scroll_anim, ms, tween, easing))
	{
		m_scroll_run = false;
		return 0;
	}
	const float t = msSince(m_scroll_start, std::chrono::steady_clock::now()) / ms;
	if (t >= 1.0f)
	{
		m_scroll_run = false;
		return 0;
	}
	return (int)std::lround(m_scroll_off0 * (1.0f - ganim::tweenValue(tween, easing, t)));
}

// The first visible row moved by `delta_rows` (new - old): the rows are now laid out for the new first row,
// start them where they were and let them ease into place. A scroll that is still running continues from
// where it is, so a held key gives one continuous motion.
bool eListbox::startScrollAnimation(int delta_rows)
{
	float ms;
	ganim::Tween tween;
	ganim::Easing easing;
	if (!m_anim_timer || m_itemheight <= 0 || !scrollAnimationParams(m_scroll_anim, ms, tween, easing))
		return false;
	// the paint loop draws the rows above the page (positive offset) or below it (negative) that slide into view,
	// for up to kMaxScrollRows rows
	const float max_off = (float)(kMaxScrollRows * m_itemheight);
	const float off = std::max(-max_off, std::min(max_off, (float)scrollOffset() + (float)(delta_rows * m_itemheight)));
	m_scroll_off0 = off;
	const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
	// Only an isolated key press waits for the render thread (see animationTick()); with a key held the queue is
	// never empty, and waiting would leave the list behind the selection.
	m_scroll_synced = m_scroll_run || msSince(m_scroll_requested, now) < 400.0f;
	m_scroll_start = m_scroll_requested = now;
	m_scroll_run = true;
	m_anim_timer->start(16, true);
	return true;
}

void eListbox::animationTick()
{
	const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
	// The key press that started a scroll queues more frames (the list and everything else that follows the
	// selection) than the render thread has drawn yet, so a clock started at the key press is over before the
	// first frame shows. Hold the animation at its start until the queue has drained (at most 400 ms), then
	// let it run; the effect of the newly selected row starts with it.
	if (m_scroll_run && !m_scroll_synced)
	{
		if (gRC::getInstance() && gRC::getInstance()->pendingOpcodes() > 60 && msSince(m_scroll_requested, now) < 400.0f)
		{
			m_scroll_start = now;
			m_anim_new_start = now;
			m_anim_timer->start(16, true);
			return;
		}
		m_scroll_synced = true;
		m_scroll_start = now;
		m_anim_new_start = now;
	}
	const int pending = gRC::getInstance() ? gRC::getInstance()->pendingOpcodes() : 0;
	// The same for the rows coming in when the list is shown: the clock starts when the render thread has drawn
	// what was queued when the screen opened (at most 400 ms), until then the rows wait at their start state.
	if (m_open_state == 2)
	{
		if (pending > 60 && msSince(m_open_first_paint, now) < 400.0f)
		{
			m_open_start = now;
			m_anim_timer->start(16, true);
			return;
		}
		m_open_state = 3;
		m_open_start = now;
	}
	bool running = false;
	bool opening = false; // the rows are coming in: repaint the whole list
	if (m_open_state == 3)
	{
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_open_anim);
		opening = true;
		if (a && msSince(m_open_start, now) < a->durationMs() + (float)m_items_per_page * a->stagger_ms)
			running = true;
		else
			m_open_state = 4; // this frame paints the final state
	}
	const bool scrolling = m_scroll_run || opening; // every row moves: repaint the whole list
	if (m_scroll_run)
	{
		scrollOffset(); // ends the animation when it is over, the repaint below then draws the final place
		if (m_scroll_run)
			running = true;
	}
	if (m_focus_anim)
	{
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_focus_anim);
		if (a && msSince(m_anim_new_start, now) < a->durationMs())
			running = true;
	}
	if (m_anim_old_row >= 0 && m_unfocus_anim)
	{
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_unfocus_anim);
		if (a && msSince(m_anim_old_start, now) < a->durationMs())
			running = true;
	}

	// The render thread is still busy with the last frame (a full list is some 170 opcodes): another one
	// would only queue up and block the main thread when the queue is full, which stalls key handling too.
	// Skip this frame; all animations follow the clock, so nothing gets slower, it just shows less frames.
	// A scroll frame repaints the whole list (some 190 opcodes, about 45 ms on the render thread): only paint one
	// when the queue is nearly empty, else the frames reach the screen late and the animation is over before they
	// are seen. The small frames of the row effects may queue a little.
	if (running && pending > (scrolling ? 60 : 250))
	{
		m_anim_timer->start(16, true);
		return;
	}

	if (scrolling)
		invalidate();
	// Repaint the animated rows and their neighbours (a zoomed row overlaps them).
	else if (m_orientation == orVertical || m_orientation == orHorizontal)
	{
		int first = m_selected, last = m_selected;
		if (m_anim_old_row >= 0)
		{
			first = std::min(first, m_anim_old_row);
			last = std::max(last, m_anim_old_row);
		}
		const int top = m_orientation == orVertical ? m_top : m_left;
		const int item = m_orientation == orVertical ? m_itemheight : m_itemwidth;
		const int from = std::max(0, first - 1 - top), to = std::min(m_items_per_page + 1, last + 2 - top);
		if (to > from && item > 0)
		{
			if (m_orientation == orVertical)
				invalidate(gRegion(eRect(0, from * item, size().width(), (to - from) * item)));
			else
				invalidate(gRegion(eRect(from * item, 0, (to - from) * item, size().height())));
		}
	}
	else
		invalidate();

	if (running)
		m_anim_timer->start(16, true);
	else
		m_anim_old_row = -1; // the invalidate above already paints the final state
}

bool eListbox::rowTransform(int index, const eRect &row, float &sx, float &sy, float &tx, float &ty, float &alpha)
{
	if (!ganim::listsEnabled())
		return false;
	const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
	ganim::Xf xf;
	bool opening = false;
	if (m_open_state == 2 || m_open_state == 3)
	{
		// the rows come in one after the other: row k (counted from the top of the page) starts k * stagger later
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_open_anim);
		if (a)
		{
			const int first_index = m_orientation == orGrid ? m_max_columns * m_top : (m_orientation == orHorizontal ? m_left : m_top);
			const float elapsed = (m_open_state == 2 ? 0.0f : msSince(m_open_start, now)) - (float)std::max(0, index - first_index) * a->stagger_ms;
			xf = ganim::evaluateAnimation(*a, std::max(0.0f, elapsed), row.x(), row.y(), row.width(), row.height());
			opening = elapsed < a->durationMs();
		}
	}
	if (opening)
	{
		// The selected one is already zoomed while it comes in: the focus effect (applied the whole time the row is
		// selected) is combined with the entrance, else it would pop when the entrance ends.
		std::shared_ptr<const ganim::Animation> f = (index == m_selected && m_focus_anim && m_selection_enabled) ? ganim::getAnimation(m_focus_anim) : nullptr;
		if (f)
		{
			const ganim::Xf inner = ganim::evaluateAnimation(*f, msSince(m_anim_new_start, now), row.x(), row.y(), row.width(), row.height());
			xf.tx = xf.sx * inner.tx + xf.tx;
			xf.ty = xf.sy * inner.ty + xf.ty;
			xf.sx *= inner.sx;
			xf.sy *= inner.sy;
			xf.alpha *= inner.alpha;
		}
	}
	else if (!m_selection_enabled)
		return false;
	else if (index == m_selected && m_focus_anim)
	{
		// stays applied for as long as the row is selected (the start state of a fresh list is "long ago")
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_focus_anim);
		if (!a)
			return false;
		xf = ganim::evaluateAnimation(*a, msSince(m_anim_new_start, now), row.x(), row.y(), row.width(), row.height());
	}
	else if (index == m_anim_old_row && m_unfocus_anim)
	{
		std::shared_ptr<const ganim::Animation> a = ganim::getAnimation(m_unfocus_anim);
		if (!a)
			return false;
		const float elapsed = msSince(m_anim_old_start, now);
		if (elapsed >= a->durationMs())
			return false;
		xf = ganim::evaluateAnimation(*a, elapsed, row.x(), row.y(), row.width(), row.height());
	}
	else
		return false;
	if (xf.identity())
		return false;
	// The transformed row is clipped to the list (that is all that gets invalidated), which would cut off the
	// rounded corners of a row filling the list. A zoomed row therefore never grows beyond the list (a full width
	// row does not zoom at all), and is moved inwards where it would stick out, e.g. a cell at the edge of a grid
	// zooms with its outer edges staying in place.
	if (xf.sx > 1.0f || xf.sy > 1.0f)
	{
		const ePoint abs = getAbsolutePosition();
		const float W = (float)size().width(), H = (float)size().height();
		const float cx = row.x() + row.width() / 2.0f, cy = row.y() + row.height() / 2.0f;
		float ncx = xf.sx * cx + xf.tx, ncy = xf.sy * cy + xf.ty;
		float s = std::min(xf.sx, xf.sy);
		s = std::min(s, W / (float)std::max(1, row.width()));
		s = std::min(s, H / (float)std::max(1, row.height()));
		s = std::max(s, 1.0f);
		const float hw = s * row.width() / 2.0f, hh = s * row.height() / 2.0f;
		ncx = std::max(abs.x() + hw, std::min(abs.x() + W - hw, ncx));
		ncy = std::max(abs.y() + hh, std::min(abs.y() + H - hh, ncy));
		xf.sx = xf.sy = s;
		xf.tx = ncx - s * cx;
		xf.ty = ncy - s * cy;
		if (xf.identity())
			return false;
	}
	sx = xf.sx;
	sy = xf.sy;
	tx = xf.tx;
	ty = xf.ty;
	alpha = xf.alpha;
	return true;
}
#endif

void eListbox::setOpenAnimation(int anim_id)
{
#ifdef HAVE_EGL_ANIMATION
	m_open_anim = anim_id;
	m_open_state = anim_id > 0 ? 1 : 0;
	if (anim_id > 0 && !m_anim_timer)
	{
		m_anim_timer = eTimer::create(eApp);
		CONNECT(m_anim_timer->timeout, eListbox::animationTick);
	}
#endif
}

void eListbox::setScrollAnimation(int anim_id, bool smooth)
{
#ifdef HAVE_EGL_ANIMATION
	m_scroll_anim = anim_id;
	m_smooth_scroll = smooth;
	if (!m_anim_timer)
	{
		m_anim_timer = eTimer::create(eApp);
		CONNECT(m_anim_timer->timeout, eListbox::animationTick);
	}
#endif
}

// The first visible row (column) changed: a page, or a single row with smooth scrolling, and the whole
// list is redrawn at once; let the DC slide the old content out and the new one in (EGL list animation,
// see doc/ANIMATIONS_PROPOSAL.md). The hint goes out before the invalidate()/repaint.
void eListbox::sendPageAnimation(long r_dir, int new_first, int old_first, bool horizontal)
{
#ifdef HAVE_EGL_ANIMATION
	// Positioning the list on an entry (opening it, selecting an index) is a jump, not a scroll.
	if (r_dir == justCheck)
	{
		m_scroll_run = false;
		return;
	}
	// A few rows in a vertical list are scrolled by painting the rows with an offset. Never with a snapshot of
	// the list (a slow read back on some GPUs, it made every page flip take 300 ms and more): larger jumps
	// (page up/down) just flip.
	if (!horizontal)
	{
		if (!(m_orientation == orVertical && m_smooth_scroll && ganim::listsEnabled() && std::abs(new_first - old_first) <= kMaxScrollRows && startScrollAnimation(new_first - old_first)))
			m_scroll_run = false;
		return;
	}
	m_scroll_run = false;
#endif
	const bool fallbackBackwards = new_first < old_first;
	// moving by exactly one row (smooth scrolling) slides by one row, anything else by the whole list
	const int step = (m_smooth_scroll && std::abs(new_first - old_first) == 1) ? (horizontal ? m_itemwidth : m_itemheight) : 0;
	bool backwards;
	switch (r_dir)
	{
		case moveUp:
		case moveTop:
		case pageUp:
		case prevItem:
		case prevPage:
		case moveStart:
		case moveStartTop:
			backwards = true;
			break;
		case moveDown:
		case moveEnd:
		case pageDown:
		case nextItem:
		case nextPage:
			backwards = false;
			break;
		default:
			backwards = fallbackBackwards;
			break;
	}
	sendShowItem((horizontal ? 2 : 1) * (backwards ? -1 : 1), m_scroll_anim, step);
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
		entries = (m_content->size() + m_max_columns - 1) / m_max_columns;

	int maxItems = (m_orientation == orGrid) ? m_max_rows : m_items_per_page;

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
			if (entries > m_items_per_page)
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
				m_content->setSize(eSize(m_itemwidth, m_itemwidth));

			m_scrollbar->hide();
		}
	}
	if (maxItems && entries)
	{
		int topleft = m_orientation == orVertical || m_orientation == orGrid ? m_top : m_left;

		int curVisiblePage = m_smooth_scroll ? topleft : topleft / maxItems; // smooth scrolling moves the thumb row by row
		if (m_prev_scrollbar_page != curVisiblePage)
		{
			m_prev_scrollbar_page = curVisiblePage;
			int pages = entries / maxItems;
			if ((pages*maxItems) < entries)
				++pages;
			int start=(topleft*100)/(pages*maxItems);
			int vis=(maxItems*100+pages*maxItems-1)/(pages*maxItems);
			if (vis < 3)
				vis=3;
			m_scrollbar->setStartEnd(start,start+vis);
		}
	}
}

int eListbox::getEntryTop()
{
	if (m_orientation == orVertical || m_orientation == orGrid)
	{
		return (m_selected - m_top) * m_itemheight;
	}
	else
	{
		return (m_selected - m_left) * m_itemwidth;
	}
}

ePoint eListbox::getItemPostion(int index)
{
	int posx = 0, posy = 0;

	if (m_orientation == orGrid || m_orientation == orHorizontal)
	{
		posx = (m_orientation == orGrid) ? (m_itemwidth) * ((index - (m_top * m_max_columns)) % m_max_columns) : (m_itemwidth) * (index - m_left);
		posy = (m_orientation == orGrid) ? (m_itemheight) * ((index - (m_top * m_max_columns)) / m_max_columns) : 0;
	}
	else
		posy = (m_itemheight) * (index - m_top);

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
			if (m_orientation == orVertical)
			{
				m_content->cursorMove(m_top - m_selected);
			}
			else if (m_orientation == orHorizontal)
			{
				m_content->cursorMove(m_left - m_selected);
			}
			else
			{
				m_content->cursorMove((m_max_columns * m_top) - m_selected);
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

#ifdef HAVE_EGL_ANIMATION
			if (m_open_state == 1 && ganim::listsEnabled() && m_anim_timer)
			{
				// the list is painted for the first time: the rows start their entrance (see animationTick())
				m_open_state = 2;
				m_open_first_paint = m_open_start = std::chrono::steady_clock::now();
				m_anim_timer->start(16, true);
			}
#endif
			if (m_orientation == orVertical)
			{
#ifdef HAVE_EGL_ANIMATION
				// Rows with a control animation (focus/unfocus, see rowTransform()) are drawn in a second
				// pass, scaled/moved by the DC, on top of their neighbours.
				const ePoint list_abs = getAbsolutePosition();
				const eRect list_rect(list_abs, size());
				std::vector<int> animated;
#endif
				// While the scroll animation runs all rows are painted `scroll_off` pixels off their place;
				// a downwards shifted list needs the row above the page as well.
				int scroll_off = 0, first_i = 0, last_i = m_items_per_page;
#ifdef HAVE_EGL_ANIMATION
				scroll_off = scrollOffset();
				if (scroll_off > 0 && m_top > 0)
				{
					first_i = -std::min(m_top, (scroll_off + m_itemheight - 1) / m_itemheight);
					m_content->cursorMove(first_i);
				}
				else if (scroll_off < 0)
					last_i = m_items_per_page + std::max(0, (-scroll_off + m_itemheight - 1) / m_itemheight - 1);
#endif
				entryrect.moveBy(ePoint(0, first_i * m_itemheight + scroll_off));
				for (int y = first_i * m_itemheight + scroll_off, i = first_i; i <= last_i; y += m_itemheight, ++i)
				{
					gRegion entry_clip_rect = paint_region & entryrect;

					if (!entry_clip_rect.empty())
					{
#ifdef HAVE_EGL_ANIMATION
						float tsx, tsy, ttx, tty, ta;
						if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + xoffset, list_abs.y() + y, size().width() - xoffset, m_itemheight), tsx, tsy, ttx, tty, ta))
							animated.push_back(i);
						else
#endif
						m_content->paint(painter, *style, ePoint(xoffset, y), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
					}

						/* (we could clip with entry_clip_rect, but
						this shouldn't change the behavior of any
						well behaving content, so it would just
						degrade performance without any gain.) */

					m_content->cursorMove(+1);
					entryrect.moveBy(ePoint(0, m_itemheight));
				}
#ifdef HAVE_EGL_ANIMATION
				if (!animated.empty())
				{
					m_content->cursorRestore();
					m_content->cursorSave();
					m_content->cursorMove(m_top - m_selected + first_i);
					size_t next = 0;
					for (int y = first_i * m_itemheight + scroll_off, i = first_i; i <= last_i && next < animated.size(); y += m_itemheight, ++i)
					{
						if (i == animated[next])
						{
							++next;
							float tsx, tsy, ttx, tty, ta;
							if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + xoffset, list_abs.y() + y, size().width() - xoffset, m_itemheight), tsx, tsy, ttx, tty, ta))
							{
								painter.setTransform(tsx, tsy, ttx, tty, ta, list_rect);
								// some contents clear or clip more than their cell (a grid cell's highlight reached the whole list): keep it to the cell
								painter.clip(gRegion(eRect(ePoint(xoffset, y), eSize(size().width() - xoffset, m_itemheight))));
								m_content->paint(painter, *style, ePoint(xoffset, y), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
								painter.clippop();
								painter.resetTransform();
							}
						}
						m_content->cursorMove(+1);
					}
				}
#endif
				m_content->cursorRestore();
			}
			else if (m_orientation == orHorizontal)
			{
#ifdef HAVE_EGL_ANIMATION
				const ePoint list_abs = getAbsolutePosition();
				const eRect list_rect(list_abs, size());
				std::vector<int> animated;
#endif
				for (int x = 0, i = 0; i <= m_items_per_page; x += m_itemwidth, ++i)
				{
					gRegion entry_clip_rect = paint_region & entryrect;

					if (!entry_clip_rect.empty())
					{
#ifdef HAVE_EGL_ANIMATION
						float tsx, tsy, ttx, tty, ta;
						if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + x, list_abs.y() + yoffset, m_itemwidth, size().height() - yoffset), tsx, tsy, ttx, tty, ta))
							animated.push_back(i);
						else
#endif
						m_content->paint(painter, *style, ePoint(x, yoffset), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
					}

						/* (we could clip with entry_clip_rect, but
						this shouldn't change the behavior of any
						well behaving content, so it would just
						degrade performance without any gain.) */

					m_content->cursorMove(+1);
					entryrect.moveBy(ePoint(m_itemwidth, 0));
				}
#ifdef HAVE_EGL_ANIMATION
				if (!animated.empty())
				{
					m_content->cursorRestore();
					m_content->cursorSave();
					m_content->cursorMove(m_left - m_selected);
					size_t next = 0;
					for (int x = 0, i = 0; i <= m_items_per_page && next < animated.size(); x += m_itemwidth, ++i)
					{
						if (i == animated[next])
						{
							++next;
							float tsx, tsy, ttx, tty, ta;
							if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + x, list_abs.y() + yoffset, m_itemwidth, size().height() - yoffset), tsx, tsy, ttx, tty, ta))
							{
								painter.setTransform(tsx, tsy, ttx, tty, ta, list_rect);
								// some contents clear or clip more than their cell (a grid cell's highlight reached the whole list): keep it to the cell
								painter.clip(gRegion(eRect(ePoint(x, yoffset), eSize(m_itemwidth, size().height() - yoffset))));
								m_content->paint(painter, *style, ePoint(x, yoffset), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
								painter.clippop();
								painter.resetTransform();
							}
						}
						m_content->cursorMove(+1);
					}
				}
#endif
				m_content->cursorRestore();
			}
			else
			{
				int line = 0;
				int m_max_items = m_items_per_page_with_partials;
#ifdef HAVE_EGL_ANIMATION
				// Cells with a control animation (see rowTransform()) are drawn in a second pass, like the rows of a list.
				const ePoint list_abs = getAbsolutePosition();
				const eRect list_rect(list_abs, size());
				std::vector<int> animated;
#endif
				for (int posx = 0, posy = 0, i = 0; i < m_max_items; posx += m_itemwidth, ++i)
				{
					if (i > 0)
					{
						if (i % m_max_columns == 0)
						{
							posy += m_itemheight;
							posx = 0;
						}
					}

					entryrect = eRect(posx, posy, m_itemwidth, m_itemheight);
					gRegion entry_clip_rect = paint_region & entryrect;
					if (!entry_clip_rect.empty())
					{
						// always paint, even for out-of-range cursors (e.g. a ragged last row),
						// so the content clears stale/selected pixels left over from a previous entry
#ifdef HAVE_EGL_ANIMATION
						float tsx, tsy, ttx, tty, ta;
						if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + posx, list_abs.y() + posy, m_itemwidth, m_itemheight), tsx, tsy, ttx, tty, ta))
							animated.push_back(i);
						else
#endif
						m_content->paint(painter, *style, ePoint(posx, posy), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
					}
					m_content->cursorMove(+1);
				}
#ifdef HAVE_EGL_ANIMATION
				if (!animated.empty())
				{
					m_content->cursorRestore();
					m_content->cursorSave();
					m_content->cursorMove((m_max_columns * m_top) - m_selected);
					size_t next = 0;
					for (int posx = 0, posy = 0, i = 0; i < m_max_items && next < animated.size(); posx += m_itemwidth, ++i)
					{
						if (i > 0 && i % m_max_columns == 0)
						{
							posy += m_itemheight;
							posx = 0;
						}
						if (i == animated[next])
						{
							++next;
							float tsx, tsy, ttx, tty, ta;
							if (rowTransform(m_content->cursorGet(), eRect(list_abs.x() + posx, list_abs.y() + posy, m_itemwidth, m_itemheight), tsx, tsy, ttx, tty, ta))
							{
								painter.setTransform(tsx, tsy, ttx, tty, ta, list_rect);
								// some contents clear or clip more than their cell (a grid cell's highlight reached the whole list): keep it to the cell
								painter.clip(gRegion(eRect(ePoint(posx, posy), eSize(m_itemwidth, m_itemheight))));
								m_content->paint(painter, *style, ePoint(posx, posy), m_selected == m_content->cursorGet() && m_content->size() && m_selection_enabled);
								painter.clippop();
								painter.resetTransform();
							}
						}
						m_content->cursorMove(+1);
					}
				}
#endif

				m_content->cursorRestore();

			}

			// clear/repaint empty/unused space between scrollbar and listboxentrys
			if (m_scrollbar && !isTransparent())
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
				else
				{
					if (m_orientation == orVertical)
					{
						if (m_scrollbar->isVisible())
						{
							painter.clip(eRect(m_scrollbar->position() - ePoint(5,0), eSize(5,m_scrollbar->size().height())));
						}
						else
						{
							painter.clip(eRect(m_scrollbar->position() - ePoint(5,0), eSize(m_scrollbar->size().width() + 5, m_scrollbar->size().height())));
						}
					}
					else
					{
						if (m_scrollbar->isVisible())
						{
							painter.clip(eRect(m_scrollbar->position() - ePoint(0,5), eSize(m_scrollbar->size().width(), 5)));
						}
						else
						{
							painter.clip(eRect(m_scrollbar->position() - ePoint(0,5), eSize(m_scrollbar->size().width(), m_scrollbar->size().height() + 5)));
						}
					}
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
		m_items_per_page = size().height() / m_itemheight;
	}
	else if (m_orientation == orHorizontal)
	{
		if (m_content)
			m_content->setSize(eSize(m_itemwidth, size().height()));
		m_items_per_page = size().width() / m_itemwidth;
	}
	else
	{
		if (m_content)
			m_content->setSize(eSize(m_itemwidth, m_itemheight));

		int w = size().width();
		int h = size().height();

		m_max_columns = w / m_itemwidth;
		m_max_rows = h / m_itemheight;
		m_items_per_page = m_max_columns * m_max_rows;
		m_items_per_page_with_partials = m_max_columns * ((h + m_itemheight - 1) / m_itemheight);
	}

	if (m_items_per_page < 0) /* TODO: whyever - our size could be invalid, or itemheigh could be wrongly specified. */
		m_items_per_page = 0;

	if (m_max_columns < 0)
		m_max_columns = 0;
	if (m_max_rows < 0)
		m_max_rows = 0;

	moveSelection(justCheck);
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
	entryChanged(m_selected); /* redraw current entry */
}

void eListbox::entryAdded(int index)
{
	if (m_content && (m_content->size() % m_items_per_page) == 1)
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
		if ((m_top <= index) && (index < (m_top + m_items_per_page)))
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
	if (m_content && !(m_content->size() % m_items_per_page))
		m_content_changed=true;

	if (index == m_selected && m_content)
		m_selected = m_content->cursorGet();

	if (m_content && m_content->cursorGet() >= m_content->size())
		moveSelection(moveUp);
	else
		moveSelection(justCheck);

	if (m_orientation == orVertical)
	{
		if ((m_top <= index) && (index < (m_top + m_items_per_page)))
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
	if (m_orientation == orVertical)
	{
		if ((m_top <= index) && (index <= (m_top + m_items_per_page)))
		{
			gRegion inv = eRect(0, m_itemheight * (index-m_top), size().width(), m_itemheight);
			invalidate(inv);
		}
	}
	else if (m_orientation == orHorizontal)
	{
		if ((m_left <= index) && (index <= (m_left + m_items_per_page + 1)))
		{
			gRegion inv = eRect(m_itemwidth * (index-m_left), 0, m_itemwidth, size().height());
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
		int gridStart = m_top * m_max_columns;
		int gridEnd = gridStart + m_items_per_page_with_partials;
		if ((index >= gridStart) && (index < gridEnd))
		{
			gRegion inv = eRect(getItemPostion(index), eSize(m_itemwidth, m_itemheight));
			invalidate(inv);
		}
	}
}

void eListbox::entryReset(bool selectionHome)
{
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
