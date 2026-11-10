import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "profile_helper", Path(__file__).parents[1] / "scripts/prepare_browser_profile.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "user/Local State"
        self.source.parent.mkdir()
        self.profile = self.root / "automation"

    def write_source(self, prefs):
        self.source.write_text(json.dumps({"password_manager": prefs, "secret": "do-not-copy"}),
                               encoding="utf-8")

    def test_copies_only_cache_and_preserves_target(self):
        self.write_source({"os_password_last_changed": "13359901926290193",
                           "os_password_blank": False, "secret": "do-not-copy"})
        self.profile.mkdir()
        target = self.profile / "Local State"
        target.write_text('{"other": 42, "password_manager": {"keep": true}}')
        before = self.source.read_bytes()
        helper.prepare(self.source, self.profile)
        result = json.loads(target.read_text())
        self.assertEqual(result, {"other": 42, "password_manager": {
            "keep": True, "os_password_last_changed": "13359901926290193",
            "os_password_blank": False}})
        self.assertEqual(self.source.read_bytes(), before)

    def test_invalid_cache_does_not_create_profile(self):
        for prefs in [{}, {"os_password_last_changed": "bad", "os_password_blank": False},
                      {"os_password_last_changed": 0, "os_password_blank": False},
                      {"os_password_last_changed": "123", "os_password_blank": "false"}]:
            with self.subTest(prefs=prefs):
                self.write_source(prefs)
                with self.assertRaises(ValueError):
                    helper.prepare(self.source, self.profile)
                self.assertFalse(self.profile.exists())

    def test_rejects_real_user_profile_and_children(self):
        for target in [self.source.parent, self.source.parent / "Default"]:
            with self.assertRaises(ValueError):
                helper.prepare(self.source, target)

    def test_missing_source_does_not_create_profile(self):
        with self.assertRaises(OSError):
            helper.prepare(self.source, self.profile)
        self.assertFalse(self.profile.exists())


if __name__ == "__main__":
    unittest.main()
