"""Render preview screenshots of the KeyForge window for every profile.

These are *renderings* of the layout defined in keyforge/gui.py, drawn with Pillow from the
same profiles.json, the same lock geometry and real output of keyforge.core.generate().
They exist so docs can be produced on machines without a display / tkinter. Real Tk widgets
differ slightly per OS (fonts, button chrome), so treat them as faithful previews, not captures.

Usage:  python tools/render_previews.py            (needs: pip install pillow)
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from keyforge.branding import lock_shapes, shade  # noqa: E402
from keyforge.core import LENGTH_RANGES, LENGTH_UNITS, MODE_LABELS, generate, soft_wrap  # noqa: E402
from keyforge.profiles import Profile, action_for, load_profiles  # noqa: E402

K = 4          # internal supersampling factor
OUT_SCALE = 2  # final pixel density (2 = "retina")
W, CHROME = 520, 30
RATING_COLORS = ("#d64545", "#e08a3c", "#d6b73c", "#7fb944", "#2f9e5b")

FONT_DIR = Path("/usr/share/fonts/truetype")
SANS = FONT_DIR / "liberation/LiberationSans-Regular.ttf"
SANS_B = FONT_DIR / "liberation/LiberationSans-Bold.ttf"
MONO_B = FONT_DIR / "dejavu/DejaVuSansMono-Bold.ttf"
MONO_R = FONT_DIR / "dejavu/DejaVuSansMono.ttf"


def font(path: Path, pt: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), round(pt * 1.333 * K))


class Canvas:
    def __init__(self, w: int, h: int, bg: str):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * K, h * K), bg)
        self.d = ImageDraw.Draw(self.img)

    def rect(self, x1, y1, x2, y2, fill=None, outline=None, width=1):
        self.d.rectangle([x1 * K, y1 * K, x2 * K - 1, y2 * K - 1], fill=fill, outline=outline,
                         width=width * K if outline else 0)

    def text(self, x, y, s, f, fill, anchor="la"):
        self.d.text((x * K, y * K), s, font=f, fill=fill, anchor=anchor)

    def width_of(self, s, f) -> float:
        return self.d.textlength(s, font=f) / K

    def final(self) -> Image.Image:
        return self.img.resize((self.w * OUT_SCALE, self.h * OUT_SCALE), Image.LANCZOS)


def wrap_chars(c: Canvas, value: str, f, max_px: float) -> list[str]:
    lines, cur = [], ""
    for ch in value:
        if c.width_of(cur + ch, f) > max_px and cur:
            lines.append(cur)
            cur = ""
        cur += ch
    return lines + [cur] if cur else lines


def draw_lock(c: Canvas, cx, cy, s, accent, bg):
    for shape in lock_shapes(cx, cy, s):
        kind, role = shape[0], shape[-1]
        col = accent if role == "accent" else bg
        if kind == "arc_top":
            x1, y1, x2, y2 = shape[1]
            hw = shape[2] / 2  # Tk centres stroke on the path; Pillow draws inward -> grow bbox
            c.d.arc([(x1 - hw) * K, (y1 - hw) * K, (x2 + hw) * K, (y2 + hw) * K], 180, 360,
                    fill=col, width=round(shape[2] * K))
        elif kind == "line":
            x1, y1, x2, y2 = shape[1]
            c.d.line([x1 * K, y1 * K, x2 * K, y2 * K], fill=col, width=round(shape[2] * K))
        elif kind == "rrect":
            x1, y1, x2, y2 = shape[1]
            c.d.rounded_rectangle([x1 * K, y1 * K, x2 * K, y2 * K], radius=shape[2] * K, fill=col)
        elif kind == "oval":
            x1, y1, x2, y2 = shape[1]
            c.d.ellipse([x1 * K, y1 * K, x2 * K, y2 * K], fill=col)
        elif kind == "rect":
            x1, y1, x2, y2 = shape[1]
            c.d.rectangle([x1 * K, y1 * K, x2 * K, y2 * K], fill=col)


def render_window(profile: Profile, policy, history: list[str], status: str) -> Image.Image:
    t = profile.theme
    result = generate(policy)
    mode = policy.mode
    has_options = mode in ("password", "passphrase")

    f_ui, f_ui_b = font(SANS, 10), font(SANS_B, 10)
    f_small, f_title = font(SANS, 9), font(SANS_B, 22)
    f_mono, f_hist = font(MONO_B, 12), font(MONO_R, 11)
    f_gen = font(SANS_B, 12)

    # ---- vertical layout (mirrors the grid/pack order in gui.py) ----
    y = CHROME + 112                       # header canvas height
    card_top = y
    r_profile, r_type, r_len = y + 16, y + 50, y + 84
    y_opts = y + 114
    y = y + 114 + (32 if has_options else 0)
    y_sep = y + 10
    y_res = y_sep + 11
    res_h = 58
    y_meter = y_res + res_h + 10
    card_bot = y_meter + 8 + 18 + 4
    y_btn = card_bot + 14
    btn_h = 40
    y_hist = y_btn + btn_h + 14
    y_list = y_hist + 20
    list_h = 3 * 19 + 4
    y_status = y_list + list_h + 10
    H = y_status + 14 + 14

    c = Canvas(W, H, t.bg)

    # ---- title bar chrome (generic, neutral) ----
    c.rect(0, 0, W, CHROME, fill="#e8e8ea")
    c.rect(0, CHROME - 1, W, CHROME, fill="#cfcfd3")
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = 16 + i * 20
        c.d.ellipse([(cx - 6) * K, (CHROME / 2 - 6) * K, (cx + 6) * K, (CHROME / 2 + 6) * K], fill=col)
    c.text(W / 2, CHROME / 2, "KeyForge", font(SANS_B, 9.5), "#4a4a4f", anchor="mm")

    # ---- header ----
    draw_lock(c, 62, CHROME + 54, 76, t.accent, t.bg)
    c.text(116, CHROME + 42, profile.name, f_title, t.text, anchor="lm")
    c.text(117, CHROME + 74, profile.tagline, f_ui, t.muted, anchor="lm")

    # ---- card ----
    c.rect(24, card_top, W - 24, card_bot, fill=t.surface, outline=t.border)
    lx, fx, fr = 42, 42 + 132 + 14, W - 42

    def combo(y0, label, text):
        c.text(lx, y0 + 13, label, f_ui, t.text, anchor="lm")
        c.rect(fx, y0, fr, y0 + 26, fill=t.field, outline=t.border)
        c.text(fx + 8, y0 + 13, text, f_ui, t.text, anchor="lm")
        ax, ay = fr - 14, y0 + 13
        c.d.polygon([(ax - 4) * K, (ay - 2) * K, (ax + 4) * K, (ay - 2) * K, ax * K, (ay + 3) * K], fill=t.text)

    combo(r_profile, "Profile", profile.name)
    combo(r_type, "Type", MODE_LABELS[mode])

    c.text(lx, r_len + 13, f"Length: {policy.length} {LENGTH_UNITS[mode]}", f_ui, t.text, anchor="lm")
    lo, hi = LENGTH_RANGES[mode]
    c.rect(fx, r_len + 5, fr, r_len + 19, fill=t.field)
    frac = (policy.length - lo) / (hi - lo)
    sx = fx + frac * (fr - fx - 30)
    c.rect(sx, r_len + 5, sx + 30, r_len + 19, fill=t.accent)

    def check(x0, y0, label, on):
        c.rect(x0, y0 + 3, x0 + 14, y0 + 17, fill=t.field, outline=t.border)
        if on:
            c.d.line([(x0 + 3) * K, (y0 + 10) * K, (x0 + 6) * K, (y0 + 14) * K, (x0 + 11) * K, (y0 + 6) * K],
                     fill=t.text, width=round(1.8 * K))
        c.text(x0 + 20, y0 + 10, label, f_ui, t.text, anchor="lm")
        return x0 + 20 + c.width_of(label, f_ui) + 14

    if mode == "password":
        x0 = lx
        for label, on in (("a-z", policy.lower), ("A-Z", policy.upper), ("0-9", policy.digits),
                          ("!@#", policy.symbols), ("No look-alikes", policy.avoid_ambiguous)):
            x0 = check(x0, y_opts, label, on)
    elif mode == "passphrase":
        x0 = check(lx, y_opts, "Capitalize words", policy.capitalize)
        check(x0 + 4, y_opts, "Add number", policy.add_number)

    c.rect(lx, y_sep, fr, y_sep + 1, fill=t.border)

    # result box (+ copy button)
    box_r = fr - 8 - 76  # entry width = card inner width - copy button
    c.rect(lx, y_res, box_r, y_res + res_h, fill=t.field, outline=t.border)
    shown = soft_wrap(result.value, policy.separator if mode == "passphrase" else "")
    lines = [ln for part in shown.split("\n") for ln in wrap_chars(c, part, f_mono, 330)]
    lh = 19
    top = y_res + res_h / 2 - len(lines) * lh / 2
    for i, line in enumerate(lines):
        c.text(lx + 10, top + i * lh + lh / 2, line, f_mono, t.text, anchor="lm")
    c.rect(box_r + 8, y_res, fr, y_res + res_h, fill=t.accent)
    c.text((box_r + 8 + fr) / 2, y_res + res_h / 2, "Copy", f_ui_b, t.on_accent, anchor="mm")

    # strength meter
    filled = result.rating + 1
    for i in range(5):
        x0 = lx + i * 51
        c.rect(x0, y_meter, x0 + 46, y_meter + 8, fill=RATING_COLORS[filled - 1] if i < filled else t.border)
    c.text(lx + 262, y_meter + 4, f"{result.label}  -  ~{round(result.entropy_bits)} bits", f_small, t.muted, anchor="lm")
    c.text(fr, y_meter + 4, "Hide", f_small, t.muted, anchor="rm")
    hx = fr - c.width_of("Hide", f_small) - 20
    c.rect(hx, y_meter - 3, hx + 11, y_meter + 8, fill=t.field, outline=t.border)

    # generate button
    c.rect(24, y_btn, W - 24, y_btn + btn_h, fill=t.accent)
    c.text(W / 2, y_btn + btn_h / 2, action_for(profile, mode), f_gen, t.on_accent, anchor="mm")

    # history
    c.text(24, y_hist + 8, "This session (memory only)", f_small, t.muted, anchor="lm")
    c.text(W - 24, y_hist + 8, "Clear", f_small, t.muted, anchor="rm")
    c.rect(24, y_list, W - 24, y_list + list_h, fill=t.surface, outline=t.border)
    for i, item in enumerate(history[:3]):
        c.text(30, y_list + 3 + i * 19 + 9, item, f_hist, t.text, anchor="lm")

    c.text(24, y_status + 7, status, f_small, t.muted, anchor="lm")

    # ---- window frame + soft shadow ----
    win = c.final()
    pad = 34
    shadow = Image.new("RGBA", (win.width + pad * 2, win.height + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([pad, pad + 10, pad + win.width, pad + win.height + 10], fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    ImageDraw.Draw(win).rectangle([0, 0, win.width - 1, win.height - 1], outline="#b9b9be", width=2)
    shadow.paste(win, (pad, pad))
    return shadow


def demo_state(profile: Profile, policy=None):
    policy = policy or profile.policy
    history = [generate(policy).value for _ in range(3)]
    return policy, history


def main():
    out = ROOT / "screenshots"
    out.mkdir(exist_ok=True)
    profiles = load_profiles()
    pages = {}

    for i, p in enumerate(profiles, 1):
        policy, hist = demo_state(p)
        img = render_window(p, policy, hist, "Generated - press Copy to use it")
        path = out / f"{i:02d}-{p.id}.png"
        img.save(path)
        pages[p.id] = img
        print("wrote", path.relative_to(ROOT))

    # overview montage (4 x 2)
    thumbs = [im.resize((im.width // 2, im.height // 2), Image.LANCZOS) for im in pages.values()]
    tw, th = max(t.width for t in thumbs), max(t.height for t in thumbs)
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "#e9ebee")
    for idx, im in enumerate(thumbs):
        sheet.paste(im, ((idx % cols) * tw, (idx // cols) * th), im)
    sheet.save(out / "00-overview.png")
    print("wrote screenshots/00-overview.png")

    # one profile, four credential types
    base = next(p for p in profiles if p.id == "general")
    variants = [
        replace(base.policy, mode="password", length=20),
        replace(base.policy, mode="passphrase", length=6),
        replace(base.policy, mode="pin", length=6),
        replace(base.policy, mode="token", length=48),
    ]
    imgs = []
    for pol in variants:
        pol, hist = demo_state(base, pol)
        imgs.append(render_window(base, pol, hist, "Preview updated"))
    thumbs = [im.resize((im.width // 2, im.height // 2), Image.LANCZOS) for im in imgs]
    tw, th = max(t.width for t in thumbs), max(t.height for t in thumbs)
    sheet = Image.new("RGB", (len(thumbs) * tw, th), "#e9ebee")
    for idx, im in enumerate(thumbs):
        sheet.paste(im, (idx * tw, 0), im)
    sheet.save(out / "09-credential-types.png")
    print("wrote screenshots/09-credential-types.png")


if __name__ == "__main__":
    main()
