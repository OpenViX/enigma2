#ifndef __lib_gui_epanel_h
#define __lib_gui_epanel_h

#include <algorithm>
#include <cstdint>
#include <lib/gui/ewidget.h>
#include <vector>

class eStack : public eWidget {
public:
	enum LayoutDirection : uint8_t {
		Horizontal,
		Vertical
	};

	eStack(eWidget* parent = nullptr, LayoutDirection dir = Vertical);

	void setLayoutDirection(LayoutDirection dir);
	LayoutDirection layoutDirection() const { return m_direction; }

	void addChild(eWidget* child);
	void removeChild(eWidget* child);

	int getSpacing() const { return m_spacing; }
	void setSpacing(int spacing) { m_spacing = spacing; }

protected:
	int event(int event, void* data = 0, void* data2 = 0) override;
	void recalcLayout();
	void invalidateChilds() override;

private:
	LayoutDirection m_direction;
	std::vector<eWidget*> m_stackchilds;
	int m_spacing;
};

#endif
