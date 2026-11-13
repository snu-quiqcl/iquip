"""Persistence and restoration for Builder app windows."""

import dataclasses
import datetime
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Set

from PyQt5.QtCore import QEvent, QObject, QRect, QTimer, Qt

import qiwis
from iquip.apps.builder import BuilderApp
from iquip.apps.thread import ExperimentInfoThread

logger = logging.getLogger(__name__)

SCHEMA_NAME = "iquip.builder-session"
SCHEMA_VERSION = 1
AUTOSAVE_DELAY_MS = 350


def resolveStatePath(path: str) -> Path:
    """Expands a state path and resolves relative paths from the current directory."""
    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return expanded.resolve(strict=False)


class IquipQiwis(qiwis.Qiwis):
    """Qiwis manager with narrow Builder lifecycle notifications."""

    def __init__(self, *args, **kwargs):
        appInfos = kwargs.get("appInfos", args[0] if args else None)
        self.initialAppNames = frozenset(appInfos or ())
        self.startupMaximized = kwargs.get(
            "isMaximized", args[2] if len(args) > 2 else False
        )
        self.builderStateManager: Optional[BuilderStateManager] = None
        self.constants = kwargs.get("constants", args[1] if len(args) > 1 else None)
        super().__init__(*args, **kwargs)

    def createApp(self, name: str, info: qiwis.AppInfo, replace: bool = False):
        existed = name in self._apps  # pylint: disable=protected-access
        super().createApp(name, info, replace)
        if self.builderStateManager is not None and (not existed or replace):
            app = self._apps.get(name)  # pylint: disable=protected-access
            if isinstance(app, BuilderApp):
                self.builderStateManager.builderCreated(name, app)

    def destroyApp(self, name: str):
        app = self._apps.get(name)  # pylint: disable=protected-access
        isBuilder = isinstance(app, BuilderApp)
        super().destroyApp(name)
        if self.builderStateManager is not None and isBuilder:
            self.builderStateManager.builderDestroyed(name)


