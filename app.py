import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import traceback

# Sayfa Ayarları
st.set_page_config(page_title="AI Borsa Analiz Sistemi", layout="wide")

# --- YARDIMCI FONKSİYONLAR ---
@st.cache_data(ttl=900)  # 15 dakika boyunca önbellekte tut
def veri_cek(sembol, baslangic, bitis):
    try:
        df = yf.download(sembol, start=baslangic, end=bitis, progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except:
        return pd.DataFrame()

def safe_float(val):
    """Pandas Series hatalarını önler."""
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)

def sembol_duzelt(sembol):
    """BIST- öneklerini temizler ve .IS uzantısını ekler."""
    sembol = sembol.strip().upper()
    if sembol.startswith("BIST-"):
        sembol = sembol.split("-")[1]
    elif sembol.startswith("BIST:"):
        sembol = sembol.split(":")[1]
    
    if not sembol.endswith(".IS"):
        sembol = f"{sembol}.IS"
    return sembol

def skor_hesapla(df):
    """Basit strateji ile 10 üzerinden puanlama."""
    if len(df) < 50:
        return None, None, None, None
    
    df['SMA_10'] = df['Close'].rolling(window=10).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df = df.dropna()
    
    if len(df) == 0:
        return None, None, None, None
    
    last_close = safe_float(df['Close'].iloc[-1])
    last_sma10 = safe_float(df['SMA_10'].iloc[-1])
    last_sma50 = safe_float(df['SMA_50'].iloc[-1])
    
    skor = 0
    if last_close > last_sma10: skor += 4
    if last_close > last_sma50: skor += 4
    if last_sma10 > last_sma50: skor += 2
    
    return skor, last_close, last_sma10, last_sma50

# --- ARAYÜZ BAŞLANGICI ---
st.title("📈 AI Destekli Borsa Analiz Sistemi")
st.caption("BIST ve Global hisse senetleri için Akıllı Teknik Analiz Paneli")

bugun = datetime.now()
varsayilan_baslangic = (bugun - timedelta(days=180))  # Son 6 ay

# --- KENAR ÇUBUĞU (Sidebar) ---
with st.sidebar:
    st.header("⚙️ Parametreler")
    st.divider()
    
    # Popüler Hisseler Listesi
    POPULER = ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "THYAO.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS", "SISE.IS", "SASA.IS"]
    
    secenekler = ["GARAN.IS", "AKBNK.IS", "THYAO.IS"] + POPULER
    secenekler = list(dict.fromkeys(secenekler)) # Tekrarları sil
    
    ticker_input = st.selectbox("📊 Hisse Sembolü", options=secenekler, index=0)
    date_input = st.date_input("📅 Başlangıç Tarihi", value=varsayilan_baslangic)
    date_input_str = date_input.strftime('%Y-%m-%d')
    
    analiz_btn = st.button("🚀 Analizi Başlat", type="primary", width='stretch')

    st.divider()
    st.caption(f"Analiz Tarihi: {bugun.strftime('%d-%m-%Y')}")

