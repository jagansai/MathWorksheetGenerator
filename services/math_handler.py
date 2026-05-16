"""Prompt handler tuned for Mathematics worksheets."""

from services.base_handler import QuestionType, _SubjectHandler

_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.MCQ: 'MCQ (multiple-choice)',
    QuestionType.WORD: 'Word Problem',
    QuestionType.NON_WORD: 'Non-Word Problem',
}

_TYPE_DESCRIPTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        'multiple-choice with exactly 4 lettered choices (A, B, C, D); '
        'one correct answer and three plausible-but-wrong distractors; '
        'prefer computational or formula-based stems (no narrative).'
    ),
    QuestionType.WORD: (
        'real-world application with a narrative context '
        '(e.g. distance/rate/time, area of a room, sharing money); open answer — no choices.'
    ),
    QuestionType.NON_WORD: (
        'direct computation or formula-based, no narrative '
        '(e.g. "Solve: 2x + 3 = 9" or "Evaluate: 3^2 + 4^2"); open answer — no choices.'
    ),
}


def _compute_breakdown(num_questions: int, question_types: list[QuestionType]) -> dict[QuestionType, int]:
    """Distribute num_questions as evenly as possible among the given types."""
    k = len(question_types)
    base = num_questions // k
    rem = num_questions % k
    return {t: base + (1 if i < rem else 0) for i, t in enumerate(question_types)}


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
        self, topic: str, difficulty: str, guidance: str, num_questions: int,
        question_types: list[QuestionType] | None = None,
    ) -> str:
        types = question_types or [QuestionType.NON_WORD]
        breakdown = _compute_breakdown(num_questions, types)
        has_mcq = QuestionType.MCQ in types

        type_lines = '\n'.join(
            f'  - {breakdown[t]} {_TYPE_LABELS[t]}'
            f' question{"s" if breakdown[t] != 1 else ""}: {_TYPE_DESCRIPTIONS[t]}'
            for t in types
        )
        type_values = ', '.join(f'"{t.value}"' for t in types)

        if has_mcq:
            choices_schema = (
                '  "choices"        \u2014 (MCQ only) JSON array of exactly 4 strings, '
                'e.g. ["A) 3", "B) 6", "C) 9", "D) 12"]. '
                'Omit this key for non-MCQ questions.\n'
                '  "correct_choice" \u2014 (MCQ only) letter of the correct answer: '
                '"A", "B", "C", or "D". Omit this key for non-MCQ questions.\n'
            )
        else:
            choices_schema = ''

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
            f'QUESTION TYPE BREAKDOWN \u2014 generate exactly {num_questions} questions total, '
            f'distributed throughout the array:\n'
            f'{type_lines}\n\n'
            f'CRITICAL RULES:\n'
            f'1. Every question must be 100% self-contained in its text. '
            f'Do NOT reference "the image", "the figure", "the graph shown", "the diagram", '
            f'"the table above", "the textbook", or any external visual material.\n'
            f'2. Students will receive a plain printed sheet. '
            f'If a problem involves a coordinate plane, describe all points and coordinates '
            f'directly in the question text (e.g. "Plot the points A(2,3), B(-1,4) and find..."). '
            f'A blank coordinate grid will be printed below questions that need one.\n'
            f'3. Use plain-text math notation (e.g. x^2 + 3x - 4 = 0, not LaTeX).\n'
            f'4. MCQ distractors must be plausible (e.g. common student errors) but unambiguously wrong.\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the problem statement following the rules above.\n'
            f'  "type"           \u2014 one of: {type_values}.\n'
            f'{choices_schema}'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer '
            f'(for MCQ: include the full winning option text, e.g. "B) x = 3").\n'
            f'  "needs_grid"     \u2014 true if the student must plot points or draw on a coordinate plane '
            f'to solve the problem, false for all others (always false for MCQ).\n\n'
            f'REQUIRED JSON FORMAT (structural examples only \u2014 '
            f'do NOT copy or reuse these specific problems):\n'
            f'[\n'
            f'{self._json_examples(types)}\n'
            f']'
        )

    def _json_examples(self, types: list[QuestionType]) -> str:
        """Build the structural JSON examples block for the prompt."""
        examples = []
        for t in types:
            if t == QuestionType.MCQ:
                examples.append(
                    '  {\n'
                    '    "question": "<computational or formula-based question>",\n'
                    '    "type": "mcq",\n'
                    '    "choices": ["A) <option>", "B) <option>", "C) <option>", "D) <option>"],\n'
                    '    "correct_choice": "<A|B|C|D>",\n'
                    '    "solution_steps": ["<step 1>", "<step 2>"],\n'
                    '    "final_answer": "<letter) full winning option text>",\n'
                    '    "needs_grid": false\n'
                    '  }'
                )
            elif t == QuestionType.WORD:
                examples.append(
                    '  {\n'
                    '    "question": "<real-world narrative problem>",\n'
                    '    "type": "word",\n'
                    '    "solution_steps": ["<step 1>", "<step 2>", "<step 3>"],\n'
                    '    "final_answer": "<concise answer>",\n'
                    '    "needs_grid": false\n'
                    '  }'
                )
            else:  # NON_WORD
                examples.append(
                    '  {\n'
                    '    "question": "<direct computation, e.g. Solve: 2x + 3 = 9>",\n'
                    '    "type": "non_word",\n'
                    '    "solution_steps": ["<step 1>", "<step 2>"],\n'
                    '    "final_answer": "<concise answer>",\n'
                    '    "needs_grid": false\n'
                    '  }'
                )
        return ',\n'.join(examples)


_MATH_HANDLER = _MathHandler()
