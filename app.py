# -*- coding: utf-8 -*-
import sys
import traceback
import time
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import gradio as gr
import yfinance as yf
from datetime import datetime

# Selenium kütüphaneleri
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

print("0. Uygulama başlatılıyor...")
sys.stdout.flush()


# ============================================================
# 1. FINTABLES RADAR - YÜKSEK POTANSİYELLİ TAVAN HİSSELERİ
# ============================================================
def fintables_radar_veri_cek():
    """
    Fintables Radar sayfasından yüksek potansiyelli hisseleri çeker
    """
    try:
        print("Fintables Radar verileri çekiliyor...")
        
        # Chrome driver'ı başlat
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Arka planda çalıştır
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        # Sayfayı yükle
        driver.get("https://fintables.com/radar/hisse-senetleri")
        time.sleep(5)  # Sayfanın yüklenmesi için bekle
        
        # Tablo verilerini çek - sayfa yapısına göre seçicileri ayarla
        # Not: Fintables sürekli güncellendiği için seçiciler değişebilir
        # Aşağıdaki seçiciler örnek amaçlıdır, gerçek kullanımda inspect edilmelidir
        
        try:
            # Tablo satırlarını bul
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            veriler = []
            for row in rows[:20]:  # İlk 20 hisseyi al
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 5:
                    hisse = {
                        'Sembol': cols[0].text.strip(),
                        'Fiyat': cols[1].text.strip(),
                        'Değişim': cols[2].text.strip(),
                        'Hacim': cols[3].text.strip(),
                        'Potansiyel': cols[4].text.strip() if len(cols) > 4 else "-"
                    }
                    veriler.append(hisse)
            
            driver.quit()
            
            if veriler:
                df = pd.DataFrame(veriler)
                return df
            else:
                return pd.DataFrame({"Durum": ["Veri çekilemedi, sayfa yapısı değişmiş olabilir."]})
                
        except Exception as e:
            driver.quit()
            return pd.DataFrame({"Hata": [f"Veri çekme hatası: {str(e)}"]})
            
    except Exception as e:
        return pd.DataFrame({"Hata": [f"Selenium hatası: {str(e)}. Lütfen Chrome ve ChromeDriver'ın kurulu olduğundan emin olun."]})


# ============================================================
# 2. TEMEL ANALİZ FONKSİYONU
# ============================================================
def temel_analiz(ticker):
    """
    Hisse senedinin temel analiz verilerini çeker
    """
    try:
        if not ticker or not ticker.strip():
            return "⚠️ Lütfen bir hisse sembolü girin."
        
        ticker_symbol = ticker.strip().upper()
        print(f"Temel analiz yapılıyor: {ticker_symbol}")
        
        # Yahoo Finance'den temel verileri çek
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info:
            return f"❌ '{ticker_symbol}' için veri bulunamadı."
        
        # Temel göstergeler
        sonuc = f"""
### 📊 Temel Analiz Raporu: {ticker_symbol}

**🏢 Şirket Bilgileri:**
- Şirket Adı: {info.get('longName', 'Bilgi yok')}
- Sektör: {info.get('sector', 'Bilgi yok')}
- Endüstri: {info.get('industry', 'Bilgi yok')}
- Ülke: {info.get('country', 'Bilgi yok')}

**💰 Fiyat ve Değerleme:**
- Güncel Fiyat: ${info.get('currentPrice', info.get('regularMarketPrice', 'Bilgi yok'))}
- Piyasa Değeri: ${info.get('marketCap', 'Bilgi yok'):,} 
- F/K Oranı: {info.get('trailingPE', 'Bilgi yok')}
- Defter Değeri: ${info.get('bookValue', 'Bilgi yok')}
- F/DD Oranı: {info.get('priceToBook', 'Bilgi yok')}

**📈 Temettü ve Getiri:**
- Temettü Verimi: %{info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'Bilgi yok'}
- Öneri: {info.get('recommendationKey', 'Bilgi yok')}

**📊 Hedef Fiyat:**
- Ortalama Hedef: ${info.get('targetMeanPrice', 'Bilgi yok')}
- En Düşük Hedef: ${info.get('targetLowPrice', 'Bilgi yok')}
- En Yüksek Hedef: ${info.get('targetHighPrice', 'Bilgi yok')}
        """
        return sonuc
        
    except Exception as e:
        return f"❌ Temel analiz hatası: {str(e)}"


