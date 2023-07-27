"""Unit tests for builder module."""

import copy
import json
import unittest
from unittest import mock

from PyQt5.QtCore import QObject, Qt
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

    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("requests.get")
        self.mocked_get = patcher.start()
        self.mocked_response = self.mocked_get.return_value
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init_thread(self):
        experimentArgs = {"arg1": "value1", "arg2": "value2"}
        schedOpts = {"opt1": "value1", "opt2": "value2"}
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder.ExperimentSubmitThread.submitted") as mocked_submitted:
            thread = builder.ExperimentSubmitThread(
                experimentPath="experiment_path",
                experimentArgs=experimentArgs,
                schedOpts=schedOpts,
                callback=callback,
                parent=parent
            )
        self.assertEqual(thread.experimentPath, "experiment_path")
        self.assertEqual(thread.experimentArgs, experimentArgs)
        self.assertEqual(thread.schedOpts, schedOpts)
        mocked_submitted.connect.assert_called_once_with(callback, type=Qt.QueuedConnection)

    def test_run(self):
        self.mocked_response.json.return_value = 100
        experimentArgs = {"arg1": "arg_value1", "arg2": "arg_value2"}
        schedOpts = {"opt1": "opt_value1", "opt2": "opt_value2"}
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder.ExperimentSubmitThread.submitted") as mocked_submitted:
            thread = builder.ExperimentSubmitThread(
                experimentPath="experiment_path",
                experimentArgs=experimentArgs,
                schedOpts=schedOpts,
                callback=callback,
                parent=parent
            )
            thread.run()
            thread.wait()
        params = {
            "file": "experiment_path",
            "args": json.dumps(experimentArgs),
            "opt1": "opt_value1",
            "opt2": "opt_value2"
        }
        self.mocked_get.assert_called_once_with("http://127.0.0.1:8000/experiment/submit/",
                                                 params=params,
                                                 timeout=10)
        mocked_submitted.emit.assert_called_once_with(100)


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

    @mock.patch("iquip.apps.builder.ExperimentSubmitThread")
    def test_submit(self, mocked_experiment_submit_thread_cls):
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        experimentArgs = {"key1": "value1"}
        schedOpts = {"key2": "value2"}
        with mock.patch.multiple(
            app,
            argumentsFromListWidget=mock.DEFAULT,
            onSubmitted=mock.DEFAULT
        ) as mocked:
            mocked_arguments_from_list_widget = mocked["argumentsFromListWidget"]
            mocked_on_submitted = mocked["onSubmitted"]
            mocked_arguments_from_list_widget.side_effect=[experimentArgs, schedOpts]
            app.submit()
        mocked_arguments_from_list_widget.assert_any_call(app.builderFrame.argsListWidget)
        mocked_arguments_from_list_widget.assert_any_call(app.builderFrame.schedOptsListWidget)
        mocked_experiment_submit_thread_cls.assert_called_once_with(
            "experimentPath",
            experimentArgs,
            schedOpts,
            mocked_on_submitted,
            app
        )

    def test_frames(self):
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        self.assertEqual(app.frames(), (app.builderFrame,))


if __name__ == "__main__":
    unittest.main()
