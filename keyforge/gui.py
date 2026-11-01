"""Tkinter front-end. Secrets are never written to disk; they live in memory only."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from . import APP_NAME
from .branding import lock_shapes, shade
from .core import (
    LENGTH_RANGES,
    LENGTH_UNITS,
    MODE_LABELS,
    MODES,
    GenerationResult,
    Policy,
    generate,
    soft_wrap,
)
from .profiles import Profile, Theme, action_for

WIDTH = 520
HEADER_H = 112
CLIPBOARD_CLEAR_MS = 30_000
HISTORY_LIMIT = 6
RATING_COLORS = ("#d64545", "#e08a3c", "#d6b73c", "#7fb944", "#2f9e5b")

FONT_UI = ("Helvetica", 10)
FONT_SMALL = ("Helvetica", 9)
FONT_BOLD = ("Helvetica", 10, "bold")
FONT_TITLE = ("Helvetica", 22, "bold")
FONT_MONO = ("Courier", 12, "bold")
LABEL_COL_PX = 132  # fixed so the controls don't shift when 'characters'/'words' changes
WRAP_PX = 330  # result box wraps long values (up to ~100 chars fit in 3 lines)

_LABEL_TO_MODE = {label: mode for mode, label in MODE_LABELS.items()}


class KeyForgeApp:
    def __init__(self, root: tk.Tk, profiles: list[Profile], initial_id: Optional[str] = None):
        self.root = root
        self.profiles = {p.id: p for p in profiles}
        self.profile: Profile = profiles[0]
        self._last: Optional[GenerationResult] = None
        self._history: list[str] = []
        self._clip_job = None
        self._clip_value = ""
        self._wrap_sep = ""

        root.title(APP_NAME)
        root.resizable(False, False)

        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self._init_vars()
        self._build()
        self.select_profile(initial_id if initial_id in self.profiles else profiles[0].id)

        root.bind("<Control-g>", lambda _e: self.generate())
        root.bind("<Return>", lambda _e: self.generate())

    # ------------------------------------------------------------------ state
    def _init_vars(self) -> None:
        self.v_profile = tk.StringVar()
        self.v_mode = tk.StringVar()
        self.v_length = tk.IntVar(value=16)
        self.v_length_text = tk.StringVar()
        self.v_lower = tk.BooleanVar(value=True)
        self.v_upper = tk.BooleanVar(value=True)
        self.v_digits = tk.BooleanVar(value=True)
        self.v_symbols = tk.BooleanVar(value=True)
        self.v_ambiguous = tk.BooleanVar(value=False)
        self.v_capitalize = tk.BooleanVar(value=True)
        self.v_number = tk.BooleanVar(value=True)
        self.v_hide = tk.BooleanVar(value=False)
        self.v_result = tk.StringVar()   # the real secret (copied)
        self.v_display = tk.StringVar()  # what is shown (masked when Hide is on)
        self.v_strength = tk.StringVar()
        self.v_status = tk.StringVar(value="Ready")
        self.v_action = tk.StringVar(value="Generate")

    @property
    def mode(self) -> str:
        return _LABEL_TO_MODE.get(self.v_mode.get(), "password")

    def current_policy(self) -> Policy:
        base = self.profile.policy
        return Policy(
            mode=self.mode,
            length=int(self.v_length.get()),
            lower=self.v_lower.get(),
            upper=self.v_upper.get(),
            digits=self.v_digits.get(),
            symbols=self.v_symbols.get(),
            symbol_set=base.symbol_set,
            avoid_ambiguous=self.v_ambiguous.get(),
            separator=base.separator,
            capitalize=self.v_capitalize.get(),
            add_number=self.v_number.get(),
        )

    # ----------------------------------------------------------------- layout
    def _build(self) -> None:
        self.header = tk.Canvas(self.root, width=WIDTH, height=HEADER_H, highlightthickness=0, bd=0)
        self.header.pack(fill="x")

        self.body = tk.Frame(self.root, padx=24)
        self.body.pack(fill="both", expand=True)

        self.card = tk.Frame(self.body, padx=18, pady=16, highlightthickness=1)
        self.card.pack(fill="x")
        self.card.columnconfigure(0, minsize=LABEL_COL_PX)
        self.card.columnconfigure(1, weight=1)

        self.lbl_profile = tk.Label(self.card, text="Profile", font=FONT_UI, anchor="w")
        self.lbl_profile.grid(row=0, column=0, sticky="w", pady=4)
        self.cmb_profile = ttk.Combobox(
            self.card, textvariable=self.v_profile, state="readonly",
            values=[p.name for p in self.profiles.values()], font=FONT_UI,
        )
        self.cmb_profile.grid(row=0, column=1, sticky="ew", padx=(14, 0), pady=4)
        self.cmb_profile.bind("<<ComboboxSelected>>", self._on_profile_chosen)

        self.lbl_type = tk.Label(self.card, text="Type", font=FONT_UI, anchor="w")
        self.lbl_type.grid(row=1, column=0, sticky="w", pady=4)
        self.cmb_mode = ttk.Combobox(
            self.card, textvariable=self.v_mode, state="readonly",
            values=[MODE_LABELS[m] for m in MODES], font=FONT_UI,
        )
        self.cmb_mode.grid(row=1, column=1, sticky="ew", padx=(14, 0), pady=4)
        self.cmb_mode.bind("<<ComboboxSelected>>", self._on_mode_chosen)

        self.lbl_length = tk.Label(self.card, textvariable=self.v_length_text, font=FONT_UI, anchor="w")
        self.lbl_length.grid(row=2, column=0, sticky="w", pady=4)
        self.scale = tk.Scale(
            self.card, orient="horizontal", from_=8, to=64, showvalue=False, variable=self.v_length,
            command=self._on_length, bd=0, highlightthickness=0, sliderrelief="flat", width=14,
        )
        self.scale.grid(row=2, column=1, sticky="ew", padx=(14, 0), pady=4)

        # Option rows: one for character modes, one for passphrases. Only one is shown.
        self.opts_chars = tk.Frame(self.card)
        self.opts_phrase = tk.Frame(self.card)
        self.char_checks = [
            self._check(self.opts_chars, "a-z", self.v_lower),
            self._check(self.opts_chars, "A-Z", self.v_upper),
            self._check(self.opts_chars, "0-9", self.v_digits),
            self._check(self.opts_chars, "!@#", self.v_symbols),
            self._check(self.opts_chars, "No look-alikes", self.v_ambiguous),
        ]
        self.phrase_checks = [
            self._check(self.opts_phrase, "Capitalize words", self.v_capitalize),
            self._check(self.opts_phrase, "Add number", self.v_number),
        ]
        for i, cb in enumerate(self.char_checks):
            cb.grid(row=0, column=i, padx=(0, 10), sticky="w")
        for i, cb in enumerate(self.phrase_checks):
            cb.grid(row=0, column=i, padx=(0, 14), sticky="w")
        self.opts_chars.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))
        self.opts_phrase.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))

        self.sep = tk.Frame(self.card, height=1)
        self.sep.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)

        result_row = tk.Frame(self.card)
        result_row.grid(row=5, column=0, columnspan=2, sticky="ew")
        result_row.columnconfigure(0, weight=1)
        self.result_row = result_row
        self.entry = tk.Label(
            result_row, textvariable=self.v_display, font=FONT_MONO, height=3, anchor="w",
            justify="left", wraplength=WRAP_PX, padx=10, highlightthickness=1,
        )
        self.entry.grid(row=0, column=0, sticky="ew")
        self.btn_copy = tk.Button(
            result_row, text="Copy", font=FONT_BOLD, relief="flat", bd=0, padx=16,
            cursor="hand2", command=self.copy,
        )
        self.btn_copy.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        meter_row = tk.Frame(self.card)
        meter_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.meter_row = meter_row
        self.meter = tk.Canvas(meter_row, width=250, height=8, highlightthickness=0, bd=0)
        self.meter.pack(side="left")
        self.lbl_strength = tk.Label(meter_row, textvariable=self.v_strength, font=FONT_SMALL)
        self.lbl_strength.pack(side="left", padx=(12, 0))
        self.chk_hide = tk.Checkbutton(
            meter_row, text="Hide", variable=self.v_hide, font=FONT_SMALL, command=self._apply_mask,
        )
        self.chk_hide.pack(side="right")

        self.btn_generate = tk.Button(
            self.body, textvariable=self.v_action, font=("Helvetica", 12, "bold"), relief="flat",
            bd=0, pady=11, cursor="hand2", command=self.generate,
        )
        self.btn_generate.pack(fill="x", pady=(14, 0))

        hist_head = tk.Frame(self.body)
        hist_head.pack(fill="x", pady=(14, 2))
        self.hist_head = hist_head
        self.lbl_hist = tk.Label(hist_head, text="This session (memory only)", font=FONT_SMALL)
        self.lbl_hist.pack(side="left")
        self.btn_clear = tk.Button(
            hist_head, text="Clear", font=FONT_SMALL, relief="flat", bd=0, cursor="hand2",
            command=self.clear_history,
        )
        self.btn_clear.pack(side="right")
        self.listbox = tk.Listbox(
            self.body, height=HISTORY_LIMIT // 2, font=("Courier", 11), relief="flat", bd=0,
            highlightthickness=1, activestyle="none", exportselection=False,
        )
        self.listbox.pack(fill="x")
        self.listbox.bind("<Double-Button-1>", self._copy_from_history)

        self.lbl_status = tk.Label(self.body, textvariable=self.v_status, font=FONT_SMALL, anchor="w")
        self.lbl_status.pack(fill="x", pady=(10, 14))

    def _check(self, parent: tk.Misc, text: str, var: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent, text=text, variable=var, font=FONT_UI, command=self._auto,
            bd=0, highlightthickness=0, anchor="w",
        )

    # ------------------------------------------------------------------ theme
    def apply_theme(self, t: Theme) -> None:
        self.root.configure(bg=t.bg)
        self.header.configure(bg=t.bg)
        for w in (self.body, self.hist_head):
            w.configure(bg=t.bg)
        self.card.configure(bg=t.surface, highlightbackground=t.border, highlightcolor=t.border)
        for w in (self.opts_chars, self.opts_phrase, self.result_row, self.meter_row):
            w.configure(bg=t.surface)
        self.sep.configure(bg=t.border)

        for w in (self.lbl_profile, self.lbl_type, self.lbl_length):
            w.configure(bg=t.surface, fg=t.text)
        for cb in self.char_checks + self.phrase_checks:
            cb.configure(bg=t.surface, fg=t.text, activebackground=t.surface,
                         activeforeground=t.text, selectcolor=t.field)
        self.chk_hide.configure(bg=t.surface, fg=t.muted, activebackground=t.surface,
                                activeforeground=t.muted, selectcolor=t.field)
        self.lbl_strength.configure(bg=t.surface, fg=t.muted)
        self.meter.configure(bg=t.surface)
        self.scale.configure(bg=t.accent, troughcolor=t.field, activebackground=shade(t.accent, 0.85),
                             highlightbackground=t.surface)

        self.entry.configure(bg=t.field, fg=t.text, highlightbackground=t.border)
        for btn in (self.btn_generate,):
            btn.configure(bg=t.accent, fg=t.on_accent, activebackground=shade(t.accent, 0.85),
                          activeforeground=t.on_accent, highlightbackground=t.accent)
        self.btn_copy.configure(bg=t.accent, fg=t.on_accent, activebackground=shade(t.accent, 0.85),
                                activeforeground=t.on_accent, highlightbackground=t.accent)
        self.btn_clear.configure(bg=t.bg, fg=t.muted, activebackground=t.bg, activeforeground=t.text,
                                 highlightbackground=t.bg)
        self.lbl_hist.configure(bg=t.bg, fg=t.muted)
        self.listbox.configure(bg=t.surface, fg=t.text, selectbackground=t.accent,
                               selectforeground=t.on_accent, highlightbackground=t.border,
                               highlightcolor=t.border)
        self.lbl_status.configure(bg=t.bg, fg=t.muted)

        self.style.configure("TCombobox", fieldbackground=t.field, background=t.field,
                             foreground=t.text, arrowcolor=t.text, bordercolor=t.border,
                             lightcolor=t.border, darkcolor=t.border, selectbackground=t.field,
                             selectforeground=t.text)
        self.style.map("TCombobox", fieldbackground=[("readonly", t.field)],
                       foreground=[("readonly", t.text)], background=[("readonly", t.field)])
        self.root.option_add("*TCombobox*Listbox.background", t.surface)
        self.root.option_add("*TCombobox*Listbox.foreground", t.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", t.accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", t.on_accent)
        self._draw_header()
        self._draw_meter()

    def _draw_header(self) -> None:
        t, c = self.profile.theme, self.header
        c.delete("all")
        for shape in lock_shapes(62, 54, 76):
            kind, role = shape[0], shape[-1]
            color = t.accent if role == "accent" else t.bg
            if kind == "arc_top":
                c.create_arc(*shape[1], start=0, extent=180, style="arc", outline=color, width=shape[2])
            elif kind == "line":
                c.create_line(*shape[1], width=shape[2], fill=color)
            elif kind == "rrect":
                self._round_rect(c, shape[1], shape[2], color)
            elif kind == "oval":
                c.create_oval(*shape[1], fill=color, outline="")
            elif kind == "rect":
                c.create_rectangle(*shape[1], fill=color, outline="")
        c.create_text(116, 42, text=self.profile.name, font=FONT_TITLE, fill=t.text, anchor="w")
        c.create_text(117, 74, text=self.profile.tagline, font=FONT_UI, fill=t.muted, anchor="w")

    @staticmethod
    def _round_rect(canvas: tk.Canvas, bbox, r: float, color: str) -> None:
        x1, y1, x2, y2 = bbox
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        canvas.create_polygon(pts, smooth=True, fill=color, outline="")

    def _draw_meter(self) -> None:
        t, c = self.profile.theme, self.meter
        c.delete("all")
        filled = (self._last.rating + 1) if self._last else 0
        seg_w, gap = 46, 5
        for i in range(5):
            x = i * (seg_w + gap)
            color = RATING_COLORS[filled - 1] if i < filled else t.border
            c.create_rectangle(x, 0, x + seg_w, 8, fill=color, outline="")

    # ---------------------------------------------------------------- actions
    def select_profile(self, profile_id: str) -> None:
        self.profile = self.profiles[profile_id]
        p = self.profile.policy
        self.v_profile.set(self.profile.name)
        self.v_mode.set(MODE_LABELS[p.mode])
        self.v_lower.set(p.lower)
        self.v_upper.set(p.upper)
        self.v_digits.set(p.digits)
        self.v_symbols.set(p.symbols)
        self.v_ambiguous.set(p.avoid_ambiguous)
        self.v_capitalize.set(p.capitalize)
        self.v_number.set(p.add_number)
        self.v_action.set(action_for(self.profile, self.mode))
        self._configure_for_mode(p.length)
        self.apply_theme(self.profile.theme)
        self.generate(remember=False)

    def _configure_for_mode(self, length: Optional[int] = None) -> None:
        lo, hi = LENGTH_RANGES[self.mode]
        self.scale.configure(from_=lo, to=hi)
        target = self.v_length.get() if length is None else length
        self.v_length.set(max(lo, min(hi, target)))
        self._update_length_text()
        if self.mode == "passphrase":
            self.opts_chars.grid_remove()
            self.opts_phrase.grid()
        elif self.mode == "password":
            self.opts_phrase.grid_remove()
            self.opts_chars.grid()
        else:
            self.opts_phrase.grid_remove()
            self.opts_chars.grid_remove()

    def _update_length_text(self) -> None:
        self.v_length_text.set(f"Length: {self.v_length.get()} {LENGTH_UNITS[self.mode]}")

    def _on_profile_chosen(self, _event=None) -> None:
        for p in self.profiles.values():
            if p.name == self.v_profile.get():
                self.select_profile(p.id)
                return

    def _on_mode_chosen(self, _event=None) -> None:
        self.v_action.set(action_for(self.profile, self.mode))
        self._configure_for_mode(self.profile.policy.length if self.mode == self.profile.policy.mode else None)
        self._auto()

    def _on_length(self, _value=None) -> None:
        self._update_length_text()
        self._auto()

    def _auto(self) -> None:
        """Refresh after an option change without adding to the session history."""
        self.generate(remember=False)

    def generate(self, remember: bool = True) -> None:
        policy = self.current_policy()
        try:
            result = generate(policy)
        except ValueError as exc:
            self.v_status.set(f"Cannot generate: {exc}")
            return
        self._last = result
        self._wrap_sep = policy.separator if policy.mode == "passphrase" else ""
        self.v_result.set(result.value)
        self.v_strength.set(f"{result.label}  -  ~{round(result.entropy_bits)} bits")
        if remember:
            self._remember(result.value)
        self._apply_mask()
        self._draw_meter()
        self.v_status.set("Generated - press Copy to use it" if remember else "Preview updated")

    def _remember(self, value: str) -> None:
        self._history.insert(0, value)
        del self._history[HISTORY_LIMIT:]

    def _apply_mask(self) -> None:
        value = self.v_result.get()
        shown = "\u2022" * len(value) if self.v_hide.get() else soft_wrap(value, self._wrap_sep)
        self.v_display.set(shown)
        self.listbox.delete(0, "end")
        for item in self._history:
            self.listbox.insert("end", "\u2022" * len(item) if self.v_hide.get() else item)

    def clear_history(self) -> None:
        self._history.clear()
        self.listbox.delete(0, "end")
        self.v_status.set("History cleared")

    def _copy_from_history(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if selection:
            self._to_clipboard(self._history[selection[0]])

    def copy(self) -> None:
        if self.v_result.get():
            self._to_clipboard(self.v_result.get())

    def _to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self._clip_value = value
        if self._clip_job is not None:
            self.root.after_cancel(self._clip_job)
        self._clip_job = self.root.after(CLIPBOARD_CLEAR_MS, self._clear_clipboard)
        self.v_status.set(f"Copied - clipboard clears in {CLIPBOARD_CLEAR_MS // 1000}s")

    def _clear_clipboard(self) -> None:
        self._clip_job = None
        try:
            if self.root.clipboard_get() == self._clip_value:
                self.root.clipboard_clear()
                self.v_status.set("Clipboard cleared")
        except tk.TclError:
            pass  # clipboard empty or unavailable
        self._clip_value = ""


def run(profiles: list[Profile], initial_id: Optional[str] = None) -> None:
    root = tk.Tk()
    KeyForgeApp(root, profiles, initial_id)
    root.mainloop()
