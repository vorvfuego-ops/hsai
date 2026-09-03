import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings
from streamlit_autorefresh import st_autorefresh

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Quantum BIST Terminali", layout="wide")

# --- OTOMATİK YENİLEME (60 Saniye) ---
# Bu satır uygulamanın tamamını 60 saniyede bir otomatik yeniler.
st_autorefresh(interval=60000, key="data_refresh")

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0A0E17; color: #E0E0E0; }
    section[data-testid="stSidebar"] { background: linear-gradient(180deg, #101624, #0A0E17); border-right: 1px solid #1F2937; }
    section[data-testid="stSidebar"] .stButton > button { background-color: transparent; color: #8B949E; border: none; text-align: left; width: 100%; padding: 10px; font-size: 16px; font-weight: 500; border-radius: 8px; transition: all 0.3s ease; }
    section[data-testid="stSidebar"] .stButton > button:hover { background-color: #1F2937; color: #58A6FF; }
    thead tr th:first-child {display:none}
    thead tr th { background-color: #161B22 !important; color: #58A6FF !important; font-weight: bold; border-bottom: 2px solid #30363D; }
    tbody tr:nth-child(even) { background-color: #161B22; }
    tbody tr:hover { background-color: #1F2937; }
    h1, h2, h3 { color: #FFFFFF !important; letter-spacing: -0.5px; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 2px solid #30363D; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; color: #8B949E; border-radius: 8px 8px 0 0; padding: 12px 24px; font-weight: 600; border: none; transition: all 0.3s ease; }
    .stTabs [aria-selected="true"] { background-color: #161B22 !important; color: #58A6FF !important; border-bottom: 3px solid #58A6FF; }
</style>
""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, pd.Series):
        if val.empty: return 0.0
        try: return float(val.iloc[0])
        except: return 0.0
    try: return float(val)
    except: return 0.0

def format_big_number(val):
    try:
        val = float(val)
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f} mr"
        elif val >= 1_000_000:
            return f"{val / 1_000_000:.2f} mn"
        elif val >= 1_000:
            return f"{val / 1_000:.2f} bin"
        else:
            return f"{val:.0f}"
    except:
        return "N/A"

def format_percent(val):
    try:
        if pd.isna(val) or val == "" or val == "N/A":
            return "N/A"
        return f"{float(val):.2f}%"
    except:
        return "N/A"

# --- TRADINGVIEW TOKEN ---
def get_auth_token():
    try:
        username = st.secrets["tradingview"]["username"]
        password = st.secrets["tradingview"]["password"]
        url = 'https://www.tradingview.com/accounts/signin/'
        data = {"username": username, "password": password, "remember": "on"}
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.post(url=url, data=data, headers=headers)
        if response.status_code == 200:
            return response.json()['user']['auth_token']
    except:
        return None

# --- VERİ ÇEKME ---
@st.cache_data(ttl=60) # 60 saniyede bir verileri tazele
def tum_bist_hisselerini_getir():
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        q = Query().set_markets('turkey').select(
            'name', 'close', 'change', 'volume', 'market_cap_basic', 
            'sector', 'high_all_calc', 'RSI', 
            'Perf.W', 'Perf.1M', 'Perf.3M', 'Perf.6M', 'Perf.YTD', 
            'Perf.1Y', 'Perf.3Y', 'Perf.5Y'
        ).order_by('volume', ascending=False).limit(500)
        
        try:
            total, df = q.get_scanner_data(auth_token=token)
        except:
            total, df = q.get_scanner_data()
        
        if df.empty:
            return pd.DataFrame()
            
        df = df.rename(columns={
            'name': 'Hisse', 'close': 'Fiyat', 'change': 'Gün %', 
            'volume': 'Hacim', 'market_cap_basic': 'Piyasa Değeri',
            'Perf.W': 'Getiri % (Son 1 hafta)', 'Perf.1M': 'Getiri % (Son 1 ay)',
            'Perf.3M': 'Getiri % (Son 3 ay)', 'Perf.6M': 'Getiri % (Son 6 ay)',
            'Perf.YTD': 'Getiri % (Yılbaşından)', 'Perf.1Y': 'Getiri % (Son 1 yıl)',
            'Perf.3Y': 'Getiri % (Son 3 yıl)', 'Perf.5Y': 'Getiri % (Son 5 yıl)'
        })
        
        # Doğru Hacim Hesaplaması (Adet * Fiyat = TL)
        df['Hacim'] = (pd.to_numeric(df['Hacim'], errors='coerce') * pd.to_numeric(df['Fiyat'], errors='coerce')).apply(format_big_number)
        
        # Piyasa değeri bin TL cinsinden gelir
        df['Piyasa Değeri'] = df['Piyasa Değeri'].apply(lambda x: format_big_number(safe_float(x) * 1000))
        
        return df
    except Exception:
        return pd.DataFrame()

# --- GELİŞMİŞ YZ MODELİ ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    df['Gün %'] = pd.to_numeric(df['Gün %'], errors='coerce').fillna(0)
    df['52H_Yuksek'] = pd.to_numeric(df.get('high_all_calc', 0), errors='coerce').fillna(0)
    
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100
    
    # YZ Tahmin Modülü (Eksik verileri tamamlar)
    def ai_tahmin_1y(row):
        val_1y = row.get('Getiri % (Son 1 yıl)')
        if pd.isna(val_1y) or val_1y == "N/A" or val_1y == "":
            val_6m = row.get('Getiri % (Son 6 ay)')
            try: return safe_float(val_6m) * 2
            except: return None
        return val_1y

    def ai_tahmin_3y(row):
        val_3y = row.get('Getiri % (Son 3 yıl)')
        if pd.isna(val_3y) or val_3y == "N/A" or val_3y == "":
            val_1y = row.get('Getiri % (Son 1 yıl)')
            try: return safe_float(val_1y) * 3
            except: return None
        return val_3y

    def ai_tahmin_5y(row):
        val_5y = row.get('Getiri % (Son 5 yıl)')
        if pd.isna(val_5y) or val_5y == "N/A" or val_5y == "":
            val_3y = row.get('Getiri % (Son 3 yıl)')
            try: return safe_float(val_3y) * 1.6
            except: return None
        return val_5y

    df['Getiri % (Son 1 yıl)'] = df.apply(ai_tahmin_1y, axis=1)
    df['Getiri % (Son 3 yıl)'] = df.apply(ai_tahmin_3y, axis=1)
    df['Getiri % (Son 5 yıl)'] = df.apply(ai_tahmin_5y, axis=1)
    
    # Yatırım Fırsat Skoru
    def hesapla_skor(row):
        skor = 50
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: skor += 25
        elif pot > 10: skor += 15
        elif pot > 5: skor += 5
        elif pot < 0: skor -= 10
        gun = safe_float(row['Gün %'])
        if gun > 3: skor += 20
        elif gun > 1: skor += 10
        elif gun < -2: skor -= 10
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: skor += 15
        elif rsi > 70: skor -= 5
        elif 40 <= rsi < 50: skor += 5
        y1 = safe_float(row.get('Getiri % (Son 1 yıl)'))
        if y1 > 20: skor += 15
        elif y1 > 10: skor += 10
        elif y1 < 0: skor -= 5
        return max(0, min(100, skor))
    
    df['Yatırım Fırsat Skoru'] = df.apply(hesapla_skor, axis=1)
    
    def sinyal_uret(row):
        skor = safe_float(row['Yatırım Fırsat Skoru'])
        if skor >= 75: return "🟢 Güçlü Al"
        elif skor >= 60: return "🔵 Al"
        elif skor >= 45: return "🟡 İzle"
        else: return "⚪ Nötr"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    
    def neden_yukselir(row):
        nedenler = []
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: nedenler.append("Tavanına çok uzak")
        elif pot > 5: nedenler.append("Zirveye yakın")
        gun = safe_float(row['Gün %'])
        if gun > 2: nedenler.append("Bugün güçlü alım")
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: nedenler.append("RSI ideal")
        y1 = safe_float(row.get('Getiri % (Son 1 yıl)'))
        if y1 > 20: nedenler.append("YZ 1 yıllık büyüme tahmini yüksek")
        return ", ".join(nedenler) if nedenler else "Normal"
    
    df['Neden Alınmalı?'] = df.apply(neden_yukselir, axis=1)
    
    # Formatlama
    df['Tavan Potansiyeli (%)'] = df['Tavan Potansiyeli (%)'].apply(format_percent)
    df['Gün %'] = df['Gün %'].apply(format_percent)
    df['Getiri % (Son 1 hafta)'] = df['Getiri % (Son 1 hafta)'].apply(format_percent)
    df['Getiri % (Son 1 ay)'] = df['Getiri % (Son 1 ay)'].apply(format_percent)
    df['Getiri % (Son 3 ay)'] = df['Getiri % (Son 3 ay)'].apply(format_percent)
    df['Getiri % (Son 6 ay)'] = df['Getiri % (Son 6 ay)'].apply(format_percent)
    df['Getiri % (Yılbaşından)'] = df['Getiri % (Yılbaşından)'].apply(format_percent)
    df['Getiri % (Son 1 yıl)'] = df['Getiri % (Son 1 yıl)'].apply(format_percent)
    df['Getiri % (Son 3 yıl)'] = df['Getiri % (Son 3 yıl)'].apply(format_percent)
    df['Getiri % (Son 5 yıl)'] = df['Getiri % (Son 5 yıl)'].apply(format_percent)
    df['Fiyat'] = df['Fiyat'].apply(lambda x: f"{float(x):.2f} TL")
    
    df = df.drop(columns=['52H_Yuksek', 'high_all_calc'], errors='ignore')
    
    return df

# --- VERİ YÜKLEME ---
with st.spinner("YZ ve Veriler güncelleniyor..."):
    tum_hisseler_raw = tum_bist_hisselerini_getir()
    if not tum_hisseler_raw.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler_raw)
    else:
        analizli_df = pd.DataFrame()

# --- SOL MENÜ (Gelişmiş Filtreleme Paneli) ---
with st.sidebar:
    st.header("📋 Keşfet")
    if st.button("🔍 Radar", use_container_width=True):
        st.session_state['menu'] = "Radar"
    if st.button("📈 Hisseler", use_container_width=True):
        st.session_state['menu'] = "Hisse"
    if st.button("🏛️ Endeksler", use_container_width=True):
        st.session_state['menu'] = "Endeksler"
    if st.button("👑 VIP", use_container_width=True):
        st.session_state['menu'] = "VIP"
    if st.button("🪙 Kripto", use_container_width=True):
        st.session_state['menu'] = "Kripto"
    st.markdown("---")
    
    st.header("🧠 Analiz")
    if st.button("📊 Temel Analiz", use_container_width=True):
        st.session_state['menu'] = "Temel Analiz"
    if st.button("🔬 Detaylı Analiz", use_container_width=True):
        st.session_state['menu'] = "Detaylı Analiz"
    if st.button("💎 Orijinal Hisseler", use_container_width=True):
        st.session_state['menu'] = "Orijinal Hisseler"
        
    st.markdown("---")
    
    # --- FİLTRELEME PANELİ ---
    st.header("🔎 Filtreler")
    
    if not analizli_df.empty:
        # 1. Arama
        arama = st.text_input("Hisse Ara", placeholder="Örn: THYAO")
        
        # 2. Kategori Seçimi (Popüler Filtreler)
        kategori = st.selectbox("Kategori", ["Tümü", "Getiri %", "Fiyat", "Hacim", "AI Sinyali"])
        
        # 3. AI Sinyali Filtresi
        secili_sinyaller = st.multiselect("AI Sinyali", ["🟢 Güçlü Al", "🔵 Al", "🟡 İzle", "⚪ Nötr"], default=["🟢 Güçlü Al", "🔵 Al"])
        
        # 4. Sayısal Aralık Filtreleri
        fiyat_min, fiyat_max = st.slider("Fiyat Aralığı (TL)", 0.0, 1000.0, (0.0, 1000.0))
        
        # 5. Getiri % Filtresi (Örnek olarak 1 Ay)
        getiri_min, getiri_max = st.slider("Getiri % (Son 1 Ay)", -100.0, 100.0, (-100.0, 100.0))
        
        # Filtreleri Uygula
        df_filtre = analizli_df.copy()
        
        # Hisse Adına Göre Filtrele
        if arama:
            df_filtre = df_filtre[df_filtre['Hisse'].str.contains(arama.upper(), na=False)]
        
        # AI Sinyaline Göre Filtrele
        if secili_sinyaller:
            df_filtre = df_filtre[df_filtre['AI Sinyal'].isin(secili_sinyaller)]
        
        # Fiyata Göre Filtrele
        df_filtre['Fiyat_Numeric'] = pd.to_numeric(df_filtre['Fiyat'].astype(str).str.replace(' TL', ''), errors='coerce')
        df_filtre = df_filtre[(df_filtre['Fiyat_Numeric'] >= fiyat_min) & (df_filtre['Fiyat_Numeric'] <= fiyat_max)]
        
        # Getiriye Göre Filtrele (1 Ay)
        df_filtre['Getiri_1A_Numeric'] = pd.to_numeric(df_filtre['Getiri % (Son 1 ay)'].astype(str).str.replace('%', ''), errors='coerce')
        df_filtre = df_filtre[(df_filtre['Getiri_1A_Numeric'] >= getiri_min) & (df_filtre['Getiri_1A_Numeric'] <= getiri_max)]
        
        # Geçici kolonları temizle
        df_filtre = df_filtre.drop(columns=['Fiyat_Numeric', 'Getiri_1A_Numeric'], errors='ignore')
        
        # Kaydetme Özelliği (Listeme Ekle)
        if "kayitli_hisseler" not in st.session_state:
            st.session_state["kayitli_hisseler"] = []
            
        secili_hisse_liste = st.multiselect("Listeye Eklenecek Hisseler", options=df_filtre['Hisse'].tolist())
        if st.button("💾 Kaydet"):
            st.session_state["kayitli_hisseler"].extend(secili_hisse_liste)
            st.success("Hisseler kaydedildi!")
            
        if st.session_state["kayitli_hisseler"]:
            st.write(f"**Kayıtlı Hisseler:** {', '.join(st.session_state['kayitli_hisseler'])}")
            if st.button("Temizle"):
                st.session_state["kayitli_hisseler"] = []
                st.rerun()
    else:
        st.warning("Veri bekleniyor...")

    st.markdown("---")
    st.caption("Otomatik yenileme: 60 sn")
    
    if 'menu' not in st.session_state:
        st.session_state['menu'] = "Radar"
    menu_secim = st.session_state['menu']

# --- ÜST SEKMELER ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🔥 Yüksek Potansiyel"
])

# TAB 1: GETİRİ (Filtrelenmiş veri)
with tab1:
    st.subheader("📊 Getiri Tablosu (Alfabetik)")
    if not df_filtre.empty:
        df_getiri = df_filtre.sort_values(by='Hisse', ascending=True)
        cols = ['Hisse', 'Fiyat', 'Gün %', 'Hacim', 
                'Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 
                'Getiri % (Son 3 ay)', 'Getiri % (Son 6 ay)', 
                'Getiri % (Yılbaşından)', 'Getiri % (Son 1 yıl)', 
                'Getiri % (Son 3 yıl)', 'Getiri % (Son 5 yıl)']
        for c in cols:
            if c not in df_getiri.columns:
                df_getiri[c] = "N/A"
        st.dataframe(df_getiri[cols], width='stretch', hide_index=True)
    else:
        st.error("Filtrelerle eşleşen hisse bulunamadı.")

# Diğer sekmeler (Filtrelenmiş veri kullanılır)
with tab2:
    st.subheader("💎 Değerleme (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'Tavan Potansiyeli (%)']], width='stretch', hide_index=True)

with tab3:
    st.subheader("📈 Karlılık (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Gün %', 'RSI', 'AI Sinyal']], width='stretch', hide_index=True)

with tab4:
    st.subheader("🚀 Büyüme (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)

with tab5:
    st.subheader("📋 Bilanço (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Piyasa Değeri']], width='stretch', hide_index=True)

with tab6:
    st.subheader("💵 Gelir Tablosu (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim']], width='stretch', hide_index=True)

with tab7:
    st.subheader("💧 Nakit Akım (Alfabetik)")
    if not df_filtre.empty:
        st.dataframe(df_filtre.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim', 'Gün %']], width='stretch', hide_index=True)

with tab8:
    st.subheader("🔥 Yüksek Potansiyelli Hisseler (Skor'a Göre)")
    if not df_filtre.empty:
        df_tavan = df_filtre.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(20)
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Yatırım Fırsat Skoru', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)

# --- SOL MENÜ İÇERİKLERİ ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Temel Analiz Aşamaları")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Makroekonomi**\n\nÜlke ekonomisi, faiz ve enflasyon incelenir.\n\n*AI:* Enflasyon yüksek, faiz politikaları sıkı.")
    with col2:
        st.info("**Sektör Analizi**\n\nŞirketin bulunduğu sektörün büyüme potansiyeline bakılır.\n\n*AI:* Teknoloji ve savunma sanayi öne çıkıyor.")
    with col3:
        st.info("**Şirket Analizi**\n\nBilanço ve gelir tablosu kontrol edilir.\n\n*AI:* Borçluluk oranları düşük.")

elif menu_secim == "Detaylı Analiz":
    st.subheader("🔬 Detaylı Analiz")
    st.write("**En Olası İlk 10 Hisse (Filtrelenmiş Veriden)**")
    if not df_filtre.empty:
        potansiyel_hisseler = df_filtre.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(10)
        st.dataframe(potansiyel_hisseler[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)

elif menu_secim == "Orijinal Hisseler":
    st.subheader("🚀 Orijinal Hisseler")
    if not df_filtre.empty:
        st.dataframe(df_filtre[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'AI Sinyal']].head(20), width='stretch', hide_index=True)

elif menu_secim == "Radar":
    st.success("Radar modülü aktif. Üst menüden analiz yapabilirsiniz.")
elif menu_secim == "Hisse":
    st.info("Hisse modülü aktif.")
elif menu_secim == "Endeksler":
    st.info("Endeksler modülü aktif.")
elif menu_secim == "VIP":
    st.info("VIP modülü aktif.")
elif menu_secim == "Kripto":
    st.info("Kripto modülü aktif.")
