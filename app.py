import streamlit as st
import requests
import time
from auth import login_form
from database import (create_tables, add_user, has_users, get_trade_history,
                      get_user_id, save_api_keys, get_api_keys, delete_api_keys,
                      get_user_membership, set_user_membership, migrate_tables)
from binance_api import (test_api_connection, get_futures_balance, get_historical_data,
                         get_binance_client, get_position, get_24h_ticker)
from utils.helpers import get_available_strategies
from bots.bot_manager import start_new_bot, stop_bot, get_active_bot_configs, start_all_bots_from_config
from strategies.adaptive_trend_strategy import AdaptiveTrendStrategy
from ai.ai_model import get_ai_analysis
from config import GEMINI_API_KEY
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- Uygulama Başlangıç Kurulumu ---
def initialize_app():
    """Veritabanını ve varsayılan kullanıcıyı hazırlar."""
    create_tables()
    migrate_tables() # Veritabanı şemasını güncelle
    if not has_users():
        add_user("admin", "admin123")
        print("Varsayılan 'admin' kullanıcısı (şifre: 'admin123') oluşturuldu.")
    
    # Start bots on app launch if API keys are available
    if 'user_api_client' in st.session_state and st.session_state.user_api_client:
        if not st.session_state.get('bots_started'):
            start_all_bots_from_config(st.session_state.user_api_client)
            st.session_state['bots_started'] = True

initialize_app()

st.set_page_config(page_title="Binance AI Trade Bot", layout="wide")

@st.cache_resource
def get_user_api_client():
    """Mevcut kullanıcı için API anahtarlarını alır ve bir istemci nesnesi döndürür."""
    if 'username' not in st.session_state:
        return None
    user_id = get_user_id(st.session_state['username'])
    if not user_id:
        return None
    
    api_key, secret_key = get_api_keys(user_id)
    if api_key and secret_key:
        client = get_binance_client(api_key, secret_key)
        st.session_state['user_api_client'] = client
        return client
    return None

def api_management_page():
    """Kullanıcının API anahtarlarını veritabanında yönetmesi için arayüz."""
    st.header("🔐 API Anahtar Yönetimi")
    
    user_id = get_user_id(st.session_state.get('username', ''))
    if not user_id:
        st.error("Kullanıcı bulunamadı. Lütfen tekrar giriş yapın.")
        return

    api_key, secret_key = get_api_keys(user_id)

    if api_key and secret_key:
        is_connected, message = test_api_connection(api_key, secret_key)
        if is_connected:
            st.success(f"Binance Futures'a başarıyla bağlanıldı: {message}")
        else:
            st.error(f"Bağlantı hatası: {message}")
        
        if st.button("API Anahtarlarını Sil"):
            delete_api_keys(user_id)
            get_user_api_client.clear()
            st.rerun()
    else:
        st.warning("Bu kullanıcı için Binance API anahtarları ayarlanmamış. Lütfen devam etmek için girin.")

    with st.form("api_keys_form"):
        st.write("Yeni anahtar girmek veya mevcutları güncellemek için formu kullanın.")
        new_api_key = st.text_input("API Key", type="password", help="Binance API Anahtarınız")
        new_secret_key = st.text_input("Secret Key", type="password", help="Binance Secret Key'iniz")
        submitted = st.form_submit_button("Kaydet ve Bağlan")
        
        if submitted:
            if new_api_key and new_secret_key:
                save_api_keys(user_id, new_api_key, new_secret_key)
                get_user_api_client.clear()
                st.success("API anahtarları kaydedildi! Sayfa yenileniyor...")
                st.rerun()
            else:
                st.error("Lütfen hem API Key hem de Secret Key girin.")

