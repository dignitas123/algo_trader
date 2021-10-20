# import unittest

# from algo_trader.clients import BinanceOrder

# class TestStringMethods(unittest.TestCase):
    
#     def test_is


# if __name__ == '__main__':
#     unittest.main()

import datetime

interval = 30
count = 15

now = datetime.datetime.utcnow()
minutenow = now.minute
overdue_min = minutenow % interval
i = 0

time = (now - datetime.timedelta(minutes=count*interval + overdue_min))

print(time)