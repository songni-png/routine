import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import joblib
import requests
import os

# ▶ OpenWeatherMap API 키
API_KEY = "db993432d1b5f597ea03fd182d005ce9"

# ▶ 페이지 설정
st.set_page_config(page_title="회복 루틴 추천기", page_icon="🧘", layout="centered")
st.title("🧘 회복이 필요한 날을 위한 맞춤 루틴 추천기")
st.markdown(f"⏰ 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ▶ 사용자 위치 요청
loc = streamlit_js_eval(
    js_expressions="""
    new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
            (err) => reject(err)
        );
    })
    """,
    key="get_location"
)

if loc and isinstance(loc, dict) and "latitude" in loc:
    lat, lon = loc["latitude"], loc["longitude"]
    st.success(f"📍 현재 위치: 위도 {lat:.5f}, 경도 {lon:.5f}")
else:
    st.warning("📡 위치 권한이 허용되지 않았습니다.")
    lat, lon = None, None

# ▶ 반경 설정
radius = st.slider("추천 반경 (km)", 1.0, 5.0, 2.5, step=0.1)

# ▶ 데이터 파일 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
PLACE_FILE = os.path.join(current_dir, "장소_카테고리_최종분류.csv")
CLICK_FILE = os.path.join(current_dir, "click_log.csv")
MODEL_PATH = os.path.join(current_dir, "recovery_rf_model_v3.pkl")
ENCODER_PATH = os.path.join(current_dir, "recovery_rf_encoders_v3.pkl")

# ▶ 모델 및 인코더 로드
model = joblib.load(MODEL_PATH)
encoders = joblib.load(ENCODER_PATH)

# ▶ 장소 데이터 로딩
try:
    df = pd.read_csv(PLACE_FILE, encoding="cp949")
    df = df.dropna(subset=["LAT", "LON", "CATEGORY"])
    df["LAT"] = df["LAT"].astype(float)
    df["LON"] = df["LON"].astype(float)
    df["TAG"] = df["TAG"].fillna("")
except Exception as e:
    st.error(f"❌ 장소 파일을 불러올 수 없습니다: {e}")
    st.stop()

# ▶ 거리 계산 함수
def compute_distance(row):
    return geodesic((lat, lon), (row["LAT"], row["LON"])).km if lat and lon else None

# ▶ 날씨 가져오기
@st.cache_data
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
    nearby_df = df[df["DIST_KM"] <= radius]

    filtered_df = nearby_df.copy()

    if filtered_df.empty:
        st.warning("❌ 조건에 맞는 장소가 없습니다.")
    else:
        sampled_df = filtered_df.groupby("CATEGORY", group_keys=False).apply(lambda x: x.sample(1)).reset_index(drop=True)
        st.session_state["recommendation"] = sampled_df
        st.session_state["selected_place"] = None

# ▶ 추천 결과 유지
sampled_df = st.session_state.get("recommendation")
selected_place = st.session_state.get("selected_place")

if sampled_df is not None:
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
        st.markdown(f"- 🏷️ 태그: {row.get('TAG', '없음')}")
        st.markdown(f"- 📏 거리: 약 {row['DIST_KM']:.2f} km")

        if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
            st.session_state["selected_place"] = row['NAME']
            selected_place = row['NAME']

        if selected_place == row['NAME']:
            st.success(f"✅ '{row['NAME']}' 상세 내용")
            st.write(f"- 위치: {row['LOCATION']}")
            st.write(f"- 카테고리: {row['CATEGORY']}")
            st.write(f"- 거리: {row['DIST_KM']:.2f} km")

            # ▶ 같은 카테고리의 가까운 장소 3개 찾기
            similar_places = df[df["CATEGORY"] == row["CATEGORY"]].sort_values(by="DIST_KM").head(3)
            st.markdown("### 🏷️ 같은 카테고리의 가까운 장소 추천")
            for _, s_row in similar_places.iterrows():
                st.write(f"- **{s_row['NAME']}** ({s_row['DIST_KM']:.2f} km) - {s_row['LOCATION']}")

            log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": row['NAME'],
                "category": row['CATEGORY'],
                "location": row['LOCATION'],
                "distance_km": round(row['DIST_KM'], 2)
            }
            pd.DataFrame([log]).to_csv(CLICK_FILE, mode="a", index=False, header=not os.path.exists(CLICK_FILE))

        st.markdown("---")

    st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))


# ▶ 클릭 로그 확인
st.markdown("## 🗂️ 내가 클릭한 장소 기록")
if os.path.exists(CLICK_FILE):
    log_df = pd.read_csv(CLICK_FILE)
    st.dataframe(log_df.tail(10))
    csv = log_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 클릭 로그 CSV 다운로드", data=csv, file_name="click_log.csv", mime="text/csv")
else:
    st.info("아직 클릭한 장소가 없어요. 위에서 장소를 선택해보세요!")
