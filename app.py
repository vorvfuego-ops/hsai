import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="BIST Pro AI Terminali", layout="wide")

# --- FINTABLES STİLİ (CSS) ---
st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    section[data-testid="stSidebar"] { background-color: #1E1E1E; border-right: 1px solid #333; }
    section[data-testid="stSidebar"] .stRadio label { color: #FFFFFF; }
    section[data-testid="stSidebar"] .stButton button { background-color: transparent; color: #FFFFFF; border: none; text-align: left; width: 100%; }
    section[data-testid="stSidebar"] .stButton button:hover { background-color: #2C2C2C; color: #FF9900; }
    thead tr th:first-child {display:none}
    thead tr th { background-color: #2C2C2C !important; color: #FF9900 !important; font-weight: bold; }
    tbody tr:nth-child(even) { background-color: #1E1E1E; }
    tbody tr:hover { background-color: #333333; }
    h1, h2, h3 { color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

# --- GÜVENLİ VERİ DÖNÜŞTÜRÜCÜ ---
def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, pd.Series):
        if val.empty: return 0.0
        try: return float(val.iloc[0])
        except: return 0.0
    try: return float(val)
    except: return 0.0

# --- TRADINGVIEW TOKEN DOĞRULAMA ---
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

# --- TÜM BIST HİSSELERİNİ TRADINGVIEW'DEN ÇEKME (yfinance YOK) ---
@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        
        # Fintables'taki tüm sütunları TradingView'den çekiyoruz
        q = Query().set_markets('turkey').select(
            'name', 
            'close', 
            'change', 
            'volume', 
            'market_cap_basic', 
            'sector',
            'high_all_calc',       # 52 Haftalık Yüksek
            'RSI',
            'Perf.W',              # Son 1 Hafta
            'Perf.1M',             # Son 1 Ay
            'Perf.3M',             # Son 3 Ay
            'Perf.6M',             # Son 6 Ay
            'Perf.YTD'             # Yılbaşından Bugüne
        ).order_by('volume', ascending=False).limit(500)
        
        try:
            total, df = q.get_scanner_data(auth_token=token)
        except:
            total, df = q.get_scanner_data()
        
        # Veri yoksa boş döndür
        if df.empty:
            return pd.DataFrame()
            
        # Sütunları Fintables isimlerine çevir
        df = df.rename(columns={
            'name': 'Hisse',
            'close': 'Fiyat',
            'change': 'Gün %',
            'volume': 'Hacim',
            'Perf.W': 'Getiri % (Son 1 hafta)',
            'Perf.1M': 'Getiri % (Son 1 ay)',
            'Perf.3M': 'Getiri % (Son 3 ay)',
            'Perf.6M': 'Getiri % (Son 6 ay)',
            'Perf.YTD': 'Getiri % (Yılbaşından)'
        })
        
        # Eksik kolonları tamamla (Bazı hisselerde 1 yıl verisi olmayabilir)
        if 'Getiri % (Son 1 yıl)' not in df.columns:
            df['Getiri % (Son 1 yıl)'] = "N/A"
            
        return df
    except Exception as e:
        st.error(f"TradingView verileri çekilemedi: {e}")
        return pd.DataFrame()

# --- YAPAY ZEKA MOTORU (Hesaplamalar) ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    # 52 Haftalık Yüksek ve Tavan Potansiyeli
    # TradingView "high_all_calc" verisini sağlar, yfinance'e gerek yok!
    df['52H_Yuksek'] = pd.to_numeric(df.get('high_all_calc', 0), errors='coerce').fillna(0)
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    
    # Tavan Potansiyeli Hesabı
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100
    
    # Neden Yükselebilir? (AI Yorumu)
    def neden_yukselir(row):
        nedenler = []
        rsi = pd.to_numeric(row.get('RSI', 0), errors='coerce')
        if pd.notna(rsi):
            if rsi > 70: nedenler.append("Aşırı alım, güçlü momentum")
            elif rsi > 50: nedenler.append("Pozitif alıcı baskısı")
        
        pot = safe_float(row.get('Tavan Potansiyeli (%)'))
        if pot > 20: nedenler.append("Tavanına çok uzak")
        elif pot > 5: nedenler.append("52 haftalık zirvesine yakın")
        
        gün = safe_float(row.get('Gün %'))
        if gün > 2: nedenler.append("Bugün güçlü alım")
        
        hacim = safe_float(row.get('Hacim'))
        if hacim > 1000000: nedenler.append("Likidite çok yüksek")
        
        return ", ".join(nedenler) if nedenler else "Normal piyasa seyri"
    
    df['Neden Yükselebilir?'] = df.apply(neden_yukselir, axis=1)
    
    # Monte Carlo AI Sinyali (Fiyat Tahmini)
    def monte_carlo(row):
        fiyat = safe_float(row.get('Fiyat'))
        degisim = abs(safe_float(row.get('Gün %'))) / 100.0
        # Negatif standart sapmayı önle (abs kullan)
        sims = np.random.normal(fiyat, max(degisim * fiyat, 0.01), 200)
        return np.median(sims)
    
    df['Tahmini Fiyat'] = df.apply(monte_carlo, axis=1).round(2)
    df['Hata Payı'] = (df['Fiyat'] * 0.02).round(2)
    df['Alt Eşik'] = (df['Tahmini Fiyat'] - df['Hata Payı']).round(2)
    df['Üst Eşik'] = (df['Tahmini Fiyat'] + df['Hata Payı']).round(2)
    
    # AI Sinyalleri
    def sinyal_uret(row):
        if safe_float(row.get('Tavan Potansiyeli (%)')) > 10 and pd.to_numeric(row.get('RSI', 50), errors='coerce') < 70:
            return "🟢 AL"
        elif safe_float(row.get('Tavan Potansiyeli (%)')) > 0:
            return "🟡 TUT"
        else:
            return "🔴 SAT"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    
    # Temizlik: Geçici sütunları kaldır
    df = df.drop(columns=['52H_Yuksek', 'high_all_calc'], errors='ignore')
    
    return df

# --- VERİ YÜKLEME ---
with st.spinner("TradingView'den anlık veriler yükleniyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()
    
    if not tum_hisseler.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler)
    else:
        analizli_df = pd.DataFrame()

# --- ANA ARAYÜZ ---
st.title("📊 BIST Pro AI Terminali")
st.caption("Fintables menü yapısı + TradingView verileri + Yapay Zeka Motoru")

# --- SOL MENÜ ---
with st.sidebar:
    st.header("📋 Menü")
    menu_secim = st.radio(
        "Menü Seçin",
        ["Radar", "Hisse", "Endeksler", "VIP", "Kripto"],
        key="sidebar_menu"
    )
    st.markdown("---")
    st.caption("Veriler TradingView hesabınızla çekildi.")
    
    if not tum_hisseler.empty:
        st.subheader("Tüm Hisseler")
        secim = st.selectbox("Hisse Ara ve Seç", options=tum_hisseler['Hisse'].tolist(), key="hisse_secim")
        if st.button("Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.rerun()

# --- ÜST SEKMELER (Fintables Menü Düzeni) ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyüme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🚀 Yüksek Potansiyel"
])

# TAB 1: GETİRİ (Fintables'taki tablonun aynısı)
with tab1:
    st.subheader("📊 Getiri Tablosu")
    if not analizli_df.empty:
        # Sıralama: Günlük değişime göre
        df_getiri = analizli_df.sort_values(by='Gün %', ascending=False)
        st.dataframe(df_getiri[['Hisse', 'Fiyat', 'Gün %', 'Hacim', 'Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Son 6 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)
    else:
        st.error("Veri yüklenemedi. TradingView bağlantısını kontrol edin.")

# TAB 2: DEĞERLEME
with tab2:
    st.subheader("💎 Değerleme")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Tahmini Fiyat', 'Hata Payı', 'Alt Eşik', 'Üst Eşik']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 3: KARLILIK
with tab3:
    st.subheader("📈 Karlılık")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Gün %', 'RSI']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 4: BÜYÜME
with tab4:
    st.subheader("🚀 Büyüme")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 5: BİLANÇO
with tab5:
    st.subheader("📋 Bilanço")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 6: GELİR TABLOSU
with tab6:
    st.subheader("💵 Gelir Tablosu")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Hacim']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 7: NAKİT AKIM
with tab7:
    st.subheader("💧 Nakit Akım")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Hacim', 'Gün %']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

# TAB 8: YÜKSEK POTANSİYEL (Tavan Hisseleri)
with tab8:
    st.subheader("🔥 Yüksek Potansiyelli Tavan Hisseleri")
    if not analizli_df.empty:
        df_tavan = analizli_df.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(10)
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Yükselebilir?']], width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# --- PROFESYONEL ANALİZ (Grafik bölümü - yfinance kaldırıldığı için TradingView verisi ile gösterim yapılır) ---
st.markdown("---")
st.subheader("🧠 Profesyonel Analiz (TradingView Verileriyle)")

if 'secili_hisse' in st.session_state:
    sec = st.session_state['secili_hisse']
else:
    sec = "GARAN"

if not analizli_df.empty:
    sec = st.selectbox("Analiz Edilecek Hisse", analizli_df['Hisse'].tolist(), index=0, key="prof")

if st.button("Analizi Başlat"):
    # TradingView'den tek hissenin detaylı verilerini çek
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        q = Query().set_markets('turkey').select(
            'name', 'close', 'change', 'volume', 'RSI', 'sector', 'high_all_calc', 'Perf.W'
        )
        q = q.where(f"name={sec}")
        total, df_detay = q.get_scanner_data(auth_token=token)
        
        if not df_detay.empty:
            st.success(f"{sec} verileri güncel olarak çekildi.")
            st.write(f"**Güncel Fiyat:** {safe_float(df_detay.iloc[0]['close'])} TL")
            st.write(f"**Günlük Değişim:** %{safe_float(df_detay.iloc[0]['change'])}")
            st.write(f"**Sektör:** {df_detay.iloc[0]['sector']}")
            st.write(f"**RSI:** {safe_float(df_detay.iloc[0]['RSI'])}")
            st.write(f"**52 Haftalık Yüksek:** {safe_float(df_detay.iloc[0]['high_all_calc'])}")
        else:
            st.error("Veri bulunamadı.")
    except Exception as e:
        st.error(f"Analiz sırasında hata oluştu: {e}")
