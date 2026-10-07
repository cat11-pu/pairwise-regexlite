r"""A small backtracking regular expression engine (standard library only).

Syntax: literals; . any character except a newline; [abc] [^abc] [a-z]
character classes with ranges and complement; \d \D \w \W \s \S shorthand
classes; \n \t \r \f \v and escaped specials such as \. and \\; * + ?
{n} {n,} {n,m} repeats, greedy by default and lazy with a following ?;
( ) groups; | alternation; ^ the start of the text or of a line;
$ the end of the text or of a line.

Matching is a backtracking search over the pattern tree: the leftmost start
position wins and, inside one start position, the first alternative of the
pattern in its preference order wins.  A greedy repeat prefers the longest
repeat, a lazy repeat the shortest one, and a repeat is unwound again
whenever the rest of the pattern cannot match.
"""

MAX_STEPS = 100000

DIGITS = frozenset("0123456789")
WORD_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
SPACE_CHARS = frozenset(" \t\n\r\f\v")

SHORTHAND = {
    "d": (DIGITS, False), "D": (DIGITS, True),
    "w": (WORD_CHARS, False), "W": (WORD_CHARS, True),
    "s": (SPACE_CHARS, False), "S": (SPACE_CHARS, True),
}
CONTROL_CHARS = {"n": "\n", "t": "\t", "r": "\r", "f": "\f", "v": "\v"}


class RegexError(Exception):
    """Base class of the errors raised by this module."""


class PatternSyntaxError(RegexError):
    """The pattern cannot be parsed."""


class Match:
    """A successful match.  Group 0 is the whole match and the other groups are
    numbered from 1 in the order of their opening parenthesis; a group that did
    not take part in the match has the span (-1, -1) and the value None.
    """
    def __init__(self, text, start, end, captures, group_count):
        self.text, self.start, self.end = text, start, end
        self.captures, self.group_count = captures, group_count
    def span(self, group=0):
        if group == 0:
            return (self.start, self.end)
        if not 1 <= group <= self.group_count:
            raise IndexError("no such group: %r" % (group,))
        return self.captures.get(group, (-1, -1))
    def group(self, group=0):
        start, end = self.span(group)
        if start < 0:
            return None
        return self.text[start:end]
    def groups(self):
        return tuple(self.group(index) for index in range(1, self.group_count + 1))


def class_matches(terms, negated, ch):
    """True when the character ch belongs to a character class."""
    hit = False
    for chars, inner_negated in terms:
        if (ch in chars) != inner_negated:
            hit = True
            break
    return (not hit) if negated else hit


class _Parser:
    """Turns a pattern into a tree of nodes (see the module docstring)."""
    QUANTIFIERS = {"*": (0, None), "+": (1, None), "?": (0, 1)}
    def __init__(self, pattern):
        self.pattern = pattern
        self.pos = 0
        self.group_count = 0
    def error(self, message):
        return PatternSyntaxError("%s at %d in %r" % (message, self.pos, self.pattern))
    def peek(self):
        return self.pattern[self.pos] if self.pos < len(self.pattern) else None
    def parse(self):
        node = self.parse_alternation()
        if self.pos != len(self.pattern):
            raise self.error("unexpected character")
        return node, self.group_count
    def parse_alternation(self):
        branches = [self.parse_concat()]
        while self.peek() == "|":
            self.pos += 1
            branches.append(self.parse_concat())
        return branches[0] if len(branches) == 1 else ("alt", branches)
    def parse_concat(self):
        items = []
        while self.peek() not in (None, "|", ")"):
            items.append(self.parse_repeat())
        return items[0] if len(items) == 1 else ("cat", items)
    def parse_repeat(self):
        node = self.parse_atom()
        if self.peek() in ("*", "+", "?", "{"):
            minimum, maximum, greedy = self.parse_quantifier()
            return ("rep", node, minimum, maximum, greedy)
        return node
    def parse_quantifier(self):
        ch = self.pattern[self.pos]
        self.pos += 1
        minimum, maximum = self.parse_braces() if ch == "{" else self.QUANTIFIERS[ch]
        greedy = self.peek() != "?"
        if not greedy:
            self.pos += 1
        return minimum, maximum, greedy
    def parse_braces(self):
        start = self.pos
        while self.peek() is not None and self.peek().isdigit():
            self.pos += 1
        if start == self.pos:
            raise self.error("expected a count after {")
        minimum = int(self.pattern[start:self.pos])
        if self.peek() == "}":
            self.pos += 1
            return minimum, minimum
        if self.peek() != ",":
            raise self.error("expected } or , after the count")
        self.pos += 1
        start = self.pos
        while self.peek() is not None and self.peek().isdigit():
            self.pos += 1
        maximum = int(self.pattern[start:self.pos]) if start != self.pos else None
        if self.peek() != "}":
            raise self.error("expected } to close the repeat")
        self.pos += 1
        if maximum is not None and maximum < minimum:
            raise self.error("repeat bounds are out of order")
        return minimum, maximum
    def parse_atom(self):
        ch = self.pattern[self.pos]
        self.pos += 1
        if ch == "\\":
            return ("class", (self.parse_escape(),), False)
        if ch == "[":
            return self.parse_class()
        if ch == "(":
            return self.parse_group()
        if ch == ".":
            return ("any",)
        if ch == "^":
            return ("bol",)
        if ch == "$":
            return ("eol",)
        if ch in "*+?{":
            raise self.error("nothing to repeat")
        return ("lit", ch)
    def parse_group(self):
        if self.peek() == "?":
            raise self.error("unsupported group syntax")
        self.group_count += 1
        index = self.group_count
        body = self.parse_alternation()
        if self.peek() != ")":
            raise self.error("unbalanced (")
        self.pos += 1
        return ("group", index, body)
    def parse_escape(self):
        """The escape body as a (chars, negated) term."""
        ch = self.peek()
        if ch is None:
            raise self.error("a backslash cannot end a pattern")
        self.pos += 1
        if ch in SHORTHAND:
            return SHORTHAND[ch]
        if ch in CONTROL_CHARS:
            return (frozenset([CONTROL_CHARS[ch]]), False)
        if ch.isalnum():
            raise self.error("unknown escape")
        return (frozenset([ch]), False)
    def parse_class(self):
        negated = False
        if self.peek() == "^":
            self.pos += 1
            negated = True
        terms = []
        literals = set()
        first = True
        while True:
            ch = self.peek()
            if ch is None:
                raise self.error("unterminated character class")
            if ch == "]" and not first:
                self.pos += 1
                break
            first = False
            if ch == "\\":
                self.pos += 1
                terms.append(self.parse_escape())
                continue
            self.pos += 1
            if self.peek() == "-" and self.pattern[self.pos + 1:self.pos + 2] not in ("", "]"):
                self.pos += 1
                high = self.pattern[self.pos]
                self.pos += 1
                if ord(high) < ord(ch):
                    raise self.error("character range is out of order")
                literals.update(chr(code) for code in range(ord(ch), ord(high) + 1))
                continue
            literals.add(ch)
        if literals:
            terms.append((frozenset(literals), False))
        return ("class", tuple(terms), negated)


