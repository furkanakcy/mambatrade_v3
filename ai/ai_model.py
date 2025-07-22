import google.generativeai as genai
from config import GEMINI_API_KEY
import pandas as pd

def get_ai_analysis(symbol: str, df: pd.DataFrame) -> str:
    """
    Verilen piyasa verilerini Gemini AI modelini kullanarak analiz eder.

    Args:
        symbol (str): Analiz edilecek coin sembolü.
        df (pd.DataFrame): OHLCV ve indikatörleri içeren veri.

    Returns:
        str: Yapay zeka modelinden gelen analiz metni veya hata mesajı.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "Hata: Gemini API anahtarı .env dosyasında ayarlanmamış."

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Model adını güncel ve desteklenen bir versiyonla değiştir
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Modele gönderilecek veriyi hazırla (son 20 mum)
        data_summary = df.tail(20).to_string()
        
        last_price = df['close'].iloc[-1]
        last_rsi = df['RSI_14'].iloc[-1]
        last_macd = df['MACD_12_26_9'].iloc[-1]
        last_signal = df['MACDs_12_26_9'].iloc[-1]

        prompt = f"""
        Sen bir kripto para piyasası analistisin. Aşağıdaki verileri kullanarak {symbol} için bir teknik analiz yap.

        Mevcut Durum:
        - Son Fiyat: {last_price:.2f} USDT
        - Son RSI Değeri: {last_rsi:.2f}
        - Son MACD Değeri: {last_macd:.2f}
        - Son MACD Sinyal Değeri: {last_signal:.2f}

        Son 20 mum verisi:
        {data_summary}

        Lütfen aşağıdaki başlıkları kullanarak kısa ve öz bir analiz sun:
        1.  **Trend Yönü:** (Yükseliş, Düşüş, Yatay)
        2.  **Önemli Destek Seviyeleri:** (En az 2 seviye belirt)
        3.  **Önemli Direnç Seviyeleri:** (En az 2 seviye belirt)
        4.  **Potansiyel İşlem Fırsatı:** (Mevcut verilere göre en mantıklı kısa vadeli işlem stratejisi nedir? Örneğin: 'RSI'ın 30'un altına inmesi ve MACD kesişimi ile long pozisyon düşünülebilir.' veya 'Mevcut durumda piyasa belirsiz, işlem için daha net sinyaller beklenmeli.')
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Yapay zeka analizi sırasında bir hata oluştu: {e}"

if __name__ == '__main__':
    # Bu dosyanın doğrudan test edilmesi için
    # .env dosyanıza geçerli bir GEMINI_API_KEY eklediğinizden emin olun.
    if GEMINI_API_KEY and GEMINI_API_KEY != "AIzaSyBdr_QbAAEbMe4MQ2H-MRwKbahSs5MXCp8":
        # Örnek bir dataframe oluştur
        data = {'close': [100, 102, 101], 'RSI_14': [45, 55, 65], 'MACD_12_26_9': [1, 1.2, 1.1], 'MACDs_12_26_9': [0.9, 1.1, 1.15]}
        sample_df = pd.DataFrame(data)
        analysis = get_ai_analysis("TEST/USDT", sample_df)
        print("--- Örnek AI Analizi ---")
        print(analysis)
    else:
        print("Lütfen .env dosyanıza geçerli bir GEMINI_API_KEY ekleyin.")
