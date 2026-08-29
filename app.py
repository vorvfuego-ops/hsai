import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import traceback

# Sayfa ayarları
st.set_page_config(page_title="AI Hisse Analiz Sistemi", layout="wide")

# Başlık
st.title("📈 AI Destekli Hisse Analiz Sistemi")

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.header("Parametreler")
    ticker_input = st.text_input("Hisse Sembolü", value="AAPL", placeholder="Örn: AAPL, THYAO.IS")
    date_input = st.text_input("Başlangıç Tarihi", value="2022-01-01", placeholder="YYYY-AA-GG")
    analiz_btn = st.button("🚀 Analizi Başlat", type="primary")

# --- ANA MANTIK ---
if analiz_btn:
    if not ticker_input or not ticker_input.strip():
        st.warning("⚠️ Lütfen bir hisse sembolü girin.")
    else:
        # Tarih formatı kontrolü
        try:
            datetime.strptime(date_input, '%Y-%m-%d')
            tarih_gecerli = True
        except:
            tarih_gecerli = False
            st.error("⚠️ Tarih formatı hatalı. Lütfen YYYY-AA-GG formatında girin.")

        if tarih_gecerli:
            try:
                ticker_symbol = ticker_input.strip().upper()
                
                with st.spinner(f"Veri çekiliyor ve analiz ediliyor: {ticker_symbol}..."):
                    # Veri çekme (Yeni sürümler için auto_adjust=False ekledik)
                    df = yf.download(ticker_symbol, start=date_input, progress=False, auto_adjust=False)
                    
                    if df.empty:
                        st.error(f"❌ '{ticker_symbol}' sembolüne ait veri bulunamadı. Lütfen sembolü kontrol edin (Örn: THYAO.IS).")
                    else:
                        # Kolon isimlerini düzeltme (MultiIndex durumu)
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        
                        # Hareketli ortalamalar (SMA)
                        df['SMA_10'] = df['Close'].rolling(window=10).mean()
                        df['SMA_50'] = df['Close'].rolling(window=50).mean()
                        
                        # Son verileri al
                        last_close = float(df['Close'].iloc[-1])
                        last_sma10 = float(df['SMA_10'].iloc[-1])
                        last_sma50 = float(df['SMA_50'].iloc[-1])
                        
                        # Yapay zeka sinyali
                        if last_sma10 > last_sma50 and last_close > last_sma10:
                            signal = "🟢 GÜÇLÜ AL"
                            recommendation = "Kısa vadeli trend yukarı yönlü"
                        else:
                            signal = "🔴 SAT / BEKLE"
                            recommendation = "Piyasada aşağı yönlü baskı var"
                        
                        # Sonuç Metni
                        st.markdown(f"""
                        ### 📊 Analiz Raporu: {ticker_symbol}
                        
                        **💰 Fiyat Bilgileri:**
                        - Son Kapanış: **${last_close:.2f}**
                        - SMA 10: ${last_sma10:.2f}
                        - SMA 50: ${last_sma50:.2f}
                        
                        **🎯 Yapay Zeka Kararı: {signal}**
                        - **Öneri:** {recommendation}
                        """)
                        
                        # Verileri hazırlama
                        df_reset = df.reset_index()
                        # 'Date' sütununun adı bazen 'Date' bazen 'Datetime' olabilir, kontrol edelim
                        date_col = 'Date' if 'Date' in df_reset.columns else df_reset.columns[0]
                        
                        last_10_days = df_reset.tail(10)[[date_col, 'Close', 'SMA_10', 'SMA_50']].copy()
                        last_10_days['Close'] = last_10_days['Close'].round(2)
                        last_10_days['SMA_10'] = last_10_days['SMA_10'].round(2)
                        last_10_days['SMA_50'] = last_10_days['SMA_50'].round(2)
                        
                        # Grafik (Plotly)
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df_reset[date_col],
                            y=df_reset['Close'],
                            mode='lines',
                            name='Kapanış Fiyatı'
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_reset[date_col],
                            y=df_reset['SMA_10'],
                            mode='lines',
                            name='SMA 10'
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_reset[date_col],
                            y=df_reset['SMA_50'],
                            mode='lines',
                            name='SMA 50'
                        ))
                        
                        fig.update_layout(
                            title=f'{ticker_symbol} Fiyat Grafiği',
                            xaxis_title='Tarih',
                            yaxis_title='Fiyat',
                            height=500
                        )
                        
                        # Çıktıları ekrana bas
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader("📊 Son 10 Gün Verileri")
                        st.dataframe(last_10_days, use_container_width=True)

            except Exception as e:
                st.error(f"❌ Hata: {e}")
                # Hata ayıklama için detaylı kod
                with st.expander("Hata Detaylarını Göster"):
                    st.code(traceback.format_exc())

else:
    # Butona basılmadıysa gösterilecek bilgi
    st.info("Analiz yapmak için sol taraftaki parametreleri girip 'Analizi Başlat' butonuna basın.")