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

    async def summarize_topic(self, raw_text: str) -> str:
        """Summarize raw math content (from images or PDFs) into a worksheet topic description.

        This is the shared final step for both image and PDF analysis paths.
        """
        model = self._config.get('text_model', 'llama-3.3-70b-versatile')
        logger.info('Summarizing topic with text model: %s', model)

        prompt = (
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

        client = self._client()
        response = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=256,
            temperature=0,
            timeout=60,
        )
        return response.choices[0].message.content.strip()

    async def generate_questions(
        self, topic: str, difficulty: str, num_questions: int
    ) -> list:
        """Generate worksheet questions with full solutions. Returns list of dicts."""
        guidance = _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE['Intermediate'])
        model = self._config.get('text_model', 'llama-3.3-70b-versatile')
        logger.info(
            'Generating %d questions | difficulty=%s | model=%s',
            num_questions, difficulty, model,
        )

        prompt = (
            f'You are an experienced math teacher creating a printed practice worksheet.\n\n'
            f'Topic description:\n{topic}\n\n'
            f'Difficulty: {difficulty} — {guidance}\n\n'
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
            f'IMPORTANT: Return ONLY a valid JSON array — no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       — the problem statement following the rules above.\n'
            f'  "solution_steps" — a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   — the concise final answer only (e.g. "x = 4" or "42").\n'
            f'  "needs_grid"     — true if the student must plot points or draw on a coordinate plane '
            f'to solve the problem, false for all other questions.\n\n'
            f'Example of correct format:\n'
            f'[\n'
            f'  {{\n'
            f'    "question": "Solve: 2x + 4 = 12",\n'
            f'    "solution_steps": ["Subtract 4 from both sides: 2x = 8", "Divide both sides by 2: x = 4"],\n'
            f'    "final_answer": "x = 4",\n'
            f'    "needs_grid": false\n'
            f'  }},\n'
            f'  {{\n'
            f'    "question": "Plot the points A(2, 3) and B(-1, 4) on the coordinate plane. '
            f'Find the length of segment AB.",\n'
            f'    "solution_steps": ["Mark A(2,3) and B(-1,4) on the grid", '
            f'"Apply distance formula: d = sqrt((2-(-1))^2 + (3-4)^2) = sqrt(9+1) = sqrt(10)"],\n'
            f'    "final_answer": "sqrt(10) approx 3.16",\n'
            f'    "needs_grid": true\n'
            f'  }}\n'
            f']'
        )

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
