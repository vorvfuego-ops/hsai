import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import hashlib

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Quantum BIST Terminali", layout="wide")
st_autorefresh(interval=60000, key="data_refresh")

# --- YARDIMCI FONKSİYONLAR ---
def safe_float(val):
    try: return float(val)
    except: return 0.0

def format_big_number(val):
    try:
        val = float(val)
        if val >= 1_000_000_000: return f"{val / 1_000_000_000:.2f} mr"
        elif val >= 1_000_000: return f"{val / 1_000_000:.2f} mn"
        elif val >= 1_000: return f"{val / 1_000:.2f} bin"
        else: return f"{val:.0f}"
    except: return "N/A"

def parse_big_number(val):
    if pd.isna(val): return 0.0
    val_str = str(val)
    if 'mr' in val_str: return float(val_str.replace(' mr', '')) * 1_000_000_000
    elif 'mn' in val_str: return float(val_str.replace(' mn', '')) * 1_000_000
    elif 'bin' in val_str: return float(val_str.replace(' bin', '')) * 1_000
    try: return float(val_str)
    except: return 0.0

def format_percent(val):
    try: return f"{float(val):.2f}%"
    except: return "N/A"

# --- TELEGRAM BİLDİRİM FONKSİYONU ---
def send_telegram_alert(message):
    try:
        bot_token = st.secrets["telegram"]["bot_token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            st.warning(f"Telegram Hatası: {response.text}")
    except Exception as e:
        st.error(f"Telegram Ayarları Hatalı: {e}")

# --- MAKRO VERİ ---
def get_macro_data():
    return {"enflasyon": 23.6, "faiz": 28.5, "buyume": 3.9, "cds": 320}

# --- TRADINGVIEW TOKEN ---
def get_auth_token():
    try:
        username = st.secrets["tradingview"]["username"]
        password = st.secrets["tradingview"]["password"]
        url = 'https://www.tradingview.com/accounts/signin/'
        data = {"username": username, "password": password, "remember": "on"}
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.post(url=url, data=data, headers=headers)
        if response.status_code == 200:
            return response.json()['user']['auth_token']
    except:
        return None

# --- VERİ ÇEKME ---
@st.cache_data(ttl=60)
def tum_bist_hisselerini_getir():
    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "symbols": {"tickers": [], "query": {"types": []}},
        "columns": [
            "name", "close", "change", "volume", "market_cap_basic", 
            "high_all_calc", "RSI", 
            "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.YTD", 
            "Perf.1Y", "Perf.3Y", "Perf.5Y", "sector",
            "price_earnings_ttm", "price_book_fq", "return_on_equity_fq", 
            "net_margin_ttm", "debt_to_equity_fq", "dividends_yield_current"
        ]
    }
    
    try:
        token = get_auth_token()
        headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rows = []
        for item in data.get("data", []):
            d = item["d"]
            rows.append({
                "Hisse": d[0], "Fiyat": d[1], "Gün %": d[2],
                "Hacim (Adet)": d[3], "Piyasa Değeri (Bin TL)": d[4],
                "52H_Yuksek": d[5], "RSI": d[6],
                "Getiri % (Son 1 hafta)": d[7], "Getiri % (Son 1 ay)": d[8],
                "Getiri % (Son 3 ay)": d[9], "Getiri % (Son 6 ay)": d[10],
                "Getiri % (Yılbaşından)": d[11], "Getiri % (Son 1 yıl)": d[12],
                "Getiri % (Son 3 yıl)": d[13], "Getiri % (Son 5 yıl)": d[14],
                "Sektör": d[15], "F/K": d[16], "PD/DD": d[17],
                "ROE": d[18], "Net Marj": d[19], "Borç/Özkaynak": d[20],
                "Temettü Verimi": d[21]
            })
        
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        
        df['Hacim_TL'] = pd.to_numeric(df['Hacim (Adet)'], errors='coerce') * pd.to_numeric(df['Fiyat'], errors='coerce')
        df['Hacim'] = df['Hacim_TL'].apply(format_big_number)
        df['Piyasa_Değeri_TL'] = pd.to_numeric(df['Piyasa Değeri (Bin TL)'], errors='coerce') * 1000
        df['Piyasa Değeri'] = df['Piyasa_Değeri_TL'].apply(format_big_number)
        
        df = df.drop(columns=['Hacim (Adet)', 'Piyasa Değeri (Bin TL)'], errors='ignore')
        df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce')
        df['Gün %'] = pd.to_numeric(df['Gün %'], errors='coerce')
        df['RSI'] = pd.to_numeric(df['RSI'], errors='coerce')
        
        for col in ['F/K', 'PD/DD', 'ROE', 'Net Marj', 'Borç/Özkaynak', 'Temettü Verimi']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df['Sektör'] = df['Sektör'].astype(str)
        return df
    except Exception as e:
        st.error(f"TradingView verileri alınamadı: {e}")
        return pd.DataFrame()

