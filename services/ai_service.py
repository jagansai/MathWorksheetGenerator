"""Groq AI service — image analysis and worksheet question generation."""
import asyncio
import base64
import json
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from utils.logger import setup_logger

if TYPE_CHECKING:
    from utils.config_manager import ConfigManager

logger = setup_logger(__name__)

_DIFFICULTY_GUIDANCE = {
    'Beginner': (
        'simple, single-step problems suitable for students just learning the topic. '
        'Use small, friendly numbers. Avoid complex notation.'
    ),
    'Intermediate': (
        'moderate problems requiring 2-4 steps. Include some application of the concept. '
        'Mix of straightforward and slightly tricky problems.'
    ),
    'Advanced': (
        'challenging multi-step problems requiring deeper understanding. '
        'May combine multiple concepts. Include word problems where appropriate.'
    ),
}


# ---------------------------------------------------------------------------
# Per-subject prompt handlers
# ---------------------------------------------------------------------------

def _split_into_segments(text: str, n: int = 3, min_chars_per_segment: int = 3000) -> list[str]:
    """Split *text* into *n* roughly equal segments.

    Returns a single-element list (the original text) when the text is too
    short to benefit from segmentation (i.e. fewer than *n × min_chars_per_segment*
    characters).
    """
    if len(text) < min_chars_per_segment * n:
        return [text]
    size = len(text) // n
    return [text[i * size: (i + 1) * size] for i in range(n)]


class _SubjectHandler:
    """Base class — subclass per subject and override the three prompt methods."""

    def summarize_prompt(self, raw_text: str) -> str:
        raise NotImplementedError

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        raise NotImplementedError

    def generate_prompt(
        self, topic: str, difficulty: str, guidance: str, num_questions: int
    ) -> str:
        raise NotImplementedError


class _MathHandler(_SubjectHandler):
    """Prompts tuned for mathematics worksheets."""

    def summarize_prompt(self, raw_text: str) -> str:
        return (
            'You are helping generate a standalone math practice worksheet. '
            'Below is content extracted from a math resource. '
            'Identify the mathematical SKILLS and PROBLEM TYPES that students would actually practise — '
            'ignore historical context, biographies, introductory theory, and any non-problem text. '
            'Fill in EXACTLY this template — no extra text before or after, no markdown, no bullet symbols:\n\n'
            'Topic: <specific math topic, e.g. "Cartesian coordinate system — plotting and reading points">\n'
            'Grade level: <approximate grade, e.g. "Grade 9">\n'
            'Problem types: <comma-separated list of practice problem types, e.g. "plotting points, reading coordinates, finding distances">\n'
            'Notation/constraints: <specific notation or constraints, e.g. "integer coordinates, all four quadrants">\n\n'
            'RULES: '
            'Do NOT mention textbook names, book titles, chapter numbers, page numbers, '
            'image numbers, historical figures, or any source references. '
            'Every field must be filled; write "Standard notation" if no special constraints apply.\n\n'
            f'Content:\n{raw_text[:4000]}'
        )

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        segment_note = (
            f' This excerpt is from the **{segment_label}** of the chapter,'
            ' so the problems here are likely more representative of the'
            ' chapter\'s difficulty than the opening introductory examples.'
            if segment_label and segment_label != 'beginning'
            else ''
        )
        return (
            f'Below is text extracted from a math textbook or worksheet.{segment_note}\n'
            'Find 2 to 3 ACTUAL EXERCISE PROBLEMS from the text — problems students are asked to solve. '
            'Select problems that show VARIETY: '
            'include word problems, computational problems, pattern/sequence problems, '
            'and table/graph problems if present. Prefer problems that test deeper understanding '
            'over trivial one-step calculations.\n\n'
            'Return ONLY a numbered list of the problems, copied VERBATIM from the source. '
            'Do NOT rewrite, summarise, or add any explanation. '
            'If the text contains no exercise problems, return exactly the word: NONE\n\n'
            f'Text:\n{raw_text[:6000]}'
        )

    def generate_prompt(
        self, topic: str, difficulty: str, guidance: str, num_questions: int
    ) -> str:
        return (
            f'You are an experienced math teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" section, '
            f'generate questions that CLOSELY MATCH the style, real-world contexts, and problem '
            f'types shown in those samples \u2014 same structural patterns and variety, but with '
            f'different numbers and scenarios. Cover the FULL RANGE of problem types shown, '
            f'not just the simplest ones. Problems labelled "[From the middle of the chapter]" '
            f'or "[From the end of the chapter]" represent the intended difficulty level; '
            f'weight your generated questions accordingly.\n\n'
            f'Difficulty: {difficulty} \u2014 {guidance}\n\n'
            f'Generate exactly {num_questions} distinct math problems.\n\n'
            f'CRITICAL RULES:\n'
            f'1. Every question must be 100% self-contained in its text. '
            f'Do NOT reference "the image", "the figure", "the graph shown", "the diagram", '
            f'"the table above", "the textbook", or any external visual material.\n'
            f'2. Students will receive a plain printed sheet. '
            f'If a problem involves a coordinate plane, describe all points and coordinates '
            f'directly in the question text (e.g. "Plot the points A(2,3), B(-1,4) and find..."). '
            f'A blank coordinate grid will be printed below questions that need one.\n'
            f'3. Use plain-text math notation (e.g. x^2 + 3x - 4 = 0, not LaTeX).\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the problem statement following the rules above.\n'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer only (e.g. "x = 4" or "42").\n'
            f'  "needs_grid"     \u2014 true if the student must plot points or draw on a coordinate plane '
            f'to solve the problem, false for all other questions.\n\n'
            f'REQUIRED JSON FORMAT (these are structural examples only \u2014 '
            f'do NOT copy or reuse these specific problems):\n'
            f'[\n'
            f'  {{\n'
            f'    "question": "<problem statement relevant to the topic above>",\n'
            f'    "solution_steps": ["<step 1>", "<step 2>", "<step 3>"],\n'
            f'    "final_answer": "<concise answer>",\n'
            f'    "needs_grid": false\n'
            f'  }},\n'
            f'  {{\n'
            f'    "question": "<another problem statement relevant to the topic above>",\n'
            f'    "solution_steps": ["<step 1>", "<step 2>"],\n'
            f'    "final_answer": "<concise answer>",\n'
            f'    "needs_grid": true\n'
            f'  }}\n'
            f']'
        )


