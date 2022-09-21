# rnotes
Release notes manager.

This is kindof like reno, except it's faster because it makes some assumptions about git logs,
and uses current tag state, not branch history.


The idea is you create a folder with note files, and on your merge CI, you run a linter to ensure that your
devs are posting release notes.

The notes relevant to a tag are those committed between that tag's creation and the previous tag (if any).

Note history is then easy to extract from git tags and logs.


### USAGE: rnotes

```
  -h, --help            show this help message and exit
  --version VERSION     Version to report on (default: current branch)
  --previous PREVIOUS   Previous version, (default: ordinal previous tag)
  --version-regex VERSION_REGEX
                        Regex to use when parsing (default: from rnotes.yaml)
  --notes-dir REL_NOTES_DIR
                        Release notes folder
  --debug               Debug mode
  --yaml                Dump yaml
  --lint                Lint notes for valid markdown
  --create              Create a new note
  --check               Check if current branch has a release note
  --target TARGET       Target branch for merge (default: from ci env or upstream)
  --blame               Show more commit info in the report
```


### EXAMPLE config: rnotes.yaml

```
encoding: utf8
earliest_version: 0.0.1
release_tag_re: ^((?:[\d.ab]|rc)+)$
editor.win32: notepad.exe
sections:
  - [features, New Features]
  - [issues, Known Issues]
  - [upgrade, Upgrade Notes]
  - [security, Security Issues]
  - [fixes, Bug Fixes]
  - [internal, Internal Changes]
prelude_section_name: release_summary
template: |
  # These notes are public facing!!! Write your notes accordingly.
  release_summary: >
      Replace this text with content to appear at the
      top of the section for this release.
  features:
    - List new features here, or remove this section.
  issues:
    - List known issues here, or remove this section.
  upgrade:
    - List upgrade notes here, or remove this section.
  security:
    - Add security notes here, or remove this section.
  fixes:
    - Add normal bug fixes here, or remove this section.
  internal:
    - List internal non-user-facing notes here, or remove this section
```

[(view source)](https://github.com/atakamallc/rnotes)
