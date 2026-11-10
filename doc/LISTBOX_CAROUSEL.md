# Listbox carousel mode

A listbox can behave as a carousel: the selection stays locked on the centre slot and the entries scroll past it. It works for horizontal and vertical listboxes, with every content type (MultiContent, string lists, the templated service list, ...).

## Skin attributes

|  Attribute  |  Values  | Default | Meaning |
|---|---|---|---|
| `carousel` | `0` / `1` | `0` | Enable carousel mode. Ignored for `orGrid`, and for vertical lists with entries of different heights. |
| `carouselZoom` | `100`..`300` | `112` | Size of the centre slot in percent. `100` disables the zoom. |
| `selectionZoom` | `100`..`300` | `100` (off) | Size of the selected entry in percent, for **horizontal and grid** lists without carousel (see "Selection zoom"). |
| `enableWrapAround` | `0` / `1` | `0` | With carousel: entries also wrap visually, so the last entry is shown just before the first one. |

```xml
<widget source="list" render="Listbox" orientation="orHorizontal"
        position="0,400" size="1280,200" itemWidth="200"
        carousel="1" carouselZoom="115" enableWrapAround="1"/>
```

Python (on the `eListbox` instance): `setCarousel(bool)`, `getCarousel()`, `setCarouselZoom(percent)`.

## Behaviour

- The centre slot is slot number `visible items / 2` (counting from 0). Use an odd number of visible items (widget size = odd multiple of the item size) for an exactly centred selection.
- Without wrap-around, slots before the first / after the last entry stay empty, so the first entry starts in the centre.
- The key handling is unchanged. Left/right (horizontal) or up/down (vertical) move one entry; page keys move one entry as before.
- Every selection change repaints the whole list, because all entries move.
- The scrollbar position follows the selected entry.
- Pager: a carousel has no pages, so the pager widget shows the selected entry's position (`getPageCount()` = number of entries, `getCurrentPage()` = selected entry), e.g. "5 / 120".

## Zoom

The centre slot is enlarged uniformly with its content (see "What is scaled") and drawn last, so it overlaps its neighbours.

The zoom works by giving the content a larger cell size for that one entry, then restoring it. Content that lays itself out relative to the cell size (centred text, templated service list rows, `width="*"` items) grows with it. Absolute positions and fixed-size pixmaps in a MultiContent template do not move or scale.

Content classes that do not report their cell size (`getItemSize()`) are painted unzoomed.

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
