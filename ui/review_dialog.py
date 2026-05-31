"""Review dialog — lets the user inspect and deselect questions before PDF creation."""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import utils.question_bank as question_bank
from utils.logger import setup_logger

logger = setup_logger(__name__)


class _QuestionRow(QWidget):
    """A single collapsible row: checkbox + question text, with answer revealed on expand."""

    def __init__(self, index: int, q: dict, parent=None):
        super().__init__(parent)
        self._q = q
        self._expanded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # ── Top row: checkbox + question + expand toggle ──
        top = QHBoxLayout()
        top.setSpacing(8)

        self._check = QCheckBox()
        self._check.setChecked(True)
        self._check.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Question number label
        num_label = QLabel(f'<b>Q{index}.</b>')
        num_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Question text — wraps
        q_text = str(q.get('question', '')).strip()
        self._q_label = QLabel(q_text)
        self._q_label.setWordWrap(True)
        self._q_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Expand/collapse toggle for the answer
        self._toggle_btn = QPushButton('▶ Answer')
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedWidth(80)
        self._toggle_btn.setStyleSheet('color: #1565c0; font-size: 11px;')
        self._toggle_btn.clicked.connect(self._toggle_answer)

        top.addWidget(self._check, 0)
        top.addWidget(num_label, 0)
        top.addWidget(self._q_label, 1)

        # Source badge (shown only for appended question sets)
        source = q.get('_source', '')
        if source:
            src_label = QLabel(f'[{source}]')
            src_label.setStyleSheet('color: #888; font-size: 10px; font-style: italic;')
            src_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            top.addWidget(src_label, 0)

        top.addWidget(self._toggle_btn, 0)
        root.addLayout(top)

        # MCQ choices (always visible when present)
        choices = q.get('choices') or []
        if choices:
            choices_text = '  '.join(str(c) for c in choices)
            cl = QLabel(f'<small><i>{choices_text}</i></small>')
            cl.setWordWrap(True)
            cl.setContentsMargins(28, 0, 0, 0)
            root.addWidget(cl)

        # Answer panel (hidden by default)
        self._answer_widget = QWidget()
        self._answer_widget.setVisible(False)
        ans_layout = QVBoxLayout(self._answer_widget)
        ans_layout.setContentsMargins(28, 0, 0, 0)
        ans_layout.setSpacing(2)

        answer_text = self._build_answer_text(q)
        ans_label = QLabel(answer_text)
        ans_label.setWordWrap(True)
        ans_label.setStyleSheet('color: #2e7d32; font-size: 11px;')
        ans_layout.addWidget(ans_label)
        root.addWidget(self._answer_widget)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet('color: #e0e0e0;')
        root.addWidget(line)

    @staticmethod
    def _build_answer_text(q: dict) -> str:
        parts = []
        steps = q.get('solution_steps') or []
        if steps:
            parts.append('Steps: ' + ' → '.join(str(s) for s in steps))
        final = q.get('final_answer') or q.get('answer') or ''
        if final:
            parts.append(f'Answer: {final}')
        return '\n'.join(parts) if parts else '(no answer provided)'

    def _toggle_answer(self):
        self._expanded = not self._expanded
        self._answer_widget.setVisible(self._expanded)
        self._toggle_btn.setText('▼ Answer' if self._expanded else '▶ Answer')

    # ── Public API ──

    def is_selected(self) -> bool:
        return self._check.isChecked()

    def set_selected(self, value: bool):
        self._check.setChecked(value)

    def connect_changed(self, slot):
        self._check.toggled.connect(slot)

    def question_data(self) -> dict:
        return self._q


