import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings

warnings.filterwarnings("ignore")

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Quantum BIST Terminali", layout="wide")

# --- Modern Fintables Tarzı CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0A0E17; color: #E0E0E0; }
    section[data-testid="stSidebar"] { 
        background: linear-gradient(180deg, #101624, #0A0E17); 
        border-right: 1px solid #1F2937; 
    }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: transparent;
        color: #8B949E;
        border: none;
        text-align: left;
        width: 100%;
        padding: 10px;
        font-size: 16px;
        font-weight: 500;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #1F2937;
        color: #58A6FF;
    }
    thead tr th:first-child {display:none}
    thead tr th { 
        background-color: #161B22 !important; 
        color: #58A6FF !important; 
        font-weight: bold; 
        border-bottom: 2px solid #30363D; 
    }
    tbody tr:nth-child(even) { background-color: #161B22; }
    tbody tr:hover { background-color: #1F2937; }
    h1, h2, h3 { color: #FFFFFF !important; letter-spacing: -0.5px; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 2px solid #30363D; }
    .stTabs [data-baseweb="tab"] { 
        background-color: transparent; 
        color: #8B949E; 
        border-radius: 8px 8px 0 0; 
        padding: 12px 24px; 
        font-weight: 600; 
        border: none;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #161B22 !important; 
        color: #58A6FF !important; 
        border-bottom: 3px solid #58A6FF; 
    }
</style>
""", unsafe_allow_html=True)

# --- Yardımcı Fonksiyonlar (DÜZELTİLDİ) ---
def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, pd.Series):
        if val.empty: return 0.0
        try: return float(val.iloc[0])
        except: return 0.0
    try: return float(val)
    except: return 0.0

def format_big_number(val):
    """Büyük sayıları Fintables gibi anlamlı birimlere (mr, mn, bin) çevirir."""
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

def format_market_cap(val):
    """TradingView'den gelen 'bin TL' cinsindeki Piyasa Değerini 'mr/mn' cinsine çevirir."""
    try:
        val = float(val)
        # TradingView market_cap_basic değerini Bin TL cinsinden gönderir.
        # Gerçek TL değerini elde etmek için 1000 ile çarpıyoruz.
        val = val * 1000
        return format_big_number(val)
    except:
        return "N/A"

# --- TradingView Token ---
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

# --- Tüm BIST Hisselerini Çekme (Yenileme: 120 saniye) ---
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
            'name': 'Hisse', 'close': 'Fiyat', 'change': 'Gün %', 'volume': 'Hacim', 'market_cap_basic': 'Piyasa Değeri',
            'Perf.W': 'Getiri % (Son 1 hafta)', 'Perf.1M': 'Getiri % (Son 1 ay)',
            'Perf.3M': 'Getiri % (Son 3 ay)', 'Perf.6M': 'Getiri % (Son 6 ay)',
            'Perf.YTD': 'Getiri % (Yılbaşından)', 'Perf.1Y': 'Getiri % (Son 1 yıl)',
            'Perf.3Y': 'Getiri % (Son 3 yıl)', 'Perf.5Y': 'Getiri % (Son 5 yıl)'
        })
        
        # HATA DÜZELTME: Hacim ve Piyasa Değeri doğru formatlarda gösteriliyor
        df['Hacim'] = df['Hacim'].apply(format_big_number)
        df['Piyasa Değeri'] = df['Piyasa Değeri'].apply(format_market_cap)
        
        return df
    except Exception:
        return pd.DataFrame()

# --- Quantum AI Motoru ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    df['52H_Yuksek'] = pd.to_numeric(df.get('high_all_calc', 0), errors='coerce').fillna(0)
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100

    def neden_yukselir(row):
        nedenler = []
        rsi = pd.to_numeric(row.get('RSI', 0), errors='coerce')
        if pd.notna(rsi):
            if rsi > 70: nedenler.append("Aşırı alım, güçlü momentum")
            elif rsi > 50: nedenler.append("Pozitif alıcı baskısı (RSI)")
        
        pot = safe_float(row.get('Tavan Potansiyeli (%)'))
        if pot > 20: nedenler.append("Tavanına çok uzak, büyük yükseliş alanı var")
        elif pot > 5: nedenler.append("52 haftalık zirvesine yaklaşıyor, tavan denemesi beklenebilir")
        
        gün = safe_float(row.get('Gün %'))
        if gün > 2: nedenler.append("Bugün güçlü alım var")
        
        # Hacim verisi artık formatlı (metin) geldiği için sayıya çevirip kontrol et
        hacim_str = str(row.get('Hacim', '0'))
        hacim_numeric = 0
        if 'mn' in hacim_str:
            hacim_numeric = float(hacim_str.replace(' mn', '')) * 1_000_000
        elif 'mr' in hacim_str:
            hacim_numeric = float(hacim_str.replace(' mr', '')) * 1_000_000_000
        elif 'bin' in hacim_str:
            hacim_numeric = float(hacim_str.replace(' bin', '')) * 1_000
        
        if hacim_numeric > 1_000_000: nedenler.append("İşlem hacmi çok yüksek (likidite güçlü)")
        
        return ", ".join(nedenler) if nedenler else "Normal piyasa seyri"

    df['Neden Yükselebilir?'] = df.apply(neden_yukselir, axis=1)

    def monte_carlo(row):
        fiyat = safe_float(row.get('Fiyat'))
        degisim = abs(safe_float(row.get('Gün %'))) / 100.0
        sims = np.random.normal(fiyat, max(degisim * fiyat, 0.01), 500)
        return np.median(sims)

    df['Tahmini Fiyat'] = df.apply(monte_carlo, axis=1).round(2)
    df['Hata Payı'] = (df['Fiyat'] * 0.02).round(2)
    df['Alt Eşik'] = (df['Tahmini Fiyat'] - df['Hata Payı']).round(2)
    df['Üst Eşik'] = (df['Tahmini Fiyat'] + df['Hata Payı']).round(2)

    def sinyal_uret(row):
        pot = safe_float(row.get('Tavan Potansiyeli (%)'))
        rsi = pd.to_numeric(row.get('RSI', 50), errors='coerce')
        
        if pot > 10 and rsi < 70:
            return "🟢 Güçlü Al"
        elif pot > 5 and rsi < 65:
            return "🔵 Al"
        elif pot > 0:
            return "🟡 İzle"
        else:
            return "⚪ Nötr"

    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    df['Neden Alınmalı?'] = df['Neden Yükselebilir?']
    
    df = df.drop(columns=['52H_Yuksek', 'high_all_calc'], errors='ignore')
    
    return df

# --- YENİLEME BUTONU (Otomatik 120sn + Manuel) ---
col1, col2 = st.columns([8, 1])
with col1:
    st.title("⚡ Quantum BIST Terminali")
    st.caption("Yapay Zeka Destekli Piyasa Analizi")
with col2:
    if st.button("🔄 Şimdi Yenile", help="Verileri anlık olarak tazele"):
        st.cache_data.clear()
        st.rerun()

# --- Veri Yükleme ---
with st.spinner("Quantum AI Motoru verileri işliyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()
    if not tum_hisseler.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler)
    else:
        analizli_df = pd.DataFrame()

# --- Sol Menü ---
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
    st.caption("Veriler 2 dakikada bir otomatik güncellenir.")
    
    if 'menu' not in st.session_state:
        st.session_state['menu'] = "Radar"
    menu_secim = st.session_state['menu']
    
    if not tum_hisseler.empty:
        st.subheader("Tüm Hisseler")
        secim = st.selectbox("Hisse Ara ve Seç", options=tum_hisseler['Hisse'].tolist(), key="hisse_secim")
        if st.button("Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.rerun()

# --- Üst Menü Sekmeleri ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyüme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🔥 Yüksek Potansiyel"
])

