import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# --- BORSAPY & TRADINGVIEW YAPILANDIRMASI ---
# Kullanıcının paylaştığı değerler:
SESSION_ID = "v3jp9jqZTQwZpkYFGNqmcp37KrOE30jn3OlSl538mamY68="
SESSION_SIGN = "jebbmm7kzum3kzdt7w3mtok8ke5nqfp10"

# Borsapy kullanılacaksa import edilir (TradingViewStream için)
try:
    import borsapy as bp
    # TradingView oturum bilgilerini tanımla
    bp.set_tradingview_auth(session=SESSION_ID, session_sign=SESSION_SIGN)
    TV_BAGLANTI_AKTIF = True
except Exception as e:
    TV_BAGLANTI_AKTIF = False
    print(f"borsapy kurulu değil: {e}")

# --- NAVİGASYON ---
if "sayfa" not in st.session_state:
    st.session_state.sayfa = "Ana Sayfa"
if "secili_hisse" not in st.session_state:
    st.session_state.secili_hisse = "GARAN"

def ana_sayfaya_don():
    st.session_state.sayfa = "Ana Sayfa"
    st.rerun()

def analiz_et(hisse):
    st.session_state.secili_hisse = hisse
    st.session_state.sayfa = "Analiz"
    st.rerun()

# --- VERİ ÇEKME (Çift Kaynaklı: Önce yfinance, Sonra borsapy) ---
@st.cache_data(ttl=300)
def veri_cek(sembol, period="6mo"):
    # Sembolü formatla (GARAN -> GARAN.IS)
    sembol_uzun = sembol.upper().replace(".IS", "") + ".IS"
    sembol_kisa = sembol.upper().replace(".IS", "")

    # 1. Yöntem: yfinance (En stabil)
    df = pd.DataFrame()
    try:
        df = yf.download(sembol_uzun, period=period, progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
    except:
        pass

    # 2. Yöntem (Yedek): borsapy (TradingViewStream)
    if df.empty and TV_BAGLANTI_AKTIF:
        try:
            stock = bp.Ticker(sembol_kisa) # .IS eklenmeden kullanılır
            # TradingView period formatı: "6mo" yerine "6ay" gerekebilir
            df = stock.history(period="6ay")
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = df.rename(columns={c: c.capitalize() for c in df.columns})
                df = df.dropna()
        except:
            pass

    return df

# --- YZ TAHMİN MOTORU (Volatilite + Momentum) ---
def yz_tahmin_hesapla(sembol):
    df = veri_cek(sembol, period="3mo")
    if df.empty or len(df) < 10:
        return {"sinyal": "Veri Yetersiz", "gunluk": 5.0, "haftalik": 10.0, "aylik": 20.0}

    # Volatilite Hesaplama
    df['Return'] = df['Close'].pct_change()
    gunluk_vol = df['Return'].std() * 100

    # RSI Hesaplama (Momentum)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    son_rsi = float(rsi.iloc[-1])

    # Tahmin Matrisi
    taban = (son_rsi - 50) / 10
    gunluk_potansiyel = max(5.0, min(40.0, gunluk_vol + taban * 3))
    haftalik = gunluk_potansiyel * 2.5
    aylik = gunluk_potansiyel * 4.0

    if son_rsi > 70: sinyal = "Aşırı Alım / Güçlü Yükseliş"
    elif son_rsi > 55: sinyal = "Pozitif Momentum"
    else: sinyal = "Nötr / Takip"

    return {"sinyal": sinyal, "gunluk": round(gunluk_potansiyel, 1), 
            "haftalik": round(haftalik, 1), "aylik": round(aylik, 1)}

# --- ARAYÜZ ---
if st.session_state.sayfa == "Ana Sayfa":
    st.title("📊 BIST AI Yatırım Stüdyosu")
    st.caption("Türkiye piyasası için güncel verilerle olası yükseliş senaryoları")
    
    populer = ["GARAN", "AKBNK", "ISCTR", "YKBNK", "THYAO", "ASELS", "EREGL", "BIMAS", "SISE", "SASA"]
    
    with st.spinner("Model analizleri yapılıyor..."):
        tahminler = []
        for hisse in populer:
            tahmin = yz_tahmin_hesapla(hisse)
            tahminler.append({
                "Hisse": hisse, 
                "Sinyal": tahmin["sinyal"],
                "Günlük Potansiyel (%)": tahmin["gunluk"],
                "Haftalık Potansiyel (%)": tahmin["haftalik"],
                "Aylık Potansiyel (%)": tahmin["aylik"]
            })
        
        df_tablo = pd.DataFrame(tahminler)
        st.dataframe(df_tablo, width='stretch', hide_index=True)
        
        secim = st.selectbox("Detaylı Analiz İçin Hisse Seçin", options=populer)
        if st.button("🚀 Analiz Et ve Öneri Al"):
            analiz_et(secim)

elif st.session_state.sayfa == "Analiz":
    sembol = st.session_state.secili_hisse
    
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Ana Sayfa"):
            ana_sayfaya_don()
    with col_title:
        st.title(f"🔍 {sembol} Analizleri")
    
    df = veri_cek(sembol, period="6mo")
    
    if df.empty:
        st.error("⚠️ Veri akışı kurulamadı. Sembolü kontrol edin veya daha sonra tekrar deneyin.")
    else:
        tahmin = yz_tahmin_hesapla(sembol)
        last_close = float(df['Close'].iloc[-1])
        
        st.markdown("### 🤖 YZ Tahmin Motoru")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Olası Sinyal", tahmin["sinyal"])
        col2.metric("1 Günlük Hedef", f"%{tahmin['gunluk']} 📈")
        col3.metric("1 Haftalık Hedef", f"%{tahmin['haftalik']} 📈")
        col4.metric("1 Aylık Hedef", f"%{tahmin['aylik']} 📈")
        
        st.info("⚠️ Bu tahminler geçmiş verilere dayanır, yatırım tavsiyesi değildir.")
        
        # Profesyonel Grafik (Candlestick + Hacim)
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray'), row=2, col=1)
        
        fig.update_layout(title=f"{sembol} Teknik Görünüm", xaxis_rangeslider_visible=False, template='plotly_dark', height=700)
        st.plotly_chart(fig, width='stretch')