# ============================================================
# 3. TEKNİK ANALİZ (MEVCUT)
# ============================================================
def analiz_et(ticker, start_date):
    """
    Hisse senedi analizi yapar ve teknik göstergeleri hesaplar
    """
    print(f"Analiz başladı: {ticker}, {start_date}")
    
    if not ticker or not ticker.strip():
        return "⚠️ Lütfen bir hisse sembolü girin.", None, None
    
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
    except:
        return "⚠️ Tarih formatı hatalı. Lütfen YYYY-AA-GG formatında girin.", None, None
    
    try:
        ticker_symbol = ticker.strip().upper()
        print(f"Veri çekiliyor: {ticker_symbol}")
        df = yf.download(ticker_symbol, start=start_date, progress=False)
        
        if df.empty:
            return f"❌ '{ticker_symbol}' sembolüne ait veri bulunamadı.", None, None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        last_close = float(df['Close'].iloc[-1])
        last_sma10 = float(df['SMA_10'].iloc[-1])
        last_sma50 = float(df['SMA_50'].iloc[-1])
        
        if last_sma10 > last_sma50 and last_close > last_sma10:
            signal = "🟢 GÜÇLÜ AL"
            recommendation = "Kısa vadeli trend yukarı yönlü"
        else:
            signal = "🔴 SAT / BEKLE"
            recommendation = "Piyasada aşağı yönlü baskı var"
        
        sonuc_metni = f"""
### 📊 Teknik Analiz Raporu: {ticker_symbol}

**💰 Fiyat Bilgileri:**
- Son Kapanış: **${last_close:.2f}**
- SMA 10: ${last_sma10:.2f}
- SMA 50: ${last_sma50:.2f}

**🎯 Yapay Zeka Kararı: {signal}**
- **Öneri:** {recommendation}
        """
        
        df_reset = df.reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_reset['Date'],
            y=df_reset['Close'],
            mode='lines',
            name='Kapanış Fiyatı'
        ))
        fig.add_trace(go.Scatter(
            x=df_reset['Date'],
            y=df_reset['SMA_10'],
            mode='lines',
            name='SMA 10'
        ))
        fig.add_trace(go.Scatter(
            x=df_reset['Date'],
            y=df_reset['SMA_50'],
            mode='lines',
            name='SMA 50'
        ))
        
        fig.update_layout(
            title=f'{ticker_symbol} Fiyat Grafiği',
            xaxis_title='Tarih',
            yaxis_title='Fiyat',
            height=400
        )
        
        last_10_days = df_reset.tail(10)[['Date', 'Close', 'SMA_10', 'SMA_50']].copy()
        last_10_days['Close'] = last_10_days['Close'].round(2)
        last_10_days['SMA_10'] = last_10_days['SMA_10'].round(2)
        last_10_days['SMA_50'] = last_10_days['SMA_50'].round(2)
        
        print("Teknik analiz tamamlandı")
        return sonuc_metni, fig, last_10_days
        
    except Exception as e:
        print(f"HATA: {traceback.format_exc()}")
        return f"❌ Hata: {str(e)}", None, None


