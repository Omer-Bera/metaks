import pandas as pd

print("🛠️ Göz sayısı (Kalıp) verileri güvence altına alınıyor...")

# İçinde göz sayısı bulunan orijinal/temizlenmiş dosyamızı okuyoruz
df = pd.read_excel('temiz_urunler_stoklu.xlsx')

# Sadece stok kodu ve göz sayısı sütunlarını al
df_kalip = df[['ÜRÜN STOK KODU', 'ÜRÜN GÖZ SAYISI']].copy()

# Göz sayısı boş (NaN) olan satırları filtrele (sadece kalıp bilgisi olanlar kalsın)
df_kalip = df_kalip.dropna(subset=['ÜRÜN GÖZ SAYISI'])

# İleride veritabanına eklenecek yeni tablo yapısına uygun isimlendir
df_kalip.rename(columns={
    'ÜRÜN STOK KODU': 'kalip_stok_kodu',
    'ÜRÜN GÖZ SAYISI': 'kalip_goz_sayisi'
}, inplace=True)

# Ayrı bir Excel olarak kaydet
df_kalip.to_excel('kalip_bilgileri_yedek.xlsx', index=False)

print(f"✅ İşlem tamam! {len(df_kalip)} adet ürünün kalıp/göz bilgisi başarıyla kurtarıldı.")
print("💾 'kalip_bilgileri_yedek.xlsx' dosyasına kaydedildi. İleride yeni SQL tablosuna buradan aktaracağız.")