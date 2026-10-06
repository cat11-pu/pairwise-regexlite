"""Acceptance tests for the regexlite engine.

Run them from the project root with:

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regexlite import PatternSyntaxError, compile_pattern, fullmatch, match, search


def found(pattern, text):
    """The leftmost match of pattern in text; fails the test when there is none."""
    result = search(pattern, text)
    if result is None:
        raise AssertionError("%r did not match %r at all" % (pattern, text))
    return result


def whole(pattern, text):
    """The match of pattern over the whole text; fails the test when there is none."""
    result = fullmatch(pattern, text)
    if result is None:
        raise AssertionError("%r did not match the whole of %r" % (pattern, text))
    return result


class LiteralTest(unittest.TestCase):
    def test_plain_patterns_match_leftmost(self):
        self.assertEqual(found("b", "abcb").span(), (1, 2))
        self.assertEqual(found("bc", "abcb").span(), (1, 3))
        self.assertEqual(found("b", "abcb").group(), "b")
        self.assertEqual(match("ab", "abc").span(), (0, 2))
        self.assertIsNone(match("bc", "abc"))
        self.assertIsNone(search("z", "abc"))
        self.assertEqual(whole("abc", "abc").span(), (0, 3))
        self.assertIsNone(fullmatch("ab", "abc"))
        self.assertEqual(whole("ab?c", "ac").span(), (0, 2))
        self.assertEqual(found("ab*c", "ac").span(), (0, 2))
        self.assertEqual(found("b+", "abbb").span(), (1, 4))
        self.assertEqual(found("a+", "ba").span(), (1, 2))
        self.assertEqual(whole("ab+", "abb").span(), (0, 3))


class DotTest(unittest.TestCase):
    def test_dot_matches_any_character_but_a_newline(self):
        self.assertEqual(found("a.c", "abc").span(), (0, 3))
        self.assertEqual(whole("a.c", "axc").span(), (0, 3))
        self.assertEqual(found("a.b", "axb").span(), (0, 3))
        self.assertEqual(found("a.c", "a.c").span(), (0, 3))
        self.assertIsNone(search("a.c", "a\nc"))
        self.assertIsNone(search(".", "\n"))
        self.assertEqual(whole("...", "xyz").group(), "xyz")
        self.assertEqual(found("..", "ab\n").span(), (0, 2))


class AnchorTest(unittest.TestCase):
    def test_anchors_match_text_edges_and_line_edges(self):
        self.assertEqual(found("^abc", "abcdef").span(), (0, 3))
        self.assertIsNone(search("^bcd", "abcdef"))
        self.assertEqual(found("def$", "abcdef").span(), (3, 6))
        self.assertIsNone(search("def$", "abcdefg"))
        self.assertEqual(found("$", "abcdef").span(), (6, 6))
        self.assertEqual(found("^", "abcdef").span(), (0, 0))
        self.assertEqual(found("^b", "a\nb\nc").span(), (2, 3))
        self.assertEqual(found("b$", "a\nb\nc").span(), (2, 3))
        self.assertIsNone(search("x$", "a\nb\nc"))
        self.assertEqual(found("^c", "a\nb\nc").span(), (4, 5))


class ClassTest(unittest.TestCase):
    def test_character_classes_cover_literals_ranges_and_complements(self):
        self.assertEqual(found("[abc]+", "xxabcxx").span(), (2, 5))
        self.assertEqual(whole("[abc]", "b").span(), (0, 1))
        self.assertEqual(found("[a-c]+", "abcd").span(), (0, 3))
        self.assertEqual(found("[^a-c]+", "abcd").span(), (3, 4))
        self.assertEqual(whole("[^0-9]+", "abc").span(), (0, 3))
        self.assertEqual(found("[0-9]+", "ab12cd").span(), (2, 4))
        self.assertEqual(found("[a-c\\d]+", "xbc12y").span(), (1, 5))
        self.assertEqual(whole("[-a]+", "a-a").span(), (0, 3))
        self.assertEqual(found("\\d+", "ab12cd").span(), (2, 4))
        self.assertEqual(whole("\\D+", "abc").span(), (0, 3))
        self.assertEqual(whole("\\w+", "a_1").span(), (0, 3))
        self.assertEqual(found("\\s+", "a \t b").span(), (1, 4))
        self.assertEqual(found("([a-c]+)d", "abcd").group(1), "abc")


class RepeatTest(unittest.TestCase):
    def test_repeat_bounds_are_counted(self):
        self.assertEqual(found("a{3}", "aaaaa").span(), (0, 3))
        self.assertEqual(found("a{2,}", "aaaa").span(), (0, 4))
        self.assertEqual(found("a{2,}?", "aaaa").span(), (0, 2))
        self.assertEqual(whole("a{2,3}", "aaa").span(), (0, 3))
        self.assertEqual(found("(ab){2,}", "ababab").span(), (0, 6))
        self.assertIsNone(fullmatch("a{2,3}", "a"))
        self.assertIsNone(fullmatch("a{4,}", "aaa"))
        self.assertIsNone(fullmatch("a{3}", "aa"))


class LazyTest(unittest.TestCase):
    def test_lazy_repeats_prefer_the_shortest_repeat(self):
        self.assertEqual(found("a*?", "aaa").span(), (0, 0))
        self.assertEqual(found("a+?", "aaa").span(), (0, 1))
        self.assertEqual(found("a??", "aaa").span(), (0, 0))
        self.assertEqual(found("a*?b", "aab").span(), (0, 3))
        self.assertEqual(found("<.*?>", "<a><b>").span(), (0, 3))
        self.assertEqual(found("<.*?>", "<a><b>").group(), "<a>")
        self.assertEqual(whole("a{2,3}?", "aa").span(), (0, 2))
        self.assertIsNone(fullmatch("a{2,3}?", "a"))


class BacktrackTest(unittest.TestCase):
    def test_failed_continuations_unwind_a_greedy_repeat(self):
        self.assertEqual(found("a*", "aaa").span(), (0, 3))
        self.assertEqual(found("a*b", "aaab").span(), (0, 4))
        self.assertEqual(found("a*ab", "aaab").span(), (0, 4))
        self.assertEqual(found("a*a", "aa").span(), (0, 2))
        self.assertEqual(whole(".*b", "aab").span(), (0, 3))
        self.assertEqual(found("a+ab", "aaab").span(), (0, 4))
        self.assertEqual(found("[ab]*b", "aab").span(), (0, 3))
        self.assertEqual(whole("(a|b)*b", "abb").span(), (0, 3))
        self.assertIsNone(fullmatch("a*b", "aaa"))


class CaptureTest(unittest.TestCase):
    def test_groups_are_reported_and_refreshed_on_every_repeat(self):
        first = found("(a|b)+", "ab")
        self.assertEqual(first.span(), (0, 2))
        self.assertEqual(first.group(1), "b")
        self.assertEqual(first.groups(), ("b",))
        second = found("((a)(b))+", "abab")
        self.assertEqual(second.span(), (0, 4))
        self.assertEqual(second.groups(), ("ab", "a", "b"))
        self.assertEqual(second.span(1), (2, 4))
        optional = found("(a)(b)?", "ac")
        self.assertEqual(optional.span(), (0, 1))
        self.assertEqual(optional.groups(), ("a", None))
        self.assertEqual(optional.span(2), (-1, -1))
        self.assertIsNone(optional.group(2))
        branch = found("(a)|(b)", "b")
        self.assertEqual(branch.groups(), (None, "b"))
        pattern = compile_pattern("(x)(y)")
        self.assertEqual(pattern.group_count, 2)
        self.assertEqual(pattern.search("xy").group(2), "y")


class AlternationTest(unittest.TestCase):
    def test_alternation_keeps_the_written_order_and_falls_back(self):
        self.assertEqual(found("cat|dog", "hotdog").span(), (3, 6))
        self.assertEqual(found("x|yz", "ayz").span(), (1, 3))
        self.assertEqual(match("a|ab", "ab").span(), (0, 1))
        self.assertEqual(found("(a|ab)c", "abc").span(), (0, 3))
        self.assertEqual(found("(a|ab)c", "abc").group(1), "ab")
        self.assertEqual(whole("ab|a", "ab").span(), (0, 2))
        self.assertEqual(found("a|b|cd", "cd").span(), (0, 2))
        self.assertEqual(found("(ab|a)b", "aab").span(), (1, 3))
        self.assertEqual(found("(ab|a)b", "aab").group(), "ab")
        self.assertEqual(found("(ab|a)b", "aab").group(1), "a")


class ErrorTest(unittest.TestCase):
    def test_malformed_patterns_are_rejected(self):
        bad_patterns = [
            "(",
            "(a",
            "(?:a)",
            "(?=a)",
            "[abc",
            "[]",
            "[z-a]",
            "*a",
            "+a",
            "?a",
            "a{",
            "a{2",
            "a{2,1}",
            "a\\",
            "a\\q",
        ]
        for pattern in bad_patterns:
            try:
                compile_pattern(pattern)
            except PatternSyntaxError:
                continue
            raise AssertionError("pattern %r was accepted" % (pattern,))
        with self.assertRaises(TypeError):
            compile_pattern(None)
        pattern = compile_pattern("(a)(b)")
        self.assertEqual(pattern.group_count, 2)
        result = found("(a)(b)", "ab")
        with self.assertRaises(IndexError):
            result.group(3)


if __name__ == "__main__":
    unittest.main()
