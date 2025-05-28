import pandas as pd
import requests
import time

# ✅ 올바른 경로
file_path = r"C:\Users\soyoe\OneDrive\바탕 화면\홍익대학교\4학년\1학기\시스템분석\Project Data\tag_coordi_.csv"

# CSV 불러오기
df = pd.read_csv(file_path)

# 필요한 열만 추출
locations = df[['NAME', 'LAT', 'LON']].copy()
locations['weather'] = ""
locations['temperature'] = ""
locations['humidity'] = ""

# OpenWeatherMap API 설정
API_KEY = "db993432d1b5f597ea03fd182d005ce9"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# 날씨 정보 수집
for idx, row in locations.iterrows():
    lat, lon = row['LAT'], row['LON']
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric",
        "lang": "kr"
    }
    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        locations.at[idx, 'weather'] = data['weather'][0]['description']
        locations.at[idx, 'temperature'] = data['main']['temp']
        locations.at[idx, 'humidity'] = data['main']['humidity']
    except Exception as e:
        locations.at[idx, 'weather'] = f"오류: {e}"

    time.sleep(1)  # 무료 API 속도 제한 고려

# 결과 저장
output_path = r"C:\Users\soyoe\OneDrive\바탕 화면\홍익대학교\4학년\1학기\시스템분석\Project Data\장소별_날씨_결과.csv"
locations.to_csv(output_path, index=False, encoding='utf-8-sig')

print("완료: 장소별 날씨 정보가 '바탕 화면'에 저장되었습니다.")