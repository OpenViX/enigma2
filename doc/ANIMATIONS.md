# GPU animations for enigma2 (EGL/GLES) - design proposal

Status: proposal, nothing implemented yet.

## 1. Goals and constraints

- Kodi-style animations on boxes with EGL/GLES: windows and popups opening and closing,
  list scrolling and focus, widgets appearing, disappearing and changing.
- The skin syntax adopts Kodi's tag and attribute names unchanged (section 4), so Kodi
  animation documentation and skin knowledge carry over.
- Users can enable or disable animations, per category (master switch, windows, lists,
  widgets, speed).
- A compile switch removes the feature for boxes without a working EGL/GLES. A build
  without it behaves exactly like today.
- One skin works on every box: `<animation>` elements are ignored where the feature is
  unsupported or disabled.
- Out of scope for v1: 3D flips (rotatex/rotatey with perspective), blur, shadows and
  anything involving the video plane.

## 2. What exists today (verified in this tree)

- `eWindow::show()/hide()` send `sendShow(rect)` / `sendHide(rect)` hints to the DC when
  the window animation mode is set. The painter also has `sendShowItem(dir, rect)`, which no
  `lib/gui` code calls.
- `gFBDC` implements the three opcodes with vendor code (`/proc/stb/fb/animation_mode`,
  `animation_current` presets, libvugles2). `gEGLDC` ignores them.
- `gEGLDC` renders into a persistent target (shadow FBO or a framebuffer page), treats
  `gOpcode::flush` as the end of frame (it calls `flip()`), and already has a "copy a region
  into a texture, redraw it as quads" pattern (the GPU spinner).
- Python closes a screen with `screen.hide()` before `screen.doClose()` (`Session.execEnd`,
  `deleteDialog`), so the `sendHide` hint arrives while the window is still fully drawn.
- `eWidgetAnimation` supports only a position move; its tick is only called from the unused
  `cmBuffered` composition mode of `eWidgetDesktop`.
- `eListbox` paints rows in a loop with a `selected` flag; scrolling is in whole lines
  (`m_top`), there is no pixel offset and no per-row transform.
- `eWidgetDesktop` precomputes per-widget clip regions (`calcWidgetClipRegion`) and paints
  dirty rectangles only (`cmImmediate`).

## 3. Architecture: two layers

### Layer A - frame animations inside gEGLDC (no widget changes)

Handles the three existing hints in the EGL backend.

- `sendShow(rect)`: flush the pending blit/text batches, copy the rect into a background
  texture. The window's normal draw opcodes then run. At `flush`, copy the rect again into
  a foreground texture and run N vsync frames: draw the background, then the foreground
  with the preset's transform and alpha. The last frame is the exact normal content.
- `sendHide(rect)`: copy the rect as the foreground. After the widgets behind it repaint,
  that area is the background. Animate the foreground out.
- `sendShowItem(dir, rect)`: the same snapshot method, sliding a list's contents by one row;
  `eListbox::moveSelection` must start sending it when a line scroll happens.
- Presets: keep the AnimationSetup names (simplefade, simplezoom, popup, slide*, zoom*, ...)
  as GLSL variants, speed from `setAnimation_speed`.
- Pacing: a loop on the render thread with `eglSwapInterval(1)`. This blocks later opcodes
  for the duration of the animation (the vendor library does the same). A non-blocking
  variant is a possible later step.
- Safety: skip the animation when the canvas is scaled down (`isScaled()`), a resolution
  change is pending, the framebuffer is locked, or the surface is lost. Platforms that do
  not preserve the back buffer must present from the shadow FBO on every animation frame.
  These are the same guards the GPU spinner uses.

Delivers window open/close, popups, InfoBar slide and sliding list scroll without Python
or skin changes.

### Layer B - control animations (the Kodi model)

- Data model: `Animation { type, condition?, reversible, repeat(none|pulse|loop),
  effects[] }`, `Effect { type, start, end, delay, time, tween, easing, center }` with
  types fade, fadediffuse, slide, zoom, rotate. Each effect yields a 2D matrix plus alpha;
  all effects of a widget multiply into one transform, applied through a hierarchical
  transform stack (parent x child), and alpha is multiplied into every draw colour.
