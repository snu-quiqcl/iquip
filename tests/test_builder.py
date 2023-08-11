"""Unit tests for builder module."""

import copy
import json
import logging
import unittest
from typing import Any, Callable, Dict, Optional
from unittest import mock

import requests
from PyQt5.QtCore import QDateTime, QObject, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QListWidget, QListWidgetItem, QWidget
from PyQt5.QtTest import QTest

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

EXPERIMENT_INFO_2 = {
    "name": "name2",
    "arginfo": {
        "arg4": [{"ty": "BooleanValue", "default": "default0"}, None, None],
        "arg5": [{"ty": "StringValue", "default": "default1"}, None, None],
        "arg6": [{"ty": "EnumerationValue", "default": "default2"}, None, None],
        "arg7": [{"ty": "NumberValue", "default": "default3"}, None, None]
    }
}

EXPERIMENT_PATH = "experiment_path"

EXPERIMENT_ARGS = {"arg1": "arg_value1", "arg2": "arg_value2"}

SCHED_OPTS = {"opt1": "opt_value1", "opt2": "opt_value2"}

class BaseEntryTest(unittest.TestCase):
    """Unit tests for _BaseEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_init(self):
        for argName, (argInfo, *_) in EXPERIMENT_INFO["arginfo"].items():
            entry = builder._BaseEntry(argName, argInfo)
            self.assertEqual(entry.name, argName)
            self.assertEqual(entry.argInfo, argInfo)

    def test_value(self):
        for argName, (argInfo, *_) in EXPERIMENT_INFO["arginfo"].items():
            entry = builder._BaseEntry(argName, argInfo)
            with self.assertRaises(NotImplementedError):
                entry.value()


class BooleanEntryFunctionalTest(unittest.TestCase):
    """Functional tests for _BooleanEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_value(self):
        for argName, argInfo, value in (
            ("name1", {"default": True}, True),
            ("name2", {}, False)
        ):
            entry = builder._BooleanEntry(argName, argInfo)
            self.assertEqual(entry.value(), value)


class EnumerationEntryFunctionalTest(unittest.TestCase):
    """Functional tests for _EnumerationEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_value(self):
        for argName, argInfo, value in (
            ("name1", {"choices": ["value1", "value2", "value3"], "default": "value2"}, "value2"),
            ("name2", {"choices": ["value1", "value2", "value3"]}, "value1")
        ):
            entry = builder._EnumerationEntry(argName, argInfo)
            self.assertEqual(entry.value(), value)

    def test_value_exception(self):
        """Tests when the choices argument is empty."""
        argName, argInfo = "name", {"choices": []}
        msg = f"_EnumerationEntry {argName} with the empty choice"
        with self.assertRaises(ValueError) as cm:
            entry = builder._EnumerationEntry(argName, argInfo)
            entry.value()
        self.assertEqual(str(cm.exception), msg)


class NumberEntryFunctionalTest(unittest.TestCase):
    """Functional tests for _NumberEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_init(self):
        argInfo1 = {"unit": "s", "scale": 1, "step": 0.1, "min": None, "max": 100,
                    "ndecimals": 3, "type": "float", "default": 20}
        argInfo2 = {"unit": "s", "scale": 1, "step": 0.1, "min": 10, "max": None,
                    "ndecimals": 3, "type": "float", "default": 20}
        argInfo3 = {"unit": "s", "scale": 1, "step": 0.1, "min": 100, "max": 10,
                    "ndecimals": 3, "type": "float", "default": 20}
        for argName, argInfo, minValue, maxValue in (
            ("name1", argInfo1, 0.0, 100),
            ("name2", argInfo2, 10, 99.99),
            ("name2", argInfo3, 10, 100)
        ):
            entry = builder._NumberEntry(argName, argInfo)
            self.assertEqual(entry.spinBox.minimum(), minValue)
            self.assertEqual(entry.spinBox.maximum(), maxValue)

    def test_value(self):
        argInfo1 = {"unit": "us", "scale": 1e-6, "step": 1e-7, "min": 10 * 1e-6, "max": 100 * 1e-6,
                    "ndecimals": 3, "type": "float", "default": 20 * 1e-6}
        argInfo2 = {"unit": "us", "scale": 1e-6, "step": 1e-7, "min": 10 * 1e-6, "max": 100 * 1e-6,
                    "ndecimals": 3, "type": "float"}
        argInfo3 = {"unit": "s", "scale": 1, "step": 1, "min": 10, "max": 100,
                    "ndecimals": 0, "type": "int", "default": 20}
        for argName, argInfo, value in (
            ("name1", argInfo1, 20 * 1e-6),
            ("name2", argInfo2, 10 * 1e-6),
            ("name2", argInfo3, 20)
        ):
            entry = builder._NumberEntry(argName, argInfo)
            self.assertEqual(entry.value(), value)

    def test_typical_scale(self):
        """Tests when the scale for the unit is not typical."""
        argInfo1 = {"unit": "us", "scale": 1e-6, "step": 1e-7, "min": 10 * 1e-6, "max": 100 * 1e-6,
                    "ndecimals": 3, "type": "float", "default": 20 * 1e-6}
        argInfo2 = {"unit": "us", "scale": 1e-7, "step": 1e-7, "min": 10 * 1e-6, "max": 100 * 1e-6,
                    "ndecimals": 3, "type": "float", "default": 20 * 1e-6}
        with mock.patch("iquip.apps.builder.compute_scale") as mocked_compute_scale:
            mocked_compute_scale.return_value = 1e-6
            for argName, argInfo, is_typical in (
                ("name1", argInfo1, True),
                ("name2", argInfo2, False)
            ):
                entry = builder._NumberEntry(argName, argInfo)
                warningLabelText = "" if is_typical else "Not a typical scale for the unit."
                self.assertEqual(entry.warningLabel.text(), warningLabelText)


