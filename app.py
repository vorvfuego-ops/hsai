import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import traceback
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="AI Hisse Analiz Sistemi", layout="wide")

# ============================================================
# 1. TEKNİK ANALİZ FONKSİYONU
# ============================================================
def teknik_analiz(ticker, start_date):
    try:
        ticker_symbol = ticker.strip().upper()
        df = yf.download(ticker_symbol, start=start_date, progress=False)
        if df.empty:
            return None, None, None, f"❌ '{ticker_symbol}' için veri bulunamadı."
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        last_close = float(df['Close'].iloc[-1])
        last_sma10 = float(df['SMA_10'].iloc[-1])
        last_sma50 = float(df['SMA_50'].iloc[-1])
        
        if last_sma10 > last_sma50 and last_close > last_sma10:
            signal = "🟢 GÜÇLÜ AL"
            recommendation = "Kısa vadeli trend yukarı yönlü"
        else:
            signal = "🔴 SAT / BEKLE"
            recommendation = "Piyasada aşağı yönlü baskı var"
        
        sonuc = f"""
### 📊 Teknik Analiz Raporu: {ticker_symbol}
- Son Kapanış: **${last_close:.2f}**
- SMA 10: ${last_sma10:.2f}
- SMA 50: ${last_sma50:.2f}
- **Karar: {signal}** - {recommendation}
        """
        
        df_reset = df.reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['Close'], mode='lines', name='Kapanış'))
        fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['SMA_10'], mode='lines', name='SMA 10'))
        fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['SMA_50'], mode='lines', name='SMA 50'))
        fig.update_layout(title=f'{ticker_symbol} Fiyat Grafiği', height=400)
        
        last_10 = df_reset.tail(10)[['Date', 'Close', 'SMA_10', 'SMA_50']].round(2)
        return sonuc, fig, last_10, None
    except Exception as e:
        return None, None, None, f"❌ Hata: {str(e)}"

# ============================================================
# 2. FINTABLES RADAR (SELENİUM OLMADAN - REQUESTS + BS4)
# ============================================================
def fintables_radar():
    try:
        url = "https://fintables.com/radar/hisse-senetleri"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tablo bulma (örnek seçici, gerçekte değişebilir)
        table = soup.find('table')
        if not table:
            return pd.DataFrame({"Durum": ["Tablo bulunamadı, sayfa yapısı değişmiş olabilir."]})
        
        rows = table.find_all('tr')
        data = []
        for row in rows[1:21]:  # ilk 20 satır
            cols = row.find_all('td')
            if len(cols) >= 5:
                data.append({
                    'Sembol': cols[0].text.strip(),
                    'Fiyat': cols[1].text.strip(),
                    'Değişim': cols[2].text.strip(),
                    'Hacim': cols[3].text.strip(),
                    'Potansiyel': cols[4].text.strip()
                })
        if data:
            return pd.DataFrame(data)
        else:
            return pd.DataFrame({"Durum": ["Veri çekilemedi, sayfa yapısı değişmiş olabilir."]})
    except Exception as e:
        return pd.DataFrame({"Hata": [f"Bağlantı hatası: {str(e)}"]})

# ============================================================
# 3. TEMEL ANALİZ
# ============================================================
def temel_analiz(ticker):
    try:
        ticker_symbol = ticker.strip().upper()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        if not info:
            return f"❌ '{ticker_symbol}' için veri bulunamadı."
        
        sonuc = f"""
### 📊 Temel Analiz: {ticker_symbol}
- **Şirket:** {info.get('longName', 'Bilgi yok')}
- **Sektör:** {info.get('sector', 'Bilgi yok')}
- **Fiyat:** ${info.get('currentPrice', info.get('regularMarketPrice', 'Bilgi yok'))}
- **Piyasa Değeri:** ${info.get('marketCap', 'Bilgi yok'):,}
- **F/K:** {info.get('trailingPE', 'Bilgi yok')}
- **Defter Değeri:** ${info.get('bookValue', 'Bilgi yok')}
- **Temettü Verimi:** %{info.get('dividendYield', 0)*100 if info.get('dividendYield') else 'Bilgi yok'}
- **Öneri:** {info.get('recommendationKey', 'Bilgi yok')}
- **Hedef Fiyat:** ${info.get('targetMeanPrice', 'Bilgi yok')}
        """
        return sonuc
    except Exception as e:
        return f"❌ Hata: {str(e)}"

# ============================================================
# 4. STREAMLIT ARAYÜZÜ
# ============================================================
st.title("📈 AI Destekli Hisse Analiz Sistemi")

# Menü sekmeleri
tab1, tab2, tab3, tab4 = st.tabs(["📊 Teknik Analiz", "🚀 Yüksek Potansiyelli Tavan Hisseleri", "🏢 Temel Analiz", "🌐 Genel Sistem Verileri"])

# ----- SEKME 1: TEKNİK ANALİZ -----
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input("Hisse Sembolü", "AAPL")
        start_date = st.text_input("Başlangıç Tarihi", "2022-01-01")
        analiz_btn = st.button("🚀 Analizi Başlat", type="primary")
    with col2:
        if analiz_btn:
            with st.spinner("Analiz yapılıyor..."):
                sonuc, fig, tablo, hata = teknik_analiz(ticker, start_date)
                if hata:
                    st.error(hata)
                else:
                    st.markdown(sonuc)
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(tablo, use_container_width=True)

# ----- SEKME 2: RADAR -----
with tab2:
    st.subheader("📋 Fintables Radar - Yüksek Potansiyelli Hisseler")
    if st.button("🔄 Radar Verilerini Getir"):
        with st.spinner("Veriler çekiliyor..."):
            df = fintables_radar()
            st.dataframe(df, use_container_width=True)

# ----- SEKME 3: TEMEL ANALİZ -----
with tab3:
    st.subheader("🏢 Temel Analiz - Şirket Finansal Verileri")
    temel_ticker = st.text_input("Hisse Sembolü (Temel)", "AAPL", key="temel")
    if st.button("📊 Temel Analizi Getir", type="primary"):
        with st.spinner("Veriler çekiliyor..."):
            sonuc = temel_analiz(temel_ticker)
            st.markdown(sonuc)

# ----- SEKME 4: GENEL SİSTEM VERİLERİ (iframe) -----
with tab4:
    st.subheader("🌐 Fintables - Hisse Senedi Radar Sayfası")
    st.components.v1.html(
        """
        <iframe 
            src="https://fintables.com/radar/hisse-senetleri" 
            style="width:100%; height:700px; border:1px solid #ccc; border-radius:8px;"
            sandbox="allow-scripts allow-same-origin allow-forms"
            loading="lazy"
        ></iframe>
        """,
        height=720
    )
