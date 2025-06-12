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

# TF-IDF 유사도 계산
df["feature_text"] = df["CATEGORY"] + " " + df["TAG"]
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(df["feature_text"])

def get_similar_categories(category):
    cat_index = df[df["CATEGORY"] == category].index[0]
    cat_vector = tfidf_matrix[cat_index]
    similarity_scores = cosine_similarity(cat_vector, tfidf_matrix).flatten()
    similar_cats = df.iloc[similarity_scores.argsort()[-4:-1][::-1]]["CATEGORY"].unique().tolist()
    return similar_cats

try:
    log_df = pd.read_csv(CLICK_FILE, encoding="cp949", on_bad_lines='skip')
    top_cats_series = log_df['category'].value_counts().head(3)
    top_cats = top_cats_series.index.tolist()
    similar_top_cats = []
    for cat in top_cats:
        similar_top_cats.extend(get_similar_categories(cat))
    similar_top_cats = list(set(similar_top_cats))
except Exception as e:
    st.error(f"❌ 클릭 로그 분석 중 오류: {e}")
    top_cats_series = pd.Series()
    top_cats = []
    similar_top_cats = []

if not top_cats_series.empty:
    st.markdown("### ⭐ 자주 선택된 카테고리 및 유사 카테고리")
    for cat, count in top_cats_series.items():
        st.markdown(f"- {cat} (선택 {count}회)")

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

sampled_df = st.session_state.get("recommendation")
filtered_df = st.session_state.get("filtered")
click_count = st.session_state.get("click_count", 0)

if isinstance(sampled_df, pd.DataFrame) and not sampled_df.empty:
    weather = get_weather(lat, lon)
    st.markdown("### 🌤️ 현재 위치의 날씨")
    st.write(f"- 날씨 상태: {weather['weather']}")
    st.write(f"- 기온: {weather['temp']}°C")
    st.write(f"- 습도: {weather['humidity']}%")
    st.map(sampled_df.rename(columns={"LAT": "lat", "LON": "lon"}))

    for _, row in sampled_df.iterrows():
        with st.container():
            st.markdown(f"#### 🏷️ **{row['NAME']}**")
            st.markdown(f"**카테고리:** {row['CATEGORY']}")
            st.markdown(f"📍 위치: {row['LOCATION']}")
            st.markdown(f"🏷️ 태그: {row.get('TAG', '없음')}")
            st.markdown(f"🧭 거리: {row['DIST_KM']:.2f} km")

            col1, col2 = st.columns([1, 2])

            with col1:
                if st.button(f"🔍 상세 보기", key=f"detail_{row['NAME']}"):
                    # 중복 클릭 방지: 당일 이미 클릭한 경우 무시
                    today = datetime.now().strftime("%Y-%m-%d")
                    if os.path.exists(CLICK_FILE):
                        clicks_today = pd.read_csv(CLICK_FILE, encoding="utf-8-sig", on_bad_lines='skip')
                        already_clicked = not clicks_today[
                            (clicks_today["name"] == row["NAME"]) &
                            (clicks_today["timestamp"].str.startswith(today))
                        ].empty
                    else:
                        already_clicked = False

                    if already_clicked:
                        st.info(f"⚠️ 오늘 이미 '{row['NAME']}'을(를) 클릭하셨습니다.")
                    else:
                        new_log = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user_id": "user1",
                            "name": row["NAME"],
                            "category": row["CATEGORY"]
                        }
                        pd.DataFrame([new_log]).to_csv(
                            CLICK_FILE, mode="a", index=False,
                            header=not os.path.exists(CLICK_FILE),
                            encoding="utf-8-sig"
                        )
                        st.success(f"✅ '{row['NAME']}' 클릭 기록이 저장되었습니다.")

            with col2:
                if click_count >= 2 and row["CATEGORY"] in top_cats:
                    if st.button(f"[🔎 {row['CATEGORY']}] 관련 장소 더보기", key=f"more_{row['CATEGORY']}"):
                        related_df = filtered_df[
                            (filtered_df["CATEGORY"] == row["CATEGORY"]) & 
                            (filtered_df["NAME"] != row["NAME"])
                        ]
                        st.markdown(f"##### 📌 반경 {radius}km 이내의 '{row['CATEGORY']}' 카테고리 장소:")
                        if not related_df.empty:
                            for _, r in related_df.iterrows():
                                st.markdown(f"- **{r['NAME']}** ({r['LOCATION']}, {r['TAG']})")
                        else:
                            st.info("🚫 추가로 표시할 장소가 없습니다.")
        st.markdown("---")
else:
    st.info("⏳ 먼저 '카테고리별 랜덤 장소 추천받기' 버튼을 눌러주세요.")

# 협업 추천
if os.path.exists(CLICK_FILE):
    try:
        log_df = pd.read_csv(CLICK_FILE, encoding="utf-8-sig", on_bad_lines='skip')
        st.markdown("## 🗂️ 내가 클릭한 장소 기록")
        st.dataframe(log_df.tail(10))

        if not log_df.empty and "name" in log_df.columns:
            user_place = pd.pivot_table(log_df, index="user_id", columns="name", aggfunc="size", fill_value=0)
            if user_place.shape[0] > 1:
                sim_scores = cosine_similarity(user_place, user_place)
                sim_df = pd.DataFrame(sim_scores, index=user_place.index, columns=user_place.index)
                recent_user = log_df["user_id"].iloc[-1]
                if recent_user in sim_df.index:
                    recs = sim_df.loc[recent_user].sort_values(ascending=False).drop(recent_user).head(3).index.tolist()
                    recommended_names = log_df[log_df["user_id"].isin(recs)]["name"].value_counts().head(3).index.tolist()
                    st.markdown("## 👥 당신과 비슷한 사람들이 자주 선택한 장소")
                    for r in recommended_names:
                        info = df[df["NAME"] == r]
                        if not info.empty:
                            info = info.iloc[0]
                            st.markdown(f"### ⭐ {r}")
                            st.markdown(f"- 카테고리: {info['CATEGORY']}")
                            st.markdown(f"- 위치: {info['LOCATION']}")
                            st.markdown(f"- 거리: {compute_distance(info):.2f} km")
                            st.markdown("---")
    except Exception as e:
        st.error(f"❌ 클릭 기록 테이블 불러오기 오류: {e}")
