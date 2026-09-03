import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import time
import requests

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="AI Destekli Hisse Analiz Sistemi",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FINTABLES TARZI CSS (Menü ve Renkler İçin) ---
st.markdown("""
<style>
    /* Genel Arka Plan ve Yazı Rengi */
    .stApp {
        background-color: #121212;
        color: #E0E0E0;
    }
    
    /* Fintables Menü Çubuğu (Üst Sekmeler) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #1E1E1E;
        border-bottom: 1px solid #333;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1E1E1E;
        color: #A0A0A0;
        border-radius: 0;
        padding: 10px 20px;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2C2C2C !important;
        color: #FFFFFF !important;
        border-bottom: 3px solid #FF9900; /* Fintables Turuncusu */
    }
    
    /* Sol Menü (Sidebar) */
    section[data-testid="stSidebar"] {
        background-color: #1E1E1E;
        border-right: 1px solid #333;
    }
    section[data-testid="stSidebar"] .stButton button {
        background-color: transparent;
        color: #FFFFFF;
        border: none;
        text-align: left;
        width: 100%;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background-color: #2C2C2C;
        color: #FF9900;
    }
    
    /* Tablo Başlıkları */
    thead tr th:first-child {display:none}
    thead tr th {
        background-color: #2C2C2C !important;
        color: #FF9900 !important;
        font-weight: bold;
    }
    tbody tr:nth-child(even) {
        background-color: #1E1E1E;
    }
    tbody tr:hover {
        background-color: #333333;
    }
    
    /* Başlıklar */
    h1, h2, h3 {
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

# --- BIST HİSSE LİSTESİ (İstediğiniz kadar ekleyebilirsiniz) ---
# Örnek olarak BIST 100 listesi eklendi. Tüm hisseler için bu listeyi uzatabilirsiniz.
BIST_TICKERS = [
    "THYAO", "ASELS", "GARAN", "AKBNK", "YKBNK", "ISATR", "EREGL", "SISE", "KCHOL", "SAHOL",
    "TUPRS", "PGSUS", "TAVHL", "BIMAS", "MGROS", "SOKM", "FROTO", "TOASO", "TTRAK", "KRDMD",
    "KOZAL", "KOZAA", "GUBRF", "HEKTS", "TKFEN", "ENKAI", "GOZDE", "ISGYO", "KONTR", "ALARK"
    # "A1CAP", "A1YEN", "AAGYO", "ACSEL", "ADEL" ... buraya tüm istediğinizi ekleyin
]

# --- YAPAY ZEKA DESTEKLİ HESAPLAMA MOTORU (Fintables Benzeri) ---
@st.cache_data(ttl=600) # 10 dakika boyunca veriyi önbellekte tutar
def get_radar_data():
    """Tüm hisselerin verilerini çeker ve Fintables tablosundaki gibi hesaplar."""
    rows = []
    for ticker in BIST_TICKERS:
        try:
            # Verileri çek (Son 1 yıl)
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty:
                continue
            
            # Güncel veriler
            last_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            
            # Günlük Değişim %
            daily_change = ((last_price - prev_price) / prev_price) * 100
            
            # Hacim
            volume = df['Volume'].iloc[-1] / 1000000  # Milyon cinsinden
            
            # Getiri Hesaplamaları (1 hafta, 1 ay, 3 ay, 6 ay, Yılbaşı, 1 yıl)
            def get_return(days):
                if len(df) > days:
                    past_price = df['Close'].iloc[-days-1]
                    return ((last_price - past_price) / past_price) * 100
                return np.nan
            
            ret_1w = get_return(5)
            ret_1m = get_return(21)
            ret_3m = get_return(63)
            ret_6m = get_return(126)
            
            # Yılbaşından bugüne
            year_start = datetime(datetime.now().year, 1, 1)
            year_start_data = df[df.index >= year_start]
            if not year_start_data.empty:
                ytd_return = ((last_price - year_start_data['Close'].iloc[0]) / year_start_data['Close'].iloc[0]) * 100
            else:
                ytd_return = np.nan

            ret_1y = get_return(252)
            ret_3y = np.nan
            ret_5y = np.nan
            
            rows.append({
                "Hisse": ticker,
                "Fiyat": round(last_price, 2),
                "Gün %": round(daily_change, 2),
                "Hacim": round(volume, 2),
                "Getiri % (Son 1 hafta)": round(ret_1w, 2) if not np.isnan(ret_1w) else "N/A",
                "Getiri % (Son 1 ay)": round(ret_1m, 2) if not np.isnan(ret_1m) else "N/A",
                "Getiri % (Son 3 ay)": round(ret_3m, 2) if not np.isnan(ret_3m) else "N/A",
                "Getiri % (Son 6 ay)": round(ret_6m, 2) if not np.isnan(ret_6m) else "N/A",
                "Getiri % (Yılbaşından bugüne)": round(ytd_return, 2) if not np.isnan(ytd_return) else "N/A",
                "Getiri % (Son 1 yıl)": round(ret_1y, 2) if not np.isnan(ret_1y) else "N/A",
                "Getiri % (Son 3 yıl)": ret_3y,
                "Getiri % (Son 5 yıl)": ret_5y
            })
        except Exception:
            continue
    
    return pd.DataFrame(rows)

# --- BÖLÜM 1: TEKNİK ANALİZ ---
def teknik_analiz():
    st.subheader("📊 Teknik Analiz")
    ticker = st.text_input("Hisse Sembolü", value="THYAO", key="teknik_ticker_input").upper().strip()
    
    if st.button("Analiz Et", key="analiz_buton"):
        if not ticker:
            st.error("Lütfen bir sembol girin.")
            return
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty:
                st.error(f"'{ticker}' için veri bulunamadı.")
                return
            st.session_state['teknik_df'] = df
        except Exception as e:
            st.error(f"Veri çekilirken hata oluştu: {e}")
    
    if 'teknik_df' in st.session_state:
        df = st.session_state['teknik_df']
        st.write(f"**{ticker}** Son 6 Ay Verileri:")
        st.dataframe(df.tail(20), width='stretch')
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Son Fiyat", f"{df['Close'].iloc[-1]:.2f}")
        with col2:
            st.metric("Günlük Değişim", f"{(df['Close'].iloc[-1] / df['Close'].iloc[-2] - 1) * 100:.2f}%")
        with col3:
            st.metric("Hacim", f"{df['Volume'].iloc[-1]:,.0f}")
        st.line_chart(df['Close'], width='stretch')

# --- BÖLÜM 2: YÜKSEK POTANSİYELLİ TAVAN HİSSELER ---
def yuksek_potansiyel():
    st.subheader("🚀 Yüksek Potansiyelli Tavan Hisseler")
    df = get_radar_data()
    
    if df.empty:
        st.info("Veri alınamadı. Lütfen BIST_TICKERS listesini kontrol edin.")
        return
    
    # YZ Modeli: Tavan Hisseleri Tespit Et (Günlük %10 ve üzeri artış)
    df['Gün % Sayı'] = pd.to_numeric(df['Gün %'], errors='coerce')
    tavanlar = df[df['Gün % Sayı'] >= 9.9]
    
    if not tavanlar.empty:
        st.success(f"🔔 Şu an {len(tavanlar)} adet tavan hisse var!")
        st.dataframe(tavanlar, width='stretch')
    else:
        st.info("Şu an tavan hisse bulunmuyor. (Veriler 10 dakikada bir güncellenir)")
    
    st.subheader("📋 Tüm Radar Verileri")
    # Fintables Stilinde Renkli Tablo
    st.dataframe(df.drop(columns=['Gün % Sayı']), width='stretch')

# --- BÖLÜM 3: TEMEL ANALİZ ---
def temel_analiz():
    st.subheader("📈 Temel Analiz")
    st.write("Temel analiz verileri (F/K, PD/DD vb.) burada gösterilecektir.")

# --- BÖLÜM 4: GENEL SİSTEM VERİLERİ - FINTABLES KLONU ---
def genel_sistem_verileri():
    st.subheader("🌐 Genel Sistem Verileri - Fintables Benzeri Arayüz")
    
    # Fintables Menü Çubuğu Simülasyonu (Tabs)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Getiri", "Değerleme", "Karlılık", "Büyüme", "Bilanço", "Gelir Tablosu", "Nakit Akım"])
    
    # Sol Menü Simülasyonu
    with st.sidebar:
        st.header("📋 Menü")
        if st.button("🔍 Radar"):
            st.session_state['menu'] = "Radar"
        if st.button("📈 Hisse"):
            st.session_state['menu'] = "Hisse"
        if st.button("🌍 Endeksler"):
            st.session_state['menu'] = "Endeksler"
        if st.button("💎 VIP"):
            st.session_state['menu'] = "VIP"
        if st.button("🪙 Kripto"):
            st.session_state['menu'] = "Kripto"
        st.markdown("---")
        st.caption("Veriler herkese açık kaynaklardan (yfinance) çekilir ve Fintables mantığıyla hesaplanır.")
    
    # Veriyi Çek
    df = get_radar_data()
    
    # Fintables Getiri Tablosu
    with tab1:
        st.write("### Getiri Tablosu")
        # Sıralama (Örneğin Günlük Değişime göre)
        if not df.empty:
            df_sorted = df.sort_values(by="Gün %", ascending=False)
            st.dataframe(df_sorted, width='stretch')
        else:
            st.info("Veri bekleniyor...")

    with tab2:
        st.info("Değerleme menüsü için F/K, PD/DD gibi veriler yfinance'ten çekilebilir. Bu bölüm için ek kod gerekir.")
    with tab3:
        st.info("Karlılık menüsü için Fintables API'sine bağlanmanız önerilir. (F12 -> Network)")
    with tab4:
        st.info("Büyüme menüsü simüle edilmiştir.")
    with tab5:
        st.info("Bilanço menüsü simüle edilmiştir.")
    with tab6:
        st.info("Gelir Tablosu menüsü simüle edilmiştir.")
    with tab7:
        st.info("Nakit Akım menüsü simüle edilmiştir.")

# --- ANA AKIŞ ---
def main():
    st.title("📊 AI Destekli Hisse Analiz Sistemi")
    
    # Sekmeler
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Teknik Analiz", "🚀 Yüksek Potansiyel", "📈 Temel Analiz", "🌐 Genel Sistem Verileri"])
    
    with tab1:
        teknik_analiz()
    with tab2:
        yuksek_potansiyel()
    with tab3:
        temel_analiz()
    with tab4:
        genel_sistem_verileri()

if __name__ == "__main__":
    main()
