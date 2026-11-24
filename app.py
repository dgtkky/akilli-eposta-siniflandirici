"""Demo ekranı: streamlit run app.py

Güvenlik notu: e-postadan gelen her metin (gönderen, bulunan ifadeler, benzer örnekler,
Qwen'in gerekçesi) st.text / st.code ile DÜZ METİN olarak gösterilir. Markdown kullanılmaz;
böylece e-postadaki bir oltalama bağlantısı ekranda tıklanabilir hale gelmez.
"""
import streamlit as st
from p3_analiz import analiz_et, ORNEKLER, kaynak_aciklamasi, GUVENLI_LISTE_UYARISI

# Seçim kutusundaki ad -> p3_analiz.ORNEKLER içindeki ad (metinler tek yerde tutulur)
SECENEKLER = {
    "Binance taklidi": "Kural: marka taklidi",
    "Türkçe kargo oltalaması": "Kargo oltalaması (TR)",
    "Nijerya dolandırıcılığı": "Nijerya dolandırıcılığı",
    "Talimat enjeksiyonu": "Talimat enjeksiyonu",
    "Güvenli listeden oltalama": "Güvenli liste: oltalama",
    "Normal iş e-postası": "Normal iş e-postası (TR)",
    "Trendyol kampanyası": "Trendyol kampanyası",
    "Kargo bildirimi": "Kargo (TR)",
}
BOS = "(Boş — kendim yazacağım)"
ORNEK = {ad: (gonderen, konu, metin) for ad, gonderen, konu, metin in ORNEKLER}


def ornek_yukle():
    """Seçilen örneği üç kutuya doldurur."""
    secim = st.session_state.ornek
    gonderen, konu, metin = ORNEK[SECENEKLER[secim]] if secim in SECENEKLER else ("", "", "")
    st.session_state.gonderen = gonderen
    st.session_state.konu = konu
    st.session_state.metin = metin


def asama_etiketi(s):
    kural = s["kural"]
    if s["asama"] == "liste":
        return "Gönderen listesi (engelli)"
    if s["asama"] == "kural":
        return "Kural (modelsiz): " + ("marka taklidi" if kural["taklit"] else "talimat enjeksiyonu")
    if s["asama"] == "yedek":
        return "Benzer e-postaların çoğunluğu (yedek)"
    if kural["liste"] == "guvenli":
        return "Qwen + benzer e-postalar (gönderen güvenli listede)"
    return "Qwen + benzer e-postalar"


def gonderen_satirlari(kural):
    satirlar = []
    if kural["liste"] == "guvenli":
        satirlar.append("Gönderen güvenli listende: adres kuralları atlandı, içerik yine incelendi.")
    elif kural["liste"] == "engelli":
        satirlar.append("Gönderen engelli listende.")
    if not kural["alan"]:
        satirlar.append("Gönderen adresi yok veya okunamadı.")
    if kural.get("ucretsiz"):
        satirlar.append("Adres ücretsiz bir e-posta servisinden; bu adresi herkes alabilir.")
    if kural["taklit"]:
        t = kural["taklit"]
        satirlar.append(f"Marka taklidi: {t['marka']} ({t['tur']}); gerçek adres @{t['gercek']} olmalı.")
    satirlar += kural["bulgular"]
    return satirlar or ["Gönderen kontrolü sorun bulmadı (bu, güvenilir olduğu anlamına gelmez)."]


# ---------- Sayfa ----------

st.set_page_config(page_title="Oltalama E-posta Tespiti", page_icon="🎣")
st.title("🎣 Oltalama E-posta Tespiti")
st.write("E-postayı girin. Sistem önce gönderene ve içeriğe kurallarla bakar, sonra etiketli "
         "benzer e-postalar ve Qwen ile karar verir ve nedenini açıklar.")

