"""PDF generation: student worksheet and teacher answer key."""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

from fpdf import FPDF

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Layout constants (A4 portrait, mm)
PAGE_W = 210
MARGIN = 20
CONTENT_W = PAGE_W - 2 * MARGIN   # 170 mm
HALF_W = CONTENT_W / 2            # 85 mm
LINE_H = 7

# Coordinate grid constants
_GRID_RANGE = 6                          # axis runs from -6 to +6
_GRID_CELL  = 7.5                        # mm per unit
_GRID_SIZE  = 2 * _GRID_RANGE * _GRID_CELL   # 90 mm total

# Blank diagram box constants
_DIAGRAM_BOX_H = 55                      # mm — height of blank drawing area

# ---------------------------------------------------------------------------
# Public header data-class (imported by ui/header_options_dialog.py)
# ---------------------------------------------------------------------------
@dataclass
class WorksheetHeader:
    """User-configurable header options that are printed on the first page."""
    title: str = 'Worksheet'
    title_font_size: int = 20
    grade: str = ''          # pre-filled class / grade text; blank → show underline
    show_name_line: bool = True
    show_marks_line: bool = False
    total_marks: int = 20


# Per-subject worksheet titles
_SUBJECT_TITLE: dict[str, str] = {
    'Mathematics': 'Mathematics Worksheet',
    'Physics':     'Physics Worksheet',
    'Chemistry':   'Chemistry Worksheet',
    'Biology':     'Biology Worksheet',
}


# ---------------------------------------------------------------------------
# Text sanitisation — Helvetica is Latin-1; replace common math unicode
# ---------------------------------------------------------------------------
_REPLACEMENTS = {
    '\u00b2': '^2',   # ²
    '\u00b3': '^3',   # ³
    '\u2074': '^4',   # ⁴
    '\u221a': 'sqrt', # √
    '\u221e': 'inf',  # ∞
    '\u03c0': 'pi',   # π
    '\u2264': '<=',   # ≤
    '\u2265': '>=',   # ≥
    '\u2260': '!=',   # ≠
    '\u2248': '~=',   # ≈
    '\u00f7': '/',    # ÷
    '\u00d7': 'x',    # ×
    '\u00b7': '*',    # ·
    '\u2212': '-',    # −  (minus sign)
    '\u2013': '-',    # –
    '\u2014': '--',   # —
    '\u2019': "'",
    '\u2018': "'",
    '\u201c': '"',
    '\u201d': '"',
}


def _sanitize(text: str) -> str:
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _strip_markdown(text: str) -> str:
    """Remove common markdown markers so text renders cleanly in plain-text PDFs."""
    # Bold+italic: ***text***
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text, flags=re.DOTALL)
    # Bold: **text**
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text, flags=re.DOTALL)
    # Bullet lines: "*   item" at line start -> "- item"
    text = re.sub(r'^\*[ \t]+', '- ', text, flags=re.MULTILINE)
    # Remaining italic: *text*
    text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)
    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _render_topic_block(pdf: 'FPDF', topic: str):
    """Render a markdown-stripped topic description line by line with proper spacing."""
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, 'Topic:', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    for line in _strip_markdown(topic).split('\n'):
        stripped = line.rstrip()
        if not stripped:
            pdf.ln(2)   # blank line between paragraphs
        elif stripped.startswith('- '):
            pdf.set_x(MARGIN + 4)
            pdf.multi_cell(CONTENT_W - 4, 4.5, _sanitize(stripped), align='L', new_x='LMARGIN')
        else:
            pdf.multi_cell(0, 4.5, _sanitize(stripped), align='L', new_x='LMARGIN')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

