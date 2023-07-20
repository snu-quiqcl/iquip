"""Unit tests for builder module."""

import copy
import unittest
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QWidget

from iquip.apps import builder

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
        self.mockedEntries = {
            f"{type_}Value": mock.MagicMock(return_value=QWidget())
            for type_ in ("Boolean", "String", "Enumeration", "Number")
        }
        experiment_submit_thread_patcher = mock.patch("iquip.apps.builder.ExperimentSubmitThread")
        entries_patcher = mock.patch.multiple(
            "iquip.apps.builder",
            _BooleanEntry=self.mockedEntries["BooleanValue"],
            _StringEntry=self.mockedEntries["StringValue"],
            _EnumerationEntry=self.mockedEntries["EnumerationValue"],
            _NumberEntry=self.mockedEntries["NumberValue"]
        )
        self.mocked_submit_thread_cls = experiment_submit_thread_patcher.start()
        self.mocked_entries = entries_patcher.start()
        self.addCleanup(experiment_submit_thread_patcher.stop)
        self.addCleanup(entries_patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init_args_entry(self):
        builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EXPERIMENT_INFO),
            parent=QObject()
        )
        for argName, (argInfo, *_) in EXPERIMENT_INFO["arginfo"].items():
            self.mockedEntries[argInfo.pop("ty")].assert_any_call(argName, argInfo)


if __name__ == "__main__":
    unittest.main()
