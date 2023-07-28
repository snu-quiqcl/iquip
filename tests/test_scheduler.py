"""Unit tests for monitor module."""

import unittest

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject,  QMimeData

from iquip.apps import scheduler
from iquip.apps.scheduler import ExperimentView as ExpView
from iquip.protocols import ExperimentInfo as ExpInfo

class TestExperimentModel(unittest.TestCase):
    """Unit tests for ExperimentModel class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_model_index(self):
        data1 = []
        for i in range(10):
            data1.append(ExpInfo("exp" + str(i), {"rid": i, "priority": i}))
        data2 = []
        for i in range(100):
            data1.append(ExpInfo("exp" + str(i), {"rid": i, "priority": 0}))
        for data in (data1, data2):
            mdl = scheduler.ExperimentModel()
            mdl.experimentQueue.extend(data)
            self.assertEqual(mdl.rowCount(), len(data))
            for i, exp in enumerate(data):
                self.assertEqual(mdl.data(mdl.index(i)), exp)

    def test_drag_and_drop(self):
        mdl = scheduler.ExperimentModel()
        data = [ExpInfo("exp1", {"rid": 1, "priority": 2}),
                ExpInfo("exp2", {"rid": 2, "priority": 1}),
                ExpInfo("exp3", {"rid": 3, "priority": 1})
               ]
        mdl.experimentQueue.extend(data)
        mime0 = QMimeData()
        mime0.setText("0")
        mime1 = QMimeData()
        mime1.setText("1")
        mime2 = QMimeData()
        mime2.setText("2")
        mdl.dropMimeData(mime0, Qt.MoveAction, 0, 0, mdl.index(0)) # exp1 above exp1
        self.assertEqual(mdl.experimentQueue, data)
        mdl.dropMimeData(mime0, Qt.MoveAction, 2, 0, mdl.index(0)) # exp1 above exp3
        self.assertEqual(mdl.experimentQueue, data)
        mdl.dropMimeData(mime1, Qt.MoveAction, 3, 0, mdl.index(0)) # exp2 below exp3
        self.assertEqual(mdl.experimentQueue, [data[0], data[2], data[1]])
        mdl.dropMimeData(mime2, Qt.MoveAction, 1, 0, mdl.index(0)) # exp2 above exp3
        self.assertEqual(mdl.experimentQueue, data)

class TestSchedulerApp(unittest.TestCase):
    """Unit tests for SchedulerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_add_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        data = [ExpInfo("exp" + str(i), {"rid": i, "priority": 10-i}) for i in range(10)]
        for info in data:
            app.addExperiment(info=info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue, data)
        app.schedulerFrame.model.experimentQueue = []
        permutation = [1, 9, 3, 8, 7, 4, 2, 6, 5, 0]
        inv_permutation = [1, 3, 4, 7, 8, 5, 2, 6, 0, 9]
        data = [ExpInfo("exp" + str(i), {"rid": i, "priority": permutation[i]}
                       ) for i in range(10)]
        for info in data:
            app.addExperiment(info=info)
        self.assertEqual(app.schedulerFrame.model.experimentQueue,
                         [data[inv_permutation[i]] for i in range(10)])

    def test_run_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_run = ExpInfo("exp1", {"rid": 1, "priority": 1})
        experiment_queue = ExpInfo("exp2", {"rid": 2, "priority": 2})
        app.schedulerFrame.model.experimentQueue.append(experiment_run)
        app.schedulerFrame.model.experimentQueue.append(experiment_queue)
        app.runExperiment(experiment_run)
        self.assertEqual(app.schedulerFrame.model.experimentQueue, [experiment_queue])
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, experiment_run)
        app.runExperiment(None)
        self.assertEqual(app.schedulerFrame.runningView.experimentInfo, None)

    def test_modify_experiment(self):
        app = scheduler.SchedulerApp(name="name", parent=QObject())
        experiment_change = ExpInfo("exp1", {"rid": 1, "priority": 1})
        experiment_new_info = ExpInfo("exp1", {"rid": 1, "priority": 2})
        experiment_delete = ExpInfo("exp2", {"rid": 2, "priority": 1})
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
