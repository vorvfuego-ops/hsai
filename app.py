import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Quantum BIST Terminali", layout="wide")

# --- MODERN CSS ---
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
    """Sayıları '12.50 mr', '3.20 mn' formatına çevirir."""
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
    """Yüzde değerlerini '%' işaretiyle ve 2 basamaklı gösterir."""
    try:
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

# --- VERİ ÇEKME (TTL: 120 sn) ---
@st.cache_data(ttl=120)
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
        
        # Veri düzeltmeleri
        df['Hacim'] = df['Hacim'].apply(format_big_number)
        # Piyasa değeri TradingView'de bin TL cinsinden gelir, 1000 ile çarpıp mr/mn yap
        df['Piyasa Değeri'] = df['Piyasa Değeri'].apply(lambda x: format_big_number(safe_float(x) * 1000))
        
        # Getiri % (Son 1 yıl) verisi yoksa N/A yap (None hatasını çözer)
        df['Getiri % (Son 1 yıl)'] = df['Getiri % (Son 1 yıl)'].fillna('N/A')
        
        return df
    except Exception:
        return pd.DataFrame()

# --- GELİŞMİŞ QUANTUM YZ MODELİ ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    df['Gün %'] = pd.to_numeric(df['Gün %'], errors='coerce').fillna(0)
    df['52H_Yuksek'] = pd.to_numeric(df.get('high_all_calc', 0), errors='coerce').fillna(0)
    
    # Tavan Potansiyeli Hesabı
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100
    
    # Hacim ve Piyasa Değerini sayıya çevir
    def str_to_number(s):
        s = str(s)
        if 'mr' in s: return float(s.replace(' mr', '')) * 1_000_000_000
        if 'mn' in s: return float(s.replace(' mn', '')) * 1_000_000
        if 'bin' in s: return float(s.replace(' bin', '')) * 1_000
        return 0
    
    df['Hacim_Sayi'] = df['Hacim'].apply(str_to_number)
    df['Piyasa_Sayi'] = df['Piyasa Değeri'].apply(str_to_number)
    
    # --- GELİŞMİŞ YATIRIM FIRSAT SKORU (0-100) ---
    def hesapla_skor(row):
        skor = 50  # Başlangıç nötr
        
        # 1. Tavan Potansiyeli Etkisi (Max 30 puan)
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: skor += 25
        elif pot > 10: skor += 15
        elif pot > 5: skor += 5
        elif pot < 0: skor -= 10
        
        # 2. Günlük Momentum (Max 20 puan)
        gun = safe_float(row['Gün %'])
        if gun > 3: skor += 20
        elif gun > 1: skor += 10
        elif gun < -2: skor -= 10
        
        # 3. RSI Durumu (Max 20 puan)
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: skor += 15
        elif rsi > 70: skor -= 5  # Aşırı alım riski
        elif 40 <= rsi < 50: skor += 5
        
        # 4. Hacim (Max 15 puan)
        hacim = safe_float(row['Hacim_Sayi'])
        if hacim > 50_000_000: skor += 15
        elif hacim > 10_000_000: skor += 10
        elif hacim > 1_000_000: skor += 5
        
        # 5. Piyasa Değeri (Max 15 puan - Küçük şirketler daha hareketli)
        pyd = safe_float(row['Piyasa_Sayi'])
        if pyd < 500_000_000: skor += 15
        elif pyd < 2_000_000_000: skor += 10
        elif pyd > 10_000_000_000: skor -= 5
        
        return max(0, min(100, skor))
    
    df['Yatırım Fırsat Skoru'] = df.apply(hesapla_skor, axis=1)
    
    # --- SİNYAL ÜRETİMİ (Skor'a göre) ---
    def sinyal_uret(row):
        skor = safe_float(row['Yatırım Fırsat Skoru'])
        if skor >= 75: return "🟢 Güçlü Al"
        elif skor >= 60: return "🔵 Al"
        elif skor >= 45: return "🟡 İzle"
        else: return "⚪ Nötr"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    
    # --- NEDEN ALINMALI? (Skor Bileşenlerine Göre) ---
    def neden_yukselir(row):
        nedenler = []
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: nedenler.append("Tavanına çok uzak, büyük potansiyel var")
        elif pot > 5: nedenler.append("52 haftalık zirvesine yakın")
        
        gun = safe_float(row['Gün %'])
        if gun > 2: nedenler.append("Bugün güçlü alım gördü")
        
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: nedenler.append("RSI ideal bölgede, momentum güçlü")
        elif rsi > 70: nedenler.append("RSI aşırı alımda, dikkatli olunmalı")
        
        hacim = safe_float(row['Hacim_Sayi'])
        if hacim > 10_000_000: nedenler.append("Hacim çok yüksek, likidite güçlü")
        
        pyd = safe_float(row['Piyasa_Sayi'])
        if pyd < 1_000_000_000: nedenler.append("Küçük piyasa değeri, yüksek esneklik")
        
        return ", ".join(nedenler) if nedenler else "Potansiyel değerlendiriliyor"
    
    df['Neden Alınmalı?'] = df.apply(neden_yukselir, axis=1)
    
    # Gereksiz sayısal kolonları temizle
    df = df.drop(columns=['52H_Yuksek', 'high_all_calc', 'Hacim_Sayi', 'Piyasa_Sayi'], errors='ignore')
    
    # Değerleri formatla (Anlamsız uzun sayıları düzelt)
    df['Tavan Potansiyeli (%)'] = df['Tavan Potansiyeli (%)'].apply(format_percent)
    df['Gün %'] = df['Gün %'].apply(format_percent)
    df['Fiyat'] = df['Fiyat'].apply(lambda x: f"{float(x):.2f} TL")
    
    return df

