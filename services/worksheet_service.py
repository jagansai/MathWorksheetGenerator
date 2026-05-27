"""QThread workers that orchestrate image analysis and worksheet generation."""
import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from services.ai_service import AIService
from services.base_handler import QuestionType
from utils.pdf_generator import generate_pdfs
from utils.logger import setup_logger

if TYPE_CHECKING:
    from utils.config_manager import ConfigManager

logger = setup_logger(__name__)

def _combine_content(topic: str, examples: str) -> str:
    """Merge the topic summary and style examples into a single string for the UI and AI."""
    if not examples.strip():
        return topic
    return f'{topic}\n\n\u2500\u2500 Sample problems from source \u2500\u2500\n{examples}'


class ImageAnalysisWorker(QThread):
    """Extracts content from images via the vision model, then summarizes to a topic description."""

    finished = pyqtSignal(str)   # topic description
    error = pyqtSignal(str)      # error message

    def __init__(self, ai_service: AIService, image_paths: list[str], subject: str = 'Mathematics'):
        super().__init__()
        self._ai = ai_service
        self._image_paths = image_paths
        self._subject = subject

    def run(self):
        try:
            result = asyncio.run(self._analyze())
            self.finished.emit(result)
        except Exception as e:
            logger.error('Image analysis failed: %s', e)
            self.error.emit(str(e))

    async def _analyze(self) -> str:
        raw = await self._ai.extract_from_images(self._image_paths)
        topic, examples = await asyncio.gather(
            self._ai.summarize_topic(raw, self._subject),
            self._ai.extract_style_examples(raw, self._subject),
        )
        return _combine_content(topic, examples)


class PDFAnalysisWorker(QThread):
    """Extracts text from one or more PDFs via pdfplumber, then summarizes to a topic description."""

    finished = pyqtSignal(str)   # topic description
    error = pyqtSignal(str)      # error message

    def __init__(
        self,
        ai_service: AIService,
        pdf_paths: list[str],
        config_manager: 'ConfigManager',
        subject: str = 'Mathematics',
        page_ranges: dict[str, tuple[int, int]] | None = None,
    ):
        super().__init__()
        self._ai = ai_service
        self._pdf_paths = pdf_paths
        self._config = config_manager
        self._subject = subject
        self._page_ranges: dict[str, tuple[int, int]] = page_ranges or {}

    def run(self):
        try:
            result = asyncio.run(self._analyze())
            self.finished.emit(result)
        except Exception as e:
            logger.error('PDF analysis failed: %s', e)
            self.error.emit(str(e))

    async def _analyze(self) -> str:
        from utils.pdf_reader import extract_text
        texts = []
        for p in self._pdf_paths:
            r = self._page_ranges.get(p)
            start, end = (r[0], r[1]) if r else (1, None)
            texts.append(extract_text(p, start_page=start, end_page=end))
        combined = '\n\n'.join(t for t in texts if t)
        if not combined.strip():
            raise ValueError(
                'No selectable text found in the PDF(s). '
                'Try uploading a scanned image instead.'
            )
        topic, examples = await asyncio.gather(
            self._ai.summarize_topic(combined, self._subject),
            self._ai.extract_style_examples(combined, self._subject),
        )
        return _combine_content(topic, examples)


class WorksheetWorker(QThread):
    """Generates questions via AI and writes both PDFs in a background thread."""

    step_updated = pyqtSignal(str)   # progress message for the progress dialog
    finished = pyqtSignal(str, str)  # (student_pdf_path, teacher_pdf_path)
    error = pyqtSignal(str)          # error message

    def __init__(
        self,
        ai_service: AIService,
        config_manager: 'ConfigManager',
        topic: str,
        difficulty: str,
        num_questions: int,
        output_dir: str,
        subject: str = 'Mathematics',
        question_types: list[QuestionType] | None = None,
        grade: str = '',
    ):
        super().__init__()
        self._ai = ai_service
        self._config = config_manager
        self._topic = topic
        self._difficulty = difficulty
        self._num_questions = num_questions
        self._output_dir = output_dir
        self._subject = subject
        self._question_types = question_types or [QuestionType.NON_WORD]
        self._grade = grade

    def run(self):
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            logger.exception('Worksheet generation failed')
            self.error.emit(str(e))

    async def _run_async(self):
        self.step_updated.emit(
            f'Asking AI to generate {self._num_questions} questions ({self._difficulty})...'
        )
        questions = await self._ai.generate_questions(
            self._topic, self._difficulty, self._num_questions, self._subject, self._question_types,
            self._grade,
        )
        logger.info('Received %d questions from AI', len(questions))

        self.step_updated.emit('Creating PDF files...')
        # Strip the sample-problems block (style reference only — not for the PDF title)
        topic_for_pdf = self._topic.split('\n\n\u2500\u2500 Sample problems from source \u2500\u2500')[0].strip()
        student_path, teacher_path = generate_pdfs(
            questions, topic_for_pdf, self._output_dir, self._subject
        )

        self.finished.emit(student_path, teacher_path)


# ---------------------------------------------------------------------------
# Two-step workers for the review-before-PDF workflow
# ---------------------------------------------------------------------------

class QuestionFetchWorker(QThread):
    """Step 1 — asks the AI for questions and emits them for user review."""

    step_updated = pyqtSignal(str)
    questions_ready = pyqtSignal(list)   # list of question dicts
    error = pyqtSignal(str)

    def __init__(
        self,
        ai_service: AIService,
        config_manager: 'ConfigManager',
        topic: str,
        difficulty: str,
        num_questions: int,
        subject: str = 'Mathematics',
        question_types: list[QuestionType] | None = None,
        grade: str = '',
    ):
        super().__init__()
        self._ai = ai_service
        self._config = config_manager
        self._topic = topic
        self._difficulty = difficulty
        self._num_questions = num_questions
        self._subject = subject
        self._question_types = question_types or [QuestionType.NON_WORD]
        self._grade = grade

    def run(self):
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            logger.exception('Question fetch failed')
            self.error.emit(str(e))

    async def _run_async(self):
        self.step_updated.emit(
            f'Asking AI to generate {self._num_questions} questions ({self._difficulty})...'
        )
        questions = await self._ai.generate_questions(
            self._topic, self._difficulty, self._num_questions,
            self._subject, self._question_types, self._grade,
        )
        logger.info('Received %d questions from AI', len(questions))
        self.questions_ready.emit(questions)


class PDFCreateWorker(QThread):
    """Step 2 — writes PDFs from the user-approved question list."""

    step_updated = pyqtSignal(str)
    finished = pyqtSignal(str, str)   # (student_path, teacher_path)
    error = pyqtSignal(str)

    def __init__(
        self,
        questions: list,
        topic: str,
        output_dir: str,
        subject: str = 'Mathematics',
    ):
        super().__init__()
        self._questions = questions
        self._topic = topic
        self._output_dir = output_dir
        self._subject = subject

    def run(self):
        try:
            self.step_updated.emit('Creating PDF files...')
            student_path, teacher_path = generate_pdfs(
                self._questions, self._topic, self._output_dir, self._subject
            )
            self.finished.emit(student_path, teacher_path)
        except Exception as e:
            logger.exception('PDF creation failed')
            self.error.emit(str(e))
