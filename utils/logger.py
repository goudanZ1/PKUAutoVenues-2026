import logging
import sys

from .config import LOG_FILE


class Logger:

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setLevel(logging.INFO)
        self._console_handler.setFormatter(formatter)
        self._logger.addHandler(self._console_handler)

        self._file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(formatter)
        self._logger.addHandler(self._file_handler)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)

    def breathe(self) -> None:
        """Insert a blank line in the log file, see function `StreamHandler.emit`"""
        self._file_handler.stream.write("\n")
        self._file_handler.flush()
