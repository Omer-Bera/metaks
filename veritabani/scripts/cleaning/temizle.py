import pandas as pd
import re

print("🚀 Veri temizleme süreci başlatılıyor...")

# 1. Görsersiz Ham Excel Dosyasını Oku
input_file = 'urun_listesi_temiz.xlsx'
df = pd.read_excel(input_file)

# Sütun isimlerindeki gizli boşlukları temizle
df.columns = [str(col).strip() for col in df.columns]
stok_col = 'ÜRÜN STOK KODU'
kat_col = 'ÜRÜN KATEGORİ GRUBU'

# ---------------------------------------------------------
# ADIM 1: Karmaşık ve Temiz Ürünleri Bölme
# ---------------------------------------------------------
def is_complex_row(val):
    if pd.isna(val):
        return False
    val_str = str(val).strip()
    return any(char in val_str for char in ['/', ';', ':', '\n', ','])

complex_mask = df[stok_col].apply(is_complex_row)
df_clean = df[~complex_mask].copy()
df_complex = df[complex_mask].copy()

# Karmaşık olanları kaydet
df_complex.to_excel('karisik_urunler.xlsx', index=False)
print(f"1. AŞAMA: {len(df_clean)} adet temiz satır, {len(df_complex)} adet karmaşık satır ayrıldı.")

# ---------------------------------------------------------
# ADIM 2: Kategori Standartlaştırma (34 Ana Kategori)
# ---------------------------------------------------------
kategori_mapping = {
    '?': None, 'NAN': None, 'ÜRÜN YOK': None, 'NUMUNE': None, 'E': None,
    'TOKA': 'TOKA', 'BAŞLANTI TOKASI': 'BAŞLANTI TOKASI', 'PİERCİNG TOKA': 'PİERCİNG TOKA',
    'D TOKA': 'D TOKA', 'GECMELİ TOKA': 'GEÇMELİ TOKA', 'KEMER TOKASI': 'KEMER TOKASI',
    'ÇANTA TOKASI': 'ÇANTA TOKASI', 'AYAR TOKASI': 'AYAR', 'AYAR': 'AYAR', 'KANCALI AYAR TOKASI': 'AYAR',
    'ALTTAN DİKME': 'ALTTAN DİKME DÜĞME', 'ALTTAN DİKME DÜĞME': 'ALTTAN DİKME DÜĞME',
    'DİKME DÜĞME': 'ALTTAN DİKME DÜĞME', 'DİKME': 'ALTTAN DİKME DÜĞME', 'TOP DÜĞME': 'ALTTAN DİKME DÜĞME',
    'ÜSTEN DİKME DÜĞME': 'ÜSTTEN DİKME DÜĞME', 'ÜSTTEN DİKME DÜĞME': 'ÜSTTEN DİKME DÜĞME',
    'İKİ DELİKLİ DİKME DÜĞME': 'ÜSTTEN DİKME DÜĞME', 'BLAZER DÜĞME': 'ÜSTTEN DİKME DÜĞME',
    'ÇAKMA DÜĞME': 'ÇAKMA DÜĞME', 'ÇAKMA DÜĞME KAFASI': 'ÇAKMA DÜĞME', 'BLAZER ÇAKMA DÜĞME': 'ÇAKMA DÜĞME',
    'RİVET': 'RİVET', 'YILDIZ RİVET': 'RİVET', 'VİDALI RİVET': 'RİVET',
    'TROP': 'TROP', 'ÇİVİ': 'ÇİVİ', 'KÜÇÜK ÇİVİ': 'ÇİVİ',
    'ÇIT ÇIT': 'ÇIT ÇIT', 'ÇITÇIT KAFASI': 'ÇIT ÇIT',
    'PİRSİNG': 'PİRSİNG', 'PİERCİNG': 'PİRSİNG', 'BÜYÜK PİERCİNG': 'PİRSİNG',
    'KÜÇÜK PİERCİNG': 'PİRSİNG', 'KURU KAFA PİRSİNG': 'PİRSİNG', 'PRSİNG HALKASI': 'PİRSİNG',
    'BAĞ UCU': 'BAĞ UCU', 'HUNİ BAĞUCU': 'BAĞ UCU', 'BAĞUCU DELİKLİ': 'BAĞ UCU',
    'HALKA': 'HALKA', 'DESENLİ HALKA': 'HALKA', 'DİKDÖRTGEN HALKA': 'HALKA',
    'HALKA YASSI': 'HALKA', 'KESİK HALKA': 'HALKA', 'KUŞGÖZÜ': 'KUŞGÖZÜ',
    'BRİT': 'BRİT', 'YAKALIK': 'YAKALIK', 'SALLANTI': 'SALLANTI', 'PLAKA': 'PLAKA',
    'DİKME PLAKA': 'PLAKA', 'KÖPRÜ': 'KÖPRÜ', 'BİJUTERİ KÖPRÜ': 'KÖPRÜ',
    'İÇ ÇAMAŞI KÖPRÜ': 'KÖPRÜ', 'PAPAĞAN': 'PAPAĞAN', 'PAPAĞAN HALKA': 'PAPAĞAN',
    'PUL': 'PUL', 'AGRAF': 'AGRAF', 'ELCİK': 'ELCİK', 'ROZET': 'ROZET',
    'KANCA': 'KANCA', 'AYAR KANCA': 'KANCA', 'DİKME KANCA': 'KANCA', 'KISTIRMA': 'KISTIRMA',
    'STOPER': 'STOPER', 'ÇANTA KLİT': 'KİLİT',
    'AKSESUAR': 'DİĞER AKSESUAR', 'YAN AKSESUAR': 'DİĞER AKSESUAR', 'ÇANTA AKSESUAR': 'DİĞER AKSESUAR',
    'DİKME AKSESUAR': 'DİĞER AKSESUAR', 'BOYUNLUK': 'DİĞER AKSESUAR', 'HAMSİ': 'DİĞER AKSESUAR',
    'DİL': 'DİĞER AKSESUAR', 'ÇAN': 'DİĞER AKSESUAR', 'LOGOLU': 'DİĞER AKSESUAR',
    'V BALEN': 'DİĞER AKSESUAR', 'U BALEN': 'DİĞER AKSESUAR', 'İNCİ KASASI': 'DİĞER AKSESUAR'
}

