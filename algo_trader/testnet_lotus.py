from algo_trader.clients import BitmexClient, BitmexData, BitmexTrade
from algo_trader.settings import api_links
import time
import sys
import os
import importlib
import random

settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "settings")
settings_file = 'testnet_lotus_settings.py'
broker_name = 'Bitmex Testnet'
strategy_name = 'Lotus'


def user_inputs():
    if os.path.exists(os.path.join(settings_path, settings_file)):
        return file_change_input()
    else:
        return file_create_input()


def file_change_input():
    strat_token, api_key = '', ''
    pos_size = 0
    from algo_trader.settings import testnet_lotus_settings as settings
    if not settings.STRATEGY_TOKEN:
        strat_token = input("Submit your "+broker_name+" Strategytoken: ")
    if not settings.API_KEY:
        api_key = input("Submit your "+broker_name+" API ID: ")
    if not settings.POSITION_SIZE:
        pos_size = input("Choose your Position Size per trade in %: ")
        pos_size = check_pos_size(pos_size)
    if strat_token or api_key or pos_size != 0:
        os.remove(settings_path + settings_file)
        make_py_file(settings_path, settings_file,
                     settings.STRATEGY_TOKEN or strat_token,
                     settings.API_KEY or api_key,
                     settings.POSITION_SIZE or pos_size)
    import algo_trader.settings
    importlib.reload(algo_trader.settings)
    from algo_trader.settings import testnet_lotus_settings as settings
    return check_settings(str(settings.STRATEGY_TOKEN),
                          settings.API_KEY,
                          settings.POSITION_SIZE)


def file_create_input():
    strat_token = input("Submit your " + broker_name + " Strategytoken: ")
    api_key = input("Submit your " + broker_name + " API ID: ")
    pos_size = input("Choose your Position Size per trade in %: ")
    pos_size = check_pos_size(pos_size)
    make_py_file(settings_path, settings_file,
                 strat_token, api_key, pos_size)
    return check_settings(strat_token, api_key, pos_size)


def check_pos_size(pos_size, max_position_size=10):
    try:
        float(pos_size)
    except ValueError:
        new_size = input("Position Size is not a number,"
                         " please type it in again: ")
        return check_pos_size(new_size, max_position_size=max_position_size)
    if float(pos_size) > max_position_size:
        new_size = input("Position Size is over " + str(max_position_size) +
                         " %, please type in a lower size: ")
        return check_pos_size(new_size, max_position_size=max_position_size)
    return pos_size


def check_settings(strat_token, api_key, pos_size):
    while True:
        qr = input("Start Strategy '" + strategy_name + "' with"
                   "\n\tBroker: " + broker_name +
                   "\n\tToken: {}..."
                   "\n\tAPI ID: {}"
                   "\n\tPosition Size: {} %\n\n"
                   "Do you want to continue? ['y' for yes, 'n' for no, 'c' for"
                   " change settings] "
                   .format(strat_token[:4], api_key, pos_size))
        if qr == '' or qr[0].lower() not in ['y', 'n', 'c']:
            print("Please answer with 'y' for yes, 'n' for no or 'c' for "
                  "change settings (no '' to be typed in).")
        elif qr[0].lower() == 'c':
            return file_create_input()
        else:
            return qr[0].lower(), strat_token, api_key, pos_size


def make_py_file(filepath, filename, strat_token, api_key, pos_size):
    with open(os.path.join(filepath, filename), 'w') as f:
        f.write('''\
STRATEGY_TOKEN = '{}'
API_KEY = '{}'
POSITION_SIZE = {}
'''.format(strat_token, api_key, pos_size))


answer, strat_token, api_key, pos_size = user_inputs()
api_secret = ''

if answer == 'y':
    api_secret =\
        input('Submit your Bitmex Testnet API Secret to start the Bot: ')
if answer == 'n':
    print("Shutting down...")
    sys.exit()

client = BitmexClient(api_key=api_key,
                      api_secret=api_secret)
api_secret = ''


if not client.is_connected:
    print("Invalid API ID or API Secret, please restart and provide the right keys")
    # empty the inputs
    os.remove(os.path.join(settings_path, settings_file))
    sys.exit()

data = BitmexData(client)
trade = BitmexTrade(client, data, pos_size)


def get_api_signal():
    pass


def rand_sec():
    return random.randrange(1, 60) / 100

# Main loop
while True:
    if round(time.time()) % 15 == 0:
        act = get_api_signal()
        trade.process_signal(act)

        time.sleep(2)
    if round(time.time()) % 2 == 0:
        pass

"""
every 15 minutes make request and check if has new timestamp,
first time when checked (think logic) maybe first is 0, but if first signal
is > 0 then do nothing (can check when first == 0), then of course put it in
the `last` variable

then add a random 0-0.5 second wait logic if not new timestamp to check for new
timestamp

then activate the trade engine depending on incoming data to send request to
server. learn how to use python request module with jwt. make a test first

in the other generator file: make it so that it will create a test output
that is a timestamp to check if it refreshes

in the flask view: think the logic for an IP double check, check the token
(where to store the token?) and then give the json response if the check is
good. also learn and apply rate limits for the api call.

then make the ready version, install it on the server with password protection
and run the two files, make sure to add some prints in between and make sure
to monitor them. (maybe with logging?? have to learn that too...) and then
yea.. monitor it and see if it executes orders correct, what is the spread,
will it make SL correct (also ideas for the right comments)
"""
