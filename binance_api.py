import ccxt
import pandas as pd
import requests


def get_binance_client(api_key, secret_key):
    """Verilen anahtarlar ile yapılandırılmış bir CCXT Binance Futures istemcisi döndürür."""
    if not api_key or not secret_key:
        return None
    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'options': {
                'defaultType': 'future',
            },
        })
        return exchange
    except Exception as e:
        print(f"CCXT istemcisi oluşturulurken hata: {e}")
        return None

def test_api_connection(api_key, secret_key):
    """Verilen API anahtarlarının geçerliliğini test eder."""
    client = get_binance_client(api_key, secret_key)
    if client is None:
        return False, "API anahtarları ile istemci oluşturulamadı."
    try:
        client.fetch_balance()
        return True, "API bağlantısı başarılı."
    except ccxt.AuthenticationError as e:
        return False, f"Kimlik doğrulama hatası: {e}"
    except Exception as e:
        return False, f"Bir hata oluştu: {e}"

def get_futures_balance(client):
    """USDT cinsinden Futures cüzdan bakiyesini döndürür."""
    if not client:
        return None
    try:
        balance = client.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        return usdt_balance
    except Exception as e:
        print(f"Bakiye alınırken hata: {e}")
        return None

def get_historical_data(client, symbol, timeframe='1h', limit=100):
    """Belirtilen sembol için geçmiş mum verilerini CoinGecko'dan çeker."""
    # client parametresi uyumluluk için korunuyor.
    try:
        # CoinGecko için sembolü ID'ye dönüştür (örn: BTC/USDT -> bitcoin)
        coin_id = symbol.split('/')[0].lower()
        
        # CoinGecko zaman aralığı (days)
        # timeframe ve limit'e göre gün sayısını kabaca hesapla
        days = 1
        if 'h' in timeframe:
            days = (limit * int(timeframe.replace('h', ''))) // 24
        elif 'd' in timeframe:
            days = limit * int(timeframe.replace('d', ''))
        days = max(1, days) # En az 1 gün

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {'vs_currency': 'usd', 'days': days}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        # CoinGecko OHLC verisi hacim bilgisi içermez, bu yüzden 0 olarak ekliyoruz.
        df['volume'] = 0.0
        
        return df.astype(float)
    except requests.exceptions.RequestException as e:
        print(f"CoinGecko'dan geçmiş veri alınırken API hatası: {e}")
        return None
    except Exception as e:
        print(f"CoinGecko'dan geçmiş veri işlenirken hata: {e}")
        return None

def create_market_order(client, symbol, side, amount, take_profit_price=None, stop_loss_price=None):
    """Verilen sembol için bir market emri ve isteğe bağlı olarak TP/SL emirleri oluşturur."""
    if not client:
        return None, "Geçersiz istemci."
    try:
        # Ana market emrini oluştur
        order = client.create_market_order(symbol, side, amount)
        print(f"Market order created: {order}")

        # TP/SL emirlerini oluştur
        opposite_side = 'sell' if side == 'buy' else 'buy'
        
        if take_profit_price:
            try:
                tp_params = {'stopPrice': take_profit_price, 'reduceOnly': True}
                tp_order = client.create_order(symbol, 'TAKE_PROFIT_MARKET', opposite_side, amount, None, tp_params)
                print(f"Take profit order created: {tp_order}")
            except Exception as e:
                print(f"Take profit emri oluşturulurken hata: {e}")

        if stop_loss_price:
            try:
                sl_params = {'stopPrice': stop_loss_price, 'reduceOnly': True}
                sl_order = client.create_order(symbol, 'STOP_MARKET', opposite_side, amount, None, sl_params)
                print(f"Stop loss order created: {sl_order}")
            except Exception as e:
                print(f"Stop loss emri oluşturulurken hata: {e}")

        return order, "Emir başarıyla oluşturuldu."
    except Exception as e:
        return None, f"Emir oluşturulurken hata: {e}"

def get_24h_ticker():
    """Piyasa değeri en yüksek 100 coin için 24 saatlik verileri CoinGecko'dan çeker."""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 100,
            'page': 1,
            'sparkline': 'false'
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        
        # Gerekli sütunları seç ve uygulamanın beklediği formata dönüştür
        df = df[['symbol', 'price_change_percentage_24h', 'current_price', 'total_volume']]
        df.rename(columns={
            'symbol': 'Sembol',
            'price_change_percentage_24h': 'Değişim (%)',
            'current_price': 'Son Fiyat',
            'total_volume': 'Hacim (USDT)'
        }, inplace=True)
        
        # Sembolü büyük harf yap ve /USD formatına getir
        df['Sembol'] = df['Sembol'].str.upper() + '/USD'
        
        return df.dropna()
    except requests.exceptions.RequestException as e:
        print(f"CoinGecko API'sine bağlanırken hata (ticker): {e}")
        return None
    except Exception as e:
        print(f"CoinGecko'dan 24 saatlik ticker verisi işlenirken hata: {e}")
        return None

def get_position(client, symbol):
    """Belirtilen sembol için mevcut pozisyonu döndürür."""
    if not client:
        return None
    try:
        positions = client.fetch_positions([symbol])
        if positions:
            position = positions[0]
            if position.get('contracts') and position['contracts'] != 0:
                return position
        return None
    except Exception as e:
        print(f"Pozisyon bilgisi alınırken hata: {e}")
        return None

if __name__ == '__main__':
    print("Bu betik artık doğrudan çalıştırılamaz.")
    print("API anahtarları artık veritabanından, kullanıcıya özel olarak yüklenmektedir.")