def _accept(end, captures):
    yield (end, captures)


class _Matcher:
    def __init__(self, text):
        self.text = text
        self.steps = 0
    def node(self, item, pos, captures, cont):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RegexError("the match needed more than %d steps" % MAX_STEPS)
        kind = item[0]
        text = self.text
        if kind == "lit":
            if pos < len(text) and text[pos] == item[1]:
                yield from cont(pos + 1, captures)
            return
        if kind == "any":
            if pos < len(text) and text[pos] != "\n":
                yield from cont(pos + 1, captures)
            return
        if kind == "class":
            if pos < len(text) and class_matches(item[1], item[2], text[pos]):
                yield from cont(pos + 1, captures)
            return
        if kind == "bol":
            if pos == 0 or (pos > 0 and text[pos - 1] == "\n"):
                yield from cont(pos, captures)
            return
        if kind == "eol":
            if pos == len(text) or text[pos] == "\n":
                yield from cont(pos, captures)
            return
        if kind == "group":
            index = item[1]
            start = pos

            def inner(end, inner_captures):
                updated = dict(inner_captures)
                updated[index] = (start, end)
                yield from cont(end, updated)

            yield from self.node(item[2], pos, captures, inner)
            return
        if kind == "cat":
            yield from self.concatenate(item[1], 0, pos, captures, cont)
            return
        if kind == "alt":
            for branch in item[1]:
                yield from self.node(branch, pos, captures, cont)
            return
        if kind == "rep":
            yield from self.repeat(item[1], pos, captures, cont, item[2], item[3], item[4], 0)
            return
        raise RegexError("unknown node %r" % (kind,))
    def concatenate(self, items, index, pos, captures, cont):
        if index == len(items):
            yield from cont(pos, captures)
            return

        def rest(end, inner_captures):
            yield from self.concatenate(items, index + 1, end, inner_captures, cont)

        yield from self.node(items[index], pos, captures, rest)
    def repeat(self, item, pos, captures, cont, minimum, maximum, greedy, count):
        if greedy:
            if maximum is None or count < maximum:
                for end, caps in self.node(item, pos, captures, _accept):
                    if end != pos:
                        yield from self.repeat(item, end, caps, cont, minimum, maximum, greedy, count + 1)
            if count >= minimum:
                yield from cont(pos, captures)
            return
        if count >= minimum:
            yield from cont(pos, captures)
        if maximum is not None and count >= maximum:
            return
        for end, caps in self.node(item, pos, captures, _accept):
            if end == pos:
                return
            yield from self.repeat(item, end, caps, cont, minimum, maximum, greedy, count + 1)


class Pattern:
    """A compiled pattern."""
    def __init__(self, source, root, group_count):
        self.source, self.root, self.group_count = source, root, group_count
    def search(self, text):
        return self.run(text, False, False)
    def match(self, text):
        return self.run(text, True, False)
    def fullmatch(self, text):
        return self.run(text, True, True)
    def run(self, text, anchored, whole):
        last = len(text)
        matcher = _Matcher(text)
        starts = (0,) if anchored else range(last + 1)
        for start in starts:
            for end, captures in matcher.node(self.root, start, {}, _accept):
                if whole and end != last:
                    continue
                return Match(text, start, end, captures, self.group_count)
        return None


def compile_pattern(pattern):
    """Compile a pattern string into a Pattern, or raise PatternSyntaxError."""
    if not isinstance(pattern, str):
        raise TypeError("the pattern must be a string")
    root, group_count = _Parser(pattern).parse()
    return Pattern(pattern, root, group_count)


def search(pattern, text):
    """The leftmost match of pattern in text, or None."""
    return compile_pattern(pattern).search(text)


def match(pattern, text):
    """The match of pattern at the start of text, or None."""
    return compile_pattern(pattern).match(text)


def fullmatch(pattern, text):
    """The match of pattern over the whole of text, or None."""
    return compile_pattern(pattern).fullmatch(text)