class BuilderStateManager(QObject):
    """Owns the versioned Builder session file and its lifecycle."""

    def __init__(self, manager: IquipQiwis, statePath: Path, parent: Optional[QObject] = None):
        super().__init__(parent=parent)
        self.manager = manager
        self.statePath = statePath
        self.manager.builderStateManager = self
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(AUTOSAVE_DELAY_MS)
        self._timer.timeout.connect(self.saveNow)
        self._restoreTimer = QTimer(self)
        self._restoreTimer.setSingleShot(True)
        self._restoreTimer.timeout.connect(self._beginRestoration)
        self._recordsToRestore = []
        self._savedWorkspace = None
        self._tracked: Set[str] = set()
        self._threads: Set[ExperimentInfoThread] = set()
        self._configuredBuilders = {
            name: app
            for name, app in self.manager._apps.items()  # pylint: disable=protected-access
            if name in self.manager.initialAppNames and isinstance(app, BuilderApp)
        }
        self._claimedConfiguredBuilders: Set[str] = set()
        self._restoring = False
        self._remaining = 0
        self._restoreFailures = False
        self._savePending = False
        self._internalRestoreMutation = False
        self._writesEnabled = False
        self._writesDisabled = False
        self._shuttingDown = False
        self._started = False
        self.manager.mainWindow.installEventFilter(self)
        for name, app in self.manager._apps.items():  # pylint: disable=protected-access
            if isinstance(app, BuilderApp):
                self._track(name, app)

    @property
    def restoring(self) -> bool:
        """Whether asynchronous restoration is still in progress."""
        return self._restoring

    @property
    def writesEnabled(self) -> bool:
        """Whether this run may replace the configured session file."""
        return self._writesEnabled and not self._writesDisabled

    def start(self):
        """Reads the input snapshot and starts asynchronous restoration."""
        if self._started:
            return
        self._started = True
        if not self.statePath.exists():
            self._writesEnabled = True
            if self._tracked:
                self.scheduleSave()
            return
        try:
            with self.statePath.open("r", encoding="utf-8") as stateFile:
                state = json.load(stateFile, parse_constant=self._rejectJsonConstant)
            builders = self._validateDocument(state)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            self._disableWrites(
                "Cannot restore Builder state file %s; it will be left untouched: %s",
                self.statePath,
                error,
            )
            return

        try:
            workspace = self._validateWorkspace(state.get("workspace"))
        except (TypeError, ValueError) as error:
            logger.warning(
                "Ignoring invalid Builder workspace geometry in %s: %s",
                self.statePath,
                error,
            )
            workspace = None
        self._restoring = True
        self._remaining = len(builders)
        self._recordsToRestore = list(enumerate(builders))
        self._internalRestoreMutation = True
        try:
            self._restoreWorkspace(workspace)
        finally:
            self._internalRestoreMutation = False
        self._restoreTimer.start(0)

    def _beginRestoration(self):
        if self._shuttingDown:
            return
        records = self._recordsToRestore
        self._recordsToRestore = []
        if not records:
            self._finishRestoration()
            return
        for index, record in records:
            self._startRecord(index, record)

    @staticmethod
    def _rejectJsonConstant(value: str):
        raise ValueError(f"non-finite JSON number {value!r}")

    @staticmethod
    def _validateDocument(state: Any):
        if not isinstance(state, dict):
            raise ValueError("top-level state must be an object")
        if state.get("schema") != SCHEMA_NAME:
            raise ValueError(f"unsupported schema {state.get('schema')!r}")
        if state.get("version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version {state.get('version')!r}")
        builders = state.get("builders")
        if not isinstance(builders, list):
            raise ValueError("builders must be an array")
        return builders

    @staticmethod
    def _validateWorkspace(workspace: Any) -> Optional[Dict[str, Any]]:
        if workspace is None:
            return None
        if not isinstance(workspace, dict):
            raise TypeError("workspace must be an object")
        if set(workspace) != {"width", "height", "maximized"}:
            raise ValueError("workspace must contain width, height, and maximized")
        for field in ("width", "height"):
            value = workspace[field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"workspace {field} must be a positive integer")
        if not isinstance(workspace["maximized"], bool):
            raise ValueError("workspace maximized must be a boolean")
        return workspace

    def _restoreWorkspace(self, workspace: Optional[Mapping[str, Any]]):
        self._savedWorkspace = workspace
        if workspace is None:
            return
        mainWindow = self.manager.mainWindow
        if workspace["maximized"] or self.manager.startupMaximized:
            mainWindow.showMaximized()

    @staticmethod
    def _validateRecord(record: Any) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise ValueError("record must be an object")
        expected = {"instance_id", "name", "experiment", "arguments", "submission", "window"}
        if set(record) != expected:
            raise ValueError(
                f"record fields {sorted(record)} do not match {sorted(expected)}"
            )
        for field in ("instance_id", "name"):
            if not isinstance(record[field], str) or not record[field]:
                raise ValueError(f"{field} must be a non-empty string")
        experiment = record["experiment"]
        if not isinstance(experiment, dict) or set(experiment) != {"path", "class"}:
            raise ValueError("experiment must contain exactly path and class")
        if any(not isinstance(experiment[field], str) or not experiment[field]
               for field in ("path", "class")):
            raise ValueError("experiment path and class must be non-empty strings")
        if not isinstance(record["arguments"], dict):
            raise ValueError("arguments must be an object")
        if not isinstance(record["submission"], dict):
            raise ValueError("submission must be an object")
        window = record["window"]
        if window is not None:
            if not isinstance(window, dict) or set(window) != {"x", "y", "width", "height"}:
                raise ValueError("window must be null or contain x, y, width, and height")
            if any(isinstance(value, bool) or not isinstance(value, int)
                   for value in window.values()):
                raise ValueError("window coordinates and dimensions must be integers")
        return record

    def _startRecord(self, index: int, unvalidatedRecord: Any):
        try:
            record = self._validateRecord(unvalidatedRecord)
        except (ValueError, TypeError) as error:
            self._recordFailed(index, unvalidatedRecord, error)
            return
        configuredApp = self._configuredBuilders.get(record["name"])
        if (configuredApp is not None
                and record["name"] not in self._claimedConfiguredBuilders):
            self._claimedConfiguredBuilders.add(record["name"])
            self._restoreConfiguredRecord(index, record, configuredApp)
            return
        experiment = record["experiment"]
        context = {"done": False, "index": index, "record": record, "error": None}
        try:
            thread = ExperimentInfoThread(
                experiment["path"],
                self.manager.constants.proxy_ip,
                self.manager.constants.proxy_port,
                self,
            )
            context["thread"] = thread
            thread.fetched.connect(
                lambda infos, ctx=context: self._metadataFetched(ctx, infos),
                type=Qt.QueuedConnection,
            )
            thread.failed.connect(
                lambda reason, ctx=context: self._metadataFailed(ctx, reason),
                type=Qt.QueuedConnection,
            )
            thread.finished.connect(
                lambda ctx=context: self._metadataFinished(ctx),
                type=Qt.QueuedConnection,
            )
            thread.finished.connect(thread.deleteLater)
            self._threads.add(thread)
            thread.start()
        except Exception as error:  # pylint: disable=broad-exception-caught
            thread = context.get("thread")
            if thread is not None:
                self._threads.discard(thread)
            self._recordFailed(index, record, error, context)

    def _restoreConfiguredRecord(
        self,
        index: int,
        record: Mapping[str, Any],
        app: BuilderApp
    ):
        """Restores state into a Builder already created by the qiwis config."""
        experiment = record["experiment"]
        if (app.experimentPath != experiment["path"]
                or app.experimentClsName != experiment["class"]):
            self._recordFailed(
                index,
                record,
                ValueError(
                    "configured Builder experiment identity does not match the saved record: "
                    f"configured={app.experimentPath!r}:{app.experimentClsName!r}, "
                    f"saved={experiment['path']!r}:{experiment['class']!r}"
                ),
            )
            return

        previousArguments, previousSubmission = app.persistentState()
        previousInstanceId = app.builderInstanceId
        failure = None
        rollbackFailure = None
        self._internalRestoreMutation = True
        try:
            app.applyPersistentState(record["arguments"], record["submission"])
            app.builderInstanceId = record["instance_id"]
            self._restoreGeometry(record["name"], record["window"])
        except Exception as error:  # pylint: disable=broad-exception-caught
            failure = error
            app.builderInstanceId = previousInstanceId
            try:
                app.applyPersistentState(previousArguments, previousSubmission)
            except Exception as rollbackError:  # pylint: disable=broad-exception-caught
                rollbackFailure = rollbackError
        finally:
            self._internalRestoreMutation = False
        if failure is not None:
            if rollbackFailure is not None:
                failure = RuntimeError(
                    f"{failure}; restoring the configured Builder defaults also failed: "
                    f"{rollbackFailure}"
                )
            self._recordFailed(index, record, failure)
            return
        self._recordCompleted()

    def _metadataFetched(self, context: Dict[str, Any], experimentInfos: Mapping[str, Any]):
        if context["done"] or self._shuttingDown:
            return
        record = context["record"]
        experiment = record["experiment"]
        className = experiment["class"]
        createdName = None
        failure = None
        self._internalRestoreMutation = True
        try:
            if className not in experimentInfos:
                raise ValueError(f"experiment class {className!r} is not present in metadata")
            createdName = self._uniqueName(record["name"])
            info = qiwis.AppInfo(
                module="iquip.apps.builder",
                cls="BuilderApp",
                pos="center",
                args={
                    "experimentPath": experiment["path"],
                    "experimentClsName": className,
                    "experimentInfo": dataclasses.asdict(experimentInfos[className]),
                    "builderInstanceId": record["instance_id"],
                },
            )
            self.manager.createApp(createdName, info)
            app = self.manager._apps.get(createdName)  # pylint: disable=protected-access
            if not isinstance(app, BuilderApp):
                raise RuntimeError("normal Builder creation did not register an app")
            app.applyPersistentState(record["arguments"], record["submission"])
            self._restoreGeometry(createdName, record["window"])
        except Exception as error:  # pylint: disable=broad-exception-caught
            if createdName in self.manager._apps:  # pylint: disable=protected-access
                self.manager.destroyApp(createdName)
            failure = error
        finally:
            self._internalRestoreMutation = False
        if failure is not None:
            self._recordFailed(context["index"], record, failure, context)
            return
        context["done"] = True
        self._recordCompleted()

    def _metadataFailed(self, context: Dict[str, Any], reason: str):
        if context["done"] or self._shuttingDown:
            return
        context["error"] = reason

    def _metadataFinished(self, context: Dict[str, Any]):
        thread = context.get("thread")
        if thread is not None:
            self._threads.discard(thread)
        if context["done"] or self._shuttingDown:
            return
        reason = context.get("error") or "metadata request finished without usable data"
        self._recordFailed(context["index"], context["record"], RuntimeError(reason), context)

    def _recordFailed(
        self,
        index: int,
        record: Any,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ):
        if context is not None:
            context["done"] = True
        self._restoreFailures = True
        logger.error(
            "Failed to restore Builder record %d from %s (%s): %s",
            index,
            self.statePath,
            self._recordIdentity(record),
            error,
            exc_info=(type(error), error, error.__traceback__) if error.__traceback__ else None,
        )
        self._recordCompleted()

    @staticmethod
    def _recordIdentity(record: Any) -> str:
        if not isinstance(record, dict):
            return repr(record)
        experiment = record.get("experiment", {})
        if not isinstance(experiment, dict):
            experiment = {}
        return (
            f"name={record.get('name')!r}, instance={record.get('instance_id')!r}, "
            f"experiment={experiment.get('path')!r}:{experiment.get('class')!r}"
        )

    def _recordCompleted(self):
        self._remaining -= 1
        if self._remaining == 0:
            self._finishRestoration()

    def _finishRestoration(self):
        if self._shuttingDown:
            return
        self._restoring = False
        if self._restoreFailures:
            try:
                backupPath = self._createRecoveryBackup()
            except Exception as error:  # pylint: disable=broad-exception-caught
                self._disableWrites(
                    "Builder restoration was partial, but a recovery backup of %s could not be "
                    "created; the original will be left untouched and writes are disabled: %s",
                    self.statePath,
                    error,
                )
                return
            logger.warning(
                "Builder restoration was partial. Preserved the original state file as %s",
                backupPath,
            )
        shouldSave = self._restoreFailures or self._savePending
        self._savePending = False
        self._writesEnabled = True
        if shouldSave:
            self.scheduleSave()

    def _createRecoveryBackup(self) -> Path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        prefix = f"{self.statePath.name}.recovery-{timestamp}-{os.getpid()}"
        for collision in range(1000):
            suffix = "" if collision == 0 else f"-{collision}"
            candidate = self.statePath.with_name(f"{prefix}{suffix}.json")
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            try:
                with self.statePath.open("rb") as source, os.fdopen(descriptor, "wb") as target:
                    descriptor = -1
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
                    target.flush()
                    os.fsync(target.fileno())
            except Exception:
                if descriptor >= 0:
                    os.close(descriptor)
                try:
                    candidate.unlink()
                except OSError:
                    pass
                raise
            return candidate
        raise OSError("could not allocate a collision-free recovery backup name")

    def _uniqueName(self, savedName: str) -> str:
        if savedName not in self.manager.appNames():
            return savedName
        number = 2
        while f"{savedName} (restored {number})" in self.manager.appNames():
            number += 1
        uniqueName = f"{savedName} (restored {number})"
        logger.warning(
            "Builder name %r from %s is already registered; restoring it as %r",
            savedName,
            self.statePath,
            uniqueName,
        )
        return uniqueName

    def builderCreated(self, name: str, app: BuilderApp):
        """Tracks a Builder created through the normal qiwis path."""
        self._track(name, app)
        self.scheduleSave()

    def _track(self, name: str, app: BuilderApp):
        if name in self._tracked:
            return
        self._tracked.add(name)
        app.stateChanged.connect(self.scheduleSave)
        wrappers = self.manager._wrapperWidgets.get(name, ())  # pylint: disable=protected-access
        for wrapper in wrappers:
            wrapper.installEventFilter(self)

    def builderDestroyed(self, name: str):
        """Removes an intentionally closed Builder from the next snapshot."""
        self._tracked.discard(name)
        if not self._shuttingDown:
            self.scheduleSave()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        mainWindow = getattr(self.manager, "mainWindow", None)
        wrappersByName = getattr(self.manager, "_wrapperWidgets", {})
        if watched is mainWindow:
            if event.type() == QEvent.Close:
                self.shutdown()
            elif event.type() in (QEvent.Resize, QEvent.WindowStateChange):
                self.scheduleSave()
        elif event.type() in (QEvent.Move, QEvent.Resize) and any(
            watched in wrappers
            for name, wrappers in wrappersByName.items()
            if name in self._tracked
        ):
            self.scheduleSave()
        return super().eventFilter(watched, event)

    def scheduleSave(self):
        """Debounces an autosave when writes are safe for this run."""
        if self._shuttingDown or self._writesDisabled or self._internalRestoreMutation:
            return
        if self._restoring:
            self._savePending = True
            return
        if self.writesEnabled:
            self._timer.start()

    def saveNow(self, commitEditors: bool = False):
        """Atomically writes the complete current Builder snapshot."""
        if not self.writesEnabled or self._restoring or self._shuttingDown:
            return False
        try:
            document = self._snapshot(commitEditors=commitEditors)
            self._atomicWrite(document)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to save Builder state file %s; the previous file is intact: %s",
                self.statePath,
                error,
                exc_info=True,
            )
            return False
        return True

    def _snapshot(self, commitEditors: bool = False) -> Dict[str, Any]:
        builders = []
        for name, app in self.manager._apps.items():  # pylint: disable=protected-access
            if not isinstance(app, BuilderApp):
                continue
            arguments, submission = app.persistentState(commitEditors=commitEditors)
            builders.append({
                "instance_id": app.builderInstanceId,
                "name": name,
                "experiment": {
                    "path": app.experimentPath,
                    "class": app.experimentClsName,
                },
                "arguments": arguments,
                "submission": submission,
                "window": self._geometry(name),
            })
        return {
            "schema": SCHEMA_NAME,
            "version": SCHEMA_VERSION,
            "workspace": self._workspace(),
            "builders": builders,
        }

    def _workspace(self) -> Dict[str, Any]:
        viewport = self.manager.centralWidget.viewport()
        return {
            "width": viewport.width(),
            "height": viewport.height(),
            "maximized": self.manager.mainWindow.isMaximized(),
        }

    def _geometry(self, name: str) -> Optional[Dict[str, int]]:
        wrappers = self.manager._wrapperWidgets.get(name, ())  # pylint: disable=protected-access
        if not wrappers:
            return None
        geometry = wrappers[0].geometry()
        return {
            "x": geometry.x(),
            "y": geometry.y(),
            "width": geometry.width(),
            "height": geometry.height(),
        }

    def _restoreGeometry(self, name: str, geometry: Optional[Mapping[str, int]]):
        if geometry is None:
            return
        wrappers = self.manager._wrapperWidgets.get(name, ())  # pylint: disable=protected-access
        if not wrappers:
            return
        requested = QRect(
            geometry["x"], geometry["y"], geometry["width"], geometry["height"]
        )
        workspace = self._savedWorkspace
        if requested.width() < 100 or requested.height() < 80:
            logger.warning(
                "Ignoring invalid Builder geometry in %s for %s",
                self.statePath,
                name,
            )
            return
        if workspace is not None:
            savedBounds = QRect(0, 0, workspace["width"], workspace["height"])
            if not savedBounds.intersects(requested):
                logger.warning(
                    "Ignoring Builder geometry outside its saved MDI workspace in %s for %s",
                    self.statePath,
                    name,
                )
                return
        elif not self.manager.centralWidget.viewport().rect().intersects(requested):
            logger.warning(
                "Ignoring off-screen Builder geometry in legacy state file %s for %s",
                self.statePath,
                name,
            )
            return
        wrappers[0].setGeometry(requested)

    def _atomicWrite(self, document: Mapping[str, Any]):
        self.statePath.parent.mkdir(parents=True, exist_ok=True)
        temporaryPath = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.statePath.parent,
                prefix=f".{self.statePath.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporaryFile:
                temporaryPath = Path(temporaryFile.name)
                json.dump(
                    document,
                    temporaryFile,
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                temporaryFile.write("\n")
                temporaryFile.flush()
                os.fsync(temporaryFile.fileno())
            os.replace(temporaryPath, self.statePath)
            temporaryPath = None
        finally:
            if temporaryPath is not None:
                try:
                    temporaryPath.unlink()
                except OSError:
                    pass

    def shutdown(self):
        """Takes the final snapshot before qiwis destroys Builder frames."""
        if self._shuttingDown:
            return
        self._timer.stop()
        self._restoreTimer.stop()
        if self._restoring:
            logger.warning(
                "Builder restoration from %s is incomplete during shutdown; preserving the "
                "input snapshot without writing partial state",
                self.statePath,
            )
        elif self.writesEnabled:
            self.saveNow(commitEditors=True)
        self._shuttingDown = True
        for thread in tuple(self._threads):
            thread.requestInterruption()
        for thread in tuple(self._threads):
            thread.wait()
        self._threads.clear()

    def _disableWrites(self, message: str, *args: Any):
        self._timer.stop()
        self._writesEnabled = False
        self._writesDisabled = True
        logger.error(message, *args)

