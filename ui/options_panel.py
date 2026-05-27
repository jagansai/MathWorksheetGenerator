"""Options panel: topic description, difficulty, question count, output directory."""
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.base_handler import QuestionType
from utils.logger import setup_logger

logger = setup_logger(__name__)

DIFFICULTY_LEVELS = ['Beginner', 'Intermediate', 'Advanced']
GRADE_LEVELS = [f'Grade {i}' for i in range(1, 13)]


class OptionsPanel(QWidget):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._setup_ui()

    def _setup_ui(self):
        # Outer layout holds only the scroll area so the panel is usable on
        # small / low-resolution screens (e.g. 13").
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(10)

        # ---- Topic description + approval ----
        topic_group = QGroupBox('Analyzed Content')
        tg_layout = QVBoxLayout(topic_group)
        tg_layout.setSpacing(6)

        hint = QLabel(
            'Auto-filled from your uploaded file. Review and edit if needed, then approve below.'
        )
        hint.setStyleSheet('color: #777; font-size: 10px;')
        hint.setWordWrap(True)

        self.topic_edit = QTextEdit()
        self.topic_edit.setPlaceholderText(
            'Upload an image or PDF to auto-extract the topic and sample problems,\n'
            'or type a description here.\n\n'
            'After analysis, this area will show the detected topic summary followed by\n'
            'representative sample problems from your source material.'
        )
        self.topic_edit.setMinimumHeight(200)

        self.approve_check = QCheckBox('Content looks correct — enable Generate Worksheet')
        self.approve_check.setStyleSheet('font-weight: bold; color: #2e7d32;')

        self.topic_edit.textChanged.connect(lambda: self.approve_check.setChecked(False))

        tg_layout.addWidget(hint)
        tg_layout.addWidget(self.topic_edit)
        tg_layout.addWidget(self.approve_check)

        # ---- Worksheet settings ----
        ws_group = QGroupBox('Worksheet Settings')
        ws_layout = QVBoxLayout(ws_group)
        ws_layout.setSpacing(8)

        # Difficulty
        diff_row = QHBoxLayout()
        diff_row.addWidget(QLabel('Difficulty:'))
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTY_LEVELS)
        default_diff = self._config.get('default_difficulty', 'Intermediate')
        idx = self.difficulty_combo.findText(default_diff)
        if idx >= 0:
            self.difficulty_combo.setCurrentIndex(idx)
        diff_row.addWidget(self.difficulty_combo)
        diff_row.addStretch()

        # Grade
        grade_row = QHBoxLayout()
        grade_row.addWidget(QLabel('Grade:'))
        self.grade_combo = QComboBox()
        self.grade_combo.setPlaceholderText('Select a grade...')
        self.grade_combo.addItems(GRADE_LEVELS)
        default_grade = self._config.get('default_grade', '')
        if default_grade:
            idx = self.grade_combo.findText(default_grade)
            if idx >= 0:
                self.grade_combo.setCurrentIndex(idx)
        else:
            self.grade_combo.setCurrentIndex(-1)
        grade_row.addWidget(self.grade_combo)
        grade_row.addStretch()
        self.grade_combo.currentIndexChanged.connect(self._on_grade_changed)

        # Number of questions
        num_row = QHBoxLayout()
        num_row.addWidget(QLabel('Number of questions:'))
        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, self._config.get('max_num_questions', 25))
        self.num_spin.setValue(self._config.get('default_num_questions', 10))
        num_row.addWidget(self.num_spin)
        num_row.addStretch()

        ws_layout.addLayout(diff_row)
        ws_layout.addLayout(grade_row)
        ws_layout.addLayout(num_row)

        # ---- Question types ----
        qt_group = QGroupBox('Question Types')
        qt_layout = QVBoxLayout(qt_group)
        qt_layout.setSpacing(6)

        qt_hint = QLabel('Select one or more types. Questions will be split evenly across selected types.')
        qt_hint.setStyleSheet('color: #777; font-size: 10px;')
        qt_hint.setWordWrap(True)

        self.mcq_check = QCheckBox('MCQ (Multiple Choice)')
        self.word_check = QCheckBox('Word Problems')
        self.non_word_check = QCheckBox('Non-Word Problems  (computation / formula-based)')
        self.non_word_check.setChecked(True)
        self.proof_check = QCheckBox('Challenge Questions  (Proof / Show that\u2026 / Constructions)')
        self.proof_check.setVisible(False)

        qt_layout.addWidget(qt_hint)
        qt_layout.addWidget(self.mcq_check)
        qt_layout.addWidget(self.word_check)
        qt_layout.addWidget(self.non_word_check)
        qt_layout.addWidget(self.proof_check)

        # ---- Output directory ----
        out_group = QGroupBox('Output Directory')
        og_layout = QHBoxLayout(out_group)
        self.output_edit = QLineEdit()
        self.output_edit.setText(self._config.get_output_directory())
        self.output_edit.setPlaceholderText('Select output folder...')
        browse_btn = QPushButton('Browse...')
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_output)
        og_layout.addWidget(self.output_edit)
        og_layout.addWidget(browse_btn)

        layout.addWidget(topic_group)
        layout.addWidget(ws_group)
        layout.addWidget(qt_group)
        layout.addWidget(out_group)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Select Output Folder', self.output_edit.text()
        )
        if d:
            self.output_edit.setText(d)

    def _on_grade_changed(self, _index: int):
        grade_text = self.grade_combo.currentText()
        try:
            grade_num = int(grade_text.split()[-1])
            show = grade_num >= 7
        except (ValueError, IndexError):
            show = False
        self.proof_check.setVisible(show)
        if not show:
            self.proof_check.setChecked(False)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_topic(self) -> str:
        return self.topic_edit.toPlainText().strip()

    def set_topic(self, text: str):
        self.topic_edit.setPlainText(text)

    def get_difficulty(self) -> str:
        return self.difficulty_combo.currentText()

    def get_grade(self) -> str:
        return self.grade_combo.currentText()

    def get_num_questions(self) -> int:
        return self.num_spin.value()

    def get_output_dir(self) -> str:
        d = self.output_edit.text().strip()
        return d if d else self._config.get_output_directory()

    def get_approved(self) -> bool:
        return self.approve_check.isChecked()

    def reset_approval(self):
        self.approve_check.setChecked(False)

    def get_question_types(self) -> list[QuestionType]:
        types = []
        if self.mcq_check.isChecked():
            types.append(QuestionType.MCQ)
        if self.word_check.isChecked():
            types.append(QuestionType.WORD)
        if self.non_word_check.isChecked():
            types.append(QuestionType.NON_WORD)
        if self.proof_check.isChecked() and self.proof_check.isVisible():
            types.append(QuestionType.PROOF)
        return types or [QuestionType.NON_WORD]  # fallback: never return empty
