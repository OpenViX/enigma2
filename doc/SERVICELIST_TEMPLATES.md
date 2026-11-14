# Templated service list

## Goal

A service list renderer whose row design is defined by the skin, with separate templates for a single row, two rows, two rows plus next event, or anything else the skin wants. It supports everything the legacy `eListboxServiceContent` draws and keeps its Python API, so `ChannelSelection` and plugins are unaffected.

The legacy renderer (`lib/service/listboxservice.cpp`) has two hard-coded layouts, allocates `eTextPara`s on every paint and bakes every config option into if-chains. OpenATV's variant builds each row in Python per paint. This one parses the template once, lays each row out once, and caches the result.

## Components

| File | Role |
|---|---|
| `lib/service/listboxservice.{h,cpp}` | Legacy renderer and shared model. Background/selection painting is now shared (`paintBackground` etc.). |
| `lib/service/listboxservicetpl.{h,cpp}` | `eListboxServiceTemplateContent`. Derives from the legacy class, so cursor, marks, sort and movemode are shared. |
| `lib/python/Components/ServiceList.py` | `TemplatedServiceList` and the `createServiceList()` factory. |
| `lib/python/skin.py` | Parses `<servicelisttemplates>`. |

## Skin format

```xml
<servicelisttemplates>
  <styles>
    <style name="name" fg="#ffffff" fgSelected="#ffffff" fgNotAvail="#bbbbbb"
           fgRecorded="#b40431" fgMarked="..." fgMarkedSelected="..."
           fgFallback="..." fgSelectedFallback="..." border="..." borderSelected="..."/>
  </styles>

  <template name="single" title="Single line" itemHeight="40">
    <row for="service" gap="10" padding="0,10">
      <item type="number" width="60" align="right" font="Regular;20" fontGroup="number"
            style="name" text="{number}" visible="cfg.numbers,hasnumber"/>
      <item type="picon" width="auto" margin="2" visible="cfg.picons"/>
      <item type="text" text="{name}" width="*" font="Regular;22" fontGroup="name" style="name"/>
      <item type="text" text="{event}" width="*" style="event" visible="event"/>
    </row>
    <row for="marker"> ... </row>
    <row for="directory"> ... </row>
  </template>

  <template name="double" base="single" itemHeight="70" large="1"> ... </template>
</servicelisttemplates>
```

### Layout

- A template is a vertical stack of `<row>`s: fixed `height`, or sharing the remainder by `weight`.
- A row is a horizontal flow of `<item>`s. A row can have its own `visible="..."` condition; hidden rows are skipped and the remaining rows share the height (e.g. a second line shown only when there is an EPG event).
- Item `width` is a number, `auto` (content size) or `*` (fill, with `weight` / `min`). Hidden items take no space.
- Text that does not fit is elided (`ellipsis="0"` turns it off per item). Fixed and `*` text is cut at its width; if the row overflows, content-sized (`auto`) text shrinks, widest first, down to `min` (at least 24px). Give a `*` item a `min` to reserve room for it.
- `pos="x,y,w,h"` places an item absolutely (overlay, not in the flow).
- `for` selects which kind of list entry a row draws, see below.
- Layout must not depend on the selection state (colours may).
- `base="name"` inherits from an earlier template. A row with an `id` replaces the inherited row with the same `id`; other rows are appended.

### Row kinds (`for`)

A service list holds three kinds of entries, and each can have its own layout. For every entry only the rows whose `for` matches its kind are used.

| `for=` | Entry | Examples |
|---|---|---|
| `service` (default) | A normal playable entry | A TV or radio channel, an IPTV stream |
| `marker` | A separator or heading inside a bouquet | "--- Sports ---" |
| `directory` | A folder-like entry that is entered | A bouquet in the bouquet list, a satellite or provider group |

- Several rows of the same kind stack, e.g. two `service` rows give a two-line layout.
- If a template has no `marker` or `directory` rows, those entries are drawn with the `service` rows. Define them explicitly when the service rows would show things that make no sense for them (picon, event, ...).
- `for` is not the same as `visible`: `for` picks the entry kind, `visible="..."` hides a row or item depending on state (`event`, `recorded`, ...). A row can use both, e.g. `<row for="service" visible="event">`.

