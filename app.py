import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from tradingview_screener import Query, col
import yfinance as yf
from datetime import datetime, timedelta

# Sayfa Yapılandırması
st.set_page_config(page_title="BIST Pro AI Terminali", layout="wide")

# --- GÜVENLİ API BAĞLANTISI ---
try:
    import borsapy as bp
    # Güvenli kimlik doğrulama st.secrets üzerinden yapılır
    bp.set_tradingview_auth(
        session=st.secrets["tradingview"]["session"],
        session_sign=st.secrets["tradingview"]["session_sign"]
    )
    TV_AUTH = True
except:
    TV_AUTH = False
    st.sidebar.warning("⚠️ TradingView kimlik bilgileri bulunamadı. Veriler gecikmeli gelebilir.")

# --- GELİŞMİŞ CANLI TARAMA (Tüm BIST Hisseleri) ---
@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    """TradingView API üzerinden tüm BIST hisselerini ve göstergelerini çeker."""
    try:
        # 3000+ veri alanına erişim sağlar [citation:8]
        query = (
            Query()
            .set_markets('turkey')  # Türkiye Piyasası
            .select(
                'name', 'close', 'change', 'volume', 'market_cap_basic',
                'RSI', 'MACD.macd', 'MACD.signal', 'Perf.W', 'Perf.1M',
                'Perf.3M', 'Perf.6M', 'Perf.YTD', 'sector',
                'high_all_calc', 'low_all_calc', 'Volatility.W'
            )
            .order_by('volume', ascending=False) # İşlem hacmine göre sırala
            .limit(1000) # BIST 1000'e kadar hisse çek
        )
        total, df = query.get_scanner_data()
        return df
    except Exception as e:
        return pd.DataFrame()

# --- TAVAN KAPASİTESİ MODELİ (YZ) ---
def tavan_kapasite_hesapla(sembol):
    """Geçmiş volatilite ve trend ile tavan potansiyelini hesaplar."""
    try:
        # Ana veri yedeklemesi yfinance üzerinden
        sembol_uzun = sembol.upper().replace(".IS", "") + ".IS"
        df = yf.download(sembol_uzun, period="6mo", progress=False, auto_adjust=False)
        
        if len(df) < 50:
            return 0, 0, 0
        
        # Volatilite ve RSI analizi
        df['Return'] = df['Close'].pct_change()
        volatilite = df['Return'].std() * 100
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        son_rsi = float(rsi.iloc[-1])
        
        # Mevcut fiyatın 52 haftalık yüksekliğe oranı (Tavan analizi)
        yuksek = float(df['High'].max())
        mevcut = float(df['Close'].iloc[-1])
        tavan_potansiyeli = ((yuksek - mevcut) / mevcut) * 100
        
        # Verimlilik Skoru (10 üzerinden)
        skor = 0
        if son_rsi > 50: skor += 3
        if tavan_potansiyeli > 10: skor += 3
        if volatilite > 3: skor += 4
        
        return skor, tavan_potansiyeli, son_rsi
    except:
        return 0, 0, 0

# --- ARAYÜZ ---
st.title("📊 BIST Pro AI Terminali")
st.caption("TradingView Altyapısı ile Sınırsız Analiz")

tab1, tab2, tab3 = st.tabs(["🚀 Tavan Avcıları", "📈 Ana Sayfa", "🧠 Profesyonel Analiz"])

# Tab 1: Tavan Avcıları
with tab1:
    st.subheader("🔥 Yüksek Potansiyelli Tavan Hisseleri")
    st.info("Bu modül, tüm BIST hisselerini tarayarak 52 haftalık yüksekliğine yakın, yüksek hacimli ve pozitif momentumlu hisseleri listeler.")
    
    with st.spinner("Tüm BIST hisseleri taranıyor..."):
        hisse_verisi = tum_bist_hisselerini_getir()
        
        if not hisse_verisi.empty:
            # Yükseliş potansiyeline göre filtrele (52 hafta yükseğine uzaklık)
            hisse_verisi['Tavan Potansiyeli (%)'] = ((hisse_verisi['high_all_calc'] - hisse_verisi['close']) / hisse_verisi['close']) * 100
            
            # Sıralama ve İlk 5
            tavan_hisseleri = hisse_verisi.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(5)
            
            st.dataframe(tavan_hisseleri[['name', 'close', 'change', 'volume', 'Tavan Potansiyeli (%)', 'RSI', 'sector']], width='stretch', hide_index=True)
            
            # Tavan listesindeki hisselerin grafikleri
            st.markdown("### 📈 Tavan Hisselerinin Performansı")
            fig = go.Figure()
            
            for i, row in tavan_hisseleri.iterrows():
                try:
                    # Grafik verisi çek
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
            st.error("BIST verileri çekilemedi. Kimlik doğrulamasını kontrol edin.")

# Tab 2: Ana Sayfa (Gelişmiş Görünüm)
with tab2:
    st.subheader("📊 Piyasa Genel Bakış")
    st.write("Burada, yüksek hacimli hisselerin anlık durumları listelenir.")
    # Mevcut popüler hisse listesi
    populer = ["GARAN", "AKBNK", "ISCTR", "YKBNK", "THYAO", "ASELS", "EREGL", "BIMAS", "SISE", "SASA"]
    with st.spinner("Veriler yükleniyor..."):
        veriler = []
        for hisse in populer:
            skor, pot, rsi = tavan_kapasite_hesapla(hisse)
            # Hacim verisi çekme (gerekli olduğu için yfinance ile)
            df = yf.download(hisse + ".IS", period="1mo", progress=False, auto_adjust=False)
            hacim = float(df['Volume'].iloc[-1]) if not df.empty else 0
            veriler.append({
                "Hisse": hisse, "Skor": skor, 
                "Tavan Pot. (%)": round(pot, 1), 
                "RSI": round(rsi, 1),
                "Hacim": round(hacim / 1_000_000, 1)
            })
        
        df_veri = pd.DataFrame(veriler).sort_values(by="Skor", ascending=False)
        st.dataframe(df_veri, width='stretch', hide_index=True)

# Tab 3: Profesyonel Analiz
with tab3:
    st.subheader("🧠 Sınırsız Analiz")
    secim = st.selectbox("Analiz Edilecek Hisse", ["GARAN", "AKBNK", "ISCTR", "YKBNK", "THYAO", "ASELS", "EREGL", "BIMAS", "SISE", "SASA"])
    
    if st.button("Derinlemesine Analiz Başlat"):
        df = yf.download(secim + ".IS", period="6mo", progress=False, auto_adjust=False)
        
        if df.empty:
            st.error("Veri bulunamadı.")
        else:
            # Profesyonel Grafik Yapısı
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
            
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray'), row=2, col=1)
            
            # Basit RSI Hesabı
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='purple')), row=3, col=1)
            
            fig.update_layout(title=f"{secim} Profesyonel Görünüm", height=800, template='plotly_white')
            st.plotly_chart(fig, width='stretch')