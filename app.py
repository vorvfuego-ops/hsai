import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import yfinance as yf
import requests

# --- GÜVENLİ FLOAT DÖNÜŞTÜRÜCÜ ---
def safe_float(val):
    """Pandas/yfinance sürüm farklılıklarından kaynaklanan TypeError'ları engeller."""
    if val is None:
        return 0.0
    if isinstance(val, pd.Series):
        if val.empty:
            return 0.0
        try:
            return float(val.iloc[0])
        except:
            return 0.0
    try:
        return float(val)
    except:
        return 0.0

# --- TRADINGVIEW HESAP DOĞRULAMA (Otomatik Token) ---
def get_auth_token():
    """Kullanıcı adı ve şifreyi kullanarak TradingView token'ını otomatik çeker."""
    try:
        username = st.secrets["tradingview"]["username"]
        password = st.secrets["tradingview"]["password"]
        
        sign_in_url = 'https://www.tradingview.com/accounts/signin/'
        data = {"username": username, "password": password, "remember": "on"}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.post(url=sign_in_url, data=data, headers=headers)
        
        if response.status_code == 200 and 'auth_token' in response.json().get('user', {}):
            return response.json()['user']['auth_token']
        else:
            return None
    except:
        return None

@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    """TradingView Screener ile tüm BIST hisselerini tarar."""
    try:
        from tradingview_screener import Query
        
        # Önce token dene, sonra anonim (gecikmeli veri) olarak devam et
        token = get_auth_token()
        
        query = (
            Query()
            .set_markets('turkey')
            .select('name', 'close', 'change', 'volume', 'market_cap_basic',
                    'RSI', 'MACD.macd', 'MACD.signal', 'Perf.W', 'Perf.1M',
                    'Perf.3M', 'Perf.6M', 'Perf.YTD', 'sector',
                    'high_all_calc', 'low_all_calc', 'Volatility.W')
            .order_by('volume', ascending=False)
            .limit(1000)
        )
        
        # Otomatik token enjeksiyonu
        try:
            total, df = query.get_scanner_data(auth_token=token)
        except:
            total, df = query.get_scanner_data()
            
        return df
    except Exception as e:
        return pd.DataFrame()

# --- TAVAN KAPASİTESİ MODELİ (YZ) ---
def tavan_kapasite_hesapla(sembol):
    try:
        sembol_uzun = sembol.upper().replace(".IS", "") + ".IS"
        df = yf.download(sembol_uzun, period="6mo", progress=False, auto_adjust=False)
        
        if len(df) < 50:
            return 0, 0, 0
        
        df['Return'] = df['Close'].pct_change()
        volatilite = df['Return'].std() * 100
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        son_rsi = safe_float(rsi.iloc[-1])
        
        yuksek = safe_float(df['High'].max())
        mevcut = safe_float(df['Close'].iloc[-1])
        tavan_potansiyeli = ((yuksek - mevcut) / mevcut) * 100 if mevcut > 0 else 0
        
        skor = 0
        if son_rsi > 50: skor += 3
        if tavan_potansiyeli > 10: skor += 3
        if volatilite > 3: skor += 4
        
        return skor, tavan_potansiyeli, son_rsi
    except:
        return 0, 0, 0

# --- ARAYÜZ ---
st.set_page_config(page_title="BIST Pro AI Terminali", layout="wide")
st.title("📊 BIST Pro AI Terminali")
st.caption("TradingView Altyapısı ile Sınırsız Analiz")

tab1, tab2 = st.tabs(["🚀 Tavan Avcıları", "📈 Profesyonel Analiz"])

# Tab 1: Tavan Avcıları
with tab1:
    st.subheader("🔥 Yüksek Potansiyelli Tavan Hisseleri")
    
    with st.spinner("Tüm BIST hisseleri taranıyor..."):
        hisse_verisi = tum_bist_hisselerini_getir()
        
        if not hisse_verisi.empty:
            hisse_verisi['Tavan Potansiyeli (%)'] = ((hisse_verisi['high_all_calc'] - hisse_verisi['close']) / hisse_verisi['close']) * 100
            hisse_verisi = hisse_verisi.fillna(0)
            
            tavan_hisseleri = hisse_verisi.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(5)
            
            st.dataframe(tavan_hisseleri[['name', 'close', 'change', 'volume', 'Tavan Potansiyeli (%)', 'RSI', 'sector']], width='stretch', hide_index=True)
            
            st.markdown("### 📈 Tavan Hisselerinin Performansı")
            fig = go.Figure()
            
            for i, row in tavan_hisseleri.iterrows():
                try:
                    df_yf = yf.download(row['name'] + ".IS", period="6mo", progress=False)
                    if not df_yf.empty:
                        fig.add_trace(go.Scatter(
                            x=df_yf.index, y=df_yf['Close'], 
                            mode='lines', name=row['name'],
                            line=dict(width=2)
                        ))
                except:
                    pass
            
            fig.update_layout(title="Potansiyel Tavan Hisseleri", height=500, template='plotly_white')
            st.plotly_chart(fig, width='stretch')
        else:
            st.error("BIST verileri çekilemedi. Secrets ayarlarını kontrol edin.")

# Tab 2: Profesyonel Analiz
with tab2:
    st.subheader("🧠 Profesyonel Analiz")
    secim = st.selectbox("Analiz Edilecek Hisse", ["GARAN", "AKBNK", "ISCTR", "YKBNK", "THYAO", "ASELS", "EREGL", "BIMAS", "SISE", "SASA"])
    
    if st.button("Derinlemesine Analiz Başlat"):
        df = yf.download(secim + ".IS", period="6mo", progress=False, auto_adjust=False)
        
        if df.empty:
            st.error("Veri bulunamadı.")
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
            
            fig.update_layout(title=f"{secim} Profesyonel Görünüm", height=800, template='plotly_white')
            st.plotly_chart(fig, width='stretch')