# --- QUANTUM SEVİYE 2 YZ MODELİ ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    df['52H_Yuksek'] = pd.to_numeric(df['52H_Yuksek'], errors='coerce').fillna(0)
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    df['Tavan Potansiyeli (%)'] = np.where(df['Fiyat'] > 0, ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100, 0)
    
    def ai_tahmin_1y(row):
        val = row.get('Getiri % (Son 1 yıl)')
        if pd.isna(val) or val == "":
            val_6m = row.get('Getiri % (Son 6 ay)')
            try: return safe_float(val_6m) * 2
            except: return None
        return val
    def ai_tahmin_3y(row):
        val = row.get('Getiri % (Son 3 yıl)')
        if pd.isna(val) or val == "":
            val_1y = row.get('Getiri % (Son 1 yıl)')
            try: return safe_float(val_1y) * 3
            except: return None
        return val
    def ai_tahmin_5y(row):
        val = row.get('Getiri % (Son 5 yıl)')
        if pd.isna(val) or val == "":
            val_3y = row.get('Getiri % (Son 3 yıl)')
            try: return safe_float(val_3y) * 1.6
            except: return None
        return val

    df['Getiri % (Son 1 yıl)'] = df.apply(ai_tahmin_1y, axis=1)
    df['Getiri % (Son 3 yıl)'] = df.apply(ai_tahmin_3y, axis=1)
    df['Getiri % (Son 5 yıl)'] = df.apply(ai_tahmin_5y, axis=1)
    
    def sektorel_degerleme(row):
        sektor = str(row.get('Sektör', '') or '')
        fk = safe_float(row.get('F/K'))
        
        if "Banka" in sektor or "Finans" in sektor:
            if fk > 0 and fk < 5: return "Çok Ucuz"
            elif fk < 8: return "Ucuz"
            elif fk < 12: return "Normal"
            else: return "Pahalı"
        elif "Teknoloji" in sektor:
            if fk > 0 and fk < 15: return "Çok Ucuz"
            elif fk < 25: return "Ucuz"
            elif fk < 40: return "Normal"
            else: return "Pahalı"
        else:
            if fk > 0 and fk < 8: return "Çok Ucuz"
            elif fk < 15: return "Ucuz"
            elif fk < 25: return "Normal"
            else: return "Pahalı"
    
    df['Sektörel Değerleme'] = df.apply(sektorel_degerleme, axis=1)
    
    # Markov Rejimi
    ort_getiri_1m = pd.to_numeric(df['Getiri % (Son 1 ay)'].astype(str).str.replace('%', ''), errors='coerce').mean()
    if ort_getiri_1m > 3:
        rejim = "BOĞA"
        rejim_bonus = 10
    elif ort_getiri_1m < -3:
        rejim = "AYI"
        rejim_bonus = -10
    else:
        rejim = "YATAY"
        rejim_bonus = 0

    # Backtesting
    ucuz_hisseler = df[df['Sektörel Değerleme'].isin(["Çok Ucuz", "Ucuz"])]
    diger_hisseler = df[~df['Sektörel Değerleme'].isin(["Çok Ucuz", "Ucuz"])]
    
    if not ucuz_hisseler.empty and not diger_hisseler.empty:
        ucuz_ort_6m = pd.to_numeric(ucuz_hisseler['Getiri % (Son 6 ay)'].astype(str).str.replace('%', ''), errors='coerce').mean()
        diger_ort_6m = pd.to_numeric(diger_hisseler['Getiri % (Son 6 ay)'].astype(str).str.replace('%', ''), errors='coerce').mean()
        backtest_farki = ucuz_ort_6m - diger_ort_6m
        backtest_skoru = max(-10, min(10, backtest_farki / 5))
    else:
        backtest_skoru = 0

    # Monte Carlo Simülasyonu
    def monte_carlo_olasilik(row):
        fiyat = safe_float(row['Fiyat'])
        gunluk_degisim = abs(safe_float(row['Gün %'])) / 100
        volatilite = max(gunluk_degisim, 0.01)
        
        hisse = row['Hisse']
        bugun = datetime.now().date()
        seed_str = f"{hisse}-{bugun}"
        seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        
        np.random.seed(seed_int)
        
        fiyat_5_gun = fiyat * np.exp((0 * 5) + (volatilite * np.sqrt(5) * np.random.randn(10000)))
        olasilik = np.mean(fiyat_5_gun >= fiyat * 1.10) * 100
        return olasilik

    df['Monte Carlo Olasılığı (%)'] = df.apply(monte_carlo_olasilik, axis=1)

    def hesapla_skor(row):
        skor = 50
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: skor += 15
        elif pot > 10: skor += 8
        elif pot > 5: skor += 4
        elif pot < 0: skor -= 5
        
        gun = safe_float(row['Gün %'])
        if gun > 3: skor += 10
        elif gun > 1: skor += 5
        elif gun < -2: skor -= 5
        
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: skor += 8
        elif rsi > 70: skor -= 5
        
        mc_olasilik = safe_float(row['Monte Carlo Olasılığı (%)'])
        skor += (mc_olasilik / 2.5)

        skor += backtest_skoru
        skor += rejim_bonus
        
        return max(0, min(100, skor))
    
    df['Yatırım Fırsat Skoru'] = df.apply(hesapla_skor, axis=1).round(1)
    
    def sinyal_uret(row):
        skor = safe_float(row['Yatırım Fırsat Skoru'])
        if skor >= 80: return "🟢 Çok Güçlü Al"
        elif skor >= 70: return "🟢 Güçlü Al"
        elif skor >= 60: return "🔵 Al"
        elif skor >= 45: return "🟡 İzle"
        else: return "⚪ Nötr"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    
    def neden_yukselir(row):
        nedenler = []
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: nedenler.append(f"Tavan potansiyeli %{pot:.1f}")
        
        mc = safe_float(row['Monte Carlo Olasılığı (%)'])
        if mc > 15: nedenler.append(f"5 günde %10 artış olasılığı %{mc:.1f}")
        
        gun = safe_float(row['Gün %'])
        if gun > 2: nedenler.append("Bugün güçlü alım")
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: nedenler.append("RSI ideal")
        if row.get('Sektörel Değerleme') == "Çok Ucuz": nedenler.append("Sektörüne göre çok ucuz")
        if rejim == "BOĞA": nedenler.append("Piyasa boğa rejiminde")
        return ", ".join(nedenler) if nedenler else "Normal"
    
    df['Neden Alınmalı?'] = df.apply(neden_yukselir, axis=1)
    
    df['Tavan Potansiyeli (%)'] = df['Tavan Potansiyeli (%)'].apply(format_percent)
    df['Gün %'] = df['Gün %'].apply(format_percent)
    df['Monte Carlo Olasılığı (%)'] = df['Monte Carlo Olasılığı (%)'].round(2).apply(lambda x: f"%{x}")
    for col in ['Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 
                'Getiri % (Son 6 ay)', 'Getiri % (Yılbaşından)', 'Getiri % (Son 1 yıl)', 
                'Getiri % (Son 3 yıl)', 'Getiri % (Son 5 yıl)']:
        df[col] = df[col].apply(format_percent)
    
    df['Fiyat'] = df['Fiyat'].apply(lambda x: f"{float(x):.2f} TL")
    df = df.drop(columns=['52H_Yuksek'], errors='ignore')
    
    return df

