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

# 페이지 상태 관리
if "page" not in st.session_state:
    st.session_state.page = "home"

# 위치 정보 가져오기
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

# 데이터 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
PLACE_FILE = os.path.join(current_dir, "장소_카테고리_최종분류.csv")
df = pd.read_csv(PLACE_FILE, encoding="cp949").dropna(subset=["LAT", "LON", "CATEGORY"])
df["LAT"], df["LON"] = df["LAT"].astype(float), df["LON"].astype(float)

# 상세 페이지 렌더링
if st.session_state.page == "detail":
    place = st.session_state.selected_place
    st.title(f"🔍 {place['NAME']} 상세 보기")
    st.write(f"- 위치: {place['LOCATION']}")
    st.write(f"- 카테고리: {place['CATEGORY']}")
    st.write(f"- 거리: {place['DIST_KM']:.2f} km")
    
    # 뒤로 가기 버튼 추가
    if st.button("⬅️ 뒤로 가기"):
        st.session_state.page = "home"
        st.rerun()

else:  # 홈 페이지
    st.title("🧘 회복 루틴 추천기")
    radius = st.slider("추천 반경 (km)", 1.0, 5.0, 2.5, step=0.1)

    df["DIST_KM"] = df.apply(lambda row: geodesic((lat, lon), (row["LAT"], row["LON"])).km if lat and lon else None, axis=1)
    nearby_df = df[df["DIST_KM"] <= radius]

    if st.button("카테고리별 랜덤 장소 추천받기") and lat and lon:
        sampled_df = nearby_df.groupby("CATEGORY", group_keys=False).apply(lambda x: x.sample(1))

        for _, row in sampled_df.iterrows():
            st.markdown(f"### 🏷️ {row['CATEGORY']}: **{row['NAME']}**")
            if st.button(f"🔍 {row['NAME']} 상세 보기", key=f"detail_{row['NAME']}"):
                st.session_state.selected_place = row
                st.session_state.page = "detail"
                st.rerun()
