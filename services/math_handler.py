"""Prompt handler tuned for Mathematics worksheets."""

from services.base_handler import QuestionType, _SubjectHandler

_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.MCQ: 'MCQ (multiple-choice)',
    QuestionType.WORD: 'Word Problem',
    QuestionType.NON_WORD: 'Non-Word Problem',
    QuestionType.PROOF: 'Proof / Construction',
}

_TYPE_DESCRIPTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        'multiple-choice with exactly 4 lettered choices (A, B, C, D); '
        'one correct answer and three plausible-but-wrong distractors; '
        'stems may be either computational/formula-based OR word-problem/narrative — '
        'aim for a roughly even mix of both styles across all MCQ questions.'
    ),
    QuestionType.WORD: (
        'real-world application with a narrative context '
        '(e.g. distance/rate/time, area of a room, sharing money); open answer — no choices.'
    ),
    QuestionType.NON_WORD: (
        'direct computation or formula-based, no narrative '
        '(e.g. "Solve: 2x + 3 = 9" or "Evaluate: 3^2 + 4^2"); open answer — no choices.'
    ),
    QuestionType.PROOF: (
        'a "Show that\u2026" or "Prove that\u2026" statement requiring a step-by-step geometric or '
        'algebraic proof; OR a compass-and-ruler construction with precise steps. '
        'Set needs_diagram: true for constructions, false for written proofs.'
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
                'e.g. ["A) 3", "B) 6", "C) 9", "D) 12"]. '
                'Omit this key for non-MCQ questions.\n'
                '  "correct_choice" \u2014 (MCQ only) letter of the correct answer: '
                '"A", "B", "C", or "D". Omit this key for non-MCQ questions.\n'
            )
        else:
            choices_schema = ''

        topic_text = topic[:3000] if compact else topic

        return (
            f'You are an experienced math teacher creating a printed practice worksheet.\n\n'
            f'Content and style reference:\n{topic_text}\n\n'
            f'If the content above includes a "\u2500\u2500 Sample problems from source \u2500\u2500" section, '
            f'generate questions that CLOSELY MATCH the style, real-world contexts, and problem '
            f'types shown in those samples \u2014 same structural patterns and variety, but with '
            f'different numbers and scenarios. Cover the FULL RANGE of problem types shown, '
            f'not just the simplest ones. Problems labelled "[From the middle of the chapter]" '
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
            f'Do NOT reference "the image", "the figure", "the graph shown", "the diagram", '
            f'"the table above", "the textbook", or any external visual material.\n'
            f'2. Students will receive a plain printed sheet. '
            f'If a problem involves a coordinate plane, describe all points and coordinates '
            f'directly in the question text (e.g. "Plot the points A(2,3), B(-1,4) and find..."). '
            f'A blank coordinate grid will be printed below questions that need one. '
            f'IMPORTANT: geometry problems about circles, triangles, angles, or other shapes '
            f'do NOT need a coordinate grid unless the explicit task is to plot specific '
            f'coordinate pairs on Cartesian axes. Circle problems should use the "figure" '
            f'field instead \u2014 never needs_grid for circle problems.\n'
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
            f'  "needs_grid"     \u2014 true ONLY if the student must plot specific coordinate pairs '
            f'on a Cartesian (x-y) axis as part of the answer '
            f'(e.g. "plot A(2,3) and B(-1,4)"); '
            f'false for all geometry problems about shapes, circles, angles, constructions, '
            f'or any problem that does not explicitly require plotting on coordinate axes; '
            f'always false for MCQ.\n'
            f'  "needs_diagram"  \u2014 true only if the student must physically construct a '
            f'geometric figure themselves (compass-and-ruler); '
            f'false when a "figure" is already provided; always false for MCQ.\n'
            f'  "diagram_label"  \u2014 caption for the blank drawing box when needs_diagram is true; '
            f'empty string "" otherwise.\n'
            + (
                '  "figure"         \u2014 always null for this generation mode.\n'
                if compact else
                '  "figure"         \u2014 a JSON object that prints a diagram automatically for geometry questions;\n'
                '    null for MCQ, word/algebra problems, and anything that does not need a drawn figure.\n'
                '    Choose the right shape:\n'
                '      "circle"       \u2014 circle with centre/points/chords/angle arcs.\n'
                f'        {{"shape":"circle","center":"O","points":[{{"label":"A","angle_deg":150}},{{"label":"B","angle_deg":30}}],\n'
                f'         "segments":[["O","A"],["O","B"],["A","B"]],'
                f'"angle_arcs":[{{"vertex":"O","from_point":"A","to_point":"B","label":"120\u00b0"}}],\n'
                f'         "segment_labels":[{{"on":["O","A"],"text":"10 cm"}}]}}\n'
                "        angle_deg: 0=right/3-o'clock, increases CCW; "
                'for central angle X\u00b0 place points at (90+X/2)\u00b0 and (90-X/2)\u00b0.\n'
                '      "triangle" / "right_triangle"  \u2014 provide actual-value x,y coords.\n'
                '        Right triangle: right angle at (0,0), legs along +x and +y axes.\n'
                f'        {{"shape":"triangle","vertices":[{{"label":"A","x":0,"y":4}},{{"label":"B","x":0,"y":0}},{{"label":"C","x":3,"y":0}}],\n'
                f'         "sides":[{{"from":"A","to":"B","label":"4 cm"}},{{"from":"B","to":"C","label":"3 cm"}},{{"from":"A","to":"C","label":"5 cm"}}],\n'
                f'         "right_angle_at":"B","angle_labels":[{{"at":"A","label":"53\u00b0"}},{{"at":"C","label":"37\u00b0"}}]}}\n'
                '      "angle"        \u2014 standalone angle with two rays.\n'
                f'        {{"shape":"angle","vertex":"O","ray1_deg":0,"ray2_deg":120,"label":"120\u00b0","point1_label":"A","point2_label":"B"}}\n'
                '      "quadrilateral"\u2014 rectangle, square, parallelogram, trapezoid. Use actual dimensions as coords.\n'
                '        Rectangle: corners at (0,0),(w,0),(w,h),(0,h); include right_angles_at all four.\n'
                f'        {{"shape":"quadrilateral","vertices":[{{"label":"A","x":0,"y":0}},{{"label":"B","x":6,"y":0}},{{"label":"C","x":6,"y":4}},{{"label":"D","x":0,"y":4}}],\n'
                f'         "sides":[{{"from":"A","to":"B","label":"6 cm"}},{{"from":"B","to":"C","label":"4 cm"}},{{"from":"C","to":"D","label":"6 cm"}},{{"from":"D","to":"A","label":"4 cm"}}],\n'
                f'         "right_angles_at":["A","B","C","D"],"diagonals":[],"angle_labels":[]}}\n'
                '      "polygon"      \u2014 any closed polygon with x,y vertex coords and optional side labels.\n'
                '      "number_line"  \u2014 early-grade problems: fractions, integers, inequalities.\n'
                f'        {{"shape":"number_line","min":0,"max":10,"tick_interval":1,\n'
                f'         "marked_points":[{{"value":3,"label":"x","color":"#1565c0"}}],'
                f'"segment":{{"from":3,"to":7,"label":"4 units"}}}}\n'
                '    Set needs_diagram=false whenever figure is provided (diagram already printed).\n'
            )
            + f'\nREQUIRED JSON FORMAT (structural examples only \u2014 '
            f'do NOT copy or reuse these specific problems):\n'
            f'[\n'
            f'{self._json_examples(types, compact=compact)}\n'
            f']'
        )

    def _json_examples(self, types: list[QuestionType], compact: bool = False) -> str:
        """Build the structural JSON examples block for the prompt."""
        examples = []
        for t in types:
            if t == QuestionType.MCQ:
                examples.append(
                    '  {\n'
                    '    "question": "<computational/formula-based OR word-problem/narrative question>",\n'
                    '    "type": "mcq",\n'
                    '    "choices": ["A) <option>", "B) <option>", "C) <option>", "D) <option>"],\n'
                    '    "correct_choice": "<A|B|C|D>",\n'
                    '    "solution_steps": ["<step 1>", "<step 2>"],\n'
                    '    "final_answer": "<letter) full winning option text>",\n'
                    '    "needs_grid": false,\n'
                    '    "needs_diagram": false,\n'
                    '    "diagram_label": "",\n'
                    '    "figure": null\n'
                    '  }'
                )
            elif t == QuestionType.WORD:
                examples.append(
                    '  {\n'
                    '    "question": "<real-world narrative problem>",\n'
                    '    "type": "word",\n'
                    '    "solution_steps": ["<step 1>", "<step 2>", "<step 3>"],\n'
                    '    "final_answer": "<concise answer>",\n'
                    '    "needs_grid": false,\n'
                    '    "needs_diagram": false,\n'
                    '    "diagram_label": "",\n'
                    '    "figure": null\n'
                    '  }'
                )
            elif t == QuestionType.NON_WORD:
                examples.append(
                    '  {\n'
                    '    "question": "Using a ruler and compass only, construct a triangle PQR'
                    ' where PQ = 6 cm, QR = 5 cm, and PR = 4 cm.'
                    ' Then construct the perpendicular bisector of side QR.",\n'
                    '    "type": "non_word",\n'
                    '    "solution_steps": ["Draw line segment PQ = 6 cm.",'
                    ' "With Q as centre radius 5 cm and P as centre radius 4 cm, draw arcs;'
                    ' mark intersection as R.",'
                    ' "To bisect QR: with Q and R as centres and radius > QR/2,'
                    ' draw arcs above and below; join intersections."],\n'
                    '    "final_answer": "Triangle PQR constructed; perpendicular bisector of QR drawn.",\n'
                    '    "needs_grid": false,\n'
                    '    "needs_diagram": true,\n'
                    '    "diagram_label": "Construct triangle PQR and the perpendicular bisector of QR",\n'
                    '    "figure": null\n'
                    '  }'
                )
            elif t == QuestionType.PROOF:
                proof_figure = (
                    'null'
                    if compact else
                    '{"shape": "circle", "center": "O", "points": [{"label": "A", "angle_deg": 180}, {"label": "B", "angle_deg": 0}, {"label": "C", "angle_deg": 90}], "segments": [["A","B"],["O","C"],["A","C"],["B","C"]], "angle_arcs": [{"vertex": "C", "from_point": "A", "to_point": "B", "label": "90\u00b0"}], "segment_labels": []}'
                )
                examples.append(
                    '  {\n'
                    '    "question": "Show that the angle subtended by a diameter of a circle '
                    'at any point on the circle is 90\u00b0.",\n'
                    '    "type": "proof",\n'
                    '    "solution_steps": ['
                    '"Let O be the centre of the circle, AB be the diameter, and C be any point on the circle.",'
                    ' "Join OC. Since OA = OB = OC (radii), triangles OAC and OBC are isosceles.",'
                    ' "Let angle OCA = x and angle OCB = y; the equal base angles give angle OAC = x and angle OBC = y.",'
                    ' "Angles in triangle ABC sum to 180\u00b0: x + y + (x + y) = 180\u00b0, so x + y = 90\u00b0.",'
                    ' "Therefore angle ACB = 90\u00b0."],\n'
                    '    "final_answer": "Angle ACB = 90\u00b0 (angle in a semicircle)",\n'
                    '    "needs_grid": false,\n'
                    '    "needs_diagram": false,\n'
                    '    "diagram_label": "",\n'
                    f'    "figure": {proof_figure}\n'
                    '  }'
                )
        return ",\n".join(examples)


_MATH_HANDLER = _MathHandler()