# --- VERİ YÜKLEME ---
with st.spinner("Quantum YZ çalışıyor..."):
    tum_hisseler_raw = tum_bist_hisselerini_getir()
    if not tum_hisseler_raw.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler_raw)
    else:
        analizli_df = pd.DataFrame()

# --- PİYASA SAATİ KONTROLÜ VE TELEGRAM BİLDİRİMİ ---
if not analizli_df.empty:
    now = datetime.now()
    piyasa_acik = (now.weekday() < 5) and (now.hour >= 9 and now.hour < 18)
    
    if 'bildirilen_tarih' not in st.session_state or st.session_state['bildirilen_tarih'] != str(now.date()):
        st.session_state['bildirilen_hisseler'] = []
        st.session_state['bildirilen_tarih'] = str(now.date())

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔔 Telegram Testi")
    if st.sidebar.button("Test Bildirimi Gönder", key="telegram_test_btn"):
        test_mesaji = "✅ <b>Test Bildirimi Başarılı!</b>\n\nQuantum BIST Terminali çalışıyor ve Telegram bağlantısı aktif."
        send_telegram_alert(test_mesaji)
        st.sidebar.success("Test mesajı gönderildi. Telegram'ı kontrol edin.")

    if piyasa_acik:
        # Olasılık değerini doğru okumak için % işaretini kaldır
        bildirim_listesi = analizli_df[
            (analizli_df['Yatırım Fırsat Skoru'] >= 75) & 
            (analizli_df['Monte Carlo Olasılığı (%)'].str.replace('%', '').astype(float) > 15)
        ]
        
        for _, row in bildirim_listesi.iterrows():
            hisse = row['Hisse']
            if hisse not in st.session_state['bildirilen_hisseler']:
                mesaj = f"🚀 <b>Kuantum Alarmı!</b>\n\n"
                mesaj += f"📈 Hisse: <b>{hisse}</b>\n"
                mesaj += f"💰 Fiyat: {row['Fiyat']}\n"
                mesaj += f"📊 Skor: <b>{row['Yatırım Fırsat Skoru']}</b>\n"
                mesaj += f"🎲 5 Günlük %10 Olasılığı: {row['Monte Carlo Olasılığı (%)']}\n"
                mesaj += f"💡 Neden: {row['Neden Alınmalı?']}"
                
                send_telegram_alert(mesaj)
                st.session_state['bildirilen_hisseler'].append(hisse)