- State machine, driven by wall-clock time (not frame count):
  process none/normal/reverse, state none/delayed/in-process/applied, start time and elapsed
  amount. A trigger only queues a process; it starts at the next tick. The opposite trigger
  (unfocus during focus, hidden during visible) reverses the running animation from its
  current position.
- Visibility is held by animations: a `hidden` animation keeps the widget visible until it
  finishes.
- Painter: new opcodes `setTransform(matrix, alpha)` and reset, honoured by `gEGLDC` and
  ignored by other DCs.
- Clip regions: a transformed widget leaves its precomputed clip region, so an animated
  widget cannot paint through the normal pass. During its animation it is rendered to an
  offscreen layer; the normal pass repaints what is behind it (old and new bounds are marked
  dirty on every tick) and an overlay pass composites the layer with the transform. v1
  simplification: the overlay is drawn above the window's other widgets.
- Triggers: `windowopen`/`windowclose` (Layer A covers whole screens), `visible`/`hidden`
  (from `ConditionalShowHide` and `conditional`), `focus`/`unfocus` (listbox selection
  change, for the old and new row). `conditional` needs an expression syntax, see section 7.
- Lists: a tweened pixel scroll offset replaces the integer `m_top`, with one extra partial
  row drawn. Each row keeps its own animation state, so the previously selected row finishes
  its `unfocus` animation while the new row runs `focus`.
- Reference: Kodi's `VisibleEffect.cpp` (CAnimation, CAnimEffect, CScroller),
  `GUIControl.cpp` (Animate, QueueAnimation, UpdateStates), `GUIWindow.cpp` (deferred close)
  and `GUIBaseContainer.cpp`. Kodi is GPL-2.0-or-later; the implementation here is written
  from the model, not copied.

## 4. Skin syntax: Kodi's, unchanged

Child elements of a `<screen>` or `<widget>`, parsed in `skin.py` into plain data:

```xml
<animation type="windowopen" reversible="false">
    <effect type="fade" start="0" end="100" time="200" tween="cubic" easing="out"/>
    <effect type="slide" start="0,60" end="0,0" time="200"/>
</animation>
```

- `type`: `windowopen`, `windowclose`, `visible`, `hidden`, `focus`, `unfocus`,
  `conditional`.
- `condition`, `reversible`, and for conditional animations `pulse="true"` / `loop="true"`.
- `effect` `type`: `fade`, `fadediffuse`, `slide`, `zoom`, `rotate` (z), `rotatex` and
  `rotatey` (accepted, ignored in v1).
- `start`, `end`, `delay`, `time` (ms), `tween` (`linear`, `quadratic`, `cubic`, `sine`,
  `back`, `circle`, `bounce`, `elastic`), `easing` (`in`, `out`, `inout`), `acceleration`,
  `center` (`auto` or `x,y`).
- Zoom `start`/`end` take `percent`, `x,y` percent, or `x,y,w,h` as in Kodi.
- Old inline form `<animation effect="fade" time="200">WindowOpen</animation>` and the
  `VisibleChange` shorthand (creates `visible` plus the reversed `hidden`) are accepted.
- Defaults as in Kodi: in-effects fade 0 to 100, out-effects fade 100 to 0.

## 4a. Default animation file: `skin.ani`

Writing `<animation>` into every widget of a skin is a lot of work, so animations can be
collected in one file per skin instead: `skin.ani`, next to the skin's `skin.xml`, for example
`/usr/share/enigma2/MaterialSkinCockpit/skin.ani`. The file is optional. Its root is
`<animations version="1">`; a complete example for a real skin is `skin.ani` in the
MaterialSkinCockpit repository.

Rules are `<screen>` and `<widget>` elements whose attributes select what they apply to,
and whose children are the same Kodi `<animation>` elements as in section 4, plus the list
elements `<scrolltime>` and `<focusedlayout>` (which holds the `focus`/`unfocus`
animations for a row):

