"""Adım 3 (modelsiz kısım): gönderen listeleri, gönderen kuralları ve marka taklidi kontrolü.

Bu dosya LangChain veya Ollama kullanmaz; model çalışmadan test edilebilir:
    python p3_kurallar.py                    # örnek adreslerle tablo
    python -m unittest -v test_kurallar.py   # testler
"""
import re
from difflib import SequenceMatcher
from email.utils import parseaddr
from config import (ENGELLI_LISTE, GUVENLI_LISTE, MARKALAR_DOSYASI, BENZERLIK_ESIGI,
                    UCRETSIZ_SERVISLER, SUPHELI_UZANTILAR, KURUMSAL_ADLAR)

# Kararlar
SUPHELI = "ŞÜPHELİ"            # kesin: engelli liste veya marka taklidi
GUVENLI_GONDEREN = "GÜVENLİ LİSTE"  # yalnızca gönderen adresi kuralları atlanır; içerik yine incelenir
QWEN = "QWEN'E"                # kesin karar yok; bulgular Qwen'e ipucu olarak verilir

# İki parçalı uzantılar: bu durumda asıl alan adı son ÜÇ parçadır (garantibbva.com.tr)
IKI_PARCALI = {"com.tr", "gov.tr", "org.tr", "net.tr", "edu.tr", "k12.tr", "bel.tr",
               "gen.tr", "biz.tr", "web.tr", "co.uk", "org.uk", "ac.uk", "com.au", "com.br"}

KISA_MARKA = 4   # bu uzunlukta veya daha kısa marka adları yalnızca tam parça olarak aranır
TURKCE = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


# ---------- Dosya okuma ----------

def satirlari_oku(dosya):
    """Boş satırları ve # ile başlayan yorumları atlayarak satırları küçük harfle döndürür."""
    if not dosya.exists():
        return []
    satirlar = [s.strip().lower() for s in dosya.read_text(encoding="utf-8").splitlines()]
    return [s for s in satirlar if s and not s.startswith("#")]

def markalari_oku():
    """'binance: binance.com' satırlarını {"binance": ["binance.com"]} sözlüğüne çevirir."""
    markalar = {}
    for satir in satirlari_oku(MARKALAR_DOSYASI):
        marka, alanlar = satir.split(":", 1)
        markalar[marka.strip()] = [a.strip() for a in alanlar.split(",") if a.strip()]
    return markalar


# ---------- Yardımcılar ----------

def asil_alan(alan):
    """binance.com.hesap-dogrula.xyz -> hesap-dogrula.xyz  |  bilgi.garantibbva.com.tr -> garantibbva.com.tr"""
    parcalar = alan.split(".")
    if len(parcalar) >= 3 and ".".join(parcalar[-2:]) in IKI_PARCALI:
        return ".".join(parcalar[-3:])
    return ".".join(parcalar[-2:])

def ad_kismi(alan):
    """Uzantısız ad: binanse.com -> binanse  |  garantibbva.com.tr -> garantibbva"""
    return asil_alan(alan).split(".")[0]

def marka_geciyor_mu(metin, marka):
    """Uzun marka adları metnin içinde aranır; kısa olanlar (ptt, ups) yalnızca tam parça olarak.
    Böylece 'groups.com' içinde 'ups' bulunmaz."""
    if len(marka) > KISA_MARKA:
        return marka in metin
    return marka in re.split(r"[^a-z]+", metin)

def benzer_karakter_halleri(ad):
    """Benzer karakterler düzeltilince ortaya çıkabilecek halleri döndürür (1->i/l, 0->o, rn->m)."""
    temel = ad.replace("rn", "m").replace("0", "o")
    haller = {temel.replace("1", "i"), temel.replace("1", "l")}
    haller.discard(ad)          # hiçbir şey değişmediyse benzer karakter hilesi yoktur
    return haller

def listede_mi(adres, alan, liste):
    for kayit in liste:
        if kayit.startswith("@"):
            kayit_alan = kayit[1:]
            if alan == kayit_alan or alan.endswith("." + kayit_alan):
                return True
        elif adres == kayit:
            return True
    return False


# ---------- Marka taklidi (alan adına göre) ----------