### Alignment

- Item `align="left|center|right"` places the content inside the item's own width (text, icons, and the picon, which is centred by default). Item `valign="top|center|bottom"` places it vertically in the row; `center` is the default.
- A picon can be given a `height` smaller than the row and then placed with `valign`.
- Row `align="left|center|right"` positions the whole group of items when they do not fill the row, i.e. when there is no `*` item.

```xml
<!-- a picon alone on a row, centred horizontally: either let it fill the row ... -->
<row for="service" weight="3"> <item type="picon" width="*" align="center" /> </row>
<!-- ... or give it a size and centre the group -->
<row for="service" weight="3" align="center"> <item type="picon" width="200" /> </row>
```

### Item types

`text`, `number` (alias of text), `spacer` (empty, reserves width), `picon`, `servicetype`, `crypto`, `record`, `resolution`, `backup`, `catchup`, `kind` (folder/marker pixmap), `progress`, `line`, `rect`, `pixmap` (static image).

### Rectangles and static pixmaps

```xml
<!-- a rounded card behind the whole cell (z < 0 draws it first) -->
<item type="rect" pos="3,3,186,134" radius="8" color="background2" colorSelected="darkgreen" z="-1" />
<!-- a thin square frame, the border colour changes when selected -->
<item type="rect" width="*" height="40" border="2" borderColor="separator" borderColorSelected="light_yellow" />
<!-- only the top corners rounded, like itemCornerRadius -->
<item type="rect" width="80" height="6" radius="6;top" color="blue" />
<!-- a fixed image, with a variant for the selected row -->
<item type="pixmap" src="icons/star.png" srcSelected="icons/star_sel.png" width="24" height="24" />
```

