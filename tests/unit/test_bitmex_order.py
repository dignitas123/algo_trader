import unittest

from algo_trader.clients.bitmex import BitmexClient

from unittest.mock import MagicMock


class BitmexOrderTestCase(unittest.TestCase):
    """Test BitmexOrder Class Functions with Client Mock Data"""

    def setUp(self):
        self.mockClient = BitmexClient(api_key='', api_secret='')
        self.mockClient.get_histories = MagicMock(return_value=3)
        self.mockClient.get_histories(3, 4, 5, key='value')

    def test_get_histories(self):
        self.mockClient.get_histories.assert_called_with(3, 4, 5, key='value')
