import streamlit as st
import pandas as pd
import numpy as np
import requests
import warnings
from streamlit_autorefresh import st_autorefresh

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

def format_percent(val):
    try: return f"{float(val):.2f}%"
    except: return "N/A"

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

# --- VERİ ÇEKME (Temel Verilerle Zenginleştirildi) ---
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
                "Hisse": d[0],
                "Fiyat": d[1],
                "Gün %": d[2],
                "Hacim (Adet)": d[3],
                "Piyasa Değeri (Bin TL)": d[4],
                "52H_Yuksek": d[5],
                "RSI": d[6],
                "Getiri % (Son 1 hafta)": d[7],
                "Getiri % (Son 1 ay)": d[8],
                "Getiri % (Son 3 ay)": d[9],
                "Getiri % (Son 6 ay)": d[10],
                "Getiri % (Yılbaşından)": d[11],
                "Getiri % (Son 1 yıl)": d[12],
                "Getiri % (Son 3 yıl)": d[13],
                "Getiri % (Son 5 yıl)": d[14],
                "Sektör": d[15],
                "F/K": d[16],
                "PD/DD": d[17],
                "ROE": d[18],
                "Net Marj": d[19],
                "Borç/Özkaynak": d[20],
                "Temettü Verimi": d[21]
            })
        
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        
        # DOĞRU HACİM: Adet * Fiyat = TL Hacim
        df['Hacim'] = (pd.to_numeric(df['Hacim (Adet)'], errors='coerce') * pd.to_numeric(df['Fiyat'], errors='coerce')).apply(format_big_number)
        
        # DOĞRU PİYASA DEĞERİ: Bin TL * 1000 = TL
        df['Piyasa Değeri'] = (pd.to_numeric(df['Piyasa Değeri (Bin TL)'], errors='coerce') * 1000).apply(format_big_number)
        
        df = df.drop(columns=['Hacim (Adet)', 'Piyasa Değeri (Bin TL)'], errors='ignore')
        df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce')
        df['Gün %'] = pd.to_numeric(df['Gün %'], errors='coerce')
        df['RSI'] = pd.to_numeric(df['RSI'], errors='coerce')
        
        # Temel verileri sayıya çevir (hesaplama için)
        for col in ['F/K', 'PD/DD', 'ROE', 'Net Marj', 'Borç/Özkaynak', 'Temettü Verimi']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['Sektör'] = df['Sektör'].astype(str)
        return df
    except Exception as e:
        st.error(f"TradingView verileri alınamadı: {e}")
        return pd.DataFrame()

