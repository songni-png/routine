import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
import requests
import os
from geopy.distance import geodesic

# ▶ SQLite 데이터베이스 설정
DB_FILE = os.path.join(os.getcwd(), "click_log.db")

# ▶ 데이터베이스 연결 및 테이블 생성 (CREATE TABLE IF NOT EXISTS)
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ClickLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            name TEXT,
            category TEXT,
            location TEXT,
            distance_km REAL
        )
    """)
    conn.commit()
    conn.close()

# ▶ 클릭 이벤트 저장 함수
def log_click(name, category, location, distance_km):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ClickLog (timestamp, name, category, location, distance_km)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, category, location, distance_km))
    conn.commit()
    conn.close()

# ▶ 데이터베이스 초기화
init_db()

# ▶ OpenWeatherMap API 키
API_KEY = "db993432d1b5f597ea03fd182d005ce9"

st.set_page_config(page_title="회복 루틴 추천기", page_icon="🧘", layout="centered")

# ▶ 위치 정보 가져오기 (비동기 Promise 방식)
loc = streamlit_js_eval(
    js_expressions="""
    new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
            (err) => reject(err)
        );
    })
    """,
    key="get_location_with_coords"
)

# 현재 위치 설정
lat, lon = loc["latitude"], loc["longitude"] if loc and "latitude" in loc else (None, None)

# 데이터 파일 경로 설정
PLACE_FILE = os.path.join(os.getcwd(), "장소_카테고리_최종분류.csv")

# 데이터 로드
def load_data():
    df = pd.read_csv(PLACE_FILE, encoding="cp949", header=1)
    df = df.dropna(subset=["LAT", "LON", "CATEGORY"])
    df["LAT"], df["LON"] = df["LAT"].astype(float), df["LON"].astype(float)
    return df

df = load_data()

# 거리 계산 함수
def compute_distance(row):
    return geodesic((lat, lon), (row["LAT"], row["LON"])).km if lat and lon else None

# 날씨 정보 가져오기 함수
def get_weather(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": "metric",
            "lang": "kr"
        }
        res = requests.get(url, params=params)
        data = res.json()
        return {
            "weather": data["weather"][0]["description"],
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"]
        }
    except:
        return {"weather": "에러", "temp": "-", "humidity": "-"}

# ▶ 추천 버튼 동작
if st.button("카테고리별 랜덤 장소 추천받기") and lat and lon:
    df["DIST_KM"] = df.apply(compute_distance, axis=1)
    nearby_df = df[df["DIST_KM"] <= 2.5]
    sampled_df = nearby_df.groupby("CATEGORY", group_keys=False).apply(lambda x: x.sample(1))

    if sampled_df.empty:
        st.warning("❌ 조건에 맞는 장소가 없습니다.")
    else:
        st.session_state["recommendation"] = sampled_df
        st.session_state["selected_place"] = None

# ▶ 추천 유지
sampled_df = st.session_state.get("recommendation")
selected_place = st.session_state.get("selected_place")

if sampled_df is not None:
    weather = get_weather(lat, lon)
    st.markdown(f"### 🌤️ 현재 위치 날씨")
    st.write(f"- 날씨: {weather['weather']}")
    st.write(f"- 기온: {weather['temp']}°C")
    st.write(f"- 습도: {weather['humidity']}%")
    st.markdown("---")

    st.markdown(f"## 📌 추천 장소")

    for _, row in sampled_df.iterrows():
        st.markdown(f"### 🏷️ {row['CATEGORY']}: **{row['NAME']}**")
        st.markdown(f"- 📍 위치: {row['LOCATION']}")
        st.markdown(f"- 🏷️ 태그: {row.get('TAG', '없음')}")
        st.markdown(f"- 📏 거리: 약 {row['DIST_KM']:.2f} km")

        if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
            st.session_state["selected_place"] = row['NAME']
            selected_place = row['NAME']
            log_click(row['NAME'], row['CATEGORY'], row['LOCATION'], row['DIST_KM'])

        if selected_place == row['NAME']:
            st.success(f"✅ '{row['NAME']}' 상세 내용")
            st.write(f"- 위치: {row['LOCATION']}")
            st.write(f"- 카테고리: {row['CATEGORY']}")
            st.write(f"- 거리: {row['DIST_KM']:.2f} km")

        st.markdown("---")

    st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))

# ▶ 클릭 로그 확인 및 다운로드
st.markdown("## 🗂️ 내가 클릭한 장소 기록")
conn = sqlite3.connect(DB_FILE)
log_df = pd.read_sql("SELECT * FROM ClickLog ORDER BY id DESC LIMIT 10", conn)
conn.close()

if not log_df.empty:
    st.dataframe(log_df)
else:
    st.info("아직 클릭한 장소가 없어요!")
