# regexlite

A small backtracking regular expression engine written with the Python standard
library only. It supports literals, the dot, character classes with ranges and
complement, shorthand classes, greedy and lazy repeats, capturing groups,
alternation and the two anchors; the engine lives in `regexlite/core.py`.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v