def marka_taklidi(alan, markalar=None):
    """Alan adı bir markayı taklit ediyorsa {"marka", "gercek", "tur"} döndürür, etmiyorsa None.
    Kontrol sırası: (a) marka adı içeriyor, (c) benzer karakter, (d) alt alan adı, (b) benzer yazım."""
    markalar = markalar or markalari_oku()
    asil = asil_alan(alan)
    tum_gercekler = {g for gercekler in markalar.values() for g in gercekler}
    if asil in tum_gercekler or asil in UCRETSIZ_SERVISLER:
        return None

    ad = ad_kismi(asil)
    alt = alan[: -len(asil)].rstrip(".")    # asıl alan adından önceki kısım
    haller = benzer_karakter_halleri(ad)

    def sonuc(marka, tur):
        return {"marka": marka, "gercek": markalar[marka][0], "tur": tur}

    for marka in markalar:                                   # (a)
        if marka_geciyor_mu(ad, marka):
            return sonuc(marka, "marka adı eklenmiş alan adı")
    for marka, gercekler in markalar.items():                # (c)
        gercek_adlar = {ad_kismi(g) for g in gercekler}
        if any(h in gercek_adlar or marka_geciyor_mu(h, marka) for h in haller):
            return sonuc(marka, "benzer karakter hilesi")
    for marka, gercekler in markalar.items():                # (d)
        if alt and (marka_geciyor_mu(alt, marka) or any(g in alt for g in gercekler)):
            return sonuc(marka, "alt alan adı hilesi")
    for marka, gercekler in markalar.items():                # (b)
        for g in gercekler:
            if len(ad) > KISA_MARKA and SequenceMatcher(None, ad, ad_kismi(g)).ratio() >= BENZERLIK_ESIGI:
                return sonuc(marka, "benzer yazım")
    return None


# ---------- Gönderen kuralları ----------

def gorunen_ad_markasi(gorunen_ad, markalar):
    """Görünen adda geçen markayı döndürür: 'Garanti BBVA' -> 'garanti'."""
    sade = gorunen_ad.translate(TURKCE).lower()
    bitisik = re.sub(r"[^a-z0-9]", "", sade)          # "e-Devlet Kapısı" -> "edevletkapisi"
    kelimeler = re.split(r"[^a-z0-9]+", sade)
    for marka in markalar:
        if (len(marka) > KISA_MARKA and marka in bitisik) or marka in kelimeler:
            return marka
    return None

def kurumsal_ad(gorunen_ad):
    """Görünen ad kurumsal görünüyorsa eşleşen kelimeyi döndürür: 'Update Account' -> 'update'."""
    sade = " ".join(re.split(r"[^a-z0-9]+", gorunen_ad.translate(TURKCE).lower()))
    for kelime in KURUMSAL_ADLAR:
        if re.search(rf"\b{kelime}\b", sade):
            return kelime
    return None

def garip_alan_bulgulari(alan):
    bulgular = []
    if re.fullmatch(r"\[?\d{1,3}(\.\d{1,3}){3}\]?", alan):
        bulgular.append(f"Gönderen alan adı yerine IP adresi kullanılmış ({alan}).")
    if "xn--" in alan:
        bulgular.append(f"Alan adında punycode var; harfler başka alfabeden olabilir ({alan}).")
    uzanti = alan.rsplit(".", 1)[-1]
    if uzanti in SUPHELI_UZANTILAR:
        bulgular.append(f"Alan adı oltalamada sık görülen '.{uzanti}' uzantısını kullanıyor.")
    ad = ad_kismi(alan)
    if ad.count("-") >= 2 or sum(k.isdigit() for k in ad) >= 3:
        bulgular.append(f"Alan adında çok sayıda tire veya rakam var ({asil_alan(alan)}).")
    return bulgular


# ---------- Talimat enjeksiyonu (konu + metin) ----------

# Metin önce Türkçe karaktersiz küçük harfe çevrilir, sonra bu desenle aranır.
ENJEKSIYON_DESENI = re.compile(
    # Cevap biçimimizi taklit eden satırlar: "KARAR: GÜVENLİ", "verdict: safe"
    r"(karar|verdict|classification)\s*:\s*\**\s*(guvenli|supheli|safe|legit|not spam|ham)\b"
    # Türkçe: talimatları unutturma, güvenli işaretletme
    r"|onceki (tum )?talimat|talimatlari (unut|yok say)|sistem talimati"
    r"|guvenli (olarak |diye )?isaretle"
    # İngilizce: ignore previous instructions, mark as safe
    r"|(ignore|disregard|forget) (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?)"
    r"|system prompt|you are now (a|an) "
    r"|(mark|flag|classify|label) (this |it |the )?(email |message |mail )?as (safe|legitimate|not phishing)\b"
)

