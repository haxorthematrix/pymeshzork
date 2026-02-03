"""Text parser for PyMeshZork - natural language command processing."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymeshzork.engine.world import World
    from pymeshzork.engine.state import GameState


class TokenType(Enum):
    """Types of tokens in parsed input."""

    VERB = auto()
    NOUN = auto()
    ADJECTIVE = auto()
    PREPOSITION = auto()
    DIRECTION = auto()
    NUMBER = auto()
    ARTICLE = auto()
    BUZZ = auto()  # Ignored words
    UNKNOWN = auto()


@dataclass
class Token:
    """A single parsed token."""

    text: str
    token_type: TokenType
    value: str | int | None = None  # Resolved value (verb ID, object ID, etc.)


@dataclass
class ParsedCommand:
    """Result of parsing a command."""

    verb: str | None = None
    direct_object: str | None = None  # Object ID
    indirect_object: str | None = None  # Object ID
    direction: str | None = None
    preposition: str | None = None
    raw_input: str = ""
    tokens: list[Token] = field(default_factory=list)
    error: str | None = None
    ambiguous_objects: list[str] = field(default_factory=list)


class Parser:
    """Natural language parser for adventure game commands."""

    # Buzz words - ignored during parsing
    BUZZ_WORDS = frozenset([
        "a", "an", "the", "and", "of", "to", "is", "by", "go",
        "run", "proceed", "please", "then",
    ])

    # Articles
    ARTICLES = frozenset(["a", "an", "the"])

    # Prepositions with their IDs
    PREPOSITIONS = {
        "over": 1,
        "with": 2,
        "using": 2,
        "through": 2,
        "at": 3,
        "to": 4,
        "in": 5,
        "inside": 5,
        "into": 5,
        "down": 6,
        "up": 7,
        "under": 8,
        "of": 9,
        "on": 10,
        "off": 11,
        "from": 12,
        "about": 13,
        "for": 14,
        "behind": 15,
        "around": 16,
    }

    # Direction words
    DIRECTIONS = {
        "n": "north", "north": "north",
        "s": "south", "south": "south",
        "e": "east", "east": "east",
        "w": "west", "west": "west",
        "ne": "northeast", "northeast": "northeast",
        "nw": "northwest", "northwest": "northwest",
        "se": "southeast", "southeast": "southeast",
        "sw": "southwest", "southwest": "southwest",
        "u": "up", "up": "up",
        "d": "down", "down": "down",
        "enter": "enter", "in": "enter",
        "exit": "exit", "out": "exit", "leave": "exit",
        "launch": "launch",
        "land": "land",
        "cross": "cross",
    }

    # Verb vocabulary with synonyms
    VERBS = {
        # Movement
        "go": "walk", "walk": "walk", "run": "walk", "travel": "walk",
        "move": "move",  # MOVE is distinct - moves objects, not player

        # Looking
        "look": "look", "l": "look", "stare": "look", "gaze": "look",
        "examine": "examine", "x": "examine", "describe": "examine",
        "what": "examine",
        "read": "read", "skim": "read",

        # Object manipulation
        "take": "take", "get": "take", "pick": "take", "grab": "take",
        "hold": "take", "carry": "take", "remove": "take",
        "drop": "drop", "release": "drop", "put": "put", "place": "put",
        "insert": "put", "stuff": "put",
        "throw": "throw", "hurl": "throw", "chuck": "throw",
        "give": "give", "hand": "give", "donate": "give",
        "pour": "pour", "spill": "pour",

        # Container operations
        "open": "open",
        "close": "close", "shut": "close",
        "lock": "lock",
        "unlock": "unlock",
        "fill": "fill",
        "empty": "empty",

        # Combat
        "attack": "attack", "fight": "attack", "hit": "attack",
        "hurt": "attack", "injure": "attack",
        "kill": "kill", "murder": "kill", "slay": "kill",
        "stab": "kill", "dispatch": "kill",
        "swing": "swing", "thrust": "swing",
        "poke": "poke", "break": "poke", "jab": "poke",

        # Physical actions
        "push": "push", "press": "push", "shove": "push",
        "pull": "pull", "tug": "pull",
        "turn": "turn", "set": "turn", "rotate": "turn",
        "spin": "spin",
        "shake": "shake",
        "rub": "rub", "caress": "rub", "touch": "rub", "fondle": "rub",
        "wave": "wave", "flaunt": "wave", "brandish": "wave",
        "raise": "raise", "lift": "raise",
        "lower": "lower",
        "tie": "tie", "fasten": "tie",
        "untie": "untie", "free": "untie",
        "dig": "dig",
        "climb": "climb",
        "jump": "jump", "leap": "jump",
        "kick": "kick", "bite": "kick", "taunt": "kick",
        "knock": "knock", "rap": "knock",
        "ring": "ring", "peal": "ring",

        # Light/fire
        "light": "light",
        "extinguish": "extinguish", "douse": "extinguish",
        "burn": "burn", "ignite": "burn", "incinerate": "burn",
        "melt": "melt", "liquify": "melt",

        # Food/drink
        "eat": "eat", "consume": "eat", "gobble": "eat",
        "munch": "eat", "taste": "eat",
        "drink": "drink", "imbibe": "drink", "swallow": "drink",

        # Communication
        "say": "say", "speak": "say", "talk": "say",
        "tell": "tell", "command": "tell", "request": "tell",
        "yell": "yell", "scream": "yell", "shout": "yell",
        "hello": "hello", "hi": "hello",
        "pray": "pray",
        "chat": "chat", "broadcast": "chat",
        "who": "who", "players": "who", "online": "who",

        # Special/meta
        "inventory": "inventory", "i": "inventory", "invent": "inventory",
        "wait": "wait", "z": "wait",
        "save": "save",
        "restore": "restore", "load": "restore",
        "quit": "quit", "q": "quit",
        "score": "score",
        "time": "time",
        "brief": "brief",
        "verbose": "verbose",
        "superbrief": "superbrief",
        "version": "version",
        "help": "help", "info": "help",
        "diagnose": "diagnose",
        "again": "again", "g": "again",

        # Vehicle
        "board": "board",
        "disembark": "disembark",

        # Water
        "swim": "swim", "bathe": "swim", "wade": "swim",
        "pump": "pump",
        "inflate": "inflate",
        "deflate": "deflate",

        # Special verbs
        "find": "find", "seek": "find", "where": "find", "see": "find",
        "follow": "follow",
        "wake": "wake", "surprise": "wake", "alarm": "wake", "startle": "wake",
        "mung": "mung", "hack": "mung", "frob": "mung", "damage": "mung",
        "plug": "plug", "glue": "plug", "patch": "plug",
        "brush": "brush", "clean": "brush",
        "strike": "strike",
        "wind": "wind",
        "exorcise": "exorcise",
        "incant": "incant",
        "answer": "answer",

        # Zork-specific
        "zork": "zork",
        "frobozz": "frobozz",
        "dungeon": "dungeon",
        "treasure": "treasure",
        "temple": "temple",
        "win": "win",
        "blast": "blast",
        "granite": "granite",
    }

    # Common adjectives
    ADJECTIVES = frozenset([
        "large", "small", "big", "little", "old", "new", "rusty",
        "brass", "broken", "brown", "white", "black", "red", "blue",
        "green", "yellow", "purple", "orange", "gold", "golden",
        "silver", "wooden", "wood", "steel", "iron", "crystal",
        "glass", "stone", "ancient", "oriental", "persian", "nasty",
        "elvish", "bloody", "dead", "burned", "hot", "cold",
        "large", "huge", "enormous", "tiny", "beautiful", "ugly",
        "shiny", "dull", "sharp", "blunt", "round", "square",
        "long", "short", "empty", "full", "open", "closed",
        "north", "south", "east", "west", "upper", "lower",
    ])

    # Special pronouns
    PRONOUNS = {
        "it": "it",
        "that": "it",
        "this": "it",
        "them": "them",
        "all": "all",
        "everything": "all",
        "me": "me",
        "myself": "me",
    }

    def __init__(self) -> None:
        """Initialize the parser."""
        self.last_command: ParsedCommand | None = None

    def tokenize(self, input_text: str) -> list[Token]:
        """Break input into tokens."""
        tokens = []
        # Normalize input
        text = input_text.lower().strip()
        # Remove punctuation except apostrophes
        text = "".join(c if c.isalnum() or c in " '" else " " for c in text)
        words = text.split()

        # Track context for ambiguous words
        last_meaningful_type = None

        for word in words:
            # Determine context based on previous token
            context = ""
            if last_meaningful_type == TokenType.NOUN:
                context = "after_noun"

            token = self._classify_token(word, context)
            tokens.append(token)

            # Update context tracker (skip buzz words and articles)
            if token.token_type not in (TokenType.BUZZ, TokenType.ARTICLE):
                last_meaningful_type = token.token_type

        return tokens

    def _classify_token(self, word: str, context: str = "") -> Token:
        """Classify a single word token.

        Args:
            word: The word to classify
            context: Context hint - "after_noun" means interpret ambiguous words as preps
        """
        word_lower = word.lower()

        # Check for buzz words first
        if word_lower in self.BUZZ_WORDS:
            return Token(word, TokenType.BUZZ)

        # Check for articles
        if word_lower in self.ARTICLES:
            return Token(word, TokenType.ARTICLE)

        # Check for prepositions - before directions for context-sensitive words
        # Words like "in" should be prepositions when following a noun
        if word_lower in self.PREPOSITIONS:
            # If in "after_noun" context, prefer preposition
            if context == "after_noun":
                return Token(word, TokenType.PREPOSITION, word_lower)
            # If not also a direction, it's definitely a preposition
            if word_lower not in self.DIRECTIONS:
                return Token(word, TokenType.PREPOSITION, word_lower)

        # Check for directions
        if word_lower in self.DIRECTIONS:
            return Token(word, TokenType.DIRECTION, self.DIRECTIONS[word_lower])

        # Check for verbs
        if word_lower in self.VERBS:
            return Token(word, TokenType.VERB, self.VERBS[word_lower])

        # Fallback for prepositions that weren't handled above
        if word_lower in self.PREPOSITIONS:
            return Token(word, TokenType.PREPOSITION, word_lower)

        # Check for pronouns
        if word_lower in self.PRONOUNS:
            return Token(word, TokenType.NOUN, self.PRONOUNS[word_lower])

        # Check for adjectives
        if word_lower in self.ADJECTIVES:
            return Token(word, TokenType.ADJECTIVE, word_lower)

        # Check for numbers
        if word.isdigit():
            return Token(word, TokenType.NUMBER, int(word))

        # Default to noun
        return Token(word, TokenType.NOUN, word_lower)

    def parse(
        self,
        input_text: str,
        world: "World",
        state: "GameState",
    ) -> ParsedCommand:
        """Parse a command string into structured form."""
        result = ParsedCommand(raw_input=input_text)

        # Handle empty input
        if not input_text.strip():
            result.error = "I beg your pardon?"
            return result

        # Tokenize
        tokens = self.tokenize(input_text)
        result.tokens = tokens

        # Filter out buzz words and articles for processing
        meaningful_tokens = [
            t for t in tokens
            if t.token_type not in (TokenType.BUZZ, TokenType.ARTICLE)
        ]

        if not meaningful_tokens:
            result.error = "I don't understand that."
            return result

        # Handle "again" command
        if (len(meaningful_tokens) == 1 and
            meaningful_tokens[0].token_type == TokenType.VERB and
            meaningful_tokens[0].value == "again"):
            if self.last_command and not self.last_command.error:
                return self.last_command
            else:
                result.error = "There is nothing to repeat."
                return result

        # Parse based on first token type
        first = meaningful_tokens[0]

        # Direction-only command (implicit "go")
        if first.token_type == TokenType.DIRECTION:
            result.verb = "walk"
            result.direction = first.value
            self.last_command = result
            return result

        # Must start with a verb
        if first.token_type != TokenType.VERB:
            result.error = "I don't know how to do that."
            return result

        result.verb = first.value

        # Handle communication verbs that take literal text
        if result.verb in self.TEXT_VERBS:
            # Extract raw text after the verb
            verb_word = first.word if hasattr(first, 'word') else first.value
            # Find where the verb ends in the original input
            lower_input = input_text.lower()
            verb_pos = lower_input.find(verb_word.lower())
            if verb_pos >= 0:
                text_start = verb_pos + len(verb_word)
                raw_text = input_text[text_start:].strip()
                if raw_text:
                    result.direct_object = raw_text
            self.last_command = result
            return result

        # Handle verb-only commands
        if len(meaningful_tokens) == 1:
            self.last_command = result
            return result

        # Process remaining tokens
        remaining = meaningful_tokens[1:]
        current_adjectives: list[str] = []
        looking_for_indirect = False
        current_prep = None

        for token in remaining:
            if token.token_type == TokenType.DIRECTION:
                result.direction = token.value

            elif token.token_type == TokenType.PREPOSITION:
                current_prep = token.value
                looking_for_indirect = True

            elif token.token_type == TokenType.ADJECTIVE:
                current_adjectives.append(token.value)

            elif token.token_type == TokenType.NOUN:
                # Build noun phrase with adjectives
                noun_phrase = " ".join(current_adjectives + [token.value])
                current_adjectives = []

                if looking_for_indirect:
                    result.indirect_object = noun_phrase
                    result.preposition = current_prep
                    looking_for_indirect = False
                elif result.direct_object is None:
                    result.direct_object = noun_phrase
                else:
                    result.indirect_object = noun_phrase

            elif token.token_type == TokenType.NUMBER:
                # Treat numbers as nouns
                if result.direct_object is None:
                    result.direct_object = str(token.value)
                else:
                    result.indirect_object = str(token.value)

        # Resolve object references
        self._resolve_objects(result, world, state)

        self.last_command = result
        return result

    # Verbs that take literal text arguments, not object references
    TEXT_VERBS = frozenset([
        "say", "yell", "shout", "tell", "answer", "incant", "chat", "broadcast",
    ])

    def _resolve_objects(
        self,
        result: ParsedCommand,
        world: "World",
        state: "GameState",
    ) -> None:
        """Resolve noun phrases to actual object IDs."""
        # Skip resolution for verbs that take literal text
        if result.verb in self.TEXT_VERBS:
            return

        # Handle pronouns
        if result.direct_object == "it":
            if state.last_it:
                result.direct_object = state.last_it
            else:
                result.error = "I don't know what 'it' refers to."
                return

        if result.indirect_object == "it":
            if state.last_it:
                result.indirect_object = state.last_it
            else:
                result.error = "I don't know what 'it' refers to."
                return

        # Try to match direct object to actual objects
        if result.direct_object and result.direct_object not in ("all", "me"):
            matches = world.find_object_by_name(
                result.direct_object,
                state,
                search_inventory=True,
                search_room=True,
            )

            if len(matches) == 0:
                result.error = f"I don't see any {result.direct_object} here."
            elif len(matches) == 1:
                result.direct_object = matches[0].id
                state.last_it = matches[0].id
            else:
                # Ambiguous - multiple matches
                result.ambiguous_objects = [m.id for m in matches]
                names = ", ".join(m.name for m in matches)
                result.error = f"Which do you mean: {names}?"

        # Resolve indirect object similarly
        if result.indirect_object and result.indirect_object not in ("all", "me"):
            matches = world.find_object_by_name(
                result.indirect_object,
                state,
                search_inventory=True,
                search_room=True,
            )

            if len(matches) == 0:
                result.error = f"I don't see any {result.indirect_object} here."
            elif len(matches) == 1:
                result.indirect_object = matches[0].id
            else:
                result.ambiguous_objects = [m.id for m in matches]
                names = ", ".join(m.name for m in matches)
                result.error = f"Which do you mean: {names}?"

    def get_verb_info(self, verb: str) -> dict:
        """Get information about a verb."""
        return {
            "canonical": self.VERBS.get(verb, verb),
            "requires_object": verb in {
                "take", "drop", "put", "throw", "give", "open", "close",
                "read", "examine", "push", "pull", "turn", "attack", "kill",
                "eat", "drink", "light", "extinguish", "fill", "tie", "untie",
            },
            "requires_direction": verb in {"walk", "go", "run", "move"},
        }

    def format_help(self, multiplayer_connected: bool = False) -> str:
        """Return help text for available commands.

        Args:
            multiplayer_connected: Whether multiplayer is active (shows chat commands).
        """
        verbs = sorted(set(self.VERBS.values()))
        directions = sorted(set(self.DIRECTIONS.values()))

        help_text = (
            "Available commands:\n"
            f"  Verbs: {', '.join(verbs[:20])}...\n"
            f"  Directions: {', '.join(directions)}\n"
            "\nExamples:\n"
            "  go north, n, take lamp, examine sword\n"
            "  put book in case, attack troll with sword"
        )

        if multiplayer_connected:
            help_text += (
                "\n\nMultiplayer commands:\n"
                "  say <message>  - Say something to players in your room\n"
                "  yell <message> - Shout to all players\n"
                "  chat <message> - Broadcast to all players\n"
                "  who            - See who's online and where"
            )

        return help_text
