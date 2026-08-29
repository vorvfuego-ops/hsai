import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import yfinance as yf
import requests

# Sayfa Ayarları
st.set_page_config(page_title="BIST Pro AI Terminali", layout="wide")

# --- 1. GÜVENLİ VERİ DÖNÜŞTÜRÜCÜ ---
def safe_float(val):
    """Pandas verilerini hatasız float'a çevirir."""
    if val is None: return 0.0
    if isinstance(val, pd.Series):
        if val.empty: return 0.0
        try: return float(val.iloc[0])
        except: return 0.0
    try: return float(val)
    except: return 0.0

# --- 2. TRADINGVIEW OTOMATİK TOKEN DOĞRULAMA ---
def get_auth_token():
    """Secrets'taki kullanıcı adı/şifre ile TradingView token'ı alır."""
    try:
        username = st.secrets["tradingview"]["username"]
        password = st.secrets["tradingview"]["password"]
        sign_in_url = 'https://www.tradingview.com/accounts/signin/'
        data = {"username": username, "password": password, "remember": "on"}
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.post(url=sign_in_url, data=data, headers=headers)
        if response.status_code == 200 and 'auth_token' in response.json().get('user', {}):
            return response.json()['user']['auth_token']
        else:
            return None
    except:
        return None

# --- 3. TÜM BIST HİSSELERİNİ ÇEKME (TradingView Screener) ---
@st.cache_data(ttl=600)
def tum_bist_hisselerini_getir():
    """Türkiye piyasasındaki tüm hisseleri çeker."""
    try:
        from tradingview_screener import Query
        token = get_auth_token()
        query = (
            Query()
            .set_markets('turkey')
            .select('name', 'close', 'change', 'volume', 'market_cap_basic',
                    'RSI', 'sector', 'high_all_calc')
            .order_by('volume', ascending=False)
            .limit(1000)
        )
        try:
            total, df = query.get_scanner_data(auth_token=token)
        except:
            total, df = query.get_scanner_data()
        return df
    except Exception as e:
        return pd.DataFrame()

# --- 4. TAVAN POTANSİYELİ VE NEDEN AÇIKLAMASI ---
def potansiyel_hesapla(df):
    """Tavan Potansiyelini hesaplar ve neden yükselebileceğini Türkçe açıklar."""
    # Yüksek değerleri hesapla (Yahoo Finance üzerinden 52 haftalık tepe noktalarını baz al)
    # Çünkü TradingView'un "high_all_calc" değeri bazen 0 dönebiliyor.
    yuksek_degerler = []
    
    for isim in df['name']:
        try:
            veri = yf.download(isim + ".IS", period="1y", progress=False, auto_adjust=False)
            yuksek = safe_float(veri['High'].max()) if not veri.empty else 0
        except:
            yuksek = 0
        yuksek_degerler.append(yuksek)
    
    df['52H_Yuksek'] = yuksek_degerler
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['close']) / df['close']) * 100
    
    # Neden Yükselebilir? sütunu
    def neden_yukselebilir(row):
        nedenler = []
        if row['RSI'] > 70: nedenler.append("Aşırı alım, güçlü momentum")
        elif row['RSI'] > 50: nedenler.append("Pozitif alıcı baskısı (RSI)")
        
        if row['Tavan Potansiyeli (%)'] > 20: nedenler.append("Tavanına çok uzak, büyük yükseliş alanı var")
        elif row['Tavan Potansiyeli (%)'] > 5: nedenler.append("52 haftalık zirvesine yaklaşıyor, tavan denemesi beklenebilir")
        
        if safe_float(row['change']) > 2: nedenler.append("Bugün güçlü bir yükseliş var")
        if safe_float(row['volume']) > 1000000: nedenler.append("İşlem hacmi çok yüksek (likidite güçlü)")
        
        return ", ".join(nedenler) if nedenler else "Normal piyasa seyri"
    
    df['Neden Yükselebilir?'] = df.apply(neden_yukselebilir, axis=1)
    return df

# --- ARAYÜZ VE SIDEBAR (SOL MENÜ) ---
st.title("📊 BIST Pro AI Terminali")
st.caption("TradingView Altyapısı ile Sınırsız Türk Piyasası Analizi")

# Tüm hisseleri çek
with st.spinner("BIST hisseleri yükleniyor..."):
    tum_hisseler = tum_bist_hisselerini_getir()

# Sol Menü
with st.sidebar:
    st.header("📋 Tüm BIST Hisseleri")
    if not tum_hisseler.empty:
        # Sol menüde tüm hisseleri listele
        secim = st.selectbox("Hisse Ara ve Seç", options=tum_hisseler['name'].tolist())
        if st.button("Seçilen Hisseleri Analiz Et"):
            st.session_state['secili_hisse'] = secim
            st.session_state['aktif_tab'] = 1
            st.rerun()
    else:
        st.warning("Veri çekilemedi. Lütfen Secrets ayarlarını kontrol edin.")

