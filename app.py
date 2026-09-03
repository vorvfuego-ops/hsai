import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import time
import traceback

# Selenium importları
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

st.set_page_config(page_title="AI Hisse Analiz Sistemi", layout="wide")
st.title("📈 AI Destekli Hisse Analiz Sistemi")

# ===================== FONKSİYONLAR =====================

@st.cache_data(ttl=3600)
def get_stock_data(ticker, start_date, end_date):
    """Yahoo Finance'den hisse verilerini çeker"""
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None

@st.cache_data(ttl=3600)
def get_fundamental_data(ticker):
    """Yahoo Finance'den temel analiz verilerini çeker"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info
    except Exception:
        return None

@st.cache_data(ttl=3600)
def get_fintables_radar():
    """Fintables radar sayfasından verileri çeker (Selenium ile)"""
    if not SELENIUM_AVAILABLE:
        return None, "Selenium kurulu değil. Lütfen 'selenium' ve 'webdriver-manager' paketlerini kurun."
    
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        driver.get("https://fintables.com/radar/hisse-senetleri")
        time.sleep(5)  # Sayfanın yüklenmesi için bekle
        
        # Tablo satırlarını bul (sayfa yapısına göre ayarlanmalı)
        # Örnek seçici: table tbody tr
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        veriler = []
        for row in rows[:20]:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                veriler.append({
                    'Sembol': cols[0].text.strip(),
                    'Fiyat': cols[1].text.strip(),
                    'Değişim': cols[2].text.strip(),
                    'Hacim': cols[3].text.strip(),
                    'Potansiyel': cols[4].text.strip() if len(cols) > 4 else "-"
                })
        driver.quit()
        
        if veriler:
            df = pd.DataFrame(veriler)
            return df, None
        else:
            return None, "Veri çekilemedi. Sayfa yapısı değişmiş olabilir."
    except Exception as e:
        return None, f"Selenium hatası: {str(e)}"

# ===================== TEKNİK ANALİZ =====================
def teknik_analiz():
    st.subheader("📊 Teknik Analiz")
    col1, col2 = st.columns([1, 3])
    with col1:
        ticker = st.text_input("Hisse Sembolü", value="AAPL", key="teknik_ticker")
        # Varsayılan başlangıç tarihi: 1 yıl önce
        default_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        start_date = st.date_input("Başlangıç Tarihi", value=datetime.strptime(default_start, "%Y-%m-%d"), key="teknik_start")
        end_date = st.date_input("Bitiş Tarihi", value=datetime.now(), key="teknik_end")
        analiz_btn = st.button("Analizi Başlat", key="teknik_btn")
    
    if analiz_btn or 'teknik_df' not in st.session_state:
        if not ticker:
            st.warning("Lütfen bir hisse sembolü girin.")
            return
        with st.spinner("Veri çekiliyor..."):
            df = get_stock_data(ticker, start_date, end_date)
            if df is None or df.empty:
                st.error(f"'{ticker}' için veri bulunamadı.")
                return
            st.session_state['teknik_df'] = df
            st.session_state['teknik_ticker'] = ticker
    
    if 'teknik_df' in st.session_state:
        df = st.session_state['teknik_df']
        ticker = st.session_state['teknik_ticker']
        
        # SMA hesapla
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        last_close = df['Close'].iloc[-1]
        last_sma10 = df['SMA_10'].iloc[-1]
        last_sma50 = df['SMA_50'].iloc[-1]
        
        # Sinyal
        if last_sma10 > last_sma50 and last_close > last_sma10:
            signal = "🟢 GÜÇLÜ AL"
            recommendation = "Kısa vadeli trend yukarı yönlü"
        else:
            signal = "🔴 SAT / BEKLE"
            recommendation = "Piyasada aşağı yönlü baskı var"
        
        # Metrikler
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Son Kapanış", f"${last_close:.2f}")
        col2.metric("SMA 10", f"${last_sma10:.2f}")
        col3.metric("SMA 50", f"${last_sma50:.2f}")
        col4.metric("Sinyal", signal)
        st.info(f"**Öneri:** {recommendation}")
        
        # Grafik
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Kapanış'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_10'], mode='lines', name='SMA 10'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], mode='lines', name='SMA 50'))
        fig.update_layout(title=f"{ticker} Fiyat Grafiği", xaxis_title="Tarih", yaxis_title="Fiyat", height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Son 10 gün
        st.subheader("Son 10 Gün Verileri")
        st.dataframe(df[['Close', 'SMA_10', 'SMA_50']].tail(10).round(2), use_container_width=True)

# ===================== YÜKSEK POTANSİYELLİ TAVAN HİSSELERİ =====================
def yuksek_potansiyel():
    st.subheader("🚀 Yüksek Potansiyelli Tavan Hisseleri")
    st.markdown("**Fintables Radar verilerine göre yüksek potansiyelli hisseler**")
    
    # Otomatik olarak verileri çek
    with st.spinner("Veriler çekiliyor..."):
        df, hata = get_fintables_radar()
    
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)
        st.success("Veriler başarıyla çekildi.")
        
        # Grafiksel gösterim (örneğin potansiyel dağılımı)
        if 'Potansiyel' in df.columns:
            try:
                # Potansiyel sütunundan sayısal değerleri çıkarmaya çalış
                df['Potansiyel_Num'] = df['Potansiyel'].str.replace('%', '').str.replace(',', '.').astype(float)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['Sembol'], y=df['Potansiyel_Num'], name='Potansiyel %'))
                fig.update_layout(title="Potansiyel Yüzdesi", xaxis_title="Hisse", yaxis_title="%")
                st.plotly_chart(fig, use_container_width=True)
            except:
                pass
        
        # Açıklama: neden yükselebileceği (örnek metin)
        st.markdown("""
        **📈 Yüksek Potansiyel Nedenleri:**
        - Fintables Radar verilerine göre seçilen hisseler, teknik ve temel göstergeler açısından yüksek potansiyele sahiptir.
        - Hacim artışı, fiyat hareketleri ve sektörel gelişmeler bu hisseleri öne çıkarmaktadır.
        - Detaylı analiz için lütfen ilgili hissenin teknik ve temel analizlerini inceleyiniz.
        """)
    else:
        st.error(f"Veri çekilemedi: {hata}")
        st.info("Fintables sayfasına doğrudan erişmek için 'Genel Sistem Verileri' sekmesini kullanabilirsiniz.")

# ===================== TEMEL ANALİZ =====================
def temel_analiz():
    st.subheader("🏢 Temel Analiz")
    ticker = st.text_input("Hisse Sembolü", value="AAPL", key="temel_ticker")
    analiz_btn = st.button("Temel Analizi Getir", key="temel_btn")
    
    if analiz_btn:
        if not ticker:
            st.warning("Lütfen bir hisse sembolü girin.")
            return
        with st.spinner("Veri çekiliyor..."):
            info = get_fundamental_data(ticker)
            if info is None or not info:
                st.error(f"'{ticker}' için temel veri bulunamadı.")
                return
            st.session_state['temel_info'] = info
            st.session_state['temel_ticker'] = ticker
    
    if 'temel_info' in st.session_state:
        info = st.session_state['temel_info']
        ticker = st.session_state['temel_ticker']
        
        # Verileri kategorilere ayır
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Getiri")
            st.write(f"**Fiyat Değişimi (Günlük):** {info.get('regularMarketChangePercent', 'N/A')}%")
            st.write(f"**52 Hafta Yüksek:** ${info.get('fiftyTwoWeekHigh', 'N/A')}")
            st.write(f"**52 Hafta Düşük:** ${info.get('fiftyTwoWeekLow', 'N/A')}")
            st.write(f"**Ortalama Hacim (10 gün):** {info.get('averageVolume10days', 'N/A')}")
            
            st.markdown("### 💰 Değerleme")
            st.write(f"**Piyasa Değeri:** ${info.get('marketCap', 'N/A'):,}")
            st.write(f"**F/K Oranı:** {info.get('trailingPE', 'N/A')}")
            st.write(f"**F/DD Oranı:** {info.get('priceToBook', 'N/A')}")
            st.write(f"**F/S Oranı:** {info.get('priceToSalesTrailing12Months', 'N/A')}")
            st.write(f"**Kazanç/Hisse:** ${info.get('trailingEps', 'N/A')}")
            st.write(f"**Defter Değeri/Hisse:** ${info.get('bookValue', 'N/A')}")
            
            st.markdown("### 📈 Karlılık")
            st.write(f"**ROE:** {info.get('returnOnEquity', 'N/A')*100 if info.get('returnOnEquity') else 'N/A'}%")
            st.write(f"**ROA:** {info.get('returnOnAssets', 'N/A')*100 if info.get('returnOnAssets') else 'N/A'}%")
            st.write(f"**Kar Marjı:** {info.get('profitMargins', 'N/A')*100 if info.get('profitMargins') else 'N/A'}%")
        
        with col2:
            st.markdown("### 🏦 Borçluluk")
            st.write(f"**Toplam Borç/Özsermaye:** {info.get('debtToEquity', 'N/A')}")
            st.write(f"**Likidite Oranı:** {info.get('currentRatio', 'N/A')}")
            st.write(f"**Fazla Borç Oranı:** {info.get('quickRatio', 'N/A')}")
            
            st.markdown("### 📊 Büyüme")
            st.write(f"**Gelir Büyümesi (Yıllık):** {info.get('revenueGrowth', 'N/A')*100 if info.get('revenueGrowth') else 'N/A'}%")
            st.write(f"**Kar Büyümesi (Yıllık):** {info.get('earningsGrowth', 'N/A')*100 if info.get('earningsGrowth') else 'N/A'}%")
            
            st.markdown("### 📋 Bilanço (Özet)")
            st.write(f"**Toplam Varlıklar:** ${info.get('totalAssets', 'N/A'):,}")
            st.write(f"**Toplam Borçlar:** ${info.get('totalDebt', 'N/A'):,}")
            st.write(f"**Özsermaye:** ${info.get('totalEquity', 'N/A'):,}")
            
            st.markdown("### 📊 Gelir Tablosu (Özet)")
            st.write(f"**Yıllık Gelir:** ${info.get('totalRevenue', 'N/A'):,}")
            st.write(f"**Yıllık Brüt Kar:** ${info.get('grossProfits', 'N/A'):,}")
            st.write(f"**Yıllık Net Gelir:** ${info.get('netIncomeToCommon', 'N/A'):,}")
            
            st.markdown("### 💵 Nakit Akım")
            st.write(f"**İşletme Nakit Akımı:** ${info.get('operatingCashflow', 'N/A'):,}")
            st.write(f"**Serbest Nakit Akım:** ${info.get('freeCashflow', 'N/A'):,}")
        
        # Ek açıklama
        st.info("Temel analiz verileri Yahoo Finance kaynağından alınmaktadır. Bazı veriler BIST hisseleri için eksik olabilir.")

# ===================== GENEL SİSTEM VERİLERİ =====================
def genel_sistem():
    st.subheader("🌐 Genel Sistem Verileri - Fintables Radar")
    st.markdown("Aşağıda Fintables.com hisse senedi radar sayfası görüntülenmektedir.")
    # iframe ile göster
    st.iframe("https://fintables.com/radar/hisse-senetleri", width=1100, height=700)

# ===================== ANA SAYFA =====================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Teknik Analiz", "🚀 Yüksek Potansiyelli Tavan Hisseleri", "🏢 Temel Analiz", "🌐 Genel Sistem Verileri"])

with tab1:
    teknik_analiz()

with tab2:
    yuksek_potansiyel()

with tab3:
    temel_analiz()

with tab4:
    genel_sistem()
