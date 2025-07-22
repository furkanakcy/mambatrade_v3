import json
import threading
import time
from datetime import datetime, timedelta
import importlib

from binance_api import get_historical_data, create_market_order, get_position
from database import log_trade, update_trade
from utils.helpers import get_available_strategies

BOT_STATE_FILE = "bot_state.json"
_running_bot_threads = {}

class Bot(threading.Thread):
    def __init__(self, bot_id, symbol, strategy_instance, settings, client):
        super().__init__()
        self.bot_id = bot_id
        self.symbol = symbol
        self.strategy = strategy_instance
        self.settings = settings
        self.client = client
        self.is_running = True
        self.active_trade_id = None
        self.daemon = True

    def run(self):
        """Bot's main execution loop."""
        print(f"Bot {self.bot_id} started for hourly checks.")
        timeframe = self.settings.get('timeframe', '1m')

        while self.is_running:
            try:
                now = datetime.utcnow()
                next_run_time = (now + timedelta(hours=1)).replace(minute=0, second=2, microsecond=0)
                sleep_duration = (next_run_time - now).total_seconds()
                
                if sleep_duration > 0:
                    print(f"[{self.bot_id}] Next check at {next_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}. Waiting for {sleep_duration:.0f} seconds.")
                    for _ in range(int(sleep_duration)):
                        if not self.is_running: break
                        time.sleep(1)
                    if not self.is_running: break
            except Exception as e:
                print(f"[{self.bot_id}] Error in sleep logic: {e}. Falling back to 1 hour sleep.")
                time.sleep(3600)
                continue

            if not self.is_running: break

            try:
                df = get_historical_data(self.client, self.symbol, timeframe=timeframe, limit=100)
                if df is None:
                    print(f"[{self.bot_id}] Could not fetch data, skipping cycle.")
                    continue

                df_with_signals = self.strategy.generate_signals(df)
                last_signal = df_with_signals['signal'].iloc[-1]
                position = get_position(self.client, self.symbol)
                
                print(f"[{self.bot_id}] Last signal: {last_signal}, Position: {'Yes' if position else 'No'}")

                if last_signal == 1 and position is None:
                    entry_price = df['close'].iloc[-1]
                    amount = self.settings['balance'] / entry_price
                    tp = self.settings.get('take_profit')
                    sl = self.settings.get('stop_loss')
                    tp_price = entry_price * (1 + tp / 100) if tp else None
                    sl_price = entry_price * (1 - sl / 100) if sl else None
                    order, msg = create_market_order(self.client, self.symbol, 'buy', round(amount, 3), tp_price, sl_price)
                    if order:
                        self.active_trade_id = log_trade(self.bot_id, self.symbol, 'long', amount, entry_price)

                elif last_signal == -1 and position is None:
                    entry_price = df['close'].iloc[-1]
                    amount = self.settings['balance'] / entry_price
                    tp = self.settings.get('take_profit')
                    sl = self.settings.get('stop_loss')
                    tp_price = entry_price * (1 - tp / 100) if tp else None
                    sl_price = entry_price * (1 + sl / 100) if sl else None
                    order, msg = create_market_order(self.client, self.symbol, 'sell', round(amount, 3), tp_price, sl_price)
                    if order:
                        self.active_trade_id = log_trade(self.bot_id, self.symbol, 'short', amount, entry_price)
                
                elif position is not None and self.active_trade_id is not None:
                    pos_side = 'long' if float(position['contracts']) > 0 else 'short'
                    if (pos_side == 'long' and last_signal == -1) or (pos_side == 'short' and last_signal == 1):
                        close_side = 'sell' if pos_side == 'long' else 'buy'
                        amount = abs(float(position['contracts']))
                        order, msg = create_market_order(self.client, self.symbol, close_side, amount)
                        if order:
                            exit_price = df['close'].iloc[-1]
                            entry_price = float(position['entryPrice'])
                            pnl = ((exit_price - entry_price) / entry_price) * 100 * self.settings['leverage']
                            if pos_side == 'short': pnl = -pnl
                            update_trade(self.active_trade_id, exit_price, pnl)
                            self.active_trade_id = None
            except Exception as e:
                print(f"[{self.bot_id}] Error in bot loop: {e}")

    def stop(self):
        self.is_running = False
        print(f"Bot {self.bot_id} stopping...")

def _load_bot_state():
    try:
        with open(BOT_STATE_FILE, "r") as f: return json.load(f)
    except FileNotFoundError: return {}

def _save_bot_state(state):
    with open(BOT_STATE_FILE, "w") as f: json.dump(state, f, indent=4)

def start_new_bot(bot_id, symbol, strategy_name, settings, client):
    """Sadece bot konfigürasyonunu veritabanına (JSON dosyası) kaydeder, botu başlatmaz."""
    configs = _load_bot_state()
    if bot_id in configs:
        print(f"Bot '{bot_id}' zaten yapılandırılmış.")
        return False
    
    # Stratejinin var olup olmadığını kontrol et, ancak başlatma
    available_strategies = get_available_strategies()
    if strategy_name not in available_strategies:
        print(f"Strateji '{strategy_name}' bulunamadı.")
        return False

    # Botu başlatmak yerine sadece konfigürasyonu kaydet
    # client parametresi artık bu aşamada gerekli değil.
    configs[bot_id] = {"symbol": symbol, "strategy": strategy_name, "settings": settings}
    _save_bot_state(configs)
    print(f"Bot '{bot_id}' başarıyla yapılandırıldı ve veritabanına kaydedildi. (Başlatılmadı)")
    return True

def stop_bot(bot_id):
    configs = _load_bot_state()
    if bot_id in _running_bot_threads:
        _running_bot_threads[bot_id].stop()
        _running_bot_threads[bot_id].join()
        del _running_bot_threads[bot_id]
    
    if bot_id in configs:
        del configs[bot_id]
        _save_bot_state(configs)
        print(f"Bot '{bot_id}' stopped and configuration removed.")
        return True
    return False

def get_active_bot_configs():
    return _load_bot_state()

def start_all_bots_from_config(client):
    """Load all bot configs from file and start them."""
    print("Starting all configured bots...")
    configs = _load_bot_state()
    for bot_id, config in configs.items():
        if bot_id not in _running_bot_threads:
            available_strategies = get_available_strategies()
            strategy_class = available_strategies.get(config['strategy'])
            if strategy_class:
                bot_thread = Bot(bot_id, config['symbol'], strategy_class(), config['settings'], client)
                bot_thread.start()
                _running_bot_threads[bot_id] = bot_thread
                print(f"Bot '{bot_id}' started from config.")
            else:
                print(f"Strategy '{config['strategy']}' for bot '{bot_id}' not found.")
