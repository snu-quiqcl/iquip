"""Unit tests for scheduler module."""

import unittest
from collections import namedtuple
from unittest import mock

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject, QMimeData

from iquip.apps import scheduler
from iquip.protocols import SubmittedExperimentInfo

_CONSTANTS_DICT = {"proxy_ip": "127.0.0.1", "proxy_port": 8000}

CONSTANTS = namedtuple("ConstantNamespace", _CONSTANTS_DICT.keys())(**_CONSTANTS_DICT)

class ExperimentModelTest(unittest.TestCase):
    """Unit tests for ExperimentModel class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_row_count(self):
        data1 = tuple(SubmittedExperimentInfo(rid=i, priority=i) for i in range(10))
        data2 = tuple(SubmittedExperimentInfo(rid=i, priority=0) for i in range(10))
        for data in (data1, data2):
            model = scheduler.ExperimentModel()
            model.experimentQueue.extend(data)
            self.assertEqual(model.rowCount(), len(data))

    def test_data(self):
        data1 = tuple(SubmittedExperimentInfo(rid=i, priority=i) for i in range(10))
        data2 = tuple(SubmittedExperimentInfo(rid=i, priority=0) for i in range(10))
        for data in (data1, data2):
            model = scheduler.ExperimentModel()
            model.experimentQueue.extend(data)
            for i, exp in enumerate(data):
                self.assertEqual(model.data(model.index(i)), exp)

    def test_drop_mime_data(self):
        model = scheduler.ExperimentModel()
        data = (
            SubmittedExperimentInfo(rid=1, priority=2),
            SubmittedExperimentInfo(rid=2, priority=1),
            SubmittedExperimentInfo(rid=3, priority=1)
        )
        model.experimentQueue.extend(data)
        mime0 = QMimeData()
        mime0.setText("0")
        mime1 = QMimeData()
        mime1.setText("1")
        mime2 = QMimeData()
        mime2.setText("2")
        model.dropMimeData(mime0, Qt.MoveAction, 0, 0, model.index(0)) # exp1 above exp1
        self.assertEqual(model.experimentQueue, list(data))
        model.dropMimeData(mime0, Qt.MoveAction, 2, 0, model.index(0)) # exp1 above exp3
        self.assertEqual(model.experimentQueue, list(data))
        model.dropMimeData(mime1, Qt.MoveAction, 3, 0, model.index(0)) # exp2 below exp3
        self.assertEqual(model.experimentQueue, [data[0], data[2], data[1]])
        model.dropMimeData(mime2, Qt.MoveAction, 1, 0, model.index(0)) # exp2 above exp3
        self.assertEqual(model.experimentQueue, list(data))


class SchedulerAppTest(unittest.TestCase):
    """Unit tests for SchedulerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        constants_patcher = mock.patch("iquip.apps.scheduler.SchedulerApp._constants", CONSTANTS)
        thread_patcher = mock.patch("iquip.apps.scheduler._ExperimentQueueFetcherThread")
        worker_patcher = mock.patch("iquip.apps.scheduler.SchedulerPostWorker")
        constants_patcher.start()
        thread_patcher.start()
        worker_patcher.start()
        self.addCleanup(constants_patcher.stop)
        self.addCleanup(thread_patcher.stop)
        self.addCleanup(worker_patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_add_experiment(self):
        app = scheduler.SchedulerApp(name="name")
        with mock.patch.object(app.schedulerFrame.model, "experimentQueue") as mocked_queue:
            data = tuple(SubmittedExperimentInfo(rid=i, priority=10 - i) for i in range(10))
            for info in data:
                app._addExperiment(info)
                mocked_queue.append.assert_called_with(info)
            self.assertEqual(mocked_queue.sort.call_count, len(data))

    def test_run_experiment(self):
        app = scheduler.SchedulerApp(name="name")
        with mock.patch.object(app.schedulerFrame, "runningView") as mocked_view:
            info = SubmittedExperimentInfo(rid=1, priority=1)
            app._runExperiment(info)
            mocked_view.updateInfo.assert_called_with(info)


class SchedulerFunctionalTest(unittest.TestCase):
    """Functional tests for SchedulerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        constants_patcher = mock.patch("iquip.apps.scheduler.SchedulerApp._constants", CONSTANTS)
        thread_patcher = mock.patch("iquip.apps.scheduler._ExperimentQueueFetcherThread")
        worker_patcher = mock.patch("iquip.apps.scheduler.SchedulerPostWorker")
        constants_patcher.start()
        thread_patcher.start()
        worker_patcher.start()
        self.addCleanup(constants_patcher.stop)
        self.addCleanup(thread_patcher.stop)
        self.addCleanup(worker_patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_add_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        priorities = [1, 9, 3, 8, 7, 4, 2, 6, 5, 0]
        sorted_indices = [1, 3, 4, 7, 8, 5, 2, 6, 0, 9]
        data = tuple(
            SubmittedExperimentInfo(rid=i, priority=priorities[i]) for i in range(10)
        )
        for info in data:
            app._addExperiment(info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue,
                         [data[sorted_indices[i]] for i in range(10)])

    def test_run_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_run = SubmittedExperimentInfo(rid=1, priority=1)
        app._runExperiment(experiment_run)
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, experiment_run)
        app._runExperiment(None)
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, None)

    def test_modify_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_change = SubmittedExperimentInfo(rid=1, priority=1)
        experiment_new_info = SubmittedExperimentInfo(rid=1, priority=2)
        experiment_delete = SubmittedExperimentInfo(rid=2, priority=1)
        app._addExperiment(experiment_delete)
        app._addExperiment(experiment_change)
        app._changeExperiment(0, experiment_new_info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[0], experiment_new_info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[1], experiment_delete)
        app._changeExperiment(1, None)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[0], experiment_new_info)
        self.assertEqual(app.schedulerFrame.model.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
