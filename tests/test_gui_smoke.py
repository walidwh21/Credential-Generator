"""Exercise gui.py logic with a stubbed tkinter (real Tk may be unavailable, e.g. CI).

This checks wiring and control flow - NameErrors, bad attribute use, state handling.
It cannot verify pixel-level rendering, which needs a real display.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeVar:
    def __init__(self, value=None):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class StubModule(types.ModuleType):
    def __getattr__(self, name):          # any widget class -> MagicMock factory
        if name.startswith("__"):
            raise AttributeError(name)
        m = MagicMock(name=name)
        setattr(self, name, m)
        return m


def install_stub():
    tk = StubModule("tkinter")
    tk.StringVar = tk.IntVar = tk.BooleanVar = FakeVar
    tk.TclError = type("TclError", (Exception,), {})
    ttk = StubModule("tkinter.ttk")
    tk.ttk = ttk
    sys.modules["tkinter"], sys.modules["tkinter.ttk"] = tk, ttk
    return tk


class GuiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved = {k: sys.modules.get(k) for k in ("tkinter", "tkinter.ttk")}
        for k in [k for k in sys.modules if k.startswith("keyforge.gui")]:
            del sys.modules[k]
        install_stub()
        from keyforge import gui
        from keyforge.profiles import load_profiles
        cls.gui, cls.profiles = gui, load_profiles()

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("keyforge.gui", None)

    def make(self, pid="general"):
        return self.gui.KeyForgeApp(MagicMock(), self.profiles, pid)

    def test_every_profile_builds_and_generates(self):
        for p in self.profiles:
            app = self.make(p.id)
            self.assertTrue(app.v_result.get(), p.id)
            self.assertEqual(app.mode, p.policy.mode)
            self.assertEqual(app.v_action.get(), p.action_label)

    def test_mode_switch_clamps_length_and_toggles_option_rows(self):
        app = self.make("general")                 # password, 20
        app.v_mode.set("Passphrase"); app._on_mode_chosen()
        self.assertTrue(3 <= app.v_length.get() <= 10)
        self.assertEqual(app.v_action.get(), "Generate passphrase")
        app.opts_chars.grid_remove.assert_called()
        app.v_mode.set("PIN"); app._on_mode_chosen()
        self.assertEqual(len(app.v_result.get()), app.v_length.get())
        self.assertEqual(app.v_action.get(), "Generate PIN")
        app.v_mode.set("Password"); app._on_mode_chosen()
        self.assertEqual(app.v_action.get(), app.profile.action_label)

    def test_history_only_records_explicit_generates(self):
        app = self.make("tesla")
        self.assertEqual(app._history, [])
        app._auto()
        self.assertEqual(app._history, [])
        for _ in range(10):
            app.generate()
        self.assertEqual(len(app._history), self.gui.HISTORY_LIMIT)
        app.clear_history()
        self.assertEqual(app._history, [])

    def test_invalid_state_shows_error_not_crash(self):
        app = self.make("general")
        for v in (app.v_lower, app.v_upper, app.v_digits, app.v_symbols):
            v.set(False)
        before = app.v_result.get()
        app.generate()
        self.assertIn("Cannot generate", app.v_status.get())
        self.assertEqual(app.v_result.get(), before)

    def test_copy_schedules_clipboard_clear(self):
        app = self.make("general")
        app.copy()
        app.root.clipboard_append.assert_called_with(app.v_result.get())
        app.root.after.assert_called()
        app.root.clipboard_get.return_value = app._clip_value
        app._clear_clipboard()
        self.assertEqual(app._clip_value, "")

    def test_no_file_io_in_gui_module(self):
        src = Path(self.gui.__file__).read_text()
        self.assertNotIn("open(", src)


if __name__ == "__main__":
    unittest.main()
