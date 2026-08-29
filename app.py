import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import traceback

# Sayfa Ayarları
st.set_page_config(page_title="AI Borsa Analiz Sistemi", layout="wide")

# --- YARDIMCI FONKSİYONLAR ---
@st.cache_data(ttl=900)
def veri_cek(sembol, baslangic, bitis):
    try:
        # Geçmiş tarih kontrolü (Bugün veya gelecekse 1 gün geri al)
        if baslangic >= bitis:
            baslangic = (bitis - timedelta(days=10)).strftime('%Y-%m-%d')
            
        df = yf.download(sembol, start=baslangic, end=bitis, progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except:
        return pd.DataFrame()

def safe_float(val):
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)

def sembol_duzelt(sembol):
    sembol = sembol.strip().upper()
    if sembol.startswith("BIST-"): sembol = sembol.split("-")[1]
    elif sembol.startswith("BIST:"): sembol = sembol.split(":")[1]
    if not sembol.endswith(".IS") and not sembol.endswith(".SI"):
        sembol = f"{sembol}.IS"
    return sembol

# --- ARAYÜZ ---
st.title("📈 AI Destekli Borsa Analiz Sistemi")
st.caption("Güncel verilerle yüksek getiri potansiyelli hisseleri keşfedin.")

bugun = datetime.now()
varsayilan_baslangic = bugun - timedelta(days=180)

with st.sidebar:
    st.header("⚙️ Parametreler")
    st.divider()
    
    POPULER = ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "THYAO.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS", "SISE.IS", "SASA.IS"]
    secenekler = list(dict.fromkeys(POPULER))
    
    ticker_input = st.selectbox("📊 Hisse Sembolü", options=secenekler, index=0)
    date_input = st.date_input("📅 Başlangıç Tarihi", value=varsayilan_baslangic)
    date_input_str = date_input.strftime('%Y-%m-%d')
    
    analiz_btn = st.button("🚀 Analizi Başlat", type="primary", width='stretch')

    st.divider()
    st.caption(f"Analiz Tarihi: {bugun.strftime('%d-%m-%Y')}")

