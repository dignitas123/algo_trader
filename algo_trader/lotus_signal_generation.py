import time
import datetime
import chainer
from chainer import serializers
import chainer.functions as F
import chainer.links as L
import sqlite3
from algo_trader.clients import BitmexClient, BitmexData
import numpy as np


def build_empty_dddqn():
    class Q_Network(chainer.Chain):
        # output size = number of states
        def __init__(self, input_size, hidden_size, output_size):
            super(Q_Network, self).__init__(
                fc1=L.Linear(input_size, hidden_size),
                fc2=L.Linear(hidden_size, hidden_size),
                fc3=L.Linear(hidden_size, hidden_size//2),
                fc4=L.Linear(hidden_size, hidden_size//2),
                state_value=L.Linear(hidden_size//2, 1),
                advantage_value=L.Linear(hidden_size//2, output_size)
            )
            self.input_size = input_size
            self.hidden_size = hidden_size
            self.output_size = output_size

        def __call__(self, x):
            h = F.relu(self.fc1(x))
            h = F.relu(self.fc2(h))
            hs = F.relu(self.fc3(h))
            ha = F.relu(self.fc4(h))
            state_value = self.state_value(hs)
            advantage_value = self.advantage_value(ha)
            advantage_mean = (F.sum(advantage_value, axis=1)
                              / float(self.output_size)).reshape(-1, 1)
            q_value = F.concat([state_value for _ in range(self.output_size)],
                               axis=1) + (advantage_value
                                          - F.concat([advantage_mean for _ in
                                                      range(self.output_size)],
                                                     axis=1))
            return q_value

        def reset(self):
            self.zerograds()

    return Q_Network(input_size=18, hidden_size=100, output_size=3)


def get_lotus_features(data):
    # calculate features
    return [datetime.datetime.utcnow().hour,
            datetime.datetime.utcnow().minute,
            client.positionValue_XBTUSD, 0]\
        + data.close_dists() + data.high_dists() + data.low_dists()


def _query(query, *args):
    con = None
    data = None

    try:
        con = sqlite3.connect('ainvest.sqlite')
        cur = con.cursor()
        cur.execute(query, tuple(args))
        data = cur.fetchall()
        if not data:
            con.commit()
    except sqlite3.Error as e:
        print("Database error: %s" % e)
    except Exception as e:
        print("Exception in _query: %s" % e)
    finally:
        if con:
            con.close()
    return data


"""
user_data = _query("SELECT FIRST_VALUE(tbitmex_id) OVER (ORDER BY apis.id)\
                   , tbitmex_secret, tlotus_position_size FROM users LEFT JOIN\
                apis ON apis.id = users.id WHERE tlotus_active = True")
print("User 0: ", user_data[0][0], user_data[0][1])
TEST_EXCHANGE = True
API_KEY = user_data[0][0]
API_SECRET = user_data[0][1]
TIMEFRAME = '15m'
POSITION_SIZE = float(user_data[0][9])
"""

Q = build_empty_dddqn()
# load the model in the empty DDDQN
serializers.load_npz('DDDQN_BTCUSD_4', Q)

client = BitmexClient(test=False)
data = BitmexData(client)

# Main loop
while True:
    if round(time.time()) % 15 == 0:
        data()  # load new data
        features = get_lotus_features(data)

        # calculate next action based on the features
        act = Q(np.array(features, dtype=np.float32).reshape(1, -1))
        act = np.argmax(act.data)

        time.sleep(2)
    if round(time.time()) % 2 == 0:
        pass
