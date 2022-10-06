"""Release notes runner class"""
import os
import os.path
import re
import shutil
import subprocess
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime

import yaml.representer

yaml.add_representer(defaultdict, yaml.representer.Representer.represent_dict)


class Msg:
    """Collection of configurable user facing message ids."""

    NEED_NOTE = "need-note"
    NEED_TARGET = "need-target"


DEFAULT_CONFIG = {
    "encoding": "utf8",
    "earliest_version": "0.0.1",
    "notes_dir": "./releasenotes",
    "release_tag_re": r"^v?((?:[\d.ab]|rc)+)",
    "sections": [
        ["features", "New Features"],
        ["internal", "Internal Changes"],
    ],
    "messages": {
        Msg.NEED_NOTE: "Please create a release note for this branch.",
        Msg.NEED_TARGET: "No upstream configured or detected, use --target <target>.",
    },
    "prelude_section_name": "release_summary",
    "template": "# Release notes template.\n"
    "release_summary: >\n"
    "    Replace this text with content to appear at the\n"
    "    top of the section for this release.\n"
    "features:\n"
    "  - List new features here, or remove this section.\n",
}

log = logging.getLogger("rnotes")


CONFIG_PATH = "./rnotes.yaml"


def normalize(git_dir):
    """Normalize to forward slash, strip off ./ from the front."""
    return git_dir.replace("\\", "/").replace("./", "")


