"""Prompt handler tuned for Chemistry worksheets."""

from services.base_handler import QuestionType, _SubjectHandler

_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.MCQ: 'MCQ (multiple-choice)',
    QuestionType.WORD: 'Application / Descriptive',
    QuestionType.NON_WORD: 'Direct Knowledge',
    QuestionType.PROOF: 'Extended Reasoning',
}

_TYPE_DESCRIPTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        'multiple-choice with exactly 4 lettered choices (A, B, C, D); '
        'one correct answer and three plausible-but-wrong distractors based on common misconceptions; '
        'may test definitions, properties, chemical reactions, or conceptual understanding.'
    ),
    QuestionType.WORD: (
        'application or descriptive question with a real-world or experimental context '
        '(e.g. "Explain why rusting of iron is a chemical change", '
        '"A student adds vinegar to baking soda — what would she observe?"); '
        'requires explanation, reasoning, or multi-step thinking; open answer — no choices.'
    ),
    QuestionType.NON_WORD: (
        'direct knowledge or skill-based question without a narrative context '
        '(e.g. "Define atomic mass", "Write the chemical formula for sodium chloride", '
        '"Balance the equation: Fe + O2 -> Fe2O3", '
        '"State two properties that distinguish a mixture from a compound"); '
        'open answer — no choices.'
    ),
    QuestionType.PROOF: (
        'multi-step reasoning or calculation requiring the student to show or justify '
        'a chemical result (e.g. "Show by calculation that the empirical formula of a compound '
        'containing 40% C, 6.7% H, and 53.3% O is CH2O", '
        '"Justify why the reaction 2H2 + O2 -> 2H2O obeys the law of conservation of mass"); '
        'open answer — no choices.'
    ),
}


def _compute_breakdown(num_questions: int, question_types: list[QuestionType]) -> dict[QuestionType, int]:
    """Distribute num_questions as evenly as possible among the given types."""
    k = len(question_types)
    base = num_questions // k
    rem = num_questions % k
    return {t: base + (1 if i < rem else 0) for i, t in enumerate(question_types)}


