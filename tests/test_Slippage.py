from algo_trader.clients import BitmexClient

client = BitmexClient(api_key='',
                      api_secret='', testnet=False)

_symbols = ["XBTUSD", "ETHUSD"]
symbol = "XBTUSD"

entry_acc_balance = {}
between_profits = {}
for symbol in _symbols:
    between_profits[symbol] = .0
    entry_acc_balance[symbol] = .0


# entry
entry_acc_balance[symbol] = 880250

acc_pos_size = 0.01

# current_acc_balance = client.acc_balance
current_acc_balance = client.client.User.User_getMargin().result()[
    0]['walletBalance']

between_profs = .0
for sym in _symbols:
    if symbol != sym:
        between_profs += between_profits[sym]
        between_profits[sym] = .0

# real acc balance difference counting the between profits
acc_balance_diff = entry_acc_balance[symbol] - \
    current_acc_balance + between_profs

print("current_acc_balance", current_acc_balance)

# in acc balance difference
between_profits[symbol] += acc_balance_diff

initial_risk_points = abs(60322.5 - 60443.5)
pnl_points = 62014 - 60443.5
pnl_rr = pnl_points / initial_risk_points

print("initial_risk_points", initial_risk_points)
print("pnl_points", pnl_points)
print("pnl_rr", pnl_rr)

pnl_rel_expected = entry_acc_balance[symbol] * (
    1 + (pnl_rr * acc_pos_size))
pnl_rel_real = entry_acc_balance[symbol] * (
    1 + (acc_balance_diff / entry_acc_balance[symbol]))

print("pnl_rel_expected", pnl_rel_expected)
print("pnl_rel_real", pnl_rel_real)

# slippage is real acc balance change relative - executed pnl percent
print("Slippage: {}%".format(
    round((pnl_rel_real - pnl_rel_expected) * 100, 2)), flush=True)

entry_acc_balance[symbol] = current_acc_balance