st.selectbox("Hazır örnek", [BOS, *SECENEKLER], key="ornek", on_change=ornek_yukle)
gonderen = st.text_input("Gönderen", key="gonderen", placeholder='"Ad Soyad" <adres@ornek.com>')
konu = st.text_input("Konu", key="konu")
metin = st.text_area("Metin", key="metin", height=220)

if st.button("Analiz et", type="primary"):
    if not metin.strip():
        st.warning("Lütfen e-posta metnini girin.")
        st.stop()
    try:
        with st.spinner("Analiz ediliyor..."):
            s = analiz_et(gonderen, konu, metin)
    except Exception as hata:
        st.error(f"Analiz yapılamadı. Ollama çalışıyor mu ve `python p2_indeks.py` çalıştırıldı mı?\n\n"
                 f"Hata: {type(hata).__name__}")
        st.stop()

    kural = s["kural"]
    gerekce = s["gerekce"]

    # --- Karar kutusu ---
    if s["karar"] == "ŞÜPHELİ":
        mesaj = f"### ⚠️ ŞÜPHELİ E-POSTA — Tür: {s['tur']}\n"
        if kural["liste"] == "guvenli":
            mesaj += ("\n**Bu adres güvenli listende ama içerik şüpheli; adres taklit edilmiş "
                      "veya hesap ele geçirilmiş olabilir.**\n")
            gerekce = gerekce.removeprefix(GUVENLI_LISTE_UYARISI).strip()   # aynı uyarı iki kez yazılmasın
        mesaj += "\nBağlantılara tıklamayın, bilgi veya ödeme göndermeyin."
        st.error(mesaj)
        st.subheader("Gerekçe")
        st.text(gerekce)
    else:
        kategori = s["kategori"]
        st.success(f"### ✅ GÜVENLİ — Kategori: {kategori['ad'] if kategori else '-'}")
        if kategori:
            st.subheader("Kategori gerekçesi")
            st.text(kategori["gerekce"])
            if kategori["yedek"]:
                st.warning("Model kategori biçimine uymadı; Diğer seçildi.")
        st.subheader("Neden güvenli")
        st.text(gerekce)

    if s["yedek_kullanildi"]:
        st.warning("Model cevap biçimine uymadı; karar benzer e-postaların çoğunluğuna göre verildi.")
    st.caption(f"Karar aşaması: {asama_etiketi(s)} · Süre: {s['sure']:.1f} sn")

    # --- Kontrol sonuçları ---
    st.subheader("Kontrol sonuçları")
    sol, sag = st.columns(2)
    with sol:
        st.markdown("**Gönderen kontrolü**")
        for satir in gonderen_satirlari(kural):
            st.text(f"• {satir}")
    with sag:
        st.markdown("**İçerik işaretleri**")
        if s["isaretler"]:
            for i in s["isaretler"]:
                st.text(f"• {i['isaret']}: \"{i['ifade']}\"")
        else:
            st.text("• İşaret bulunmadı.")
        st.caption("İşaretler kelime eşleşmesidir; tek başına karar vermez.")

    # --- Teknik ayrıntılar (varsayılan kapalı) ---
    with st.expander("Teknik ayrıntılar", expanded=False):
        if s["benzerler"]:
            st.markdown("**Benzer 5 e-posta (ChromaDB)**")
            for n, doc in enumerate(s["benzerler"], 1):
                st.markdown(f"**[E{n}] {doc.metadata['etiket_adi']} ({kaynak_aciklamasi(doc.metadata)})**")
                st.code(doc.page_content[:600], language=None, wrap_lines=True)
        else:
            st.info("Bu karar kurallarla verildi; benzer e-postalara bakılmadı.")
        if s["cevap"]:
            st.markdown("**Qwen'in ham cevabı (karar)**")
            st.code(s["cevap"], language=None, wrap_lines=True)
        if s["kategori"]:
            st.markdown("**Qwen'in ham cevabı (konu)**")
            st.code(s["kategori"]["cevap"], language=None, wrap_lines=True)
