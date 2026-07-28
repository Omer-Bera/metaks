import pandas as pd
import re

print("✂️ Dosya standart ve düzenlenecek ölçüler olarak ikiye ayrılıyor...")

# Ana temiz dosyayı oku
df = pd.read_excel('temiz_urunler_stoklu.xlsx')

# Ölçünün temiz olup olmadığını kontrol eden fonksiyon
def is_clean_val(val):
    if pd.isna(val):
        return True # Boş hücre (NULL) standart kabul edilir
    
    val_str = str(val).strip().lower()
    
    if val_str in ['?', 'ürün yok', 'nan', 'none', '', '-', '.']:
        return True # İçi boş/geçersiz stringler standart (NULL) kabul edilir
        
    # Sadece sayı ve isteğe bağlı birim (mm, cm, boy vb.) kuralı
    match = re.fullmatch(r'^(\d+(?:[.,]\d+)?)\s*(mm|cm|boy|ligne)?\s*$', val_str)
    return match is not None

# 'mm' ve 'Boy' sütunlarını denetle
clean_mm = df['ÜRÜN DETAYI (mm)'].apply(is_clean_val)
clean_boy = df['ÜRÜN DETAYI (Boy)'].apply(is_clean_val)

# İki sütun da temizse True, biri bile bozuksa False
is_totally_clean = clean_mm & clean_boy

# Dataframeleri ikiye böl
df_standart = df[is_totally_clean].copy()
df_duzenlenecek = df[~is_totally_clean].copy()

# Ayrı ayrı Excel olarak kaydet
df_standart.to_excel('temiz_urunler_standart.xlsx', index=False)
df_duzenlenecek.to_excel('temiz_urunler_olcu_duzenlenecek.xlsx', index=False)

print(f"✅ İşlem Tamamlandı!")
print(f"📁 1. temiz_urunler_standart.xlsx oluşturuldu ({len(df_standart)} satır).")
print(f"📁 2. temiz_urunler_olcu_duzenlenecek.xlsx oluşturuldu ({len(df_duzenlenecek)} satır).")