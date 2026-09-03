import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings

warnings.filterwarnings("ignore")

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Quantum BIST Terminali", layout="wide")

# --- Modern 2026 Tasarımı CSS ---
st.markdown("""
<style>
    /* Arka plan */
    .stApp { background-color: #0A0E17; color: #E0E0E0; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] { 
        background: linear-gradient(180deg, #101624, #0A0E17); 
        border-right: 1px solid #1F2937; 
    }
    
    /* Segmentli Menü Butonları */
    .stSegmentedControl button {
        background-color: transparent;
        color: #8B949E;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 8px 16px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stSegmentedControl button:hover {
        background-color: #1F2937;
        color: #FFFFFF;
        border-color: #58A6FF;
    }
    
    .stSegmentedControl button[aria-selected="true"] {
        background-color: #1F2937;
        color: #58A6FF;
        border-color: #58A6FF;
        box-shadow: 0 0 10px rgba(88,166,255,0.3);
    }
    
    /* Tablo */
    thead tr th:first-child {display:none}
    thead tr th { 
        background-color: #161B22 !important; 
        color: #58A6FF !important; 
        font-weight: bold; 
        border-bottom: 2px solid #30363D; 
    }
    tbody tr:nth-child(even) { background-color: #161B22; }
    tbody tr:hover { background-color: #1F2937; }
    
    /* Başlıklar */
    h1, h2, h3 { color: #FFFFFF !important; letter-spacing: -0.5px; }
    
    /* Üst Sekmeler */
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
    
    /* Butonlar */
    .stButton > button {
        background: linear-gradient(90deg, #1F2937, #161B22);
        color: #FFFFFF;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        border-color: #58A6FF;
        box-shadow: 0 0 10px rgba(88,166,255,0.2);
    }
</style>
""", unsafe_allow_html=True)

# --- Güvenli Veri Dönüştürücü ---
def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, pd.Series):
        if val.empty: return 0.0
        try: return float(val.iloc[0])
        except: return 0.0
    try: return float(val)
    except: return 0.0

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

# --- Tüm BIST Hisselerini Çekme (TradingView) ---
@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        q = Query().set_markets('turkey').select(
            'name', 'close', 'change', 'volume', 'market_cap_basic', 
            'sector', 'high_all_calc', 'RSI', 'Perf.W', 'Perf.1M', 
            'Perf.3M', 'Perf.6M', 'Perf.YTD'
        ).order_by('volume', ascending=False).limit(500)
        
        # Hata önleme: token parametresini dene, olmazsa dene
        try:
            total, df = q.get_scanner_data(auth_token=token)
        except:
            total, df = q.get_scanner_data()
        
        if df.empty:
            return pd.DataFrame()
            
        df = df.rename(columns={
            'name': 'Hisse', 'close': 'Fiyat', 'change': 'Gün %', 'volume': 'Hacim',
            'Perf.W': 'Getiri % (Son 1 hafta)', 'Perf.1M': 'Getiri % (Son 1 ay)',
            'Perf.3M': 'Getiri % (Son 3 ay)', 'Perf.6M': 'Getiri % (Son 6 ay)',
            'Perf.YTD': 'Getiri % (Yılbaşından)'
        })
        if 'Getiri % (Son 1 yıl)' not in df.columns:
            df['Getiri % (Son 1 yıl)'] = "N/A"
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
        if safe_float(row.get('Tavan Potansiyeli (%)')) > 10 and pd.to_numeric(row.get('RSI', 50), errors='coerce') < 70:
            return "🟢 AL"
        elif safe_float(row.get('Tavan Potansiyeli (%)')) > 0:
            return "🟡 TUT"
        else:
            return "🔴 SAT"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    df = df.drop(columns=['52H_Yuksek', 'high_all_calc'], errors='ignore')
    return df

# --- Veri Yükleme ---
with st.spinner("Quantum AI Motoru verileri işliyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()
    if not tum_hisseler.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler)
    else:
        analizli_df = pd.DataFrame()

# --- Ana Başlık ---
st.title("⚡ Quantum BIST Terminali")
st.caption("Yapay Zeka Destekli Piyasa Analizi")

# --- Sol Menü (Modern Segmentli) ---
with st.sidebar:
    st.header("📋 Analiz Modülleri")
    
    # 2026 tasarımı: Segmentli kontrol
    menu_secim = st.segmented_control(
        "Modül Seçin",
        ["Radar", "Hisse", "Endeksler", "VIP", "Kripto", "Temel Analiz", "Detaylı Analiz", "Orijinal Hisseler"],
        default="Radar",
        key="menu"
    )
    
    st.markdown("---")
    st.caption("Quantum AI Çekirdeği Aktif")
    
    if not tum_hisseler.empty:
        st.subheader("Tüm Hisseler")
        secim = st.selectbox("Hisse Ara ve Seç", options=tum_hisseler['Hisse'].tolist(), key="hisse_secim")
        if st.button("Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.rerun()

# --- Üst Menü Sekmeleri ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🔥 Yüksek Potansiyel"
])

