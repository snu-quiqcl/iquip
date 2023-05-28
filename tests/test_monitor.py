"""Unit tests for monitor module."""

import unittest

from iquip import monitor

class TestMonitor(unittest.TestCase):
    """Unit tests for Monitor class."""

    def test_initial_value(self):
        for value in (True, None, 1.0, "value", object()):
            mon = monitor.Monitor(initial_value=value)
            self.assertEqual(mon._value, value)


if __name__ == "__main__":
    unittest.main()
