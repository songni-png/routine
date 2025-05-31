import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
import requests
import os
from geopy.distance import geodesic

# ▶ OpenWeatherMap API 키
API_KEY = "db993432d1b5f597ea03fd182d005ce9"

st.set_page_config(page_title="회복 루틴 추천기", page_icon="🧘", layout="centered")

# ▶ 페이지 상태 관리 (초기 설정)
if "page" not in st.session_state:
    st.session_state.page = "home"

if "selected_place" not in st.session_state:
    st.session_state.selected_place = None

# 1. 위치 정보 가져오기 (비동기 Promise 방식)
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
current_dir = os.path.dirname(os.path.abspath(__file__))
PLACE_FILE = os.path.join(current_dir, "장소_카테고리_최종분류.csv")

# 데이터 로드
def load_data():
    df = pd.read_csv(PLACE_FILE, encoding="cp949")
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
    except Exception:
        return {"weather": "에러", "temp": "-", "humidity": "-"}

# ▶ 페이지 렌더링
if st.session_state.page == "detail":
    place = st.session_state.selected_place
    st.title(f"🔍 {place['NAME']} 상세 보기")
    st.write(f"- 위치: {place['LOCATION']}")
    st.write(f"- 카테고리: {place['CATEGORY']}")
    st.write(f"- 거리: {place['DIST_KM']:.2f} km")

    # ▶ 뒤로 가기 버튼 추가
    if st.button("⬅️ 뒤로 가기"):
        st.session_state.page = "home"
        st.rerun()

else:  # 홈 페이지
    st.title("🧘 회복 루틴 추천기")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"⏰ 현재 시간: {now}")

    activity = st.radio("오늘 얼마나 활동하셨나요?", ["많이 움직였어요", "적당히 움직였어요", "거의 안 움직였어요"])
    social = st.radio("얼마나 사람을 만나셨나요?", ["많은 사람을 만났어요", "혼자 있었어요"])
    tag = st.selectbox("원하는 회복 태그를 골라주세요", ["힐링", "에너지","감정 정화","감정 자극", "집중력", "안정"])

    # 위치 정보 출력
    if lat and lon:
        st.success(f"📍 현재 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")
    else:
        st.info("📡 위치 정보를 불러오는 중이거나, 위치 권한이 허용되지 않았습니다.")

    # 반경 설정
    radius = st.slider("추천 반경 (km)", 1.0, 5.0, 2.5, step=0.1)

    if lat and lon:
        df["DIST_KM"] = df.apply(compute_distance, axis=1)
        nearby_df = df[df["DIST_KM"] <= radius]
    else:
        nearby_df = df

    if st.button("카테고리별 랜덤 장소 추천받기") and lat and lon:
        with st.spinner("추천 장소를 찾는 중입니다..."):
            sampled_df = nearby_df.groupby("CATEGORY", group_keys=False).apply(lambda x: x.sample(1))

            if sampled_df.empty:
                st.warning("❌ 조건에 맞는 장소가 없습니다.")
            else:
                # 현재 위치 날씨 표시
                weather = get_weather(lat, lon)
                st.markdown(f"### 🌤️ 현재 위치 날씨")
                st.write(f"- 날씨: {weather['weather']}")
                st.write(f"- 기온: {weather['temp']}°C")
                st.write(f"- 습도: {weather['humidity']}%")
                st.markdown("---")

                st.markdown(f"## 📌 반경 {radius:.1f}km 이내 추천 장소")

                for _, row in sampled_df.iterrows():
                    st.markdown(f"### 🏷️ {row['CATEGORY']}: **{row['NAME']}**")
                    st.markdown(f"- 📍 위치: {row['LOCATION']}")
                    st.markdown(f"- 📏 거리: 약 {row['DIST_KM']:.2f} km")

                    # ▶ 상세 보기 버튼 및 클릭 로그 저장
                    if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
                        st.session_state.selected_place = row
                        st.session_state.page = "detail"
                        st.rerun()

                # 🗺 지도 표시
                st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))