```xml
<animations version="1">
    <screen name="InfoBar,MoviePlayer">
        <animation type="windowopen">
            <effect type="slide" start="0,120" end="0,0" time="220" tween="cubic" easing="out"/>
        </animation>
    </screen>
    <widget render="Listbox">
        <scrolltime tween="cubic" easing="out">180</scrolltime>
        <focusedlayout>
            <animation type="focus"><effect type="zoom" start="100" end="103" center="auto" time="120"/></animation>
            <animation type="unfocus"><effect type="zoom" start="103" end="100" center="auto" time="120"/></animation>
        </focusedlayout>
    </widget>
</animations>
```

- Selectors: for a `<screen>` rule `name`; for a `<widget>` rule `render`, `source`, `name`,
  `addon`, optionally narrowed by `screen`. Values are comma separated lists with `*` and `?`
  wildcards. A rule without selectors applies to everything of its kind: a plain `<screen>`
  is the rule for all screens, a plain `<widget>` for all widgets. `name` of a screen rule
  matches any entry of the screen's name list (the skin name plus the class names in its
  chain, as in enigma2's "Processing screen ... from list ..." log line), so a rule can
  target a base class such as `Setup` and cover every screen derived from it.
- Cascade, evaluated separately for every animation type: an `<animation>` inside skin.xml
  wins over a `.ani` rule; among `.ani` rules the one with the most selector attributes wins,
  a later rule wins a tie; otherwise there is no animation.
- An empty `<animation type="..."/>` cancels what a less specific rule would give, so a rule
  for all screens can be switched off for, say, the volume bar or the standby screen.
- Loaded once at skin load by `skin.py` from the current skin directory and resolved into
  the same plain data structure as inline animations, so the engine does not know where an
  animation came from. Whole-file switches (master, categories, speed) apply to it like to
  anything else (section 5).
- Boxes without the feature do not read the file. It is a data file with no code, so the
  same skin package works everywhere.
- Install: listed in the skin's `Makefile.am` (`install_DATA`).

## 5. Build switches and user settings

Build:
- The engine (snapshot and layer compositing, animation shaders) lives under
  `lib/gdi/egl/`, so it exists only with `--with-egl` (`HAVE_EGL`).
- Generic parts (state machine, tween, painter opcodes, skin parsing) are always built, so
  Python and skins are identical on every box; without the engine they are no-ops: the DC
  ignores the opcodes, `IsAnimating()` returns false and nothing is deferred.
- A second switch `--enable-egl-animation` (default yes when EGL is on, define
  `HAVE_EGL_ANIMATION`) lets a distro keep EGL for rendering but drop animations; hot paths
  (per-row listbox transform, deferred visibility) sit behind it.
- Both configurations (with and without EGL) must build; the non-EGL build must contain no
  references to the engine.

Runtime:
- A Python capability flag (for example `SystemInfo["HasEGLAnimation"]`), true only if the
  feature is built in and the GLES context came up.
- Config entries: master switch, windows, lists, widgets, speed (effects slowdown). The
  existing AnimationSetup plugin is extended and hidden when the capability is false.
- Settings are pushed into the C++ engine when they change and checked at trigger time. When
  off, triggers queue nothing and state changes apply instantly, with no extra invalidation,
  so behaviour equals today's.
- The driver-level animation (`HAVE_OSDANIMATION`, `/proc/stb/fb/animation_mode`) is not
  written on boxes using this engine; the two never run together.

## 6. Phases and acceptance

1. Plumbing: configure switches, config entries, capability flag, no-op stubs, both builds.
   Accept: no behaviour change; the non-EGL build has no engine references.
2. Layer A windows: `sendShow`/`sendHide` snapshots and three presets (fade, zoom, slide).
   Accept: menus, popups and InfoBar animate on dm900 and one window-surface box, with no
   stale or black frames and correct alpha over video.
3. Layer A lists: `sendShowItem` from the listbox, slide scroll, remaining presets, speed
   setting.
