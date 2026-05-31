"""Save and load question sets to / from JSON files (the 'question bank')."""
import json
import os
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger(__name__)

# The sub-folder created inside the user's output directory.
_BANK_SUBDIR = 'question_bank'


def save(questions: list, topic: str, subject: str, output_dir: str) -> str:
    """Serialise *questions* to a JSON file and return the saved path.

    Creates ``<output_dir>/question_bank/`` if it does not already exist.
    """
    bank_dir = os.path.join(output_dir, _BANK_SUBDIR)
    os.makedirs(bank_dir, exist_ok=True)

    date_tag = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    safe_topic = (
        ''.join(c for c in topic[:30] if c.isalnum() or c in (' ', '-', '_'))
        .strip()
        .replace(' ', '_')
    )
    path = os.path.join(bank_dir, f'questions_{safe_topic}_{date_tag}.json')

    payload = {
        'subject': subject,
        'topic': topic,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'questions': questions,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info('Question bank saved: %s  (%d questions)', path, len(questions))
    return path


def load(path: str) -> dict:
    """Load a question bank JSON file.

    Returns a dict with at minimum the keys ``questions``, ``topic``, ``subject``.
    Raises ``ValueError`` for files that are not valid question bank exports.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict) or 'questions' not in data:
        raise ValueError('Not a valid question bank file — missing "questions" key.')
    if not isinstance(data['questions'], list):
        raise ValueError('Corrupt question bank file — "questions" is not a list.')

    logger.info('Question bank loaded: %s  (%d questions)', path, len(data['questions']))
    return data
