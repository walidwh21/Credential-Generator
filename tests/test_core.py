import json
import string
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keyforge.core import AMBIGUOUS, Policy, generate, soft_wrap  # noqa: E402
from keyforge.profiles import load_profiles  # noqa: E402
from keyforge.words import WORDS  # noqa: E402
from keyforge import __main__ as cli  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_password_contains_every_enabled_class(self):
        for _ in range(300):
            v = generate(Policy(mode="password", length=8)).value
            self.assertEqual(len(v), 8)
            self.assertTrue(any(c.islower() for c in v))
            self.assertTrue(any(c.isupper() for c in v))
            self.assertTrue(any(c.isdigit() for c in v))
            self.assertTrue(any(c in Policy().symbol_set for c in v))

    def test_avoid_ambiguous(self):
        for _ in range(200):
            v = generate(Policy(mode="password", length=40, avoid_ambiguous=True)).value
            self.assertFalse(AMBIGUOUS & set(v))

    def test_digits_only_password(self):
        v = generate(Policy(mode="password", length=12, lower=False, upper=False, symbols=False)).value
        self.assertTrue(v.isdigit())

    def test_invalid_policies(self):
        bad = [
            Policy(mode="nope"),
            Policy(mode="password", length=4),
            Policy(mode="password", lower=False, upper=False, digits=False, symbols=False),
            Policy(mode="pin", length=3),
            Policy(mode="passphrase", separator="toolong"),
        ]
        for p in bad:
            with self.assertRaises(ValueError, msg=p):
                generate(p)

    def test_passphrase(self):
        r = generate(Policy(mode="passphrase", length=5, separator="."))
        parts = r.value.split(".")
        self.assertEqual(len(parts), 6)           # 5 words + number
        self.assertTrue(parts[-1].isdigit())
        for w in parts[:-1]:
            self.assertIn(w.lower(), WORDS)
            self.assertTrue(w[0].isupper())

    def test_pin_never_trivial(self):
        for _ in range(500):
            v = generate(Policy(mode="pin", length=4)).value
            self.assertTrue(v.isdigit() and len(v) == 4)
            self.assertNotIn(v, {"0000", "1111", "1234", "4321", "9999", "0123", "9876"})

    def test_token_alphabet(self):
        v = generate(Policy(mode="token", length=64)).value
        self.assertTrue(set(v) <= set(string.ascii_letters + string.digits + "-_"))

    def test_entropy_and_rating(self):
        self.assertGreater(generate(Policy(mode="password", length=24)).entropy_bits, 100)
        self.assertEqual(generate(Policy(mode="pin", length=4)).rating, 0)
        self.assertEqual(generate(Policy(mode="token", length=40)).label, "Excellent")

    def test_soft_wrap_breaks_between_words_and_preserves_content(self):
        v = "Canoe-Coral-Bread-Cello-Badge-Balmy-Bronze-42"
        wrapped = soft_wrap(v, "-", 32)
        self.assertEqual(wrapped.replace("\n", ""), v)
        self.assertTrue(all(len(line) <= 32 for line in wrapped.split("\n")))
        self.assertTrue(all(line.endswith("-") for line in wrapped.split("\n")[:-1]))
        self.assertEqual(soft_wrap("abc123", ""), "abc123")

    def test_uniqueness(self):
        self.assertEqual(len({generate(Policy(length=20)).value for _ in range(200)}), 200)


class ProfileTests(unittest.TestCase):
    def test_builtin_profiles_valid(self):
        profiles = load_profiles()
        ids = {p.id for p in profiles}
        self.assertTrue({"general", "tesla", "google", "microsoft", "amazon"} <= ids)
        for p in profiles:
            generate(p.policy)

    def test_user_file_overrides_and_extends(self):
        extra = {"profiles": [
            {"id": "tesla", "name": "Tesla (custom)", "policy": {"mode": "pin", "length": 4}},
            {"id": "mine", "name": "Mine", "theme": {"accent": "#123456"}},
        ]}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "p.json")
            f.write_text(json.dumps(extra))
            by_id = {p.id: p for p in load_profiles(f)}
        self.assertEqual(by_id["tesla"].policy.mode, "pin")
        self.assertEqual(by_id["mine"].theme.accent, "#123456")

    def test_rejects_bad_profiles(self):
        bad = [
            {"id": "Bad Id"},
            {"id": "x", "theme": {"accent": "red"}},
            {"id": "x", "policy": {"length": 2}},
            {"id": "x", "policy": {"bogus": 1}},
        ]
        for raw in bad:
            with tempfile.TemporaryDirectory() as d:
                f = Path(d, "p.json")
                f.write_text(json.dumps({"profiles": [raw]}))
                with self.assertRaises(ValueError, msg=raw):
                    load_profiles(f)


class CliTests(unittest.TestCase):
    def test_cli_paths(self):
        self.assertEqual(cli.main(["--cli", "--profile", "tesla", "--count", "2"]), 0)
        self.assertEqual(cli.main(["--list-profiles"]), 0)
        self.assertEqual(cli.main(["--cli", "--profile", "nope"]), 2)
        self.assertEqual(cli.main(["--cli", "--length", "2"]), 2)


if __name__ == "__main__":
    unittest.main()
