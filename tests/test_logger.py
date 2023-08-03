"""Unit tests for logger module."""

import unittest
from unittest import mock
import logging

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication

from iquip.apps import logger

class TestloggerApp(unittest.TestCase):
    """Unit tests for loggerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_handler_connection(self):
        """Tests that the handler's signal is successfully connected to LoggerApp method addLog."""
        with mock.patch('iquip.apps.logger._Signaller.signal') as mocked_signal:
            app = logger.LoggerApp(name="name", parent=QObject())
            mocked_signal.connect.assert_called_once_with(app.addLog)

    def test_set_level(self):
        """Tests for the LoggerApp's method setLevel.
        
        For vaild input, tests whether level of rootLogger and handler changes succesfully.
        For invaild input, tests whether level of rootLogger and handler remains same.
        """
        levels_dict = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        app = logger.LoggerApp('name')
        root_logger = logging.getLogger()
        for level in levels_dict.values():
            app.setLevel(levelText = level)
            self.assertEqual(levels_dict[app.handler.level], level)
            self.assertEqual(levels_dict[root_logger.level], level)
        prev_level = app.handler.level
        non_levels = ["debug", "CODE", "ERR"]
        for temp in non_levels:
            app.setLevel(levelText = temp)
            self.assertEqual(prev_level, app.handler.level)
            self.assertEqual(prev_level, root_logger.level)

    def test_frames(self):
        """Tests for the LoggerApp's method frames."""
        app = logger.LoggerApp(name="name", parent=QObject())
        self.assertEqual(app.frames(), (app.loggerFrame,))

    def test_call_check_to_clear(self):
        """Tests for the LoggerApp's method checkToClear.
        
        Tests that LoggerApp's method checkToclear is connected to the clearButton of LoggerFrame.
        """
        with mock.patch('iquip.apps.logger.LoggerApp.checkToClear') as mocked_method:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.loggerFrame.clearButton.clicked.emit()
            mocked_method.assert_called_once()

    def test_call_clear_log(self):
        """Tests for the LoggerApp's method clearLog.

        Tests that LoggerApp's method clearLog is connected to confirmFrame's OK button.
        """
        with mock.patch('iquip.apps.logger.LoggerApp.clearLog') as mocked_method:
            app = logger.LoggerApp(name="name", parent=QObject())
            app.confirmFrame.buttonBox.accepted.emit()
            mocked_method.assert_called_once()

    def test_call_add_log(self):
        """Tests for the LoggerApp's method addLog.
        
        Tests that LoggerApp's method addLog is called only for proper level of logs.
        """
        with mock.patch('iquip.apps.logger.LoggerApp.addLog') as mocked_method:
            app = logger.LoggerApp(name="name", parent=QObject())
            log = logger.logger
            app.frames()
            messages = {"DEBUG": "Hello", "INFO": "this", "WARNING": "code",
                        "ERROR": "is", "CRITICAL": "unittest"}
            for level, msg in messages.items():
                app.setLevel(level)
                log.warning(msg)
                if logging.WARNING >= getattr(logging, level):
                    mocked_method.assert_called_once()
                    mocked_method.reset_mock()
                else:
                    mocked_method.assert_not_called()


if __name__ == "__main__":
    unittest.main()
