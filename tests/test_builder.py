"""Unit tests for builder module."""

import copy
import functools
import unittest
from unittest import mock

from PyQt5.QtWidgets import QApplication, QListWidget, QListWidgetItem, QWidget

from iquip.apps import builder

EMPTY_EXPERIMENT_INFO = {
    "name": "name",
    "arginfo": {}
}


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


class _ExperimentSubmitThreadTest(unittest.TestCase):
    """Unit tests for _ExperimentSubmitThread class."""


class BuilderAppTest(unittest.TestCase):
    """Unit tests for BuilderApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        self.mocked_entries = {
            f"{type_}Value": mock.MagicMock(return_value=QWidget())
            for type_ in ("Boolean", "String", "Enumeration", "Number", "DateTime")
        }
        experiment_submit_thread_patcher = mock.patch("iquip.apps.builder._ExperimentSubmitThread")
        entries_patcher = mock.patch.multiple(
            "iquip.apps.builder",
            _BooleanEntry=self.mocked_entries["BooleanValue"],
            _StringEntry=self.mocked_entries["StringValue"],
            _EnumerationEntry=self.mocked_entries["EnumerationValue"],
            _NumberEntry=self.mocked_entries["NumberValue"],
            _DateTimeEntry=self.mocked_entries["DateTimeValue"]
        )
        entries_patcher.start()
        self.addCleanup(entries_patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init_args_entry(self):
        builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EXPERIMENT_INFO)
        )
        for argName, (argInfo, *_) in EXPERIMENT_INFO["arginfo"].items():
            self.mocked_entries[argInfo.pop("ty")].assert_any_call(argName, argInfo)

    def test_init_sched_opts_entry(self):
        builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        pipelineInfo = {
            "default": "main"
        }
        priorityInfo = {
            "default": 1,
            "unit": "",
            "scale": 1,
            "step": 1,
            "min": 1,
            "max": 10,
            "ndecimals": 0,
            "type": "int"
        }
        self.mocked_entries["StringValue"].assert_any_call("pipeline", pipelineInfo)
        self.mocked_entries["NumberValue"].assert_any_call("priority", priorityInfo)
        self.mocked_entries["DateTimeValue"].assert_any_call("timed")

    def test_arguments_from_list_widget(self):
        listWidget = QListWidget()
        for name, value in (
            ("name1", "value1"),
            ("name2", None),
        ):
            widget = QWidget()
            widget.name = name
            widget.value = mock.MagicMock(return_value=value)
            item = QListWidgetItem(listWidget)
            listWidget.addItem(item)
            listWidget.setItemWidget(item, widget)
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        args = app.argumentsFromListWidget(listWidget)
        self.assertEqual(args["name1"], "value1")
        self.assertNotIn("name2", args)


if __name__ == "__main__":
    unittest.main()
