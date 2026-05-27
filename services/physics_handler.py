"""Prompt handler tuned for Physics worksheets."""

from services.base_handler import QuestionType, _SubjectHandler

_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.MCQ: 'MCQ (multiple-choice)',
    QuestionType.WORD: 'Application / Conceptual',
    QuestionType.NON_WORD: 'Numerical',
    QuestionType.PROOF: 'Derivation / Proof',
}

_TYPE_DESCRIPTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        'multiple-choice with exactly 4 lettered choices (A, B, C, D); '
        'one correct answer and three plausible-but-wrong distractors based on common misconceptions; '
        'may test definitions, laws, formulas, units, or conceptual understanding.'
    ),
    QuestionType.WORD: (
        'application or conceptual question with a real-world or experimental context '
        '(e.g. "A car brakes suddenly and the passengers lurch forward — explain using Newton\'s First Law", '
        '"Why does a ball thrown upward slow down before stopping?"); '
        'requires reasoning, explanation, or multi-step thinking; open answer — no choices.'
    ),
    QuestionType.NON_WORD: (
        'direct numerical calculation using a physics formula, no narrative context '
        '(e.g. "A car accelerates from rest to 20 m/s in 5 s. Calculate its acceleration.", '
        '"An object of mass 5 kg is lifted 3 m. Find the work done against gravity (g = 10 m/s^2)."); '
        'must state the given values, required quantity, and formula; open answer — no choices.'
    ),
    QuestionType.PROOF: (
        'derive a formula from first principles or show a physics result step by step '
        '(e.g. "Derive the second equation of motion v = u + at", '
        '"Show that the kinetic energy of a body is (1/2)mv\u00b2 using the work-energy theorem"); '
        'written working required; open answer — no choices.'
    ),
}


def _compute_breakdown(num_questions: int, question_types: list[QuestionType]) -> dict[QuestionType, int]:
    """Distribute num_questions as evenly as possible among the given types."""
    k = len(question_types)
    base = num_questions // k
    rem = num_questions % k
    return {t: base + (1 if i < rem else 0) for i, t in enumerate(question_types)}


