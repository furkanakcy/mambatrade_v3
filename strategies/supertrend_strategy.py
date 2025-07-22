import pandas as pd
import pandas_ta as ta
from strategies.strategy_template import StrategyTemplate

class SuperTrendStrategy(StrategyTemplate):
    """
    SuperTrend, RSI ve MACD göstergelerini birleştiren bir strateji.
    - SuperTrend yönü belirler.
    - RSI aşırı alım/satım bölgelerini teyit eder.
    - MACD momentumu onaylar.
    """
    def __init__(self, st_length=10, st_multiplier=3.0, rsi_period=14, rsi_oversold=35, rsi_overbought=65):
        self.st_length = int(st_length)
        self.st_multiplier = float(st_multiplier)
        self.rsi_period = int(rsi_period)
        self.rsi_oversold = int(rsi_oversold)
        self.rsi_overbought = int(rsi_overbought)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Verilen DataFrame üzerinde alım/satım sinyalleri üretir.
        """
        # Gerekli indikatörleri hesapla
        df.ta.supertrend(length=self.st_length, multiplier=self.st_multiplier, append=True)
        df.ta.rsi(length=self.rsi_period, append=True)
        df.ta.macd(append=True)
        df.dropna(inplace=True)

        # Sinyal sütununu başlat
        df['signal'] = 0

        # Sinyal koşullarını tanımla
        # SuperTrend yönü (SUPERTd_10_3.0), 1 ise yükseliş, -1 ise düşüş trendi
        long_condition = (
            (df[f'SUPERTd_{self.st_length}_{self.st_multiplier}'] == 1) &
            (df[f'RSI_{self.rsi_period}'] < self.rsi_overbought) &
            (df['MACD_12_26_9'] > df['MACDs_12_26_9'])
        )

        short_condition = (
            (df[f'SUPERTd_{self.st_length}_{self.st_multiplier}'] == -1) &
            (df[f'RSI_{self.rsi_period}'] > self.rsi_oversold) &
            (df['MACD_12_26_9'] < df['MACDs_12_26_9'])
        )

        # Sinyalleri ata
        # Trend değiştiğinde sinyal üret
        df.loc[(long_condition) & (df[f'SUPERTd_{self.st_length}_{self.st_multiplier}'].shift(1) == -1), 'signal'] = 1
        df.loc[(short_condition) & (df[f'SUPERTd_{self.st_length}_{self.st_multiplier}'].shift(1) == 1), 'signal'] = -1

        return df
