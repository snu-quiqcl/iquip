"""Regression tests for Builder window persistence and restoration."""

import copy
import json
import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from PyQt5 import sip
from PyQt5.QtCore import QDateTime, QObject, QRect, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication

import qiwis
from iquip import builder_state
from iquip.apps import builder
from iquip.protocols import ExperimentInfo


EXPERIMENT_INFO = {
    "name": "Persistence experiment",
    "arginfo": {
        "enabled": [{"ty": "BooleanValue", "default": False}, None, None],
        "label": [{"ty": "StringValue", "default": "initial"}, None, None],
        "mode": [{
            "ty": "EnumerationValue", "choices": ["a", "b"], "default": "a"
        }, None, None],
        "count": [{
            "ty": "NumberValue", "unit": "", "scale": 1, "step": 1,
            "min": 0, "max": 20, "ndecimals": 0, "type": "int", "default": 2,
        }, None, None],
        "frequency": [{
            "ty": "NumberValue", "unit": "MHz", "scale": 1e6, "step": 1e6,
            "min": 1e6, "max": 100e6, "ndecimals": 3, "type": "float",
            "default": 10e6,
        }, None, None],
        "scan": [{
            "ty": "Scannable", "unit": "V", "scale": 1.0, "global_step": 0.1,
            "global_min": -10.0, "global_max": 10.0, "ndecimals": 3,
            "default": {"ty": "NoScan", "value": 0.0, "repetitions": 1},
        }, None, None],
    },
}


class FakeExperimentInfoThread(QObject):
    """Signal-compatible deterministic replacement for the network thread."""

    fetched = pyqtSignal(dict)
    failed = pyqtSignal(str)
    finished = pyqtSignal()
    responses = {}
    automatic = True
    instances = []

    def __init__(self, experimentPath, _ip, _port, parent=None):
        super().__init__(parent)
        self.experimentPath = experimentPath
        self.running = False
        self.interruptionRequested = False
        self.waitCalled = False
        self.instances.append(self)

    def start(self):
        self.running = True
        if self.automatic:
            QTimer.singleShot(0, self.complete)

    def complete(self):
        self.running = False
        response = self.responses[self.experimentPath]
        if isinstance(response, Exception):
            self.failed.emit(repr(response))
        else:
            self.fetched.emit(response)
        self.finished.emit()

    def requestInterruption(self):
        self.interruptionRequested = True

    def wait(self):
        self.waitCalled = True
        self.running = False
        return True