class _PhysicsHandler(_SubjectHandler):
    """Prompts tuned for  Physics worksheets (primarily Class 9)."""

    def summarize_prompt(self, raw_text: str) -> str:
        return (
            'You are helping generate a standalone Physics practice worksheet for students. '
            'Below is content extracted from a Physics resource. '
            'Identify the physics CONCEPTS, LAWS, FORMULAS, and QUESTION TYPES that students '
            'would actually practise — ignore introductory narrative, historical context, '
            'biographies, and any non-question text. '
            'Fill in EXACTLY this template — no extra text before or after, no markdown, no bullet symbols:\n\n'
            'Topic: <specific physics topic, e.g. "Motion — equations of motion and uniform acceleration">\n'
            'Grade level: <approximate grade, e.g. "Grade 9">\n'
            'Problem types: <comma-separated list of practice question types, '
            'e.g. "applying equations of motion, calculating velocity and acceleration, '
            'distance-time graph interpretation, defining terms">\n'
            'Notation/constraints: <specific notation or constraints, '
            'e.g. "SI units throughout; use u for initial velocity, v for final velocity, '
            'a for acceleration, s for displacement, t for time">\n\n'
            'RULES: '
            'Do NOT mention textbook names, book titles, chapter numbers, page numbers, '
            'image numbers, historical figures, or any source references. '
            'Every field must be filled; write "SI units, standard physics notation" '
            'if no special constraints apply.\n\n'
            f'Content:\n{raw_text[:4000]}'
        )

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        segment_note = (
            f' This excerpt is from the **{segment_label}** of the chapter,'
            ' so the questions here are likely more representative of the'
            ' chapter\'s difficulty than the opening introductory examples.'
            if segment_label and segment_label != 'beginning'
            else ''
        )
        return (
            f'Below is text extracted from a Physics textbook or worksheet.{segment_note}\n'
            'Find 2 to 3 ACTUAL EXERCISE QUESTIONS from the text — questions students are asked to answer. '
            'Select questions that show VARIETY: '
            'include numerical problems, conceptual/application questions, '
            'definition or law-statement tasks, and graph-based or experimental questions if present. '
            'Prefer questions that test deeper understanding over trivial recall.\n\n'
            'Return ONLY a numbered list of the questions, copied VERBATIM from the source. '
            'Do NOT rewrite, summarise, or add any explanation. '
            'If the text contains no exercise questions, return exactly the word: NONE\n\n'
            f'Text:\n{raw_text[:6000]}'
        )

    def generate_prompt(
        self, topic: str, difficulty: str, guidance: str, num_questions: int,
        question_types: list[QuestionType] | None = None, grade: str = '',
        compact: bool = False,
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
                'e.g. ["A) 10 m/s^2", "B) 5 m/s^2", "C) 20 m/s^2", "D) 2 m/s^2"]. '
                'Omit this key for non-MCQ questions.\n'
                '  "correct_choice" \u2014 (MCQ only) letter of the correct answer: '
                '"A", "B", "C", or "D". Omit this key for non-MCQ questions.\n'
            )
        else:
            choices_schema = ''

        return (
            f'You are an experienced Physics teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" section, '
            f'generate questions that CLOSELY MATCH the style, real-world contexts, and question '
            f'types shown in those samples \u2014 same structural patterns and variety, but with '
            f'different values and scenarios. Cover the FULL RANGE of question types shown, '
            f'not just the simplest ones. Questions labelled "[From the middle of the chapter]" '
            f'or "[From the end of the chapter]" represent the intended difficulty level; '
            f'weight your generated questions accordingly.\n\n'
            f'Difficulty: {difficulty} \u2014 {guidance}\n'
            f'{f"Grade level: {grade}" + chr(10) if grade else ""}'
            f'\n'
            f'QUESTION TYPE BREAKDOWN \u2014 generate exactly {num_questions} questions total, '
            f'distributed throughout the array:\n'
            f'{type_lines}\n\n'
            f'CRITICAL RULES:\n'
            f'1. Every question must be 100% self-contained in its text. '
            f'Do NOT reference "the image", "the figure", "the diagram above", '
            f'"the graph shown", "the table", "the textbook", or any external visual material.\n'
            f'2. Use plain-text physics notation throughout '
            f'(e.g. v^2 = u^2 + 2as, F = ma, KE = (1/2)mv^2). '
            f'State all quantities in SI units (m, kg, s, N, J, W, Pa). '
            f'For numerical questions, always state the given values and required quantity '
            f'in the question stem.\n'
            f'3. MCQ distractors must be plausible (e.g. common unit errors, sign errors, '
            f'formula mix-ups) but unambiguously wrong.\n'
            f'4. solution_steps must show the full working: identify given values, '
            f'state the relevant formula, substitute values, calculate, and state units in the answer.\n'
            f'5. Use needs_diagram judiciously -- only set it to true when drawing is genuinely '
            f'the expected student response (e.g. free body diagram, ray diagram, circuit sketch). '
            f'For questions where a diagram would help but is not the answer itself, '
            f'describe the physical setup in words in the question stem instead.\n'
            f'6. SELF-CONTAINED NUMERICAL VALUES — every number needed to solve the problem '
            f'must appear explicitly in the question stem. '
            f'Source materials often carry values only in scales, diagrams, number lines, '
            f'graph axes, or figures that cannot be reproduced on a plain printed sheet. '
            f'If a sample problem relies on any such visual to supply a quantity '
            f'(distance, height, mass, voltage, temperature, time interval, position, etc.), '
            f'you must invent a concrete, realistic numerical value for that quantity and '
            f'state it directly in the question text. '
            f'NEVER leave a quantity undefined or resolvable only by reference to a figure.\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the question statement following the rules above.\n'
            f'  "type"           \u2014 one of: {type_values}.\n'
            f'{choices_schema}'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer with units '
            f'(for MCQ: include the full winning option text, e.g. "B) 10 m/s^2").\n'
            f'  "needs_diagram"  \u2014 true if the question genuinely requires a student-drawn diagram '
            f'as part of the answer (e.g. free body diagram, ray diagram, circuit sketch); '
            f'false for all other questions (always false for MCQ).\n'
            f'  "diagram_label"  \u2014 a short caption for the blank drawing box when needs_diagram is true '
            f'(e.g. "Draw the free body diagram of the block"); '
            f'use an empty string "" when needs_diagram is false.\n\n'
            f'REQUIRED JSON FORMAT (structural examples only \u2014 '
            f'do NOT copy or reuse these specific questions):\n'
            f'[\n'
            f'{self._json_examples(types)}\n'
            f']'
        )

    def _json_examples(self, types: list[QuestionType]) -> str:
        """Build structural JSON examples block for the prompt."""
        _MCQ_EX = (
            '  {\n'
            '    "question": "A body moving with uniform velocity has zero acceleration.'
            ' Which of the following best explains this?",\n'
            '    "type": "mcq",\n'
            '    "choices": ["A) The net force acting on it equals its weight",'
            ' "B) The net force acting on it is zero",'
            ' "C) The body has no mass", "D) Friction is absent"],\n'
            '    "correct_choice": "B",\n'
            '    "solution_steps": ["By Newton\'s Second Law, F = ma.",'
            ' "If a = 0 (uniform velocity), then F = 0. The net force must be zero."],\n'
            '    "final_answer": "B) The net force acting on it is zero",\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _WORD_EX = (
            '  {\n'
            '    "question": "A block of mass 4 kg sits on a rough horizontal surface.'
            ' A horizontal force of 15 N is applied to the right and a frictional force of 6 N'
            ' acts to the left. Draw the free body diagram of the block showing all four forces'
            ' (weight, normal reaction, applied force, friction) with correct directions and magnitudes.",\n'
            '    "type": "word",\n'
            '    "solution_steps": ["Identify all forces: weight W = mg = 4 x 10 = 40 N downward;'
            ' normal reaction N = 40 N upward; applied force F = 15 N rightward;'
            ' friction f = 6 N leftward.",'
            ' "In the free body diagram, represent the block as a dot and draw four labelled arrows'
            ' in the correct directions."],\n'
            '    "final_answer": "Free body diagram: W = 40 N down, N = 40 N up, F = 15 N right, f = 6 N left.",\n'
            '    "needs_diagram": true,\n'
            '    "diagram_label": "Free body diagram of the block"\n'
            '  }'
        )
        _NON_WORD_EX = (
            '  {\n'
            '    "question": "An athlete runs from point A to point B, a distance of 400 m,'
            ' at a constant speed of 8 m/s, then immediately returns to A at the same speed.'
            ' Calculate: (a) the total distance travelled, (b) the total displacement,'
            ' (c) the average speed for the entire journey.",\n'
            '    "type": "non_word",\n'
            '    "solution_steps": ["Given: one-way distance A to B = 400 m, speed = 8 m/s.",'
            ' "(a) Total distance = 400 + 400 = 800 m.",'
            ' "(b) Displacement = final position - initial position = 0 m (returns to start).",'
            ' "(c) Total time = 800 / 8 = 100 s; average speed = 800 / 100 = 8 m/s."],\n'
            '    "final_answer": "(a) 800 m  (b) 0 m  (c) 8 m/s",\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _PROOF_EX = (
            '  {\n'
            '    "question": "Derive the second equation of motion: s = ut + (1/2)at^2",\n'
            '    "type": "proof",\n'
            '    "solution_steps": ["From the definition of uniform acceleration, velocity at time t is v = u + at.",'
            ' "Displacement s = average velocity x time = ((u + v) / 2) x t.",'
            ' "Substitute v = u + at: s = ((u + u + at) / 2) x t = ((2u + at) / 2) x t.",'
            ' "Expand: s = ut + (1/2)at^2."],\n'
            '    "final_answer": "s = ut + (1/2)at^2",\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _MAP = {
            QuestionType.MCQ: _MCQ_EX,
            QuestionType.WORD: _WORD_EX,
            QuestionType.NON_WORD: _NON_WORD_EX,
            QuestionType.PROOF: _PROOF_EX,
        }
        return ',\n'.join(_MAP[t] for t in types)


_PHYSICS_HANDLER = _PhysicsHandler()