# --- ANA MANTIK (Analiz Butonuna Basılınca) ---
if analiz_btn:
    sembol = sembol_duzelt(ticker_input)
    st.subheader(f"📈 {sembol} Analizi")
    
    try:
        with st.spinner(f"Veriler çekiliyor ve analiz ediliyor: {sembol}..."):
            df = veri_cek(sembol, date_input_str, bugun.strftime('%Y-%m-%d'))
            
            if df.empty:
                st.error(f"❌ '{sembol}' sembolü için veri bulunamadı. Lütfen sembolü veya tarihi kontrol edin.")
            else:
                # Teknik Göstergeler
                df['SMA_10'] = df['Close'].rolling(window=10).mean()
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df = df.dropna()
                
                last_close = safe_float(df['Close'].iloc[-1])
                last_sma10 = safe_float(df['SMA_10'].iloc[-1])
                last_sma50 = safe_float(df['SMA_50'].iloc[-1])
                
                # Skorlama
                skor = 0
                if last_close > last_sma10: skor += 4
                if last_close > last_sma50: skor += 4
                if last_sma10 > last_sma50: skor += 2
                
                if skor >= 8: signal = "🟢 GÜÇLÜ AL"
                elif skor >= 6: signal = "🟡 AL / TUT"
                elif skor >= 4: signal = "🟠 TAKİP ET"
                else: signal = "🔴 SAT / BEKLE"
                
                # Profesyonel Metrikler (4 Sütun)
                st.markdown(f"### 📊 Analiz Raporu: {sembol}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Son Kapanış", f"${last_close:.2f}")
                col2.metric("SMA 10", f"${last_sma10:.2f}")
                col3.metric("SMA 50", f"${last_sma50:.2f}")
                col4.metric("Skor", f"{skor}/10")
                
                st.info(f"**Yapay Zeka Kararı:** {signal} - Fiyat, kısa ve uzun vadeli ortalamalara göre değerlendirildi.")
                
                # Grafik
                df_reset = df.reset_index()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['Close'], mode='lines', name='Kapanış Fiyatı', line=dict(color='blue')))
                fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['SMA_10'], mode='lines', name='SMA 10', line=dict(color='green')))
                fig.add_trace(go.Scatter(x=df_reset['Date'], y=df_reset['SMA_50'], mode='lines', name='SMA 50', line=dict(color='red')))
                
                fig.update_layout(
                    title=f'{sembol} Fiyat Grafiği',
                    xaxis_title='Tarih',
                    yaxis_title='Fiyat',
                    height=500,
                    template='plotly_white',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig, width='stretch')
                
                # Son 10 Gün Tablosu
                st.subheader("📋 Son 10 Gün Verileri")
                last_10 = df_reset.tail(10)[['Date', 'Close', 'SMA_10', 'SMA_50']].copy()
                last_10['Close'] = last_10['Close'].round(2)
                last_10['SMA_10'] = last_10['SMA_10'].round(2)
                last_10['SMA_50'] = last_10['SMA_50'].round(2)
                st.dataframe(last_10, width='stretch', hide_index=True)
                
    except Exception as e:
        st.error(f"❌ Hata: {e}")
        with st.expander("Hata Detaylarını Göster"):
            st.code(traceback.format_exc())

# --- ANA SAYFA (Popüler Hisseler Paneli) ---
else:
    st.subheader("🔥 Popüler Hisseler ve 10 Üzerinden Skorları")
    st.markdown("BIST 100'de en çok işlem gören hisselerin güncel verileriyle oluşturulmuş sıralama.")
    
    with st.spinner("Popüler hisseler analiz ediliyor..."):
        analizler = []
        for sembol in ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "THYAO.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS", "SISE.IS", "SASA.IS"]:
            df = veri_cek(sembol, varsayilan_baslangic.strftime('%Y-%m-%d'), bugun.strftime('%Y-%m-%d'))
            if not df.empty:
                skor, last_close, sma10, sma50 = skor_hesapla(df)
                if skor is not None:
                    analizler.append({"Hisse": sembol.replace(".IS", ""), "Skor": skor, "Son Kapanış": round(last_close, 2)})
        
        if analizler:
            df_analiz = pd.DataFrame(analizler).sort_values(by="Skor", ascending=False).reset_index(drop=True)
            
            # Skor Tablosu
            st.dataframe(df_analiz, width='stretch', hide_index=True)
            
            st.divider()
            
            # En yüksek puanlı 3 hissenin grafiği (TradingView tarzı)
            st.markdown("### 📈 En Yüksek Puanlı 3 Hissenin Son 6 Ay Performansı")
            
            fig = go.Figure()
            renkler = ['#1f77b4', '#2ca02c', '#ff7f0e'] # Profesyonel renkler
            
            for i, row in df_analiz.head(3).iterrows():
                sembol = row['Hisse'] + ".IS"
                df_graf = veri_cek(sembol, varsayilan_baslangic.strftime('%Y-%m-%d'), bugun.strftime('%Y-%m-%d'))
                if not df_graf.empty:
                    df_graf = df_graf.reset_index()
                    fig.add_trace(go.Scatter(
                        x=df_graf['Date'],
                        y=df_graf['Close'],
                        mode='lines',
                        name=row['Hisse'],
                        line=dict(color=renkler[i % len(renkler)])
                    ))
            
            fig.update_layout(
                title='Popüler Hisselerin Son 6 Ay Fiyat Hareketleri',
                xaxis_title='Tarih',
                yaxis_title='Fiyat',
                height=500,
                template='plotly_white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, width='stretch')
            
        else:
            st.warning("Popüler hisseler için şu anda veri alınamıyor. Lütfen daha sonra tekrar deneyin.")