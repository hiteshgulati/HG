import numpy_financial as npf
import pandas as pd
from datetime import datetime as dt
import warnings
warnings.filterwarnings('ignore')
from dateutil.relativedelta import relativedelta
import os
from scipy.stats import norm
import alm_utils


def run():
    dravid = Instrument('dravid',type='debt',r_annual=.06, entry_transaction_cost=10,exit_transaction_cost=20)
    cash_instrument = Instrument('cash',type='debt',r_annual=0, entry_transaction_cost=0,exit_transaction_cost=0)


    data_folder_name = 'Data'
    instruments_folder_name = "Instruments"

    date_lists = [dt(2015,2,1),dt(2015,7,3),dt(2017,2,4),dt(2022,2,7)]

    nifty = Instrument('Nifty',type='equity',ticker='N50',entry_transaction_cost=20, exit_transaction_cost=20)
    nifty.fetch_historical(folder_path=os.path.join(data_folder_name, instruments_folder_name),file_name='NIFTY50_Data.csv')
    dravid = Instrument('dravid',type='debt',r_annual=.06, entry_transaction_cost=10,exit_transaction_cost=20)
    nifty_p = Position(instrument=nifty,date=date_lists[0],investment_amount=10_000)
    dravid_p = Position(instrument=dravid,date=date_lists[0],investment_amount=10_000)
    cash_p = Position(instrument=cash_instrument,date=date_lists[0],investment_amount=10_000)
    print(f'''{date_lists[0].strftime("%d %b %y")}\n\t{nifty_p}\n\t{dravid_p}\n\t{cash_p}''')

    for date in date_lists[1:]:
        nifty_p.update(date=date)
        dravid_p.update(date=date)
        cash_p.withdraw(date=date,amount=7000)
        print(f'''{date.strftime("%d %b %y")}\n\t{nifty_p}\n\t{dravid_p}\n\t{cash_p}''')

    print(alm_utils.to_currency(dravid.future_exit_value(investment_amount=10_000,
        entry_date=date_lists[0],exit_date=date_lists[2])))

    pass


class Instrument:
    def __init__(self,name,type,ticker=None,r_annual=0,
        entry_transaction_cost=0, exit_transaction_cost=0):
        self.name = name
        self.ticker = ticker
        self.type = type
        self.historical = pd.DataFrame()
        self.r_annual = r_annual
        self.entry_transaction_cost = entry_transaction_cost
        self.exit_transaction_cost = exit_transaction_cost
    
    def __repr__ (self):
        return f'''{self.name}'''
    def __str__ (self):
        return self.__repr__()
    
    def fetch_historical(self,folder_path,file_name):
        self.historical = pd.read_csv(os.path.join(folder_path, file_name))
        self.historical['Date'] = pd.to_datetime(self.historical['Date'])
        self.historical.sort_values(by='Date', inplace=True)
        self.historical['change'] = (self.historical['Close'] \
            - self.historical['Close'].shift(periods=1)) \
            / self.historical['Close'].shift(periods=1)
    
    def get_value(self, date):
        return self.historical[self.historical['Date']<=date].iloc[-1]['Close']
    
    
    def get_fall_prob (self, fall,date, lookback_years = None):
        if self.type == 'debt':
            if self.r_annual >= fall:
                return 1
            else: 
                return 0
        if not lookback_years:
            lookback_years = 10
        dist_df = self.historical[self.historical['Date']<=date]\
            .iloc[-(lookback_years*250):]
        dist_prob = dist_df[dist_df['change']<=fall].shape[0] / dist_df.shape[0]
        norm_prob = norm(dist_df['change'].mean(), dist_df['change'].std()).cdf(fall)
        return dist_prob if dist_prob > norm_prob else norm_prob

    def get_return (self,date, lookback_years = None):
        if self.type == 'equity':
            if not lookback_years:
                lookback_years = 10
            return self.historical[self.historical['Date']<=date]\
                .iloc[-(lookback_years*250):]['change'].mean()
        else:
            return alm_utils.return_conversion(self.r_annual,1,365)
    
    def future_exit_value (self, entry_date, exit_date, investment_amount):
        r = self.get_return(entry_date)
        n_days = (exit_date-entry_date).days
        holding_period_years = n_days/365
        fv = (investment_amount-self.entry_transaction_cost) * (1+r)**n_days - self.exit_transaction_cost
        pnl = fv-investment_amount
        tax_liability = 0
        if pnl > 0:
            if self.type == 'equity':
                if holding_period_years >=1: #Long Term
                    tax_liability = pnl * .1
                else: #Short Term
                    tax_liability = pnl * .15
            elif self.type == 'debt':
                if holding_period_years >=3: #long Term
                    tax_liability = pnl * .2
                else: #short term
                    tax_liability = pnl * .3

        future_exit_value = fv - tax_liability
        return future_exit_value

