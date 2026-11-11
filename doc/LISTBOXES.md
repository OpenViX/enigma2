# Listboxes: layout, scrolling, carousel and templates

One overview of everything the listbox (`eListbox`, `lib/gui/elistbox.{h,cpp}`) can do for a skin, and how the content types and the templated service list plug into it. The details that have a document of their own stay there:

- [LISTBOX_CAROUSEL.md](LISTBOX_CAROUSEL.md): carousel, zoom, scroll type, header line style, spacing in depth.
- [SERVICELIST_TEMPLATES.md](SERVICELIST_TEMPLATES.md): rows, items, conditions, styles of the templated service list.

> Status: built and tested on a device (2026-11-11): spacing, carousel focus size and focus slot, template overrides, selection zoom and paging work.

---

## 1. Concepts

| Term | Meaning |
|---|---|
| **Listbox** | `eListbox`, the widget. Handles layout, cursor, scrolling, scrollbar, zoom, carousel. |
| **Content** | What fills it (`iListboxContent`): string list, MultiContent, TemplatedMultiContent, config list, service list, templated service list. Paints one entry at a time into a cell given by the listbox. |
| **Tile / cell** | The area of one entry, `itemWidth` x `itemHeight`. |
| **Gap / spacing** | Empty space between tiles. |
| **Pitch** | Distance from one tile to the next = tile size + gap. All position, paging and scrollbar math uses the pitch. |
| **Slot** | A position on screen. In a carousel the selection always sits in one slot (the focus slot). |

The listbox draws the cells; the content only draws *inside* the cell it is given. That is why most features work for every content type.

## 2. Orientation and tile size

| `orientation` | Layout | Tile size |
|---|---|---|
| `orVertical` (default) | One column of rows | width = widget width (minus scrollbar), height = `itemHeight` |
| `orHorizontal` | One row of tiles | width = `itemWidth`, height = widget height (minus scrollbar) |
| `orGrid` | Rows of tiles, `columns = (width + gapX) / (itemWidth + gapX)` | `itemWidth` x `itemHeight` |

Skin attributes: `orientation`, `itemWidth`, `itemHeight`. A content can bring its own values (a template, `setItemWidth()` on a MultiContent), which replace the widget's.

Without a gap, the number of tiles per page is `size / itemSize`. With a gap it is `1 + (size - itemSize) / (itemSize + gap)`: only tiles need a gap *between* them, the last tile may end at the widget edge.

## 3. Item spacing

| Attribute | Meaning |
|---|---|
| `itemSpacing="N"` | The same gap in both directions |
| `itemSpacing="X,Y"` | `X` between columns, `Y` between rows |
| `itemSpacingX="N"` | Gap between columns / between the tiles of a horizontal list |
| `itemSpacingY="N"` | Gap between rows / between the tiles of a vertical list |

A list only uses the gap of its scroll direction (vertical: `Y`, horizontal and carousel: `X`), a grid uses both. A spanning grid entry (marker) is as wide as all columns *plus* the gaps between them.

Everything is gap-aware: visible-tile count, pages, page keys, scrollbar, pager, `scrollType`, partial redraw regions, selection zoom, carousel slots.

Where it can be set:

| Content | How |
|---|---|
| any (skin) | widget attributes above |
| Templated service list | `<template itemSpacing="12,8">`, or `itemSpacingX` / `itemSpacingY` (these win over `itemSpacing`) |
| TemplatedMultiContent | `"itemSpacing": 10` or `(10, 20)` in the template dict, or the optional 7th element of a `templates` style tuple `(itemHeight, template, selectionEnabled, scrollbarMode, itemWidth, orientation, itemSpacing)` |
| MultiContent / string | `content.setItemSpacing(x, y)`; `-1` leaves the axis to the widget |

Precedence: **content value (if set) > widget value > 0**.

## 4. Scrolling and paging

- `scrollType="page"` (default): when the selection leaves the visible part the list jumps to the page that holds it. `scrollType="item"`: the list moves one entry (grid: one row) at a time, only as far as needed.
- `enableWrapAround="1"`: the cursor wraps from the last entry to the first and back.
- Page keys (`prevPage` / `nextPage`, `pageUp` / `pageDown`) move a page of tiles; for horizontal lists the up/down actions are mapped to previous/next page for compatibility.
- **Pager** (`Components/Addons/Pager.py`) uses `getPageCount()` / `getCurrentPage()`:
  - plain list: `ceil(entries / tilesPerPage)`;
  - grid with spanning entries, or a vertical list with entries of different heights: pages are "as many rows as fit";
  - `scrollType="item"`: pages-worth of entries;
  - carousel: no pages, every entry is a position (`selected / total`).