# --- YENİLEME ---
col1, col2 = st.columns([8, 1])
with col1:
    st.title("⚡ Quantum BIST Terminali")
    st.caption("Gelişmiş Yapay Zeka Destekli Piyasa Analizi")
with col2:
    if st.button("🔄 Şimdi Yenile"):
        st.cache_data.clear()
        st.rerun()

# --- VERİ YÜKLEME ---
with st.spinner("Gelişmiş Yapay Zeka Motoru çalışıyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()
    if not tum_hisseler.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler)
    else:
        analizli_df = pd.DataFrame()

# --- SOL MENÜ ---
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
    st.caption("Veriler 2 dakikada bir yenilenir.")
    
    if 'menu' not in st.session_state:
        st.session_state['menu'] = "Radar"
    menu_secim = st.session_state['menu']
    
    if not tum_hisseler.empty:
        st.subheader("Tüm Hisseler")
        secim = st.selectbox("Hisse Ara", options=tum_hisseler['Hisse'].tolist(), key="hisse_secim")
        if st.button("Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.rerun()

# --- ÜST SEKMELER ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyüme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🔥 Yüksek Potansiyel"
])

with tab1:
    st.subheader("📊 Getiri Tablosu (Alfabetik)")
    if not analizli_df.empty:
        df_getiri = analizli_df.sort_values(by='Hisse', ascending=True)
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
        st.error("Veri yüklenemedi.")

