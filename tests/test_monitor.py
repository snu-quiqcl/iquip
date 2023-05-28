"""Unit tests for monitor module."""

import unittest
from unittest import mock

from iquip import monitor

class TestMonitor(unittest.TestCase):
    """Unit tests for Monitor class."""

    def test_initial_value(self):
        for value in (True, None, 1.0, "value", object()):
            mon = monitor.Monitor(initial_value=value)
            self.assertEqual(mon._value, value)

    def test_updated_callback(self):
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


if __name__ == "__main__":
    unittest.main()
