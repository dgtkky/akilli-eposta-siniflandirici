"""Adım 6: n8n köprüsü (dersteki api_kopru.py gibi). Gmail'den gelen e-postayı analiz eder.

Güvenlik:
- Yalnızca 127.0.0.1'de dinler. Docker'daki n8n, http://host.docker.internal:8000 adresiyle
  ulaşır; aynı ağdaki diğer cihazlar ulaşamaz.
- /analiz için X-API-Anahtari başlığı zorunludur. Anahtar API_ANAHTARI ortam değişkeninden
  okunur; tanımlı değilse API başlamaz.
- E-posta içeriği günlüğe yazılmaz; yalnızca karar, aşama ve süre yazılır.

Çalıştır:
    export API_ANAHTARI=...          (README.md'ye bakın)
    uvicorn api:app --host 127.0.0.1 --port 8000
"""
import logging
import os
import secrets
import urllib.request
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from config import DB_DIR, OLLAMA_URL, CHAT_MODEL
from p3_analiz import analiz_et, get_store

log = logging.getLogger("uvicorn.error")
API_ANAHTARI = os.getenv("API_ANAHTARI", "")


class EpostaGirdi(BaseModel):
    gonderen: str = Field("", max_length=1_000)
    konu: str = Field("", max_length=2_000)
    metin: str = Field(..., max_length=200_000)   # aşırı büyük isteklere karşı sınır

    @field_validator("metin")
    @classmethod
    def bos_olmasin(cls, metin):
        if not metin.strip():
            raise ValueError("metin boş olamaz")
        return metin


class Isaret(BaseModel):
    isaret: str
    ifade: str


class AnalizSonucu(BaseModel):
    karar: str                      # ŞÜPHELİ / GÜVENLİ
    tur: str                        # oltalama / dolandırıcılık / spam-reklam / -
    kategori: str | None            # yalnızca GÜVENLİ e-postalarda
    kategori_gerekce: str | None
    gerekce: str
    isaretler: list[Isaret]
    asama: str                      # liste / kural / qwen / yedek
    guvenli_liste_uyarisi: bool     # güvenli listedeki adresten gelip ŞÜPHELİ çıktı mı
    sure: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(API_ANAHTARI) < 20:
        raise RuntimeError("API_ANAHTARI ortam değişkeni tanımlı değil veya çok kısa (en az 20 karakter).")
    get_store()   # Chroma bağlantısı bir kez kurulur; klasör yoksa API başlamaz
    yield


app = FastAPI(title="Oltalama E-posta Analiz API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def dogrulama_hatasi(request, hata):
    """Girdinin kendisini geri göndermez; yalnızca hangi alanın neden hatalı olduğunu söyler."""
    # Bozuk JSON'da konum alan adı değil karakter numarasıdır; o durumda "govde" yazılır
    hatalar = [{"alan": "govde" if e["type"] == "json_invalid"
                else ".".join(str(p) for p in e["loc"][1:]) or "govde", "hata": e["msg"]}
               for e in hata.errors()]
    return JSONResponse(status_code=422, content={"detail": hatalar})


def anahtar_kontrol(x_api_anahtari: str = Header(default="")):
    """X-API-Anahtari başlığını sabit sürede karşılaştırır. Gövde doğrulamasından önce çalışır."""
    if not secrets.compare_digest(x_api_anahtari.encode(), API_ANAHTARI.encode()):
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı (X-API-Anahtari başlığı).")


def ollama_acik():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as cevap:
            return cevap.status == 200
    except Exception:
        return False


@app.get("/health")
def health():
    return {"status": "ok", "service": "Oltalama E-posta Analiz API",
            "ollama": ollama_acik(), "chroma": DB_DIR.exists(), "model": CHAT_MODEL}


@app.post("/analiz", response_model=AnalizSonucu, dependencies=[Depends(anahtar_kontrol)])
def analiz(girdi: EpostaGirdi):
    try:
        s = analiz_et(girdi.gonderen, girdi.konu, girdi.metin)
    except Exception as hata:
        log.error("Analiz hatası: %s", type(hata).__name__)   # ayrıntı ve içerik yazılmaz
        raise HTTPException(status_code=503, detail="Analiz yapılamadı; Ollama çalışıyor mu?")

    kategori = s["kategori"]
    log.info("analiz: karar=%s asama=%s sure=%.1f sn", s["karar"], s["asama"], s["sure"])
    return AnalizSonucu(
        karar=s["karar"],
        tur=s["tur"],
        kategori=kategori["ad"] if kategori else None,
        kategori_gerekce=kategori["gerekce"] if kategori else None,
        gerekce=s["gerekce"],
        isaretler=s["isaretler"],
        asama=s["asama"],
        guvenli_liste_uyarisi=s["kural"]["liste"] == "guvenli" and s["karar"] == "ŞÜPHELİ",
        sure=s["sure"],
    )