class _GenericHandler(_SubjectHandler):
    """Placeholder handler for subjects not yet fully implemented.

    Uses the same structure as _MathHandler but replaces math-specific framing
    with the subject name.  Replace with a dedicated handler in Phase 2.
    """

    def __init__(self, subject: str):
        self._subject = subject

    def summarize_prompt(self, raw_text: str) -> str:
        return (
            f'You are helping generate a standalone {self._subject} practice worksheet. '
            f'Below is content extracted from a {self._subject} resource. '
            f'Identify the SKILLS and PROBLEM TYPES that students would actually practise \u2014 '
            'ignore historical context, biographies, introductory theory, and any non-problem text. '
            'Fill in EXACTLY this template \u2014 no extra text before or after, no markdown, no bullet symbols:\n\n'
            f'Topic: <specific {self._subject} topic>\n'
            'Grade level: <approximate grade, e.g. "Grade 9">\n'
            'Problem types: <comma-separated list of practice problem types>\n'
            'Notation/constraints: <specific notation or constraints>\n\n'
            'RULES: '
            'Do NOT mention textbook names, book titles, chapter numbers, page numbers, '
            'image numbers, historical figures, or any source references. '
            'Every field must be filled; write "Standard notation" if no special constraints apply.\n\n'
            f'Content:\n{raw_text[:4000]}'
        )

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        segment_note = (
            f' This excerpt is from the **{segment_label}** of the chapter,'
            ' so the problems here are likely more representative of the'
            ' chapter\'s difficulty than the opening introductory examples.'
            if segment_label and segment_label != 'beginning'
            else ''
        )
        return (
            f'Below is text extracted from a {self._subject} textbook or worksheet.{segment_note}\n'
            'Find 2 to 3 ACTUAL EXERCISE PROBLEMS from the text — problems students are asked to solve. '
            'Select problems that show VARIETY across the different sections. '
            'Prefer problems that test deeper understanding over trivial one-step calculations.\n\n'
            'Return ONLY a numbered list of the problems, copied VERBATIM from the source. '
            'Do NOT rewrite, summarise, or add any explanation. '
            'If the text contains no exercise problems, return exactly the word: NONE\n\n'
            f'Text:\n{raw_text[:6000]}'
        )

    def generate_prompt(
        self, topic: str, difficulty: str, guidance: str, num_questions: int
    ) -> str:
        return (
            f'You are an experienced {self._subject} teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" section, '
            f'generate questions that CLOSELY MATCH the style, real-world contexts, and problem '
            f'types shown in those samples \u2014 same structural patterns and variety, but with '
            f'different numbers and scenarios. Cover the FULL RANGE of problem types shown.\n\n'
            f'Difficulty: {difficulty} \u2014 {guidance}\n\n'
            f'Generate exactly {num_questions} distinct {self._subject} problems.\n\n'
            f'CRITICAL RULES:\n'
            f'1. Every question must be 100% self-contained in its text. '
            f'Do NOT reference "the image", "the figure", "the graph shown", "the diagram", '
            f'"the table above", "the textbook", or any external visual material.\n'
            f'2. Students will receive a plain printed sheet. Use plain-text notation.\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the problem statement.\n'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer only.\n'
            f'  "needs_grid"     \u2014 false.\n'
        )


_MATH_HANDLER = _MathHandler()


def _get_handler(subject: str) -> _SubjectHandler:
    """Return the prompt handler for *subject*, falling back to a generic stub."""
    if subject == 'Mathematics':
        return _MATH_HANDLER
    return _GenericHandler(subject)


# ---------------------------------------------------------------------------