def _draw_coordinate_grid(pdf: FPDF):
    """Draw a blank Cartesian coordinate plane (-6 to +6) for students to work on."""
    needed = _GRID_SIZE + 18   # grid height + axis labels + padding
    if pdf.get_y() + needed > pdf.h - MARGIN:
        pdf.add_page()

    y0 = pdf.get_y() + 4
    x0 = MARGIN + (CONTENT_W - _GRID_SIZE) / 2   # horizontally centred
    ox = x0 + _GRID_RANGE * _GRID_CELL            # x-pixel of origin
    oy = y0 + _GRID_RANGE * _GRID_CELL            # y-pixel of origin

    # Background grid lines
    pdf.set_draw_color(210, 210, 210)
    pdf.set_line_width(0.2)
    for i in range(2 * _GRID_RANGE + 1):
        gx = x0 + i * _GRID_CELL
        gy = y0 + i * _GRID_CELL
        pdf.line(gx, y0, gx, y0 + _GRID_SIZE)
        pdf.line(x0, gy, x0 + _GRID_SIZE, gy)

    # Axes
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.7)
    pdf.line(x0, oy, x0 + _GRID_SIZE, oy)   # x-axis
    pdf.line(ox, y0, ox, y0 + _GRID_SIZE)   # y-axis

    # Arrowheads
    pdf.set_line_width(0.5)
    pdf.line(x0 + _GRID_SIZE,     oy, x0 + _GRID_SIZE - 2.5, oy - 1.2)
    pdf.line(x0 + _GRID_SIZE,     oy, x0 + _GRID_SIZE - 2.5, oy + 1.2)
    pdf.line(ox, y0,     ox - 1.2, y0 + 2.5)
    pdf.line(ox, y0,     ox + 1.2, y0 + 2.5)

    # Tick labels every 2 units (skip 0)
    pdf.set_font('Helvetica', '', 6)
    pdf.set_text_color(60, 60, 60)
    for v in range(-_GRID_RANGE, _GRID_RANGE + 1, 2):
        if v == 0:
            continue
        lx = x0 + (_GRID_RANGE + v) * _GRID_CELL
        pdf.set_xy(lx - 3, oy + 2)
        pdf.cell(6, 3, str(v), align='C')
        ly = y0 + (_GRID_RANGE - v) * _GRID_CELL
        pdf.set_xy(ox - 9, ly - 1.5)
        pdf.cell(7, 3, str(v), align='R')

    # Origin label
    pdf.set_xy(ox - 5, oy + 2)
    pdf.cell(4, 3, '0', align='R')

    # Axis letter labels
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(x0 + _GRID_SIZE + 1.5, oy - 3)
    pdf.cell(5, 6, 'x')
    pdf.set_xy(ox + 1.5, y0 - 5)
    pdf.cell(5, 5, 'y')

    # Reset state and advance cursor below the grid
    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(MARGIN, y0 + _GRID_SIZE + 8)


def _draw_diagram_space(pdf: FPDF, label: str = 'Draw your diagram here'):
    """Draw a labelled blank box for student diagram work (free body diagram, geometric construction, etc.)."""
    needed = _DIAGRAM_BOX_H + 14
    if pdf.get_y() + needed > pdf.h - MARGIN:
        pdf.add_page()

    y0 = pdf.get_y() + 4

    # Dashed border rectangle
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    pdf.set_dash_pattern(dash=2, gap=2)
    pdf.rect(MARGIN, y0, CONTENT_W, _DIAGRAM_BOX_H)
    pdf.set_dash_pattern()

    # Caption label centred below the box
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(130, 130, 130)
    pdf.set_xy(MARGIN, y0 + _DIAGRAM_BOX_H + 2)
    pdf.cell(CONTENT_W, 5, _sanitize(label), align='C', new_x='LMARGIN', new_y='NEXT')

    # Reset drawing state and advance cursor
    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _embed_figure(pdf: FPDF, figure: dict) -> None:
    """Render *figure* with matplotlib and embed the PNG into the PDF."""  # noqa: E501
    from utils.figure_renderer import render_figure, _FIG_H, _FIG_W, _NL_H, _NL_W
    tmp = render_figure(figure)
    if tmp is None:
        return
    try:
        shape = figure.get('shape') or figure.get('type', '')
        # Aspect ratio from matplotlib figsize constants
        h_ratio = _NL_H / _NL_W if shape == 'number_line' else _FIG_H / _FIG_W
        fig_w = CONTENT_W * 0.62             # ~105 mm, centred on content
        fig_h = fig_w * h_ratio
        x = MARGIN + (CONTENT_W - fig_w) / 2
        if pdf.get_y() + fig_h + 8 > pdf.h - MARGIN:
            pdf.add_page()
        y_start = pdf.get_y()
        pdf.image(tmp, x=x, y=y_start, w=fig_w)
        pdf.set_xy(MARGIN, y_start + fig_h + 4)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# MCQ rendering helpers
# ---------------------------------------------------------------------------