class Position:
    def __init__(self, instrument, date,investment_amount):
        self.instrument = instrument
        self.entry_date = date
        self.position_name = str(self.instrument) + "_on_" + self.entry_date.strftime('%d%b%y')
        self.pnl = 0
        self.current_value = investment_amount-instrument.entry_transaction_cost
        if self.instrument.type == 'equity':
            self.number_of_units = self.current_value\
                    /self.instrument.get_value(date)
        else: 
            self.number_of_units = 1
        self.entry_value = self.current_value
        self.exit_value = self.current_value - instrument.exit_transaction_cost
        self.tax_liability = 0
        self.last_update = date
        self.is_active = True
    
    def __repr__ (self):
        return f'''{self.position_name} {alm_utils.to_currency(self.current_value)} | exit: {alm_utils.to_currency(self.exit_value)}, entry: {alm_utils.to_currency(self.entry_value)} | update:{self.last_update.strftime('%d%b%y')}'''
    def __str__ (self):
        return self.__repr__()
    def __float__(self):
        return float(self.exit_value)
    
    def update_current_value (self,date):
        if self.instrument.type == 'equity':
            self.current_value = self.instrument.get_value(date) * self.number_of_units
        if self.instrument.type == 'cash':
            pass
        if self.instrument.type == 'debt':
            self.current_value = self.entry_value * (1+alm_utils.return_conversion(self.instrument.r_annual,1,365))**(date-self.entry_date).days
            
    
    def update(self,date):
        self.update_current_value(date)
        self.pnl = self.current_value - self.instrument.exit_transaction_cost - self.entry_value
    
        #Computing tax Component
        holding_period_years = relativedelta(date,self.entry_date).years
        if self.pnl > 0:
            if self.instrument.type == 'equity':
                if holding_period_years >=1: #Long Term
                    self.tax_liability = self.pnl * .1
                else: #Short Term
                    self.tax_liability = self.pnl * .15
            elif self.instrument.type == 'debt':
                if holding_period_years >=3: #long Term
                    self.tax_liability = self.pnl * .2
                else: #short term
                    self.tax_liability = self.pnl * .3
        else:
            self.tax_liability = 0
        self.exit_value = self.current_value - self.tax_liability - self.instrument.exit_transaction_cost
        self.last_update = date

    def future_exit_value(self, date, exit_date):
        r = self.instrument.get_return(date)
        n_days = (exit_date-self.entry_date).days
        holding_period_years = n_days/365
        fv = (self.current_value) * (1+r)**n_days - self.instrument.exit_transaction_cost
        pnl = fv-self.entry_value
        tax_liability = 0
        if pnl > 0:
            if self.type == 'equity':
                if holding_period_years >=1: #Long Term
                    tax_liability = pnl * .1
                else: #Short Term
                    tax_liability = pnl * .15
            elif self.type == 'debt':
                if holding_period_years >=3: #long Term
                    tax_liability = pnl * .2
                else: #short term
                    tax_liability = pnl * .3

        future_exit_value = fv - tax_liability
        return future_exit_value
    
    def withdraw(self,date,amount):
        self.update(date)
        if amount <= self.exit_value:
            self.current_value = self.current_value - amount
            self.exit_value = self.current_value - self.instrument.exit_transaction_cost
            self.last_update = date
            return amount
        else:
            return 0

    def withdraw_full(self,date):
        self.is_active = False
        return self.withdraw(date=date,amount=self.exit_value)