def data_analysis_page():
    """Coin analizi ve grafiklerin gösterildiği sayfa."""
    st.header("📈 Coin Analiz ve Grafik")
    
    # API anahtarları olmadan da halka açık verilerin analiz edilebilmesi için
    # client kontrolü bu fonksiyonun başına taşındı.
    # client nesnesi, get_historical_data'ya gönderilse bile artık orada kullanılmıyor.
    client = get_user_api_client()

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Sembol (örn: BTC/USDT)", "BTC/USDT").upper()
    with col2:
        timeframe = st.selectbox("Zaman Dilimi", ['1m', '5m', '15m', '1h', '4h', '1d'], index=3)
    with col3:
        limit = st.number_input("Mum Sayısı", 50, 500, 100)

    if st.button("Verileri Getir"):
        with st.spinner(f"{symbol} verileri çekiliyor..."):
            df = get_historical_data(client, symbol, timeframe, limit)
            if df is not None and not df.empty:
                # Teknik İndikatörleri Hesapla
                df.ta.rsi(append=True)
                df.ta.macd(append=True)
                df.dropna(inplace=True)

                # İndikatör hesaplamasından sonra verinin kalıp kalmadığını kontrol et
                if df.empty:
                    st.error(f"'{symbol}' için indikatör hesaplaması sonrası yeterli veri kalmadı. Lütfen daha uzun bir zaman aralığı veya daha fazla mum sayısı deneyin.")
                    return

                # EMA'ları Hesapla
                df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
                df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
                df['EMA_100'] = df['close'].ewm(span=100, adjust=False).mean()

                # Destek ve Direnç Seviyelerini Bul (Basit Pivot Noktaları)
                support = df['low'].rolling(15, center=True).min()
                resistance = df['high'].rolling(15, center=True).max()

                # Strateji Sinyallerini Hesapla (Örnek olarak AdaptiveTrendStrategy kullanılıyor)
                # Bu kısım, al-sat sinyallerini göstermek için kalabilir.
                adaptive_strategy = AdaptiveTrendStrategy()
                df = adaptive_strategy.generate_signals(df.copy())
                
                st.success(f"{symbol} için son {len(df)} mum verisi ve analizler başarıyla hesaplandı.")
                
                # Grafik Çizimi
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.05, 
                                    row_heights=[0.8, 0.2])

                # Ana Fiyat Grafiği
                fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Fiyat'), row=1, col=1)
                
                # EMA'ları Ekle
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], name='EMA 20', line=dict(color='yellow', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], name='EMA 50', line=dict(color='orange', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_100'], name='EMA 100', line=dict(color='purple', width=1)), row=1, col=1)

                # Destek ve Direnç Seviyelerini Ekle
                fig.add_trace(go.Scatter(x=df.index, y=support, name='Destek', mode='lines', line=dict(color='rgba(0, 255, 0, 0.4)', dash='dash')), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=resistance, name='Direnç', mode='lines', line=dict(color='rgba(255, 0, 0, 0.4)', dash='dash')), row=1, col=1)

                # Al-Sat Sinyallerini Ekle
                buy_signals = df[df['signal'] == 1]
                sell_signals = df[df['signal'] == -1]
                fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['low'] * 0.98, name='Al Sinyali', mode='markers', marker_symbol='triangle-up', marker_color='green', marker_size=10), row=1, col=1)
                fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['high'] * 1.02, name='Sat Sinyali', mode='markers', marker_symbol='triangle-down', marker_color='red', marker_size=10), row=1, col=1)

                # RSI Grafiği (MACD kaldırıldı)
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name='RSI', line=dict(color='orange')), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

                fig.update_layout(title=f'{symbol} Fiyat ve İndikatör Grafiği', height=800, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
                    st.subheader("🧠 Yapay Zeka Analizi")
                    with st.spinner("Yapay zeka piyasayı analiz ediyor..."):
                        ai_response = get_ai_analysis(symbol, df)
                        st.markdown(ai_response)
                else:
                    st.info("Yapay zeka analizi özelliğini kullanmak için .env dosyanıza geçerli bir Gemini API anahtarı ekleyebilirsiniz.")
            else:
                st.error("Veri çekilemedi. Lütfen sembolü kontrol edin veya daha sonra tekrar deneyin.")

def membership_page(user_id):
    """A modern and stylish interface for the user to choose a membership plan."""
    st.title("✨ Upgrade to Premium Membership")
    st.markdown("Choose a plan to unlock the full power of trading bots.")

    # Define plans
    plans = {
        "$750": {"features": ["1 Active Bot", "Limited Data"]},
        "$1500": {"features": ["5 Active Bots", "Fast Data"]},
        "$2500": {"features": ["Unlimited Bots", "Unlimited API Access"]}
    }
    
    # Create columns
    col1, col2, col3 = st.columns(3)
    columns = [col1, col2, col3]
    
    # Store selected plan in session state
    if 'selected_plan' not in st.session_state:
        st.session_state.selected_plan = "$750" # Default

    for i, (price, details) in enumerate(plans.items()):
        with columns[i]:
            # Highlight the selected plan's card
            border_style = "border: 2px solid #007bff; border-radius: 10px; padding: 20px;" if st.session_state.selected_plan == price else "border: 1px solid #6c757d; border-radius: 10px; padding: 20px;"
            
            st.markdown(f'<div style="{border_style}">', unsafe_allow_html=True)
            st.metric(label="PLAN", value=price)
            st.markdown("---")
            for feature in details['features']:
                st.markdown(f"- {feature}")
            
            # Selection button
            if st.button(f"Select {price} Plan", key=f"select_{price}", use_container_width=True):
                st.session_state.selected_plan = price
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"Confirmation & Payment Step")
    st.info(f"Selected Plan: **{st.session_state.selected_plan}**")

    # Display wallet address
    wallet_address = "0xf392f2f06c625c679e5aafc1e5134ee4b18d0a3b"
    st.markdown("Please send exactly **" + st.session_state.selected_plan.replace('$', '') + " USDT** to the following **USDC (ERC20)** address.")
    st.code(wallet_address)
    
    agreed = st.checkbox("✅ I confirm that I have completed the payment and agree to the terms of service.")
    
    if st.button("Activate My Membership", use_container_width=True, type="primary"):
        if agreed:
            set_user_membership(user_id, st.session_state.selected_plan)
            st.success(f"Your '{st.session_state.selected_plan}' membership has been successfully activated! Redirecting to bot management...")
            st.balloons()
            time.sleep(2) # Short delay
            st.rerun()
        else:
            st.error("Please confirm that you have completed the payment and agree to the terms.")


