"""Abstract base class for per-subject prompt handlers."""
from enum import Enum


class QuestionType(str, Enum):
    """Identifies the style of a generated question."""
    MCQ = 'mcq'
    WORD = 'word'
    NON_WORD = 'non_word'
    PROOF = 'proof'


class _SubjectHandler:
    """Base class — subclass per subject and override the three prompt methods."""

    def summarize_prompt(self, raw_text: str) -> str:
        raise NotImplementedError

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        raise NotImplementedError

    def generate_prompt(
        self, topic: str, difficulty: str, guidance: str, num_questions: int,
        question_types: list[QuestionType] | None = None, grade: str = '',
        compact: bool = False,
    ) -> str:
        raise NotImplementedError