class AIService:
    def __init__(self, config_manager: 'ConfigManager'):
        self._config = config_manager

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self._config.get('groq_api_key'),
            base_url='https://api.groq.com/openai/v1',
        )

    async def extract_from_images(self, image_paths: list[str]) -> str:
        """Use the vision model to transcribe mathematical content from images as plain text.

        The result is raw extracted content, intended to be passed to summarize_topic().
        """
        content: list[dict] = []
        for image_path in image_paths:
            with open(image_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            ext = image_path.rsplit('.', 1)[-1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            content.append({
                'type': 'image_url',
                'image_url': {'url': f'data:{mime};base64,{encoded}'},
            })

        content.append({
            'type': 'text',
            'text': (
                'Describe the mathematical content in these image(s) as plain text. '
                'Include: the topic, types of problems shown, any equations or expressions, '
                'notation used, and approximate grade level. '
                'Do NOT mention image numbers, textbook names, or cite visual evidence. '
                'Write as plain, self-contained text only.'
            ),
        })

        model = self._config.get('vision_model', 'meta-llama/llama-4-scout-17b-16e-instruct')
        logger.info('Extracting content from %d image(s) with vision model: %s', len(image_paths), model)

        client = self._client()
        response = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': content}],
            max_tokens=1024,
            timeout=60,
        )
        return response.choices[0].message.content.strip()

    async def summarize_topic(self, raw_text: str, subject: str = 'Mathematics') -> str:
        """Summarize raw content into a worksheet topic description.

        Dispatches to the per-subject prompt handler.  This is the shared
        final step for both image and PDF analysis paths.
        """
        model = self._config.get('text_model', 'llama-3.3-70b-versatile')
        logger.info('Summarizing topic | subject=%s | model=%s', subject, model)

        prompt = _get_handler(subject).summarize_prompt(raw_text)

        client = self._client()
        response = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=256,
            temperature=0,
            timeout=60,
        )
        return response.choices[0].message.content.strip()

    async def extract_style_examples(self, raw_text: str, subject: str = 'Mathematics') -> str:
        """Return representative exercise problems verbatim from the raw content.

        When the source text is long enough, it is split into three segments
        (beginning / middle / end) and sampled in parallel so that harder
        problems from later in the chapter are included alongside the simpler
        introductory ones.  Results from all segments are merged.

        Dispatches to the per-subject prompt handler.  The results are passed
        back into generate_questions as few-shot style examples.
        Returns an empty string when no exercise problems are found.
        """
        handler = _get_handler(subject)
        model = self._config.get('text_model', 'llama-3.3-70b-versatile')
        logger.info('Extracting style examples | subject=%s | model=%s', subject, model)

        client = self._client()

        async def _call_segment(prompt: str) -> str:
            response = await client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=1024,
                temperature=0,
                timeout=60,
            )
            return response.choices[0].message.content.strip()

        segments = _split_into_segments(raw_text)

        if len(segments) == 1:
            # Short document — single call, original behaviour
            result = await _call_segment(handler.style_examples_prompt(raw_text))
            return '' if result.upper() == 'NONE' else result

        # Long document — sample beginning, middle, and end in parallel
        segment_labels = ['beginning', 'middle', 'end']
        prompts = [
            handler.style_examples_prompt(seg, label)
            for seg, label in zip(segments, segment_labels)
        ]
        logger.info(
            'Sampling style examples from %d segments (%s chars each)',
            len(segments), len(segments[0]),
        )
        results = await asyncio.gather(*[_call_segment(p) for p in prompts])

        # Merge non-empty results, labelled by chapter position
        parts = []
        for label, result in zip(segment_labels, results):
            if result and result.upper() != 'NONE':
                header = f'[Problems from the {label} of the chapter]'
                parts.append(f'{header}\n{result}')

        return '\n\n'.join(parts)

    async def generate_questions(
        self, topic: str, difficulty: str, num_questions: int, subject: str = 'Mathematics'
    ) -> list:
        """Generate worksheet questions with full solutions. Returns list of dicts."""
        guidance = _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE['Intermediate'])
        model = self._config.get('text_model', 'llama-3.3-70b-versatile')
        logger.info(
            'Generating %d questions | subject=%s | difficulty=%s | model=%s',
            num_questions, subject, difficulty, model,
        )

        prompt = _get_handler(subject).generate_prompt(topic, difficulty, guidance, num_questions)

        client = self._client()
        response = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=4096,
            temperature=0.7,
            timeout=120,
        )

        raw = response.choices[0].message.content.strip()
        return self._parse_questions(raw)

    def _parse_questions(self, raw: str) -> list:
        """Parse JSON from AI response, stripping any accidental markdown fences."""
        text = raw
        if '```' in text:
            # Strip markdown code fences
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        text = text.strip()

        # Find the JSON array boundaries as a fallback
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            text = text[start:end + 1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error('JSON parse error: %s\nRaw (first 500 chars): %s', e, raw[:500])
            raise ValueError(
                f'The AI returned an unexpected format. Please try again.\nDetail: {e}'
            ) from e

        if not isinstance(data, list):
            raise ValueError('AI response was not a JSON array.')

        return data
