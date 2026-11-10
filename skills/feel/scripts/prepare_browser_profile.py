"""Prepare an automation-only profile without attempting Windows authentication."""

import argparse
import json
import os
from pathlib import Path
import tempfile


def prepare(source, profile):
    source = source.resolve()
    profile = profile.resolve()
    if profile == source.parent or source.parent in profile.parents:
        raise ValueError("Use a dedicated automation profile outside the real browser profile")
    state = json.loads(source.read_text(encoding="utf-8"))
    cached = state.get("password_manager", {})
    timestamp = cached.get("os_password_last_changed")
    blank = cached.get("os_password_blank")
    if (not isinstance(timestamp, (str, int)) or isinstance(timestamp, bool)
            or not str(timestamp).isdigit() or int(timestamp) <= 0
            or type(blank) is not bool):
        raise ValueError("No valid OS password-check cache; stop Windows browser measurements")
    target = profile / "Local State"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    prefs = existing.setdefault("password_manager", {})
    if not isinstance(prefs, dict):
        raise ValueError("Invalid automation profile password_manager state")
    # Copy only the two cache values, never credentials or the full user profile.
    prefs.update(os_password_last_changed=timestamp, os_password_blank=blank)
    profile.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=profile,
                                         prefix=".feel-state-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(existing, handle)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--source-state", type=Path, help="Override Local State for offline validation")
    parser.add_argument("--profile", type=Path, help="Dedicated profile; browser must be closed")
    args = parser.parse_args()
    try:
        if args.source_state:
            source = args.source_state
        else:
            vendor = "Google/Chrome" if args.browser == "chrome" else "Microsoft/Edge"
            source = Path(os.environ["LOCALAPPDATA"]) / vendor / "User Data/Local State"
        profile = args.profile or Path(tempfile.gettempdir()) / ("feel-" + args.browser + "-profile")
        print(prepare(source, profile))
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        parser.exit(1, "Profile preparation failed; do not launch the browser: " + str(error) + "\n")


if __name__ == "__main__":
    main()