# Sekmeleri oluştur (0: Tavan Avcıları, 1: Profesyonel Analiz)
tab1, tab2 = st.tabs(["🚀 Yüksek Potansiyelli Tavan Hisseleri", "📈 Profesyonel Analiz"])

# --- TAB 1: YÜKSEK POTANSİYELLİ TAVAN HİSSELERİ (10 Hisse) ---
with tab1:
    st.subheader("🔥 En Yüksek Tavan Potansiyeline Sahip 10 Hisse")
    st.write("Bu liste; hacim, RSI ve 52 haftalık zirveye olan mesafeye göre yapay zeka tarafından hesaplanır.")
    
    if not tum_hisseler.empty:
        # Potansiyel hesaplamalarını yap (10 hisse için Yahoo verileriyle 52H yüksekliği çek)
        # Not: Bu işlem biraz zaman alabilir, o yüzden 10 hisse ile sınırlandırıyoruz.
        ilk_10 = tum_hisseler.head(20) # İlk 20'yi alıp en iyi 10'u bulacağız
        analiz_df = potansiyel_hesapla(ilk_10)
        
        # En yüksek potansiyele göre sırala
        tavan_hisseleri = analiz_df.sort_values(by='Tavan Potansiyeli (%)', ascending=False).head(10)
        
        # Türkçe Tablo Oluştur
        tablo_df = tavan_hisseleri[['name', 'close', 'change', 'volume', 'Tavan Potansiyeli (%)', 'RSI', 'sector', 'Neden Yükselebilir?']].copy()
        tablo_df.columns = ['Hisse', 'Kapanış', 'Değişim (%)', 'Hacim', 'Tavan Potansiyeli (%)', 'RSI', 'Sektör', 'Neden Yükselebilir?']
        tablo_df['Kapanış'] = tablo_df['Kapanış'].round(2)
        tablo_df['Değişim (%)'] = tablo_df['Değişim (%)'].round(2)
        tablo_df['Tavan Potansiyeli (%)'] = tablo_df['Tavan Potansiyeli (%)'].round(2)
        tablo_df['RSI'] = tablo_df['RSI'].round(2)
        
        st.dataframe(tablo_df, width='stretch', hide_index=True)
        
        # PROFESYONEL VE ANLAMLI GRAFİK (Normalize Edilmiş Performans)
        st.markdown("### 📈 10 Hissenin Kıyaslamalı Performansı")
        st.caption("Tüm hisseler 100 birimden başlatılarak normalize edilmiştir. Böylece pahalı ve ucuz hisseler aynı grafikte doğru kıyaslanır.")
        
        fig = go.Figure()
        
        for isim in tavan_hisseleri['name']:
            try:
                # 6 aylık veri çek
                df_hisse = yf.download(isim + ".IS", period="6mo", progress=False, auto_adjust=False)
                if not df_hisse.empty:
                    # Normalize et: İlk fiyatı 100 kabul et
                    df_hisse['Normalize'] = (df_hisse['Close'] / df_hisse['Close'].iloc[0]) * 100
                    
                    fig.add_trace(go.Scatter(
                        x=df_hisse.index,
                        y=df_hisse['Normalize'],
                        mode='lines',
                        name=isim,
                        line=dict(width=2)
                    ))
            except:
                pass
        
        fig.update_layout(
            title="Son 6 Ay Performansı (100 Baz Puan)",
            xaxis_title="Tarih",
            yaxis_title="Performans (%)",
            height=600,
            template='plotly_white',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.error("TradingView'dan veri alınamadı.")

# --- TAB 2: PROFESYONEL ANALİZ (Tüm Menüden Seçilebilir) ---
with tab2:
    st.subheader("🧠 Profesyonel Analiz")
    
    # Sol menüden seçilen hisse varsa onu kullan, yoksa varsayılanı kullan
    if 'secili_hisse' in st.session_state:
        secim = st.session_state['secili_hisse']
    else:
        secim = "GARAN"
    
    # Sadece menüdeki hisseleri seçtir
    secim = st.selectbox("Analiz Edilecek Hisse", options=tum_hisseler['name'].tolist() if not tum_hisseler.empty else ["GARAN"], index=0, key="analiz_secimi")
    
    if st.button("Derinlemesine Analizi Başlat"):
        df = yf.download(secim + ".IS", period="6mo", progress=False, auto_adjust=False)
        
        if df.empty:
            st.error("Bu hisse için veri bulunamadı.")
        else:
            # Teknik Göstergeler
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            # Profesyonel 3 Satırlı Grafik
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
            
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
            
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color='gray'), row=2, col=1)
            
            # RSI Hesabı
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='purple')), row=3, col=1)
            
            fig.update_layout(title=f"{secim} Profesyonel Görünüm", height=800, template='plotly_dark', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, width='stretch')