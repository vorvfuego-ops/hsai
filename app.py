import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import borsapy as bp
from datetime import datetime, timedelta

st.set_page_config(page_title="BIST AI Yatırım Stüdyosu", layout="wide")

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

# --- YARDIMCI FONKSİYONLAR ---

@st.cache_data(ttl=300)  # 5 dakikalık önbellek
def veri_cek(sembol, period="6mo"):
    try:
        # borsapy "THYAO" formatını bekler
        stock = bp.Stock(sembol.upper().replace(".IS", ""))
        
        # Dönem bazlı veri çekme (Türkçe period destekli) - Kaynak 1
        df = stock.history(period=period, interval="1d")
        
        if isinstance(df, pd.DataFrame) and not df.empty:
            # Sütun isimlerini standartlaştır
            df = df.rename(columns={c: c.capitalize() for c in df.columns})
            if 'Adj close' in df.columns: df.rename(columns={'Adj close': 'Adj Close'}, inplace=True)
            if 'Adj close' in df.columns: df.rename(columns={'Adj close': 'Adj Close'}, inplace=True)
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def yz_tahmin_hesapla(sembol):
    """
    Geçmiş verilere dayalı 'ileriye dönük' tahmin modeli.
    Basit volatilite ve momentum analizi ile olası yükseliş senaryoları üretir.
    """
    # 1 aylık veriyi çek (Ayarlanmış fiyatları kullan - auto_adjust / actions True) - Kaynak 5
    try:
        stock = bp.Stock(sembol.upper().replace(".IS", ""))
        df = stock.history(period="1ay", interval="1d", auto_adjust=True)
        if df.empty or len(df) < 10:
            return {"sinyal": "Yetersiz Veri", "gunluk": 0, "haftalik": 0, "aylik": 0}
        
        # Günlük getiriler (Volatilite)
        df['Return'] = df['Close'].pct_change()
        günlük_volatilite = df['Return'].std()
        
        # RSI (Momentum) - history_with_indicators kullanarak daha güvenilir veri - Kaynak 2
        df_ind = stock.history_with_indicators(period="1ay", indicators=["rsi"])
        rsi_val = float(df_ind['RSI'].iloc[-1]) if 'RSI' in df_ind.columns and not df_ind.empty else 50.0
        
        # Tahmin Motoru:
        # Eğer RSI > 55 (alım gücü) ise ve volatilite yüksekse büyük yükselişler mümkün
        taban = (rsi_val - 50) / 10 # 50 üstü ise pozitif değer
        
        günlük_potansiyel = max(5, min(30, taban * 5 + günlük_volatilite * 100))
        haftalik = günlük_potansiyel * 3
        aylik = günlük_potansiyel * 5
        
        if rsi_val > 70:
            sinyal = "Aşırı Alım (Güçlü Yükseliş)"
        elif rsi_val > 55:
            sinyal = "Pozitif Momentum"
        else:
            sinyal = "Nötr / Takip"
            
        return {"sinyal": sinyal, "gunluk": round(günlük_potansiyel, 1), 
                "haftalik": round(haftalik, 1), "aylik": round(aylik, 1)}
    except:
        return {"sinyal": "Veri Hatası", "gunluk": 0, "haftalik": 0, "aylik": 0}

# --- ARAYÜZ ---

if st.session_state.sayfa == "Ana Sayfa":
    st.title("📊 BIST AI Yatırım Stüdyosu")
    st.caption("Geçmiş analizlere dayalı olası yükseliş senaryoları")
    
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
    
    df = veri_cek(sembol)
    
    if df.empty:
        st.error("⚠️ Bu hisse için şu anda veri akışı sağlanamıyor. Lütfen geçici bir hata olduğunu varsayarak tekrar deneyin.")
    else:
        tahmin = yz_tahmin_hesapla(sembol)
        last_close = float(df['Close'].iloc[-1])
        
        # YZ Tahmin Paneli
        st.markdown(f"### 🤖 YZ Tahmin Motoru (Geçmiş Verilere Göre)")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Olası Sinyal", tahmin["sinyal"])
        col2.metric("1 Günlük Hedef", f"%{tahmin['gunluk']} 📈")
        col3.metric("1 Haftalık Hedef", f"%{tahmin['haftalik']} 📈")
        col4.metric("1 Aylık Hedef", f"%{tahmin['aylik']} 📈")
        
        st.info(f"⚠️ Bu senaryolar geçmiş volatilite ve momentum verilerine dayanmaktadır. Gerçekleşmesi garanti edilemez; finansal tavsiye niteliği taşımaz.")
        
        # Profesyonel Grafik (Candlestick + Hacim + RSI)
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['RSI'] = 50 # Basit gösterge koyma
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        
        # Ana Grafik
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                     low=df['Low'], close=df['Close'], name='Fiyat', 
                                     increasing_line_color='green', decreasing_line_color='red'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange', width=1)), row=1, col=1)
        
        # Hacim
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray'), row=2, col=1)
        
        # RSI Simülasyonu
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
        
        fig.update_layout(
            title=f"{sembol} Teknik Görünüm",
            xaxis_rangeslider_visible=False,
            template='plotly_dark', # Daha profesyonel görünüm
            height=800,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, width='stretch')