"""Dialog that asks the user to pick a page range from an oversized PDF."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class PageRangeDialog(QDialog):
    """Modal dialog shown when a PDF exceeds the analysis page limit.

    After ``exec()`` returns ``QDialog.DialogCode.Accepted``, read the chosen
    range via ``start_page`` and ``end_page`` (both 1-based, inclusive).
    """

    def __init__(self, filename: str, total_pages: int, max_pages: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Page Range')
        self.setMinimumWidth(380)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        info = QLabel(
            f'<b>{filename}</b> has <b>{total_pages} pages</b>.<br>'
            f'Only up to <b>{max_pages} pages</b> can be analyzed at once.<br>'
            f'Choose which pages to include:'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        range_row = QHBoxLayout()
        range_row.setSpacing(8)
        range_row.addWidget(QLabel('From page:'))

        self._start = QSpinBox()
        self._start.setRange(1, total_pages)
        self._start.setValue(1)
        self._start.setMinimumWidth(80)
        self._start.setStyleSheet('QSpinBox { padding: 4px 6px; }')
        range_row.addWidget(self._start)

        range_row.addSpacing(16)
        range_row.addWidget(QLabel('to page:'))

        self._end = QSpinBox()
        self._end.setRange(1, total_pages)
        self._end.setValue(min(max_pages, total_pages))
        self._end.setMinimumWidth(80)
        self._end.setStyleSheet('QSpinBox { padding: 4px 6px; }')
        range_row.addWidget(self._end)

        range_row.addStretch()
        layout.addLayout(range_row)

        self._warning = QLabel()
        self._warning.setStyleSheet('color: #b71c1c; font-size: 10px;')
        self._warning.setWordWrap(True)
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._max_pages = max_pages
        self._start.valueChanged.connect(self._validate)
        self._end.valueChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        start = self._start.value()
        end   = self._end.value()
        span  = end - start + 1

        if end < start:
            self._warning.setText('End page must be greater than or equal to start page.')
        elif span > self._max_pages:
            self._warning.setText(
                f'Selected range is {span} pages — please reduce to {self._max_pages} or fewer.'
            )
        else:
            self._warning.setText('')

    def _on_accept(self):
        start = self._start.value()
        end   = self._end.value()
        if end < start or (end - start + 1) > self._max_pages:
            return  # keep dialog open
        self.accept()

    @property
    def start_page(self) -> int:
        return self._start.value()

    @property
    def end_page(self) -> int:
        return self._end.value()