def sadelestir(yazi):
    """Türkçe karakterleri sadeleştirir ve küçük harfe çevirir: 'ŞİFRENİZİ' -> 'sifrenizi'.
    Karakter karakter çalışır, uzunluk değişmez; böylece sadeleştirilmiş metinde bulunan
    yerin konumu orijinal metinde de aynıdır ve ifade orijinal yazımıyla alınabilir."""
    return "".join((k.translate(TURKCE).lower() or k)[0] for k in yazi)

def birlestir(konu, metin):
    return f"{'' if konu is None else konu}\n{'' if metin is None else metin}"

def talimat_enjeksiyonu(konu, metin):
    """Konu veya metinde güvenlik sistemine talimat verme girişimi varsa bulunan ifadeyi
    (orijinal yazımıyla), yoksa None döndürür."""
    yazi = birlestir(konu, metin)
    bulunan = ENJEKSIYON_DESENI.search(sadelestir(yazi))
    return yazi[bulunan.start():bulunan.end()] if bulunan else None


# ---------- İçerik işaretleri (konu + metin) ----------
# Bunlar anahtar kelime eşleşmesidir; "istiyor" olup olmadığını anlamaz
# ("Şifrenizi kimseyle paylaşmayın" da şifre ifadesi sayılır). Karar vermez, Qwen'e ipucu olur.
# Desenler sadeleştirilmiş (Türkçe karaktersiz, küçük harf) metinde aranır.

ICERIK_DESENLERI = [
    ("şifre/kimlik ifadesi", re.compile(
        r"\bsifre\w*|\bparola\w*|\bt\.?c\.? kimlik\w*|\bkimlik (no|numara)\w*|\bgiris bilgi\w*"
        r"|\b(hesabinizi|kimliginizi|bilgilerinizi) dogrula\w*"
        r"|\bpassword\w*|\bpasscode\b|\busername\b|\blogin (details|credentials|information)\b"
        r"|\b(verify|confirm|validate|update) your (account|identity|login|password|details|information)\b"
        r"|\bsocial security\b|\bssn\b")),
    ("kart/ödeme ifadesi", re.compile(
        r"\bkart (numara|bilgi)\w*|\bkredi kart\w*|\bcvv\b|\bcvc\b|\bson kullanma tarih\w*"
        r"|\bodeme\w*|\biban\b|\bhavale\w*|\beft\b|\bbanka hesab\w*|\bhesap numara\w*"
        r"|\bcredit card\w*|\bcard (number|details|information)\b|\bexpiration date\b|\bpayments?\b"
        r"|\bbilling (information|details|address)\b|\bbank (account|details)\b|\baccount number\b"
        r"|\bwire transfer\b|\brouting number\b")),
    ("aciliyet/tehdit ifadesi", re.compile(
        r"\b\d+ (saat|gun) icinde\b|\bhemen\b|\bacil\w*|\bson uyari\w*"
        r"|\bhesabiniz\w* (kapatil|askiya|kilitlen|bloke|dondurul|iptal)\w*"
        r"|\burgent\w*|\bimmediately\b|\bwithin \d+ (hours|days)\b|\bsuspend(ed|ion)?\b|\blocked\b"
        r"|\bdeactivat\w*|\bunusual activity\b|\bunauthori[sz]ed\b|\bfinal notice\b|\bact now\b")),
    ("para/ödül ifadesi", re.compile(
        r"\bkazandin\w*|\bodul\w*|\bmiras\w*|\bpiyango\w*|\bcekilis\w*"
        r"|\bmilyon (dolar|euro|avro|tl|sterlin)\w*"
        r"|\byou (have )?won\b|\bwinner\w*|\blottery\b|\binheritance\b|\bbeneficiar\w*|\bprize\w*"
        r"|\bclaim your\b|\bmillion (us )?(dollars|usd|pounds|euros)\b|\$ ?\d{1,3}(,\d{3}){2,}")),
    ("bağlantı", re.compile(r"(https?://|www\.)[^\s<>\"')\]]+")),
    ("IP adresine giden bağlantı", re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}[^\s<>\"')\]]*")),
]

BAGLANTI_HOST = re.compile(r"(?:https?://|\bwww\.)([a-z0-9.-]+)", re.IGNORECASE)
IP = re.compile(r"\d{1,3}(\.\d{1,3}){3}")

