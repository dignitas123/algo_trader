import unittest
import os

from algo_trader.clients.bitmex import BitmexClient, BitmexOrder

from unittest.mock import MagicMock, PropertyMock
from tests.unit.mock.mockBrokerSettings import mockSettings

mockSetting_file_name = '{}_{}_settings.pickle'.format(
    'bitmex_testnet', 'lotus')

mockSettingsPath = os.path.abspath(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'settings', mockSetting_file_name))


class BitmexOrderTestCase(unittest.TestCase):
    """Tests BitmexOrder Class Functions with Client Mock Data"""

    def setUp(self):
        self.mockClient = BitmexClient()
        type(self.mockClient).acc_balance = PropertyMock(
            return_value=100000000)

        self.mockOrder = BitmexOrder(
            ['ETHUSD', 'XBTUSD'],
            self.mockClient,
            mockSettings,
            mockSettingsPath
        )

    def test_check_open_bot_order(self):
        pass

    def test_calc_pos_size(self):
        self.mockOrder.client.last_current_price = MagicMock(
            return_value=50000)
        self.mockOrder.settings.symbols = {'XBTUSD': {'position_size': 1.0}}
        pos_size = self.mockOrder.calc_pos_size('XBTUSD', 200)
        self.assertEqual(pos_size, 125000)
        self.mockOrder.settings.symbols = {'XBTUSD': {'position_size': 0.5}}
        pos_size = self.mockOrder.calc_pos_size('XBTUSD', 200)
        self.assertEqual(pos_size, 62500)

        self.mockClient.client.last_current_price = MagicMock(
            return_value=3000)
        self.mockOrder.settings.symbols = {'ETHUSD': {'position_size': 1.0}}
        pos_size = self.mockOrder.calc_pos_size('ETHUSD', 50)
        self.assertEqual(pos_size, 200)
        self.mockOrder.settings.symbols = {'ETHUSD': {'position_size': 0.5}}
        pos_size = self.mockOrder.calc_pos_size('ETHUSD', 50)
        self.assertEqual(pos_size, 100)
