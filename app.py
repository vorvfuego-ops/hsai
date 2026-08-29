import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import borsapy as bp

# Sayfa Ayarları
st.set_page_config(page_title="BIST AI Analiz Sistemi", layout="wide")

# --- NAVİGASYON YÖNETİMİ ---
if "sayfa" not in st.session_state:
    st.session_state.sayfa = "Ana Sayfa"
if "secili_hisse" not in st.session_state:
    st.session_state.secili_hisse = "GARAN.IS"

def ana_sayfaya_don():
    st.session_state.sayfa = "Ana Sayfa"
    st.rerun()

def analiz_et(hisse):
    st.session_state.secili_hisse = hisse
    st.session_state.sayfa = "Analiz"
    st.rerun()

# --- YARDIMCI FONKSİYONLAR ---
@st.cache_data(ttl=300)
def bist_veri_cek(sembol, period="6mo"):
    """BIST verilerini borsapy ile çeker."""
    try:
        sembol = sembol.replace(".IS", "")
        hisse = bp.Ticker(sembol)
        df = hisse.history(period=period)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def getiri_hesapla(sembol):
    """1 saatlik verilerle yükseliş potansiyeli (yön) hesaplar."""
    try:
        sembol = sembol.replace(".IS", "")
        hisse = bp.Ticker(sembol)
        # 1 saatlik mumlar (Son 1 ay)
        df_1h = hisse.history(period="1mo", interval="1h")
        if df_1h.empty or len(df_1h) < 20:
            return 0, 0
        
        fiyat = df_1h['Close'].iloc[-1]
        # RSI (14 periyot)
        delta = df_1h['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        son_rsi = float(rsi.iloc[-1])
        
        # Potansiyel yön tahmini (0-100 arası yükseliş potansiyeli)
        potansiyel = max(0, min(100, (son_rsi - 40) * 2.5))
        getiri = ((fiyat / df_1h['Close'].iloc[0]) - 1) * 100
        
        return potansiyel, getiri
    except:
        return 0, 0

# --- UYGULAMA ---
if st.session_state.sayfa == "Ana Sayfa":
    st.title("📈 BIST AI Destekli Analiz Sistemi")
    st.caption("Türkiye piyasası için güncel verilerle yüksek potansiyelli hisseleri keşfedin.")
    
    POPULER = ["GARAN", "AKBNK", "ISCTR", "YKBNK", "THYAO", "ASELS", "EREGL", "BIMAS", "SISE", "SASA"]
    
    st.subheader("🔥 Getiri Potansiyeli Yüksek Hisseler")
    st.markdown("(1 saatlik verilerle son 1 aylık trend değerlendirmesi)")
    
    with st.spinner("BIST verileri analiz ediliyor..."):
        veriler = []
        for hisse in POPULER:
            pot, get = getiri_hesapla(hisse)
            veriler.append({
                "Hisse": hisse + ".IS", 
                "Yükseliş Potansiyeli (%)": round(pot, 1), 
                "1 Ay Getiri (%)": round(get, 2)
            })
        
        df_tablo = pd.DataFrame(veriler).sort_values(by="Yükseliş Potansiyeli (%)", ascending=False)
        
        st.dataframe(df_tablo, width='stretch', hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            secim = st.selectbox("Bir hisse seçin (Analiz etmek için):", options=df_tablo['Hisse'].tolist())
        with col2:
            if st.button("🚀 Seçilen Hisseleri Analiz Et"):
                analiz_et(secim)

elif st.session_state.sayfa == "Analiz":
    sembol = st.session_state.secili_hisse
    
    # Üst Bar
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Ana Sayfa"):
            ana_sayfaya_don()
    with col_title:
        st.title(f"📊 {sembol} Analizi")
    
    # Veri Çekme
    df = bist_veri_cek(sembol)
    
    if df.empty:
        st.error("Bu hisse için veri alınamadı. Lütfen daha sonra tekrar deneyin.")
        if st.button("Ana Sayfaya Dön"):
            ana_sayfaya_don()
    else:
        st.caption(f"Analiz Tarihi: {datetime.now().strftime('%d-%m-%Y %H:%M')} | Veri Kaynağı: BIST (borsapy)")
        
        # Güncel Fiyat ve Getiriler
        last_close = float(df['Close'].iloc[-1])
        getiri = getiri_hesapla(sembol)[1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Güncel Fiyat", f"₺{last_close:.2f}")
        col2.metric("Periyot Getirisi", f"%{getiri:.2f}")
        col3.metric("Yükseliş Potansiyeli", f"%{getiri_hesapla(sembol)[0]:.1f}")
        col4.metric("Al/Sat", "🟢 AL" if getiri_hesapla(sembol)[0] >= 50 else "🔴 SAT / BEKLE")
        
        # Profesyonel Grafik
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                     low=df['Low'], close=df['Close'], name='Fiyat'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='green')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='red')), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray', opacity=0.5), row=2, col=1)
        
        fig.update_layout(
            title=f'{sembol} BIST Grafiği',
            xaxis_rangeslider_visible=False,
            template='plotly_white',
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, width='stretch')
        
        # Kullanıcı Seçimi (Getiri Tahmini)
        st.divider()
        st.markdown("### 🎯 Kullanıcı Seçimi ile Yükseliş Hedefi")
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            hedef_yuzde = st.number_input("Hedef Getiri (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
        with col_sec2:
            if st.button("Hedefi Hesapla"):
                hedef_fiyat = last_close * (1 + hedef_yuzde / 100)
                st.success(f"**{sembol}** hissesinde hedef fiyat: ₺{hedef_fiyat:.2f} (Mevcut: ₺{last_close:.2f})")