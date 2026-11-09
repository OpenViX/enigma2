#include <lib/gui/estack.h>

eStack::eStack(eWidget* parent, LayoutDirection dir) : eWidget(parent), m_direction(dir) {
	m_spacing = 0;
	setTransparent(1);
}

eStack::~eStack() {
	/* children must not call back into a destroyed stack */
	for (auto child : m_stackchilds)
		child->setStack(nullptr);
}

void eStack::setSpacing(int spacing) {
	m_spacing = spacing;
	recalcLayout();
}

void eStack::show() {
	eWidget::show();
	recalcLayout();
}

void eStack::forgetStackChild(eWidget* child) {
	if (auto it = std::ranges::find(m_stackchilds, child); it != m_stackchilds.end())
		m_stackchilds.erase(it);
}

void eStack::setLayoutDirection(LayoutDirection dir) {
	m_direction = dir;
	recalcLayout();
}

void eStack::addChild(eWidget* child) {
	if (!child)
		return;

	child->setStack(this);
	m_stackchilds.push_back(child);
	recalcLayout();
}

void eStack::removeChild(eWidget* child) {
	if (!child)
		return;

	if (auto it = std::ranges::find(m_stackchilds, child); it != m_stackchilds.end()) {
		m_stackchilds.erase(it);
		child->setStack(nullptr);
	}

	recalcLayout();
}

void eStack::invalidateChilds() {
	recalcLayout();
}


int eStack::event(int event, void* data, void* data2) {
	if (event == evtPaint)
		return 0;

	int ret = eWidget::event(event, data, data2);
	if (event == evtChangedPosition) {
		/* the children are siblings, not real children, so they don't follow
		   us: shift them along the axis the layout doesn't control (a nested
		   stack gets moved by its parent stack) */
		ePoint delta = position() - m_lastpos;
		m_lastpos = position();
		if (delta.x() || delta.y()) {
			for (auto child : m_stackchilds) {
				if (m_direction == Horizontal)
					child->move(ePoint(child->position().x(), child->position().y() + delta.y()));
				else
					child->move(ePoint(child->position().x() + delta.x(), child->position().y()));
			}
			recalcLayout();
		}
	} else if (event == evtChangedSize)
		recalcLayout();
	return ret;
}

void eStack::recalcLayout() {
	int stack_w = size().width();
	int stack_h = size().height();

	if (stack_w < 0 || stack_h < 0)
		return;
	if (!isVisible())
		return;
	/* resizing or moving a child calls back into invalidateChilds() */
	if (m_layouting)
		return;
	m_layouting = true;

	/* a child with stackFill gets the space the other children leave over */
	{
		const bool horizontal = m_direction == Horizontal;
		eWidget* fill = nullptr;
		int used = 0, count = 0;
		for (auto child : m_stackchilds) {
			if (!child->isVisible() || child->align() == 0 || (child->align() & eStackAlignCenter))
				continue;
			/* a child without any size takes no space, not even spacing, but a fill child can grow again */
			if (!child->stackFill() && (horizontal ? child->size().width() : child->size().height()) == 0)
				continue;
			count++;
			if (child->stackFill() && !fill) {
				fill = child;
				continue;
			}
			used += horizontal ? child->size().width() : child->size().height();
		}
		if (fill) {
			int avail = (horizontal ? stack_w : stack_h) - used - m_spacing * (count - 1);
			if (avail < 0)
				avail = 0;
			eSize fsize = fill->size();
			if (horizontal && fsize.width() != avail)
				fill->resize(eSize(avail, fsize.height()));
			else if (!horizontal && fsize.height() != avail)
				fill->resize(eSize(fsize.width(), avail));
		}
	}

	int x = 0, y = 0;
	int xr = stack_w;
	int yb = stack_h;
	int lcount = 0;
	int rcount = 0;
	int tcount = 0;
	int bcount = 0;

	for (auto child : m_stackchilds) {
		if (!child->isVisible())
			continue;

		eSize csize = child->size();
		int cx = 0, cy = 0;
		int cw = csize.width();
		int ch = csize.height();
		if (child->align() == 0)
			continue;
		if (!child->stackFill() && (m_direction == Horizontal ? cw : ch) == 0)
			continue;

		if (m_direction == Horizontal) {
			if (child->align() & eStackAlignLeft) {
				cx = x;
				x += cw;
				if (lcount > 0) {
					x += m_spacing;
					cx += m_spacing;
				}
				lcount++;
			} else if (child->align() & eStackAlignRight) {
				cx = xr - cw;
				xr -= cw;
				if (rcount > 0) {
					cx -= m_spacing;
					xr -= m_spacing;
				}
				rcount++;
			} else if (child->align() & eStackAlignCenter)
				cx = (stack_w - cw) / 2;

			int cross = child->position().y();
			switch (child->stackCross()) {
			case 1: cross = position().y(); break;
			case 2: cross = position().y() + (stack_h - ch) / 2; break;
			case 3: cross = position().y() + stack_h - ch; break;
			}
			child->move(ePoint(cx + position().x(), cross));
		} else {
			if (child->align() & eStackAlignTop) {
				cy = y;
				y += ch;
				if (tcount > 0) {
					y += m_spacing;
					cy += m_spacing;
				}
				tcount++;
			} else if (child->align() & eStackAlignBottom) {
				cy = yb - ch;
				yb -= ch;
				if (bcount > 0) {
					cy -= m_spacing;
					yb -= m_spacing;
				}
				bcount++;
			} else if (child->align() & eStackAlignCenter)
				cy = (stack_h - ch) / 2;

			int cross = child->position().x();
			switch (child->stackCross()) {
			case 1: cross = position().x(); break;
			case 2: cross = position().x() + (stack_w - cw) / 2; break;
			case 3: cross = position().x() + stack_w - cw; break;
			}
			child->move(ePoint(cross, cy + position().y()));
		}
	}
	m_layouting = false;
}
