#pragma once

#include <memory>
#include <string>
#include <vector>

// Window show/hide animation presets for the EGL backend (Layer A of doc/ANIMATIONS.md).
//
// Pure math, no GL: a preset says how a window's snapshot is faded, scaled and moved over
// time; gEGLDC (gegldc.cpp) turns that into quads. The two settings below are written from
// the Python main thread (AnimationSetup via setAnimation_current/speed) and read on gRC's
// render thread, hence atomics.

namespace ganim {

// How a snapshot is drawn at one instant. Scale is about the anchor point (fractions of
// the window rect), the translation is in fractions of the window size.
struct Transform {
	float alpha;
	float sx, sy;
	float ax, ay;
	float tx, ty;
};

struct Preset {
	const char* name;
	float a0, a1;
	float sx0, sx1, sy0, sy1;
	float ax, ay;
	float tx0, tx1, ty0, ty1;
	bool stripes; // drawn as horizontal stripes sweeping in, transform ignored
	bool overshoot; // show eases out with a small overshoot
	int base_ms; // duration at the default speed
};

// Index 0 (and anything out of range) means "no animation". The numbering is the one
// AnimationSetup uses (1 simple fade ... 14 stripes).
const Preset* getPreset(int index);

void setPreset(int index);
void setSpeed(int speed);
int currentPreset();
int currentSpeed();

// The AnimationSetup entry "skin animations": windows then animate with the open/close rules of the
// skin (skin.ani) instead of one of the presets above.
const int kSkinPreset = 15;

// The "controls" switch: list animations (page slide, smooth scrolling, focus/unfocus of the rows) and
// the show/hide animations of widgets. Independent of the window preset, off until AnimationSetup turns
// it on (setAnimation_lists).
void setListsEnabled(bool enabled);
bool listsEnabled();

// Duration of a list page slide at `speed` (same 15..30 scale as durationMs()) and the 0..1 timeline
// position -> how far the slide has progressed (ease out).
int listDurationMs(int speed);
float listAmountAt(float t);

int durationMs(const Preset& preset, int speed);

// 0..1 timeline position -> how far the window is "in" (show: 0 -> 1, hide: 1 -> 0).
float amountAt(const Preset& preset, bool show, float t);

Transform evaluate(const Preset& preset, float amount);

// Destination rectangle (x0, y0, x1, y1) of a window rect (x, y, w, h) under a transform.
void destRect(const Transform& tr, float x, float y, float w, float h, float out[4]);

// ---------------------------------------------------------------------------------------
// Kodi style control animations (Layer B of doc/ANIMATIONS.md).
//
// An animation is a list of effects (fade, slide, zoom) that all run from the same start.
// Their tag and attribute names are Kodi's. Skins (skin.ani / skin.xml) are parsed by skin.py,
// which hands each animation over as a compact string; the engine keeps them in a registry and
// everything else only passes the integer id around.
//
//   effect  := type ( '|' key '=' value )*          type: fade | slide | zoom | rotate
//   spec    := effect ( ';' effect )*
//   keys    := start end time delay tween easing center
//
// `start`/`end`: fade = percent; slide = "x,y" pixels; zoom = "percent", "x,y" percent or
// "x,y,w,h" (the control is mapped onto that rect, relative to its own origin).
// `time`/`delay` in ms. `tween`: linear quadratic cubic sine back circle bounce elastic.
// `easing`: in out inout. `center`: "auto" (middle of the control) or "x,y" relative to it.
// ---------------------------------------------------------------------------------------

// An affine transform that only scales and moves, plus an opacity: x' = sx * x + tx.
// Coordinates are canvas pixels, so the controls' own rect has to be given to evaluateAnimation().
struct Xf {
	float alpha = 1.0f;
	float sx = 1.0f, sy = 1.0f;
	float tx = 0.0f, ty = 0.0f;
	bool identity() const;
};

enum class EffType { Fade, Slide, Zoom, Rotate };
enum class Tween { Linear, Quadratic, Cubic, Sine, Back, Circle, Bounce, Elastic };
enum class Easing { In, Out, InOut };

struct Effect {
	EffType type = EffType::Fade;
	float s[4] = {0, 0, 0, 0};
	float e[4] = {0, 0, 0, 0};
	int s_count = 0, e_count = 0;
	float delay_ms = 0, time_ms = 0;
	Tween tween = Tween::Linear;
	Easing easing = Easing::Out;
	bool center_auto = true;
	float cx = 0, cy = 0;
};

struct Animation {
	std::vector<Effect> effects;
	// Per row delay of a list's "itemopen" animation: row k starts k * stagger_ms later (key `stagger` of any effect).
	float stagger_ms = 0;
	// delay + time of the longest effect
	float durationMs() const;
};

// Parses `spec` for an animation of Kodi type `type` (windowopen, focus, unfocus, ...): the type
// only decides the defaults of fade (in types 0 -> 100, the others 100 -> 0). False if empty.
bool parseAnimation(const std::string& type, const std::string& spec, Animation& out);

// Registry used by skin.py: returns an id > 0 (equal specs share one) or 0 for an empty/invalid spec.
int registerAnimation(const char* type, const char* spec);
std::shared_ptr<const Animation> getAnimation(int id);

// The transform of `anim` after `elapsed_ms` for a control occupying (x, y, w, h). Before an
// effect's delay its start value applies, after its end the end value stays. All effects are combined.
Xf evaluateAnimation(const Animation& anim, float elapsed_ms, float x, float y, float w, float h);

float tweenValue(Tween tween, Easing easing, float t);

} // namespace ganim