# --- SOL MENÜ VE DİĞER SEKMELER ---
with st.sidebar:
    st.header("📋 Keşfet")
    if st.button("🔍 Radar", use_container_width=True): st.session_state['menu'] = "Radar"
    if st.button("📈 Hisseler", use_container_width=True): st.session_state['menu'] = "Hisse"
    if st.button("🏛️ Endeksler", use_container_width=True): st.session_state['menu'] = "Endeksler"
    if st.button("👑 VIP", use_container_width=True): st.session_state['menu'] = "VIP"
    if st.button("🪙 Kripto", use_container_width=True): st.session_state['menu'] = "Kripto"
    st.markdown("---")
    st.header("🧠 Analiz")
    if st.button("📊 Temel Analiz", use_container_width=True): st.session_state['menu'] = "Temel Analiz"
    if st.button("🔬 Detaylı Analiz", use_container_width=True): st.session_state['menu'] = "Detaylı Analiz"
    if st.button("💎 Orijinal Hisseler", use_container_width=True): st.session_state['menu'] = "Orijinal Hisseler"
    if st.button("📈 Grafik Analizi", use_container_width=True): st.session_state['menu'] = "Grafik Analizi"
    st.markdown("---")
    if 'menu' not in st.session_state: st.session_state['menu'] = "Radar"
    menu_secim = st.session_state['menu']