def bot_management_page():
    """Botları yönetmek için arayüz."""
    st.header("🤖 Bot Kontrol Paneli")
    
    user_id = get_user_id(st.session_state['username'])
    if not user_id:
        st.error("Kullanıcı bulunamadı.")
        return

    # Üyelik durumunu kontrol et
    membership = get_user_membership(user_id)
    if not membership or not membership.get('onaylandi'):
        membership_page(user_id)
        return

    # Üyelik onaylandıysa normal bot yönetimi sayfasını göster
    # API anahtarları artık bot kurmak için zorunlu değil, sadece canlı botları izlemek için gerekli.
    client = get_user_api_client()
        
    st.subheader(f"Aktif Üyelik Planı: **{membership['plan']}**")
    st.markdown("---")
    
    st.subheader("Aktif Botlar")
    active_bot_configs = get_active_bot_configs()
    if not active_bot_configs:
        st.info("Şu anda çalışan bir bot yok.")
    else:
        bot_data = [{"ID": bot_id, **bot_info} for bot_id, bot_info in active_bot_configs.items()]
        st.dataframe(pd.DataFrame(bot_data))

        bot_to_stop = st.selectbox("Durdurulacak Botu Seçin", options=[""] + list(active_bot_configs.keys()))
        if st.button("Seçili Botu Durdur"):
            if bot_to_stop:
                if stop_bot(bot_to_stop):
                    st.success(f"Bot '{bot_to_stop}' başarıyla durduruldu.")
                    st.rerun()
                else:
                    st.error(f"Bot '{bot_to_stop}' durdurulamadı.")
            else:
                st.warning("Lütfen durdurulacak bir bot seçin.")

    st.subheader("Yeni Bot Kur")
    available_strategies = get_available_strategies()
    
    if not available_strategies:
        st.error("Hiçbir strateji bulunamadı. Lütfen 'strategies' klasörünü kontrol edin.")
        return

    with st.form("new_bot_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bot_symbol = st.text_input("Sembol (örn: BTC/USDT)", "BTC/USDT").upper()
            bot_strategy_name = st.selectbox("Strateji Seçin", options=list(available_strategies.keys()))
        with col2:
            bot_timeframe = st.selectbox("Zaman Dilimi", ['1m', '5m', '15m', '1h', '4h', '1d'], index=1)
            bot_trade_direction = st.selectbox("İşlem Yönü", ["Long", "Short", "Her İkisi de"])
        with col3:
            bot_leverage = st.slider("Kaldıraç", 1, 125, 10)
            bot_balance = st.number_input("Ayrılacak Bakiye (USDT)", min_value=10.0, value=100.0, step=10.0)
            take_profit = st.number_input("Kar Al (%)", min_value=0.1, value=5.0, step=0.1)
            stop_loss = st.number_input("Zarar Durdur (%)", min_value=0.1, value=2.5, step=0.1)

        submitted = st.form_submit_button("Botu Başlat")

        if submitted:
            bot_id = f"{bot_symbol.replace('/', '')}_{bot_strategy_name}_{bot_timeframe}"
            settings = {
                "leverage": bot_leverage, 
                "balance": bot_balance, 
                "direction": bot_trade_direction, 
                "timeframe": bot_timeframe,
                "take_profit": take_profit,
                "stop_loss": stop_loss
            }
            # `client` parametresi artık `start_new_bot` için gerekli değil.
            if start_new_bot(bot_id, bot_symbol, bot_strategy_name, settings, None):
                st.success(f"Bot '{bot_id}' başarıyla yapılandırıldı ve kaydedildi.")
                st.rerun()
            else:
                st.error(f"Bot '{bot_id}' yapılandırılamadı. Zaten var olabilir veya bir hata oluştu.")

def trade_history_page():
    """İşlem geçmişini gösteren sayfa."""
    st.header("📜 İşlem Geçmişi")
    history_data = get_trade_history()

    if not history_data:
        st.info("Henüz tamamlanmış bir işlem yok.")
        return

    df_history = pd.DataFrame(history_data, columns=['ID', 'Bot ID', 'Sembol', 'Yön', 'Miktar', 'Giriş Fiyatı', 'Çıkış Fiyatı', 'PNL (%)', 'Durum', 'Açılış Zamanı', 'Kapanış Zamanı'])
    
    st.subheader("Performans Özeti")
    closed_trades = df_history[df_history['Durum'] == 'closed']
    if not closed_trades.empty:
        total_pnl = closed_trades['PNL (%)'].sum()
        win_rate = (closed_trades['PNL (%)'] > 0).mean() * 100
        total_trades = len(closed_trades)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam K/Z (%)", f"{total_pnl:.2f}%")
        col2.metric("Kazanma Oranı", f"{win_rate:.2f}%")
        col3.metric("Toplam İşlem Sayısı", total_trades)
    else:
        st.write("Henüz kapanmış bir işlem bulunmuyor.")

    st.dataframe(df_history)

def dashboard_page():
    """Sadece yapılandırılmış botları gösteren dashboard sayfası."""
    st.header("📊 Dashboard")
    
    st.subheader("Yapılandırılmış Botlar")
    active_bot_configs = get_active_bot_configs()
    
    if not active_bot_configs:
        st.info("Henüz yapılandırılmış bir bot yok. 'Bot Yönetimi' sayfasından yeni bir bot kurabilirsiniz.")
    else:
        # Bot konfigürasyonlarını daha okunabilir bir DataFrame'e dönüştür
        bot_list = []
        for bot_id, config in active_bot_configs.items():
            # Ayarları düz bir sözlüğe çıkar
            flat_settings = config.get('settings', {})
            bot_info = {
                "Bot ID": bot_id,
                "Sembol": config.get('symbol'),
                "Strateji": config.get('strategy'),
                "Kaldıraç": flat_settings.get('leverage'),
                "Bakiye": flat_settings.get('balance'),
                "Yön": flat_settings.get('direction'),
                "Zaman Dilimi": flat_settings.get('timeframe'),
                "Kar Al (%)": flat_settings.get('take_profit'),
                "Zarar Durdur (%)": flat_settings.get('stop_loss')
            }
            bot_list.append(bot_info)
        
        df_bots = pd.DataFrame(bot_list)
        st.dataframe(df_bots, use_container_width=True)

# --- Start of new backtest code ---

# CoinGecko verisi çekme
def get_klines(symbol, interval, limit=1000):
    """Belirtilen sembol için geçmiş mum verilerini CoinGecko'dan çeker."""
    try:
        # CoinGecko için sembolü ID'ye dönüştür (örn: BTCUSDT -> bitcoin)
        coin_id = symbol.split('USDT')[0].lower()
        
        # CoinGecko zaman aralığı (days)
        # interval ve limit'e göre gün sayısını kabaca hesapla
        days = 1
        if 'h' in interval:
            days = (limit * int(interval.replace('h', ''))) // 24
        elif 'd' in interval:
            days = limit * int(interval.replace('d', ''))
        days = max(1, days) # En az 1 gün

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {'vs_currency': 'usd', 'days': str(days)}
        
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
        st.error(f"CoinGecko API Hatası: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Veri işlenirken hata: {e}")
        return pd.DataFrame()


# Backtest fonksiyonu
def backtest(df, leverage, initial_balance, fee, tp_percent, sl_percent):
    balance = initial_balance
    position = None
    entry_price = 0
    entry_time = None
    equity_curve = []
    trades = []

    for i in range(1, len(df)):
        signal = df["signal"].iloc[i]
        price = df["close"].iloc[i]
        time = df.index[i]

        unrealized_pnl = 0
        if position is not None:
            change = (price - entry_price) / entry_price * position
            unrealized_pnl = (initial_balance * change * leverage)
        
        equity_curve.append(balance + unrealized_pnl)

        if position is None:
            if signal != 0:
                position = signal
                entry_price = price
                entry_time = time
        else:
            change = (price - entry_price) / entry_price * position
            pnl_ratio = change * leverage

            should_close = False
            close_reason = ""
            
            if pnl_ratio >= tp_percent:
                should_close = True
                close_reason = "TP"
            elif pnl_ratio <= -sl_percent:
                should_close = True
                close_reason = "SL"
            elif signal != 0 and signal != position:
                should_close = True
                close_reason = "Reverse Signal"

            if should_close:
                pnl_after_fee = pnl_ratio - (fee * leverage * 2)
                pnl_amount = initial_balance * pnl_after_fee
                balance += pnl_amount

                trades.append({
                    "time": entry_time, "exit_time": time,
                    "entry_price": entry_price, "exit_price": price,
                    "type": "LONG" if position == 1 else "SHORT",
                    "pnl_percentage": pnl_after_fee * 100,
                    "pnl_usd": pnl_amount, "reason": close_reason
                })
                position = None

                if close_reason == "Reverse Signal":
                    position = signal
                    entry_price = price
                    entry_time = time
    
    if len(equity_curve) < len(df):
        last_val = equity_curve[-1] if equity_curve else initial_balance
        equity_curve.extend([last_val] * (len(df) - len(equity_curve)))

    df["Equity"] = equity_curve[:len(df)]
    return df, balance, trades

def backtesting_page():
    """Stratejileri geçmiş verilerle test etmek için arayüz."""
    st.header("🔬 Strateji Backtesting")

    available_strategies = get_available_strategies()
    if not available_strategies:
        st.error("Hiçbir strateji bulunamadı. Lütfen 'strategies' klasörünü kontrol edin.")
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("⚙️ Backtest Ayarları")
        symbol = st.text_input("Coin Seç (örn: BTCUSDT)", "BTCUSDT", key="bt_symbol").upper()
        interval = st.selectbox("Zaman Dilimi", ["1m","5m","15m","1h", "4h", "1d"], key="bt_interval")
        strategy_name = st.selectbox("Strateji Seçin", list(available_strategies.keys()), key="bt_strategy")
        
    with col2:
        st.subheader("💰 Ticaret Ayarları")
        leverage = st.slider("Kaldıraç", 1, 20, 5, key="bt_leverage")
        initial_balance = st.number_input("Başlangıç Bakiyesi (USDT)", value=1000.0, key="bt_balance")
        fee = st.number_input("Komisyon Oranı (örn: 0.0004)", value=0.0004, step=0.0001, format="%.4f", help="Tek yönlü komisyon oranı (örn: 0.04% için 0.0004)", key="bt_fee")
        tp = st.slider("Take Profit (%)", 0.1, 100.0, 5.0, key="bt_tp") 
        sl = st.slider("Stop Loss (%)", 0.1, 100.0, 2.0, key="bt_sl")

    if st.button("🚀 Backtest Başlat"):
        with st.spinner("Veriler çekiliyor ve backtest çalıştırılıyor..."):
            try:
                df = get_klines(symbol, interval)
                if df.empty:
                    st.warning("Veri çekilemedi. Lütfen seçiminizi kontrol edin.")
                else:
                    # Seçilen stratejiyi başlat ve sinyalleri üret
                    strategy_class = available_strategies[strategy_name]
                    strategy_instance = strategy_class() # Varsayılan ayarlarla başlat
                    df_strat = strategy_instance.generate_signals(df.copy())
                    
                    df_result, final_balance, trades = backtest(df_strat.copy(), leverage, initial_balance, fee, tp / 100.0, sl / 100.0)

                    st.subheader("📈 Bakiye Grafiği")
                    st.line_chart(df_result["Equity"])

                    st.subheader("📌 İşlem Noktaları")
                    fig = go.Figure(data=[go.Candlestick(x=df_result.index, open=df_result['open'], high=df_result['high'], low=df_result['low'], close=df_result['close'], name='Fiyat')])

                    buy_signals = df_result[df_result['signal'] == 1]
                    sell_signals = df_result[df_result['signal'] == -1]

                    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['low'] * 0.99, mode='markers', marker=dict(symbol='triangle-up', size=10, color='green'), name='AL Sinyali'))
                    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['high'] * 1.01, mode='markers', marker=dict(symbol='triangle-down', size=10, color='red'), name='SAT Sinyali'))

                    for trade in trades:
                        fig.add_trace(go.Scatter(x=[trade["time"]], y=[trade["entry_price"]], mode="markers", marker=dict(symbol='diamond', size=12, color='blue' if trade["type"] == "LONG" else 'orange'), name=f'{trade["type"]} Giriş', showlegend=False))
                        fig.add_trace(go.Scatter(x=[trade["exit_time"]], y=[trade["exit_price"]], mode="markers", marker=dict(symbol='square', size=10, color='purple'), name=f'{trade["type"]} Çıkış ({trade["reason"]})', showlegend=False))
                        fig.add_trace(go.Scatter(x=[trade["time"], trade["exit_time"]], y=[trade["entry_price"], trade["exit_price"]], mode='lines', line=dict(color='gray', dash='dot', width=1), showlegend=False))

                    fig.update_layout(title="📉 Fiyat ve İşlem Noktaları", xaxis_title="Zaman", yaxis_title="Fiyat", xaxis_rangeslider_visible=False, height=700)
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("📊 Özet")
                    total_trades = len(trades)
                    winning_trades = [t for t in trades if t["pnl_usd"] > 0]
                    
                    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
                    total_pnl = final_balance - initial_balance

                    st.metric("Toplam İşlem Sayısı", total_trades)
                    st.metric("Son Bakiye", f"{final_balance:.2f} USDT")
                    st.metric("Net Kar/Zarar", f"{total_pnl:.2f} USDT", delta=f"{total_pnl:.2f} USDT")
                    st.metric("Kazanma Oranı", f"{win_rate:.2f}%")
                    
                    if total_trades > 0:
                        st.subheader("Detaylı İşlem Kayıtları")
                        trades_df = pd.DataFrame(trades)
                        trades_df['time'] = trades_df['time'].dt.strftime('%Y-%m-%d %H:%M')
                        trades_df['exit_time'] = trades_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
                        st.dataframe(trades_df.round(4))
                    else:
                        st.info("Bu parametrelerle hiç işlem gerçekleşmedi.")

            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")
                st.warning("Lütfen girdiğiniz coin, zaman dilimi ve tarih aralığının doğru olduğundan emin olun. Binance API'si belirli limitlerde geçmiş veri sağlar.")

    st.markdown("---")
    st.info("Bu bir finansal tavsiye aracı değildir. Sadece strateji test etme amaçlıdır. Geçmiş performans, gelecekteki sonuçların garantisi değildir.")

