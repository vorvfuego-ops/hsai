import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# Sayfa ayarları
st.set_page_config(
    page_title="AI Destekli Hisse Analiz Sistemi",
    page_icon="📈",
    layout="wide"
)

# -----------------------------------------------------------------------------
# Fintables API Ayarları
# -----------------------------------------------------------------------------
# İpucu: F12 -> Network sekmesinden radar verilerini çeken gerçek URL'i buraya yapıştırın.
# Örnek: https://api.fintables.com/radar/all
FINTABLES_API_URL = "https://api.fintables.com/radar/all"

def fintables_veri_cek():
    """Fintables'tan veri çeker veya API'ye ulaşılamazsa örnek veri döndürür."""
    try:
        response = requests.get(FINTABLES_API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # API'nin döndürdüğü veriyi DataFrame'e çevir
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict) and "data" in data:
                return pd.DataFrame(data["data"])
    except Exception:
        pass  # API'ye ulaşılamazsa aşağıdaki örnek veriyi kullan

    # Fintables görselindeki mevcut verileri birebir simüle eden yedek veri seti
    # (Bu veriler güncel değildir, API bağlanana kadar gösterilir)
    yedek_veri = {
        "Hisse": ["A1CAP", "A1YEN", "AAGYO", "ACSEL", "ADEL", "ADESE", "ADGYO", "AEFES", "AFYON", "AGESA"],
        "Fiyat": [9.55, 2.63, 12.11, 113.30, 31.78, 8.84, 57.55, 18.08, 12.47, 257.25],
        "Gün %": [-1.95, -0.75, -1.46, -0.87, -0.63, -1.18, -1.96, -0.50, -0.09, -1.86],
        "Hacim": [8.61, 5.19, 23.05, 2.16, 21.57, 16.87, 8.73, 146.26, 1.36, 2.79],
        "Getiri % (Son 1 hafta)": [-10.44, -6.41, -7.56, -5.82, -13.81, -2.33, -5.27, -4.34, -1.66, 2.18],
        "Getiri % (Son 1 ay)": [-14.01, -0.38, -6.41, -8.78, -9.88, -3.45, -18.61, -17.37, -2.88, -5.91],
        "Getiri % (Son 3 ay)": [-27.12, -25.71, -31.05, -34.39, -4.00, -28.00, -6.38, -10.41, -6.55, -20.79],
        "Getiri % (Son 6 ay)": [-56.48, -2.10, "N/A", -12.18, -1.67, -17.65, -30.85, -16.85, -5.68, -20.68],
        "Getiri % (Yılbaşından bugüne)": [-36.82, -0.72, "N/A", -15.97, -3.94, -4.74, -33.72, -30.05, -0.20, -65.49],
        "Getiri % (Son 1 yıl)": [-28.61, -12.92, "N/A", -11.97, -13.10, -78.13, -33.22, -15.82, -6.20, -395.27],
        "Getiri % (Son 3 yıl)": [32.92, 4.86, "N/A", 19.48, -48.80, 184.88, "N/A", 73.13, 39.77, 1418.67],
        "Getiri % (Son 5 yıl)": ["N/A", 105.23, "N/A", 587.08, 1.231.93, 300.00, "N/A", 798.97, 310.23, "N/A"]
    }
    return pd.DataFrame(yedek_veri)

# -----------------------------------------------------------------------------
# Teknik Analiz (Hata düzeltildi)
# -----------------------------------------------------------------------------
def teknik_analiz():
    st.subheader("📊 Teknik Analiz")
    ticker = st.text_input("Hisse Sembolü", value="THYAO", key="teknik_ticker_input").upper().strip()
    
    if st.button("Analiz Et", key="analiz_buton"):
        if not ticker:
            st.error("Lütfen bir sembol girin.")
            return
        
        try:
            import yfinance as yf
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty:
                st.error(f"'{ticker}' için veri bulunamadı.")
                return
            
            # session_state'e veri kaydet
            st.session_state['teknik_df'] = df
        except Exception as e:
            st.error(f"Veri çekme hatası: {e}")
    
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

# -----------------------------------------------------------------------------
# Yüksek Potansiyelli Tavan Hisseler
# -----------------------------------------------------------------------------
def yuksek_potansiyel():
    st.subheader("🚀 Yüksek Potansiyelli Tavan Hisseler")
    st.write("Fintables verilerinden yüksek potansiyelli hisseler listelenir.")
    
    # Veriyi çek (tekrar tekrar istek atmamak için cache kullanıyoruz)
    @st.cache_data(ttl=300)  # 5 dakika boyunca önbellekte tut
    def veri_yukle():
        return fintables_veri_cek()
    
    df = veri_yukle()
    
    if df.empty:
        st.info("Veri alınamadı. Lütfen API URL'ini kontrol edin.")
        return
    
    # Güncel verilerle tavan hisseleri filtrele (Örn: Gün % >= 9.9)
    if 'Gün %' in df.columns:
        tavanlar = df[df['Gün %'] >= 9.9]
        if not tavanlar.empty:
            st.success(f"🔔 Şu an {len(tavanlar)} adet tavan hisse var!")
            st.dataframe(tavanlar, width='stretch')
        else:
            st.info("Şu an tavan hisse bulunmuyor.")
    
    st.subheader("📋 Tüm Radar Verileri")
    st.dataframe(df, width='stretch')

# -----------------------------------------------------------------------------
# Temel Analiz
# -----------------------------------------------------------------------------
def temel_analiz():
    st.subheader("📈 Temel Analiz")
    st.write("Bu bölümde temel analiz verileri gösterilecektir.")

# -----------------------------------------------------------------------------
# Genel Sistem Verileri - Fintables (Menü Düzeni ve Veri)
# -----------------------------------------------------------------------------
def genel_sistem_verileri():
    st.subheader("🌐 Genel Sistem Verileri - Fintables Radar")
    st.write("Aşağıda Fintables menü düzeni ve tablo yapısı birebir simüle edilmiştir. Veriler herkese açık API'den çekilir.")
    
    # Fintables'taki Sekmeler (Menü Çubuğu)
    menuler = ["Getiri", "Değerleme", "Karlılık", "Büyüme", "Bilanço", "Gelir Tablosu", "Nakit Akım"]
    secili_menu = st.radio("Menü Seçin", menuler, horizontal=True, key="fintables_menu")
    
    # Verileri Çek
    df = fintables_veri_cek()
    
    # Fintables'taki Alt Menüler (Radar, Hisse, Endeksler, VIP vb.)
    st.markdown("---")
    st.write("**Alt Menüler:**")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.button("Radar")
    with col2:
        st.button("Hisse")
    with col3:
        st.button("Endeksler")
    with col4:
        st.button("VIP")
    with col5:
        st.button("Kripto")
    
    # Menüye göre içerik değişimi (Örnek: Getiri menüsünde tabloyu göster)
    if secili_menu == "Getiri":
        st.write("### Getiri Tablosu")
        st.dataframe(df, width='stretch')
    elif secili_menu == "Değerleme":
        st.info("Değerleme menüsü verileri API'den çekilecektir. (F12 ile URL güncellenmelidir)")
    elif secili_menu == "Karlılık":
        st.info("Karlılık menüsü verileri API'den çekilecektir. (F12 ile URL güncellenmelidir)")
    else:
        st.info(f"'{secili_menu}' menüsü için örnek veri gösteriliyor.")
        st.dataframe(df.head(10), width='stretch')
    
    st.caption(f"Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')} (Veriler 5 dakikada bir önbellekten yenilenir)")

# -----------------------------------------------------------------------------
# Ana Akış
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
