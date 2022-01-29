from __future__           import (absolute_import, division, print_function, unicode_literals)
from strategies.DCA3C.dca import DCA

import backtrader as bt




class DCA3C(bt.Strategy):
    ############################################################################################
    """
    SCALP7 $10,000 start
        period 1: 2.03%
        period 2: 2.49%
        period 3: 1.10%

        period 4: 2.03%
        period 5: 1.42%
        period 6: 0.43%
        
        period 7: 0.06%
        period 8: 0.49%
        period 9: 0.24%

        period 10: ??? (ALL)

    """
    # params = (
    #     ('target_profit_percent',        1),
    #     ('trail_percent',                0.002), # even though it says its a percent, its a decimal -> 0.2%
    #     ('safety_orders_max',            7),
    #     ('safety_orders_active_max',     7),
    #     ('safety_order_volume_scale',    2.5),
    #     ('safety_order_step_scale',      1.56),
    #     ('safety_order_price_deviation', 1.3),
    #     ('base_order_size_usd',          20),
    #     ('safety_order_size_usd',        4)
    # )

    ############################################################################################
    
    """
    SCALP 15
        period 1: 6.97%
        period 2: 2.64%
        period 3: 3.23% (bear market AVG 4.28%)

        period 4: 8.59%
        period 5: 5.94%
        period 6: 1.89% (bull market AVG 5.47%)
        
        period 7: 0.95%
        period 8: 1.72%
        period 9: 0.88% (sideways market AVG 1.183%)

        period 10: 174.57% (ALL)
    """

    params = (
        ('target_profit_percent',        1),
        ('trail_percent',                0.002), # even though it says its a percent, its a decimal -> 0.2%
        ('safety_orders_max',            15),
        ('safety_orders_active_max',     15),
        ('safety_order_volume_scale',    1.2),
        ('safety_order_step_scale',      1.16),
        ('safety_order_price_deviation', 1.0),
        ('base_order_size_usd',          20),
        ('safety_order_size_usd',        10)
    )


    ############################################################################################

    """
    SCALP20 
        period 1: 5.58%
        period 2: 4.20%
        period 3: 2.75%

        period 4: 2.75%
        period 5: 3.37%
        period 6: 0.99%

        period 7: 0.76%
        period 8: 1.14%
        period 9: 0.59%

        period 10: ??? (ALL)

    """
    # params = (
    #     ('target_profit_percent',        1),
    #     ('trail_percent',                0.002), # even though it says its a percent, its a decimal -> 0.2%
    #     ('safety_orders_max',            20),
    #     ('safety_orders_active_max',     20),
    #     ('safety_order_volume_scale',    1.2),
    #     ('safety_order_step_scale',      1.05),
    #     ('safety_order_price_deviation', 1.0),
    #     ('base_order_size_usd',          20),
    #     ('safety_order_size_usd',        10)
    # )

    ############################################################################################
    
    """
    SCALP26 
        period 1: 2.33%
        period 2: 1.73%
        period 3: 1.01%
        period 4: 2.08%
        period 5: 1.30%
        period 6: 0.44%
        period 7: 0.35%
        period 8: 0.45%
        period 9: 0.24%

        period 10: ??? (ALL)

    """
    params = (
        ('target_profit_percent',        1),
        ('trail_percent',                0.002), # even though it says its a percent, its a decimal -> 0.2%
        ('safety_orders_max',            26),
        ('safety_orders_active_max',     26),
        ('safety_order_volume_scale',    1.2),
        ('safety_order_step_scale',      1.05),
        ('safety_order_price_deviation', 1.0),
        ('base_order_size_usd',          20),
        ('safety_order_size_usd',        10)
    )

    ############################################################################################

    """
    BUY & HOLD
        period 1: -53.19%
        period 2: -59.49%
        period 3: -24.28%
        period 4: 399.52%
        period 5: 106.58%
        period 6: 61.47%
        period 7: 3.47%
        period 8: 42.69%
        period 9: 10.87%

        period 10: ??? (ALL)

    """

    ############################################################################################

    def __init__(self) -> None:
        # if you use this, you will need a warm up
        self.hullma_20_day = bt.indicators.HullMovingAverage(self.data, period=30240)  # 21 day warm up
        self.ma_200_day    = bt.indicators.HullMovingAverage(self.data, period=289440) # 201 day warm up

        # Store all the Safety Orders so we can cancel the unfilled ones after TPing
        self.safety_orders         = []

        # Store the take profit order so we can cancel and update take profit price with every filled safety order
        self.take_profit_order = None
        
        self.dca                   = None
        self.time_period           = None
        self.is_first_safety_order = True

        self.start_cash            = 0
        self.start_value           = 0
        return

    def log(self, txt: str, dt=None) -> None:
        ''' Logging function fot this strategy'''
        dt      = dt or self.data.datetime[0]
        minutes = self.datas[0].datetime.time(0)

        if isinstance(dt, float):
            dt = bt.num2date(dt)

        _dt = dt.isoformat().split("T")[0]
        print('%s, %s' % (_dt, txt))
        return

    def money_format(self, money: float) -> str:
        return "${:,.6f}".format(money)

    def print_ohlc(self) -> None:
        date    = self.data.datetime.date()
        minutes = self.datas[0].datetime.time(0)
        open    = self.money_format(self.data.open[0])
        high    = self.money_format(self.data.high[0])
        low     = self.money_format(self.data.low[0])
        close   = self.money_format(self.data.close[0])
        print(f"[{date} {minutes}] Open: {open}, High: {high}, Low: {low}, Close: {close}")
        return

    def __set_take_profit(self) -> None:
        if self.take_profit_order is None:
            return

        print("\nCANCELED TAKE PROFIT SELL ORDER")
        print(f"Price: {self.money_format(self.take_profit_order.price)}, Size: {self.take_profit_order.size}\n")

        safety_order = None

        if self.is_first_safety_order:
            self.is_first_safety_order = False

            self.take_profit_order = self.sell(price=self.dca.required_price_levels[0],
                                               size=self.dca.total_quantity_levels[0],
                                               trailpercent=self.params.trail_percent,
                                               plimit=self.dca.required_price_levels[0],
                                               exectype=bt.Order.StopTrailLimit)
                                                # exectype=bt.Order.StopTrail)
                                                # exectype=bt.Order.Limit)
            
            self.dca.remove_top_safety_order()

            safety_order = self.buy(price=self.dca.price_levels[0],
                                    size=self.dca.safety_order_quantity_levels[0],
                                    exectype=bt.Order.Limit,
                                    oco=self.take_profit_order) # oco = One Cancel Others
        else:
            self.take_profit_order = self.sell(price=self.dca.required_price_levels[0],
                                               size=self.dca.total_quantity_levels[0],
                                               trailpercent=self.params.trail_percent,
                                               plimit=self.dca.required_price_levels[0],
                                               exectype=bt.Order.StopTrailLimit)
                                                # exectype=bt.Order.StopTrail)
                                                # exectype=bt.Order.Limit)

            self.dca.remove_top_safety_order()

            # check if we have placed all safety orders
            if len(self.dca.price_levels) > 0:
                safety_order = self.buy(price=self.dca.price_levels[0],
                                        size=self.dca.safety_order_quantity_levels[0],
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
                self.log('BUY EXECUTED, Size: {:,.8f} Price: {:,.8f}, Cost: {:,.8f}, Comm {:,.8f}'.format(order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
                if order.exectype == 0:
                    entry_price       = order.executed.price
                    base_order_size   = order.executed.size
                    size              = self.params.safety_order_size_usd

                    # If the cost of the stock/coin is larger than our base order size, 
                    # then we can't order in integer sizes. We must order in fractional sizes                    
                    safety_order_size = size//entry_price if size//entry_price != 0 else size/entry_price

                    self.dca = DCA( entry_price_usd=entry_price,
                                    target_profit_percent=self.params.target_profit_percent,
                                    safety_orders_max=self.params.safety_orders_max,
                                    safety_orders_active_max=self.params.safety_orders_active_max,
                                    safety_order_volume_scale=self.params.safety_order_volume_scale,
                                    safety_order_step_scale=self.params.safety_order_step_scale,
                                    safety_order_price_deviation_percent=self.params.safety_order_price_deviation,
                                    base_order_size=base_order_size,
                                    safety_order_size=safety_order_size,
                                    total_usd=self.broker.get_cash()
                                )
                    
                    take_profit_price = self.dca.base_order_required_price

                    # BASE ORDER SELL (TAKE PROFIT: if this sell is filled, cancel all the other safety orders)
                    self.take_profit_order = self.sell(price=take_profit_price,
                                                        size=base_order_size,
                                                        trailpercent=self.params.trail_percent,
                                                        plimit=take_profit_price,
                                                        exectype=bt.Order.StopTrailLimit)
                                                        # exectype=bt.Order.StopTrail)
                                                        # exectype=bt.Order.Limit)

                    """instead of submitting the takeprofit and all safety orders at a single time,
                    submit one safety order and one take profit order until one of them is canceled!"""
                    safety_order = self.buy(price=self.dca.price_levels[0],
                                                size=self.dca.safety_order_quantity_levels[0],
                                                exectype=bt.Order.Limit,
                                                oco=self.take_profit_order) # oco = One Cancel Others

                    self.safety_orders.append(safety_order)
            elif order.issell():
                self.log('SELL EXECUTED, Size: {:,.8f} Price: {:,.8f}, Cost: {:,.8f}, Comm {:,.8f}'.format(order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
                
                if self.position.size != 0:
                    print()
                    print(self.position)
                    print()

                # reset variables
                self.safety_orders         = []
                self.take_profit_order     = None
                self.is_first_safety_order = True
        elif order.status in [order.Canceled]:
            # if the sell was canceled, that means a safety order was filled and its time to put in a new updated take profit order.
            if order.issell():
                self.__set_take_profit()
            elif order.isbuy():
                self.log(f'BUY ORDER CANCELED: Size: {order.size}')
        elif order.status in [order.Margin]:
            self.log('ORDER MARGIN: Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.executed.size, order.executed.price, order.executed.value, order.executed.comm))
            print()
            print("Cash:", self.broker.get_cash())
            print("Value", self.broker.get_value())
            print()
            print(order)
            print()
            self.dca.print_table()
            print()
        elif order.status in [order.Rejected]:
            self.log('ORDER REJECTED: Size: %.6f Price: %.6f, Cost: %.6f, Comm %.6f' % (order.size, order.price, order.value, order.comm))
            print()
            print(order)
            print()
        else:
            self.log("ORDER UNKNOWN: SOMETHNG WENT WRONG!")
            print()
            print(order)
            print()
        return

    def notify_trade(self, trade: bt.trade.Trade) -> None:
        if trade.isclosed:
            self.log('OPERATION PROFIT, GROSS %.6f, NET %.6f, Size: %.6f' % (trade.pnl, trade.pnlcomm, trade.size))

            if trade.pnl <= 0 or trade.pnlcomm <= 0:
                print(trade.pnl, trade.pnlcomm)
                print()
                print(trade)
                print()
        return

    def __start_new_deal(self) -> None:
        print("\n*** NEW DEAL ***")

        # BASE ORDER BUY
        entry_price = self.data.close[0]
        size        = self.params.base_order_size_usd // entry_price

        # If the cost of the stock/coin is larger than our base order size, 
        # then we can't order in integer sizes. We must order in fractional sizes
        base_order_size = size if size != 0 else self.params.base_order_size_usd/entry_price
        
        buy_order = self.buy(size=base_order_size, exectype=bt.Order.Market)
        self.safety_orders.append(buy_order)
        return

    def next(self) -> None:
        self.print_ohlc()

        if len(self.safety_orders) == 0:
            self.__start_new_deal()
        return

    def start(self) -> None:
        self.time_period = self.datas[0].p.todate - self.datas[0].p.fromdate
        self.start_cash  = self.broker.get_cash()
        self.start_value = self.broker.get_value()

        # print("minperiod: ", self._minperiod)
        # print("minperiods:", self._minperiods)
        return

    def stop(self) -> None:
        total_value = self.broker.get_value()
        profit      = total_value - self.start_cash
        roi         = ((total_value / self.start_cash) - 1.0) * 100
        roi         = '{:.2f}%'.format(roi)

        profit           = self.money_format(round(profit, 2))
        self.start_value = self.money_format(round(self.start_value, 2))
        total_value      = self.money_format(round(total_value, 2))

        print("\n\n^^^^ FINISHED BACKTESTING ^^^^^")
        print()

        print('target_profit_percent',        self.params.target_profit_percent)
        print('trail_percent',                self.params.trail_percent)
        print('safety_orders_max',            self.params.safety_orders_max)
        print('safety_orders_active_max',     self.params.safety_orders_max)
        print('safety_order_volume_scale',    self.params.safety_order_volume_scale)
        print('safety_order_step_scale',      self.params.safety_order_step_scale)
        print('safety_order_price_deviation', self.params.safety_order_price_deviation)
        print('base_order_size_usd',          self.params.base_order_size_usd)
        print('safety_order_size_usd: optimized')

        print(f"Time period:           {self.time_period}")
        print(f"Total Profit:          {profit}")
        print(f"ROI:                   {roi}")
        print(f"Start Portfolio Value: {self.start_value}")
        print(f"Final Portfolio Value: {total_value}")
        return