4. Engine: C++ animation state machine, tweens, painter transform opcodes, Kodi skin
   parsing, widget visible/hidden fades.
5. Lists in the engine: pixel scrolling, per-row focus/unfocus, content cross-fade.
6. Extras: loop and pulse, rotate, per-screen opt-out.

## 6a. Implementation status

Phase 1 and the window part of phase 2 (Layer A) are implemented and run on the dm900. Phase 3 (list
page slide, below) is implemented but has not been run on a box yet.

- Build switch: `--enable-egl-animation` (default yes when EGL is on) defines
  `HAVE_EGL_ANIMATION`. The AnimationSetup plugin is built for it unless the libvugles2 or
  OSD-animation paths already build it.
- `lib/gdi/egl/ganimation.{h,cpp}`: presets, easing and transform math (no GL), and the two
  atomics for the current preset and speed.
- `gEGLDC`: handles `sendShow`/`sendHide`. At the hint the rect is copied into a texture; at the
  first flush after the window's own draw opcodes ran, the second snapshot is taken and the
  animation plays as ordinary frames (restore base snapshot, draw the moving snapshot with the
  preset transform, `flip()`), ending with an exact write-back of the real final content.
  Skipped when the canvas is scaled, a resolution change is pending, the surface is lost, the
  framebuffer is locked, the spinner is active, or no preset is selected.
- `setAnimation_current(idx)`/`setAnimation_speed(n)`: the existing AnimationSetup interface now
  reaches the engine (`main/enigma.cpp`). Preset 0 is "disabled" and is the default, so nothing
  animates until the user picks one under Menu > Skin setup > Animations.
