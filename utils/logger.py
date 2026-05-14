"""Logging setup for Math Worksheet Generator."""
import logging
import os
import sys


def _get_log_dir() -> str:
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'logs')


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    log_dir = _get_log_dir()
    if os.path.exists(log_dir):
        try:
            fh = logging.FileHandler(
                os.path.join(log_dir, 'worksheet_app.log'), encoding='utf-8'
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            pass

    return logger