# --- End of new backtest code ---

def display_top_movers():
    """En çok hareket eden coinleri gösteren modern bir panel oluşturur."""
    st.subheader("🚀 Günün Öne Çıkanları")
    
    # Veriyi cache'leyerek API çağrılarını azalt
    @st.cache_data(ttl=60) # 60 saniye cache'le
    def fetch_ticker_data():
        # Doğrudan halka açık API'yi çağır
        return get_24h_ticker()

    df_tickers = fetch_ticker_data()
    
    if df_tickers is not None and not df_tickers.empty:
        # En çok yükselen ve düşenleri bul
        top_gainers = df_tickers.sort_values(by='Değişim (%)', ascending=False).head(5)
        top_losers = df_tickers.sort_values(by='Değişim (%)', ascending=True).head(5)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<h5><span style='color: #28a745;'>📈 En Çok Yükselenler</span></h5>", unsafe_allow_html=True)
            for _, row in top_gainers.iterrows():
                st.metric(label=row['Sembol'], value=f"${row['Son Fiyat']:.4f}", delta=f"{row['Değişim (%)']:.2f}%")

        with col2:
            st.markdown("<h5><span style='color: #dc3545;'>📉 En Çok Düşenler</span></h5>", unsafe_allow_html=True)
            for _, row in top_losers.iterrows():
                st.metric(label=row['Sembol'], value=f"${row['Son Fiyat']:.4f}", delta=f"{row['Değişim (%)']:.2f}%")
        st.markdown("---")
    else:
        st.warning("Piyasa verileri alınamadı.")