- Scrollbar: `scrollbarMode` = `showOnDemand`, `showAlways`, `showNever`, `showLeft`, `showTop`. The thumb follows pages (page mode) or entries (item mode and carousel).

## 5. Variable heights and spanning entries

- **Vertical lists:** a content can report a height per entry (`entryHeightList`): headers, markers. The listbox then lays out, scrolls and pages by the real heights (entry by entry, as many as fit).
- **Grids:** a content can mark entries that span the whole row (`gridSpanList`), e.g. markers (`spanMarkers="1"` in a template), optionally with a height of their own (`markerHeight`). Such an entry is a row on its own; paging counts rows that fit.
- The gap is added between rows of any height and is not part of the entry.

## 6. Headers

Non-selectable section titles for any listbox: put `ListHeader(_("Title"))` in the list (config lists: `getConfigListEntry(_("Title"), HEADER)`). The cursor never stops on it.

Widget attributes: `headerFont`, `headerForegroundColor`, `headerBackgroundColor`, `headerLineColor`, `headerLineThickness`, `headerLineStyle` (`bottom` | `top` | `split` | `none`), `headerLineMargin`, `headerHeight`, `headerValign`, `headerHalign`, `headerTextOffset`. Details in LISTBOX_CAROUSEL.md.

## 7. Selection zoom (horizontal and grid)

`selectionZoom="115"`: the selected tile is drawn 115 % size, centred on its cell, on top of its neighbours, kept inside the widget. Reduced automatically if the enlarged tile would not fit the widget. Not used in carousel mode (`carouselZoom` is used there). Every selection change repaints the whole list while it is on.

What is scaled: MultiContent / TemplatedMultiContent scale positions, sizes and fonts; the templated service list scales the whole template (geometry, fonts, borders, radii); other contents only get a larger cell.

## 8. Carousel (horizontal and vertical)

The selection stays in the focus slot and the entries scroll past it.

| Attribute | Default | Meaning |
|---|---|---|
| `carousel` | `0` | Enable |
| `carouselZoom` | `112` | Focus tile size in percent, `100` = no zoom |
| `carouselCenterWidth` | = `itemWidth` | Width of the focused tile |
| `carouselCenterHeight` | = other tiles | Height of the focused tile |
| `carouselFocus` | `center` | Slot (from 0) that holds the selection; `center` = `visible / 2` |
| `enableWrapAround` | `0` | Entries also wrap visually around the list ends |

Geometry:

- Slot `i` before the focus slot is at `i * pitch`; the focus slot has the focus size; slots after it follow after the focus size plus one gap.
- Visible slots = `1 + (widgetSize - focusSize) / pitch`. For an exactly centred selection use an odd count with the default focus.
- Cross axis: the focused tile is centred on the other tiles and never larger than the widget.
- `carouselZoom` is applied **on top of** the dedicated size; set `carouselZoom="100"` for the exact size.
- `carouselFocus` beyond the last visible slot is limited to the last one.
- Pager and scrollbar follow the selected entry; keys are unchanged (one entry per step). Without wrap-around, slots before the first and after the last entry stay empty.

## 9. Which settings a template can override (templated service list)

A `<template>` of `<servicelisttemplates>` may set the settings below. While the template is active they replace the widget's; whatever the template leaves out comes from the widget. They are inherited through `base`.

