"""Unit tests for monitor module."""

import unittest
from unittest import mock
from typing import Optional, Tuple

from PyQt5.QtWidgets import QApplication

from iquip import monitor

class TestMonitor(unittest.TestCase):
    """Unit tests for Monitor class."""

    def test_init_initial_value(self):
        for value in (True, None, 1.0, "value", object()):
            mon = monitor.Monitor(initial_value=value)
            self.assertEqual(mon._value, value)

    def test_init_updated_callback(self):
        callback = mock.MagicMock()
        mon = monitor.Monitor(initial_value=None, updated_callback=callback)
        mon.updated_callback(None)
        callback.assert_called_once_with(None)

    def test_get_value(self):
        for value in (True, None, 1.0, "value", object()):
            mon = monitor.Monitor(initial_value=value)
            self.assertEqual(mon.get_value(), mon._value)

    def test_set_value(self):
        values = ((True, False), (1, 0), ("old", "new"))
        for init_value, new_value in values:
            mon = monitor.Monitor(initial_value=init_value)
            mon.set_value(new_value)
            self.assertEqual(mon._value, new_value)

    def test_set_value_callback(self):
        callback = mock.MagicMock()
        mon = monitor.Monitor(initial_value="old", updated_callback=callback)
        mon.set_value("new")
        callback.assert_called_once_with("new")

    def test_update(self):
        mon = monitor.Monitor(initial_value="old")
        with mock.patch.multiple(mon, set_value=mock.DEFAULT, _read=mock.DEFAULT):
            mon._read.return_value = "new"
            mon.update()
            mon.set_value.assert_called_once_with("new")

    def test_read(self):
        """Tests if _read() returns self._value.

        Although _read() will be overridden in most cases,
        this tests the default behavior of this method.
        """
        mon = monitor.Monitor(initial_value="value")
        self.assertEqual(mon._read(), mon._value)


class TestTTLMonitorWidget(unittest.TestCase):
    """Unit tests for TTLMonitorWidget class."""

    def setUp(self):
        self.qapp = QApplication([])
    
    def tearDown(self):
        del self.qapp

    def test_init_monitor(self):
        mon, widget = self.get_widget_with(None)
        self.assertIs(widget.monitor, mon)

    def test_init_callback(self):
        """Tests if the updated_callback is overwritten by _setValue()."""
        callback = mock.MagicMock()
        mon = monitor.Monitor[Optional[bool]](
            initial_value=None, updated_callback=callback)
        with mock.patch.object(monitor.TTLMonitorWidget, "_updateValue") as mocked_set_value:
            widget = monitor.TTLMonitorWidget(monitor=mon)
            widget.monitor.updated_callback(True)
            mocked_set_value.assert_called_once_with(True)
            callback.assert_not_called()

    def test_set_value(self):
        for value, text in ((True, "HIGH"), (False, "LOW"), (None, "--")):
            _, widget = self.get_widget_with(None)
            with mock.patch.object(widget, "valueUpdated") as mocked_signal:
                widget._setValue(value)
            self.assertEqual(widget.stateLabel.text(), text)
            mocked_signal.assert_not_called()

    def get_widget_with(
        self,
        initial_value: Optional[bool],
    ) -> Tuple[monitor.Monitor[Optional[bool]], monitor.TTLMonitorWidget]:
        """Returns a new TTLMonitorWidget and Monitor with initial_value.

        Args:
            initial_value: The initial value of the new Monitor.
        """
        mon = monitor.Monitor[Optional[bool]](initial_value=initial_value)
        widget = monitor.TTLMonitorWidget(monitor=mon)
        return mon, widget


if __name__ == "__main__":
    unittest.main()