def main_app():
    """Kullanıcı giriş yaptıktan sonra gösterilecek ana uygulama."""
    st.sidebar.title(f"Hoş Geldin, {st.session_state['username']}!")
    page = st.sidebar.radio("Sayfa Seçin",
                              ["📊 Dashboard", "📈 Coin Analiz", "🔐 API Yönetimi",
                               "🤖 Bot Yönetimi", "📜 Geçmiş İşlemler", "🔬 Backtesting"])

    st.title("🤖 Binance AI Trade Bot")
    
    # "Günün Öne Çıkanları" paneli her zaman gösterilir
    display_top_movers()

    # API istemcisini al ve uyarıyı yönet
    client = get_user_api_client()
    if not client:
        st.sidebar.warning("API anahtarları ayarlanmamış. Lütfen 'API Yönetimi' sayfasını ziyaret edin.")
    
    pages = {
        "📊 Dashboard": dashboard_page,
        "📈 Coin Analiz": data_analysis_page,
        "🔐 API Yönetimi": api_management_page,
        "🤖 Bot Yönetimi": bot_management_page,
        "📜 Geçmiş İşlemler": trade_history_page,
        "🔬 Backtesting": backtesting_page
    }
    pages[page]()

    if st.sidebar.button("Çıkış Yap"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- Ana Uygulama Akışı ---
if login_form():
    main_app()
else:
    st.info("Lütfen devam etmek için giriş yapın.")

import os
import sys
import subprocess
import threading
import time

# ... (Mevcut Streamlit kodunuz buraya kadar devam ediyor) ...

# Sadece uygulama PyInstaller ile derlenmiş ve çalıştırılıyorsa bu kısmı çalıştır
if getattr(sys, 'frozen', False):
    def run_streamlit_server():
        try:
            print("Streamlit sunucusu başlatılıyor...")
            # PyInstaller tarafından paketlenmiş Python yorumlayıcısını ve Streamlit'i kullan
            # __file__ yerine 'app.py' veya 'mambax_trader_app.py' gibi ana Streamlit dosyanızın adı
            # Eğer uygulamanız tek bir dosya ise, __file__ kullanılabilir.
            # Ancak PyInstaller'ın çıkardığı geçici dizin içinde çalışacağından,
            # Streamlit'in ana betiği olarak kendi dosya adınızı kullanmak daha güvenli olabilir.
            
            # Örneğin, ana dosyanızın adı 'app.py' ise:
            main_script_name = "app.py" 
            # Eğer başka bir isimse, onu buraya yazın:
            # main_script_name = "mambax_trader_app.py" 
            
            # Geçici PyInstaller dizini içindeki ana betik yolu
            script_path_in_temp = os.path.join(sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(__file__)), main_script_name)

            # subprocess.run([sys.executable, "-m", "streamlit", "run", script_path_in_temp], check=True)
            
            # Alternatif ve genelde daha güvenilir yol: Doğrudan kendi uygulamanızı başlatma
            # Streamlit'in arkasındaki mekanizma otomatik olarak çalışır.
            # Bu genellikle PyInstaller ile derlenmiş bir Streamlit uygulamasını başlatmak için en temiz yoldur.
            # Yani, ek bir 'streamlit run' komutuna gerek kalmaz.
            # Sadece uygulamanın kendi kodunun çalışması yeterli olur.
            
            # Eğer Streamlit uygulamanız sadece st.XXXX fonksiyonlarını kullanıyorsa,
            # ek bir 'streamlit run' komutuna ihtiyaç duymadan da çalışması gerekir.
            # Sizin önceki çıktınızdaki uyarılar (missing ScriptRunContext vb.) bunun işaretiydi.
            
            # Bu noktada, eğer tarayıcı açılmıyorsa sorun Streamlit'in kendi içinden kaynaklanıyor olabilir.
            # Yine de, Streamlit'in varsayılan portu 8501'i kontrol edebilirsiniz.
            # Eğer uygulamanız PyInstaller çıktısı çalıştıktan sonra otomatik bir tarayıcı penceresi açmıyorsa,
            # aşağıdaki manuel açma kodunu deneyebilirsiniz.
            
            # Tarayıcıyı otomatik açmak için (bu kısmı yorum satırından çıkarabilirsiniz):
            web_url = "http://localhost:8501" # Varsayılan Streamlit portu
            if sys.platform == "win32":
                os.startfile(web_url)
            elif sys.platform == "darwin": # macOS
                subprocess.Popen(['open', web_url])
            else: # Linux
                try:
                    subprocess.Popen(['xdg-open', web_url])
                except FileNotFoundError:
                    print(f"Tarayıcıyı otomatik açamadım. Lütfen şu adresi ziyaret edin: {web_url}")

        except Exception as e:
            print(f"Streamlit sunucusu başlatılırken veya tarayıcı açılırken hata oluştu: {e}")

    # Sunucuyu ayrı bir iş parçacığında başlatın ki ana program kitlenmesin
    thread = threading.Thread(target=run_streamlit_server)
    thread.daemon = True 
    thread.start()

    # Uygulamanın çalışmaya devam etmesini sağlamak için ana thread'i canlı tutun
    try:
        while True:
            time.sleep(1) # Uygulama kapanana kadar bekle
    except KeyboardInterrupt:
        print("Uygulama kapatılıyor...")
        sys.exit(0)
else:
    # Uygulama normal Python ile çalıştırıldığında bu kısım çalışmaz.
    pass
