"""Entry point for Math Worksheet Generator."""
import ctypes
import os
import sys

# Windows: declare an explicit AppUserModelID *before* any Qt or COM
# initialisation.  Without this Windows groups the process under Python's own
# identity and shows the Python (floppy-disk) icon for pinned taskbar items.
if sys.platform == 'win32':
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'WorksheetApp.MathWorksheetGenerator.1'
        )
    except Exception:
        pass

# Ensure working directory is the app root (matters for PyInstaller .exe)
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtGui import QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from utils.config_manager import ConfigManager  # noqa: E402
from utils.logger import setup_logger  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.settings_dialog import SettingsDialog  # noqa: E402

logger = setup_logger(__name__)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Math Worksheet Generator')
    app.setOrganizationName('WorksheetApp')

    # Set application icon
    # PyInstaller 6+ puts bundled data inside _internal/ (sys._MEIPASS).
    # In development, use the project root.
    _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    _icon_path = os.path.join(_base, 'assets', 'icon.png')
    if os.path.exists(_icon_path):
        app.setWindowIcon(QIcon(_icon_path))

    config = ConfigManager()

    # First-run: prompt for API key
    if not config.get('groq_api_key'):
        QMessageBox.information(
            None,
            'Welcome to Math Worksheet Generator',
            'Welcome!\n\n'
            'To get started, please enter your Groq API key on the next screen.\n\n'
            'You can get a free key at:  https://console.groq.com',
        )
        dlg = SettingsDialog(config)
        dlg.exec()

    window = MainWindow(config)
    window.show()
    logger.info('Math Worksheet Generator started.')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