class DateTimeEntryFunctionalTest(unittest.TestCase):
    """Functional tests for _DateTimeEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_value(self):
        entry = builder._DateTimeEntry("name")
        date_time = "2023-01-01T09:00:00"
        with mock.patch.object(entry.dateTimeEdit, "dateTime") as mocked_date_time:
            mocked_date_time.return_value = QDateTime.fromString(date_time, Qt.ISODate)
            # If the checkBox is disabled.
            self.assertEqual(entry.dateTimeEdit.isEnabled(), False)
            self.assertEqual(entry.value(), None)
            entry.checkBox.setChecked(True)
            # If the checkBox is enabled.
            self.assertEqual(entry.dateTimeEdit.isEnabled(), True)
            self.assertEqual(entry.value(), date_time)


class StringEntryFunctionalTest(unittest.TestCase):
    """Functional tests for _StringEntry class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_value(self):
        for argName, argInfo, value in (
            ("name1", {"default": "value"}, "value"),
            ("name2", {}, "")
        ):
            entry = builder._StringEntry(argName, argInfo)
            self.assertEqual(entry.value(), value)


class ExperimentSubmitThreadTest(unittest.TestCase):
    """Unit tests for _ExperimentSubmitThread class."""

    # pylint: disable=duplicate-code
    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("requests.get")
        self.mocked_get = patcher.start()
        self.mocked_response = self.mocked_get.return_value
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init(self):
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder._ExperimentSubmitThread.submitted") as mocked_submitted:
            thread = get_thread(callback, parent)
        self.assertEqual(thread.experimentPath, EXPERIMENT_PATH)
        self.assertEqual(thread.experimentArgs, EXPERIMENT_ARGS)
        self.assertEqual(thread.schedOpts, SCHED_OPTS)
        mocked_submitted.connect.assert_called_once_with(callback, type=Qt.QueuedConnection)

    def test_run(self):
        self.mocked_response.json.return_value = 100
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder._ExperimentSubmitThread.submitted") as mocked_submitted:
            thread = get_thread(callback, parent)
            thread.run()
            thread.wait()
        params = {
            "file": EXPERIMENT_PATH,
            "args": json.dumps(EXPERIMENT_ARGS),
            **SCHED_OPTS
        }
        self.mocked_get.assert_called_once_with("http://127.0.0.1:8000/experiment/submit/",
                                                 params=params,
                                                 timeout=10)
        mocked_submitted.emit.assert_called_once_with(100)

    def test_run_request_exception(self):
        """Tests when a requests.exceptions.RequestException occurs."""
        self.mocked_response.raise_for_status.side_effect = requests.exceptions.RequestException()
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder._ExperimentSubmitThread.submitted") as mocked_submitted:
            thread = get_thread(callback, parent)
            thread.run()
            thread.wait()
        params = {
            "file": EXPERIMENT_PATH,
            "args": json.dumps(EXPERIMENT_ARGS),
            **SCHED_OPTS
        }
        self.mocked_get.assert_called_once_with("http://127.0.0.1:8000/experiment/submit/",
                                                 params=params,
                                                 timeout=10)
        mocked_submitted.emit.assert_not_called()

    def test_run_type_error(self):
        """Tests when a TypeError occurs."""
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.builder._ExperimentSubmitThread.submitted") as mocked_submitted:
            experimentArgs = {"arg1": lambda: None}  # Not JSONifiable.
            thread = get_thread(callback, parent, experimentArgs)
            thread.run()
            thread.wait()
        self.mocked_get.assert_not_called()
        mocked_submitted.emit.assert_not_called()


