import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import requests
import os


# ▶ 설정
API_KEY = "db993432d1b5f597ea03fd182d005ce9"

# ▶ 데이터 불러오기 (cp949 인코딩 사용)
current_dir = os.path.dirname(os.path.abspath(__file__))
PLACE_FILE = os.path.join(current_dir, "장소_카테고리_최종분류.csv")
MODEL_PATH = os.path.join(current_dir,"recovery_rf_model_v3.pkl")
ENCODER_PATH = os.path.join(current_dir,"recovery_rf_encoders_v3.pkl")
CLICK_FILE = r"C:\Users\soyoe\OneDrive\바탕 화면\홍익대학교\4학년\1학기\시스템분석\Project_code\click_log.csv"

try:
    df = pd.read_csv(PLACE_FILE, encoding="cp949")
    df = df.dropna(subset=["LAT", "LON", "CATEGORY"])
    df["LAT"] = df["LAT"].astype(float)
    df["LON"] = df["LON"].astype(float)
except Exception as e:
    st.error(f"❌ 장소 파일을 불러올 수 없습니다: {e}")
    st.stop()

# ▶ 모델 및 인코더 로드
model = joblib.load(MODEL_PATH)
encoders = joblib.load(ENCODER_PATH)

# ▶ 페이지 설정
st.set_page_config(page_title="회복 루틴 추천기", page_icon="🧘", layout="centered") 
st.title("🧘 회복이 필요한 날을 위한 맞춤 루틴 추천기") 
now = datetime.now() 
st.markdown(f"⏰ 현재 시간: {now.strftime('%Y-%m-%d %H:%M')}")

# ▶ 사용자 입력
age_group = st.selectbox("나이대는 어떻게 되시나요?", ["20대", "30대", "40대", "50대 이상"])
job_type = st.selectbox("어떤 직업이신가요?", ["학생", "회사원", "프리랜서"])

# ▶ 위치 가져오기
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

# ▶ 반경 슬라이더
radius = st.slider("추천 반경 (km)", 1.0, 5.0, 2.5, step=0.1)

# ▶ 날씨 API 매핑 함수
def map_weather(api_weather):
    if api_weather in ["Clear"]:
        return "맑음"
    elif api_weather in ["Clouds"]:
        return "흐림"
    elif api_weather in ["Rain", "Drizzle", "Thunderstorm"]:
        return "비"
    else:
        return "기타"

# ▶ 시간대 매핑 함수
def map_time(hour):
    if 6 <= hour < 12:
        return "오전"
    elif 12 <= hour < 18:
        return "오후"
    elif 18 <= hour < 22:
        return "저녁"
    else:
        return "심야"

# ▶ 날씨 API 요청
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
        return data["weather"][0]["main"]
    except:
        return "Unknown"

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

# ▶ 추천 버튼
if st.button("🔮 회복 장소 추천받기") and lat and lon:
    # 현재 시간, 날씨 매핑
    hour = now.hour
    time_slot = map_time(hour)
    raw_weather = get_weather(lat, lon)
    weather = map_weather(raw_weather)

    st.info(f"📡 현재 날씨: {raw_weather} → 매핑: {weather}, 시간대: {time_slot}")

    # ▶ 예측 입력값 구성 및 인코딩
    input_data = {
        "시간대": time_slot,
        "날씨": weather,
        "나이대": age_group,
        "직업": job_type
    }

    try:
        for key in input_data:
            encoder = encoders[key]
            input_data[key] = encoder.transform([input_data[key]])[0]

        X_pred = pd.DataFrame([input_data])
        predicted_tag = model.predict(X_pred)[0]
        tag_encoder = encoders["회복태그"]
        predicted_label = tag_encoder.inverse_transform([predicted_tag])[0]

        st.success(f"🎯 예측된 회복 태그: **{predicted_label}**")

        # ▶ 거리 필터 + 태그 필터
        df["DIST_KM"] = df.apply(compute_distance, axis=1)
        nearby_df = df[df["DIST_KM"] <= radius]
        tag_df = nearby_df[nearby_df["TAG"].str.contains(predicted_label, case=False, na=False)]

        if tag_df.empty:
            st.warning("😢 해당 태그에 맞는 장소가 없습니다.")
        else:
            for i, (_, row) in enumerate(tag_df.iterrows()):
                st.markdown(f"### 🏷️ {row['CATEGORY']}: **{row['NAME']}**")
                st.markdown(f"- 📍 위치: {row['LOCATION']}")
                st.markdown(f"- 🏷️ 태그: {row['TAG']}")
                st.markdown(f"- 📏 거리: 약 {row['DIST_KM']:.2f} km")

                # ▶ 상세 보기 버튼 및 클릭 로그 저장
                if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
                    st.success(f"✅ '{row['NAME']}' 선택됨!")
                    st.write(f"- 위치: {row['LOCATION']}")
                    st.write(f"- 카테고리: {row['CATEGORY']}")
                    st.write(f"- 거리: {row['DIST_KM']:.2f} km")

                    log = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "name": row['NAME'],
                        "category": row['CATEGORY'],
                        "location": row['LOCATION'],
                        "distance_km": round(row['DIST_KM'], 2)
                    }
                    pd.DataFrame([log]).to_csv("click_log.csv", mode="a", index=False, header=not os.path.exists("click_log.csv"))

                st.markdown("---")

            # 🗺 지도 표시
            st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))

# 첫 실행 대기
else:
    st.info("📌 아래 버튼을 눌러 추천 장소를 받아보세요.")
