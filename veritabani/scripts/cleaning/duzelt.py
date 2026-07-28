import pandas as pd

print("🧹 Tekrar eden açıklamalar temizleniyor...")

# Mevcut dosyanızı okuyoruz (en son hangi isme kaydettiyseniz onu yazın)
df = pd.read_excel('temiz_urunler_stoklu.xlsx')

def tekrar_temizle(val):
    if pd.isna(val):
        return val
    
    # Metni ' | ' işaretinden parçalara böl
    parcalar = str(val).split(' | ')
    
    # Tekrar edenleri silmek için bir küme (set) kullan
    temiz_parcalar = []
    gorulenler = set()
    
    for p in parcalar:
        p = p.strip()
        if p and p not in gorulenler:
            gorulenler.add(p)
            temiz_parcalar.append(p)
            
    # Temizlenmiş parçaları tekrar ' | ' ile birleştir
    return ' | '.join(temiz_parcalar)

# Açıklama sütununa temizlik fonksiyonunu uygula
df['ÜRÜN AÇIKLAMASI'] = df['ÜRÜN AÇIKLAMASI'].apply(tekrar_temizle)

# Aynı dosyanın üzerine tertemiz şekilde kaydet
df.to_excel('temiz_urunler_stoklu.xlsx', index=False)

print("✅ İşlem tamam! Çift yazılan açıklamalar teke düşürüldü.")