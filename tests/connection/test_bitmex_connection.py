from algo_trader.clients.bitmex import BitmexClient

test_id = 'Wy-golkVr1wwO2-jy8lDOzzU'
test_secret = 'fRRvX8rMh6_QkcZRANs1maqzHYnFBunit4uMr87ub2j_eREz'
client = BitmexClient(api_key=test_id,
                      api_secret=test_secret)


def test_clientConnection():
    '''Tests if bitmex client can connect to testnet'''

    assert client.is_connected