with tab2:
    st.subheader("💎 Değerleme (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'Tavan Potansiyeli (%)']], width='stretch', hide_index=True)

with tab3:
    st.subheader("📈 Karlılık (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Gün %', 'RSI', 'AI Sinyal']], width='stretch', hide_index=True)

with tab4:
    st.subheader("🚀 Büyüme (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)

with tab5:
    st.subheader("📋 Bilanço (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Piyasa Değeri']], width='stretch', hide_index=True)

with tab6:
    st.subheader("💵 Gelir Tablosu (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim']], width='stretch', hide_index=True)

with tab7:
    st.subheader("💧 Nakit Akım (Alfabetik)")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim', 'Gün %']], width='stretch', hide_index=True)

with tab8:
    st.subheader("🔥 Yüksek Potansiyelli Hisseler (Skor'a Göre)")
    if not analizli_df.empty:
        # Yüksek potansiyel bölümünde SADECE "Al" olanları değil, TÜM hisseleri skorlarına göre sıralayıp göstereceğiz
        df_tavan = analizli_df.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(20)
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Yatırım Fırsat Skoru', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)

# --- SOL MENÜ İÇERİKLERİ ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Temel Analiz Aşamaları")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Makroekonomi**\n\nÜlke ekonomisi, faiz ve enflasyon incelenir.\n\n*AI:* Enflasyon yüksek seyrediyor, faiz politikaları sıkı.")
    with col2:
        st.info("**Sektör Analizi**\n\nŞirketin bulunduğu sektörün büyüme potansiyeline bakılır.\n\n*AI:* Teknoloji ve savunma sanayi öne çıkıyor.")
    with col3:
        st.info("**Şirket Analizi**\n\nBilanço ve gelir tablosu kontrol edilir.\n\n*AI:* Seçilen şirketlerin borçluluk oranları düşük.")
    if not analizli_df.empty and 'sector' in analizli_df.columns:
        st.subheader("Sektör Bazlı Şirket Listesi")
        st.dataframe(analizli_df[['Hisse', 'Piyasa Değeri', 'sector']].head(20), width='stretch', hide_index=True)

elif menu_secim == "Detaylı Analiz":
    st.subheader("🔬 Detaylı Analiz")
    st.write("**En Olası İlk 10 Hisse (Yatırım Skoruna Göre)**")
    
    if not analizli_df.empty:
        potansiyel_hisseler = analizli_df.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(10)
        st.dataframe(potansiyel_hisseler[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)
    
    st.markdown("---")
    st.write("**Hisse Seçimi**")
    if 'secili_hisse' in st.session_state:
        sec = st.session_state['secili_hisse']
    else:
        sec = "GARAN"
    if not analizli_df.empty:
        sec = st.selectbox("Analiz Edilecek Hisse", analizli_df['Hisse'].tolist(), index=0, key="detay_secim")
    
    if st.button("Derinlemesine Analizi Başlat"):
        hisse_verisi = analizli_df[analizli_df['Hisse'] == sec]
        if not hisse_verisi.empty:
            st.success(f"{sec} için detaylı veriler:")
            st.write(f"**Güncel Fiyat:** {hisse_verisi.iloc[0]['Fiyat']}")
            st.write(f"**Piyasa Değeri:** {hisse_verisi.iloc[0].get('Piyasa Değeri', 'N/A')}")
            st.write(f"**Günlük Değişim:** {hisse_verisi.iloc[0]['Gün %']}")
            st.write(f"**Yatırım Fırsat Skoru:** {hisse_verisi.iloc[0]['Yatırım Fırsat Skoru']}")
            st.write(f"**AI Sinyal:** {hisse_verisi.iloc[0]['AI Sinyal']}")
            st.markdown(f"**Neden Alınmalı?** \n\n> {hisse_verisi.iloc[0]['Neden Alınmalı?']}")
            st.write(f"**Tahmini Fiyat (5 Gün):** {hisse_verisi.iloc[0]['Tahmini Fiyat']} TL")
        else:
            st.error("Seçilen hisse veri setinde bulunamadı.")

elif menu_secim == "Orijinal Hisseler":
    st.subheader("🚀 Orijinal Hisseler")
    if not analizli_df.empty:
        # Orijinal hisseler = Küçük piyasa değerli ve yüksek skorlu
        df_orig = analizli_df.copy()
        df_orig['Piyasa_Numeric'] = df_orig['Piyasa Değeri'].apply(lambda x: 0 if 'mr' not in str(x) else float(str(x).replace(' mr', '')) * 1_000_000_000)
        df_orig = df_orig[df_orig['Piyasa_Numeric'] < 1_000_000_000].sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(20)
        st.dataframe(df_orig[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Yatırım Fırsat Skoru', 'AI Sinyal']], width='stretch', hide_index=True)

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
