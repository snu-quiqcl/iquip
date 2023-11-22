"""Unit tests for logger module."""

import os
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
        self.log_dir = "logfile-unittest/"
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        self.app = logger.LoggerApp(name="name", logFilePath=self.log_dir, parent=QObject())

    def tearDown(self):
        self.app.fileHandler.close()
        file_list = os.listdir(self.log_dir)
        for file in file_list:
            os.remove(os.path.join(self.log_dir, file))
        os.rmdir(self.log_dir)
        del self.qapp

    def test_emit(self):
        with mock.patch("iquip.apps.logger._Signaller.signal") as mocked_signal:
            self.app.setLevel(self.app.frameHandler ,"DEBUG")
            test_log = logging.makeLogRecord({"name": "hello"})
            self.app.frameHandler.emit(test_log)
            mocked_signal.emit.assert_called_once()


class ConfirmClearingFrameTest(unittest.TestCase):
    """Unit tests for LoggerFrame class."""

    def setUp(self):
        self.qapp = QApplication([])
        self.log_dir = "logfile-unittest/"
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        self.app = logger.LoggerApp(name="name", logFilePath=self.log_dir, parent=QObject())

    def tearDown(self):
        self.app.fileHandler.close()
        file_list = os.listdir(self.log_dir)
        for file in file_list:
            os.remove(os.path.join(self.log_dir, file))
        os.rmdir(self.log_dir)
        del self.qapp

    def test_button_ok_clicked(self):
        with mock.patch("iquip.apps.logger.QWidget.close") as mocked_close:
            self.app.confirmFrame.buttonOKClicked()
            mocked_close.assert_called_once()

    def test_button_cancel_clicked(self):
        with mock.patch("iquip.apps.logger.QWidget.close") as mocked_close:
            self.app.confirmFrame.buttonCancelClicked()
            mocked_close.assert_called_once()


class LoggerAppTest(unittest.TestCase):
    """Unit tests for LoggerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        self.log_dir = "logfile-unittest/"
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        self.app = logger.LoggerApp(name="name", logFilePath=self.log_dir, parent=QObject())

    def tearDown(self):
        self.app.fileHandler.close()
        file_list = os.listdir(self.log_dir)
        for file in file_list:
            os.remove(os.path.join(self.log_dir, file))
        os.rmdir(self.log_dir)
        del self.qapp

    def test_init_logger(self):
        self.assertEqual(self.app.frameHandler.level, logging.WARNING)
        self.assertEqual(self.app.fileHandler.level, logging.WARNING)

    def test_set_level(self):
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        root_logger = logging.getLogger()
        app = self.app
        for levelText, level in levels.items():
            app.setLevel(app.frameHandler, levelText)
            app.setLevel(app.fileHandler, levelText)
            self.assertEqual(app.frameHandler.level, level)
            self.assertEqual(app.fileHandler.level, level)
            self.assertEqual(root_logger.level, level)
        prev_level = app.frameHandler.level
        non_level = "non_level"
        app.setLevel(app.frameHandler, non_level)
        app.setLevel(app.fileHandler, non_level)
        self.assertEqual(app.frameHandler.level, prev_level)
        self.assertEqual(app.fileHandler.level, prev_level)
        self.assertEqual(root_logger.level, prev_level)

    def test_frames(self):
        self.assertEqual(self.app.frames(), (("", self.app.loggerFrame),))

    def test_namer(self):
        name = "hell.logo"
        modified_name = self.app.fileHandler.namer(name)
        self.assertEqual(modified_name, "hello.log")

    def test_call_check_to_clear(self):
        with mock.patch("iquip.apps.logger.LoggerApp.checkToClear") as mocked_method:
            app = logger.LoggerApp(name="name", logFilePath=self.log_dir, parent=QObject())
            app.loggerFrame.clearButton.clicked.emit()
            mocked_method.assert_called_once()
            app.fileHandler.close()

    def test_check_to_clear(self):
        with mock.patch("iquip.apps.logger.QWidget.show") as mocked_show:
            self.app.checkToClear()
            mocked_show.assert_called_once()

    def test_call_clear_log(self):
        with mock.patch("iquip.apps.logger.LoggerApp.clearLog") as mocked_method:
            app = logger.LoggerApp(name="name", logFilePath=self.log_dir, parent=QObject())
            app.confirmFrame.buttonBox.accepted.emit()
            mocked_method.assert_called_once()
            app.fileHandler.close()

    @mock.patch("iquip.apps.logger.QTextEdit.clear")
    def test_clear_log(self, mocked_clear):
        with mock.patch("iquip.apps.logger.logger") as mocked_logger:
            self.app.clearLog()
            mocked_clear.assert_called_once()
            mocked_logger.info.called_once_with("Tried to clear logs by clicking clear button")

    def test_add_log(self):
        with mock.patch("iquip.apps.logger.QTextEdit.insertPlainText") as mocked_insert:
            with mock.patch("iquip.apps.logger.QDateTime.currentDateTime") as mocked_time:
                self.app.addLog("hello")
                timeString = mocked_time().toString("yyyy-MM-dd HH:mm:ss")
                msg = f"{timeString}: hello\n"
                mocked_insert.assert_called_once_with(msg)


if __name__ == "__main__":
    unittest.main()
