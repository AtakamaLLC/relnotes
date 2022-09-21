"""Release notes manager.

This is kindof like reno, except it's faster because it makes some assumptions about git logs.

"""
from .runner import Runner
from .main import main, parse_args
