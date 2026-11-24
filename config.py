"""Tek merkezden kullanılan ayarlar. Model adını veya örnek sayısını buradan değiştirin."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent

# Veri dosyaları (Kaggle'daki 6 orijinal CSV; phishing_email.csv kullanılmaz)
VERI_DOSYALARI = ["CEAS_08", "SpamAssasin", "Nazario", "Nigerian_Fraud", "Enron", "Ling"]
GONDERENSIZ = ["Enron", "Ling"]   # bu dosyalarda gönderen sütunu yok
TRAIN_CSV = ROOT / "train.csv"
TEST_CSV = ROOT / "test.csv"

# ChromaDB
DB_DIR = ROOT / "chroma_eposta"
COLLECTION = "eposta_ornekleri_v1"

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:7b")
# Modeller son kullanımdan sonra 1 saat bellekte kalır (Ollama varsayılanı 5 dk);
# böylece seyrek gelen e-postalarda model her seferinde yeniden yüklenmez.
KEEP_ALIVE = 3600   # saniye
# Qwen cevabının üst sınırı (token). Ölçülen en uzun cevaplar: karar 199, konu 46.
# Sınır yalnızca sonu gelmeyen cevaplara karşı korumadır; kesilirse çağrı 2 kat sınırla tekrarlanır.
NUM_PREDICT_KARAR = 512
NUM_PREDICT_KONU = 256

# Proje ayarları
ORNEK_SAYISI = 2000     # her sınıftan (şüpheli / güvenli) kaç e-posta alınacak
TEST_ORANI = 0.2        # %80 train / %20 test
RASTGELE = 42           # her çalıştırmada aynı örnekler seçilsin
MAX_KARAKTER = 1500     # uzun e-postalar bu uzunlukta kırpılır
NOTR_ALAN = "example.com"   # Nazario'daki monkey.org geçişleri bu adla değiştirilir
ETIKET_ADI = {1: "ŞÜPHELİ", 0: "GÜVENLİ"}

# Gönderen listeleri ve marka taklidi kontrolü (p3_kurallar.py)
ENGELLI_LISTE = ROOT / "engelli_gonderenler.txt"
GUVENLI_LISTE = ROOT / "guvenli_gonderenler.txt"
MARKALAR_DOSYASI = ROOT / "bilinen_markalar.txt"
BENZERLIK_ESIGI = 0.8   # difflib benzerliği bu değer ve üstündeyse "benzer yazım" sayılır
# Herkesin adres alabildiği ücretsiz e-posta servisleri
UCRETSIZ_SERVISLER = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.tr", "outlook.com",
    "outlook.com.tr", "live.com", "msn.com", "yahoo.com", "yahoo.com.tr", "yandex.com",
    "yandex.com.tr", "yandex.ru", "mail.ru", "icloud.com", "aol.com", "gmx.com",
    "gmx.net", "proton.me", "protonmail.com", "zoho.com",
}
# Kurumsal görünen gönderen adları (Türkçe karaktersiz, küçük harf; tam kelime olarak aranır).
# Ücretsiz bir servisten bu adlarla gelen e-posta yalnızca ipucu olarak işaretlenir.
KURUMSAL_ADLAR = [
    "update", "account", "security", "support", "service", "admin", "administrator",
    "helpdesk", "help desk", "team", "billing", "verification", "notification", "customer",
    "webmaster", "postmaster", "mailbox", "it department",
    "destek", "guvenlik", "hesap", "musteri hizmetleri", "bilgi islem", "yonetici",
    "dogrulama", "bildirim",
]
# Oltalamada sık görülen ucuz alan adı uzantıları (yalnızca ipucu)
SUPHELI_UZANTILAR = {"xyz", "top", "click", "online", "site", "icu", "buzz", "loan",
                     "win", "bid", "club", "work", "tk", "ml", "ga", "cf", "gq"}
