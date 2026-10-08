# Animations: how they work and how to define them in skin.ani

This describes the animations as they are implemented now. The design discussion, the reasons
behind it and the original phase plan are in `ANIMATIONS_PROPOSAL.md`.

## 1. Overview

Animations run in the EGL/GLES backend (`gEGLDC`), take their definitions from a rules file of the
skin, `skin.ani`, and use Kodi's tag and attribute names. A skin author never touches `skin.xml` for
this; one file collects the rules for all screens and widgets.

What is animated:

| What | Trigger | Rule in skin.ani |
|---|---|---|
| Selected row of a list or grid cell | selection moves | `focus`, `unfocus` |
| Scrolling of a list | selection leaves the visible rows | `<scrolltime>` |
| Entrance of the rows of a list | list is shown the first time | `itemopen` (with `stagger`) |
| A widget that appears or disappears | a converter such as `ConditionalShowHide` shows or hides it | `visible`, `hidden` |
| A window | opens or closes | `windowopen`, `windowclose` |

Not implemented yet: `conditional` animations, `rotate` (parsed, not drawn), animations written
inside `skin.xml`, and the Kodi attributes `reversible`, `pulse`, `loop`, `acceleration` and `condition`
(ignored). `fadediffuse` is ignored too.

A window animation is a snapshot animation (section 8) of the area covered by the window's widgets, not of the
window itself: an info bar, which is a bar at one edge of a full screen window, costs its bar; a full screen
menu would cost two reads of the whole screen (about 350 ms each on the dm900). Only windows that a rule of
`skin.ani` names are animated, so a skin gives rules to small windows (the OSD, dialogs) only.

## 2. Requirements and the switch

- Build: `--enable-egl-animation` (default yes when `--with-egl` is on) defines
  `HAVE_EGL_ANIMATION`. Without it none of this is compiled and the skin's `skin.ani` is ignored.
  Boxes without EGL are not affected in any way.
- User setting: **Show animations**, the last entry of Menu > Setup > User Interface > Settings
  (`config.usage.show_animations`, off by default; shown only when the engine is built in,
  `SystemInfo["HasAnimations"]`). It is the master switch, applied through `setAnimation_lists()`: off, nothing is
  animated; on, the rules of `skin.ani` decide what is: lists, widgets and the windows a rule names. There is
  nothing else to set: which screens and widgets animate is up to the skin. A skin without a `skin.ani` (and
  without the default one, section 3) is not animated, and neither is anything no rule names.
- There is no AnimationSetup plugin for the EGL engine; libvugles2 and the driver-level `HAVE_OSDANIMATION`
  paths keep theirs.
- Changes to `skin.ani` are read when the skin is loaded: restart the GUI after editing.

## 3. Where skin.ani is found

`skin.py` resolves `skin.ani` with `resolveFilename(SCOPE_GUISKIN, "skin.ani")`, not from the name of
the skin file. The first file found in this order is used:

