"""QThread workers that orchestrate image analysis and worksheet generation."""
import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from services.ai_service import AIService
from utils.pdf_generator import generate_pdfs
from utils.logger import setup_logger

if TYPE_CHECKING:
    from utils.config_manager import ConfigManager

logger = setup_logger(__name__)


class ImageAnalysisWorker(QThread):
    """Extracts content from images via the vision model, then summarizes to a topic description."""

    finished = pyqtSignal(str)   # topic description
    error = pyqtSignal(str)      # error message

    def __init__(self, ai_service: AIService, image_paths: list[str]):
        super().__init__()
        self._ai = ai_service
        self._image_paths = image_paths

    def run(self):
        try:
            result = asyncio.run(self._analyze())
            self.finished.emit(result)
        except Exception as e:
            logger.error('Image analysis failed: %s', e)
            self.error.emit(str(e))

    async def _analyze(self) -> str:
        raw = await self._ai.extract_from_images(self._image_paths)
        return await self._ai.summarize_topic(raw)


class PDFAnalysisWorker(QThread):
    """Extracts text from one or more PDFs via pdfplumber, then summarizes to a topic description."""

    finished = pyqtSignal(str)   # topic description
    error = pyqtSignal(str)      # error message

    def __init__(self, ai_service: AIService, pdf_paths: list[str]):
        super().__init__()
        self._ai = ai_service
        self._pdf_paths = pdf_paths

    def run(self):
        try:
            result = asyncio.run(self._analyze())
            self.finished.emit(result)
        except Exception as e:
            logger.error('PDF analysis failed: %s', e)
            self.error.emit(str(e))

    async def _analyze(self) -> str:
        from utils.pdf_reader import extract_text
        texts = [extract_text(p) for p in self._pdf_paths]
        combined = '\n\n'.join(t for t in texts if t)
        if not combined.strip():
            raise ValueError(
                'No selectable text found in the PDF(s). '
                'Try uploading a scanned image instead.'
            )
        return await self._ai.summarize_topic(combined)


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
    ):
        super().__init__()
        self._ai = ai_service
        self._config = config_manager
        self._topic = topic
        self._difficulty = difficulty
        self._num_questions = num_questions
        self._output_dir = output_dir

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
            self._topic, self._difficulty, self._num_questions
        )
        logger.info('Received %d questions from AI', len(questions))

        self.step_updated.emit('Creating PDF files...')
        student_path, teacher_path = generate_pdfs(
            questions, self._topic, self._output_dir
        )

        self.finished.emit(student_path, teacher_path)