- `eWindow`: the animation mode is now initialised for every window (it used to be set only in
  the first window's constructor) and counts as supported on EGL boxes.
- The presets are approximations of the vendor ones (simplefade, simplezoom, growdrop,
  growfromleft, extrudefromleft, popup, slidedrop, slidefromleft, slidelefttoright,
  sliderighttoleft, slidetoptobottom, zoomfromleft, zoomfromright, stripes).

Lessons from the first run on the dm900, kept so Layer B does not repeat them:

- The "after" snapshot must be taken only once the window's rect has been repainted. A hide
  flushes unrelated draw ops (a clock) before the area behind repaints; the engine therefore tracks
  the part of the rect covered by the clip regions of the draw opcodes since the hint and waits
  for 60% (hide) / 25% (show) of it. It gives up after 1 s, which means no animation, never a bad
  write-back.
- Pixmap-page platforms leave the READ surface on the page that was just presented
  (`gpuCopyPageContent()` only makes the new page the DRAW surface). A capture with
  `glReadPixels`/`glCopyTexImage2D` must first make read = draw (`captureAnimTexture()` does),
  otherwise it returns the previous frame and the write-back puts stale content over the window.

Phase 3, list page slide (Layer A lists):

- `eListbox::moveSelection()` sends `sendShowItem(dir, rect)` (via `eWidget::sendShowItem()` and
  `eWidgetDesktop`) when the selection changes the page (`m_top`/`m_left`). `dir` is +-1 for a
  vertical and +-2 for a horizontal slide, + meaning forward. The opcode exists for the EGL build
  (`HAVE_EGL_ANIMATION`) as well as libvugles2; other DCs never receive it.
- `gEGLDC::beginListAnimation()` snapshots the list rect, the same coverage wait as for windows
  (40%) takes the second snapshot after the list repainted, and `runListAnimation()` moves the old
  and the new page through the rect as one strip, both drawn as exact overwrites (no blending, so
  video holes stay transparent). A pending window animation is never interrupted by a list hint.
- It has its own switch, independent of the window preset: `setAnimation_lists(0/1)`, set from the
  AnimationSetup settings ("Slide list pages", off by default) and applied at session start.
  Duration is 260 ms at the default speed, scaled by the speed setting (`ganim::listDurationMs`).
- The whole list widget is slid, including its scrollbar.

Layer B, first slice (list rows, compiles, not run on a box yet):

- `ganim` (lib/gdi/egl/ganimation.{h,cpp}) has the Kodi model: `Effect` (fade, slide, zoom; rotate is
  parsed and ignored), `Animation`, the eight tweens with in/out/inout easing, delay, `center`, and
  `evaluateAnimation()` which turns an animation, an elapsed time and the control's rect into a
  scale + move + opacity transform (`Xf`). Animations are registered from a compact string
  (`zoom|start=100|end=103|center=auto|time=120|tween=sine|easing=out;fade|...`) and referred to by
  an integer id (`registerAnimation(type, spec)`, also exposed to Python). Unit-tested natively.
- A new painter opcode `setTransform(sx, sy, tx, ty, alpha, limit)` / `resetTransform()` (EGL only,
  ignored by every other DC). `gEGLDC` applies it by adding the scale/move to the shaders' projection
  matrices, mapping every scissor rect the same way and cutting it to `limit`, and multiplying the
  opacity into rectangles (blended while it is below 1), blits and text. Pending batches are flushed
  at each change and a transform never outlives a frame.
- `eListbox::setFocusAnimation(focus_id, unfocus_id)`: the selected row is drawn with the `focus`
  transform, which stays applied while it is selected, and the row the selection leaves plays
  `unfocus`. Rows with a transform are drawn in a second pass, on top of their neighbours, and an
  `eTimer` repaints the animated rows (and their neighbours) every 16 ms. Vertical and horizontal
  lists, switched by the same "lists" switch as the page slide.
- `skin.py` loads `skin.ani` (next to the primary skin's skin.xml) and resolves the selectors and the
  cascade per widget (`render`, `source`, `name`, `addon`, `screen`); for listboxes the resolved
  `focus`/`unfocus` animations (also inside `<focusedlayout>`) become the skin attribute
  `listAnimation="<focus id>,<unfocus id>"`. Older builds without the engine skip all of it.

Limits of this slice: the transform moves and scales, it does not clip the content to the scaled
row (the row is only cut to the list); a zoomed row is pixel-scaled, not re-rendered; opacity does not
reach border colours, the rounded-corner texture pieces or plain `fill`/`line` draws when blending is
off; grids are not animated.

Layer B, the rest of the `skin.ani` rules (compiles, not run on a box yet):

- `<scrolltime tween="cubic" easing="out">180</scrolltime>` in a widget rule gives the list a scroll
  animation (the time, tween and easing of its first effect) **and turns on
  smooth scrolling for it**: the list moves by single rows, just far enough to keep the selection in view,
  instead of flipping a page. A row scroll slides the old and the new content by one row (`step` of the
  `sendShowItem` hint); a jump of more than one row (wrap-around, page keys) still slides a whole page.
  `<scrolltime>0</scrolltime>` cancels it for a list. The scrollbar thumb follows row by row.
- `visible`/`hidden` rules (and the old `VisibleChange` form, which creates the reversed `hidden` too):
  a widget that is shown or hidden while its window is up (a converter, `ConditionalShowHide`) animates
  with the snapshot method, like a window. Not while its window is opening (first 800 ms), not while
  another animation is pending, and only for widgets whose rule resolved to an animation.
- `windowopen`/`windowclose` rules: every screen gets the animation its rules resolve to. A rule with
  no effects cancels it for that screen (`-1`); a screen no rule matches (`0`) falls back to the
  AnimationSetup preset. The windows only use the skin's animations with the new AnimationSetup entry
  **"Skin animations"** (preset 15); the other presets keep working as before.
- Everything is driven by the same snapshot machinery (`runSpecAnimation()`): the transform of the
  moving snapshot is `evaluateAnimation()` at the elapsed time, drawn inside
  the hinted rect.
- "Animate lists and controls" (the former "lists" switch) now covers the row animations, the scroll
  slide and the widget show/hide animations.

Not done yet: `conditional` animations, animations written inside skin.xml, rotate, and the clipping of a
scaled row to its own rect.

First things to check on a box: a list slides one page when the selection passes the last visible
row and back, in a menu, the channel list and a horizontal list; the page after the slide is
identical to one without; no black or stale frames; the plain fade on a menu opening and closing,
and the behaviour over live video (alpha at the window edges).

## 7. Risks and open questions

- Layer A blocks the render thread for the length of an animation. Accepted for v1.
- Overlay z-order in Layer B (animated widgets drawn above the window's others) and the
  cost of repainting behind animated widgets on weak GPUs.
- Memory: a full-screen RGBA texture is about 8 MB; keep to two or three.
- Alpha semantics: the video-hole versus true-alpha blend modes and the premultiplied-output
  flags (`m_premultiply_*`, `m_straight_alpha_present`) must be respected so fades neither
  punch holes nor leave halos.
- Platform spread: Dreambox pixmap surfaces, window surfaces with and without the shadow
  FBO, libMali with conservative readback, VideoCore with a 2048 texture limit, and the
  separate libvugles2 path. Start with dm900 plus one window-surface box.
- Windows that are re-shown instead of recreated need a check of the hide/show hint timing.
- `condition` (and `conditional` animations): Kodi evaluates info-label expressions every
  frame; enigma2 is event driven through sources and converters. v1 supports `type`s that do
  not need a condition; an expression syntax tied to sources must be decided before
  `conditional` is implemented.

### AnimationSetup plugin

The plugin has a single switch, "Enable animations" (`config.misc.window_animation_enabled`, off by
default). On: the "Skin animations" preset (15, the rules of the skin's skin.ani) plus the list/control
animations on EGL builds, or the simple fade on other engines. Off: no animations at all. The
presets, speed setting, preview and per-feature switches were removed; all times come from skin.ani.

Window animations are currently switched off by the plugin (`setAnimation_current(0)`): a window
animation needs two read backs of the window (about 350 ms each for a full screen on the dm900), which
made opening a screen take over a second. "Enable animations" now only switches the list and control
animations (focus effect, smooth scrolling, widget fades). The window rules of skin.ani are kept for when
the capture is fast enough.

### List scrolling and the render queue (dm900)

- Smooth scrolling of vertical lists never takes a snapshot: `eListbox` paints the rows `scrollOffset()`
  pixels off their place, eased to 0 over the skin's `<scrolltime>`, for up to 3 rows per step. Page jumps
  (page up/down) and positioning the list (`justCheck`) just flip, and so do lists without `<scrolltime>`.
- A full list is about 190 opcodes, which the render thread needs about 45 ms for; the `gRC` queue holds 2048.
  `animationTick()` therefore skips a frame while the queue is still busy (`gRC::pendingOpcodes()`: more than
  60 for scroll frames, more than 250 for the small row effect frames), else the main thread would block in
  `gRC::submit()` and key handling would stall.
- The key press of an isolated scroll queues several frames at once (the list and everything following the
  selection), so the animation clock is held at its start until the queue has drained (at most 400 ms);
  otherwise the animation is over before its first frame is on screen. A scroll that follows another within
  400 ms (key held) starts at once.

### Entrance of list rows (`itemopen`)

A list rule `<animation type="itemopen" stagger="40">` with its effects makes the rows come in one after the
other when the list is first shown: row k (counted from the top of the page) starts k * `stagger` ms after the
first. It is a list animation like the focus effect (rows are drawn in the second, transformed pass), so no
snapshot is needed. The clock starts when the render queue has drained after the first paint (at most 400 ms),
and the rows wait at their start state until then. Selectors work as for the other list rules, e.g.
`<widget render="Listbox" screen="PluginBrowser">`. Python: `eListbox.setOpenAnimation(id)` (skin attribute
`listOpen`).

A zoomed row or grid cell is kept inside the list rectangle (everything is clipped to it): the scale is limited
to what fits (a row as wide as the list does not zoom) and the cell is moved inwards where it would stick out,
so a cell at the edge of a grid zooms with its outer edges in place. While the entrance of a list runs, the
focus effect of the selected row is combined with it.