1. `/etc/enigma2/<SkinName>/skin.ani` (a user's override for one skin)
2. `/etc/enigma2/skin_common/skin.ani`
3. `/etc/enigma2/skin.ani`
4. `/usr/share/enigma2/<SkinName>/skin.ani` (the one the skin ships)
5. the fallback skins (`skin_fallback_<resolution>`, `skin_default`, `/usr/share/enigma2/`)

enigma2 ships a default for skins that have none, `data/skin.ani` (installed as `/usr/share/enigma2/skin.ani`, step 5): the values of Kodi's
default skin Estuary: window fade, dialog pop-up, OSD slide, smooth scrolling, the focus fade of the selected item,
the zoom of a focused grid cell and fading widgets, for all screens.

Only that one file is read; files are never merged, so a user's file replaces the skin's own. The log
shows what happened: `[Skin] Loaded N animation rules from '<path>'.` If that line is missing, no file was
found or it could not be parsed.

## 4. The file format

```xml
<?xml version="1.0" encoding="utf-8"?>
<animations version="1">
    <screen name="InfoBar,MoviePlayer">
        <animation type="windowopen">
            <effect type="fade" start="0" end="100" time="220" tween="cubic" easing="out"/>
            <effect type="slide" start="0,120" end="0,0" time="220" tween="cubic" easing="out"/>
        </animation>
    </screen>

    <widget render="Listbox">
        <scrolltime tween="cubic" easing="out">180</scrolltime>
        <focusedlayout>
            <animation type="focus">
                <effect type="zoom" start="100" end="108" center="auto" time="150" tween="cubic" easing="out"/>
            </animation>
            <animation type="unfocus">
                <effect type="zoom" start="108" end="100" center="auto" time="150" tween="cubic" easing="out"/>
            </animation>
        </focusedlayout>
    </widget>
</animations>
```

The root holds **rules**. A rule is a `<screen>` or a `<widget>` element; every other child is ignored. A rule's
attributes select what it applies to, its children define the animations:

- `<animation type="...">` with one or more `<effect>`: an animation (section 6).
- `<focusedlayout>`: a container for the row animations (`focus`, `unfocus`, `itemopen`) of a list. The
  same `<animation>` elements directly inside the rule work as well.
- `<scrolltime>`: smooth scrolling of a list (section 7).

A rule may contain animations of several types; each type is resolved on its own (section 5).

### Selectors

| Rule | Attribute | Matches |
|---|---|---|
| `<screen>` | `name` | any entry of the screen's name list: the skin name plus the class names in its chain (the "from list '...'" in the log line `Processing screen ...`) |
| `<widget>` | `screen` | the same name list of the screen that holds the widget |
| `<widget>` | `render`, `source`, `name`, `addon` | the widget's own attribute of that name |

Values are comma separated lists of patterns using `fnmatch` syntax (case sensitive; `*`, `?`, `[abc]`).
An attribute that is not given does not restrict, so a rule without any selector applies to all screens
or all widgets. A list component the skin names rather than renders (no `render` attribute) counts as
`render="Listbox"`.

## 5. Which rule wins

For every animation type separately, among all rules that match, the one with the **most selector
attributes** wins; a later rule wins a tie. Consequences:

- A general rule for all screens can be refined for some screens without repeating anything.
- An animation element **without effects**, such as `<animation type="windowopen"/>`, is a rule that
  gives "no animation" and so cancels what a less specific rule would give.
- For a type no rule defines there is no animation. Both a missing rule and an empty animation mean "not
  animated"; the empty one also wins over a more general rule.

## 6. Animation types and effects

| `type` | Applies to | Notes |
|---|---|---|
| `windowopen`, `windowclose` | `<screen>` rules | only for windows a rule names; the area of the window's widgets is animated, see 1 |
| `visible`, `hidden` | `<widget>` rules | a widget shown or hidden while its window is up; not during the first 800 ms of the window and not while another animation is pending |
| `focus`, `unfocus` | `<widget>` rules for lists | the selected row, and the row the selection leaves; also lists in grids |
| `itemopen` | `<widget>` rules for lists | rows come in when the list is first shown; `stagger` per row |
| `conditional` | - | accepted, not used |

`<effect>` attributes:

| Attribute | Meaning |
|---|---|
| `type` | `fade`, `slide`, `zoom`. `rotate`, `rotatex`, `rotatey` are parsed and not drawn |
| `start`, `end` | fade: percent opacity. slide: `x,y` in pixels. zoom: one percent, `x,y` percent, or `x,y,w,h` (the control is mapped onto that rectangle, relative to its own origin) |
| `time`, `delay` | milliseconds (default 0, so always give a `time`) |
| `tween` | `linear` (default), `quadratic`, `cubic`, `sine`, `back`, `circle`, `bounce`, `elastic` |
| `easing` | `in`, `out` (default), `inout` |
| `center` | zoom: `auto` (the middle of the control, default) or `x,y` relative to the control |
| `stagger` | `itemopen` only: ms between two rows; row *k* starts *k* x `stagger` after the first |

All effects of one animation run together from the same start. Defaults when `start`/`end` are left
out follow Kodi: a fade in `windowopen`, `visible`, `focus` and `conditional` runs 0 to 100, in the others 100
to 0; a zoom is 100 to 100.

The old inline Kodi form is accepted: `<animation effect="fade" start="0" end="100" time="100">VisibleChange</animation>`.
`VisibleChange` stands for a `visible` animation plus the reversed `hidden` one.

## 7. Lists

`<scrolltime tween="cubic" easing="out">180</scrolltime>` in a list rule gives the list **smooth scrolling**:
it moves by single rows, just far enough to keep the selection in view, with the given time, tween and
easing. `<scrolltime>0</scrolltime>` turns it off for a list. What happens depends on the list:

| List | Selection moves by | Result |
|---|---|---|
| vertical, with `<scrolltime>` | up to 3 rows | smooth scroll, rows painted off their place and eased to 0 |
| vertical | more than 3 rows (page up/down, wrap-around), or the list is positioned on an entry | just flips, no animation |
| vertical, without `<scrolltime>` | any | just flips |
| grid | any | just flips |
| horizontal | one item or a page | slide of the old and new page (snapshot), by one item with `<scrolltime>`, else a whole page |

The row animations (`focus`, `unfocus`, `itemopen`) work for vertical and horizontal lists and grids.

Row animations are applied while the row is selected (`focus` stays applied) and `unfocus` plays on the
row the selection leaves. Everything of a list is clipped to the list's rectangle, so a row as wide as
the list does not visibly zoom: use a slide or fade there (the skin's own `skin.ani` does) and keep
zoom for grids.

A rule for a particular screen is written with the `screen` selector, for example the plugin browser's grid:

```xml
<widget render="Listbox" screen="PluginBrowser">
    <animation type="itemopen">
        <effect type="fade" start="0" end="100" time="200" tween="cubic" easing="out" stagger="40"/>
    </animation>
</widget>
```

Lists that a skin builds inside an `<applet>` (for example the main menu) get their rules through
`skin.setListAnimation(instance, screenName, widgetAttrib)` called from the applet code.

## 8. How it works

```
skin.ani --skin.py--> rules --resolve per widget--> registerAnimation(type, spec) --> id
                                                   skin attributes: listAnimation, listScroll,
                                                   listOpen, visibilityAnimation, windowAnimation
        C++ widgets (eListbox, eWidget, eWindow) keep the ids and start the animations
        painter opcodes setTransform/resetTransform, sendShow/sendHide/sendShowItem
        gEGLDC draws them
```

- **`skin.py`** parses `skin.ani` once when the skin loads (`loadAnimationRules()`). When a widget is created
  it resolves the cascade for the types that make sense for it and turns each result into a compact string
  (`zoom|start=100|end=108|center=auto|time=150|tween=cubic|easing=out;fade|...`). `registerAnimation()`
  (`ganimation.cpp`, also exposed to Python) stores it in a registry and returns an integer id; equal
  strings share an id. The ids reach the C++ objects as skin attributes (`listAnimation="<focus>,<unfocus>"`,
  `listScroll`, `listOpen`, `visibilityAnimation="<show>,<hide>"`, `windowAnimation="<open>,<close>"`).
  The id 0 means "no animation", -1 for a window "cancelled by a rule".
- **`ganim`** (`lib/gdi/egl/ganimation.{h,cpp}`) holds the Kodi model: effects, the eight tweens,
  delay, `center`, and `evaluateAnimation()`, which turns an animation, an elapsed time and the
  control's rectangle into a scale, a move and an opacity. It has no GL code and is unit tested natively.
- **List rows.** The selected row is drawn with the `focus` transform; the row that was left plays
  `unfocus`. Rows that carry a transform are drawn in a second pass on top of their neighbours, and a
  timer repaints the animated rows every 16 ms. The painter opcode `setTransform(sx, sy, tx, ty, alpha,
  limit)` applies it: `gEGLDC` adds the scale and move to the shaders' projection, maps every scissor
  rectangle the same way and cuts it to `limit` (the list), and multiplies the opacity into rectangles,
  blits and text. Pending batches are flushed at each change; a transform never outlives a frame.
- **Smooth scrolling.** `eListbox` paints the rows a few pixels off their place, eased to 0 over the
  `<scrolltime>` and is limited to 3 rows per step; no snapshot is taken. Only horizontal lists still send
  `sendShowItem`, a page slide using the snapshot method below.
- **Snapshots (widget show/hide, page slide, windows).** On the hint (`sendShow`, `sendHide`,
  `sendShowItem`) the engine copies the rectangle into a texture. When the area has been repainted (it
  watches the clip regions of the draw opcodes; it gives up after 1 s, which means no animation) it
  copies it again and plays the animation as ordinary frames: restore the base snapshot, draw the moving
  one with the transform of the animation at that time, `flip()`. The last step writes back the exact final
  content, so the screen after an animation is identical to one without. It is skipped while the canvas is
  scaled, a resolution change is pending, the surface is lost, the framebuffer is locked or the spinner
  is active.
- **Render queue.** A full list is about 190 opcodes (about 45 ms of render thread on the dm900), so the
  animation timer skips a frame while the render queue (`gRC::pendingOpcodes()`) is busy, and holds the
  animation clock at its start until the queue has drained (at most 400 ms) after a key press.

## 9. Writing rules: practical notes

- Start with the general rules (no selector) and add specific ones below them; with equal selector
  counts the later rule wins.
- Keep times short: 100-200 ms for rows and widgets. Longer ones make navigation feel slow, because a
  list is redrawn every frame while it animates.
- To switch something off for one screen, give that screen an empty animation of the type.
- `<scrolltime>` is the only list animation not written as `<animation>`. Without it a list flips pages.
- Check the log for the "Loaded N animation rules" line after a change; an XML mistake makes the whole
  file silently produce 0 rules.
- A shipped `skin.ani` can be overridden without touching the skin by putting a complete copy in
  `/etc/enigma2/<SkinName>/`.

## 10. Known limits

- The transform moves and scales; it does not clip a scaled row to its own rectangle, only to the list.
  A zoomed row is pixel-scaled, not re-rendered. Opacity does not reach border colours, the
  rounded-corner texture pieces or plain `fill`/`line` draws when blending is off.
- `visible`/`hidden` animations are snapshot based: they need the area under the widget repainted, so they
  suit widgets on an otherwise static background.
- A window animation reads back the area of the window's widgets twice (about 150 ms per 3.7 MB on the dm900), so
  a rule for a full screen window makes it open slowly. A window without a rule is not animated.
- Alpha over live video follows the OSD's blend modes; fades near the window edges are the first thing to
  check on a new box.

## 11. Differences to Kodi

- Rules live in one file selected by attributes; Kodi writes `<animation>` into every control.
- No info-label conditions, so no `conditional` animations and no `condition` attribute.
- Only fade, slide and zoom; no 3D rotation, no `fadediffuse`.
- `reversible`, `pulse`, `loop` and `acceleration` are not supported; reversing is implicit (a hide is the
  reverse of a show).
- Clipping: everything is clipped to the list or window rectangle, which Kodi does not do.
