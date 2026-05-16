"""Main application window."""
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from services.ai_service import AIService
from services.worksheet_service import ImageAnalysisWorker, PDFAnalysisWorker, WorksheetWorker
from ui.image_panel import ImagePanel
from ui.options_panel import OptionsPanel
from ui.progress_dialog import ProgressDialog
from ui.settings_dialog import SettingsDialog
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self._config = config_manager
        self._ai = AIService(config_manager)
        self._analysis_worker: ImageAnalysisWorker | None = None
        self._pdf_worker: PDFAnalysisWorker | None = None
        self._worksheet_worker: WorksheetWorker | None = None
        self._progress: ProgressDialog | None = None
        self._current_subject: str = ''
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle('Worksheet Generator')
        self.setMinimumSize(840, 580)
        self.resize(980, 660)

        self._build_menu()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 4, 12, 8)
        root.setSpacing(6)

        # Splitter: image panel | options panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        self._image_panel = ImagePanel(self._config)
        self._image_panel.images_changed.connect(self._on_images_list_changed)
        self._image_panel.analyze_requested.connect(self._on_analyze_requested)
        self._image_panel.subject_changed.connect(self._on_subject_changed)

        self._options_panel = OptionsPanel(self._config)

        splitter.addWidget(self._image_panel)
        splitter.addWidget(self._options_panel)
        splitter.setSizes([300, 640])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)
        root.addSpacing(10)

        # Generate button
        self._generate_btn = QPushButton('  Generate Worksheet  ')
        self._generate_btn.setFixedHeight(40)
        self._generate_btn.setMaximumWidth(280)
        self._generate_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover  { background-color: #388e3c; }
            QPushButton:pressed { background-color: #1b5e20; }
            QPushButton:disabled { background-color: #b0b0b0; color: #e0e0e0; }
        """)
        self._generate_btn.clicked.connect(self._on_generate)
        self._generate_btn.setEnabled(False)
        self._options_panel.approve_check.toggled.connect(self._generate_btn.setEnabled)
        root.addWidget(self._generate_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage('Select a subject to get started.')

    def _build_menu(self):
        bar = QMenuBar(self)
        self.setMenuBar(bar)

        file_menu = bar.addMenu('File')

        settings_act = QAction('Settings...', self)
        settings_act.setShortcut('Ctrl+,')
        settings_act.triggered.connect(self._open_settings)
        file_menu.addAction(settings_act)

        file_menu.addSeparator()

        exit_act = QAction('Exit', self)
        exit_act.setShortcut('Ctrl+Q')
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _open_settings(self):
        SettingsDialog(self._config, parent=self).exec()

    def _on_subject_changed(self, subject: str):
        """Called when the user changes the subject combo in the image panel."""
        self._current_subject = subject
        self._cancel_analysis_workers()
        self._options_panel.set_topic('')
        self._options_panel.reset_approval()
        self._generate_btn.setEnabled(False)
        if subject:
            self._status.showMessage(
                f'Subject: {subject}.  Upload files then click Analyze Files.'
            )
        else:
            self._status.showMessage('Select a subject to get started.')

    def _on_images_list_changed(self, paths: list):
        """React to images being added or removed (no AI call — just reset state when empty)."""
        if not paths:
            self._cancel_analysis_workers()
            self._options_panel.set_topic('')
            self._options_panel.reset_approval()
            self._generate_btn.setEnabled(False)
            self._status.showMessage(
                'Ready.  Upload files then click Analyze Files to get started.'
            )

    def _cancel_analysis_workers(self):
        """Stop any in-flight image or PDF analysis worker."""
        for worker in (self._analysis_worker, self._pdf_worker):
            if worker and worker.isRunning():
                worker.finished.disconnect()
                worker.error.disconnect()
                worker.quit()

    def _on_analyze_requested(self, paths: list):
        """Triggered by the Analyze Files button — dispatch to the correct worker by file type."""
        if not paths:
            return

        if not self._config.get('groq_api_key'):
            self._status.showMessage(
                'No API key configured. Go to File > Settings to add your Groq key.'
            )
            return

        images = [p for p in paths if os.path.splitext(p)[1].lower() in {'.jpg', '.jpeg', '.png'}]
        pdfs   = [p for p in paths if p.lower().endswith('.pdf')]

        if images and pdfs:
            QMessageBox.warning(
                self, 'Mixed File Types',
                'Please upload either images or PDFs — not both at the same time.\n'
                'Remove one type of file before analyzing.',
            )
            return

        self._cancel_analysis_workers()
        self._options_panel.reset_approval()
        self._image_panel.set_analyzing(True)
        self._generate_btn.setEnabled(False)

        if pdfs:
            n = len(pdfs)
            self._status.showMessage(f'Extracting and analyzing {n} PDF{"s" if n > 1 else ""}...')
            self._pdf_worker = PDFAnalysisWorker(self._ai, pdfs, self._config, self._current_subject)
            self._pdf_worker.finished.connect(self._on_analysis_done)
            self._pdf_worker.error.connect(self._on_analysis_error)
            self._pdf_worker.start()
        else:
            n = len(images)
            self._status.showMessage(f'Analyzing {n} image{"s" if n > 1 else ""}...')
            self._analysis_worker = ImageAnalysisWorker(self._ai, images, self._current_subject)
            self._analysis_worker.finished.connect(self._on_analysis_done)
            self._analysis_worker.error.connect(self._on_analysis_error)
            self._analysis_worker.start()

    def _on_analysis_done(self, topic: str):
        self._image_panel.set_analyzing(False)
        self._options_panel.set_topic(topic)
        self._status.showMessage(
            'Analysis complete. Review the content above, tick the checkbox, then click Generate.'
        )
        logger.info('Image analysis complete.')

    def _on_analysis_error(self, error: str):
        self._image_panel.set_analyzing(False)
        self._status.showMessage(f'Image analysis failed: {error}')
        QMessageBox.warning(
            self, 'Image Analysis Failed',
            f'Could not analyze the file automatically:\n\n{error}\n\n'
            'You can manually type the topic description in the right panel,\n'
            'then tick the checkbox to enable Generate.',
        )

    def _on_generate(self):
        if not self._config.get('groq_api_key'):
            QMessageBox.warning(
                self, 'API Key Missing',
                'Please add your Groq API key under File > Settings.',
            )
            return

        topic = self._options_panel.get_topic()
        if not topic:
            QMessageBox.warning(
                self, 'No Topic',
                'Please upload an image or type a topic description before generating.',
            )
            return

        difficulty = self._options_panel.get_difficulty()
        num_questions = self._options_panel.get_num_questions()
        output_dir = self._options_panel.get_output_dir()

        self._generate_btn.setEnabled(False)

        self._progress = ProgressDialog(self)
        self._progress.set_step('Connecting to Groq AI...')

        self._worksheet_worker = WorksheetWorker(
            self._ai, self._config,
            topic, difficulty, num_questions, output_dir, self._current_subject,
        )
        self._worksheet_worker.step_updated.connect(self._progress.set_step)
        self._worksheet_worker.finished.connect(self._on_generation_done)
        self._worksheet_worker.error.connect(self._on_generation_error)
        self._worksheet_worker.start()

        self._progress.exec()   # blocks until accept()/reject() called from worker signals

    def _on_generation_done(self, student_path: str, teacher_path: str):
        if self._progress:
            self._progress.accept()
        self._generate_btn.setEnabled(self._options_panel.get_approved())

        folder = os.path.dirname(student_path)
        self._status.showMessage(f'Done!  Files saved to: {folder}')
        logger.info('Worksheet generation complete. Output folder: %s', folder)

        msg = QMessageBox(self)
        msg.setWindowTitle('Worksheet Generated!')
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText('<b>Your worksheet has been generated successfully.</b>')
        msg.setDetailedText(
            f'Student worksheet:\n{student_path}\n\n'
            f'Teacher answer key:\n{teacher_path}'
        )
        open_btn = msg.addButton('Open Output Folder', QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()

        if msg.clickedButton() == open_btn:
            subprocess.Popen(f'explorer /select,"{student_path}"')

    def _on_generation_error(self, error: str):
        if self._progress:
            self._progress.accept()
        self._generate_btn.setEnabled(self._options_panel.get_approved())
        self._status.showMessage('Generation failed.')
        QMessageBox.critical(
            self, 'Generation Failed',
            f'An error occurred during generation:\n\n{error}',
        )