class ReviewDialog(QDialog):
    """Shows AI-generated questions so the user can deselect any before PDF creation."""

    def __init__(self, questions: list, topic: str, subject: str,
                 output_dir: str = '', parent=None):
        super().__init__(parent)
        self._questions = questions
        self._topic = topic
        self._subject = subject
        self._output_dir = output_dir
        self._rows: list[_QuestionRow] = []
        self.setWindowTitle('Review Questions')
        self.setMinimumSize(700, 520)
        self.resize(780, 620)
        self._setup_ui()
        self._refresh_create_btn()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        # Header
        header = QLabel(
            '<b>Review generated questions</b><br>'
            '<small>Uncheck any questions you want to exclude, then click <i>Create PDF</i>.</small>'
        )
        header.setWordWrap(True)
        root.addWidget(header)

        # Select-all / Deselect-all / question-bank toolbar
        toolbar = QHBoxLayout()
        sel_all_btn = QPushButton('Select All')
        sel_all_btn.setFixedWidth(90)
        sel_all_btn.clicked.connect(self._select_all)
        desel_btn = QPushButton('Deselect All')
        desel_btn.setFixedWidth(90)
        desel_btn.clicked.connect(self._deselect_all)

        save_btn = QPushButton('Save Questions')
        save_btn.setToolTip('Save the current question list to a JSON file')
        save_btn.clicked.connect(self._save_questions)

        append_btn = QPushButton('Append from file…')
        append_btn.setToolTip('Load a previously saved question file and add its questions to this list')
        append_btn.clicked.connect(self._load_and_append)

        toolbar.addWidget(sel_all_btn)
        toolbar.addWidget(desel_btn)
        toolbar.addSpacing(16)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(append_btn)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Scrollable question list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.Box)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(0)

        for i, q in enumerate(self._questions, start=1):
            row = _QuestionRow(i, q)
            row.connect_changed(self._refresh_create_btn)
            self._rows.append(row)
            list_layout.addWidget(row)

        list_layout.addStretch()
        self._list_layout = list_layout   # kept for dynamic appending
        scroll.setWidget(list_widget)
        root.addWidget(scroll, 1)

        # Bottom button row
        btn_box = QHBoxLayout()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)

        self._create_btn = QPushButton()
        self._create_btn.setFixedHeight(36)
        self._create_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 0 16px;
            }
            QPushButton:hover   { background-color: #388e3c; }
            QPushButton:pressed { background-color: #1b5e20; }
            QPushButton:disabled { background-color: #b0b0b0; color: #e0e0e0; }
        """)
        self._create_btn.clicked.connect(self.accept)

        btn_box.addWidget(cancel_btn)
        btn_box.addStretch()
        btn_box.addWidget(self._create_btn)
        root.addLayout(btn_box)

    # ------------------------------------------------------------------
    # Slots / helpers
    # ------------------------------------------------------------------

    def _select_all(self):
        for row in self._rows:
            row.set_selected(True)

    def _deselect_all(self):
        for row in self._rows:
            row.set_selected(False)

    def _refresh_create_btn(self):
        n = sum(1 for r in self._rows if r.is_selected())
        self._create_btn.setText(f'Create PDF  ({n} question{"s" if n != 1 else ""} selected)')
        self._create_btn.setEnabled(n > 0)

    # ── Question bank helpers ──────────────────────────────────────────

    def _save_questions(self):
        """Save the current question list to a JSON file in the output directory."""
        qs = [r.question_data() for r in self._rows]
        if not qs:
            QMessageBox.information(self, 'No Questions', 'There are no questions to save.')
            return

        if self._output_dir:
            try:
                path = question_bank.save(qs, self._topic, self._subject, self._output_dir)
                QMessageBox.information(
                    self, 'Questions Saved',
                    f'Saved {len(qs)} question(s) to:\n{path}'
                )
                return
            except Exception as exc:
                # Fall through to manual file picker
                pass

        # No output_dir or save failed — ask user where to save
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Questions', '', 'Question Bank (*.json)'
        )
        if not path:
            return
        if not path.lower().endswith('.json'):
            path += '.json'
        try:
            import json
            payload = {
                'subject': self._subject,
                'topic': self._topic,
                'questions': qs,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self, 'Questions Saved',
                f'Saved {len(qs)} question(s) to:\n{path}'
            )
        except Exception as exc:
            QMessageBox.critical(self, 'Save Failed', f'Could not save questions:\n{exc}')

    def _load_and_append(self):
        """Open a question bank file and append its questions to the current list."""
        start_dir = self._output_dir or ''
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load Question Bank', start_dir, 'Question Bank (*.json)'
        )
        if not path:
            return
        try:
            data = question_bank.load(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Load Failed', f'Could not load file:\n{exc}')
            return

        new_qs = data.get('questions', [])
        if not new_qs:
            QMessageBox.information(self, 'Empty File', 'The selected file contains no questions.')
            return

        source_label = os.path.splitext(os.path.basename(path))[0]
        # Keep badge short
        if len(source_label) > 30:
            source_label = source_label[:27] + '...'

        self._append_questions(new_qs, source_label)
        self._refresh_create_btn()

    def _append_questions(self, new_qs: list, source_label: str):
        """Add *new_qs* as new rows after the existing ones, tagged with *source_label*."""
        start_index = len(self._rows) + 1
        for offset, q in enumerate(new_qs):
            tagged_q = dict(q)   # shallow copy so we don't mutate the original
            tagged_q['_source'] = source_label
            row = _QuestionRow(start_index + offset, tagged_q)
            row.connect_changed(self._refresh_create_btn)
            self._rows.append(row)
            # Insert before the trailing stretch item
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_questions(self) -> list:
        return [r.question_data() for r in self._rows if r.is_selected()]