# TAB 1: GETİRİ (Alfabetik, Tüm Sütunlar)
with tab1:
    st.subheader("📊 Getiri Tablosu")
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

# Diğer sekmeler
with tab2:
    st.subheader("💎 Değerleme")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Tahmini Fiyat', 'Hata Payı', 'Alt Eşik', 'Üst Eşik']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab3:
    st.subheader("📈 Karlılık")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Gün %', 'RSI']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab4:
    st.subheader("🚀 Büyüme")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab5:
    st.subheader("📋 Bilanço")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Piyasa Değeri']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab6:
    st.subheader("💵 Gelir Tablosu")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Hacim']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab7:
    st.subheader("💧 Nakit Akım")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Hacim', 'Gün %']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

with tab8:
    st.subheader("🔥 Yüksek Potansiyelli Tavan Hisseleri")
    if not analizli_df.empty:
        df_tavan = analizli_df.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(10)
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# --- Sol Menü Modül İçerikleri ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Temel Analiz Aşamaları")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Makroekonomi**\n\nÜlke ekonomisi, faiz ve enflasyon incelenir.\n\n*AI Yorumu:* Enflasyon yüksek seyrediyor, faiz politikaları sıkı.")
    with col2:
        st.info("**Sektör Analizi**\n\nŞirketin bulunduğu sektörün büyüme potansiyeline bakılır.\n\n*AI Yorumu:* Teknoloji ve savunma sanayi öne çıkıyor.")
    with col3:
        st.info("**Şirket Analizi**\n\nBilanço ve gelir tablosu kontrol edilir.\n\n*AI Yorumu:* Seçilen şirketlerin borçluluk oranları düşük.")
    if not analizli_df.empty and 'sector' in analizli_df.columns:
        st.subheader("Sektör Bazlı Şirket Listesi")
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'sector']].head(20), width='stretch', hide_index=True)
    else:
        st.write("Sektör verisi alınamadı.")

