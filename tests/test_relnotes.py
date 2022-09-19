import os
import re
import yaml
import sys
import contextlib
import pytest

from relnotes import Runner
from relnotes.runner import normalize
from relnotes.main import parse_args, main


def test_lint():
    args = parse_args(["--lint", "--debug"])
    r = Runner(args)
    r.run()


def test_report(capsys):
    src_branch = os.environ.get("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME")
    if src_branch and "release-" in src_branch:
        pytest.skip("Skipping test on release branch")
    args = parse_args([])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    assert "Current Branch" in captured.out


def test_yaml(capsys):
    src_branch = os.environ.get("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME")
    if src_branch and "release-" in src_branch:
        pytest.skip("Skipping test on release branch")
    args = parse_args(["--yaml"])
    r = Runner(args)
    r.run()
    captured = capsys.readouterr()
    res = yaml.safe_load(captured.out)
    assert res["HEAD"]


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