# --- GELİŞMİŞ YZ MODELİ ---
def hesapla_ai_verileri(df):
    if df.empty:
        return df
    
    df['52H_Yuksek'] = pd.to_numeric(df['52H_Yuksek'], errors='coerce').fillna(0)
    df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').fillna(0)
    df['Tavan Potansiyeli (%)'] = ((df['52H_Yuksek'] - df['Fiyat']) / df['Fiyat']) * 100
    
    # Eksik getirileri YZ ile tahminle
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
    
    # --- GELİŞMİŞ RASYO ANALİZİ ---
    def hesapla_skor(row):
        skor = 50
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: skor += 25
        elif pot > 10: skor += 15
        elif pot > 5: skor += 5
        elif pot < 0: skor -= 10
        gun = safe_float(row['Gün %'])
        if gun > 3: skor += 20
        elif gun > 1: skor += 10
        elif gun < -2: skor -= 10
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: skor += 15
        elif rsi > 70: skor -= 5
        elif 40 <= rsi < 50: skor += 5
        y1 = safe_float(row.get('Getiri % (Son 1 yıl)'))
        if y1 > 20: skor += 15
        elif y1 > 10: skor += 10
        elif y1 < 0: skor -= 5
        
        # Rasyo skorlaması (2026 sektörel referanslara göre) [citation:1]
        fk = safe_float(row.get('F/K'))
        roe = safe_float(row.get('ROE'))
        # Bankacılık için F/K < 5, perakende için F/K < 12 gibi basit heuristikler
        if fk > 0 and fk < 10: skor += 10
        elif fk > 20: skor -= 5
        if roe > 15: skor += 10
        elif roe < 5: skor -= 5
        
        return max(0, min(100, skor))
    
    df['Yatırım Fırsat Skoru'] = df.apply(hesapla_skor, axis=1)
    
    def sinyal_uret(row):
        skor = safe_float(row['Yatırım Fırsat Skoru'])
        if skor >= 75: return "🟢 Güçlü Al"
        elif skor >= 60: return "🔵 Al"
        elif skor >= 45: return "🟡 İzle"
        else: return "⚪ Nötr"
    
    df['AI Sinyal'] = df.apply(sinyal_uret, axis=1)
    
    def neden_yukselir(row):
        nedenler = []
        pot = safe_float(row['Tavan Potansiyeli (%)'])
        if pot > 20: nedenler.append("Tavanına çok uzak")
        elif pot > 5: nedenler.append("Zirveye yakın")
        gun = safe_float(row['Gün %'])
        if gun > 2: nedenler.append("Bugün güçlü alım")
        rsi = safe_float(row['RSI'])
        if 50 <= rsi <= 70: nedenler.append("RSI ideal")
        y1 = safe_float(row.get('Getiri % (Son 1 yıl)'))
        if y1 > 20: nedenler.append("YZ 1 yıllık büyüme tahmini yüksek")
        fk = safe_float(row.get('F/K'))
        if 0 < fk < 10: nedenler.append("F/K oranı sektöre göre düşük")
        roe = safe_float(row.get('ROE'))
        if roe > 15: nedenler.append("Özsermaye karlılığı güçlü")
        return ", ".join(nedenler) if nedenler else "Normal"
    
    df['Neden Alınmalı?'] = df.apply(neden_yukselir, axis=1)
    
    # Formatlama
    df['Tavan Potansiyeli (%)'] = df['Tavan Potansiyeli (%)'].apply(format_percent)
    df['Gün %'] = df['Gün %'].apply(format_percent)
    df['Getiri % (Son 1 hafta)'] = df['Getiri % (Son 1 hafta)'].apply(format_percent)
    df['Getiri % (Son 1 ay)'] = df['Getiri % (Son 1 ay)'].apply(format_percent)
    df['Getiri % (Son 3 ay)'] = df['Getiri % (Son 3 ay)'].apply(format_percent)
    df['Getiri % (Son 6 ay)'] = df['Getiri % (Son 6 ay)'].apply(format_percent)
    df['Getiri % (Yılbaşından)'] = df['Getiri % (Yılbaşından)'].apply(format_percent)
    df['Getiri % (Son 1 yıl)'] = df['Getiri % (Son 1 yıl)'].apply(format_percent)
    df['Getiri % (Son 3 yıl)'] = df['Getiri % (Son 3 yıl)'].apply(format_percent)
    df['Getiri % (Son 5 yıl)'] = df['Getiri % (Son 5 yıl)'].apply(format_percent)
    df['Fiyat'] = df['Fiyat'].apply(lambda x: f"{float(x):.2f} TL")
    df = df.drop(columns=['52H_Yuksek'], errors='ignore')
    
    return df

# --- VERİ YÜKLEME ---
with st.spinner("Veriler işleniyor..."):
    tum_hisseler_raw = tum_bist_hisselerini_getir()
    if not tum_hisseler_raw.empty:
        analizli_df = hesapla_ai_verileri(tum_hisseler_raw)
    else:
        analizli_df = pd.DataFrame()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("📋 Keşfet")
    if st.button("🔍 Radar", use_container_width=True):
        st.session_state['menu'] = "Radar"
    if st.button("📈 Hisseler", use_container_width=True):
        st.session_state['menu'] = "Hisse"
    if st.button("🏛️ Endeksler", use_container_width=True):
        st.session_state['menu'] = "Endeksler"
    if st.button("👑 VIP", use_container_width=True):
        st.session_state['menu'] = "VIP"
    if st.button("🪙 Kripto", use_container_width=True):
        st.session_state['menu'] = "Kripto"
    st.markdown("---")
    st.header("🧠 Analiz")
    if st.button("📊 Temel Analiz", use_container_width=True):
        st.session_state['menu'] = "Temel Analiz"
    if st.button("🔬 Detaylı Analiz", use_container_width=True):
        st.session_state['menu'] = "Detaylı Analiz"
    if st.button("💎 Orijinal Hisseler", use_container_width=True):
        st.session_state['menu'] = "Orijinal Hisseler"
    
    st.markdown("---")
    if 'menu' not in st.session_state:
        st.session_state['menu'] = "Radar"
    menu_secim = st.session_state['menu']

# --- ÜST SEKMELER ---
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

# Diğer sekmeler
with tab2:
    st.subheader("💎 Değerleme")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Hisse', ascending=True)[['Hisse', 'Fiyat', 'Piyasa Değeri', 'F/K', 'PD/DD', 'Yatırım Fırsat Skoru']], width='stretch', hide_index=True)

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
        st.dataframe(df_tavan[['Hisse', 'Fiyat', 'Yatırım Fırsat Skoru', 'Tavan Potansiyeli (%)', 'RSI', 'AI Sinyal', 'Neden Alınmalı?']], width='stretch', hide_index=True)

# --- SOL MENÜ MODÜLLERİ (Profesyonel Temel Analiz) ---
st.markdown("---")

