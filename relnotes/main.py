import sys
import argparse
import subprocess
import logging

log = logging.getLogger("relnotes")

from relnotes.runner import Runner


def parse_args(args):
    parser = argparse.ArgumentParser(description="Sane reno reporter")
    parser.add_argument(
        "--version", help="Version to report on (default: current branch)"
    )
    parser.add_argument(
        "--previous", help="Previous version, (default: ordinal previous tag)"
    )
    parser.add_argument(
        "--version-regex", help="Regex to use when parsing (default: from relnotes.yaml)"
    )
    parser.add_argument(
        "--rel-notes-dir", help="Release notes folder", default="./releasenotes"
    )
    parser.add_argument("--debug", help="Debug mode", action="store_true")
    parser.add_argument("--yaml", help="Dump yaml", action="store_true")
    parser.add_argument(
        "--lint", help="Lint notes for valid markdown", action="store_true"
    )
    parser.add_argument(
        "--blame", help="Show more commit info in the report", action="store_true"
    )
    return parser.parse_args(args)


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    args = parse_args(sys.argv[1:])
    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("args: %s", args)
    r = Runner(args)
    try:
        r.run()
    except (subprocess.CalledProcessError, AssertionError) as e:
        print("ERROR:", str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