class _ChemistryHandler(_SubjectHandler):
    """Prompts tuned for Chemistry worksheets (primarily Class 9)."""

    def summarize_prompt(self, raw_text: str) -> str:
        return (
            'You are helping generate a standalone Chemistry practice worksheet for students. '
            'Below is content extracted from a Chemistry resource. '
            'Identify the chemistry CONCEPTS, SKILLS, and QUESTION TYPES that students would actually practise — '
            'ignore introductory narrative, historical context, biographies, and any non-question text. '
            'Fill in EXACTLY this template — no extra text before or after, no markdown, no bullet symbols:\n\n'
            'Topic: <specific chemistry topic, e.g. "Atoms and Molecules — chemical formulae and atomic mass">\n'
            'Grade level: <approximate grade, e.g. "Grade 9">\n'
            'Problem types: <comma-separated list of practice question types, '
            'e.g. "balancing equations, writing chemical formulae, defining terms, '
            'distinguishing mixtures from compounds">\n'
            'Notation/constraints: <specific notation or constraints, '
            'e.g. "use standard chemical symbols; IUPAC nomenclature where applicable">\n\n'
            'RULES: '
            'Do NOT mention textbook names, book titles, chapter numbers, page numbers, '
            'image numbers, historical figures, or any source references. '
            'Every field must be filled; write "Standard chemical notation" if no special constraints apply.\n\n'
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
            f'Below is text extracted from a Chemistry textbook or worksheet.{segment_note}\n'
            'Find 2 to 3 ACTUAL EXERCISE QUESTIONS from the text — questions students are asked to answer. '
            'Select questions that show VARIETY: '
            'include definitional questions, application/reasoning questions, '
            'equation-balancing tasks, and "give examples" or "differentiate" questions if present. '
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
                'e.g. ["A) Ionic bond", "B) Covalent bond", "C) Metallic bond", "D) Hydrogen bond"]. '
                'Omit this key for non-MCQ questions.\n'
                '  "correct_choice" \u2014 (MCQ only) letter of the correct answer: '
                '"A", "B", "C", or "D". Omit this key for non-MCQ questions.\n'
            )
        else:
            choices_schema = ''

        return (
            f'You are an experienced Chemistry teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" section, '
            f'generate questions that CLOSELY MATCH the style, real-world contexts, and question '
            f'types shown in those samples \u2014 same structural patterns and variety, but with '
            f'different scenarios or values. Cover the FULL RANGE of question types shown, '
            f'not just the simplest definitional ones. Questions labelled "[From the middle of the chapter]" '
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
            f'"the table", "the textbook", or any external visual material.\n'
            f'2. Use standard plain-text chemical notation '
            f'(e.g. H2O, CO2, NaCl, Fe2O3, Ca(OH)2). '
            f'Write subscripts as plain numbers (H2O not H\u2082O). '
            f'Use "->" for reaction arrows (e.g. 2H2 + O2 -> 2H2O).\n'
            f'3. MCQ distractors must be plausible (e.g. common student misconceptions) '
            f'but unambiguously wrong.\n'
            f'4. For balancing-equation questions, provide the unbalanced equation in the question '
            f'and the balanced equation as the final answer.\n'
            f'5. solution_steps must explain the reasoning clearly \u2014 '
            f'not just restate the answer. For definitions, give the key points. '
            f'For equations, show the balancing steps.\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the question statement following the rules above.\n'
            f'  "type"           \u2014 one of: {type_values}.\n'
            f'{choices_schema}'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step (minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer '
            f'(for MCQ: include the full winning option text, e.g. "B) NaCl").\n'
            f'  "needs_diagram"  \u2014 false (always false for chemistry).\n\n'
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
            '    "question": "Which of the following is a chemical change?",\n'
            '    "type": "mcq",\n'
            '    "choices": ["A) Melting of ice", "B) Dissolving sugar in water",'
            ' "C) Burning of wood", "D) Cutting of paper"],\n'
            '    "correct_choice": "C",\n'
            '    "solution_steps": ["A chemical change produces new substances.'
            ' Burning wood produces CO2 and H2O -- new substances.",'
            ' "Melting, dissolving, and cutting are physical changes."],\n'
            '    "final_answer": "C) Burning of wood",\n'
            '    "needs_diagram": false\n'
            '  }'
        )
        _WORD_EX = (
            '  {\n'
            '    "question": "A student heats a blue copper sulphate crystal.'
            ' The solid turns white and water droplets appear on cooler parts of the tube.'
            ' Explain what type of change has occurred and justify your answer.",\n'
            '    "type": "word",\n'
            '    "solution_steps": ["Heating removes the water of crystallisation from CuSO4.5H2O,'
            ' giving white anhydrous CuSO4.", "Since the original substance is regenerated on adding'
            ' water, this is a reversible physical change."],\n'
            '    "final_answer": "Physical change (loss of water of crystallisation),'
            ' reversible because adding water restores blue CuSO4.5H2O.",\n'
            '    "needs_diagram": false\n'
            '  }'
        )
        _NON_WORD_EX = (
            '  {\n'
            '    "question": "Balance the following chemical equation: Fe + O2 -> Fe2O3",\n'
            '    "type": "non_word",\n'
            '    "solution_steps": ["Count atoms: Left 1 Fe, 2 O; Right 2 Fe, 3 O.",'
            ' "Place coefficients: 4Fe + 3O2 -> 2Fe2O3. Verify: 4 Fe and 6 O each side."],\n'
            '    "final_answer": "4Fe + 3O2 -> 2Fe2O3",\n'
            '    "needs_diagram": false\n'
            '  }'
        )
        _PROOF_EX = (
            '  {\n'
            '    "question": "A compound contains 40% carbon, 6.7% hydrogen, and 53.3% oxygen by mass.'
            ' Show by calculation that its empirical formula is CH2O.",\n'
            '    "type": "proof",\n'
            '    "solution_steps": ["Assume 100 g sample: C = 40 g, H = 6.7 g, O = 53.3 g.",'
            ' "Moles: C = 40/12 = 3.33, H = 6.7/1 = 6.7, O = 53.3/16 = 3.33.",'
            ' "Divide by smallest (3.33): C = 1, H = 2, O = 1.",'
            ' "Empirical formula = CH2O."],\n'
            '    "final_answer": "CH2O",\n'
            '    "needs_diagram": false\n'
            '  }'
        )
        _MAP = {
            QuestionType.MCQ: _MCQ_EX,
            QuestionType.WORD: _WORD_EX,
            QuestionType.NON_WORD: _NON_WORD_EX,
            QuestionType.PROOF: _PROOF_EX,
        }
        return ',\n'.join(_MAP[t] for t in types if t in _MAP)


_CHEMISTRY_HANDLER = _ChemistryHandler()
