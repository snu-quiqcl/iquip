"""Unit tests for scheduler module."""

import unittest
from unittest import mock

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject,  QMimeData

from iquip.apps import scheduler
from iquip.protocols import ExperimentInfo

class ExperimentModelTest(unittest.TestCase):
    """Unit tests for ExperimentModel class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_row_count(self):
        data1 = [ExperimentInfo(str(i), {"rid": i, "priority": i}) for i in range(10)]
        data2 = [ExperimentInfo(str(i), {"rid": i, "priority": 0}) for i in range(10)]
        for data in (data1, data2):
            model = scheduler.ExperimentModel()
            model.experimentQueue.extend(data)
            self.assertEqual(model.rowCount(), len(data))

    def test_data(self):
        data1 = [ExperimentInfo(str(i), {"rid": i, "priority": i}) for i in range(10)]
        data2 = [ExperimentInfo(str(i), {"rid": i, "priority": 0}) for i in range(10)]
        for data in (data1, data2):
            model = scheduler.ExperimentModel()
            model.experimentQueue.extend(data)
            for i, exp in enumerate(data):
                self.assertEqual(model.data(model.index(i)), exp)

    def test_drop_mime_data(self):
        model = scheduler.ExperimentModel()
        data = [
            ExperimentInfo("1", {"rid": 1, "priority": 2}),
            ExperimentInfo("2", {"rid": 2, "priority": 1}),
            ExperimentInfo("3", {"rid": 3, "priority": 1})
        ]
        model.experimentQueue.extend(data)
        mime0 = QMimeData()
        mime0.setText("0")
        mime1 = QMimeData()
        mime1.setText("1")
        mime2 = QMimeData()
        mime2.setText("2")
        model.dropMimeData(mime0, Qt.MoveAction, 0, 0, model.index(0)) # exp1 above exp1
        self.assertEqual(model.experimentQueue, data)
        model.dropMimeData(mime0, Qt.MoveAction, 2, 0, model.index(0)) # exp1 above exp3
        self.assertEqual(model.experimentQueue, data)
        model.dropMimeData(mime1, Qt.MoveAction, 3, 0, model.index(0)) # exp2 below exp3
        self.assertEqual(model.experimentQueue, [data[0], data[2], data[1]])
        model.dropMimeData(mime2, Qt.MoveAction, 1, 0, model.index(0)) # exp2 above exp3
        self.assertEqual(model.experimentQueue, data)


class SchedulerAppTest(unittest.TestCase):
    """Unit tests for SchedulerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_add_experiment(self):
        app = scheduler.SchedulerApp(name="name")
        with mock.patch.object(app.schedulerFrame.model, "experimentQueue") as mocked_queue:
            data = [ExperimentInfo(str(i), {"rid": i, "priority": 10 - i}) for i in range(10)]
            for info in data:
                app.addExperiment(info)
                mocked_queue.append.assert_called_with(info)
            self.assertEqual(mocked_queue.sort.call_count, len(data))

    def test_run_experiment(self):
        app = scheduler.SchedulerApp(name="name")
        with mock.patch.object(app.schedulerFrame, "runningView") as mocked_view:
            info = ExperimentInfo("1", {"rid": 1, "priority": 1})
            app.runExperiment(info)
            mocked_view.updateInfo.assert_called_with(info)


class SchedulerFunctionalTest(unittest.TestCase):
    """Functional tests for SchedulerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_add_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        priorities = [1, 9, 3, 8, 7, 4, 2, 6, 5, 0]
        sorted_indices = [1, 3, 4, 7, 8, 5, 2, 6, 0, 9]
        data = [
            ExperimentInfo(str(i), {"rid": i, "priority": priorities[i]}) for i in range(10)
        ]
        for info in data:
            app.addExperiment(info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue,
                         [data[sorted_indices[i]] for i in range(10)])

    def test_run_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_run = ExperimentInfo("1", {"rid": 1, "priority": 1})
        experiment_queue = ExperimentInfo("2", {"rid": 2, "priority": 2})
        app.schedulerFrame.model.experimentQueue.append(experiment_run)
        app.schedulerFrame.model.experimentQueue.append(experiment_queue)
        app.runExperiment(experiment_run)
        self.assertEqual(app.schedulerFrame.model.experimentQueue, [experiment_queue])
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, experiment_run)
        app.runExperiment(None)
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, None)

    def test_modify_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_change = ExperimentInfo("1", {"rid": 1, "priority": 1})
        experiment_new_info = ExperimentInfo("1", {"rid": 1, "priority": 2})
        experiment_delete = ExperimentInfo("2", {"rid": 2, "priority": 1})
        app.schedulerFrame.model.experimentQueue.append(experiment_delete)
        app.schedulerFrame.model.experimentQueue.append(experiment_change)
        app.changeExperiment(1, experiment_new_info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[0].arginfo["priority"], 2)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[1].arginfo["rid"], 2)
        app.changeExperiment(1, None)
        self.assertEqual(app.schedulerFrame.model.experimentQueue[0].arginfo["rid"], 1)
        self.assertEqual(app.schedulerFrame.model.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
