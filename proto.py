import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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

# ▶ TF-IDF 기반 코사인 유사도 계산
df["feature_text"] = df["CATEGORY"] + " " + df["TAG"]
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(df["feature_text"])

# ▶ 상위 카테고리와 유사한 카테고리 찾기
def get_similar_categories(category):
    cat_index = df[df["CATEGORY"] == category].index[0]
    cat_vector = tfidf_matrix[cat_index]
    similarity_scores = cosine_similarity(cat_vector, tfidf_matrix).flatten()
    
    # 유사도가 높은 카테고리 찾기
    similar_cats = df.iloc[similarity_scores.argsort()[-4:-1][::-1]]["CATEGORY"].unique().tolist()
    return similar_cats
    
# 📊 클릭 로그 기반 상위 카테고리 분석
if os.path.exists(CLICK_FILE):
    log_df = pd.read_csv(CLICK_FILE)
    top_cats_series = log_df['category'].value_counts().head(3)
    top_cats = top_cats_series.index.tolist()

    # 📌 코사인 유사도를 이용한 추천 카테고리 추가
    similar_top_cats = []
    for cat in top_cats:
        similar_top_cats.extend(get_similar_categories(cat))

    # 중복 제거
    similar_top_cats = list(set(similar_top_cats))
else:
    top_cats_series = pd.Series()
    top_cats = []
    similar_top_cats = []
if not top_cats_series.empty:
    st.markdown("### ⭐ 최다 선택 및 유사 카테고리")
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
                if similar_top_cats:
                    more_places = filtered_df[(filtered_df["CATEGORY"].isin(similar_top_cats)) & (~filtered_df["NAME"].isin(sampled_df["NAME"]))]
                    more_places = more_places.sort_values("DIST_KM").head(3)
                
                if more_places.empty:
                    st.info("📭 관련 장소가 없습니다.")
                else:
                    st.markdown(f"#### 🏷️ '{row['CATEGORY']}' 및 유사 카테고리 관련 추천 장소")
                    cols = st.columns(len(more_places))
                    for index, (idx, row_data) in enumerate(more_places.iterrows()):
                        with cols[index]:
                            st.markdown(f"#### 🏷️ {row_data['NAME']}")
                            st.markdown(f"📍 **위치:** {row_data['LOCATION']}")
                            st.markdown(f"🏷️ **태그:** {row_data.get('TAG', '없음')}")
                            # 🔍 상세 보기 버튼 (중복 방지 key 추가)
                            if st.button(f"🔍 {r} 상세 보기", key=f"detail_{index}"):  
                                st.session_state["selected_place"] = r
                            
                            try:
                                st.markdown(f"📏 **거리:** {float(row_data['DIST_KM']):.2f} km")
                            except (ValueError, TypeError):
                                st.markdown("📏 **거리:** 알 수 없음")


        # 구분선 추가
        st.markdown("---")


# 📜 클릭 로그 테이블
if os.path.exists(CLICK_FILE):
    st.markdown("## 🗂️ 내가 클릭한 장소 기록")
    log_df = pd.read_csv(CLICK_FILE)
    st.dataframe(log_df.tail(10))

    # 협업 추천
    if not log_df.empty and "name" in log_df.columns:
        try:
            user_place = pd.pivot_table(log_df, index="name", columns="category", aggfunc="size", fill_value=0)
            if user_place.shape[0] > 1:
                sim_scores = cosine_similarity(user_place, user_place)
                sim_df = pd.DataFrame(sim_scores, index=user_place.index, columns=user_place.index)  
                recent = log_df["name"].iloc[-1]
                
                if recent in sim_df.index:
                    recs = sim_df[recent].sort_values(ascending=False).drop(recent).head(3).index.tolist()
                    st.markdown("## 👥 당신과 비슷한 사람들이 자주 선택한 장소")
                    
                    cols = st.columns(len(recs))
                    
                    for index,r in enumerate(recs):
                        info = df[df["NAME"] == r]
                        if not info.empty:
                            info = info.iloc[0]
                            with cols[index]:
                                st.markdown(f"#### ⭐ {r}")
                                st.markdown(f"- 카테고리: {info['CATEGORY']}")
                                st.markdown(f"- 위치: {info['LOCATION']}")
                            
                                try:
                                    dist = compute_distance(info)
                                    st.markdown(f"- 거리: {dist:.2f} km")
                                except:
                                    st.markdown("- 거리: 알 수 없음")
                                st.markdown("---")
        except Exception as e:
            st.error(f"❌ 클릭 기록 테이블 불러오기 오류: {e}")