class Runner:  # pylint: disable=too-many-instance-attributes
    """Process rnotes command line args."""

    def __init__(self, args):
        self.args = args
        try:
            with open(CONFIG_PATH, encoding="utf8") as fh:
                self.cfg = yaml.safe_load(fh)
        except FileNotFoundError:
            self.cfg = DEFAULT_CONFIG.copy()

        self.prelude_name = self.cfg.get("prelude_section_name", "release_summary")
        self.earliest = self.cfg.get("earliest_version")
        self.version_regex = (
            args.version_regex
            or self.cfg.get("release_tag_re")
            or DEFAULT_CONFIG.get("release_tag_re")
        )
        self.tags = []
        self.logs = []
        self.notes = {}
        self.report = ""
        self.ver_start = self.args.previous
        self.ver_end = self.args.version or "HEAD"
        notes_dir = self.args.notes_dir or self.cfg.get(
            "notes_dir", DEFAULT_CONFIG.get("notes_dir")
        )
        self.notes_dir = normalize(notes_dir)

        log.debug("notes_dir: %s", self.notes_dir)
        if not os.path.exists(self.notes_dir):
            raise FileNotFoundError("expected folder: %s" % self.notes_dir)

        self.sections = dict(self.cfg.get("sections", {}))
        self.valid_sections = {self.prelude_name, *self.sections.keys()}

        self.__git = shutil.which("git")

    def git(self, *args):
        """Shell git with args."""
        log.debug("+ git %s", " ".join(args))
        cmd = [self.__git] + list(args)
        ret = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, encoding="utf8")
        return ret.stdout

    def get_tags(self):
        """Get release tags, reverse sorted."""
        self.tags = []

        for tag in self.git("log", self.ver_end, "--tags", "--pretty=%D").split("\n"):
            tag = tag.strip()
            if not tag:
                continue
            head = re.match(r"HEAD[^,]*, tag:", tag)
            tag = re.search(r"\btag: ([^\s,]+)", tag)
            if not tag:
                continue
            tag = tag[1]
            if re.match(self.version_regex, tag):
                self.tags.append(tag)
                if head:
                    self.ver_end = tag
            if tag == self.earliest:
                break

        self.tags = list(reversed(self.tags))

        log.debug("tags: %s", self.tags)

    def get_start_from_end(self):
        """If start not specified, assume previous release."""
        if not self.ver_start:
            if self.ver_end == "HEAD":
                self.ver_start = self.tags[-1] if self.tags else "HEAD"

            prev = None
            for t in self.tags:
                if self.ver_end == t:
                    self.ver_start = prev
                prev = t

        log.debug("prev: %s, cur: %s", self.ver_start, self.ver_end)

    def get_logs(self):
        """Get a list of logs with tag, hash and ct."""
        cur_tag = self.ver_end
        ct = 0
        cname = ""
        hsh = ""
        if self.ver_start == "TAIL" or not self.ver_start:
            vers = self.ver_end
        else:
            vers = self.ver_start + ".." + self.ver_end
        for ent in self.git(
            "log", vers, "--name-only", "--format=%D^%ct^%cn^%h", "--diff-filter=A"
        ).split("\n"):
            ent = ent.strip()
            info = ent.split("^")
            if len(info) > 1:
                tag, ct, cname, hsh = info
                tag = re.search(r"\btag: ([\S,]+)", tag)
                if tag:
                    cur_tag = tag[1]
            if ent.startswith(self.notes_dir):
                self.logs.append((cur_tag, ct, cname, hsh, ent))

    def load_note(self, tag, file, ct, cname, hsh, notes):
        """Load specified note into notes list."""
        try:
            log.debug("load note: %s, %s", tag, file)
            with open(file, encoding="utf8") as f:
                note = yaml.safe_load(f)
                for k, v in note.items():
                    assert k in self.valid_sections, "%s: %s is not a valid section" % (
                        file,
                        k,
                    )
                    if type(v) is str:
                        v = [v]
                    assert (
                        type(v) is list
                    ), "%s: '%s' : list of entries or single string" % (file, k)
                    for line in v:
                        assert (
                            type(line) is str
                        ), "%s: '%s' : must be a simple string" % (file, line)
                        line = {
                            "time": int(ct),
                            "name": cname,
                            "hash": hsh,
                            "note": line,
                        }
                        notes[tag][k].append(line)
        except FileNotFoundError:
            log.debug("ignoring missing file %s", file)
        except Exception as e:
            print("Error reading file %s: %s" % (file, repr(e)))
            raise

    def get_notes(self):
        """Fill self.notes with a structured list of notes."""
        seen = {}
        notes = defaultdict(lambda: defaultdict(lambda: []))
        for tag, ct, cname, hsh, file in self.logs:
            if seen.get(file):  # pragma: no cover
                # defensive, can happen with weird logs, hard to set up
                continue
            seen[file] = True
            try:
                self.load_note(tag, file, ct, cname, hsh, notes)
            except FileNotFoundError:
                pass

        cname = self.git("config", "user.name").strip()

        for file in self.git("diff", "--name-only", "--cached").split("\n"):
            path = normalize(file.strip())
            self._load_uncommitted(seen, notes, path, cname)

        for porc in self.git("status", "--porcelain").split("\n"):
            path = normalize(porc[3:].strip())
            self._load_uncommitted(seen, notes, path, cname)

        if self.args.lint:
            # every file, not just diffs
            for file in os.listdir(self.notes_dir):
                path = normalize(os.path.join(self.notes_dir, file))
                self._load_uncommitted(seen, notes, path, cname)

        self.notes = notes

    def _load_uncommitted(self, seen, notes, path, cname):
        if seen.get(path):
            return
        if not os.path.isfile(path):
            return
        if not path.endswith(".yaml"):
            return
        if not path.startswith(self.notes_dir):
            return
        seen[path] = True
        self.load_note("Uncommitted", path, os.stat(path).st_mtime, cname, None, notes)

    def get_report(self):
        """Turn self.notes into a markdown report."""
        num = 0
        for tag, sections in self.notes.items():
            if tag == "HEAD":
                tag = "Current Branch"
            if num > 0:
                print("")
            num += 1
            print(tag)
            print("=" * len(tag))

            ents = sections.get(self.prelude_name, {})
            for ent in sorted(ents, key=lambda ent: ent["time"], reverse=True):
                note = ent["note"].strip()
                print(note, "\n")

            for sec, title in self.sections.items():
                ents = sections.get(sec, {})
                if not ents:
                    continue
                print()
                print(title)
                print("-" * len(title))
                for ent in sorted(ents, key=lambda ent: ent["time"], reverse=True):
                    note = ent["note"]
                    if self.args.blame:
                        epoch = ent["time"]
                        name = ent["name"]
                        hsh = ent["hash"]
                        hsh = "`" + hsh + "`" if hsh else ""
                        print(
                            "-",
                            note,
                            hsh,
                            "(" + name + ")",
                            time.strftime("%y-%m-%d", time.localtime(epoch)),
                        )
                    else:
                        print("-", note)

    def get_branch(self):
        """Get current branch name."""
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def switch_branch(self, branch):
        """Switch current branch."""
        self.git("-c", "advice.detachedHead=false", "checkout", branch)

    def create_new(self):
        """Create a new note with an editor and prompt for git add."""
        ymd = datetime.today().strftime("%Y-%m-%d")
        name = ymd + "-" + os.urandom(8).hex() + ".yaml"
        fp = os.path.join(self.notes_dir, name)
        with open(fp, "w", encoding="utf8") as fh:
            fh.write(self.cfg.get("template"))

        # get editor
        editor = self.cfg.get(
            "editor." + sys.platform, self.cfg.get("editor", os.environ.get("VISUAL"))
        )

        if not editor:  # pragma: no cover
            if sys.platform == "win32":
                editor = "notepad.exe"
            else:
                editor = "vi"

        exe = shutil.which(editor)
        if exe:
            cmd = [exe, fp]
            subprocess.run(cmd, check=True)
        else:  # pragma: no cover
            # happens in the windows tests, since they use a cmd builtin
            subprocess.run(editor + ' "' + fp + '"', check=True, shell=True)

        self.lint_file(fp)

        answer = input("Add to git [y|n]: ")
        if answer[0].lower() == "y":
            self.git("add", fp)

        print("Created:", normalize(fp))

    def lint_file(self, fp):
        """Lint a single file."""
        seen = {}
        notes = defaultdict(lambda: defaultdict(lambda: []))
        cname = self.git("config", "user.name").strip()

        self._load_uncommitted(seen, notes, fp, cname)

    def run(self):
        """Run the program, with current args."""
        orig = None
        if self.args.create:
            self.create_new()
            return

        if self.args.check:
            self.branch_check()
            return

        if self.ver_end != "HEAD":
            orig = self.get_branch()
            self.switch_branch(self.ver_end)
        try:
            self.get_tags()
            self.get_start_from_end()
            self.get_logs()
            if orig:
                self.switch_branch(orig)
                orig = None
            self.get_notes()
            if self.args.lint:
                return
            if self.args.yaml:
                print(yaml.dump(self.notes))
                return
            self.get_report()

            print(self.report)
        finally:
            if orig:
                self.switch_branch(orig)

    def message(self, msgid):
        """Get a message based on msgid, uses DEFAULT_CONFIG if not set."""
        msg = self.cfg.get("messages", {}).get(msgid, None)
        msg = msg or DEFAULT_CONFIG["messages"][msgid]
        return msg

    def not_important(self, filename):
        """True if the filename will be skipped by the branch check."""
        skip = self.cfg.get("skip", [])
        for ent in skip:
            if re.search(ent, filename):
                return True
        return False

    def branch_check(self):
        """Check current branch for new notes."""
        # target for diff, in order of precedence

        target = self.args.target

        if not target:
            br = os.environ.get(
                "GITHUB_BASE_REF", os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME")
            )  # github & gitlab ci
            if br:
                target = "origin/" + br

        target = target or self.cfg.get("merge-target")

        if not target:
            # no upstream configured, guess
            for ent in self.git(
                "branch", "-r", "--format", "%(refname:short)", "--list", "origin/ma??*"
            ).split("\n"):
                if ent in ("origin/master", "origin/main"):
                    target = ent

        assert target, self.message(Msg.NEED_TARGET)

        try:
            diff_base = self.git("merge-base", "HEAD", target).strip()
            print("Check merge target:", target + ", diff base:", diff_base)
        except subprocess.CalledProcessError:
            print("Check merge target:", target)
            diff_base = target

        need_notes = False
        all_diff = self.git("diff", "--name-only", diff_base)
        for ent in all_diff.split("\n"):
            ent = ent.strip()
            if not ent or self.not_important(ent):
                continue
            if ent.startswith(self.notes_dir):
                self.lint_file(ent)
                continue
            log.debug("need notes: %s", ent)
            need_notes = True
            break

        if not need_notes:
            return

        diff = self.git("diff", "--name-only", "--diff-filter=A", diff_base)
        for ent in diff.split("\n"):
            ent = ent.strip()
            if ent.startswith(self.notes_dir):
                print("Found new note:", ent)
                return

        assert False, self.message(Msg.NEED_NOTE)