# ============================================================
# 4. GRADIO ARAYÜZÜ
# ============================================================
def create_demo():
    with gr.Blocks(theme=gr.themes.Soft(), title="AI Hisse Analiz Sistemi") as demo:
        gr.Markdown("# 📈 AI Destekli Hisse Analiz Sistemi")
        
        # ===== MENÜ SEKMELERİ =====
        with gr.Tabs():
            
            # ----- SEKME 1: TEKNİK ANALİZ (MEVCUT) -----
            with gr.TabItem("📊 Teknik Analiz"):
                with gr.Row():
                    with gr.Column(scale=1):
                        ticker_input = gr.Textbox(
                            label="Hisse Sembolü",
                            value="AAPL",
                            placeholder="Örn: AAPL, THYAO.IS"
                        )
                        date_input = gr.Textbox(
                            label="Başlangıç Tarihi",
                            value="2022-01-01",
                            placeholder="YYYY-AA-GG"
                        )
                        analiz_btn = gr.Button("🚀 Analizi Başlat", variant="primary")
                    
                    with gr.Column(scale=2):
                        output_text = gr.Markdown(label="📊 Analiz Sonuçları")
                
                with gr.Row():
                    output_plot = gr.Plot(label="📈 Fiyat Grafiği")
                
                with gr.Row():
                    output_table = gr.Dataframe(label="📊 Son 10 Gün Verileri")
                
                analiz_btn.click(
                    fn=analiz_et,
                    inputs=[ticker_input, date_input],
                    outputs=[output_text, output_plot, output_table]
                )
                
                ticker_input.submit(
                    fn=analiz_et,
                    inputs=[ticker_input, date_input],
                    outputs=[output_text, output_plot, output_table]
                )
            
            # ----- SEKME 2: YÜKSEK POTANSİYELLİ TAVAN HİSSELERİ -----
            with gr.TabItem("🚀 Yüksek Potansiyelli Tavan Hisseleri"):
                gr.Markdown("### 📋 Fintables Radar - Yüksek Potansiyelli Hisseler")
                gr.Markdown("*Not: Veriler Fintables.com'dan çekilmektedir. Sayfa yapısı değişirse veri çekme işlemi etkilenebilir.*")
                
                with gr.Row():
                    radar_btn = gr.Button("🔄 Radar Verilerini Getir", variant="primary")
                
                with gr.Row():
                    radar_output = gr.Dataframe(label="📊 Yüksek Potansiyelli Hisseler")
                
                radar_btn.click(
                    fn=fintables_radar_veri_cek,
                    inputs=[],
                    outputs=[radar_output]
                )
            
            # ----- SEKME 3: TEMEL ANALİZ -----
            with gr.TabItem("🏢 Temel Analiz"):
                gr.Markdown("### 📊 Temel Analiz - Şirket Finansal Verileri")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        temel_ticker = gr.Textbox(
                            label="Hisse Sembolü",
                            value="AAPL",
                            placeholder="Örn: AAPL, THYAO.IS"
                        )
                        temel_btn = gr.Button("📊 Temel Analizi Getir", variant="primary")
                    
                    with gr.Column(scale=2):
                        temel_output = gr.Markdown(label="📊 Temel Analiz Sonuçları")
                
                temel_btn.click(
                    fn=temel_analiz,
                    inputs=[temel_ticker],
                    outputs=[temel_output]
                )
                
                temel_ticker.submit(
                    fn=temel_analiz,
                    inputs=[temel_ticker],
                    outputs=[temel_output]
                )
            
            # ----- SEKME 4: GENEL SİSTEM VERİLERİ -----
            with gr.TabItem("🌐 Genel Sistem Verileri"):
                gr.Markdown("### 📈 Fintables - Hisse Senedi Radar Sayfası")
                gr.Markdown("*Aşağıda Fintables.com hisse senedi radar sayfası görüntülenmektedir.*")
                
                # Iframe ile sayfayı göster
                gr.HTML("""
                <iframe 
                    src="https://fintables.com/radar/hisse-senetleri" 
                    style="width:100%; height:700px; border:1px solid #ccc; border-radius:8px;"
                    sandbox="allow-scripts allow-same-origin allow-forms"
                    loading="lazy"
                ></iframe>
                """)
    
    return demo


# ============================================================
# ANA ÇALIŞTIRMA BLOĞU
# ============================================================
if __name__ == "__main__":
    print("="*50)
    print("AI Hisse Analiz Sistemi Başlatılıyor...")
    print("="*50)
    
    try:
        print("Arayüz oluşturuluyor...")
        demo = create_demo()
        print("Arayüz hazır, tarayıcı açılıyor...")
        print("Adres: http://127.0.0.1:7860")
        print("Kapatmak için CTRL+C tuşlarına basın")
        
        demo.launch(
            server_name="127.0.0.1",
            server_port=7860,
            share=False,
            debug=False,
            show_error=True,
            prevent_thread_lock=False
        )
        
    except Exception as e:
        print(f"KRİTİK HATA: {e}")
        print(traceback.format_exc())
        input("Devam etmek için ENTER'a basın...")
