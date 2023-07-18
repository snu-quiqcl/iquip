"""Unit tests for builder module."""

import copy
import unittest
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QListWidget, QWidget

from iquip.apps import builder
from iquip import protocols

EXPERIMENT_INFO = {
    "name": "name",
    "arginfo": {
        "arg0": [{"ty": "BooleanValue", "default": "default0"}, None, None],
        "arg1": [{"ty": "StringValue", "default": "default1"}, None, None],
        "arg2": [{"ty": "EnumerationValue", "default": "default2"}, None, None],
        "arg3": [{"ty": "NumberValue", "default": "default3"}, None, None]
    }
}


class _BaseEntryTest(unittest.TestCase):
    """Unit tests for _BaseEntry class."""


class _BooleanEntryTest(unittest.TestCase):
    """Unit tests for _BooleanEntry class."""


class _EnumerationEntryTest(unittest.TestCase):
    """Unit tests for _EnumerationEntry class."""


class _NumberEntryTest(unittest.TestCase):
    """Unit tests for _NumberEntry class."""


class _StringEntryTest(unittest.TestCase):
    """Unit tests for _StringEntry class."""


class _DateTimeEntryTest(unittest.TestCase):
    """Unit tests for _DateTimeEntry class."""


class ExperimentSubmitThreadTest(unittest.TestCase):
    """Unit tests for ExperimentSubmitThread class."""


class BuilderAppTest(unittest.TestCase):
    """Unit tests for BuilderApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("iquip.apps.builder.ExperimentSubmitThread")
        self.mocked_file_finder_thread_cls = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init_args_entry(self):
        mockedEntries = {
            "BooleanValue": mock.MagicMock(return_value=QWidget()),
            "StringValue": mock.MagicMock(return_value=QWidget()),
            "EnumerationValue": mock.MagicMock(return_value=QWidget()),
            "NumberValue": mock.MagicMock(return_value=QWidget())
        }
        with mock.patch.multiple(
            "iquip.apps.builder",
            _BooleanEntry=mockedEntries["BooleanValue"],
            _StringEntry=mockedEntries["StringValue"],
            _EnumerationEntry=mockedEntries["EnumerationValue"],
            _NumberEntry=mockedEntries["NumberValue"]
        ) as mocked:
            app = builder.BuilderApp(
                name="name",
                experimentPath="experimentPath",
                experimentClsName="experimentClsName",
                experimentInfo=copy.deepcopy(EXPERIMENT_INFO),
                parent=QObject()
            )
        for argName, (argInfo, *_) in EXPERIMENT_INFO["arginfo"].items():
            print(argName, argInfo)
            mockedEntries[argInfo.pop("ty")].assert_any_call(argName, argInfo)


if __name__ == "__main__":
    unittest.main()