# Üst Sekmeler
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Getiri", "💎 Değerleme", "📈 Karlılık", "🚀 Büyüme", 
    "📋 Bilanço", "💵 Gelir Tablosu", "💧 Nakit Akım", "🔥 Yüksek Potansiyel"
])

with tab1:
    st.subheader("📊 Getiri Tablosu")
    if not analizli_df.empty:
        df_getiri = analizli_df.sort_values(by='Hisse', ascending=True)
        cols = ['Hisse', 'Fiyat', 'Gün %', 'Hacim', 
                'Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 
                'Getiri % (Son 3 ay)', 'Getiri % (Son 6 ay)', 
                'Getiri % (Yılbaşından)', 'Getiri % (Son 1 yıl)', 
                'Getiri % (Son 3 yıl)', 'Getiri % (Son 5 yıl)']
        st.dataframe(df_getiri[cols], width='stretch', hide_index=True)
    else:
        st.error("Veri yüklenemedi.")

with tab2:
    st.subheader("💎 Değerleme")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Piyasa Değeri', 'F/K', 'PD/DD', 'Sektörel Değerleme', 'Yatırım Fırsat Skoru']], width='stretch', hide_index=True)

with tab3:
    st.subheader("📈 Karlılık")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Gün %', 'RSI', 'ROE', 'Net Marj', 'AI Sinyal']], width='stretch', hide_index=True)

with tab4:
    st.subheader("🚀 Büyüme")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Getiri % (Son 1 ay)', 'Getiri % (Son 3 ay)', 'Getiri % (Yılbaşından)']], width='stretch', hide_index=True)

with tab5:
    st.subheader("📋 Bilanço")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Piyasa Değeri', 'Borç/Özkaynak']], width='stretch', hide_index=True)

with tab6:
    st.subheader("💵 Gelir Tablosu")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim', 'Net Marj']], width='stretch', hide_index=True)

with tab7:
    st.subheader("💧 Nakit Akım")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Hacim', 'Gün %']], width='stretch', hide_index=True)

with tab8:
    st.subheader("🔥 Yüksek Potansiyelli Hisseler")
    if not analizli_df.empty:
        df_tavan = analizli_df.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(20)
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Yatırım Fırsat Skoru', 'Monte Carlo Olasılığı (%)', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)
        st.success("Piyasa açıkken skoru 75+ ve olasılığı %15+ olan hisseler otomatik bildirilir.")

