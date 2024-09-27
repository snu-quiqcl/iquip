"""App module for showing the configuration list and opening an configuration."""

import posixpath
import logging
from typing import Dict, List, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (
    QInputDialog, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ConfigurationInfo
from iquip.apps.thread import ConfigurationInfoThread

logger = logging.getLogger(__name__)


class RemoteEditorFrame(QWidget):
    """Frame for showing the configuration list and opening an configuration.

    Attributes:
        fileTree: The tree widget for showing the file structure.
        reloadButton: The button for reloading the fileTree.
        openButton: The button for opening the selected configuration file.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.fileTree = QTreeWidget(self)
        self.fileTree.header().setVisible(False)
        self.reloadButton = QPushButton("Reload", self)
        self.openButton = QPushButton("Open", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.reloadButton)
        layout.addWidget(self.fileTree)
        layout.addWidget(self.openButton)
        self.setLayout(layout)


class _FileFinderThread(QThread):
    """QThread for finding the file list from the proxy server.

    Signals:
        fetched(configurationList, widget): The file list is fetched.

    Attributes:
        path: The path of the directory to search for configuration files.
        widget: The widget corresponding to the path.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(list, object)

    def __init__(
        self,
        path: str,
        widget: Union[QTreeWidget, QTreeWidgetItem],
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.

        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.path = path
        self.widget = widget
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.

        Fetches the file list from the proxy server.

        Searches for only files in path, not in deeper path and adds them into the widget.
        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/ls_config/",
                                    params={"directory": self.path},
                                    timeout=10)
            response.raise_for_status()
            configurationList = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the file list.")
            return
        self.fetched.emit(configurationList, self.widget)


class RemoteEditorApp(qiwis.BaseApp):
    """App for showing the configuration json file list and opening an configuration.

    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        selectedConfigurationPath: The currently selected configuration path.
        explorerFrame: The frame that shows the file tree.
        fileFinderThread: The most recently executed _FileFinderThread instance.
        ConfigurationInfoThread: The most recently executed ConfigurationInfoThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.selectedConfigurationPath: Optional[str] = None
        self.fileFinderThread: Optional[_FileFinderThread] = None
        self.configurationInfoThread: Optional[ConfigurationInfoThread] = None
        self.explorerFrame = RemoteEditorFrame()
        self.loadFileTree()
        # connect signals to slots
        self.explorerFrame.fileTree.itemExpanded.connect(self.lazyLoadFile)
        self.explorerFrame.fileTree.itemDoubleClicked.connect(self.fetchConfigurationInfo)
        self.explorerFrame.reloadButton.clicked.connect(self.loadFileTree)
        self.explorerFrame.openButton.clicked.connect(self.openButtonClicked)

    @pyqtSlot()
    def loadFileTree(self):
        """Loads the configuration file structure in self.explorerFrame.fileTree."""
        self.explorerFrame.fileTree.clear()
        self.fileFinderThread = _FileFinderThread(
            ".",
            self.explorerFrame.fileTree,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.fileFinderThread.fetched.connect(self._addFile, type=Qt.QueuedConnection)
        self.fileFinderThread.finished.connect(self.fileFinderThread.deleteLater)
        self.fileFinderThread.start()

    @pyqtSlot(QTreeWidgetItem)
    def lazyLoadFile(self, configurationFileItem: QTreeWidgetItem):
        """Loads the configuration file in the directory.

        This will be called when a directory item is expanded,
        so it makes loading files lazy.

        Args:
            configurationFileItem: The expanded file item.
        """
        if (
            configurationFileItem.childCount() != 1 or
            configurationFileItem.child(0).columnCount() != 0
        ):
            return
        # Remove the empty item of an unloaded directory.
        configurationFileItem.takeChild(0)
        configurationPath = self.fullPath(configurationFileItem)
        self.fileFinderThread = _FileFinderThread(
            configurationPath,
            configurationFileItem,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.fileFinderThread.fetched.connect(self._addFile, type=Qt.QueuedConnection)
        self.fileFinderThread.finished.connect(self.fileFinderThread.deleteLater)
        self.fileFinderThread.start()

    @pyqtSlot(list, object)
    def _addFile(self, configurationList: List[str], widget: Union[QTreeWidget, QTreeWidgetItem]):
        """Adds the files into the children of the widget.

        A file or directory which starts with "_" will be ignored, e.g. __pycache__/.

        Args:
            configurationList: The list of files under the widget path.
            widget: See _FileFinderThread class.
        """
        for configurationFile in configurationList:
            if configurationFile.startswith("_"):
                continue
            if configurationFile.endswith("/"):
                configurationFileItem = QTreeWidgetItem(widget)
                configurationFileItem.setText(0, configurationFile[:-1])
                # Make an empty item for indicating that it is a directory.
                QTreeWidgetItem(configurationFileItem)
            elif configurationFile.endswith((".json",)):
                configurationFileItem = QTreeWidgetItem(widget)
                configurationFileItem.setText(0, configurationFile)

    @pyqtSlot()
    def openButtonClicked(self):
        """Called when the openButton is clicked.
        
        If no item is selected, nothing happens.
        """
        item = self.explorerFrame.fileTree.currentItem()
        if item is not None:  # item is selected
            self.fetchConfigurationInfo(item)


    @pyqtSlot(QTreeWidgetItem)
    def fetchConfigurationInfo(self, item: QTreeWidgetItem):
        """Fetches the given configuration info.
         
        After fetched, self.selectConfigurationCls() is called to select an configuration class.

        Once an configuration item is double-clicked or the openButton is clicked, this is called.
        If the given item is a directory, nothing happens.
        """
        if item.childCount():  # item is a directory
            return
        self.selectedConfigurationPath = self.fullPath(item)
        self.configurationInfoThread = ConfigurationInfoThread(
            self.selectedConfigurationPath,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.configurationInfoThread.fetched.connect(self.selectConfigurationCls,
                                                  type=Qt.QueuedConnection)
        self.configurationInfoThread.finished.connect(self.configurationInfoThread.deleteLater)
        self.configurationInfoThread.start()

    @pyqtSlot(dict)
    def selectConfigurationCls(self, configurationInfos: Dict[str, ConfigurationInfo]):
        """Selects an configuration class to be opened as a builder.
        
        After selected, self.openBuilder() is called to open a builder.

        If there is only one class, it is selected automatically without showing a QInputDialog.
        If no class is selected, nothing happens.

        Args:
            See thread.ConfigurationInfoThread.fetched signal.
        """
        if len(configurationInfos) > 1:
            cls, ok = QInputDialog().getItem(
                None, "Select an configuration class",
                "Configuration class: ",
                configurationInfos,
                editable=False
            )
            if not ok:
                return
        else:
            cls = next(iter(configurationInfos))
        self.openBuilder(cls, configurationInfos[cls])

    def openBuilder(
        self,
        configurationClsName: str,
        configurationInfo: ConfigurationInfo
    ):
        """Opens the configuration builder with its information.
        
        The configuration is guaranteed to be the correct configuration file.

        Args:
            configurationClsName: The class name of the configuration.
            configurationInfo: The configuration information. See protocols.ConfigurationInfo.
        """
        self.qiwiscall.createApp(
            name=f"builder - {self.selectedConfigurationPath}:{configurationClsName}",
            info=qiwis.AppInfo(
                module="iquip.apps.config_builder",
                cls="ConfigBuilderApp",
                pos="center",
                args={
                    "configurationPath": self.selectedConfigurationPath,
                    "configurationClsName": configurationClsName,
                    "configurationInfo": configurationInfo
                },
                trust=True
            )
        )

    def fullPath(self, configurationFileItem: QTreeWidgetItem) -> str:
        """Finds the full path of the file item and returns it.

        Args:
            configurationFileItem: The file item to get its full path.
        """
        paths = [configurationFileItem.text(0)]
        while configurationFileItem.parent():
            configurationFileItem = configurationFileItem.parent()
            paths.append(configurationFileItem.text(0))
        return posixpath.join(*reversed(paths))

    def frames(self) -> Tuple[Tuple[str, RemoteEditorFrame]]:
        """Overridden."""
        return (("", self.explorerFrame),)
