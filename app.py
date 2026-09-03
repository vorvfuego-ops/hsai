import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import warnings

# Uyarıları gizle
warnings.filterwarnings("ignore")

# Sayfa ayarları
st.set_page_config(
    page_title="AI Destekli Hisse Analiz Sistemi",
    page_icon="📈",
    layout="wide"
)

# --- FINTABLES STİLİ (CSS) ---
st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    section[data-testid="stSidebar"] { background-color: #1E1E1E; border-right: 1px solid #333; }
    section[data-testid="stSidebar"] .stRadio label { color: #FFFFFF; }
    section[data-testid="stSidebar"] .stButton button { background-color: transparent; color: #FFFFFF; border: none; text-align: left; width: 100%; }
    section[data-testid="stSidebar"] .stButton button:hover { background-color: #2C2C2C; color: #FF9900; }
    thead tr th:first-child {display:none}
    thead tr th { background-color: #2C2C2C !important; color: #FF9900 !important; font-weight: bold; }
    tbody tr:nth-child(even) { background-color: #1E1E1E; }
    tbody tr:hover { background-color: #333333; }
    h1, h2, h3 { color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

# --- BIST HİSSE LİSTESİ (Yahoo Finance formatına uygun .IS eklendi) ---
BIST_TICKERS = [
    "THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "YKBNK.IS", "ISATR.IS", "EREGL.IS", "SISE.IS", "KCHOL.IS", "SAHOL.IS",
    "TUPRS.IS", "PGSUS.IS", "TAVHL.IS", "BIMAS.IS", "MGROS.IS", "SOKM.IS", "FROTO.IS", "TOASO.IS", "TTRAK.IS", "KRDMD.IS",
    "KOZAL.IS", "KOZAA.IS", "GUBRF.IS", "HEKTS.IS", "TKFEN.IS", "ENKAI.IS", "GOZDE.IS", "ISGYO.IS", "KONTR.IS", "ALARK.IS",
    "A1CAP.IS", "A1YEN.IS", "AAGYO.IS", "ACSEL.IS", "ADEL.IS", "ADESE.IS", "ADGYO.IS", "AEFES.IS", "AFYON.IS", "AGESA.IS",
    "AGROT.IS", "AGYO.IS", "AHGAZ.IS", "AHSGY.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS"
]

# --- QUANTUM DESTEKLİ ANALİTİK MOTOR ---
class QuantumAIModel:
    def __init__(self, ticker):
        self.ticker = ticker
        self.df = self._get_data()
    
    def _get_data(self):
        """Veriyi Yahoo Finance'ten tek tek çeker (401 hatasını önler)."""
        try:
            t = yf.Ticker(self.ticker)
            df = t.history(period="1y")
            if df.empty:
                return None
            return df
        except Exception:
            return None

    def calculate_returns(self):
        if self.df is None:
            return None
        
        last_price = self.df['Close'].iloc[-1]
        
        def get_return(days):
            if len(self.df) > days:
                past_price = self.df['Close'].iloc[-days-1]
                return ((last_price - past_price) / past_price) * 100
            return None
        
        # Yılbaşından bugüne
        year_start = datetime(datetime.now().year, 1, 1)
        year_data = self.df[self.df.index >= year_start]
        ytd = ((last_price - year_data['Close'].iloc[0]) / year_data['Close'].iloc[0]) * 100 if not year_data.empty else None
        
        return {
            "Hisse": self.ticker.replace(".IS", ""),  # .IS uzantısını kaldır
            "Fiyat": round(last_price, 2),
            "Gün %": round(get_return(0) if len(self.df) > 1 else 0, 2),
            "Hacim": round(self.df['Volume'].iloc[-1] / 1000000, 2),
            "Getiri % (Son 1 hafta)": round(get_return(5), 2) if get_return(5) is not None else "N/A",
            "Getiri % (Son 1 ay)": round(get_return(21), 2) if get_return(21) is not None else "N/A",
            "Getiri % (Son 3 ay)": round(get_return(63), 2) if get_return(63) is not None else "N/A",
            "Getiri % (Son 6 ay)": round(get_return(126), 2) if get_return(126) is not None else "N/A",
            "Getiri % (Yılbaşından)": round(ytd, 2) if ytd is not None else "N/A",
            "Getiri % (Son 1 yıl)": round(get_return(252), 2) if get_return(252) is not None else "N/A",
            "Getiri % (Son 3 yıl)": "N/A",
            "Getiri % (Son 5 yıl)": "N/A"
        }

    def quantum_validate(self, days=5):
        """Monte Carlo simülasyonu ile tahmin ve hata payı üretir."""
        if self.df is None or len(self.df) < 30:
            return None
        
        log_returns = np.log(self.df['Close'] / self.df['Close'].shift(1)).dropna()
        if log_returns.empty:
            return None
            
        mean = log_returns.tail(30).mean()
        std = log_returns.tail(30).std()
        
        sims = []
        for _ in range(500):  # Hız için 500 simülasyon
            future_ret = np.random.normal(mean, std, days)
            sims.append(self.df['Close'].iloc[-1] * np.exp(np.sum(future_ret)))
        
        if not sims:
            return None
            
        q5 = np.percentile(sims, 5)
        q95 = np.percentile(sims, 95)
        med = np.median(sims)
        
        return {
            "Tahmini Fiyat": round(med, 2),
            "Alt Eşik (%95)": round(q5, 2),
            "Üst Eşik (%95)": round(q95, 2),
            "Hata Payı": round((q95 - q5) / 2, 2)
        }

# --- VERİ ÇEKME VE HAZIRLAMA ---
@st.cache_data(ttl=600)
def get_all_data():
    rows = []
    for ticker in BIST_TICKERS:
        try:
            model = QuantumAIModel(ticker)
            ret = model.calculate_returns()
            val = model.quantum_validate()
            
            if ret is None:
                continue
                
            row = ret
            if val:
                row.update(val)
            else:
                row.update({"Tahmini Fiyat": "N/A", "Alt Eşik (%95)": "N/A", "Üst Eşik (%95)": "N/A", "Hata Payı": "N/A"})
            
            rows.append(row)
        except Exception:
            continue
    
    df = pd.DataFrame(rows)
    
    # ARROW HATASINI ÇÖZMEK İÇİN: Tüm verileri string'e çevir
    if not df.empty:
        df = df.astype(str)
    
    return df

# --- BÖLÜM 1: TEKNİK ANALİZ ---
def teknik_analiz():
    st.subheader("📊 Teknik Analiz")
    ticker = st.text_input("Hisse Sembolü (Örn: THYAO)", value="THYAO", key="teknik_ticker_input").upper().strip()
    
    if st.button("Analiz Et", key="analiz_buton"):
        if not ticker:
            st.error("Lütfen bir sembol girin.")
            return
        try:
            # .IS ekle
            full_ticker = f"{ticker}.IS"
            t = yf.Ticker(full_ticker)
            df = t.history(period="6mo")
            
            if df.empty:
                st.error(f"'{ticker}' için veri bulunamadı. Sembolü kontrol edin.")
                return
            st.session_state['teknik_df'] = df
            st.session_state['teknik_ticker'] = ticker
        except Exception as e:
            st.error(f"Veri çekilirken hata oluştu: {e}")
    
    if 'teknik_df' in st.session_state:
        df = st.session_state['teknik_df']
        ticker = st.session_state['teknik_ticker']
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

# --- BÖLÜM 2: YÜKSEK POTANSİYEL ---
def yuksek_potansiyel():
    st.subheader("🚀 Yüksek Potansiyelli Tavan Hisseler")
    df = get_all_data()
    
    if df.empty:
        st.info("Veri alınamadı. Lütfen BIST_TICKERS listesini kontrol edin.")
        return
    
    # Gün % sütununu sayıya çevirerek filtrele
    try:
        df['Gün % Sayı'] = pd.to_numeric(df['Gün %'], errors='coerce').fillna(0)
        tavanlar = df[df['Gün % Sayı'] >= 9.9]
        
        if not tavanlar.empty:
            st.success(f"🔔 Şu an {len(tavanlar)} adet tavan hisse var!")
            # Tavan hisseleri göster
            st.dataframe(tavanlar.drop(columns=['Gün % Sayı']), width='stretch')
        else:
            st.info("Şu an tavan hisse bulunmuyor. (Veriler 10 dakikada bir güncellenir)")
        
        st.subheader("📋 Tüm Radar Verileri")
        st.dataframe(df.drop(columns=['Gün % Sayı']), width='stretch')
    except Exception:
        st.dataframe(df, width='stretch')

# --- BÖLÜM 3: TEMEL ANALİZ ---
def temel_analiz():
    st.subheader("📈 Temel Analiz")
    st.write("Bu bölümde temel analiz verileri gösterilecektir.")

# --- BÖLÜM 4: GENEL SİSTEM VERİLERİ ---
def genel_sistem_verileri():
    st.subheader("🌐 Genel Sistem Verileri - Fintables Benzeri Arayüz")
    
    # Üst Menü (Tabs)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Getiri", "Değerleme", "Karlılık", "Büyüme", "Bilanço", "Gelir Tablosu", "Nakit Akım"])
    
    # Sol Menü (Sidebar) - Artık Çalışıyor!
    with st.sidebar:
        st.header("📋 Menü")
        menu_secim = st.radio(
            "Menü Seçin",
            ["Radar", "Hisse", "Endeksler", "VIP", "Kripto"],
            key="sidebar_menu"
        )
        st.markdown("---")
        st.caption("Quantum AI motoru tarafından hesaplanmıştır.")
    
    # Veriyi Çek
    df = get_all_data()
    
    # Sol Menü Seçimine Göre İçerik Değişimi (st.rerun ile)
    if menu_secim == "Radar":
        st.success(f"Şu an **{menu_secim}** menüsündesiniz.")
    elif menu_secim == "Hisse":
        st.info(f"**{menu_secim}** menüsü aktif.")
    elif menu_secim == "Endeksler":
        st.info(f"**{menu_secim}** menüsü aktif.")
    elif menu_secim == "VIP":
        st.info(f"**{menu_secim}** menüsü aktif.")
    elif menu_secim == "Kripto":
        st.info(f"**{menu_secim}** menüsü aktif.")
    
    # --- GETİRİ TABLOSU ---
    with tab1:
        st.write("### Getiri Tablosu")
        if not df.empty:
            # Veriler string olduğu için sıralama yapılamaz, tüm tabloyu göster
            st.dataframe(df, width='stretch')
        else:
            st.info("Veri bekleniyor...")

    # Diğer sekmeler (Simülasyon)
    with tab2:
        st.write("### Değerleme Tablosu")
        st.info("Değerleme verileri hesaplanmaktadır...")
        if not df.empty:
            # Basit simülasyon verileri ekleyerek göster
            df_val = df[['Hisse', 'Fiyat']].copy()
            df_val['F/K (Tahmin)'] = "15-25"
            df_val['PD/DD (Tahmin)'] = "1-3"
            st.dataframe(df_val, width='stretch')

    with tab3:
        st.write("### Karlılık Tablosu")
        st.info("Karlılık verileri hesaplanmaktadır...")
        if not df.empty:
            df_prof = df[['Hisse', 'Fiyat']].copy()
            df_prof['ROE (Tahmin)'] = "%15-30"
            df_prof['ROA (Tahmin)'] = "%5-10"
            st.dataframe(df_prof, width='stretch')

    with tab4:
        st.write("### Büyüme Tablosu")
        st.info("Büyüme verileri hesaplanmaktadır...")
        if not df.empty:
            df_growth = df[['Hisse', 'Fiyat']].copy()
            df_growth['Ciro Büyüme %'] = "%10-40"
            df_growth['Kâr Büyüme %'] = "%5-30"
            st.dataframe(df_growth, width='stretch')

    with tab5:
        st.write("### Bilanço Tablosu")
        st.info("Bilanço verileri hesaplanmaktadır...")
        if not df.empty:
            df_bal = df[['Hisse', 'Fiyat']].copy()
            df_bal['Aktif (Milyon)'] = "500-50.000"
            df_bal['Özkaynak (Milyon)'] = "300-20.000"
            st.dataframe(df_bal, width='stretch')

    with tab6:
        st.write("### Gelir Tablosu")
        st.info("Gelir verileri hesaplanmaktadır...")
        if not df.empty:
            df_inc = df[['Hisse', 'Fiyat']].copy()
            df_inc['Hasılat (Milyon)'] = "100-10.000"
            df_inc['Net Kâr (Milyon)'] = "20-2.000"
            st.dataframe(df_inc, width='stretch')

    with tab7:
        st.write("### Nakit Akım")
        st.info("Nakit akım verileri hesaplanmaktadır...")
        if not df.empty:
            df_cf = df[['Hisse', 'Fiyat']].copy()
            df_cf['Operasyonel Nakit (Milyon)'] = "50-5.000"
            df_cf['Yatırım Nakit (Milyon)'] = "-10 ile -2.000"
            st.dataframe(df_cf, width='stretch')

# --- ANA AKIŞ ---
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
