import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import requests
import os

API_KEY = "db993432d1b5f597ea03fd182d005ce9"

st.set_page_config(page_title="회복 루틴 추천기", page_icon="🧘", layout="centered")
st.title("🧘 회복이 필요한 날을 위한 맞춤 루틴 추천기")
st.markdown(f"⏰ 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

loc = streamlit_js_eval(
    js_expressions="""
        new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
                (err) => reject(err)
            );
        })
    """,
    key="get_location",
    label="위치 권한 요청"
)

if loc and isinstance(loc, dict) and "latitude" in loc:
    lat, lon = loc["latitude"], loc["longitude"]
    st.success(f"📍 현재 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")
else:
    st.warning("📡 위치 권한이 허용되지 않았습니다.")
    lat, lon = None, None

radius = st.slider("추천 반경 (km)", 1.0, 5.0, 2.5, step=0.1)

# ▶ 데이터 파일 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
PLACE_FILE = os.path.join(current_dir, "장소_카테고리_최종분류.csv")
CLICK_FILE = os.path.join(current_dir, "click_log.csv")


try:
    df = pd.read_csv(PLACE_FILE, encoding="cp949")
    df = df.dropna(subset=["LAT", "LON", "CATEGORY"])
    df["LAT"] = df["LAT"].astype(float)
    df["LON"] = df["LON"].astype(float)
    df["TAG"] = df["TAG"].fillna("")
except Exception as e:
    st.error(f"❌ 장소 파일을 불러올 수 없습니다: {e}")
    st.stop()

# 📍 거리 계산 함수 (float 반환)
def compute_distance(row):
    return geodesic((lat, lon), (row["LAT"], row["LON"])).km if lat and lon else None

# ☁️ 날씨 API
@st.cache_data
def get_weather(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric", "lang": "kr"}
        res = requests.get(url, params=params)
        data = res.json()
        return {
            "weather": data["weather"][0]["description"],
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"]
        }
    except:
        return {"weather": "에러", "temp": "-", "humidity": "-"}

# 📊 클릭 로그 기반 상위 카테고리 분석
if os.path.exists(CLICK_FILE):
    log_df = pd.read_csv(CLICK_FILE)
    top_cats_series = log_df['category'].value_counts().head(3)
    top_cats = top_cats_series.index.tolist()
else:
    top_cats_series = pd.Series()
    top_cats = []

if not top_cats_series.empty:
    st.markdown("### ⭐ 가장 많이 선택된 카테고리")
    for cat, count in top_cats_series.items():
        st.markdown(f"- {cat} ({count}회 선택됨)")

# 🎯 추천 버튼 동작
if st.button("카테고리별 랜덤 장소 추천받기") and lat and lon:
    df["DIST_KM"] = df.apply(compute_distance, axis=1)
    nearby_df = df[df["DIST_KM"] <= radius]
    if nearby_df.empty:
        st.warning("❌ 조건에 맞는 장소가 없습니다.")
    else:
        sampled_df = nearby_df.groupby("CATEGORY", group_keys=False).apply(lambda x: x.sample(1)).reset_index(drop=True)
        sampled_df["cat_order"] = sampled_df["CATEGORY"].apply(lambda x: top_cats.index(x) if x in top_cats else 99)
        sampled_df = sampled_df.sort_values("cat_order").drop(columns="cat_order")

        st.session_state["recommendation"] = sampled_df
        st.session_state["filtered"] = nearby_df
        st.session_state["click_count"] = st.session_state.get("click_count", 0) + 1

# 📋 세션 데이터 불러오기
sampled_df = st.session_state.get("recommendation")
filtered_df = st.session_state.get("filtered")
click_count = st.session_state.get("click_count", 0)

# 🌦 날씨 및 지도 출력
if sampled_df is not None:
    weather = get_weather(lat, lon)
    st.markdown("### 🌤️ 현재 위치 날씨")
    st.write(f"- 날씨: {weather['weather']}")
    st.write(f"- 기온: {weather['temp']}°C")
    st.write(f"- 습도: {weather['humidity']}%")
    st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))

    for _, row in sampled_df.iterrows():
        st.markdown(f"### 🏷️ {row['CATEGORY']}: **{row['NAME']}**")
        st.markdown(f"- 위치: {row['LOCATION']}")
        st.markdown(f"- 태그: {row.get('TAG', '없음')}")
        try:
            st.markdown(f"- 거리: {float(row['DIST_KM']):.2f} km")
        except (ValueError, TypeError):
            st.markdown("- 거리: 알 수 없음")

        # 🔍 상세 보기 버튼
        if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
            st.session_state["selected_place"] = row["NAME"]

            log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": row["NAME"],
                "category": row["CATEGORY"],
                "location": row["LOCATION"],
                "distance_km": float(row["DIST_KM"]) if isinstance(row["DIST_KM"], (float, int)) else ""
            }
            pd.DataFrame([log]).to_csv(CLICK_FILE, mode="a", index=False, header=not os.path.exists(CLICK_FILE))

        # ➕ 더보기 버튼 (2회차 이상)
        if click_count >= 2 and row["CATEGORY"] in top_cats:
            if st.button(f"[🔎 {row['CATEGORY']}] 관련 카테고리 더보기", key=f"more_{row['CATEGORY']}"):
                more_places = filtered_df[(filtered_df["CATEGORY"] == row["CATEGORY"]) & (filtered_df["NAME"] != row["NAME"])]
                more_places = more_places.sort_values("DIST_KM").head(3)
                if more_places.empty:
                    st.info("📭 관련 장소가 없습니다.")
                else:
                    for _, mp in more_places.iterrows():
                        st.markdown(f"- **{mp['NAME']}**")
                        st.markdown(f"  - 위치: {mp['LOCATION']}")
                        st.markdown(f"  - 태그: {mp.get('TAG', '없음')}")
                        try:
                            st.markdown(f"  - 거리: {float(mp['DIST_KM']):.2f} km")
                        except (ValueError, TypeError):
                            st.markdown("  - 거리: 알 수 없음")

        st.markdown("---")

# 📜 클릭 로그 테이블
if os.path.exists(CLICK_FILE):
    st.markdown("## 🗂️ 내가 클릭한 장소 기록")
    log_df = pd.read_csv(CLICK_FILE)
    st.dataframe(log_df.tail(10))
