def file_create_input(symbols=['XBTUSD']):
    token = input("Submit your Strategytoken (found in your member area): ")
    api_key = input("Submit your API Key (ID): ")
    api_secret = input("Submit your API Secret: ")
    symbol_settings = []
    for symbol in symbols:
        pos_size = input(
            "Choose your Position Size for {} per trade in %: ".format(symbol))
        symbol_settings.append("{}{}".format(symbol, pos_size))
    return make_pickle_file()

def make_pickle_file():
    return "PICKLE YO"

file_create_input(symbols=["XBTUSD", "ETHUSD"])