def _render_mcq_choices_student(pdf: FPDF, choices: list):
    """Render four MCQ choices for the student sheet (no highlighting)."""
    pdf.set_font('Helvetica', '', 11)
    for choice in choices:
        pdf.set_x(MARGIN + 10)
        pdf.multi_cell(CONTENT_W - 10, LINE_H, _sanitize(str(choice)), align='L', new_x='LMARGIN')
    pdf.ln(2)


def _render_mcq_choices_teacher(pdf: FPDF, choices: list, correct_choice: str):
    """Render four MCQ choices for the teacher copy, highlighting the correct one in green."""
    correct = correct_choice.strip().upper() if correct_choice else ''
    for choice in choices:
        text = str(choice)
        letter = text[0].upper() if text else ''
        is_correct = letter == correct
        if is_correct:
            pdf.set_fill_color(220, 245, 220)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_x(MARGIN + 4)
            pdf.multi_cell(
                CONTENT_W - 4, LINE_H,
                _sanitize(f'\u2713  {text}'),
                align='L', fill=True, new_x='LMARGIN',
            )
            pdf.set_font('Helvetica', '', 10)
        else:
            pdf.set_x(MARGIN + 10)
            pdf.multi_cell(CONTENT_W - 10, LINE_H, _sanitize(f'   {text}'), align='L', new_x='LMARGIN')
    pdf.ln(2)

# ---------------------------------------------------------------------------
# Shared PDF base class
# ---------------------------------------------------------------------------
class _BasePDF(FPDF):
    def __init__(self, header_text: str):
        super().__init__(orientation='P', unit='mm', format='A4')
        self._header_text = header_text
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=MARGIN)

    def header(self):
        # Skip the running header on the first page — the title block serves that role.
        if self.page_no() == 1:
            return
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, _sanitize(self._header_text), align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(200, 200, 200)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, f'Page {self.page_no()}', align='C')
        self.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Student worksheet
