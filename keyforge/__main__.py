"""Entry point:  python -m keyforge [--cli] [--profile ID] [--mode M] [--length N] [--count N]"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from . import APP_NAME, __version__
from .core import MODES, generate
from .profiles import load_profiles


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="keyforge", description=f"{APP_NAME} - credential generator")
    p.add_argument("--profile", default="general", help="profile id (see --list-profiles)")
    p.add_argument("--profiles", type=Path, metavar="FILE", help="extra profiles JSON to merge in")
    p.add_argument("--list-profiles", action="store_true", help="list available profiles and exit")
    p.add_argument("--cli", action="store_true", help="print to the terminal instead of opening the GUI")
    p.add_argument("--mode", choices=MODES, help="override the profile's credential type")
    p.add_argument("--length", type=int, help="override length (characters, or words for passphrases)")
    p.add_argument("--count", type=int, default=1, help="how many to generate in --cli mode")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profiles = load_profiles(args.profiles)
    except (OSError, ValueError) as exc:
        print(f"error: could not load profiles: {exc}", file=sys.stderr)
        return 2

    if args.list_profiles:
        for prof in profiles:
            print(f"{prof.id:<10} {prof.name:<12} {prof.policy.mode:<10} {prof.tagline}")
        return 0

    by_id = {p.id: p for p in profiles}
    if args.profile not in by_id:
        print(f"error: unknown profile {args.profile!r}. Try --list-profiles.", file=sys.stderr)
        return 2
    prof = by_id[args.profile]

    if not args.cli:
        try:
            from .gui import run
        except ImportError:  # tkinter missing (common on minimal Linux installs)
            print("tkinter is not available - falling back to --cli mode.", file=sys.stderr)
            args.cli = True
        else:
            run(profiles, prof.id)
            return 0

    policy = prof.policy
    overrides = {}
    if args.mode:
        overrides["mode"] = args.mode
    if args.length:
        overrides["length"] = args.length
    try:
        policy = replace(policy, **overrides)
        for _ in range(max(1, args.count)):
            result = generate(policy)
            print(f"{result.value}    # {result.label}, ~{round(result.entropy_bits)} bits")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