if analiz_btn:
    sembol = sembol_duzelt(ticker_input)
    
    # Tarih hatası kontrolü (Bugün veya gelecekse)
    if date_input >= bugun.date():
        st.error("❌ Başlangıç tarihi bugünden önce olmalıdır. Veri çekilemiyor!")
    else:
        st.subheader(f"📈 {sembol} Analizi")
        try:
            with st.spinner("Veriler çekiliyor ve analiz ediliyor..."):
                df = veri_cek(sembol, date_input_str, bugun.strftime('%Y-%m-%d'))
                
                # Boş veri kontrolü
                if len(df) < 2:
                    st.error(f"❌ '{sembol}' için yeterli veri bulunamadı. Lütfen daha eski bir tarih seçin.")
                else:
                    # Teknik Göstergeler
                    df['SMA_20'] = df['Close'].rolling(window=20).mean()
                    df['SMA_50'] = df['Close'].rolling(window=50).mean()
                    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
                    
                    last_close = safe_float(df['Close'].iloc[-1])
                    last_sma20 = safe_float(df['SMA_20'].iloc[-1])
                    last_sma50 = safe_float(df['SMA_50'].iloc[-1])
                    
                    # Getiri Hesaplamaları (1 Ay, 3 Ay, 6 Ay)
                    getiri_1ay = ((last_close / safe_float(df['Close'].iloc[-22])) - 1) * 100 if len(df) > 22 else 0
                    getiri_3ay = ((last_close / safe_float(df['Close'].iloc[-66])) - 1) * 100 if len(df) > 66 else 0
                    getiri_6ay = ((last_close / safe_float(df['Close'].iloc[-126])) - 1) * 100 if len(df) > 126 else 0
                    
                    # Momentum Skoru (10 Üzerinden)
                    skor = 0
                    if last_close > last_sma20: skor += 3
                    if last_close > last_sma50: skor += 3
                    if getiri_1ay > 5: skor += 2
                    if getiri_3ay > 10: skor += 2
                    
                    if skor >= 8: signal = "🟢 GÜÇLÜ AL"
                    elif skor >= 6: signal = "🟡 AL / TUT"
                    elif skor >= 4: signal = "🟠 TAKİP ET"
                    else: signal = "🔴 SAT / BEKLE"
                    
                    # Profesyonel Metrikler
                    st.markdown(f"### 📊 Analiz Raporu: {sembol}")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Son Kapanış", f"${last_close:.2f}")
                    col2.metric("1 Ay Getiri", f"%{getiri_1ay:.2f}")
                    col3.metric("3 Ay Getiri", f"%{getiri_3ay:.2f}")
                    col4.metric("Momentum Skoru", f"{skor}/10")
                    
                    st.info(f"**Yapay Zeka Kararı:** {signal} - Getiri potansiyeli ve trend göstergeleri değerlendirildi.")
                    
                    # PROFESYONEL GRAFİK (TradingView Tarzı: Mum + Hacim + EMA)
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                        vertical_spacing=0.03, row_heights=[0.7, 0.3])
                    
                    # Mum Grafiği
                    fig.add_trace(go.Candlestick(
                        x=df.index, open=df['Open'], high=df['High'], 
                        low=df['Low'], close=df['Close'], name='Fiyat'
                    ), row=1, col=1)
                    
                    # EMA ve SMA Çizgileri
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], 
                        mode='lines', name='SMA 20', line=dict(color='green', width=1.5)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], 
                        mode='lines', name='SMA 50', line=dict(color='red', width=1.5)), row=1, col=1)
                    
                    # Hacim Grafiği (Alt Kısım)
                    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], 
                        name='Hacim', marker_color='gray', opacity=0.5), row=2, col=1)
                    
                    fig.update_layout(
                        title=f'{sembol} Profesyonel Grafik',
                        xaxis_rangeslider_visible=False,
                        template='plotly_white',
                        height=600,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    fig.update_xaxes(title_text="Tarih", row=2, col=1)
                    fig.update_yaxes(title_text="Fiyat", row=1, col=1)
                    fig.update_yaxes(title_text="Hacim", row=2, col=1)
                    
                    st.plotly_chart(fig, width='stretch')
                    
        except Exception as e:
            st.error(f"❌ Hata: {e}")
            with st.expander("Hata Detaylarını Göster"):
                st.code(traceback.format_exc())

# --- ANA SAYFA (Yüksek Getiri Potansiyelli Hisseler) ---
else:
    st.subheader("🔥 Yüksek Getiri Potansiyelli Hisseler (Momentum Analizi)")
    st.markdown("1, 3 ve 6 aylık getirileri ile SMA ortalamalarına göre skorlanmış en güçlü hisseler.")
    
    with st.spinner("Piyasa analiz ediliyor..."):
        analizler = []
        for sembol in ["GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "THYAO.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS", "SISE.IS", "SASA.IS"]:
            df = veri_cek(sembol, varsayilan_baslangic.strftime('%Y-%m-%d'), bugun.strftime('%Y-%m-%d'))
            if len(df) > 22:
                last_close = safe_float(df['Close'].iloc[-1])
                getiri_1ay = ((last_close / safe_float(df['Close'].iloc[-22])) - 1) * 100
                getiri_3ay = ((last_close / safe_float(df['Close'].iloc[-66])) - 1) * 100 if len(df) > 66 else 0
                getiri_6ay = ((last_close / safe_float(df['Close'].iloc[-126])) - 1) * 100 if len(df) > 126 else 0
                
                last_sma50 = safe_float(df['Close'].rolling(window=50).mean().iloc[-1])
                
                # Getiri Odaklı Skorlama
                skor = 0
                if last_close > last_sma50: skor += 3
                if getiri_1ay > 5: skor += 2
                if getiri_3ay > 10: skor += 2
                if getiri_6ay > 20: skor += 3
                
                if skor >= 6:
                    analizler.append({
                        "Hisse": sembol.replace(".IS", ""),
                        "Skor": skor,
                        "Son Fiyat": round(last_close, 2),
                        "1 Ay %": round(getiri_1ay, 2),
                        "3 Ay %": round(getiri_3ay, 2),
                        "6 Ay %": round(getiri_6ay, 2)
                    })
        
        if analizler:
            df_analiz = pd.DataFrame(analizler).sort_values(by="Skor", ascending=False).reset_index(drop=True)
            
            # Getiri Tablosu
            st.dataframe(df_analiz, width='stretch', hide_index=True)
            
            st.divider()
            
            # En Yüksek Skorlu 3 Hissenin Profesyonel Grafiği
            st.markdown("### 📈 En Yüksek Potansiyelli 3 Hissenin Performansı (Son 6 Ay)")
            
            fig = go.Figure()
            renkler = ['#1f77b4', '#2ca02c', '#ff7f0e']
            
            for i, row in df_analiz.head(3).iterrows():
                sembol = row['Hisse'] + ".IS"
                df_graf = veri_cek(sembol, varsayilan_baslangic.strftime('%Y-%m-%d'), bugun.strftime('%Y-%m-%d'))
                if not df_graf.empty:
                    df_graf = df_graf.reset_index()
                    fig.add_trace(go.Scatter(
                        x=df_graf['Date'], y=df_graf['Close'], mode='lines',
                        name=row['Hisse'], line=dict(color=renkler[i % len(renkler)], width=2)
                    ))
            
            fig.update_layout(
                title='Getiri Potansiyeli En Yüksek 3 Hisse',
                xaxis_title='Tarih', yaxis_title='Fiyat',
                height=500, template='plotly_white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, width='stretch')
            
        else:
            st.warning("Şu anda getiri potansiyeli yüksek hisse bulunamadı. Lütfen daha sonra tekrar deneyin.")