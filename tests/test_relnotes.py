import os
import re
import yaml
import sys
import contextlib
import pytest
import logging as log

from unittest.mock import patch

from relnotes import Runner
from relnotes.runner import normalize
from relnotes.main import parse_args, main


def test_lint():
    args = parse_args(["--lint", "--debug"])
    r = Runner(args)
    r.run()


@patch("relnotes.runner.CONFIG_PATH", "noconf.yaml")
def test_noconf():
    args = parse_args(["--lint", "--debug"])
    r = Runner(args)
    r.run()


def test_report(capsys):
    args = parse_args([])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    assert "Current Branch" in captured.out


@pytest.fixture
def tmp_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ndir = str(tmp_path / "notes")
    os.mkdir(ndir)
    args = parse_args(["--notes-dir", "notes"])
    r = Runner(args)
    r.git("init", ".")
    return r


@pytest.fixture
def tmp_run_with_notes(tmp_run):
    r = tmp_run
    ndir = r.notes_dir

    # set up faux notes repo
    with open(os.path.join(ndir, "note1.yaml"), "w") as n1:
        n1.write('{"features": ["feature 1"], "release_summary": ["summary 1"]}')
    r.git("add", "notes")
    r.git("commit", "-am", ".")
    r.git("tag", "0.0.1")
    with open(os.path.join(ndir, "note2.yaml"), "w") as n2:
        n2.write('{"features": ["feature 2"], "release_summary": "summary 2"}')
    r.git("add", "notes")
    r.git("commit", "-am", ".")
    r.git("tag", "0.0.2")

    yield r


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


def test_yaml(capsys):
    args = parse_args(["--yaml"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert res["HEAD"]


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
