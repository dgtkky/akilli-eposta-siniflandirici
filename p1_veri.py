"""Adım 1: 6 CSV'yi oku, temizle, her sınıftan kaynaklara eşit örnek al, train/test ayır."""
import re
import pandas as pd
from config import (ROOT, VERI_DOSYALARI, GONDERENSIZ, TRAIN_CSV, TEST_CSV,
                    ORNEK_SAYISI, TEST_ORANI, RASTGELE, NOTR_ALAN)

# monkey.org: Nazario veri setini toplayan kişinin adresi. Modelin "monkey.org geçiyorsa
# şüphelidir" gibi yanlış bir kısayol öğrenmemesi için bu adı nötr bir adla değiştiriyoruz.
MONKEY_ADRES = re.compile(r"[\w.+-]+@(?:[\w-]+\.)*monkey\.org", re.IGNORECASE)
MONKEY_ALAN = re.compile(r"(?:[\w-]+\.)*monkey\.org", re.IGNORECASE)

def monkey_temizle(yazi):
    yazi = MONKEY_ADRES.sub(f"kullanici@{NOTR_ALAN}", yazi)
    return MONKEY_ALAN.sub(NOTR_ALAN, yazi)

def dosya_oku(ad):
    df = pd.read_csv(ROOT / f"{ad}.csv")
    df["kaynak"] = ad
    df["konu"] = df["subject"].fillna("").astype(str).str.strip()
    df["govde"] = df["body"].fillna("").astype(str).str.strip()

    if ad in GONDERENSIZ:
        df["gonderen"] = "(bilinmiyor)"
    else:
        # Gönderen sütunu olan dosyalarda göndereni boş olan e-postaları atıyoruz
        df["gonderen"] = df["sender"].fillna("").astype(str).str.strip()
        df = df[df["gonderen"] != ""].copy()

    if ad == "Nazario":
        df = df[~df["gonderen"].str.contains("monkey.org", case=False)].copy()
        df["konu"] = df["konu"].map(monkey_temizle)
        df["govde"] = df["govde"].map(monkey_temizle)

    df["etiket"] = df["label"].astype(int)
    return df[["kaynak", "gonderen", "konu", "govde", "etiket"]]

def veriyi_hazirla():
    df = pd.concat([dosya_oku(ad) for ad in VERI_DOSYALARI], ignore_index=True)
    print("Okunan e-posta:", len(df))

    # Her e-posta tek metne çevrilir
    df["metin"] = "Gönderen: " + df["gonderen"] + "\nKonu: " + df["konu"] + "\nMetin: " + df["govde"]

    # Temizlik: çok kısa gövdeleri ve tamamen aynı e-postaları at
    df = df[df["govde"].str.len() > 20]
    df = df.drop_duplicates(subset="metin")
    print("Temizlik sonrası:", len(df))

    # Her sınıftan ORNEK_SAYISI e-posta, sınıftaki kaynaklara eşit paylaştırılır.
    # Her kaynak kendi içinde %80 train / %20 test ayrılır.
    train_parcalari, test_parcalari = [], []
    for etiket in (0, 1):
        sinif = df[df["etiket"] == etiket]
        kaynaklar = sorted(sinif["kaynak"].unique())
        for sira, kaynak in enumerate(kaynaklar):
            # Bölme tam çıkmazsa artan e-postalar ilk kaynaklara birer birer eklenir
            kaynak_basi = ORNEK_SAYISI // len(kaynaklar) + (1 if sira < ORNEK_SAYISI % len(kaynaklar) else 0)
            grup = sinif[sinif["kaynak"] == kaynak]
            if len(grup) < kaynak_basi:
                raise ValueError(f"{kaynak} / etiket={etiket}: {len(grup)} e-posta var, {kaynak_basi} gerekli")
            grup = grup.sample(n=kaynak_basi, random_state=RASTGELE)
            sinir = int(kaynak_basi * (1 - TEST_ORANI))
            train_parcalari.append(grup.iloc[:sinir])
            test_parcalari.append(grup.iloc[sinir:])

    train = pd.concat(train_parcalari).sample(frac=1, random_state=RASTGELE)
    test = pd.concat(test_parcalari).sample(frac=1, random_state=RASTGELE)
    train.to_csv(TRAIN_CSV, index=False)
    test.to_csv(TEST_CSV, index=False)
    return train, test

if __name__ == "__main__":
    train, test = veriyi_hazirla()
    print("\nTrain:", len(train), "| Test:", len(test))
    print("\nKaynak / etiket dağılımı (train):")
    print(train.groupby(["etiket", "kaynak"]).size().to_string())
    print("\nKaynak / etiket dağılımı (test):")
    print(test.groupby(["etiket", "kaynak"]).size().to_string())

    ortak = set(train["metin"]) & set(test["metin"])
    print("\nTrain ile test arasında ortak e-posta:", len(ortak), "(0 olmalı)")
    tum = pd.concat([train, test])
    nazario = tum[tum["kaynak"] == "Nazario"]
    print("Nazario'da kalan monkey.org geçişi:", nazario["metin"].str.contains("monkey.org", case=False).sum(), "(0 olmalı)")
    print("Gönderen bilinmeyen kaynaklar:", sorted(tum.loc[tum["gonderen"] == "(bilinmiyor)", "kaynak"].unique()))

    print("\nÖrnek metin:\n" + train.iloc[0]["metin"][:400])