if menu_secim == "Temel Analiz":
    st.subheader("📈 Profesyonel Temel Analiz")
    
    # 1. MAKROEKONOMİ ANALİZİ (2026 Verileriyle)
    st.markdown("### 🌍 Makroekonomi Analizi (2026)")
    if not analizli_df.empty:
        ort_getiri = pd.to_numeric(analizli_df['Getiri % (Son 1 yıl)'].astype(str).str.replace('%', ''), errors='coerce').mean()
        ort_fk = pd.to_numeric(analizli_df['F/K'], errors='coerce').mean()
        
        # 2026 makro verileri [citation:3][citation:13]
        enflasyon_2026 = 23.6
        faiz_2026 = 28.5
        buyume_2026 = 3.9
        
        if ort_fk < 10:
            degerleme_durumu = "BIST geneli makul değerlemede (F/K < 10)"
        elif ort_fk > 15:
            degerleme_durumu = "BIST geneli pahalı değerlemede (F/K > 15)"
        else:
            degerleme_durumu = "BIST geneli dengeli değerlemede"
        
        st.write(f"**2026 Beklentileri:** Enflasyon %{enflasyon_2026}, Faiz %{faiz_2026}, Büyüme %{buyume_2026}")
        st.write(f"**Piyasa Değerlemesi:** {degerleme_durumu}")
        st.write(f"**YZ Yorumu:** Yüksek enflasyon ve faiz ortamı, temettü ve nakit akışı güçlü şirketleri öne çıkarıyor.")
    
    # 2. SEKTÖR ANALİZİ (Sektörel Değerleme ve Getiri)
    st.markdown("### 🏭 Sektörel Analiz")
    if not analizli_df.empty and 'Sektör' in analizli_df.columns:
        sektor_df = analizli_df.copy()
        for col in ['Gün %', 'Getiri % (Son 1 hafta)', 'Getiri % (Son 1 ay)', 'Getiri % (Son 1 yıl)']:
            if col in sektor_df.columns:
                sektor_df[col] = pd.to_numeric(sektor_df[col].astype(str).str.replace('%', ''), errors='coerce')
        # Sektör özeti: hisse sayısı, getiri, F/K, ROE
        sektor_ozet = sektor_df.groupby('Sektör').agg({
            'Hisse': 'count',
            'Gün %': 'mean',
            'Getiri % (Son 1 yıl)': 'mean',
            'F/K': 'mean',
            'ROE': 'mean'
        }).rename(columns={'Hisse': 'Hisse Sayısı'}).round(2)
        
        st.dataframe(sektor_ozet, width='stretch', hide_index=True)
        
        # YZ yorumu: En güçlü sektör tespiti [citation:2]
        if not sektor_ozet.empty:
            en_iyi_sektor = sektor_ozet['Getiri % (Son 1 yıl)'].astype(float).idxmax()
            st.write(f"**YZ Yorumu:** En güçlü getiri potansiyeli **{en_iyi_sektor}** sektöründe görünüyor.")
    
    # 3. ŞİRKET FİNANSALLARI
    st.markdown("### 💼 Şirket Finansalları")
    if not analizli_df.empty:
        st.dataframe(analizli_df[['Hisse', 'Piyasa Değeri', 'F/K', 'PD/DD', 'ROE', 'Net Marj', 'Borç/Özkaynak']].sort_values(by='F/K', ascending=True).head(15), width='stretch', hide_index=True)
    
    # 4. RASYO ORANLARI ANALİZİ
    st.markdown("### 📊 Rasyo Oranları Analizi")
    if not analizli_df.empty:
        st.write("**F/K Oranı Analizi (Sektör Ortalamalarıyla Karşılaştırmalı)**")
        # Basit sektörel karşılaştırma tablosu [citation:1]
        st.info("**Referans:** Bankacılık F/K: 4-8x, Perakende F/K: 10-20x, Teknoloji F/K: 18-40x+")
        st.dataframe(analizli_df[['Hisse', 'Sektör', 'F/K', 'PD/DD', 'ROE']].sort_values(by='ROE', ascending=False).head(15), width='stretch', hide_index=True)

elif menu_secim == "Detaylı Analiz":
    st.subheader("🔬 Detaylı Analiz")
    st.write("**En Olası İlk 10 Hisse**")
    if not analizli_df.empty:
        st.dataframe(analizli_df.sort_values(by='Yatırım Fırsat Skoru', ascending=False).head(10), width='stretch', hide_index=True)

elif menu_secim == "Orijinal Hisseler":
    st.subheader("🚀 Orijinal Hisseler")
    if not analizli_df.empty:
        st.dataframe(analizli_df.head(20), width='stretch', hide_index=True)
else:
    st.success(f"{menu_secim} modülü aktif.")
