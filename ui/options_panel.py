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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.logger import setup_logger

logger = setup_logger(__name__)

DIFFICULTY_LEVELS = ['Beginner', 'Intermediate', 'Advanced']


class OptionsPanel(QWidget):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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

        # Number of questions
        num_row = QHBoxLayout()
        num_row.addWidget(QLabel('Number of questions:'))
        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, 30)
        self.num_spin.setValue(self._config.get('default_num_questions', 10))
        num_row.addWidget(self.num_spin)
        num_row.addStretch()

        ws_layout.addLayout(diff_row)
        ws_layout.addLayout(num_row)

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
        layout.addWidget(out_group)
        layout.addStretch()

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Select Output Folder', self.output_edit.text()
        )
        if d:
            self.output_edit.setText(d)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_topic(self) -> str:
        return self.topic_edit.toPlainText().strip()

    def set_topic(self, text: str):
        self.topic_edit.setPlainText(text)

    def get_difficulty(self) -> str:
        return self.difficulty_combo.currentText()

    def get_num_questions(self) -> int:
        return self.num_spin.value()

    def get_output_dir(self) -> str:
        d = self.output_edit.text().strip()
        return d if d else self._config.get_output_directory()

    def get_approved(self) -> bool:
        return self.approve_check.isChecked()

    def reset_approval(self):
        self.approve_check.setChecked(False)