def iddia_edilen_markalar(gonderen, markalar):
    """E-postanın hangi markadan geliyormuş gibi göründüğü: gönderen alan adı (gerçek marka alanı
    veya taklidi) ve görünen ad. Konu ve metindeki marka adları SAYILMAZ: posta listelerinde
    "Google", "Apple" gibi adlar çok geçiyor ve train setinde güvenli e-postalarda yanlış işaret üretti."""
    gorunen_ad, adres = parseaddr(str(gonderen))
    alan = adres.lower().rsplit("@", 1)[1] if "@" in adres else ""
    bulunan = []
    if alan:
        bulunan += [m for m, alanlar in markalar.items() if asil_alan(alan) in alanlar]
        taklit = marka_taklidi(alan, markalar)
        if taklit:
            bulunan.append(taklit["marka"])
    bulunan.append(gorunen_ad_markasi(gorunen_ad, markalar))
    return list(dict.fromkeys(m for m in bulunan if m))   # sırayı koruyarak tekrarları at

def baglanti_uyusmazligi(gonderen, konu, metin, markalar=None):
    """Bağlantılarda marka uyuşmazlığı arar. İki durumda işaret döndürür:
    a) Gönderen bir markadan geliyormuş gibi görünüyor (alan adı veya görünen ad) ama bir bağlantı
       ne o markanın ne de başka bir bilinen markanın gerçek alan adına gidiyor (IP bağlantısı dahil).
    b) Bağlantının kendisi bir markayı taklit ediyor: yurtici-teslimat.top, paypa1.com,
       yurticikargo.com.odeme.xyz (alt alan adı hilesi) — gönderen kim olursa olsun."""
    markalar = markalar or markalari_oku()
    hostlar = [h.strip(".").lower() for h in BAGLANTI_HOST.findall(birlestir(konu, metin))]
    hostlar = [h for h in hostlar if "." in h]
    if not hostlar:
        return None
    iddia = iddia_edilen_markalar(gonderen, markalar)
    tum_gercek = {a for alanlar in markalar.values() for a in alanlar}
    for host in hostlar:
        if IP.fullmatch(host):
            if iddia:
                marka = iddia[0]
                return {"isaret": "bağlantı uyuşmazlığı",
                        "ifade": f"{host} ({marka} markasının alan adı: {', '.join(markalar[marka])})"}
            continue
        if iddia and asil_alan(host) not in tum_gercek:
            marka = iddia[0]
            return {"isaret": "bağlantı uyuşmazlığı",
                    "ifade": f"{host} ({marka} markasının alan adı: {', '.join(markalar[marka])})"}
        taklit = marka_taklidi(host, markalar)
        if taklit:
            return {"isaret": "bağlantı uyuşmazlığı",
                    "ifade": f"{host} ({taklit['marka']} markasını taklit ediyor; gerçek alan adı: {taklit['gercek']})"}
    return None

def icerik_isaretleri(konu, metin, gonderen=""):
    """E-postada gerçekten bulunan işaretleri, bulunan ifadeyle (orijinal yazımıyla) döndürür:
    [{"isaret": "aciliyet/tehdit ifadesi", "ifade": "24 saat içinde"}, ...]
    Her işaret türünden ilk bulunan ifade alınır. Gönderen verilirse bağlantı uyuşmazlığına da bakılır."""
    yazi = birlestir(konu, metin)
    sade = sadelestir(yazi)
    bulunanlar = []
    for isaret, desen in ICERIK_DESENLERI:
        eslesme = desen.search(sade)
        if eslesme:
            bulunanlar.append({"isaret": isaret, "ifade": yazi[eslesme.start():eslesme.end()][:80]})
    uyusmazlik = baglanti_uyusmazligi(gonderen, konu, metin)
    if uyusmazlik:
        bulunanlar.append(uyusmazlik)
    return bulunanlar


# ---------- Ana fonksiyon ----------

