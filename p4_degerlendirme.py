"""Adım 5: Şüpheli / güvenli kararının test setinde değerlendirilmesi.

- Test setinden sabit bir örneklem alınır: 100 şüpheli + 100 güvenli, kaynaklara eşit dağıtılmış.
  Örneklem sonuclar/orneklem.csv'ye kaydedilir; dosya varsa her seferinde aynı örneklem kullanılır.
- Konu sınıflandırması kapalıdır (konu_bul=False); yalnızca karar ölçülür.
- Pozitif sınıf ŞÜPHELİ'dir: "geri çağırma" = şüphelilerin yüzde kaçı yakalandı.
- Test e-postaları ChromaDB'ye eklenmez; yalnızca analiz edilir.

Dilimler (ikisi de 100 şüpheli + 100 güvenli, kaynaklara eşit):
- a: sonuclar/orneklem.csv
- b: sonuclar/orneklem_b.csv — test setinden, a'da OLMAYAN e-postalar (değişikliklerin
     görülmemiş verideki etkisini ölçmek için)
Sonuçlar sonuclar/<sürüm>/<dilim>/ altına yazılır.

Çalıştır:
    caffeinate -i python p4_degerlendirme.py --surum v2 --dilim a
    caffeinate -i python p4_degerlendirme.py --surum v2 --dilim b
    caffeinate -i python p4_degerlendirme.py 10     # deneme: 5 şüpheli + 5 güvenli (deneme_ önekiyle kaydedilir)
"""
import argparse
import time
import pandas as pd
from config import TEST_CSV, ROOT, RASTGELE
from p3_analiz import analiz_et

SONUC_DIR = ROOT / "sonuclar"          # e-posta metinleri bu proje klasöründe kalır
ORNEKLEMLER = {"a": SONUC_DIR / "orneklem.csv", "b": SONUC_DIR / "orneklem_b.csv"}
SINIF_BASINA = 100


# ---------- Örneklem ----------

def esit_ornekle(df, toplam):
    """toplam e-postayı kaynaklara eşit dağıtır; artanlar ilk kaynaklara verilir (p1_veri.py gibi)."""
    kaynaklar = sorted(df["kaynak"].unique())
    pay, artan = divmod(toplam, len(kaynaklar))
    parcalar = [df[df["kaynak"] == k].sample(n=pay + (1 if i < artan else 0), random_state=RASTGELE)
                for i, k in enumerate(kaynaklar)]
    return pd.concat(parcalar)


def orneklem_al(dilim="a"):
    dosya = ORNEKLEMLER[dilim]
    if dosya.exists():
        return pd.read_csv(dosya, keep_default_na=False)
    test = pd.read_csv(TEST_CSV, keep_default_na=False)
    if dilim == "b":   # a örnekleminde olan e-postalar çıkarılır
        test = test[~test["metin"].isin(orneklem_al("a")["metin"])]
    orneklem = pd.concat([esit_ornekle(test[test["etiket"] == e], SINIF_BASINA) for e in (1, 0)])
    SONUC_DIR.mkdir(exist_ok=True)
    orneklem.to_csv(dosya, index=False)
    print(f"Yeni örneklem oluşturuldu: {dosya}")
    return orneklem


# ---------- Ölçütler (elle hesaplanır, öğretici olsun diye) ----------

def olcutler(gercek, tahmin):
    """1 = ŞÜPHELİ (pozitif), 0 = GÜVENLİ."""
    dp = sum(g == 1 and t == 1 for g, t in zip(gercek, tahmin))   # doğru pozitif: şüpheli yakalandı
    yp = sum(g == 0 and t == 1 for g, t in zip(gercek, tahmin))   # yanlış pozitif: güvenliye yanlış alarm
    dn = sum(g == 0 and t == 0 for g, t in zip(gercek, tahmin))   # doğru negatif
    yn = sum(g == 1 and t == 0 for g, t in zip(gercek, tahmin))   # yanlış negatif: şüpheli kaçtı
    n = dp + yp + dn + yn
    kesinlik = dp / (dp + yp) if dp + yp else 0.0
    geri = dp / (dp + yn) if dp + yn else 0.0
    f1 = 2 * kesinlik * geri / (kesinlik + geri) if kesinlik + geri else 0.0
    return {"n": n, "dp": dp, "yp": yp, "dn": dn, "yn": yn, "dogruluk": (dp + dn) / n if n else 0.0,
            "kesinlik": kesinlik, "geri_cagirma": geri, "f1": f1}


# ---------- Rapor ----------

