"""Dialog for customising the printed worksheet header before PDF creation."""
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from utils.pdf_generator import WorksheetHeader
from utils.logger import setup_logger

logger = setup_logger(__name__)


class HeaderOptionsDialog(QDialog):
    """Lets the user customise the printed page header before generating PDFs."""

    def __init__(
        self,
        default_title: str = 'Worksheet',
        default_grade: str = '',
        parent=None,
    ):
        super().__init__(parent)
        self._header = WorksheetHeader(title=default_title, grade=default_grade)
        self.setWindowTitle('Worksheet Header Options')
        self.setMinimumWidth(440)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(16, 14, 16, 14)

        # ── Title section ──────────────────────────────────────────────
        title_group = QGroupBox('Title')
        title_form = QFormLayout(title_group)
        title_form.setSpacing(8)

        self._title_edit = QLineEdit(self._header.title)
        self._title_edit.setPlaceholderText('Worksheet title shown at the top of the page')
        title_form.addRow('Title text:', self._title_edit)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 36)
        self._font_spin.setValue(self._header.title_font_size)
        self._font_spin.setSuffix(' pt')
        title_form.addRow('Font size:', self._font_spin)

        root.addWidget(title_group)

        # ── Student info block ─────────────────────────────────────────
        info_group = QGroupBox('Student Info Block')
        info_form = QFormLayout(info_group)
        info_form.setSpacing(8)

        self._grade_edit = QLineEdit(self._header.grade)
        self._grade_edit.setPlaceholderText('e.g.  Grade 8  /  Class 8A  (leave blank for underline)')
        info_form.addRow('Class / Grade:', self._grade_edit)

        self._name_check = QCheckBox('Show "Name: ___" line')
        self._name_check.setChecked(self._header.show_name_line)
        info_form.addRow('', self._name_check)

        marks_row = QHBoxLayout()
        self._marks_check = QCheckBox('Show marks line')
        self._marks_check.setChecked(self._header.show_marks_line)

        self._total_spin = QSpinBox()
        self._total_spin.setRange(1, 999)
        self._total_spin.setValue(self._header.total_marks)
        self._total_spin.setSuffix(' marks total')
        self._total_spin.setEnabled(False)
        self._marks_check.toggled.connect(self._total_spin.setEnabled)

        marks_row.addWidget(self._marks_check)
        marks_row.addWidget(self._total_spin)
        marks_row.addStretch()
        info_form.addRow('Marks:', marks_row)

        root.addWidget(info_group)

        # ── Dialog buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton('Continue  \u2192')
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_ok(self):
        self._header = WorksheetHeader(
            title=self._title_edit.text().strip() or 'Worksheet',
            title_font_size=self._font_spin.value(),
            grade=self._grade_edit.text().strip(),
            show_name_line=self._name_check.isChecked(),
            show_marks_line=self._marks_check.isChecked(),
            total_marks=self._total_spin.value(),
        )
        self.accept()

    # ------------------------------------------------------------------
    # Result accessor
    # ------------------------------------------------------------------

    def get_header(self) -> WorksheetHeader:
        """Return the ``WorksheetHeader`` populated from the dialog inputs."""
        return self._header
