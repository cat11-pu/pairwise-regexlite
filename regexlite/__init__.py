"""Public interface of the regexlite engine package."""

from .core import (
    Match,
    Pattern,
    PatternSyntaxError,
    RegexError,
    compile_pattern,
    fullmatch,
    match,
    search,
)

__all__ = [
    "Match",
    "Pattern",
    "PatternSyntaxError",
    "RegexError",
    "compile_pattern",
    "search",
    "match",
    "fullmatch",
]