def get_thread(
        callback: Callable[[int], None],
        parent: Optional[QObject] = None,
        experimentArgs: Optional[Dict[str, Any]] = None
    ) -> builder._ExperimentSubmitThread:
    """Returns an _ExperimentSubmitThread instance.
    
    Args:
        callback: The function called after the thread is done.
        parent: The parent object.
        experimentArgs: The arguments of the experiment.
    """
    if experimentArgs is None:
        experimentArgs = copy.deepcopy(EXPERIMENT_ARGS)
    return builder._ExperimentSubmitThread(
        experimentPath=EXPERIMENT_PATH,
        experimentArgs=experimentArgs,
        schedOpts=SCHED_OPTS,
        callback=callback,
        parent=parent
    )


class BuilderAppTest(unittest.TestCase):
    """Unit tests for BuilderApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        self.mocked_entries = {
            f"{type_}Value": mock.MagicMock(return_value=QWidget())
            for type_ in ("Boolean", "String", "Enumeration", "Number", "DateTime")
        }
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
        for argName, (argInfo, *_) in copy.deepcopy(EXPERIMENT_INFO)["arginfo"].items():
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
        for name, value in (("name1", "value1"), ("name2", None)):
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
        self.assertEqual(args["name2"], None)

    @mock.patch("iquip.apps.builder.ExperimentInfoThread")
    def test_reload_args(self, mocked_experiment_info_thread_cls):
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        with mock.patch.object(app, "onReloaded") as mocked_on_reloaded:
            app.reloadArgs()
        mocked_experiment_info_thread_cls.assert_called_once_with(
            "experimentPath",
            mocked_on_reloaded,
            app
        )

    def test_on_reloaded(self):
        print(EXPERIMENT_INFO)
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EXPERIMENT_INFO)
        )
        experimentInfo = builder.ExperimentInfo(**EXPERIMENT_INFO_2)
        with mock.patch.object(app, "initArgsEntry") as mocked_init_args_entry:
            app.onReloaded("experimentPath", "experimentClsName", experimentInfo)
        self.assertEqual(app.builderFrame.argsListWidget.count(), 0)
        mocked_init_args_entry.assert_called_once_with(experimentInfo)

    @mock.patch("iquip.apps.builder._ExperimentSubmitThread")
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
            mocked_arguments_from_list_widget.side_effect = [experimentArgs, schedOpts]
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

    @mock.patch("iquip.apps.builder._ExperimentSubmitThread")
    def test_submit_exception(self, mocked_experiment_submit_thread_cls):
        """Tests when argumentsFromListWidget() causes a ValueError."""
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        with mock.patch.object(app, "argumentsFromListWidget") as mocked_arguments_from_list_widget:
            mocked_arguments_from_list_widget.side_effect = ValueError
            logger = logging.getLogger()
            with self.assertLogs(logger, "ERROR") as cm:
                app.submit()
        self.assertIn("The submission is rejected because of an invalid argument.", cm.output[0])
        mocked_experiment_submit_thread_cls.assert_not_called()

    def test_frames(self):
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        self.assertEqual(app.frames(), (app.builderFrame,))


class SubmitFunctionalTest(unittest.TestCase):
    """Functional tests for an experiment submission."""

    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("requests.get")
        self.mocked_get = patcher.start()
        self.mocked_response = self.mocked_get.return_value
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_submit(self):
        self.mocked_response.json.return_value = 100
        app = builder.BuilderApp(
            name="name",
            experimentPath="experimentPath",
            experimentClsName="experimentClsName",
            experimentInfo=copy.deepcopy(EMPTY_EXPERIMENT_INFO)
        )
        QTest.mouseClick(app.builderFrame.submitButton, Qt.LeftButton)
        # The slot of ExperimentSubmitThread.submitted is executed in PyQt event loop.
        QTimer.singleShot(100, self.qapp.quit)
        self.qapp.exec_()
        # TODO(BECATRUE): After onSubmitted() uses a logging, a test for logging will be added.


class FunctionTest(unittest.TestCase):
    """Unit tests for functions."""

    def test_compute_scale(self):
        unit_scale_pairs = (
            ("s", 1), ("", None), ("fs", None), ("kJ", None), ("ks", None), ("ns", 1e-9)
        )
        for unit, scale in unit_scale_pairs:
            self.assertEqual(builder.compute_scale(unit), scale)


if __name__ == "__main__":
    unittest.main()
