# Dollar Cost Averaging Strategy
    # https://community.backtrader.com/topic/4010/dollar-cost-averaging-strategy/15

from __future__ import (absolute_import, division, print_function, unicode_literals)

from matplotlib.style import available
from dca        import DCA

import os
import datetime

import backtrader as bt
import pandas     as pd


STARTING_CASH = 1000000
ORACLE        = "historical_data/oracle.csv"
BNGO          = "historical_data/BNGO.csv"


"""
TODO
    1. Create a dynamic or static DCA: As our money increases or decreases with the DCA method,
                                        recalculate our base_order_size and safety_order_size so 
                                        that the final safety order will use 100% of our money
    2. PULL DATA FROM CRYPTO FUTURES TO SEE WHEN LIQUIDATION OCCURES
    3. Time frames: Buy and hold might win out in the long run, but what time frames does DCA when out?

"""

class DCA3C(bt.Strategy):
    # DCA values
    params = (
        ('target_profit_percent',        1),
        ('safety_orders_max',            7),
        ('safety_orders_active_max',     7),
        ('safety_order_volume_scale',    2.5),
        ('safety_order_step_scale',      1.56),
        ('safety_order_price_deviation', 1.3),
        ('base_order_size_usd',          8100), # in terms of USD
        ('safety_order_size_usd',        4050), # in terms of USD
    )

    def log(self, txt: str, dt=None) -> None:
        ''' Logging function fot this strategy'''
        dt = dt or self.data.datetime[0]
        
        if isinstance(dt, float):
            dt = bt.num2date(dt)

        _dt = dt.isoformat().split("T")[0]
        print('%s, %s' % (_dt, txt))
        return

    def __init__(self) -> None:
        # Update TP to include making back the commission
        # self.params.tp += commission

        self.start_cash = 0

        # Store the sell order (take profit) so we can cancel and update tp price with ever filled SO
        self.take_profit_order = None
        
        # Store all the Safety Orders so we can cancel the unfilled ones after TPing
        self.safety_orders = []
        # self.order                 = None
        self.dca                   = None
        self.is_first_safety_order = True
        return

    def money_format(self, money: float) -> str:
        return "${:,.6f}".format(money)

    def print_ohlc(self) -> None:
        date  = self.data.datetime.date()
        open  = self.money_format(self.data.open[0])
        high  = self.money_format(self.data.high[0])
        low   = self.money_format(self.data.low[0])
        close = self.money_format(self.data.close[0])
        print(f"{date} Open: {open}, High: {high}, Low: {low}, Close: {close}")
        return

    def print_orders(self) -> None:
        print()
        for order in self.safety_orders:
            print(f"Price: {order.price} Quantity: {order.size}, Status: {order.status}, Alive: {order.alive()}")  
        return

    def set_take_profit(self) -> None:
        print("\nCANCELED TAKE PROFIT SELL ORDER")
        print(f"Price: {self.money_format(self.take_profit_order.price)}, Size: {self.take_profit_order.size}")

        if self.is_first_safety_order:
            self.is_first_safety_order = False
            quantity_to_sell           = self.dca.total_quantities[0]
            required_price             = self.dca.required_price_levels[0]

            self.take_profit_order = self.sell(price=required_price,
                                            size=quantity_to_sell,
                                            exectype=bt.Order.Limit)
            
            self.dca.remove_top_safety_order()
            
            safety_order = self.buy(price=self.dca.price_levels[0],
                                        size=self.dca.quantities[0],
                                        exectype=bt.Order.Limit,
                                        oco=self.take_profit_order) # oco = One Cancel Others
        else:
            quantity_to_sell = self.dca.total_quantities[0]
            
            self.dca.remove_top_safety_order()
            
            required_price = self.dca.required_price_levels[0]

            self.take_profit_order = self.sell(price=required_price,
                                            size=quantity_to_sell,
                                            exectype=bt.Order.Limit)

            safety_order = self.buy(price=self.dca.price_levels[0],
                                        size=self.dca.quantities[0],
                                        exectype=bt.Order.Limit,
                                        oco=self.take_profit_order) # oco = One Cancel Others
        
        self.safety_orders.append(safety_order)
        
        print("\nNEW TAKE PROFIT ORDER")
        print(f"Price: {self.money_format(self.take_profit_order.price)}, Size: {self.take_profit_order.size}")
        print()
        return

    def notify_order(self, order: bt.order.BuyOrder) -> None:
        if order.status in [order.Submitted, order.Accepted]:
            return
        elif order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
            elif order.issell():
                self.log('SELL EXECUTED, Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
                
                self.safety_orders         = []
                self.take_profit_order     = None
                self.is_first_safety_order = True
        elif order.status in [order.Canceled]:
            # print(order.ordtype)
            self.log(f'ORDER CANCELED: Size: {order.size}')
            # if the sell was canceled, that means a safety order was filled. 
            # time to put in a new take profit order
            if order.issell(): # if the canceled order was a sell (aka. the take profit order)
                self.set_take_profit()
        elif order.status in [order.Margin]:
            self.log('ORDER MARGIN: Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
        elif order.status in [order.Rejected]:
            self.log('ORDER REJECTED: Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.size, order.price, order.value, order.comm))
        # self.order = None
        return

    def notify_trade(self, trade: bt.trade.Trade) -> None:
        if trade.isclosed:
            self.log('OPERATION PROFIT, GROSS %.6f, NET %.6f, Size: %.6f' % (trade.pnl, trade.pnlcomm, trade.size))
        return

    def start_new_deal(self) -> None:
        print('{} OPERATE: send Buy, close {}'.format(self.data.datetime.date(), self.data.close[0]))

        entry_price = self.data.close[0]

        print('')
        print('*** NEW DEAL ***')

        self.dca = DCA(entry_price,
                        self.params.target_profit_percent,
                        self.params.safety_orders_max,
                        self.params.safety_orders_active_max,
                        self.params.safety_order_volume_scale,
                        self.params.safety_order_step_scale,
                        self.params.safety_order_price_deviation,
                        int(self.params.base_order_size_usd/entry_price),
                        int(self.params.safety_order_size_usd/entry_price)
                    )
        
        # self.dca.print_table()

        # available_cash = self.broker.


        # BASE ORDER BUY
        buy_order = self.buy(price=entry_price, size=int(self.params.base_order_size_usd/entry_price))
        self.safety_orders.append(buy_order)

        # BASE ORDER SELL (if this sell is filled, cancel all the other safety orders)
        tp_price = entry_price + ( entry_price * (self.params.target_profit_percent/100) )
        
        self.take_profit_order = self.sell(price=tp_price,
                                            size=int(self.params.base_order_size_usd/entry_price),
                                            exectype=bt.Order.Limit)

        """instead of submitting the takeprofit and all safety orders at a single time,
        submit one safety order and one take profit order until one of them is canceled!"""
        safety_order = self.buy(price=self.dca.price_levels[0],
                                    size=self.dca.quantities[0],
                                    exectype=bt.Order.Limit,
                                    oco=self.take_profit_order) # oco = One Cancel Others

        self.safety_orders.append(safety_order)
        return

    def next(self) -> None:
        print("\n-> NEXT ->")
        self.print_ohlc()

        if len(self.safety_orders) == 0:
            self.start_new_deal()
        return

    def start(self) -> None:
        self.start_cash = self.broker.getvalue()
        print(f"Starting Portfolio Value: {self.start_cash}")
        return

    def stop(self) -> None:
        profit = round(self.broker.getvalue() - self.start_cash, 2)
        roi    = (self.broker.get_value() / self.start_cash) - 1.0

        print("\n^^^^ Finished Backtesting ^^^^^")
        print(f"Total Profit:          {self.money_format(profit)}")
        print('ROI:                   {:.2f}%'.format(100.0 * roi))
        print(f"Final Portfolio Value: {self.money_format(round(self.broker.getvalue(), 2))}")
        return


if __name__ == '__main__':
    os.system("cls")

    cerebro = bt.Cerebro()
    cerebro.broker.set_cash(STARTING_CASH)

    df = pd.read_csv(ORACLE)
    df.drop(columns=["Adj Close"], inplace=True)
    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    df.set_index('Date', inplace=True)

    # data = bt.feeds.PandasData(dataname=df, openinterest=-1)
    data = bt.feeds.PandasData(dataname=df,
                               fromdate=datetime.datetime(1995, 1, 3),
                               todate=datetime.datetime(2002, 12, 31),
                               openinterest=-1)

    cerebro.adddata(data)
    cerebro.addstrategy(DCA3C)

    cerebro.run()
    cerebro.plot()


    #############################
    # ('target_profit_percent',        1),
    # ('safety_orders_max',            7),
    # ('safety_orders_active_max',     7),
    # ('safety_order_volume_scale',    2.5),
    # ('safety_order_step_scale',      1.56),
    # ('safety_order_price_deviation', 1.3),
    # ('base_order_size_usd',          8100), # in terms of USD
    # ('safety_order_size_usd',        4050), # in terms of USD

    # Finished Backtesting
    # Final Portfolio Value: $1019720.15
    # Total Profit: $19720.15
    #############################


