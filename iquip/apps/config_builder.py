"""App module for editting the configuration attributes and submitting the configuration json file."""

# pylint: disable=unused-import
import json
import logging
from typing import Any, Dict, Optional, Tuple
import dataclasses

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

import qiwis
from iquip.protocols import ConfigurationInfo
from iquip.apps.thread import ConfigurationInfoThread
from iquip.apps.builder import (
    _BaseEntry,
    _StringEntry,
)
logger = logging.getLogger(__name__)

class ConfigBuilderFrame(QWidget):
    """Frame for showing the configuration attributes and requesting to submit it.
    
    Attributes:
        argsListWidget: The list widget with the configuration attributes.
        reloadArgsButton: The button for reloading the configuration attributes.
        submitButton: The button for submitting the configuration.
    """

    def __init__(
        self,
        configurationName: str,
        configurationClsName: str,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            configurationName: The configuration name, the name field of 
                protocols.ConfigurationInfo.
            configurationClsName: The class name of the configuration.
        """
        super().__init__(parent=parent)
        # widgets
        clsBox = QGroupBox("Config", self)
        clsBox.setToolTip(configurationName)
        QHBoxLayout(clsBox).addWidget(QLabel(configurationClsName, self))
        self.argsListWidget = QListWidget(self)
        tabWidget = QTabWidget(self)
        tabWidget.addTab(self.argsListWidget, "Attributes")
        self.reloadArgsButton = QPushButton("Reload", self)
        self.submitButton = QPushButton("Submit", self)
        # layout
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.reloadArgsButton)
        buttonLayout.addWidget(self.submitButton)
        layout = QVBoxLayout(self)
        layout.addWidget(clsBox)
        layout.addWidget(tabWidget)
        layout.addLayout(buttonLayout)

class _ConfigurationSubmitThread(QThread):
    """QThread for submitting the configuration.
    
    Signals:
        submitted(str): The configuration is submitted. The str is name of submitted configuration.
    
    Attributes:
        configurationPath: The file name of the configuration file.
        configurationClsName: The file name of the configuration.
        configurationArgs: The attributes of the configuration.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    submitted = pyqtSignal(str)

    def __init__(
        self,
        configurationPath: str,
        configurationClsName: str,
        configurationArgs: Dict[str, Any],
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.configurationPath = configurationPath
        self.configurationClsName = configurationClsName
        self.configurationArgs = configurationArgs
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Submits the configuration to the proxy server.

        Whenever the configuration is submitted well regardless of whether it runs successfully or not,
        the server returns the run identifier.
        """
        try:
            params = {
                "file": self.configurationPath,
                "cls": self.configurationClsName,
                "args": json.dumps(self.configurationArgs)
            }
        except TypeError:
            logger.exception("Failed to convert the build arguments to a JSON string.")
            return
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/configuration/submit/",
                                    params=params,
                                    timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to submit the configuration.")
            return
        self.submitted.emit(self.configurationClsName)

class ConfigBuilderApp(qiwis.BaseApp):
    """App for editting the build arguments and submitting the configuration.

    There are four types of build arguments.
      StringValue: Set to a string.
    
    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        builderFrame: The frame that shows the build arguments and requests to submit it.
        configurationPath: The path of the configuration file.
        configurationClsName: The class name of the configuration.
        configurationSubmitThread: The most recently executed _ConfigurationSubmitThread instance.
        configurationInfoThread: The most recently executed ConfigurationInfoThread instance.
    """

    def __init__(
        self,
        name: str,
        configurationPath: str,
        configurationClsName: str,
        configurationInfo: Dict[str, Any],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            configurationPath, configurationClsName: See the attributes section in BuilderApp.
            configurationInfo: The configuration information, a dictionary of 
                protocols ConfigurationInfo.
        """
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.configurationPath = configurationPath
        self.configurationClsName = configurationClsName
        self.configurationSubmitThread: Optional[_ConfigurationSubmitThread] = None
        self.configurationInfoThread: Optional[ConfigurationInfoThread] = None
        self.builderFrame = ConfigBuilderFrame(name, configurationClsName)
        self.initArgsEntry(ConfigurationInfo(**configurationInfo))
        # connect signals to slots
        self.builderFrame.reloadArgsButton.clicked.connect(self.reloadArgs)
        self.builderFrame.submitButton.clicked.connect(self.submit)

    def initArgsEntry(self, configurationInfo: ConfigurationInfo):
        """Initializes the configuration entry.
        
        Args:
            configurationInfo: The configuration information.
        """
        for argName, argInfo in dataclasses.asdict(configurationInfo).items():
            widget = _StringEntry(argName, {"default" : argInfo})
            listWidget = (self.builderFrame.argsListWidget)
            item = QListWidgetItem(listWidget)
            item.setSizeHint(widget.sizeHint())
            listWidget.addItem(item)
            listWidget.setItemWidget(item, widget)

    @pyqtSlot()
    def reloadArgs(self):
        """Reloads the configuration.
        
        Once the reloadArgsButton is clicked, this is called.
        """
        self.configurationInfoThread = ConfigurationInfoThread(
            self.configurationPath,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.configurationInfoThread.fetched.connect(self.onReloaded, type=Qt.QueuedConnection)
        self.configurationInfoThread.finished.connect(self.configurationInfoThread.deleteLater)
        self.configurationInfoThread.start()

    @pyqtSlot(dict)
    def onReloaded(self, configurationInfos: Dict[str, ConfigurationInfo]):
        """Clears the original configuration attributes entry and re-initializes them.
        
        Args:
            See thread.ConfigurationInfoThread.fetched signal.
        """
        configurationInfo = configurationInfos[self.configurationClsName]
        for _ in range(self.builderFrame.argsListWidget.count()):
            item = self.builderFrame.argsListWidget.takeItem(0)
            del item
        self.initArgsEntry(configurationInfo)

    def argumentsFromListWidget(self, listWidget: QListWidget) -> Dict[str, Any]:
        """Gets configuration attributes from the given list widget and returns them.
        
        Args:
            listWidget: The QListWidget containing _BaseEntry instances.

        Returns:
            A dictionary of arguments.
            Each key is the argument name and its value is the argument value.
        """
        args = {}
        for row in range(listWidget.count()):
            item = listWidget.item(row)
            widget = listWidget.itemWidget(item)
            args[widget.name] = widget.value()
        return args

    @pyqtSlot()
    def submit(self):
        """Submits the configuration with the attributes.
        
        Once the submitButton is clicked, this is called.
        """
        try:
            configurationArgs = self.argumentsFromListWidget(self.builderFrame.argsListWidget)
        except ValueError:
            logger.exception("The submission is rejected because of an invalid argument.")
            return
        self.configurationSubmitThread = _ConfigurationSubmitThread(
            self.configurationPath,
            self.configurationClsName,
            configurationArgs,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.configurationSubmitThread.submitted.connect(self.onSubmitted, type=Qt.QueuedConnection)
        self.configurationSubmitThread.finished.connect(self.configurationSubmitThread.deleteLater)
        self.configurationSubmitThread.start()

    def onSubmitted(self, rid: int):
        """Sends the rid to the logger after submitted.

        This is the slot for _ConfigurationSubmitThread.submitted.

        Args:
            rid: The run identifier of the submitted configuration.
        """
        logger.info("RID: %d", rid)

    def frames(self) -> Tuple[Tuple[str, ConfigBuilderFrame]]:
        """Overridden."""
        return (("", self.builderFrame),)