# ---------------------------------------------------------------------------
def build_student_pdf(
    questions: list,
    topic: str,
    output_path: str,
    subject: str = 'Mathematics',
    header: WorksheetHeader | None = None,
):
    default_title = _SUBJECT_TITLE.get(subject, f'{subject} Worksheet')
    title      = header.title           if header else default_title
    title_size = header.title_font_size if header else 20

    pdf = _BasePDF(title)
    pdf.add_page()

    # --- Title block ---
    pdf.set_font('Helvetica', 'B', title_size)
    pdf.cell(0, 12, _sanitize(title), align='C', new_x='LMARGIN', new_y='NEXT')

    _render_topic_block(pdf, topic)

    # --- Student info block ---
    pdf.set_font('Helvetica', '', 11)
    if header:
        grade_text = _sanitize(header.grade) if header.grade else None
        if grade_text:
            pdf.cell(0, 8, f'Class / Grade:  {grade_text}', new_x='LMARGIN', new_y='NEXT')
        else:
            pdf.cell(0, 8, 'Class / Grade: ______________________', new_x='LMARGIN', new_y='NEXT')
        if header.show_name_line:
            pdf.cell(0, 8, 'Name: ___________________________', new_x='LMARGIN', new_y='NEXT')
        if header.show_marks_line:
            pdf.cell(0, 8, f'Marks: ________ / {header.total_marks}', new_x='LMARGIN', new_y='NEXT')
    else:
        pdf.cell(0, 8, 'Name: ___________________________', new_x='LMARGIN', new_y='NEXT')
        pdf.cell(0, 8, 'Class: __________________________', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_draw_color(80, 80, 80)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(5)

    # --- Questions ---
    for i, q in enumerate(questions, start=1):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.multi_cell(0, LINE_H, _sanitize(f'Q{i}.  {q["question"]}'), align='L', new_x='LMARGIN')
        pdf.ln(1)

        figure = q.get('figure')
        if q.get('type') == 'mcq':
            _render_mcq_choices_student(pdf, q.get('choices', []))
        elif figure:
            _embed_figure(pdf, figure)
        elif q.get('needs_grid'):
            _draw_coordinate_grid(pdf)
        elif q.get('needs_diagram'):
            _draw_diagram_space(pdf, q.get('diagram_label') or 'Draw your diagram here')
            for _ in range(3):
                y = pdf.get_y() + 6
                pdf.set_draw_color(210, 210, 210)
                pdf.line(MARGIN + 4, y, PAGE_W - MARGIN, y)
                pdf.ln(8)
        else:
            # Blank working lines
            for _ in range(4):
                y = pdf.get_y() + 6
                pdf.set_draw_color(210, 210, 210)
                pdf.line(MARGIN + 4, y, PAGE_W - MARGIN, y)
                pdf.ln(8)
        pdf.ln(2)

    pdf.output(output_path)
    logger.info('Student PDF saved: %s', output_path)


# ---------------------------------------------------------------------------
# Teacher answer key
# ---------------------------------------------------------------------------
def build_teacher_pdf(
    questions: list,
    topic: str,
    output_path: str,
    subject: str = 'Mathematics',
    header: WorksheetHeader | None = None,
):
    default_title = _SUBJECT_TITLE.get(subject, f'{subject} Worksheet')
    title = header.title if header else default_title

    pdf = _BasePDF(f'TEACHER COPY - {_sanitize(title)} - Answer Key')
    pdf.add_page()

    # --- Title block ---
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(180, 0, 0)
    pdf.cell(0, 9, 'TEACHER COPY', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)

    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 11, _sanitize(f'{title} - Full Solutions'), align='C', new_x='LMARGIN', new_y='NEXT')

    _render_topic_block(pdf, topic)

    pdf.set_draw_color(80, 80, 80)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(5)

    # --- Per-question solutions ---
    for i, q in enumerate(questions, start=1):
        # Question
        pdf.set_font('Helvetica', 'B', 11)
        pdf.multi_cell(0, LINE_H, _sanitize(f'Q{i}.  {q["question"]}'), align='L', new_x='LMARGIN')
        pdf.ln(1)

        # MCQ choices (teacher copy shows correct answer highlighted)
        figure = q.get('figure')
        if q.get('type') == 'mcq':
            _render_mcq_choices_teacher(pdf, q.get('choices', []), q.get('correct_choice', ''))
        elif figure:
            _embed_figure(pdf, figure)
        elif q.get('needs_grid'):
            _draw_coordinate_grid(pdf)
            pdf.ln(2)
        elif q.get('needs_diagram'):
            _draw_diagram_space(pdf, q.get('diagram_label') or 'Diagram space')
            pdf.ln(2)

        # Solution steps
        steps = q.get('solution_steps', [])
        if isinstance(steps, str):
            steps = [steps]
        pdf.set_font('Helvetica', '', 10)
        for j, step in enumerate(steps, start=1):
            pdf.set_x(MARGIN + 6)
            pdf.multi_cell(CONTENT_W - 6, LINE_H, _sanitize(f'  Step {j}: {step}'), align='L', new_x='LMARGIN')

        # Final answer (highlighted green)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(220, 245, 220)
        pdf.set_x(MARGIN + 6)
        pdf.multi_cell(
            CONTENT_W - 6, LINE_H,
            _sanitize(f'  Answer: {q.get("final_answer", "")}'),
            align='L', fill=True, new_x='LMARGIN'
        )
        pdf.ln(4)

    # --- Quick answer key (final page) ---
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 12, 'Quick Answer Key', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_draw_color(80, 80, 80)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(5)

    pdf.set_font('Helvetica', '', 11)
    for i, q in enumerate(questions, start=1):
        answer = _sanitize(str(q.get('final_answer', '')))
        pdf.cell(10, LINE_H, f'{i}.', new_x='END', new_y='TOP')
        pdf.multi_cell(CONTENT_W - 10, LINE_H, answer, align='L', new_x='LMARGIN')
        pdf.ln(1)

    pdf.output(output_path)
    logger.info('Teacher PDF saved: %s', output_path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_pdfs(
    questions: list,
    topic: str,
    output_dir: str,
    subject: str = 'Mathematics',
    header: WorksheetHeader | None = None,
) -> tuple:
    """Generate both PDFs. Returns (student_path, teacher_path)."""
    os.makedirs(output_dir, exist_ok=True)

    date_tag = datetime.now().strftime('%Y-%m-%d_%H%M')
    safe_topic = (
        ''.join(c for c in topic[:30] if c.isalnum() or c in (' ', '-', '_'))
        .strip().replace(' ', '_')
    )

    student_path = os.path.join(output_dir, f'worksheet_{safe_topic}_{date_tag}.pdf')
    teacher_path = os.path.join(output_dir, f'answers_{safe_topic}_{date_tag}.pdf')

    build_student_pdf(questions, topic, student_path, subject, header)
    build_teacher_pdf(questions, topic, teacher_path, subject, header)

    return student_path, teacher_path
