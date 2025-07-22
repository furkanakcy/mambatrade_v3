import pandas as pd
import pandas_ta as ta
from .strategy_template import StrategyTemplate

class RsiMacdStrategy(StrategyTemplate):
    """
    RSI ve MACD indikatörlerini birleştiren bir alım satım stratejisi.
    """
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        RSI ve MACD'ye dayalı olarak long/short sinyalleri üretir.

        Sinyal Mantığı:
        - Long: RSI < 30 ve MACD, sinyal çizgisini yukarı keser.
        - Short: RSI > 70 ve MACD, sinyal çizgisini aşağı keser.
        """
        # Gerekli indikatörleri hesapla (eğer yoksa)
        if 'RSI_14' not in df.columns:
            df.ta.rsi(append=True)
        if 'MACD_12_26_9' not in df.columns:
            df.ta.macd(append=True)
        
        df.dropna(inplace=True)
        df['signal'] = 0

        # MACD kesişimlerini bul
        # Önceki adımdaki MACD ve sinyal değerlerini bir sonraki satıra taşı
        df['prev_macd'] = df['MACD_12_26_9'].shift(1)
        df['prev_signal_line'] = df['MACDs_12_26_9'].shift(1)

        # Long sinyali koşulları
        long_condition = (
            (df['RSI_14'] < 40) &  # RSI aşırı satım bölgesine yakın (daha esnek)
            (df['prev_macd'] < df['prev_signal_line']) &  # Önceki adımda MACD sinyalin altındaydı
            (df['MACD_12_26_9'] > df['MACDs_12_26_9'])    # Mevcut adımda MACD sinyalin üstüne çıktı (yukarı kesişim)
        )

        # Short sinyali koşulları
        short_condition = (
            (df['RSI_14'] > 60) &  # RSI aşırı alım bölgesine yakın (daha esnek)
            (df['prev_macd'] > df['prev_signal_line']) &  # Önceki adımda MACD sinyalin üstündeydi
            (df['MACD_12_26_9'] < df['MACDs_12_26_9'])    # Mevcut adımda MACD sinyalin altına indi (aşağı kesişim)
        )

        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        
        # Yardımcı sütunları temizle
        df.drop(columns=['prev_macd', 'prev_signal_line'], inplace=True)

        return df

if __name__ == '__main__':
    # Test için örnek bir DataFrame oluşturalım
    data = {
        'open': [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 108, 107, 105, 103, 101],
        'high': [103, 104, 103, 105, 106, 106, 108, 110, 109, 111, 110, 109, 107, 105, 103],
        'low': [99, 101, 100, 102, 104, 103, 105, 107, 106, 108, 107, 106, 104, 102, 100],
        'close': [102, 101, 103, 105, 104, 106, 108, 107, 109, 108, 107, 105, 103, 101, 102],
        'volume': [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 18, 17, 15, 13, 11]
    }
    df = pd.DataFrame(data)
    
    strategy = RsiMacdStrategy()
    df_with_signals = strategy.generate_signals(df.copy())
    
    print("RSI & MACD Stratejisi Testi:")
    print(df_with_signals[['close', 'RSI_14', 'MACD_12_26_9', 'MACDs_12_26_9', 'signal']].to_string())
    print("\nSinyal üretilen satırlar:")
    print(df_with_signals[df_with_signals['signal'] != 0].to_string())