| Template attribute | Widget attribute it replaces |
|---|---|
| `layout` (`list` / `horizontal` / `grid`) | `orientation` |
| `itemWidth` | `itemWidth` |
| `itemHeight` | `itemHeight` (service list: the widget's `itemHeight` skin attribute) |
| `itemSpacing`, `itemSpacingX`, `itemSpacingY` | `itemSpacing*` |
| `selectionZoom` | `selectionZoom` |
| `carousel` | `carousel` |
| `carouselZoom` | `carouselZoom` |
| `carouselFocus` (`center` or number) | `carouselFocus` |
| `carouselCenterWidth`, `carouselCenterHeight` | same names |
| `markerHeight`, `spanMarkers` | (template only: marker rows in vertical lists / grids) |

```xml
<template name="posters" layout="horizontal" itemWidth="180" itemHeight="260" itemSpacing="20"
          carousel="1" carouselFocus="center" carouselCenterWidth="300" carouselZoom="100">
  <row for="service" weight="3"> <item type="picon" width="*" margin="6"/> </row>
  <row for="service" weight="1"> <item type="text" text="{name}" width="*" align="center"/> </row>
</template>
```

Switching the template (`setTemplate`) re-evaluates all of them, so one service list can be a plain list in one template and a carousel in another.

Notes:

- A template **without** `itemHeight` uses the widget's `itemHeight`; **without** `itemWidth` the widget's `itemWidth` stays.
- In a horizontal template the cell is `itemHeight` high (not widget-high), so zoom has room to grow. With a dedicated carousel focus size this clamp is lifted for the focused tile only.
- The template's row cache is keyed by cell width and height, so the focused tile with its own size does not invalidate the cache of the normal tiles.
- Rows, items, tokens, conditions and styles: see SERVICELIST_TEMPLATES.md.

## 10. TemplatedMultiContent and MultiContent

- Template dict keys: `template`, `fonts`, `itemHeight` (required), `itemWidth`, `orientation`, `selectionEnabled`, `scrollbarMode`, `itemSpacing`, optionally `templates` = `{style: (itemHeight, template, selectionEnabled, scrollbarMode, itemWidth, orientation, itemSpacing)}` with a `default` entry; `None` skips an element.
- Skin scale factors are applied to item sizes, positions, fonts and the spacing.
- Selection zoom / carousel zoom scale item positions, sizes and fonts; pixmaps get `BT_SCALE`. Absolute positions of items do not follow a *dedicated* carousel focus size (only content that lays itself out by cell size fills the larger cell); use `carouselZoom` for those.

## 11. Other shared attributes

`ellipsis` (cut long text with "..."), `itemCornerRadius` / `itemCornerRadiusSelected` (`"8"` or `"8;top,left"`), item gradients, `selectionPixmap`, `scrollbar*` colours and sizes, `enableWrapAround`.

## 12. Python API on the `eListbox` instance

```python
setOrientation(eListbox.orHorizontal | orVertical | orGrid)
setItemWidth(w); setItemHeight(h)
setItemSpacing(x, y); setItemSpacingX(x); setItemSpacingY(y)
setScrollType(eListbox.scrollByPage | scrollByItem); setWrapAround(bool)
setSelectionZoom(percent)
setCarousel(bool); getCarousel(); setCarouselZoom(percent)
setCarouselCenterSize(w, h); setCarouselCenterWidth(w); setCarouselCenterHeight(h)
setCarouselFocus(slot)          # -1 = middle
getPageCount(); getCurrentPage(); getCurrentIndex()
setScrollbarMode(eListbox.showOnDemand ...)
```

Content objects: `setItemWidth/Height/Orientation/ItemSpacing` (MultiContent, string content), `setTemplate`, `setFont`, ... as before.

## 13. How it is built (for maintainers)

- **Effective settings.** `eListbox::applyContentSpacing()` computes the settings in effect from the widget values (`m_w_*`, `m_widget_gap_*`) and the content's overrides (`iListboxContent::getItemSpacing()`, `getListboxOverrides()`; `-2` = not set). It runs when a widget setter is called, when a content is attached (`setListbox`), and when a template changes. If the layout is affected it calls `recalcSize()`.
- **Pitch math.** `pitchX()` / `pitchY()` in `elistbox.h`; used by `recalcSize`, `gridUpdate` (row tops include the gap, pages exclude the trailing gap), `gridRowTop`, `gridRowHeight` (cell without gap), `verticalRect`, `getItemPostion`, `getEntryTop`, the paint loops and all invalidation rectangles.
- **Carousel geometry.** `carouselCenter()` (focus slot), `carouselSlotPos()`, `carouselFocusExtent()`, `carouselFocusCell()`. The focus cell is given to the content with `setCellOverride(true)` + `setSize(cell)` around its paint, then restored; `paintZoomed()` adds the zoom on top.
- **Zoom.** `paintZoomed()` gives the content a larger cell and `setZoom(percent)`, keeps the result inside the widget, and restores sizes afterwards.
- **Files:** `lib/gui/elistbox.{h,cpp}`, `lib/gui/elistboxcontent.{h,cpp}`, `lib/service/listboxservicetpl.{h,cpp}`, `lib/python/skin.py` (widget attributes + `<servicelisttemplates>` parsing), `lib/python/Components/Converter/TemplatedMultiContent.py`, `lib/python/Components/Addons/Pager.py`, `lib/python/Components/ListHeader.py`.

## 14. Known limits

- Zoomed or dedicated-size tiles overlap their neighbours; opaque neighbours are partly covered.
- Carousel is ignored for grids. No scaling of fixed-size images, no cross-axis zoom.
- With a dedicated focus size, MultiContent items with absolute positions keep their place.
- Not verified on a device: a rounded template `rect` frame without fill.
- Do not write an apostrophe in comments of C++ headers that SWIG parses (`elistbox.h`, `elistboxcontent.h`, `listboxservicetpl.h`): it breaks the Python bindings and the arrow keys become unhandled.
