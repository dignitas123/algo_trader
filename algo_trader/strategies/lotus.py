import sys
import random
import datetime
import time
from dateutil import parser
from algo_trader.clients.bitmex import BitmexOrder
from algo_trader.settings import TESTNET_LOTUS_LINK, LIVE_LOTUS_LINK
import requests
import os
import signal

from socket import gaierror


class Lotus:
    def __init__(self, client, symbols, settings, setting_file_name):
        self.client = client
        self.symbols = symbols
        self.settings = settings
        self._api_endpoint = TESTNET_LOTUS_LINK if self.client.testnet else LIVE_LOTUS_LINK
        self._settings_path = os.path.abspath(os.path.join(os.path.dirname(
            os.path.abspath(__file__)), os.pardir, 'settings', setting_file_name))

        self._last_signal_timestamp = self.get_api_signal_retry()['timestamp']

        self._last_timestamp = {}
        self._last_entry = {}
        self._last_sl = {}

        self.me_count = 0  # initialize manage entries count for candle check every 3rd time

        signal.signal(signal.SIGINT, self.signal_handler)

        for symbol in symbols:
            self._last_timestamp[symbol] = datetime.datetime.utcnow()
            self._last_entry[symbol] = ''
            self._last_sl[symbol] = ''

        if not self.client.is_connected:
            print(
                'Invalid API ID or API Secret, please restart and provide the right keys', flush=True)
            sys.exit()

    # helper function
    def ceil_dt(self, dt, delta):
        return dt + (datetime.datetime.min - dt) % delta

    def signal_handler(self):
        print('Doing things before exit...')
        for symbol in self.symbols:
            if self.order.props[symbol]['wait_stop']:
                self.order.close(symbol)  # cancel old order first
        sys.exit(0)

    def is_new_signal_symbol(self, signal, symbol):
        timestamp = parser.parse(signal[symbol]['timestamp'])
        if self._last_timestamp[symbol] != timestamp:
            self._last_timestamp[symbol] = timestamp
            if self._last_entry[symbol] != signal[symbol]['entry'] or self._last_sl[symbol] != signal[symbol]['stoploss']:
                self._last_entry[symbol] = signal[symbol]['entry']
                self._last_sl[symbol] = signal[symbol]['stoploss']
                return True

    def get_api_signal(self):
        auth = {'token': self.settings.token}
        try:
            return requests.get(self._api_endpoint, params=auth).json()
        except ValueError:
            print("Can't get signal on endpoint {} with token {}."
                  "It could be that you are timed out because you try to access with multiple IP's.\nIn this case wait 30 minutes to be able to access again.\(Don't need to restart)".format(
                      self._api_endpoint, self.settings.token))
            time.sleep(180)
            return False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, gaierror):
            time.sleep(30)
            print('Retrying connection to endpoint')
            return self.get_api_signal()
        except requests.exceptions.TooManyRedirects:
            print('Bad URL. Try to setup the correct endpoint. Current endpoint: {}'.format(
                self._api_endpoint))
            return False
        except requests.exceptions.RequestException as e:
            print('Another exception occured {}'.format(e))
            return False

    def get_api_signal_retry(self):
        while True:
            signal = self.get_api_signal()
            if signal:
                return signal
            else:
                time.sleep(10)

    def is_new_signal(self, signal):
        # tests if signal has new timestamp
        if signal['timestamp'] != self._last_signal_timestamp:
            self._last_signal_timestamp = signal['timestamp']
            return True
        else:
            return False

    def rand_sec(self, start=2, end=6):
        return random.randrange(start, end)

    def check_modify(self, symbol, sl):
        res = self.order.modifiy_stop(symbol, sl)
        if type(res) is str:
            if 'noValChanged' not in res:
                print('Modify order Error {}:'.format(symbol), res, flush=True)
        else:
            print('Modifying order in {} to new stoploss: {}'.format(
                symbol, sl), flush=True)
            self.order.SL = sl

    def manage_open_stop_orders(self, symbol):
        if self.order.props[symbol]['wait_stop']:
            print('Cancel old order {} first.'.format(symbol))
            self.order.stoporder_cancel(symbol)
            time.sleep(3)
        elif self.order.props[symbol]['open']:
            print('Manage open stop orders, order open. Trying to close.', flush=True)
            self.order.close(symbol, -self.client.open_contracts(symbol))
            time.sleep(3)

    def process_signals(self, ns, start=False):
        for symbol in self.symbols:
            if start:
                if ns[symbol]['signal']:
                    self.order.check_open_bot_order(
                        symbol, ns[symbol]['entry'], ns[symbol]['stoploss'])
                    time.sleep(3)
            signal = ns[symbol]['signal']
            if signal:
                if self.is_new_signal_symbol(ns, symbol):
                    entry = ns[symbol]['entry']
                    stoploss = ns[symbol]['stoploss']
                    if signal in [-1, 1]:  # signal has open position
                        if signal == 1:
                            if self.order.props[symbol]['qty'] > 0 or self.client.open_contracts(symbol) > 0:
                                self.check_modify(symbol, stoploss)
                            elif self.client.open_contracts(symbol) < 0:
                                print('Closing {} order.'.format(
                                    symbol), flush=True)
                                close = self.order.close(
                                    symbol, qty=-self.order.props[symbol]['qty'])
                                if close:
                                    print('Closed open Bot old short position in {}, because now the Bot\'s Position is long.'.format(
                                        symbol), flush=True)
                                else:
                                    print('Error closing {} order.'.format(
                                        symbol), flush=True)
                            else:
                                cp = self.client.last_current_price(symbol)
                                if cp < entry:
                                    sl_dist = abs(stoploss-entry)
                                    sl_new_dist = abs(cp - stoploss)
                                    if sl_new_dist > 0.15 * sl_dist:
                                        time.sleep(2)
                                        contracts = self.order.calc_pos_size(
                                            symbol, sl_new_dist)
                                        print('Open market order long into open Signal. {} {} Contracts, Stoploss: {}'.format(
                                            symbol, contracts, stoploss), flush=True)
                                        self.order.bracket_market_order(
                                            symbol, contracts, stoploss, cp)
                        else:
                            if self.order.props[symbol]['qty'] < 0 or self.client.open_contracts(symbol) < 0:
                                self.check_modify(symbol, stoploss)
                            elif self.client.open_contracts(symbol) > 0:
                                print('Closing order on {}.'.format(
                                    symbol), flush=True)
                                close = self.order.close(
                                    symbol, qty=-self.order.props[symbol]['qty'])
                                if close:
                                    print('Closed open Bot old long position in {}, because now the Bot\'s Position is short.'.format(
                                        symbol), flush=True)
                                else:
                                    print('Error closing {} order.'.format(
                                        symbol), flush=True)
                            else:
                                cp = self.client.last_current_price(symbol)
                                if cp > entry:
                                    sl_dist = abs(stoploss-entry)
                                    sl_new_dist = abs(cp - stoploss)
                                    if sl_new_dist > 0.15 * sl_dist:
                                        time.sleep(2)
                                        contracts = self.order.calc_pos_size(
                                            symbol, sl_new_dist)
                                        print('Open market order short into open Signal. {} {} Contracts, Stoploss: {}'.format(
                                            symbol, contracts, stoploss), flush=True)
                                        self.order.bracket_market_order(
                                            symbol, -contracts, stoploss, cp)
                    elif signal in [-2, 2]:  # signal has pending order
                        self.manage_open_stop_orders(symbol)
                        contracts = self.order.calc_pos_size(
                            symbol, abs(entry - stoploss))
                        if signal == 2:
                            print('Open bracket stop order long. {} {} Contracts, Entry: {}, Stoploss: {}'.format(
                                symbol, contracts, entry, stoploss), flush=True)
                            self.order.bracket_stop_order(
                                symbol, contracts, entry, stoploss)
                        else:
                            print('Open bracket stop order short. {} {} Contracts, Entry: {}, Stoploss: {}'.format(
                                symbol, contracts, entry, stoploss), flush=True)
                            self.order.bracket_stop_order(
                                symbol, -contracts, entry, stoploss)
                    else:
                        if self.order.props[symbol]['open'] or self.client.open_contracts(symbol) > 0:
                            self.order.close(symbol)
            elif signal != 0:
                self.manage_open_stop_orders(symbol)
                print('This position update in {} is only for premium members. Next update: {}'.format(symbol,
                                                                                                       self.ceil_dt(datetime.datetime.now(), datetime.timedelta(minutes=30))), flush=True)

    def run(self):
        # Main loop
        self.order = BitmexOrder(self.symbols,
                                 self.client, self.settings, self._settings_path)
        while True:
            signal = self.get_api_signal()
            if not signal:
                print('Trying again in 1 Minute.', flush=True)
                time.sleep(60)
            else:
                self.process_signals(signal, start=True)
                print(
                    'BOT IS RUNNING... **(ignore potential bravado.core warning)**', flush=True)
                break
        while True:
            time.sleep(10)
            self.me_count += 1
            self.order.manage_entries(self.symbols, me_count=self.me_count)
            now = datetime.datetime.utcnow()
            if now.minute % 60 == 0:
                exec_minute = now.minute
                time.sleep(19 + self.rand_sec(start=1, end=3))
                count_s_tries = 0
                while True:
                    signal = self.get_api_signal()
                    if not signal:
                        # in case the receiving of signal is not authorized
                        break
                    elif self.is_new_signal(signal):
                        # make sure to get the signal
                        self.process_signals(signal)
                        break
                    count_s_tries += 1
                    if count_s_tries > 22:
                        print('No new signal.', flush=True)
                        break
                    time.sleep(self.rand_sec())
                while True:
                    time.sleep(10)
                    self.order.manage_entries(
                        self.symbols, me_count=self.me_count)
                    if datetime.datetime.utcnow().minute != exec_minute:
                        break
