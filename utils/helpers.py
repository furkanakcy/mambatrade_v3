import os
import importlib
import inspect
from strategies.strategy_template import StrategyTemplate

def get_available_strategies():
    """
    'strategies' klasöründeki tüm strateji sınıflarını dinamik olarak bulur ve yükler.
    """
    strategies = {}
    # Betiğin bulunduğu dizine göre 'strategies' klasörünün yolunu sağlam bir şekilde belirle
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    strategy_folder_path = os.path.join(project_root, "strategies")

    if not os.path.isdir(strategy_folder_path):
        print(f"Hata: Strateji klasörü bulunamadı: {strategy_folder_path}")
        return {}

    for filename in os.listdir(strategy_folder_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            # Python'un import sistemi için modül adı 'strategies.dosya_adi' şeklinde olmalıdır.
            module_name = f"strategies.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # StrategyTemplate'den miras alan ve kendisi olmayan sınıfları bul
                    if issubclass(obj, StrategyTemplate) and obj is not StrategyTemplate:
                        strategies[name] = obj
            except ImportError as e:
                print(f"Hata: Strateji modülü yüklenemedi {module_name}. Hata: {e}")
    return strategies

if __name__ == '__main__':
    available_strategies = get_available_strategies()
    print("Kullanılabilir Stratejiler:")
    for name, class_obj in available_strategies.items():
        print(f"- {name} ({class_obj})")