**`rect`**
- Fill: `color` / `colorSelected` (the selected row falls back to `color`), or the `style` colour if neither is given.
- `border="N"` draws a frame of that width with `borderColor` / `borderColorSelected` (or the style's `border` / `borderSelected`). Without a fill colour only the frame is drawn.
- `radius="N"` rounds the corners; `radius="N;top,left"` limits them to the listed edges (`top`, `bottom`, `left`, `right`, `topLeft`, `topRight`, `bottomLeft`, `bottomRight`).
- Size is `width` (a number, `auto` has no meaning here, use `*` or a number) and `height` (default: the row height); `pos="x,y,w,h"` places it freely.
- A plain filled rectangle (no radius, no border) uses the fast fill path. Rounded or bordered ones are drawn as a rectangle with the fill as background colour. A rounded frame without any fill is the one combination I have not verified on a device.

**`pixmap`**
- `src` is a path resolved like other skin images; `srcSelected` is optional. A missing file is logged and the item is skipped.
- Content sized (`width="auto"`, no `height`): drawn at its natural size and placed by `align` / `valign`. With a `width` and/or `height` it is fitted into that box keeping its aspect ratio (`keepAspect="0"` stretches it), centred unless `align` / `valign` say otherwise.
- `.svg` files are rendered at the item's `width` x `height`.

**`z`** on any item sets the draw order across the whole entry: negative values draw behind everything, positive in front; equal values keep the template order. Absolute (`pos`) items are otherwise drawn after the flowing items of their row.

### Text tokens

`{number}` `{name}` `{event}` `{next}` `{remaining}` `{percent}` `{start}` `{end}` `{duration}`. Anything else is literal text. `{number|  •  }` adds the suffix only when the value is not empty, so a missing channel number leaves no dangling separator.

### Conditions

`visible="a,!b"` means AND, `!` negates.

- Built in: `playable` `marker` `directory` `group` `stream` `event` `nextevent` `crypted` `recorded` `fallback` `unavail` `catchup` `backup` `sd` `hd` `uhd` `hasnumber` `haspicon`.
- Config driven: any `cfg.<name>` flag the Python side sets, such as `cfg.numbers`, `cfg.picons`, `cfg.typeLeft`, `cfg.typeRight`, `cfg.cryptoLeft`, `cfg.cryptoRight`, `cfg.recLeft`, `cfg.recRight`, `cfg.recColor`, `cfg.barleft`, `cfg.barright`, `cfg.percleft`, `cfg.percright`, `cfg.column`, plus `cfg.typeAny`, `cfg.cryptoAny` (set for either left or right), `cfg.bar`, `cfg.percent`.

Conditions compile to a required/forbidden bitmask pair, so a check is two AND operations.

### Styles and fonts

- **Styles:** named colour sets resolved per state (selected, marked, fallback, unavailable, recorded).
- **Fonts:** `family;size` per item plus a `fontGroup` (`name`, `number`, `info`, `next`, `remaining`, `custom1..3`). The group's size delta from `config.usage.service*_fontsize` is applied when the template is set.

## Free layouts: grid and horizontal lists

```xml
<template name="grid" layout="grid" itemWidth="220" itemHeight="180">
  <row for="service" weight="3"> <item type="picon" width="*" margin="6"/> </row>
  <row for="service" weight="1"> <item type="text" text="{name}" width="*" align="center"/> </row>
</template>
```

`layout="list"` (default), `"horizontal"` or `"grid"`. A template can also set `itemSpacing` / `itemSpacingX` / `itemSpacingY` (gap between the tiles), `selectionZoom`, `carousel`, `carouselZoom`, `carouselFocus`, `carouselCenterWidth` and `carouselCenterHeight`; they replace the widget values while the template is active, and anything not set comes from the widget (see [LISTBOXES.md](LISTBOXES.md), section 9). A template without `itemHeight` / `itemWidth` uses the ones of the widget. `eListbox` already provides the grid/horizontal orientation; the content just reports it (`getOrientation` / `getItemWidth`). In a cell, stack rows with `height` / `weight`, and use `pos="x,y,w,h"` items for free placement.

### Runtime parameters

`width="@column"` takes the width from a numeric parameter (`setParam("column", n)`). While it is 0 or less the item is content sized. This reproduces the classic "columns" setting.

## Reference implementation

The DarkOS skin (`PLi-DarkOS`, `skin.xml`, right after `</colors>`) defines `single`, `double` and `double_next`, reproducing the classic list for that skin: same fonts, colours, separator, icon order and progress bar settings.

## Selecting it

`config.usage.servicelist_template`. The choices are built from the skin when the setting is created:

| Value | Meaning |
|---|---|
| `legacy` (default) | Classic renderer, no behaviour change. |
| `auto` | Templates `single` / `double` / `double_next` follow the existing "two lines" setting. |
| `<template name>` | One entry per template the skin defines, shown with its `title`. |

Only `legacy` is offered when the skin has no templates.

The choice is remembered per skin (`config.usage.servicelist_template_skins`, a JSON map from skin file to choice). When a skin is loaded, at startup or after a skin reload without restart, its remembered choice is restored; a skin without templates uses the classic list and does not overwrite the choices stored for other skins.

`createServiceList()` only returns the templated list if the skin defines templates and the setting is not `legacy`. Changing it needs a GUI restart.

The legacy renderer is kept as is; only its background/selection drawing was moved into shared helpers.

## Performance

- No Python in paint (the picon lookup only runs on a cache miss, shared with legacy).
- Per-service row cache holding a flat display list (text paras, pixmap blits, fills), built once; a repaint replays it.
- Cache invalidated by a template, size or flag change, by a change in dynamic state (recorded/fallback/unavailable), and by the event end time (or every 30 s when `{percent}`, `{remaining}` or a progress bar is used).
- Cache bounded: cleared above 256 rows.

## Deviation from the first sketch

The content class derives from the legacy class instead of both deriving from an extracted model base. The shared background/selection code was extracted instead. A pure model base can still follow once the legacy renderer is retired.

## Status

| Phase | State |
|---|---|
| 1. Shared paint helpers extracted, legacy list unchanged | written, not compiled |
| 2. `eListboxServiceTemplateContent`: compiler, layout, display list | written, not compiled |
| 3. `skin.py` parsing, `TemplatedServiceList`, config flag mapping | written, not run |
| 4. Default-skin templates reproducing today's look; parity check per config | TODO |
| 5. Profile against legacy on device | TODO |

Nothing has been built or run yet (no toolchain on the authoring machine).