def gonderen_kontrol(gonderen):
    """Gönderen satırını kontrol eder. Dönen sözlükteki 'karar':
    ŞÜPHELİ (kesin), GÜVENLİ LİSTE (kontrol atlanır) veya QWEN'E (bulgular ipucu olur)."""
    gorunen_ad, adres = parseaddr(str(gonderen))
    adres = adres.strip().lower()
    alan = adres.rsplit("@", 1)[1] if "@" in adres else ""
    sonuc = {"gonderen": gonderen, "adres": adres, "alan": alan, "liste": None,
             "taklit": None, "bulgular": [], "ucretsiz": False, "karar": QWEN, "gerekce": ""}

    if not alan:
        sonuc["gerekce"] = "Gönderen adresi yok veya okunamadı; karar içeriğe göre verilecek."
        return sonuc

    # 1) Listeler: önce engelli, sonra güvenli
    if listede_mi(adres, alan, satirlari_oku(ENGELLI_LISTE)):
        sonuc.update(liste="engelli", karar=SUPHELI,
                     gerekce=f"Gönderen ({adres}) engelli gönderenler listesinde.")
        return sonuc
    if listede_mi(adres, alan, satirlari_oku(GUVENLI_LISTE)):
        sonuc.update(liste="guvenli", karar=GUVENLI_GONDEREN,
                     gerekce=f"Gönderen ({adres}) güvenli gönderenler listesinde; gönderen adresi kuralları atlandı.")
        return sonuc

    markalar = markalari_oku()
    sonuc["ucretsiz"] = asil_alan(alan) in UCRETSIZ_SERVISLER   # bu adresi herkes alabilir

    # 2) Alan adıyla marka taklidi -> kesin ŞÜPHELİ
    taklit = marka_taklidi(alan, markalar)
    if taklit:
        sonuc.update(taklit=taklit, karar=SUPHELI,
                     gerekce=(f"{taklit['marka']} markası taklit ediliyor ({taklit['tur']}: {alan}); "
                              f"gerçek adres @{taklit['gercek']} olmalı."))

    # 3) Görünen ad bir markayı taşıyor ama adres o markanın değil
    marka = gorunen_ad_markasi(gorunen_ad, markalar)
    if marka and not taklit and asil_alan(alan) not in markalar[marka]:
        gercek = markalar[marka][0]
        if asil_alan(alan) in UCRETSIZ_SERVISLER:   # ücretsiz servisten kurum adıyla -> kesin ŞÜPHELİ
            taklit = {"marka": marka, "gercek": gercek, "tur": "görünen ad + ücretsiz e-posta servisi"}
            sonuc.update(taklit=taklit, karar=SUPHELI,
                         gerekce=(f"Gönderen adı '{gorunen_ad}' ama adres ücretsiz bir servisten ({alan}); "
                                  f"{marka} e-postaları @{gercek} adresinden gelir."))
        else:                                        # başka alan adı -> sadece ipucu
            sonuc["bulgular"].append(f"Gönderen adı '{gorunen_ad}' ama adres {marka} markasına ait değil "
                                     f"({alan}; gerçek alan adı {gercek}).")

    # 3b) Görünen ad kurumsal ('Update Account', 'Destek Ekibi') ama adres ücretsiz servisten -> ipucu
    kelime = kurumsal_ad(gorunen_ad)
    if kelime and not marka and sonuc["ucretsiz"]:
        sonuc["bulgular"].append(f"Gönderen adı kurumsal görünüyor ('{gorunen_ad}') ama adres ücretsiz "
                                 f"bir e-posta servisinden ({asil_alan(alan)}).")

    # 4) Görünen adda farklı bir e-posta adresi var mı?
    ad_icindeki = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", gorunen_ad.lower())
    if any(a != adres for a in ad_icindeki):
        sonuc["bulgular"].append(f"Gönderen adında başka bir adres yazıyor ({ad_icindeki[0]}); gerçek adres {adres}.")

    # 5) Garip alan adı işaretleri
    sonuc["bulgular"] += garip_alan_bulgulari(alan)

    if sonuc["karar"] == QWEN:
        sonuc["gerekce"] = (" ".join(sonuc["bulgular"]) if sonuc["bulgular"]
                            else "Gönderen kontrolü sorun bulmadı; karar içeriğe göre verilecek.")
    return sonuc


ORNEK_GONDERENLER = [
    "destek@binance.com",
    "destek@binance2.com",
    "info@binanse.com",
    "guvenlik@b1nance.com",
    "noreply@binance.com.hesap-dogrula.xyz",
    '"PayPal" <destek@gmail.com>',
    '"Garanti BBVA" <bilgi@garantibbva.com.tr>',
    "ali@firma.com",
    # Yanlış alarm kontrolü: hiçbiri taklit sayılmamalı
    "ahmet.yilmaz@gmail.com",
    "kampanya@trendyol.com",
    "bilgi@yurticikargo.com",
    "haber@hurriyet.com.tr",
]

if __name__ == "__main__":
    for g in ORNEK_GONDERENLER:
        s = gonderen_kontrol(g)
        tur = s["taklit"]["tur"] if s["taklit"] else "-"
        print(f"{g:45} | {s['karar']:13} | {tur:38} | {s['gerekce']}")