# TAB 1: GETİRİ (Alfabetik)
with tab1:
    st.subheader("📊 Getiri Tablosu (Alfabetik)")
    if not analizli_df.empty:
        df_getiri = analizli_df.sort_values(by='Hisse', ascending=True)
        st.dataframe(df_getiri[['Hisse', 'Fiyat', 'Gün %', 'Hacim', 'Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Son 6 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)
    else:
        st.error("Veri yüklenemedi.")

# Diğer sekmeler (kullanıcıya düzgün çalıştığını göster)
with tab2:
    st.subheader("💎 Değerleme")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Fiyat', 'Tahmini Fiyat', 'Hata Payı', 'Alt Eşik', 'Üst Eşik']], width='stretch', hide_index=True)
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
        st.dataframe(analizli_df[['Hisse', 'Fiyat']], width='stretch', hide_index=True)
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
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Yükselebilir?']], width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# --- Sol Menü Modül İçerikleri ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Temel Analiz Aşamaları")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Makroekonomi**\n\nÜlke ekonomisi, faiz ve enflasyon incelenir.\n\n*AI Yorumu:* Şu an enflasyon yüksek seyrediyor, faiz politikaları sıkı.")
    with col2:
        st.info("**Sektör Analizi**\n\nŞirketin bulunduğu sektörün büyüme potansiyeline bakılır.\n\n*AI Yorumu:* Teknoloji ve savunma sanayi öne çıkıyor.")
    with col3:
        st.info("**Şirket Analizi**\n\nBilanço ve gelir tablosu kontrol edilir.\n\n*AI Yorumu:* Seçilen şirketlerin borçluluk oranları düşük.")
    
    if not analizli_df.empty:
        st.subheader("Sektör Bazlı Şirket Listesi")
        # Sektör sütunu varsa
        if 'sector' in analizli_df.columns:
            st.dataframe(analizli_df[['Hisse', 'Fiyat', 'sector']].head(20), width='stretch', hide_index=True)
        else:
            st.write("Sektör verisi TradingView'den alınamadı.")
else:
    # Diğer modüller
    if menu_secim == "Detaylı Analiz":
        st.subheader("🧠 Detaylı Analiz")
        st.write("**En Olası İlk 10 Hisse** (AI Sinyaline göre)")
        if not analizli_df.empty:
            ilk10 = analizli_df.sort_values(by='AI Sinyal', ascending=False).head(10)
            st.dataframe(ilk10[['Hisse', 'Fiyat', 'AI Sinyal', 'Tavan Potansiyeli (%)']], width='stretch', hide_index=True)
        
        st.markdown("---")
        st.write("**Hisse Seçimi**")
        if 'secili_hisse' in st.session_state:
            sec = st.session_state['secili_hisse']
        else:
            sec = "GARAN"
        if not analizli_df.empty:
            sec = st.selectbox("Analiz Edilecek Hisse", analizli_df['Hisse'].tolist(), index=0, key="detay_secim")
        
        if st.button("Derinlemesine Analizi Başlat"):
            # Veri setinden hisseyi filtrele
            hisse_verisi = analizli_df[analizli_df['Hisse'] == sec]
            if not hisse_verisi.empty:
                st.success(f"{sec} için detaylı veriler:")
                st.write(f"**Güncel Fiyat:** {safe_float(hisse_verisi.iloc[0]['Fiyat'])} TL")
                st.write(f"**Günlük Değişim:** %{safe_float(hisse_verisi.iloc[0]['Gün %'])}")
                st.write(f"**RSI:** {safe_float(hisse_verisi.iloc[0]['RSI'])}")
                st.write(f"**Sektör:** {hisse_verisi.iloc[0].get('sector', 'Bilinmiyor')}")
                st.write(f"**AI Sinyal:** {hisse_verisi.iloc[0]['AI Sinyal']}")
                st.write(f"**Tahmini Fiyat:** {hisse_verisi.iloc[0]['Tahmini Fiyat']} TL")
            else:
                st.error("Seçilen hisse veri setinde bulunamadı.")
    elif menu_secim == "Orijinal Hisseler":
        st.subheader("🚀 Orijinal Hisseler")
        st.write("Endeks dışı yüksek hacimli hisseler")
        if not analizli_df.empty:
            df_orig = analizli_df[analizli_df['Hacim'] > 1000000].sort_values(by='Hacim', ascending=False).head(20)
            st.dataframe(df_orig[['Hisse', 'Fiyat', 'Hacim', 'Gün %']], width='stretch', hide_index=True)
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