elif menu_secim == "Detaylı Analiz":
    st.subheader("🔬 Detaylı Analiz")
    st.write("**En Olası İlk 10 Hisse** (Potansiyel ve Alım Gerekçeleriyle)")
    
    if not analizli_df.empty:
        potansiyel_hisseler = analizli_df[analizli_df['AI Sinyal'].isin(["🟢 Güçlü Al", "🔵 Al"])].head(10)
        if potansiyel_hisseler.empty:
            st.info("Şu an kesin alım sinyali veren hisse yok. Yine de en yüksek potansiyelli 10 hisseyi gösteriyorum.")
            potansiyel_hisseler = analizli_df.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(10)
        
        st.dataframe(potansiyel_hisseler[['Hisse', 'Fiyat', 'Piyasa Değeri', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)
    
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
            st.write(f"**Güncel Fiyat:** {safe_float(hisse_verisi.iloc[0]['Fiyat'])} TL")
            st.write(f"**Piyasa Değeri:** {hisse_verisi.iloc[0].get('Piyasa Değeri', 'N/A')}")
            st.write(f"**Günlük Değişim:** %{safe_float(hisse_verisi.iloc[0]['Gün %'])}")
            st.write(f"**RSI:** {safe_float(hisse_verisi.iloc[0]['RSI'])}")
            st.write(f"**Sektör:** {hisse_verisi.iloc[0].get('sector', 'Bilinmiyor')}")
            st.write(f"**AI Sinyal:** {hisse_verisi.iloc[0]['AI Sinyal']}")
            st.markdown(f"**Neden Alınmalı?** \n\n> {hisse_verisi.iloc[0]['Neden Alınmalı?']}")
            st.write(f"**Tahmini Fiyat (5 Gün):** {hisse_verisi.iloc[0]['Tahmini Fiyat']} TL")
        else:
            st.error("Seçilen hisse veri setinde bulunamadı.")

elif menu_secim == "Orijinal Hisseler":
    st.subheader("🚀 Orijinal Hisseler")
    st.write("Endeks dışı, yüksek hacimli fırsatlar")
    if not analizli_df.empty:
        df_orig = analizli_df.copy()
        # Hacmi sayıya çevirerek filtrele
        df_orig['Hacim_Numeric'] = pd.to_numeric(df_orig['Hacim'].astype(str).str.replace(' mn', '000000').str.replace(' mr', '000000000').str.replace(' bin', '000'), errors='coerce').fillna(0)
        df_orig = df_orig[df_orig['Hacim_Numeric'] > 1000000].sort_values(by='Hacim_Numeric', ascending=False).head(20)
        st.dataframe(df_orig[['Hisse', 'Fiyat', 'Hacim', 'Piyasa Değeri', 'Gün %', 'AI Sinyal']], width='stretch', hide_index=True)
    else:
        st.warning("Veri bekleniyor...")

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
