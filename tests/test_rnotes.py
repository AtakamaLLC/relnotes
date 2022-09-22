import os
import re
import yaml
import sys
import contextlib
import pytest
import logging as log

from unittest.mock import patch

from rnotes import Runner
from rnotes.runner import normalize, Msg
from rnotes.main import parse_args, main


def test_lint():
    args = parse_args(["--lint", "--debug"])
    r = Runner(args)
    r.run()


GENERIC_NOTES = [
    {
        "name": "note1.yaml",
        "tag": "0.0.1",
        "data": {"features": ["feature 1"], "release_summary": ["summary 1"]},
    },
    {
        "name": "note2.yaml",
        "tag": "0.0.2",
        "data": {"features": ["feature 2"], "release_summary": ["summary 2"]},
    },
]


@pytest.fixture
def tmp_run_noconf(tmp_run_generator):
    for r in tmp_run_generator(subdir="releasenotes"):
        gen_notes(r, GENERIC_NOTES)
        yield r


@patch("rnotes.runner.CONFIG_PATH", "noconf.yaml")
def test_noconf(tmp_run_noconf):
    r = tmp_run_noconf
    args = parse_args(["--lint", "--debug"])
    r = Runner(args)
    r.run()


def test_report(capsys, tmp_run_with_notes):
    args = parse_args(["--notes-dir", "notes"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    assert "0.0.2" in captured.out
    assert "feature 2" in captured.out


def gen_notes(runner, notes):
    for note in notes:
        with open(os.path.join(runner.notes_dir, note["name"]), "w") as n1:
            yaml.dump(note["data"], n1)
            runner.git("add", runner.notes_dir)
            runner.git("commit", "-am", ".")
            if note.get("tag"):
                runner.git("tag", note["tag"])


@pytest.fixture
def tmp_run_generator(tmp_path, monkeypatch):
    def _gen(*, subdir=None, extra_args=None):
        subdir = subdir or "notes"
        monkeypatch.chdir(tmp_path)
        ndir = str(tmp_path / subdir)
        os.mkdir(ndir)
        args = parse_args(["--notes-dir", subdir] + (extra_args if extra_args else []))
        r = Runner(args)
        r.git("init", ".")

        yield r

    yield _gen


@pytest.fixture
def tmp_run(tmp_run_generator):
    yield from tmp_run_generator(subdir="notes")


@pytest.fixture
def tmp_run_with_notes(tmp_run):
    gen_notes(tmp_run, GENERIC_NOTES)
    yield tmp_run


def test_head_is_earliest(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes

    # run report
    r.run()

    captured = capsys.readouterr()
    log.debug(captured.out)
    assert "feature 2" in captured.out
    assert "feature 1" not in captured.out

    # whole report
    args = parse_args(["--notes-dir", r.notes_dir, "--yaml", "--previous", "TAIL"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert "0.0.1" in res
    assert "0.0.2" in res


def test_check_branch(capsys, monkeypatch, tmp_run_with_notes):
    # don't use this for this test
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", raising=False)

    r = tmp_run_with_notes

    r.git("checkout", "-b", "branch")

    with open("dev.js", "w", encoding="utf8") as fh:
        fh.write("some file")
    r.git("add", "dev.js")

    args = parse_args(["--notes-dir", r.notes_dir, "--check", "--target", "master"])
    r = Runner(args)

    # this fails, because we're on a new branch, with no notes
    with pytest.raises(AssertionError, match=re.escape(r.message(Msg.NEED_NOTE))):
        r.run()

    with open(r.notes_dir + "/mynote.yaml", "w", encoding="utf8") as fh:
        fh.write("release_summary: some stuff")

    # not in git
    with pytest.raises(AssertionError, match=re.escape(r.message(Msg.NEED_NOTE))):
        r.run()

    # ok, this is good enough
    r.git("add", r.notes_dir + "/mynote.yaml")
    r.run()

    # commit doesn't change things
    r.git("commit", "-am", ".")
    r.run()

    # clear stdout
    capsys.readouterr()

    args = parse_args(["--notes-dir", r.notes_dir, "--yaml"])
    r = Runner(args)
    r.run()

    out = capsys.readouterr().out
    info = yaml.safe_load(out)

    # uncommitted notes go into the HEAD section
    assert "some stuff" in info["HEAD"]["release_summary"][0]["note"]


def test_uncomitted(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    with open(r.notes_dir + "/mynote.yaml", "w", encoding="utf8") as fh:
        fh.write("release_summary: some stuff")
    r.git("add", r.notes_dir + "/mynote.yaml")
    # uncommitted notes show up in reports too
    args = parse_args(["--notes-dir", r.notes_dir])
    r = Runner(args)
    r.run()
    out = capsys.readouterr().out
    assert "Uncommitted" in out
    assert "Current Branch" not in out
    assert "some stuff" in out


def test_current_branch(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    with open(r.notes_dir + "/mynote.yaml", "w", encoding="utf8") as fh:
        fh.write("release_summary: some stuff")
    r.git("add", r.notes_dir + "/mynote.yaml")
    r.git("commit", "-am", ".")
    # uncommitted notes show up in reports too
    args = parse_args(["--notes-dir", r.notes_dir])
    r = Runner(args)
    r.run()
    out = capsys.readouterr().out
    assert "Uncommitted" not in out
    assert "Current Branch" in out
    assert "some stuff" in out


def test_missing_note(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    os.unlink(os.path.join(r.notes_dir, "note1.yaml"))
    args = parse_args(["--notes-dir", r.notes_dir, "--yaml", "--previous", "TAIL"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert "0.0.2" in res
    assert "0.0.1" not in res


def test_blame(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    os.unlink(os.path.join(r.notes_dir, "note1.yaml"))
    args = parse_args(["--notes-dir", r.notes_dir, "--blame"])
    r = Runner(args)
    r.run()
    cname = r.git("config", "user.name").strip()
    captured = capsys.readouterr()
    assert "0.0.2" in captured.out
    assert cname in captured.out


def test_oldver(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    args = parse_args(["--notes-dir", r.notes_dir, "--version=0.0.1"])
    r = Runner(args)
    assert r.get_branch() == "master"
    r.run()
    assert r.get_branch() == "master"
    captured = capsys.readouterr()
    assert "0.0.1" in captured.out
    assert "0.0.2" not in captured.out


def test_oldver_error(capsys, tmp_run_with_notes):
    r = tmp_run_with_notes
    args = parse_args(["--notes-dir", r.notes_dir, "--version=0.0.1"])
    assert r.get_branch() == "master"
    r = Runner(args)
    r.get_logs = "error"
    with pytest.raises(TypeError):
        r.run()
    assert r.get_branch() == "master"


def test_yaml(capsys, tmp_run_with_notes):
    args = parse_args(["--notes-dir", "notes", "--yaml", "--previous", "TAIL"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert res["0.0.1"]


def test_create(tmp_run, capsys, monkeypatch):
    monkeypatch.setenv("VISUAL", "type" if sys.platform == "win32" else "echo")
    monkeypatch.setattr("builtins.input", lambda _: "y\n")
    args = parse_args(["--create", "--notes-dir", tmp_run.notes_dir])
    r = Runner(args)
    r.run()
    res = r.git("status").strip("\n")

    # new file was made
    assert "new file" in res
    assert ".yaml" in res
    assert tmp_run.notes_dir in res

    # fname in stdout
    out = capsys.readouterr().out
    fn = re.match(r"\bcreated[: ]*([^\n]+)", out, re.I)
    fn = fn[1]
    with open(fn, encoding="utf8") as fh:
        note = yaml.safe_load(fh)
        assert "release_summary" in note
        assert "features" in note


@contextlib.contextmanager
def mock_git(runner, regex, result):
    func = runner.git

    def new_git(*args):
        cmd = " ".join(args)
        if re.match(regex, cmd):
            return result
        return func(*args)

    runner.git = new_git
    yield
    runner.git = func


def test_diff(capsys, tmp_path):
    args = parse_args(["--yaml", "--rel-notes-dir", str(tmp_path)])
    r = Runner(args)
    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("release_summary: rel")

    norm_path = normalize(str(tmp_path)) + "/rel.yaml"
    with mock_git(r, r"diff --name-only", f"{norm_path}\n"), mock_git(r, r"log.*", ""):
        r.run()

    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert res["Uncommitted"]["release_summary"][0]["note"] == "rel"


def test_lint_all(tmp_path):
    assert os.path.exists(tmp_path)
    args = parse_args(["--lint", "--rel-notes-dir", str(tmp_path)])
    r = Runner(args)
    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("releaxxxxx: rel")

    with pytest.raises(AssertionError, match=".*is not a valid section.*"):
        r.run()


def test_bad_section(tmp_path):
    assert os.path.exists(tmp_path)
    args = parse_args(["--yaml", "--rel-notes-dir", str(tmp_path)])
    r = Runner(args)
    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("releaxxxxx: rel")

    norm_path = normalize(str(tmp_path)) + "/rel.yaml"
    with mock_git(r, r"diff --name-only", f"{norm_path}\n"), mock_git(r, r"log.*", ""):
        with pytest.raises(AssertionError, match=".*is not a valid section.*"):
            r.run()


def test_bad_entry(tmp_path):
    args = parse_args(["--rel-notes-dir", str(tmp_path)])
    r = Runner(args)
    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("release_summary: [{'bad': 'summary'}]")

    norm_path = normalize(str(tmp_path)) + "/rel.yaml"
    with mock_git(r, r"diff --name-only", f"{norm_path}\n"), mock_git(r, r"log.*", ""):
        with pytest.raises(AssertionError, match=".*simple string.*"):
            r.run()


def test_bad_entry2(tmp_path):
    args = parse_args(["--rel-notes-dir", str(tmp_path)])
    r = Runner(args)
    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("release_summary: {'bad': 'summary'}")

    norm_path = normalize(str(tmp_path)) + "/rel.yaml"
    with mock_git(r, r"diff --name-only", f"{norm_path}\n"), mock_git(r, r"log.*", ""):
        with pytest.raises(AssertionError, match=".*of entries.*"):
            r.run()


def test_main(tmp_path):
    sys.argv = ("whatever", "--lint", "--debug")
    main()

    sys.argv = ("whatever", "--rel-notes-dir=notexist")
    with pytest.raises(FileNotFoundError):
        main()

    with open(tmp_path / "rel.yaml", "w") as f:
        f.write("releaxxxxx: rel")

    sys.argv = ("whatever", "--rel-notes-dir", str(tmp_path), "--lint")
    with pytest.raises(SystemExit):
        main()


def test_args():
    args = parse_args(
        ["--version", "4.5.6", "--debug", "--previous", "4.5.1", "--lint"]
    )
    assert args.version == "4.5.6"
    assert args.previous == "4.5.1"
    assert args.lint
    assert args.debug
    args = parse_args(
        ["--version", "4.5.6", "--debug", "--previous", "4.5.1", "--yaml"]
    )
    assert args.yaml
    args = parse_args(
        ["--version", "4.5.6", "--debug", "--previous", "4.5.1", "--blame"]
    )
    assert args.blame
