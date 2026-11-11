# Listbox carousel mode

A listbox can behave as a carousel: the selection stays locked on the centre slot and the entries scroll past it. It works for horizontal and vertical listboxes, with every content type (MultiContent, string lists, the templated service list, ...).

## Skin attributes

|  Attribute  |  Values  | Default | Meaning |
|---|---|---|---|
| `carousel` | `0` / `1` | `0` | Enable carousel mode. Ignored for `orGrid`, and for vertical lists with entries of different heights. |
| `carouselZoom` | `100`..`300` | `112` | Size of the centre slot in percent. `100` disables the zoom. |
| `selectionZoom` | `100`..`300` | `100` (off) | Size of the selected entry in percent, for **horizontal and grid** lists without carousel (see "Selection zoom"). |
| `scrollType` | `page` / `item` | `page` | How a list scrolls when the selection leaves the visible part (all orientations, see "Scroll type"). |
| `enableWrapAround` | `0` / `1` | `0` | With carousel: entries also wrap visually, so the last entry is shown just before the first one. |
| `itemSpacing` | `N` or `X,Y` | `0` | Gap in pixels between the tiles, for every orientation and content type (see "Item spacing"). |
| `carouselCenterWidth` | pixels | `0` (= `itemWidth`) | Width of the focused carousel tile (see "Dedicated focus size"). |
| `carouselCenterHeight` | pixels | `0` (= the other tiles) | Height of the focused carousel tile. |
| `carouselFocus` | `center` / slot number | `center` | Which slot of the carousel holds the selection (see "Focus slot"). |

```xml
<widget source="list" render="Listbox" orientation="orHorizontal"
        position="0,400" size="1280,200" itemWidth="200"
        carousel="1" carouselZoom="115" enableWrapAround="1"/>
```

Python (on the `eListbox` instance): `setCarousel(bool)`, `getCarousel()`, `setCarouselZoom(percent)`, `setCarouselCenterSize(w, h)` (`setCarouselCenterWidth`, `setCarouselCenterHeight`), `setCarouselFocus(slot)`, `setItemSpacing(x, y)`.

## Behaviour

- The centre slot is slot number `visible items / 2` (counting from 0). Use an odd number of visible items (widget size = odd multiple of the item size) for an exactly centred selection.
- Without wrap-around, slots before the first / after the last entry stay empty, so the first entry starts in the centre.
- The key handling is unchanged. Left/right (horizontal) or up/down (vertical) move one entry; page keys move one entry as before.
- Every selection change repaints the whole list, because all entries move.
- The scrollbar position follows the selected entry.
- Pager: a carousel has no pages, so the pager widget shows the selected entry's position (`getPageCount()` = number of entries, `getCurrentPage()` = selected entry), e.g. "5 / 120".

## Item spacing

`itemSpacing="10"` puts a gap of 10 px between the tiles; `itemSpacing="12,8"` sets the horizontal and the vertical gap separately. The same can be written as `itemSpacingX="12"` (between the columns) and `itemSpacingY="8"` (between the rows), also in a service list `<template>`; in a template the axis attribute wins over `itemSpacing`; on a widget just don't give both for the same axis.

- **vertical list:** only the vertical (second) value is used, between the rows.
- **horizontal list / carousel:** only the horizontal (first) value is used, between the tiles.
- **grid:** both: the horizontal gap between the columns, the vertical gap between the rows. A spanning entry (marker) is as wide as all columns *including* the gaps between them.
- A tile keeps its `itemWidth` x `itemHeight`; the gap is added between tiles, never after the last visible one. The number of visible tiles, the page size, the scrollbar, the pager (`getPageCount()` / `getCurrentPage()`), page keys, `scrollType`, the selection zoom and the carousel all use the gap. The tiles of a page are drawn on the background of the listbox, the gap is not part of any entry.
- Works for every content type. A content can bring its own gap, which wins over the widget's one:
  - **Templated service list:** `<template name="..." itemSpacing="12,8">`, inherited through `base`.
  - **TemplatedMultiContent:** `"itemSpacing": 10` or `(10, 20)` in the template dict, or as optional 7th element of an entry of `templates` (`(itemHeight, template, selectionEnabled, scrollbarMode, itemWidth, orientation, itemSpacing)`, use `None` for the elements to skip).
  - **MultiContent / string content:** `content.setItemSpacing(x, y)`; `-1` leaves the axis to the widget.

