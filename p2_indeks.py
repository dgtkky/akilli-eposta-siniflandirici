"""Adım 2: Train e-postalarını etiket, kaynak ve gönderen bilgisiyle ChromaDB'ye ekle.

Kullanım:
    python p2_indeks.py        # train setinin tamamı
    python p2_indeks.py 100    # deneme: ilk 100 e-posta
"""
import shutil
import sys
import time
import pandas as pd
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from config import (ROOT, TRAIN_CSV, DB_DIR, COLLECTION, OLLAMA_URL,
                    EMBED_MODEL, MAX_KARAKTER, ETIKET_ADI, KEEP_ALIVE)

def embedding_client():
    return OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL, keep_alive=KEEP_ALIVE)

def belgeleri_olustur(limit=None):
    # Yalnızca train.csv okunur: test e-postaları asla ChromaDB'ye girmez
    train = pd.read_csv(TRAIN_CSV)
    if limit:
        train = train.head(limit)
    belgeler = []
    for i, satir in enumerate(train.itertuples()):
        etiket = int(satir.etiket)
        belgeler.append(Document(
            page_content=str(satir.metin)[:MAX_KARAKTER],
            metadata={
                "etiket": etiket,
                "etiket_adi": ETIKET_ADI[etiket],
                "kaynak": str(satir.kaynak),
                "gonderen": str(satir.gonderen),
                "ornek_id": f"train_{i:05d}",
            },
        ))
    return belgeler

def indeks_olustur(limit=None, parti=100):
    # Dersteki gibi: yalnızca bu projenin klasörü silinebilir
    if DB_DIR.exists():
        if DB_DIR.resolve().parent != ROOT.resolve() or DB_DIR.name != "chroma_eposta":
            raise RuntimeError("Güvensiz veritabanı silme yolu")
        shutil.rmtree(DB_DIR)

    belgeler = belgeleri_olustur(limit)
    store = Chroma(collection_name=COLLECTION, embedding_function=embedding_client(),
                   persist_directory=str(DB_DIR))

    # Çok sayıda e-posta olduğu için partiler halinde ekliyoruz
    for bas in range(0, len(belgeler), parti):
        grup = belgeler[bas:bas + parti]
        store.add_documents(grup, ids=[b.metadata["ornek_id"] for b in grup])
        print(f"  {bas + len(grup)}/{len(belgeler)} e-posta eklendi")
    return store, len(belgeler)

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    baslangic = time.time()
    db, n = indeks_olustur(limit)
    sure = time.time() - baslangic

    print("Koleksiyondaki kayıt:", len(db.get()["ids"]))
    print("Chroma dizini:", DB_DIR)
    print(f"Süre: {sure:.1f} sn | e-posta başına: {sure / n:.3f} sn")
    if limit:
        toplam = len(pd.read_csv(TRAIN_CSV))
        print(f"Tamamı ({toplam} e-posta) için tahmini süre: {sure / n * toplam / 60:.1f} dk")

    ornek = db.get(limit=1)["metadatas"][0]
    print("Örnek metadata:", ornek)
