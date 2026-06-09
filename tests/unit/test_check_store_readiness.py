"""Tests for scripts/check_store_readiness.py (gate G12-MOBILE-001).

Detects which mobile platform(s) the project targets and requires their store
metadata. Checks only present platforms; non-mobile dirs exit 0.

Run with: python -m pytest tests/unit/test_check_store_readiness.py -q

Ref: T-132 / REQ-PROFILE-MOBILE-001
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _import(name: str):
    """Import a script module by absolute path (handles hyphenated filenames)."""
    path = SCRIPTS / f"{name}.py"
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


store_mod = _import("check_store_readiness")


# A complete Android build.gradle (all three required fields present).
_ANDROID_GRADLE_COMPLETE = """
android {
    defaultConfig {
        applicationId "com.example.app"
        versionCode 7
        versionName "1.2.3"
    }
}
""".strip()

# Missing versionName.
_ANDROID_GRADLE_MISSING = """
android {
    defaultConfig {
        applicationId "com.example.app"
        versionCode 7
    }
}
""".strip()

_INFO_PLIST_COMPLETE = """
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.example.app</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
</dict>
</plist>
""".strip()

_INFO_PLIST_MISSING = """
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.example.app</string>
</dict>
</plist>
""".strip()

_PUBSPEC_COMPLETE = "name: myapp\nversion: 1.0.0+1\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n"
_PUBSPEC_MISSING = "name: myapp\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n"


# ---------- Android ----------

class TestAndroid:
    def test_complete_android_exits_zero(self, tmp_path):
        app = tmp_path / "android" / "app"
        app.mkdir(parents=True)
        (app / "build.gradle").write_text(_ANDROID_GRADLE_COMPLETE)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_android_missing_field_exits_one(self, tmp_path):
        app = tmp_path / "android" / "app"
        app.mkdir(parents=True)
        (app / "build.gradle").write_text(_ANDROID_GRADLE_MISSING)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 1


# ---------- iOS ----------

class TestIOS:
    def test_complete_ios_exits_zero(self, tmp_path):
        ios = tmp_path / "ios" / "Runner"
        ios.mkdir(parents=True)
        (ios / "Info.plist").write_text(_INFO_PLIST_COMPLETE)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_ios_missing_field_exits_one(self, tmp_path):
        ios = tmp_path / "ios" / "Runner"
        ios.mkdir(parents=True)
        (ios / "Info.plist").write_text(_INFO_PLIST_MISSING)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 1


# ---------- Flutter ----------

class TestFlutter:
    def test_complete_flutter_exits_zero(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text(_PUBSPEC_COMPLETE)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_flutter_missing_version_exits_one(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text(_PUBSPEC_MISSING)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 1


# ---------- non-mobile ----------

class TestNonMobile:
    def test_non_mobile_dir_exits_zero(self, tmp_path):
        # No mobile platform present at all → nothing to gate.
        (tmp_path / "main.py").write_text("print('hi')\n")
        (tmp_path / "README.md").write_text("# hi\n")
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_empty_dir_exits_zero(self, tmp_path):
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0


# ---------- robustness ----------

class TestRobustness:
    def test_unreadable_gradle_does_not_crash(self, tmp_path):
        # A build.gradle that exists but lacks required fields → treated as missing.
        app = tmp_path / "android"
        app.mkdir(parents=True)
        (app / "build.gradle").write_text("// empty gradle, no config\n")
        assert store_mod.main(["--cwd", str(tmp_path)]) == 1

    def test_multiple_platforms_all_complete_exits_zero(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text(_PUBSPEC_COMPLETE)
        android = tmp_path / "android" / "app"
        android.mkdir(parents=True)
        (android / "build.gradle").write_text(_ANDROID_GRADLE_COMPLETE)
        ios = tmp_path / "ios" / "Runner"
        ios.mkdir(parents=True)
        (ios / "Info.plist").write_text(_INFO_PLIST_COMPLETE)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 0

    def test_one_complete_one_missing_exits_one(self, tmp_path):
        # Flutter complete but Android present-and-incomplete → fail.
        (tmp_path / "pubspec.yaml").write_text(_PUBSPEC_COMPLETE)
        android = tmp_path / "android" / "app"
        android.mkdir(parents=True)
        (android / "build.gradle").write_text(_ANDROID_GRADLE_MISSING)
        assert store_mod.main(["--cwd", str(tmp_path)]) == 1
