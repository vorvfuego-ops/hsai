import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import traceback

st.set_page_config(page_title="AI Hisse Analiz Sistemi", layout="wide")
st.title("📈 AI Destekli Hisse Analiz Sistemi")

# Sembolleri otomatik düzeltme fonksiyonu
def normalize_symbol(symbol):
    symbol = symbol.strip().upper()
    if symbol.startswith("BIST-"):
        symbol = symbol.split("-")[1] + ".IS"
    elif symbol.startswith("BIST:"):
        symbol = symbol.split(":")[1] + ".IS"
    elif not symbol.endswith(".IS") and not symbol.endswith(".SI"):
        symbol = symbol + ".IS"
    return symbol

# Basit skorlama ve örnek popüler hisseler
def get_market_snapshot():
    populer_hisseler = ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "THYAO.IS", "ASELS.IS"]
    veriler = []
    for sembol in populer_hisseler:
        try:
            # Son 1 yıllık veriyi çek
            df = yf.download(sembol, period="1y", progress=False, auto_adjust=False)
            df = df.dropna()
            if len(df) > 50:
                fiyat = float(df['Close'].iloc[-1])
                sma50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
                # Basit skorlama (RVI 100 üzerinden gibi düşünülebilir, burada 0-10 arası temsili basit hesap)
                skor = (fiyat / sma50) * 5
                skor = min(10, max(0, skor))
                veriler.append({
                    "Hisse": sembol.replace(".IS", ""),
                    "Skor (10 Üzerinden)": round(skor, 1),
                    "Son Kapanış": fiyat
                })
        except:
            continue
    return pd.DataFrame(veriler).sort_values(by="Skor (10 Üzerinden)", ascending=False)

# Kenar Çubuğu
with st.sidebar:
    st.header("Parametreler")
    
    # Örnek Hisseler
    secenekler = ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "XBANK.IS"]
    varsayilan = "GARAN.IS"
    
    ticker_input = st.selectbox("Hisse / Endeks Sembolü", options=secenekler, index=secenekler.index(varsayilan))
    date_input = st.text_input("Başlangıç Tarihi", value="2023-01-01", placeholder="YYYY-AA-GG")
    analiz_btn = st.button("🚀 Analizi Başlat", type="primary")

# Ana Mantık
if analiz_btn:
    sembol = normalize_symbol(ticker_input)
    try:
        with st.spinner(f"Veri çekiliyor: {sembol}..."):
            df = yf.download(sembol, start=date_input, progress=False, auto_adjust=False)
            df = df.dropna()
            if df.empty:
                st.error(f"'{sembol}' için veri bulunamadı. Lütfen sembolü kontrol edin.")
            else:
                # ... (Önceki analiz kodunuzun tamamı burada)
                df['SMA_10'] = df['Close'].rolling(window=10).mean()
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df = df.dropna()
                
                last_close = float(df['Close'].iloc[-1])
                last_sma10 = float(df['SMA_10'].iloc[-1])
                last_sma50 = float(df['SMA_50'].iloc[-1])
                
                # Geliştirilmiş Skorlama Mantığı (10 üzerinden)
                skor = 0
                if last_close > last_sma10: skor += 4
                if last_close > last_sma50: skor += 4
                if last_sma10 > last_sma50: skor += 2
                skor = min(10, skor)
                
                # Rapor ve Grafik (Önceki versiyondaki gibi devam eder...)
                # ... (Raporunuzu buraya ekleyin)
    except Exception as e:
        st.error(f"Hata: {e}")
else:
    # Ana Sayfa Görünümü (Öneriler ve Puanlama)
    st.subheader("🔥 İşlem Hacmi En Yüksek Hisseler ve Skorları (Örnek)")
    snapshot = get_market_snapshot()
    if not snapshot.empty:
        st.dataframe(snapshot, use_container_width=True, hide_index=True)
    
    st.info("Analiz yapmak için sol taraftaki parametreleri girip 'Analizi Başlat' butonuna basın.")