def rapor(t):
    o = olcutler(t["etiket"], t["tahmin"])
    satirlar = [
        f"=== GENEL SONUÇLAR ({o['n']} e-posta; pozitif sınıf = ŞÜPHELİ) ===",
        f"Doğruluk       : %{o['dogruluk'] * 100:.1f}",
        f"Kesinlik       : %{o['kesinlik'] * 100:.1f}   (ŞÜPHELİ dediklerinin yüzde kaçı gerçekten şüpheli)",
        f"Geri çağırma   : %{o['geri_cagirma'] * 100:.1f}   (gerçek şüphelilerin yüzde kaçı yakalandı)",
        f"F1             : %{o['f1'] * 100:.1f}",
        f"Ortalama süre  : {t['sure'].mean():.1f} sn / e-posta  (ortanca {t['sure'].median():.1f}, "
        f"en uzun {t['sure'].max():.1f}, toplam {t['sure'].sum() / 60:.1f} dk)",
        "",
        "Karmaşıklık matrisi:",
        "                    tahmin ŞÜPHELİ   tahmin GÜVENLİ",
        f"  gerçek ŞÜPHELİ    {o['dp']:>14}   {o['yn']:>14}",
        f"  gerçek GÜVENLİ    {o['yp']:>14}   {o['dn']:>14}",
    ]
    hata = (t["karar"] == "HATA").sum()
    if hata:
        satirlar.append(f"\nNot: {hata} e-postada analiz hatası oldu; GÜVENLİ sayıldı.")

    satirlar += ["", "=== KAYNAK BAZINDA ==="]
    for etiket, baslik in ((1, "Şüpheli kaynaklar (yakalanma oranı)"),
                           (0, "Güvenli kaynaklar (doğru GÜVENLİ denme oranı)")):
        satirlar.append(baslik + ":")
        for kaynak, grup in t[t["etiket"] == etiket].groupby("kaynak"):
            dogru = (grup["tahmin"] == etiket).sum()
            satirlar.append(f"  {kaynak:<15} {dogru:>3}/{len(grup):<3} %{dogru / len(grup) * 100:5.1f}"
                            f"   ort. {grup['sure'].mean():.1f} sn")
    naz = t[(t["kaynak"] == "Nazario") & (t["etiket"] == 1)]
    if len(naz):
        satirlar.append(f"  → Nazario oltalamaları: {(naz['tahmin'] == 1).sum()}/{len(naz)} yakalandı "
                        f"(%{(naz['tahmin'] == 1).mean() * 100:.1f}).")

    satirlar += ["", "=== KARARIN VERİLDİĞİ AŞAMA ===",
                 "  aşama   sayı   doğru   gerçek şüpheli / güvenli   ort. süre"]
    for asama in ("liste", "kural", "qwen", "yedek", "hata"):
        grup = t[t["asama"] == asama]
        if len(grup):
            dogru = (grup["tahmin"] == grup["etiket"]).sum()
            satirlar.append(f"  {asama:<7} {len(grup):>4}   {dogru:>3}/{len(grup):<3}   "
                            f"{(grup['etiket'] == 1).sum():>8} / {(grup['etiket'] == 0).sum():<8}"
                            f"       {grup['sure'].mean():.1f} sn")
    return "\n".join(satirlar)


# ---------- Ana akış ----------

def degerlendir(sinir=None, surum="", dilim="a"):
    orneklem = orneklem_al(dilim)
    if sinir:   # deneme: her sınıftan sinir/2 e-posta (karışık kaynaklardan)
        orneklem = pd.concat([orneklem[orneklem["etiket"] == e].sample(n=sinir // 2, random_state=RASTGELE)
                              for e in (1, 0)])
    onek = "deneme_" if sinir else ""

    kayitlar = []
    baslangic = time.time()
    for i, s in enumerate(orneklem.itertuples(), 1):
        try:
            r = analiz_et(s.gonderen, s.konu, s.govde, konu_bul=False)
            karar, tur, asama, gerekce, sure = r["karar"], r["tur"], r["asama"], r["gerekce"], r["sure"]
        except Exception as hata:          # tek bir e-postadaki hata bütün ölçümü durdurmasın
            karar, tur, asama, gerekce, sure = "HATA", "-", "hata", type(hata).__name__, 0.0
        tahmin = 1 if karar == "ŞÜPHELİ" else 0
        kayitlar.append({"kaynak": s.kaynak, "etiket": int(s.etiket), "tahmin": tahmin, "karar": karar,
                         "tur": tur, "asama": asama, "sure": round(sure, 2), "gerekce": gerekce,
                         "gonderen": s.gonderen, "konu": s.konu, "govde": s.govde})
        isaret = "✓" if tahmin == s.etiket else "✗"
        print(f"{i:>3}/{len(orneklem)} {isaret} {s.kaynak:<15} gerçek={'ŞÜPHELİ' if s.etiket else 'GÜVENLİ'} "
              f"tahmin={karar:<8} aşama={asama:<6} {sure:.1f} sn", flush=True)

    t = pd.DataFrame(kayitlar)
    klasor = SONUC_DIR / surum / dilim if surum else SONUC_DIR
    klasor.mkdir(parents=True, exist_ok=True)
    t.drop(columns=["govde"]).to_csv(klasor / f"{onek}tahminler.csv", index=False)
    t[t["tahmin"] != t["etiket"]].to_csv(klasor / f"{onek}yanlislar.csv", index=False)
    metin = (f"Sürüm: {surum or '-'} · Dilim: {dilim}\n" + rapor(t)
             + f"\n\nToplam çalışma süresi: {(time.time() - baslangic) / 60:.1f} dk")
    (klasor / f"{onek}ozet.txt").write_text(metin, encoding="utf-8")
    print("\n" + metin)
    print(f"\nKaydedildi: {klasor}/{onek}tahminler.csv, {onek}yanlislar.csv, {onek}ozet.txt")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Şüpheli/güvenli kararını test örnekleminde ölçer.")
    ap.add_argument("sinir", nargs="?", type=int, help="deneme için e-posta sayısı (ör. 10)")
    ap.add_argument("--surum", default="", help="sonuçların yazılacağı alt klasör (ör. v2)")
    ap.add_argument("--dilim", default="a", choices=["a", "b"], help="a: orneklem.csv, b: orneklem_b.csv")
    arg = ap.parse_args()
    degerlendir(arg.sinir, arg.surum, arg.dilim)