```xml
<widget source="list" render="Listbox" orientation="orGrid" itemWidth="200" itemHeight="150"
        itemSpacing="16,12" position="40,100" size="1200,600"/>
```

## Service list templates

A `<template>` of the templated service list can set `itemWidth`, `itemHeight`, `itemSpacing`, `selectionZoom`, `carousel`, `carouselZoom`, `carouselFocus`, `carouselCenterWidth` and `carouselCenterHeight`. They replace the values of the widget while the template is active; whatever the template does not set is taken from the widget (also `itemWidth` / `itemHeight`). They are inherited through `base`.

```xml
<template name="posters" base="grid" layout="horizontal" itemWidth="180" itemHeight="260" itemSpacing="20"
          carousel="1" carouselFocus="center" carouselCenterWidth="300" carouselCenterHeight="260" carouselZoom="100"/>
```

## Dedicated focus size

`carouselCenterWidth` / `carouselCenterHeight` give the focused tile a size of its own; whatever is not given stays as large as the other tiles.

- **Scroll axis** (width for a horizontal, height for a vertical carousel): the focused slot reserves exactly that much room, the other slots move apart accordingly. The number of visible slots is `1 + (list size - focus size) / (tile size + gap)`, so with a larger focus tile the widget needs a size of `focus + n * (tile + gap)` for `n` neighbours (odd counts left and right give an exactly centred selection).
- **Cross axis:** the focused tile is centred on the other tiles and never larger than the widget.
- `carouselZoom` is applied **on top of** the dedicated size (`112` by default). Use `carouselZoom="100"` to get exactly the size you gave.
- Pager, scrollbar and key handling are not affected; the selection is still one entry per step.
- Content that lays itself out by its cell size (string lists, the templated service list, `width="*"` items) fills the larger cell. In a MultiContent with absolute positions the items keep their place, use `carouselZoom` for those.

```xml
<widget source="list" render="Listbox" orientation="orHorizontal" position="0,300" size="1280,260"
        itemWidth="180" carousel="1" itemSpacing="20" carouselCenterWidth="320" carouselZoom="100"/>
```

## Focus slot

`carouselFocus="N"` (slot number, counted from `0` at the first visible slot) selects the slot that holds the selection; entries before it are the already seen ones, entries after it come next. Default `center` is the middle slot (`visible / 2`). A number beyond the last visible slot is limited to the last slot. The dedicated size and the zoom apply to this slot.

```xml
<widget ... orientation="orHorizontal" itemWidth="200" carousel="1" carouselFocus="1"/>
```

## Zoom

The centre slot is enlarged uniformly with its content (see "What is scaled") and drawn last, so it overlaps its neighbours.

The zoom works by giving the content a larger cell size for that one entry, then restoring it. Content that lays itself out relative to the cell size (centred text, templated service list rows, `width="*"` items) grows with it. Absolute positions and fixed-size pixmaps in a MultiContent template do not move or scale.

Content classes that do not report their cell size (`getItemSize()`) are painted unzoomed.

## Scroll type

`scrollType="page"` (default) or `scrollType="item"`, for every listbox: vertical, horizontal and grid. Python: `setScrollType(eListbox.scrollByPage / scrollByItem)`.

- **page:** when the selection leaves the visible part the list jumps to the page that holds it. Pages are fixed: entries `0..n-1`, `n..2n-1`, ... With variable row heights (vertical lists whose content reports different entry heights, e.g. headers) a page is as many rows as fit, counted from the top of the list.
- **item:** the list moves only as far as needed to keep the selection visible, one entry (grid: one row) at a time. The scrollbar thumb moves item by item.