df_clean[kat_col] = (
    df_clean[kat_col]
    .astype(str)
    .str.strip()
    .str.upper()
    .replace(r'\s+', ' ', regex=True)
    .map(kategori_mapping)
)
print("2. AŞAMA: Kategoriler standartlaştırıldı.")

# ---------------------------------------------------------
# ADIM 3: Geçersiz / Boş Stok Kodlarını Ayırma
# ---------------------------------------------------------
def is_empty_or_question(val):
    if pd.isna(val):
        return True
    val_str = str(val).strip()
    return val_str in ['?', '', 'nan', 'None'] or val_str.startswith('?')

invalid_stok_mask = df_clean[stok_col].apply(is_empty_or_question)
df_stoklu = df_clean[~invalid_stok_mask].copy().reset_index(drop=True)
df_stoksuz = df_clean[invalid_stok_mask].copy()

df_stoksuz.to_excel('temiz_urunler_stoksuz.xlsx', index=False)
print(f"3. AŞAMA: {len(df_stoklu)} geçerli stoklu ürün alındı, {len(df_stoksuz)} stoksuz ürün ayrıldı.")

# ---------------------------------------------------------
# ADIM 4: Parent-Child Mantığı ("ÜSTTEKİ ÜRÜNÜN PULU" Düzeltmesi)
# ---------------------------------------------------------
df_stoklu['ANA_STOK_KODU'] = None
df_stoklu['ÜRÜN TİPİ'] = 'ANA_URUN'

for i in range(len(df_stoklu)):
    val = str(df_stoklu.loc[i, stok_col]).strip()
    if 'ÜSTTEKİ' in val.upper() or 'USTTEKİ' in val.upper():
        parent_stok = str(df_stoklu.loc[i-1, stok_col]).strip()
        new_stok = f"{parent_stok}-PUL"
        
        df_stoklu.loc[i, stok_col] = new_stok
        df_stoklu.loc[i, 'ANA_STOK_KODU'] = parent_stok
        df_stoklu.loc[i, 'ÜRÜN TİPİ'] = 'ALT_PARCA'
        df_stoklu.loc[i, 'ÜRÜN AÇIKLAMASI'] = f"{parent_stok} ürününün pulu / tamamlayıcı parçası"
        print(f"   ↳ Parent-Child Dönüştürüldü: {val} -> {new_stok} (Ana Kod: {parent_stok})")

# Tamamen temizlenmiş stoklu dosyayı kaydet
output_file = 'temiz_urunler_stoklu.xlsx'
df_stoklu.to_excel(output_file, index=False)

print(f"\n✅ İŞLEM TAMAMLANDI! Temiz dosyanız oluşturuldu: {output_file}")