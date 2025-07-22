import pandas as pd
from .strategy_template import StrategyTemplate

class AdaptiveTrendStrategy(StrategyTemplate):
    """
    Adaptive Trend Flow indikatörünü kullanan bir strateji.
    Fiyat, trend seviyesini yukarı kırdığında long, aşağı kırdığında short sinyali üretir.
    """
    def __init__(self, length: int = 21, smooth_len: int = 14, sensitivity: float = 1.0):
        self.params = {
            'length': length,
            'smooth_len': smooth_len,
            'sensitivity': sensitivity
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adaptive Trend Flow'a göre sinyal üretir."""
        
        # Parametreler (ileride arayüzden ayarlanabilir)
        length = self.params.get('length', 21)
        smooth_len = self.params.get('smooth_len', 14)
        sensitivity = self.params.get('sensitivity', 1.0)

        # İndikatör hesaplaması
        typical = (df["high"] + df["low"] + df["close"]) / 3
        fast = typical.ewm(span=length, adjust=False).mean()
        slow = typical.ewm(span=length * 2, adjust=False).mean()
        basis = (fast + slow) / 2
        vol = typical.rolling(length).std()
        smooth_vol = vol.ewm(span=smooth_len, adjust=False).mean()
        upper = basis + smooth_vol * sensitivity
        lower = basis - smooth_vol * sensitivity
        
        trends = []
        for i in range(len(df)):
            price = df["close"].iat[i]
            b, u, l = basis.iat[i], upper.iat[i], lower.iat[i]
            if i == 0:
                trend = 1 if price > b else -1
            else:
                prev = trends[-1]
                trend = -1 if prev == 1 and price < l else 1 if prev == -1 and price > u else prev
            trends.append(trend)
        
        df["trend"] = trends
        df["upper_band"] = upper
        df["lower_band"] = lower
        df["basis_line"] = basis
        
        # Sinyalleri oluştur
        df['signal'] = 0
        long_signal = (df["trend"] == 1) & (df["trend"].shift(1) == -1)
        short_signal = (df["trend"] == -1) & (df["trend"].shift(1) == 1)
        
        df.loc[long_signal, 'signal'] = 1
        df.loc[short_signal, 'signal'] = -1

        return df