# --- SOL MENÜ MODÜLLERİ ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Profesyonel Temel Analiz")
    
    # Makro Veriler
    macro = get_macro_data()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Enflasyon", f"%{macro['enflasyon']}")
    col2.metric("Faiz", f"%{macro['faiz']}")
    col3.metric("Büyüme", f"%{macro['buyume']}")
    col4.metric("CDS", macro['cds'])
    
    st.markdown("---")
    
    # Hisse Bazında Temel Veriler
    st.subheader("📊 Hisse Bazında Temel Analiz Verileri")
    if not analizli_df.empty:
        temel_cols = ['Hisse', 'Fiyat', 'Piyasa Değeri', 'F/K', 'PD/DD', 
                      'ROE', 'Net Marj', 'Borç/Özkaynak', 'Temettü Verimi', 
                      'Sektörel Değerleme', 'Yatırım Fırsat Skoru', 'AI Sinyal']
        df_temel = analizli_df[temel_cols].copy()
        
        # Sayısal sütunları formatla
        for col in ['F/K', 'PD/DD', 'ROE', 'Net Marj', 'Borç/Özkaynak', 'Temettü Verimi']:
            df_temel[col] = df_temel[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        
        st.dataframe(df_temel, use_container_width=True, hide_index=True)
        
        # Detaylı Analiz İçin Hisse Seçimi
        st.markdown("---")
        st.subheader("🔍 Detaylı Hisse Analizi")
        secilen_hisse = st.selectbox("Bir Hisse Seçin", options=analizli_df['Hisse'].tolist(), key="temel_detay")
        
        if secilen_hisse:
            detay = analizli_df[analizli_df['Hisse'] == secilen_hisse].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### 📌 {secilen_hisse}")
                st.write(f"**Fiyat:** {detay['Fiyat']}")
                st.write(f"**Günlük Değişim:** {detay['Gün %']}")
                st.write(f"**Piyasa Değeri:** {detay['Piyasa Değeri']}")
                st.write(f"**Hacim (TL):** {detay['Hacim']}")
                st.write(f"**52 Hafta Yüksek:** {detay.get('52H_Yuksek', 'N/A')}")
                st.write(f"**RSI:** {detay['RSI']:.2f}" if pd.notna(detay['RSI']) else "**RSI:** N/A")
            
            with col2:
                st.markdown(f"### 📊 Temel Göstergeler")
                st.write(f"**F/K:** {detay['F/K']:.2f}" if pd.notna(detay['F/K']) else "**F/K:** N/A")
                st.write(f"**PD/DD:** {detay['PD/DD']:.2f}" if pd.notna(detay['PD/DD']) else "**PD/DD:** N/A")
                st.write(f"**ROE:** {detay['ROE']:.2f}%" if pd.notna(detay['ROE']) else "**ROE:** N/A")
                st.write(f"**Net Marj:** {detay['Net Marj']:.2f}%" if pd.notna(detay['Net Marj']) else "**Net Marj:** N/A")
                st.write(f"**Borç/Özkaynak:** {detay['Borç/Özkaynak']:.2f}" if pd.notna(detay['Borç/Özkaynak']) else "**Borç/Özkaynak:** N/A")
                st.write(f"**Temettü Verimi:** {detay['Temettü Verimi']:.2f}%" if pd.notna(detay['Temettü Verimi']) else "**Temettü Verimi:** N/A")
                st.write(f"**Sektörel Değerleme:** {detay['Sektörel Değerleme']}")
                st.write(f"**AI Sinyal:** {detay['AI Sinyal']}")
                st.write(f"**Yatırım Fırsat Skoru:** {detay['Yatırım Fırsat Skoru']}")

elif menu_secim == "Grafik Analizi":
    st.subheader("📈 Çoklu Hisse Grafik Analizi")
    if not analizli_df.empty:
        secilen = st.multiselect("Hisse Seçin", options=analizli_df['Hisse'].tolist(), default=["THYAO", "GARAN"])
        if st.button("Grafikleri Çiz"):
            import yfinance as yf
            fig = go.Figure()
            for hisse in secilen:
                veri = yf.download(f"{hisse}.IS", period="6mo", progress=False, auto_adjust=False)
                if not veri.empty:
                    veri['Normalize'] = (veri['Close'] / veri['Close'].iloc[0]) * 100
                    fig.add_trace(go.Scatter(x=veri.index, y=veri['Normalize'], mode='lines', name=hisse))
            fig.update_layout(template='plotly_dark', height=600)
            st.plotly_chart(fig, width='stretch')

elif menu_secim == "Detaylı Analiz":
    st.subheader("🔬 Detaylı Analiz")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(10), width='stretch', hide_index=True)

elif menu_secim == "Orijinal Hisseler":
    st.subheader("🚀 Orijinal Hisseler")
    if not analizli_df.empty:
        st.dataframe(analizli_df.head(20), width='stretch', hide_index=True)
else:
    st.success(f"{menu_secim} modülü aktif.")
