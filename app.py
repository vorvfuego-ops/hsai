import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import yfinance as yf
import time
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="BIST Pro AI Terminali", layout="wide")

# CSS (Fintables benzeri stil)
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

# --- Yardımcı Fonksiyonlar ---
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

# --- Tüm BIST Hisselerini Çekme ---
@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        q = Query().set_markets('turkey').select(
            'name', 'close', 'change', 'volume', 'market_cap_basic', 'RSI', 'sector', 'high_all_calc'
        ).order_by('volume', ascending=False).limit(500)
        try:
            total, df = q.get_scanner_data(auth_token=token)
        except:
            total, df = q.get_scanner_data()
        return df
    except:
        return pd.DataFrame()

# --- AI Hesaplama Motoru (Güvenli) ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    # 52 Haftalık yüksek
    yuksekler = []
    for isim in df['name']:
        try:
            v = yf.download(isim + ".IS", period="1y", progress=False, auto_adjust=False)
            yuksek = safe_float(v['High'].max()) if not v.empty else 0
        except:
            yuksek = 0
        yuksekler.append(yuksek)
    df['52H_Yuksek'] = yuksekler
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['close']) / df['close']) * 100

    def neden_yukselir(row):
        nedenler = []
        rsi = safe_float(row['RSI'])
        if rsi > 70: nedenler.append("Aşırı alım")
        elif rsi > 50: nedenler.append("Pozitif RSI")
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: nedenler.append("Tavanına uzak")
        elif pot > 5: nedenler.append("Zirveye yakın")
        if safe_float(row['change']) > 2: nedenler.append("Bugün güçlü")
        if safe_float(row['volume']) > 1000000: nedenler.append("Yüksek hacim")
        return ", ".join(nedenler) if nedenler else "Normal"

    df['Neden Yükselebilir?'] = df.apply(neden_yukselir, axis=1)

    # Monte Carlo (Hata düzeltildi: abs kullanıldı)
    def monte_carlo(row):
        fiyat = safe_float(row['close'])
        degisim = safe_float(row['change'])
        vol = abs(degisim) / 100.0
        sims = np.random.normal(fiyat, vol * fiyat, 200)
        return np.median(sims)

    df['Tahmini Fiyat'] = df.apply(monte_carlo, axis=1).round(2)
    df['Alt Eşik'] = (df['Tahmini Fiyat'] - (df['Tahmini Fiyat']*0.05)).round(2)
    df['Üst Eşik'] = (df['Tahmini Fiyat'] + (df['Tahmini Fiyat']*0.05)).round(2)
    df['Hata Payı'] = ((df['Üst Eşik'] - df['Alt Eşik']) / 2).round(2)

    def sinyal(row):
        if safe_float(row['Tavan Potansiyeli (%)']) > 10 and safe_float(row['RSI']) < 70:
            return "🟢 AL"
        elif safe_float(row['Tavan Potansiyeli (%)']) > 0:
            return "🟡 TUT"
        else:
            return "🔴 SAT"

    df['AI Sinyal'] = df.apply(sinyal, axis=1)
    return df

# --- Veri Yükleme ---
with st.spinner("Veriler yükleniyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()
    if not tum_hisseler.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler)

# --- Ana Başlık ---
st.title("📊 BIST Pro AI Terminali")

# --- Sol Menü ---
with st.sidebar:
    st.header("📋 Menü")
    menu = st.radio("Menü Seçin", ["Radar", "Hisse", "Endeksler", "VIP", "Kripto"], key="menu")
    st.markdown("---")
    if not tum_hisseler.empty:
        st.subheader("Tüm Hisseler")
        secim = st.selectbox("Hisse Seç", tum_hisseler['name'].tolist())
        if st.button("Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.rerun()

# --- Sekmeler ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🚀 Yüksek Potansiyel", "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyüme",
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🧠 Derinlemesine Analiz"
])

# TAB 1: Yüksek Potansiyel
with tab1:
    st.subheader("🔥 Yüksek Potansiyelli Tavan Hisseleri")
    if not tum_hisseler.empty:
        df_tavan = analizli_df.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(10)
        st.dataframe(df_tavan[['name', 'close', 'change', 'Tavan Potansiyeli (%)', 'Neden Yükselebilir?']], width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 2: Getiri
with tab2:
    st.subheader("📊 Getiri Tablosu")
    if not tum_hisseler.empty:
        df_getiri = analizli_df.sort_values(by='change', ascending=False).head(50)
        st.dataframe(df_getiri[['name', 'close', 'change', 'volume', 'Tavan Potansiyeli (%)', 'RSI']], width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 3: Değerleme
with tab3:
    st.subheader("💎 Değerleme")
    if not tum_hisseler.empty:
        df_val = tum_hisseler[['name', 'close', 'market_cap_basic']].head(50)
        st.dataframe(df_val, width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 4: Karlılık
with tab4:
    st.subheader("📈 Karlılık")
    if not tum_hisseler.empty:
        st.dataframe(analizli_df[['name', 'close', 'RSI', 'AI Sinyal']].head(50), width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 5: Büyüme
with tab5:
    st.subheader("🚀 Büyüme")
    if not tum_hisseler.empty:
        st.dataframe(tum_hisseler[['name', 'close', 'volume']].head(50), width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 6: Bilanço
with tab6:
    st.subheader("📋 Bilanço")
    if not tum_hisseler.empty:
        st.dataframe(tum_hisseler[['name', 'market_cap_basic']].head(50), width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 7: Gelir Tablosu
with tab7:
    st.subheader("💵 Gelir Tablosu")
    if not tum_hisseler.empty:
        st.dataframe(tum_hisseler[['name', 'close']].head(50), width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 8: Nakit Akım
with tab8:
    st.subheader("💧 Nakit Akım")
    if not tum_hisseler.empty:
        st.dataframe(tum_hisseler[['name', 'volume']].head(50), width='stretch', hide_index=True)
    else:
        st.error("Veri yok")

# TAB 9: Derinlemesine Analiz
with tab9:
    st.subheader("🧠 Derinlemesine Analiz")
    if 'secili_hisse' in st.session_state:
        sec = st.session_state['secili_hisse']
    else:
        sec = "GARAN"
    if not tum_hisseler.empty:
        sec = st.selectbox("Analiz Edilecek Hisse", tum_hisseler['name'].tolist(), index=0, key="prof")
    if st.button("Derinlemesine Analizi Başlat"):
        df = yf.download(sec + ".IS", period="6mo", progress=False, auto_adjust=False)
        if df.empty:
            st.error("Veri yok")
        else:
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray'), row=2, col=1)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='purple')), row=3, col=1)
            fig.update_layout(title=f"{sec} Profesyonel Görünüm", height=800, template='plotly_dark')
            st.plotly_chart(fig, width='stretch')
