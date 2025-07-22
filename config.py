import os
from dotenv import load_dotenv

# .env dosyasının yolunu projenin kök dizinine göre ayarla
# Bu betiğin bulunduğu dizinden bir üst dizine çıkarak .env'yi buluruz.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

# .env dosyasını yükle
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print(f"Uyarı: .env dosyası bulunamadı: {dotenv_path}")
    print("Lütfen .env.example dosyasını kopyalayıp .env olarak adlandırın ve API anahtarlarınızı girin.")


# Gemini API Anahtarı (Opsiyonel)
# Bu anahtar, belirli bir kullanıcıya bağlı olmadığı için burada kalabilir.
GEMINI_API_KEY = "AIzaSyBdr_QbAAEbMe4MQ2H-MRwKbahSs5MXCp8"
