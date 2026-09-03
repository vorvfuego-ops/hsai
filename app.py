import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from datetime import datetime, timedelta
import time
import json
from typing import Optional

# -----------------------------------------------------------------------------
# Sayfa ayarları
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Destekli Hisse Analiz Sistemi",
    page_icon="📈",
    layout="wide"
)

# -----------------------------------------------------------------------------
# Fintables API yardımcı fonksiyonları
# -----------------------------------------------------------------------------
FINTABLES_API_BASE = "https://fintables.com/api"  # Gerçek endpoint'i kontrol edin

def fintables_api_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Fintables API'den veri çeker."""
    url = f"{FINTABLES_API_BASE}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Fintables API çağrısı başarısız: {e}")
        return None

def get_fintables_radar_data():
    """Radar sayfasındaki hisse verilerini çeker (örnek endpoint)."""
    # Gerçek endpoint'i bulmak için tarayıcı Network sekmesini kullanın.
    # Örnek: /radar?type=all&sort=...
    data = fintables_api_get("radar", {"type": "all", "sort": "popular"})
    if data and isinstance(data, dict):
        return pd.DataFrame(data.get("data", []))
    return pd.DataFrame()

# -----------------------------------------------------------------------------
# Teknik Analiz (hata düzeltilmiş)
# -----------------------------------------------------------------------------
def teknik_analiz():
    st.subheader("📊 Teknik Analiz")
    
    # Widget anahtarı ile session_state çakışmasını önlemek için farklı key kullanıyoruz
    ticker = st.text_input("Hisse Sembolü", value="THYAO", key="teknik_ticker_input").upper().strip()
    
    if st.button("Analiz Et", key="teknik_analiz_btn"):
        if not ticker:
            st.error("Lütfen bir hisse sembolü girin.")
            return
        
        try:
            # Veriyi çek
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty:
                st.error(f"'{ticker}' için veri bulunamadı.")
                return
            # Session state'e veriyi kaydet (widget anahtarı değil)
            st.session_state['teknik_df'] = df
        except Exception as e:
            st.error(f"Veri çekilirken hata oluştu: {e}")
            return
    
    if 'teknik_df' in st.session_state:
        df = st.session_state['teknik_df']
        st.write(f"**{ticker}** son 6 ay verileri:")
        st.dataframe(df.tail(20), width='stretch')
        
        # Basit teknik göstergeler
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Son Fiyat", f"{df['Close'].iloc[-1]:.2f}")
        with col2:
            st.metric("Günlük Değişim", f"{(df['Close'].iloc[-1] / df['Close'].iloc[-2] - 1) * 100:.2f}%")
        with col3:
            st.metric("Hacim", f"{df['Volume'].iloc[-1]:,.0f}")
        
        # Grafik
        st.line_chart(df['Close'], width='stretch')

# -----------------------------------------------------------------------------
# Yüksek Potansiyelli Tavan Hisseler (Selenium yerine API)
# -----------------------------------------------------------------------------
def yuksek_potansiyel():
    st.subheader("🚀 Yüksek Potansiyelli Tavan Hisseler")
    st.write("Fintables Radar verilerinden yüksek potansiyelli hisseler (otomatik güncellenir)")
    
    if st.button("Verileri Yenile", key="refresh_high_potential"):
        st.session_state['high_potential_df'] = get_fintables_radar_data()
    
    if 'high_potential_df' not in st.session_state:
        st.session_state['high_potential_df'] = get_fintables_radar_data()
    
    df = st.session_state['high_potential_df']
    if df.empty:
        st.info("Veri alınamadı. Lütfen daha sonra tekrar deneyin veya API endpoint'ini kontrol edin.")
        st.info("Alternatif olarak 'Genel Sistem Verileri' sekmesinden Fintables sayfası doğrudan incelenebilir.")
        return
    
    st.dataframe(df, width='stretch')
    
    # Tavan hisseleri filtreleme (örnek: %10 üzeri artış)
    if 'Change' in df.columns:
        tavanlar = df[df['Change'] >= 10]
        if not tavanlar.empty:
            st.success(f"Toplam {len(tavanlar)} tavan hisse bulundu:")
            st.dataframe(tavanlar, width='stretch')

# -----------------------------------------------------------------------------
# Temel Analiz
# -----------------------------------------------------------------------------
def temel_analiz():
    st.subheader("📈 Temel Analiz")
    st.info("Bu bölüm temel analiz verilerini göstermek için tasarlanmıştır.")
    # Buraya kendi temel analiz kodunuzu ekleyebilirsiniz.

# -----------------------------------------------------------------------------
# Genel Sistem Verileri - Fintables Radar (API tabanlı, menüler dahil)
# -----------------------------------------------------------------------------
def genel_sistem_verileri():
    st.subheader("🌐 Genel Sistem Verileri - Fintables Radar")
    st.write("Aşağıda Fintables.com'un sunduğu menüler ve veriler doğrudan API'den çekilerek gösterilir.")
    
    # Menü simülasyonu (Fintables'taki sekmeler)
    menus = ["Radar", "Hisse", "Endeksler", "VIP", "Kripto", "Aracı Kurumlar", "Sektörler", "Analizler", "Trading"]
    selected_menu = st.radio("Menü Seçimi", menus, horizontal=True, key="fintables_menu")
    
    # Menüye göre veri çekme (örnek endpointler - gerçek endpoint'leri kullanın)
    endpoint_map = {
        "Radar": "radar",
        "Hisse": "hisse",
        "Endeksler": "endeks",
        "VIP": "vip",
        "Kripto": "kripto",
        "Aracı Kurumlar": "aracikurum",
        "Sektörler": "sektor",
        "Analizler": "analiz",
        "Trading": "trading"
    }
    
    endpoint = endpoint_map.get(selected_menu, "radar")
    df = fintables_api_get(endpoint)  # Basit get, parametreleri kendinize göre ayarlayın
    
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        st.info(f"'{selected_menu}' menüsü için veri alınamadı. Lütfen API endpoint'ini doğru ayarlayın.")
        # Burada varsayılan olarak örnek veri gösterelim
        data = {
            "Hisse": ["A1CAP", "A1YEN", "AAGYO", "ACSEL", "ADEL"],
            "Fiyat": [9.55, 2.63, 12.88, 113.30, 31.62],
            "Gün": [-1.95, -0.75, 1.71, -0.87, -0.88],
            "Hacim": [8.25, 4.89, 19.75, 2.84, 29.58],
            "Getiri 5G": [-10.44, -6.41, 7.79, -5.82, -14.83]
        }
        df = pd.DataFrame(data)
    
    # Veri tablosu
    st.dataframe(df, width='stretch')
    
    # İsteğe bağlı alt menüler
    if selected_menu == "Radar":
        st.write("**Alt Menüler:** Tüm Hisseler, Endeksler, VIP, Kripto, Aracı Kurumlar, Sektörler, Analizler, Trading")
        alt_menus = st.selectbox("Alt Menü Seçin", ["Tüm Hisseler", "Endeksler", "VIP", "Kripto", "Aracı Kurumlar", "Sektörler"])
        st.write(f"Seçilen alt menü: {alt_menus} - Burada ilgili veriler listelenir.")
    
    # Güncelleme bilgisi
    st.caption(f"Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

# -----------------------------------------------------------------------------
# Ana uygulama
# -----------------------------------------------------------------------------
def main():
    st.title("📊 AI Destekli Hisse Analiz Sistemi")
    
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
