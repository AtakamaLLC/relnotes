# relnotes
Release notes manager.

This is kindof like reno, except it's faster because it makes some assumptions about git logs.


[(view source)](https://github.com/atakamallc/relnotes/blob/master/relnotes/__init__.py)
# [relnotes](#relnotes).runner
Release notes runner class


[(view source)](https://github.com/atakamallc/relnotes/blob/master/relnotes/runner.py)
## Runner(object)
Process relnotes command line args.


#### .get\_logs(self)
Get a list of logs with tag, hash and ct.

#### .get\_start\_from\_end(self)
If start not specified, assume previous release.

#### .get\_tags(self)
Get release tags, reverse sorted.

#### .git(self, *args)
Shell git with args.


## Functions:

