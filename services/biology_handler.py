"""Prompt handler tuned for Biology worksheets (Grade 7 and above).

Biology is primarily memory and comprehension based — no computation or
logical-derivation questions.  All generated questions must match the style
and phrasing of standard curriculum exam papers and school worksheets.
"""

from services.base_handler import QuestionType, _SubjectHandler

_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.MCQ:      'MCQ (Multiple-Choice)',
    QuestionType.WORD:     'Application / Descriptive',
    QuestionType.NON_WORD: 'Define / Identify / List',
    QuestionType.PROOF:    'Extended Answer',
}

_TYPE_DESCRIPTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        'multiple-choice with exactly 4 lettered choices (A, B, C, D); '
        'one correct answer and three plausible-but-wrong distractors based on common '
        'student misconceptions or easily confused terms; '
        'may test definitions, classification, naming structures, or understanding '
        'of biological processes.'
    ),
    QuestionType.WORD: (
        'application or descriptive question requiring the student to explain a '
        'biological process, give a real-world example, or describe an observation '
        '(e.g. "Explain why a piece of potato placed in a concentrated salt solution '
        'becomes soft and limp", '
        '"Describe one way in which the structure of a red blood cell is adapted to '
        'its function"); '
        'open answer — no choices.'
    ),
    QuestionType.NON_WORD: (
        'direct recall or identification question without a narrative context '
        '(e.g. "Define osmosis", "Name the four chambers of the human heart", '
        '"State two functions of the liver", '
        '"List the levels of biological organisation from cell to organism in the '
        'correct order"); '
        'open answer — no choices.'
    ),
    QuestionType.PROOF: (
        'extended answer requiring the student to compare, contrast, sequence steps, '
        'or describe a complete biological process '
        '(e.g. "Compare and contrast aerobic and anaerobic respiration in terms of '
        'reactants, products and energy released", '
        '"Describe the stages of mitosis in the correct order with what happens to '
        'chromosomes at each stage", '
        '"Explain how the structure of a villus is adapted for efficient absorption ")'
        '; open answer — no choices.'
    ),
}


def _compute_breakdown(num_questions: int, question_types: list[QuestionType]) -> dict[QuestionType, int]:
    """Distribute num_questions as evenly as possible among the given types."""
    k = len(question_types)
    base = num_questions // k
    rem = num_questions % k
    return {t: base + (1 if i < rem else 0) for i, t in enumerate(question_types)}


