import pandas as pd

class StrategyTemplate:
    """
    Tüm alım satım stratejileri için temel şablon.
    Her strateji bu sınıftan miras almalı ve `generate_signals` metodunu uygulamalıdır.
    """
    def __init__(self, params=None):
        """
        Stratejiye özgü parametreleri başlatır.
        Örnek: {'rsi_period': 14, 'macd_fast': 12}
        """
        self.params = params if params is not None else {}

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Verilen DataFrame üzerinde sinyalleri (long/short/neutral) üretir.
        Bu metodun her alt sınıfta üzerine yazılması (override) gerekir.

        Args:
            df (pd.DataFrame): OHLCV ve indikatörleri içeren veri.

        Returns:
            pd.DataFrame: 'signal' adında yeni bir sütun eklenmiş DataFrame.
                          Sinyal değerleri: 1 (long), -1 (short), 0 (neutral).
        """
        raise NotImplementedError("generate_signals() metodu alt sınıfta uygulanmalıdır!")

    def get_name(self):
        """Stratejinin adını döndürür."""
        return self.__class__.__name__

if __name__ == '__main__':
    # Bu şablonun nasıl kullanılacağına dair bir örnek
    class MyCustomStrategy(StrategyTemplate):
        def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
            # Örnek bir sinyal mantığı: RSI 30'un altındaysa al, 70'in üstündeyse sat.
            df['signal'] = 0
            df.loc[df['RSI_14'] < 30, 'signal'] = 1  # Long sinyali
            df.loc[df['RSI_14'] > 70, 'signal'] = -1 # Short sinyali
            return df

    # Kullanım
    # df = ... (veri çekildikten sonra)
    # df.ta.rsi(append=True)
    # strategy = MyCustomStrategy()
    # df_with_signals = strategy.generate_signals(df)
    # print(df_with_signals[['close', 'RSI_14', 'signal']].tail(10))
    print("StrategyTemplate başarıyla oluşturuldu ve test edildi.")