Page-up/down keys and the pager are unchanged: the pager counts pages in `page` mode and pages-worth of entries in `item` mode. Carousel mode ignores `scrollType`.

```xml
<widget name="list" orientation="orVertical" scrollType="item" .../>
```

## Header line style

Header entries (`ListHeader`, the config `HEADER` element) get their line from `headerLineStyle`:

| Value | Look |
|---|---|
| `bottom` (default) | line under the title, full width (needs `headerLineColor`) |
| `top` | the same above the title |
| `split` | the title, aligned by `headerHalign`, with a line on each free side of it at mid height, like a marker in the service list. Centred title: lines both sides; `left`: line only right of it; `right`: only left. The line uses `headerLineColor`, or the text colour when that is not set |
| `none` | no line |

`headerLineThickness` sets the thickness, `headerLineMargin` (default 10) the gap between the title and a `split` line.

```xml
<widget name="config" ... headerHalign="center" headerLineStyle="split" headerLineThickness="2" headerLineMargin="12"
        headerLineColor="#606060" headerForegroundColor="#ffc000"/>
```

## Selection zoom (horizontal and grid, no carousel)

```xml
<widget source="list" render="Listbox" orientation="orGrid" itemWidth="220" itemHeight="180"
        selectionZoom="115" .../>
```

The selected entry is drawn `selectionZoom` percent larger, centred on its cell, on top of its neighbours. Python: `setSelectionZoom(percent)`.

- Horizontal and grid lists both grow in both directions (see "What is scaled").
- The enlarged entry is moved back inside the widget, so it is never clipped at the list edges.
- Spanning entries in a grid (e.g. markers) are not zoomed.
- Same mechanism and caveats as the carousel zoom (the content gets a larger cell for that one entry). Leave some free space around the widget, or enough padding inside the cells, so the enlarged entry looks right.
- Every selection change repaints the whole list while the zoom is on, as the enlarged entry overlaps its neighbours.
- In carousel mode `carouselZoom` is used instead; `selectionZoom` is ignored.

## What is scaled

The zoomed entry is scaled uniformly (both axes) around the centre of its cell, with its content:

- **MultiContent / TemplatedMultiContent:** positions, sizes and font sizes of all items are multiplied by the zoom; pixmaps are scaled up (`BT_SCALE` is added). Borders and corner radii keep their size.
- **Other contents** (string list, service list): they only get the larger cell and lay themselves out inside it.

The zoomed entry deliberately **overlaps its neighbours** and is clipped by the widget, never by the cell. It is moved back inside the widget when it would stick out at an edge.

To look right:

- **Anchor:** the entry grows around the centre of the content it actually draws, not around the cell centre. For MultiContent that is the bounding box of its items (items covering the whole cell, such as backgrounds, are ignored), so a poster that is left-aligned in a wider cell stays centred on itself while it grows. Contents that cannot report bounds fall back to the cell centre.
- The enlarged content (not the whole cell) is kept inside the widget.
- Leave room above/below (horizontal lists) or left/right (vertical lists) inside the widget. A horizontal list cell is as high as the widget, so the scaled content is cut off at the widget edge unless the cell content has padding of about `(zoom - 100) / 2` percent top and bottom.

## Limitations

- No zoom of the cross axis, and no scaling of fixed-size images.
- A zoomed centre slot overlaps the neighbours, so neighbours with an opaque background are partly covered.
- Not available in grid mode.

## Implementation

`lib/gui/elistbox.cpp`: `carouselActive()`, `carouselCenter()` (`elistbox.h`), `moveSelection()` (sets `m_left` / `m_top` from the selection), the carousel branch in `evtPaint`, `entryAdded` / `entryChanged`. Skin attributes: `lib/python/skin.py`.