class InterruptibleTestThread(QThread):
    """A real QThread released by the shutdown interruption request."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self):
        self.entered.set()
        self.release.wait()

    def requestInterruption(self):
        super().requestInterruption()
        self.release.set()


class BuilderStateTest(unittest.TestCase):
    """Tests the integration controller with real qiwis/Builder widgets."""

    def setUp(self):
        self.qapp = QApplication([])
        self.qapp.setQuitOnLastWindowClosed(False)
        self.tempDirectory = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempDirectory.cleanup)
        constants = {
            "proxy_ip": "127.0.0.1",
            "proxy_port": 8000,
        }
        self.constants = qiwis.set_global_constant_namespace(constants)
        self.managers = []
        FakeExperimentInfoThread.responses = {}
        FakeExperimentInfoThread.automatic = True
        FakeExperimentInfoThread.instances = []

    def tearDown(self):
        for manager in reversed(self.managers):
            stateManager = manager.builderStateManager
            if stateManager is not None:
                stateManager._shuttingDown = True  # Avoid a test-only teardown save.
                stateManager._timer.stop()
            manager.mainWindow.close()
            sip.delete(manager.mainWindow)
            sip.delete(manager)
        self.qapp.processEvents()
        self.managers.clear()
        sip.delete(self.qapp)

    def makeManager(self, statePath, appInfos=None):
        manager = builder_state.IquipQiwis(appInfos or {}, self.constants)
        stateManager = builder_state.BuilderStateManager(manager, Path(statePath), manager)
        self.managers.append(manager)
        return manager, stateManager

    @staticmethod
    def builderInfo(path="routine.py", instanceId=None):
        args = {
            "experimentPath": path,
            "experimentClsName": "Routine",
            "experimentInfo": copy.deepcopy(EXPERIMENT_INFO),
        }
        if instanceId is not None:
            args["builderInstanceId"] = instanceId
        return qiwis.AppInfo(
            module="iquip.apps.builder", cls="BuilderApp", pos="center", args=args
        )

    def openBuilder(self, manager, name, path="routine.py", instanceId=None):
        manager.createApp(name, self.builderInfo(path, instanceId))
        return manager._apps[name]

    @staticmethod
    def waitFor(predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        qapp = QApplication.instance()
        while not predicate() and time.monotonic() < deadline:
            qapp.processEvents()
        if not predicate():
            raise AssertionError("condition did not become true")

    @staticmethod
    def record(name, path="routine.py", instanceId="instance-1", arguments=None):
        return {
            "instance_id": instanceId,
            "name": name,
            "experiment": {"path": path, "class": "Routine"},
            "arguments": arguments or {
                "enabled": True,
                "label": name,
                "mode": "b",
                "count": 7,
                "frequency": 25e6,
                "scan": {"ty": "ExplicitScan", "sequence": [1.25, 2.5]},
            },
            "submission": {"pipeline": "main", "priority": 4, "timed": None},
            "window": None,
        }

    @staticmethod
    def document(*records):
        return {
            "schema": builder_state.SCHEMA_NAME,
            "version": builder_state.SCHEMA_VERSION,
            "builders": list(records),
        }

    def writeDocument(self, statePath, *records):
        statePath.write_text(json.dumps(self.document(*records)), encoding="utf-8")

    def test_round_trip_all_types_submission_and_active_editor(self):
        statePath = Path(self.tempDirectory.name) / "nested" / "builders.json"
        manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        app = self.openBuilder(manager, "builder - routine.py:Routine", instanceId="stable-id")
        entries = app._entries(app.builderFrame.argsListWidget)
        entries.update(app._entries(app.builderFrame.scanListWidget))
        entries["enabled"].setValue(True)
        entries["label"].setValue("edited but not submitted")
        entries["mode"].setValue("b")
        entries["frequency"].setValue(25e6)
        entries["scan"].setValue({"ty": "ExplicitScan", "sequence": [1.25, 2.5]})
        # Mimic a valid value typed into the focused spin-box editor without focus loss.
        entries["count"].spinBox.lineEdit().setText("7")
        entries["count"].spinBox.setFocus()
        sched = app._entries(app.builderFrame.schedOptsListWidget)
        sched["pipeline"].setValue("calibration")
        sched["priority"].setValue(6)
        dueDate = QDateTime.currentDateTime().addDays(1).toString(Qt.ISODate)
        sched["timed"].setValue(dueDate)

        stateManager.shutdown()
        state = json.loads(statePath.read_text(encoding="utf-8"))
        saved = state["builders"][0]
        self.assertEqual(saved["instance_id"], "stable-id")
        self.assertEqual(saved["arguments"]["count"], 7)
        self.assertEqual(saved["arguments"]["scan"]["sequence"], [1.25, 2.5])
        self.assertEqual(saved["submission"]["pipeline"], "calibration")
        self.assertEqual(saved["submission"]["priority"], 6)
        self.assertEqual(saved["submission"]["timed"], dueDate)
        self.assertEqual(state["version"], 1)

    def test_autosave_does_not_commit_transient_spinbox_text(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        app = self.openBuilder(manager, "builder")
        countEntry = app._entries(app.builderFrame.argsListWidget)["count"]
        countEntry.setValue(7)
        stateManager.saveNow()

        countEntry.spinBox.lineEdit().clear()
        self.assertEqual(countEntry.spinBox.lineEdit().text(), "")
        self.assertFalse(
            countEntry.spinBox.lineEdit().property("iquipStateSignalConnected")
        )
        self.assertTrue(stateManager.saveNow())

        self.assertEqual(countEntry.spinBox.lineEdit().text(), "")
        saved = json.loads(statePath.read_text(encoding="utf-8"))["builders"][0]
        self.assertEqual(saved["arguments"]["count"], 7)

    def test_multiple_same_experiment_remain_independent(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        first = self.openBuilder(manager, "builder (one) - routine.py:Routine", instanceId="one")
        second = self.openBuilder(manager, "builder (two) - routine.py:Routine", instanceId="two")
        first._entries(first.builderFrame.argsListWidget)["label"].setValue("first")
        second._entries(second.builderFrame.argsListWidget)["label"].setValue("second")
        stateManager.saveNow()
        records = json.loads(statePath.read_text(encoding="utf-8"))["builders"]
        self.assertEqual([record["instance_id"] for record in records], ["one", "two"])
        self.assertEqual(
            [record["arguments"]["label"] for record in records], ["first", "second"]
        )

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_configured_builder_is_reconciled_without_duplication(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        firstManager, firstStateManager = self.makeManager(
            statePath,
            {"configured": self.builderInfo()},
        )
        firstStateManager.start()
        firstApp = firstManager._apps["configured"]
        firstApp._entries(firstApp.builderFrame.argsListWidget)["label"].setValue(
            "saved configured value"
        )
        savedInstanceId = firstApp.builderInstanceId
        self.assertTrue(firstStateManager.saveNow())
        firstStateManager.shutdown()

        secondManager, secondStateManager = self.makeManager(
            statePath,
            {"configured": self.builderInfo()},
        )
        secondStateManager.start()
        self.waitFor(lambda: not secondStateManager.restoring)

        configuredBuilders = {
            name: app for name, app in secondManager._apps.items()
            if isinstance(app, builder.BuilderApp)
        }
        self.assertEqual(set(configuredBuilders), {"configured"})
        restoredApp = configuredBuilders["configured"]
        self.assertEqual(restoredApp.builderInstanceId, savedInstanceId)
        self.assertEqual(
            restoredApp._entries(restoredApp.builderFrame.argsListWidget)["label"].value(),
            "saved configured value",
        )
        self.assertEqual(FakeExperimentInfoThread.instances, [])

        self.assertTrue(secondStateManager.saveNow())
        records = json.loads(statePath.read_text(encoding="utf-8"))["builders"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "configured")

    def test_nonexistent_file_and_intentional_close_versus_shutdown(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        self.assertTrue(stateManager.writesEnabled)
        self.assertFalse(statePath.exists())
        self.openBuilder(manager, "keep", instanceId="keep-id")
        self.openBuilder(manager, "close", instanceId="close-id")
        manager.destroyApp("close")
        stateManager.saveNow()
        self.assertEqual(
            [record["name"] for record in json.loads(statePath.read_text())["builders"]],
            ["keep"],
        )
        stateManager.shutdown()
        manager.destroyApp("keep")
        self.assertEqual(
            [record["name"] for record in json.loads(statePath.read_text())["builders"]],
            ["keep"],
        )

    def test_shutdown_joins_running_restore_thread(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        _manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        thread = InterruptibleTestThread(stateManager)
        stateManager._threads.add(thread)
        thread.start()
        self.assertTrue(thread.entered.wait(timeout=1))

        stateManager.shutdown()

        self.assertTrue(thread.release.is_set())
        self.assertFalse(thread.isRunning())
        self.assertEqual(stateManager._threads, set())

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_valid_bad_valid_restore_cleanup_logger_backup_and_no_submit(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        bad = self.record("bad", path="bad.py", instanceId="bad-id")
        bad["arguments"]["mode"] = "removed-choice"
        self.writeDocument(
            statePath,
            self.record("first", path="one.py", instanceId="one"),
            bad,
            self.record("second", path="two.py", instanceId="two"),
        )
        experimentInfo = {"Routine": ExperimentInfo(**copy.deepcopy(EXPERIMENT_INFO))}
        FakeExperimentInfoThread.responses = {
            "one.py": experimentInfo,
            "bad.py": experimentInfo,
            "two.py": experimentInfo,
        }
        logDirectory = Path(self.tempDirectory.name) / "logs"
        logDirectory.mkdir()
        loggerInfo = qiwis.AppInfo(
            module="iquip.apps.logger",
            cls="LoggerApp",
            pos="bottom",
            args={"logFilePath": str(logDirectory)},
        )
        manager, stateManager = self.makeManager(statePath, {"logger": loggerInfo})
        loggerApp = manager._apps["logger"]
        with mock.patch.object(builder._ExperimentSubmitThread, "start") as submitStart:
            stateManager.start()
            self.waitFor(lambda: not stateManager.restoring)
        self.assertEqual(
            [name for name, app in manager._apps.items() if isinstance(app, builder.BuilderApp)],
            ["first", "second"],
        )
        firstApp = manager._apps["first"]
        self.assertEqual(firstApp.persistentState(), (
            self.record("first", path="one.py", instanceId="one")["arguments"],
            self.record("first", path="one.py", instanceId="one")["submission"],
        ))
        submitStart.assert_not_called()
        self.assertIn(
            "Failed to restore Builder record 1",
            loggerApp.loggerFrame.logEdit.toPlainText(),
        )
        backups = list(statePath.parent.glob("builders.json.recovery-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(len(json.loads(backups[0].read_text())["builders"]), 3)
        rootLogger = logging.getLogger()
        rootLogger.removeHandler(loggerApp.frameHandler)
        rootLogger.removeHandler(loggerApp.fileHandler)
        loggerApp.fileHandler.close()

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_writes_suppressed_and_quit_during_async_restore(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        self.writeDocument(statePath, self.record("pending"))
        original = statePath.read_bytes()
        FakeExperimentInfoThread.automatic = False
        FakeExperimentInfoThread.responses = {
            "routine.py": {"Routine": ExperimentInfo(**copy.deepcopy(EXPERIMENT_INFO))}
        }
        _manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        self.assertTrue(stateManager.restoring)
        self.waitFor(lambda: len(FakeExperimentInfoThread.instances) == 1)
        stateManager.scheduleSave()
        stateManager.saveNow()
        self.assertEqual(statePath.read_bytes(), original)
        thread = FakeExperimentInfoThread.instances[0]
        stateManager.shutdown()
        self.assertTrue(thread.interruptionRequested)
        self.assertTrue(thread.waitCalled)
        self.assertEqual(statePath.read_bytes(), original)

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_close_during_restore_is_saved_after_restore_finishes(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        self.writeDocument(
            statePath,
            self.record("first", path="one.py", instanceId="one"),
            self.record("second", path="two.py", instanceId="two"),
        )
        experimentInfo = {"Routine": ExperimentInfo(**copy.deepcopy(EXPERIMENT_INFO))}
        FakeExperimentInfoThread.automatic = False
        FakeExperimentInfoThread.responses = {
            "one.py": experimentInfo,
            "two.py": experimentInfo,
        }
        manager, stateManager = self.makeManager(statePath)
        stateManager.start()
        self.waitFor(lambda: len(FakeExperimentInfoThread.instances) == 2)
        threads = {
            thread.experimentPath: thread for thread in FakeExperimentInfoThread.instances
        }

        threads["one.py"].complete()
        self.waitFor(lambda: "first" in manager._apps)
        self.assertTrue(stateManager.restoring)
        manager.destroyApp("first")
        threads["two.py"].complete()
        self.waitFor(lambda: not stateManager.restoring)
        self.waitFor(lambda: (
            not stateManager._timer.isActive()
            and [record["name"] for record in json.loads(statePath.read_text())["builders"]]
            == ["second"]
        ))

        self.assertEqual(
            [record["name"] for record in json.loads(statePath.read_text())["builders"]],
            ["second"],
        )

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_offscreen_geometry_falls_back_without_losing_builder(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        record = self.record("builder")
        record["window"] = {"x": 100000, "y": 100000, "width": 500, "height": 400}
        self.writeDocument(statePath, record)
        FakeExperimentInfoThread.responses = {
            "routine.py": {"Routine": ExperimentInfo(**copy.deepcopy(EXPERIMENT_INFO))}
        }
        manager, stateManager = self.makeManager(statePath)
        with self.assertLogs(builder_state.logger, "WARNING") as captured:
            stateManager.start()
            self.waitFor(lambda: not stateManager.restoring)
        self.assertIn("builder", manager._apps)
        self.assertTrue(stateManager.writesEnabled)
        self.assertIn("off-screen Builder geometry", "\n".join(captured.output))
        self.assertEqual(list(statePath.parent.glob("builders.json.recovery-*.json")), [])

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_maximized_mdi_workspace_and_builder_geometry_are_restored(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        firstManager, firstStateManager = self.makeManager(statePath)
        firstStateManager.start()
        self.openBuilder(firstManager, "builder")
        firstManager.mainWindow.showMaximized()
        self.qapp.processEvents()
        available = firstManager.centralWidget.viewport().rect()
        expectedGeometry = QRect(
            max(0, available.width() - 340),
            max(0, available.height() - 280),
            min(320, available.width()),
            min(240, available.height()),
        )
        firstManager._wrapperWidgets["builder"][0].setGeometry(expectedGeometry)
        self.qapp.processEvents()
        firstStateManager.shutdown()
        saved = json.loads(statePath.read_text(encoding="utf-8"))
        self.assertTrue(saved["workspace"]["maximized"])

        FakeExperimentInfoThread.responses = {
            "routine.py": {"Routine": ExperimentInfo(**copy.deepcopy(EXPERIMENT_INFO))}
        }
        secondManager, secondStateManager = self.makeManager(statePath)
        self.assertFalse(secondManager.mainWindow.isMaximized())
        secondStateManager.start()
        self.waitFor(lambda: not secondStateManager.restoring)
        self.qapp.processEvents()

        self.assertTrue(secondManager.mainWindow.isMaximized())
        restoredWorkspace = secondStateManager._workspace()
        self.assertEqual(restoredWorkspace["width"], saved["workspace"]["width"])
        self.assertEqual(restoredWorkspace["height"], saved["workspace"]["height"])
        restoredGeometry = secondStateManager._geometry("builder")
        self.assertEqual(restoredGeometry, saved["builders"][0]["window"])

    def test_malformed_and_unsupported_files_are_untouched(self):
        for content in ("{broken", json.dumps({
            "schema": builder_state.SCHEMA_NAME, "version": 99, "builders": []
        })):
            statePath = Path(self.tempDirectory.name) / f"state-{len(self.managers)}.json"
            statePath.write_text(content, encoding="utf-8")
            original = statePath.read_bytes()
            _manager, stateManager = self.makeManager(statePath)
            with self.assertLogs(builder_state.logger, "ERROR"):
                stateManager.start()
            self.assertFalse(stateManager.writesEnabled)
            stateManager.scheduleSave()
            self.assertEqual(statePath.read_bytes(), original)

    @mock.patch("iquip.builder_state.ExperimentInfoThread", FakeExperimentInfoThread)
    def test_failed_recovery_backup_disables_writes(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        self.writeDocument(statePath, self.record("bad"))
        original = statePath.read_bytes()
        FakeExperimentInfoThread.responses = {"routine.py": RuntimeError("offline")}
        _manager, stateManager = self.makeManager(statePath)
        with mock.patch("iquip.builder_state.os.open", side_effect=OSError("read only")):
            stateManager.start()
            self.waitFor(lambda: not stateManager.restoring)
        self.assertFalse(stateManager.writesEnabled)
        self.assertEqual(statePath.read_bytes(), original)

    def test_failed_atomic_replace_keeps_previous_file(self):
        statePath = Path(self.tempDirectory.name) / "builders.json"
        statePath.write_text("previous valid contents", encoding="utf-8")
        manager, stateManager = self.makeManager(statePath)
        stateManager._writesEnabled = True
        self.openBuilder(manager, "builder")
        with mock.patch("iquip.builder_state.os.replace", side_effect=OSError("disk error")):
            with self.assertLogs(builder_state.logger, "ERROR"):
                self.assertFalse(stateManager.saveNow())
        self.assertEqual(statePath.read_text(encoding="utf-8"), "previous valid contents")
        self.assertEqual(list(statePath.parent.glob(".builders.json.*.tmp")), [])

    def test_relative_and_home_path_resolution_and_no_option_default(self):
        with mock.patch("iquip.builder_state.Path.cwd", return_value=Path("/work")):
            self.assertEqual(
                builder_state.resolveStatePath("sessions/builders.json"),
                Path("/work/sessions/builders.json"),
            )
        self.assertTrue(builder_state.resolveStatePath("~/builders.json").is_absolute())
        from iquip.main import getArgParser  # Import here to keep launcher coverage focused.
        args = getArgParser().parse_args([])
        self.assertIsNone(args.builder_state_file)
        self.assertEqual(args.config_path, "./config.json")


if __name__ == "__main__":
    unittest.main()

