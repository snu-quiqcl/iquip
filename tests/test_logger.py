"""Unit tests for logger module."""

import logging
import unittest
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication

from iquip.apps import logger

class LoggingHandlerTest(unittest.TestCase):
    """Unit tests for LoggingHandler class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_emit(self):
        with mock.patch("iquip.apps.logger._Signaller.signal") as mocked_signal:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.setLevel("DEBUG")
            temp_logger= logging.getLogger(__name__)
            mocked_signal.reset_mock()
            temp_logger.info("hello")
            mocked_signal.emit.assert_called_once()


class ConfirmClearingFrameTest(unittest.TestCase):
    """Unit tests for LoggerFrame class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_button_ok_clicked(self):
        with mock.patch("iquip.apps.logger.QWidget.close") as mocked_close:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.confirmFrame.buttonOKClicked()
            mocked_close.assert_called_once()

    def test_button_cancel_clicked(self):
        with mock.patch("iquip.apps.logger.QWidget.close") as mocked_close:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.confirmFrame.buttonCancelClicked()
            mocked_close.assert_called_once()


class LoggerAppTest(unittest.TestCase):
    """Unit tests for LoggerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_set_level(self):
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        root_logger = logging.getLogger()
        app = logger.LoggerApp(name="name", parent=QObject())
        for levelText, level in levels.items():
            app.setLevel(levelText)
            self.assertEqual(app.handler.level, level)
            self.assertEqual(root_logger.level, level)
        prev_level = app.handler.level
        non_level = "non_level"
        app.setLevel(non_level)
        self.assertEqual(prev_level, app.handler.level)
        self.assertEqual(prev_level, root_logger.level)

    def test_frames(self):
        app = logger.LoggerApp(name="name", parent=QObject())
        self.assertEqual(app.frames(), (app.loggerFrame,))

    def test_call_check_to_clear(self):
        with mock.patch("iquip.apps.logger.LoggerApp.checkToClear") as mocked_method:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.loggerFrame.clearButton.clicked.emit()
            mocked_method.assert_called_once()

    def test_check_to_clear(self):
        with mock.patch("iquip.apps.logger.QWidget.show") as mocked_show:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.checkToClear()
            mocked_show.assert_called_once()

    def test_call_clear_log(self):
        with mock.patch("iquip.apps.logger.LoggerApp.clearLog") as mocked_method:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.confirmFrame.buttonBox.accepted.emit()
            mocked_method.assert_called_once()

    @mock.patch("iquip.apps.logger.QTextEdit.clear")
    def test_clear_log(self, mocked_clear):
        with mock.patch("iquip.apps.logger.logger") as mocked_logger:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.clearLog()
            mocked_clear.assert_called_once()
            mocked_logger.info.called_once_with("Tried to clear logs by clicking clear button")

    def test_add_log(self):
        with mock.patch("iquip.apps.logger.QTextEdit.insertPlainText") as mocked_insert:
            with mock.patch("iquip.apps.logger.QDateTime.currentDateTime") as mocked_time:
                app = logger.LoggerApp(name="name", parent=QObject())
                app.addLog("hello")
                timeString = mocked_time().toString("yyyy-MM-dd HH:mm:ss")
                msg = f"{timeString}: hello\n"
                mocked_insert.assert_called_once_with(msg)

if __name__ == "__main__":
    unittest.main()
