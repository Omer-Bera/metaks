import pandas as pd
import re

print("📏 Ölçü (mm ve Boy) temizleme ve açıklamalara aktarma işlemi başlatılıyor...")

df = pd.read_excel('temiz_urunler_stoklu.xlsx')

def strict_parse(val, is_mm=True):
    if pd.isna(val):
        return None, None
    val_str = str(val).strip()
    val_lower = val_str.lower()
    
    # Hatalı/Boş veriler
    if val_lower in ['?', 'ürün yok', 'nan', 'none', '', '-', '.']:
        return None, None
        
    # Sadece ve sadece rakam (ve isteğe bağlı birim) barındıranları yakala
    # Örn: "15", "15 mm", "12,5", "12.5cm" -> Temiz.
    match = re.fullmatch(r'^(\d+(?:[.,]\d+)?)\s*(mm|cm|boy|ligne)?\s*$', val_lower)
    
    if match:
        num = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
        if unit == 'cm' and is_mm:
            num *= 10 # cm'yi mm'ye çevir
        return num, None # Temiz sayı döndür, açıklama döndürme
    
    # Kurala uymayanlar (çoklu ölçü, harf içerenler) için orijinal metni döndür
    return None, val_str

# Her satır için işlemi uygula
for i in range(len(df)):
    mm_val = df.loc[i, 'ÜRÜN DETAYI (mm)']
    boy_val = df.loc[i, 'ÜRÜN DETAYI (Boy)']
    
    mm_num, mm_desc = strict_parse(mm_val, is_mm=True)
    boy_num, boy_desc = strict_parse(boy_val, is_mm=False)
    
    # Yeni temiz sütunlara sayıları bas
    df.loc[i, 'olcu_mm'] = mm_num
    df.loc[i, 'boy_ligne'] = boy_num
    
    # Karmaşık olanları açıklamaya ekle
    ek_aciklama = []
    if mm_desc:
        ek_aciklama.append(f"Orijinal Ölçü Notu: {mm_desc}")
    if boy_desc:
        ek_aciklama.append(f"Orijinal Boy Notu: {boy_desc}")
        
    if ek_aciklama:
        mevcut_aciklama = str(df.loc[i, 'ÜRÜN AÇIKLAMASI'])
        ek_metin = " | ".join(ek_aciklama)
        if pd.isna(df.loc[i, 'ÜRÜN AÇIKLAMASI']) or mevcut_aciklama.lower() == 'nan':
            df.loc[i, 'ÜRÜN AÇIKLAMASI'] = ek_metin
        else:
            df.loc[i, 'ÜRÜN AÇIKLAMASI'] = mevcut_aciklama + " | " + ek_metin

# Dosyayı kaydet
df.to_excel('temiz_urunler_stoklu.xlsx', index=False)
print("✅ Temizlik tamamlandı. Temiz sayılar 'olcu_mm' ve 'boy_ligne' sütunlarına yazıldı.")
print("   Karmaşık veriler ise başarıyla 'ÜRÜN AÇIKLAMASI' sütununa taşındı.")