class _BiologyHandler(_SubjectHandler):
    """Prompts tuned for Biology worksheets (Grade 7+)."""

    def summarize_prompt(self, raw_text: str) -> str:
        return (
            'You are helping generate a standalone Biology practice worksheet for students. '
            'Below is content extracted from a Biology resource. '
            'Identify the biology CONCEPTS, ORGANISMS, PROCESSES, and STRUCTURES '
            'that students would be tested on — ignore introductory narrative, '
            'historical context, biographies, and non-question text. '
            'Fill in EXACTLY this template — no extra text before or after, no markdown, '
            'no bullet symbols:\n\n'
            'Topic: <specific biology topic, e.g. '
            '"Cell Biology — structure and functions of plant and animal cells">\n'
            'Grade level: <approximate grade, e.g. "Grade 9">\n'
            'Problem types: <comma-separated list of practice question types, '
            'e.g. "defining terms, naming structures, describing processes, '
            'comparing cell types, explaining adaptations">\n'
            'Notation/constraints: <specific notation or constraints, '
            'e.g. "use standard biological terminology; include both plant and animal '
            'cell comparisons">\n\n'
            'RULES: '
            'Do NOT mention textbook names, book titles, chapter numbers, page numbers, '
            'image numbers, historical figures, or any source references. '
            'Every field must be filled; write "Standard biological terminology" '
            'if no special constraints apply.\n\n'
            f'Content:\n{raw_text[:4000]}'
        )

    def style_examples_prompt(self, raw_text: str, segment_label: str = '') -> str:
        segment_note = (
            f' This excerpt is from the **{segment_label}** of the chapter,'
            ' so the questions here are likely more representative of the'
            " chapter's difficulty than the opening introductory examples."
            if segment_label and segment_label != 'beginning'
            else ''
        )
        return (
            f'Below is text extracted from a Biology textbook or worksheet.{segment_note}\n'
            'Find 2 to 3 ACTUAL EXERCISE QUESTIONS from the text — questions students are '
            'asked to answer. '
            'Select questions that show VARIETY: '
            'include definition/recall questions, process-description questions, '
            'comparison questions, and application/example questions if present. '
            'Prefer questions that test understanding over trivial one-word recall.\n\n'
            'Return ONLY a numbered list of the questions, copied VERBATIM from the source. '
            'Do NOT rewrite, summarise, or add any explanation. '
            'If the text contains no exercise questions, return exactly the word: NONE\n\n'
            f'Text:\n{raw_text[:6000]}'
        )

    def generate_prompt(
        self,
        topic: str,
        difficulty: str,
        guidance: str,
        num_questions: int,
        question_types: list[QuestionType] | None = None,
        grade: str = '',
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
                'e.g. ["A) Mitochondria", "B) Nucleus", "C) Ribosome", "D) Vacuole"]. '
                'Omit this key for non-MCQ questions.\n'
                '  "correct_choice" \u2014 (MCQ only) letter of the correct answer: '
                '"A", "B", "C", or "D". Omit this key for non-MCQ questions.\n'
            )
        else:
            choices_schema = ''

        topic_text = topic[:3000] if compact else topic

        return (
            f'You are an experienced Biology teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic_text}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" '
            f'section, generate questions that CLOSELY MATCH the style and question types shown '
            f'in those samples \u2014 same structural patterns and variety, but covering different '
            f'aspects of the topic. Questions labelled "[From the middle of the chapter]" or '
            f'"[From the end of the chapter]" represent the intended difficulty level; weight '
            f'your generated questions accordingly.\n\n'
            f'Difficulty: {difficulty} \u2014 {guidance}\n'
            f'{f"Grade level: {grade}" + chr(10) if grade else ""}'
            f'\n'
            f'QUESTION TYPE BREAKDOWN \u2014 generate exactly {num_questions} questions total, '
            f'distributed throughout the array:\n'
            f'{type_lines}\n\n'
            f'BIOLOGY-SPECIFIC RULES:\n'
            f'1. SOURCE FIDELITY \u2014 Every question must be the type of factual, '
            f'curriculum-standard biology question that appears verbatim on standard school '
            f'exam papers, past papers, and biology worksheets widely available online. '
            f'Draw exclusively on well-established, universally accepted biological facts, '
            f'named processes, named structures, and standard terminology. '
            f'Do NOT invent novel scenarios, creative analogies, or logical puzzles. '
            f'If in doubt, ask yourself: "Would this exact question appear in a GCSE, '
            f'CBSE, or equivalent biology paper?" \u2014 if yes, include it.\n'
            f'2. SELF-CONTAINED \u2014 Every question must be 100% self-contained. '
            f'Do NOT reference "the diagram", "the image above", "the table", '
            f'"the textbook", or any external material.\n'
            f'3. TERMINOLOGY \u2014 Use correct biological terminology throughout '
            f'(e.g. "mitochondria" not "powerhouse", "semi-permeable membrane" not '
            f'"special membrane"). For MCQ distractors, use plausible biology '
            f'misconceptions or commonly confused terms or structures.\n'
            f'4. SOLUTION STEPS \u2014 Show clear factual reasoning: state the relevant '
            f'biology fact or definition, apply it to the question, then give the answer. '
            f'Minimum 2 steps.\n'
            f'5. DIAGRAMS \u2014 Set needs_diagram to true ONLY when the expected student '
            f'response is to draw and label a biological diagram '
            f'(e.g. a plant cell, a leaf cross-section, a neuron, a food chain). '
            f'For descriptive, recall, or MCQ questions, needs_diagram must be false.\n'
            f'6. NO MATHS \u2014 Biology questions never require coordinate grids or '
            f'mathematical computation. needs_grid is always false.\n\n'
            f'IMPORTANT: Return ONLY a valid JSON array \u2014 no markdown, no code fences, '
            f'no explanatory text before or after.\n\n'
            f'Each object in the array must have exactly these keys:\n'
            f'  "question"       \u2014 the question statement.\n'
            f'  "type"           \u2014 one of: {type_values}.\n'
            f'{choices_schema}'
            f'  "solution_steps" \u2014 a JSON array of strings, one string per step '
            f'(minimum 2 steps).\n'
            f'  "final_answer"   \u2014 the concise final answer '
            f'(for MCQ: include the full winning option text, e.g. "C) Mitochondria").\n'
            f'  "needs_grid"     \u2014 always false for Biology.\n'
            f'  "needs_diagram"  \u2014 true only if the student must draw and label a '
            f'biological diagram as part of the answer; false for all other questions '
            f'(always false for MCQ).\n'
            f'  "diagram_label"  \u2014 a short caption for the blank drawing box when '
            f'needs_diagram is true (e.g. "Draw and label a plant cell"); '
            f'use an empty string "" when needs_diagram is false.\n\n'
            f'REQUIRED JSON FORMAT (structural examples only \u2014 '
            f'do NOT copy or reuse these specific questions):\n'
            f'[\n'
            f'{self._json_examples(types)}\n'
            f']'
        )

    def _json_examples(self, types: list[QuestionType]) -> str:
        _MCQ_EX = (
            '  {\n'
            '    "question": "Which organelle is the site of aerobic respiration in a cell?",\n'
            '    "type": "mcq",\n'
            '    "choices": ["A) Nucleus", "B) Ribosome", "C) Mitochondria", "D) Chloroplast"],\n'
            '    "correct_choice": "C",\n'
            '    "solution_steps": [\n'
            '      "Recall: aerobic respiration produces ATP and takes place in the mitochondria.",\n'
            '      "The nucleus contains genetic material; ribosomes synthesise proteins; '
            'chloroplasts are the site of photosynthesis in plant cells only."\n'
            '    ],\n'
            '    "final_answer": "C) Mitochondria",\n'
            '    "needs_grid": false,\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _WORD_EX = (
            '  {\n'
            '    "question": "Explain why a piece of potato placed in a concentrated salt '
            'solution will become soft and limp.",\n'
            '    "type": "word",\n'
            '    "solution_steps": [\n'
            '      "The salt solution has a lower water potential than the potato cells.",\n'
            '      "By osmosis, water moves out of the potato cells (higher water potential) '
            'into the salt solution (lower water potential) through the partially permeable '
            'cell membrane.",\n'
            '      "Loss of water causes the cells to become flaccid, making the potato soft '
            'and limp."\n'
            '    ],\n'
            '    "final_answer": "Water moves out of the potato cells by osmosis into the salt '
            'solution, causing the cells to become flaccid and the potato to go soft and limp.",\n'
            '    "needs_grid": false,\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _NON_WORD_EX = (
            '  {\n'
            '    "question": "State two structural differences between a plant cell and an '
            'animal cell.",\n'
            '    "type": "non_word",\n'
            '    "solution_steps": [\n'
            '      "Identify features present in plant cells but absent in animal cells.",\n'
            '      "Plant cells have: (1) a cell wall made of cellulose; '
            '(2) a large permanent vacuole; (3) chloroplasts (in green parts). '
            'Animal cells have none of these."\n'
            '    ],\n'
            '    "final_answer": '
            '"1. Plant cells have a cell wall; animal cells do not. '
            '2. Plant cells have a large permanent vacuole; animal cells do not.",\n'
            '    "needs_grid": false,\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _PROOF_EX = (
            '  {\n'
            '    "question": "Compare and contrast aerobic respiration and anaerobic '
            'respiration in terms of: (a) reactants used, (b) products formed, and '
            '(c) amount of energy released.",\n'
            '    "type": "proof",\n'
            '    "solution_steps": [\n'
            '      "(a) Reactants: both use glucose as the substrate. Aerobic respiration '
            'also requires oxygen; anaerobic respiration does not.",\n'
            '      "(b) Products: aerobic respiration produces carbon dioxide and water. '
            'Anaerobic respiration in animals produces lactic acid; in yeast it produces '
            'ethanol and carbon dioxide.",\n'
            '      "(c) Energy: aerobic respiration releases approximately 38 ATP per glucose '
            'molecule; anaerobic respiration releases only 2 ATP per glucose molecule."\n'
            '    ],\n'
            '    "final_answer": '
            '"Aerobic: glucose + O2 -> CO2 + H2O + ~38 ATP. '
            'Anaerobic (animals): glucose -> lactic acid + 2 ATP. '
            'Anaerobic (yeast): glucose -> ethanol + CO2 + 2 ATP.",\n'
            '    "needs_grid": false,\n'
            '    "needs_diagram": false,\n'
            '    "diagram_label": ""\n'
            '  }'
        )
        _MAP = {
            QuestionType.MCQ:      _MCQ_EX,
            QuestionType.WORD:     _WORD_EX,
            QuestionType.NON_WORD: _NON_WORD_EX,
            QuestionType.PROOF:    _PROOF_EX,
        }
        return ',\n'.join(_MAP[t] for t in types)


_BIOLOGY_HANDLER = _BiologyHandler()