class Goal:
    def __init__ (self,name, maturity_date,inception_date,
        confidence,maturity_value,digestible_loss,wickets,pmt=0):
        self.name = name
        self.maturity_date = maturity_date
        self.inception_date = inception_date
        self.pmt = pmt
        self.confidence = confidence
        self.payday = 1
        self.maturity_value = maturity_value
        self.remaining_digestible_loss = digestible_loss
        self.wickets = wickets
        self.wickets_fallen = 0
        self.each_wicket_appetite = digestible_loss / wickets
        self.current_wicket_appetite = self.each_wicket_appetite
        self.each_wicket_safe_point = 1/wickets
        self.is_hitting = True
        self.cashflows = pd.DataFrame(index=pd.date_range(start=inception_date, end=maturity_date))\
            .reset_index().rename(columns={'index':'date'})
        self.cashflows['downpayment'] = 0
        self.cashflows['spend'] = 0
        self.cashflows['emi'] = 0
        self.cashflows.loc[self.cashflows['date']==inception_date,'downpayment'] = pmt
        self.cashflows.loc[self.cashflows['date']==maturity_date,'spend'] = maturity_value
        self.emi = self.calculate_emi(rf=alm_utils.return_conversion(.06,1,250))
        self.positions = []
        self.current_value = 0
        self.current_positions_pnl = 0
        self.update(inception_date)

    def __repr__ (self):
        return f'''{self.name} | {alm_utils.to_currency(self.maturity_value)} on {self.maturity_date.strftime('%d %b %Y')} | EMI: {alm_utils.to_currency(self.emi)}, Downpayment: {alm_utils.to_currency(self.pmt)}'''
    def __str__ (self):
        return self.__repr__()
        
    def calculate_emi(self,rf):
        tolerance = 1
        emi_guess = npf.pmt(rate = rf, nper=(self.maturity_date-self.inception_date).days/30, 
                        fv=-1*self.maturity_value, pv=self.pmt, when='begin')
        surplus = 0

        while not((surplus>0)&(surplus<tolerance)):
            emi_guess = emi_guess - surplus/((self.maturity_date-self.inception_date).days/30)
            self.cashflows.loc[self.cashflows['date'].dt.day==self.payday,'emi'] = emi_guess
            self.cashflows['cashflow'] = self.cashflows['downpayment'] + self.cashflows['emi'] - self.cashflows['spend']
            surplus = npf.npv(rf,self.cashflows['cashflow'])
            
        self.cashflows.loc[self.cashflows['date'].dt.day==self.payday,'emi'] = emi_guess
        self.cashflows['cashflow'] = self.cashflows['downpayment'] + self.cashflows['emi'] - self.cashflows['spend']
        return emi_guess

    def update_emi(self,date,updated_emi):
        self.cashflows.loc[(self.cashflows['date'].dt.day==self.payday)&(self.cashflows['date']>=date),'emi'] = updated_emi
        self.emi = updated_emi
    
    def collect_cash(self,date):
        available_cash = \
            self.cashflows.loc[self.cashflows['date']==date,'downpayment'] \
                + self.cashflows.loc[self.cashflows['date']==date,'emi']
        if available_cash > 0:
            cash_position = Position(instrument=cash_instrument,date=date,investment_amount=available_cash)
            self.positions.append(cash_position)
        return available_cash
            
    def update(self,date):
        self.collect_cash(date)
        self.current_value = 0
        for position in self.positions:
            position.update()
            self.current_value += position.exit_value
            self.current_positions_pnl += position.pnl
        return self.current_value

    def filter_instruments(self,date,instruments_list, rf_instrument):
        self.cashflows['future_cashflows'] = self.cashflows['downpayment']\
                 + self.cashflows['emi']\
                 - self.cashflows['spend']
        t_plus_1_pv_future_cashflows = npf.npv(rf_instrument.get_return(date),
            self.cashflows[self.cashflows['date']>=date]['cash_inflows'])
        r_fall_to_low = (t_plus_1_pv_future_cashflows / self.current_value) -1
        applicable_instruments_list = []
        for instrument in instruments_list:
            if instrument.get_fall_prob(r_fall_to_low,date, lookback_years = 10) < (1-self.confidence):
                applicable_instruments_list.append(instrument)
        return applicable_instruments_list
    
    def best_instrument(self,date, instruments_list):
        best_fv = 0
        best_instrument = None
        for instrument in instruments_list:
            instrument_fv = instrument.future_exit_value(investment_amount=self.current_value,
                entry_date=date,exit_date=self.maturity_date)
            if instrument_fv >= best_fv:
                best_fv = instrument_fv
                best_instrument = instrument
        return best_instrument

    def is_wicket_down(self):
        if self.current_positions_pnl <= self.current_wicket_appetite:
            return True
        else:
            return False

    def is_steady(self):
        if self.current_value\
             / (self.maturity_value-self.each_wicket_appetite*self.wickets_fallen)\
                > self.each_wicket_safe_point*self.wickets_fallen:
                return True
        else:
            return False

    def bring_dravid(self,date,dravid):
        for position in self.positions:
            transfer_amount = position.withdraw_full(date)
            new_position = Position(instrument=dravid,date=date,investment_amount=transfer_amount)
            self.positions.append(new_position)
        self.clear_closed_positions()

    def switch_positions(self,date,best_instrument):
        for position in self.positions:
            if position.is_active:
                current_future_exit_value = position.future_exit_value(date=date,exit_date=self.maturity_date)
                best_instrument_future_exit_value = \
                    best_instrument.future_exit_value(investment_amount=position.exit_value,
                        entry_date=date,exit_date=self.maturity_date)
            if best_instrument_future_exit_value > current_future_exit_value:
                transfer_amount = position.withdraw_full(date)
                new_position = Position(instrument=best_instrument,date=date,investment_amount=transfer_amount)
                self.positions.append(new_position)
        self.clear_closed_positions()

    def clear_closed_positions(self):
        new_positions = []
        for position in self.positions:
            if position.is_active:
                new_positions.append(position)
        self.positions = new_positions
        pass

    def calibrate(self,date, instruments_list,dravid):
        self.update(date)
        if not self.is_hitting:
            self.is_steady()
        if self.is_hitting():
            if self.is_wicket_down():
                self.bring_dravid(date,dravid)
                self.is_hitting = False
            else:
                applicable_instruments_list = self.filter_instruments(date,instruments_list,dravid)
                best_instrument = self.best_instrument(date=date, instruments_list = applicable_instruments_list)
                self.switch_positions(date,best_instrument)
                

dravid = Instrument('dravid',type='debt',r_annual=.06, entry_transaction_cost=10,exit_transaction_cost=20)
cash_instrument = Instrument('cash',type='debt',r_annual=0, entry_transaction_cost=0,exit_transaction_cost=0)

data_folder_name = 'Data'
instruments_folder_name = "Instruments"


if __name__ == '__main__':
    run()


