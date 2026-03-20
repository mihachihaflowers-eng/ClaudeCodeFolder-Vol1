#!/usr/bin/env python3
"""今日の天気を表示するCLIアプリ（Open-Meteo API使用・APIキー不要）"""

import json
import sys
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

# WMOコード -> (アイコン, 説明)
WMO = {
    0:  ("☀️ ", "快晴"),
    1:  ("🌤️ ", "ほぼ晴れ"),
    2:  ("⛅ ", "一部曇り"),
    3:  ("☁️ ", "曇り"),
    45: ("🌫️ ", "霧"),
    48: ("🌫️ ", "霧氷"),
    51: ("🌦️ ", "霧雨（弱）"),
    53: ("🌦️ ", "霧雨"),
    55: ("🌧️ ", "霧雨（強）"),
    61: ("🌧️ ", "小雨"),
    63: ("🌧️ ", "雨"),
    65: ("🌧️ ", "大雨"),
    71: ("🌨️ ", "小雪"),
    73: ("❄️ ", "雪"),
    75: ("❄️ ", "大雪"),
    80: ("🌦️ ", "にわか雨（弱）"),
    81: ("🌧️ ", "にわか雨"),
    82: ("⛈️ ", "にわか大雨"),
    95: ("⛈️ ", "雷雨"),
    99: ("⛈️ ", "雹を伴う雷雨"),
}

WEEKDAYS = "月火水木金土日"


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=10) as res:
        return json.loads(res.read())


def get_location() -> tuple[float, float, str]:
    """IPジオロケーションで現在地を取得"""
    data = fetch_json("https://ipapi.co/json/")
    lat = data["latitude"]
    lon = data["longitude"]
    city = data.get("city", "不明")
    region = data.get("region", "")
    return lat, lon, f"{region} {city}".strip()


def get_weather(lat: float, lon: float) -> dict:
    """Open-Meteo APIで天気を取得"""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,weathercode,"
        f"windspeed_10m,relativehumidity_2m,precipitation"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=auto&forecast_days=1"
    )
    return fetch_json(url)


def weather_info(code: int) -> tuple[str, str]:
    return WMO.get(code, ("🌡️ ", "不明"))


def print_weather(city: str, data: dict) -> None:
    c = data["current"]
    d = data["daily"]
    now = datetime.now()
    weekday = WEEKDAYS[now.weekday()]
    code = c["weathercode"]
    icon, desc = weather_info(code)

    temp      = c["temperature_2m"]
    feels     = c["apparent_temperature"]
    humidity  = c["relativehumidity_2m"]
    wind      = c["windspeed_10m"]
    precip    = c.get("precipitation", 0)
    temp_max  = d["temperature_2m_max"][0]
    temp_min  = d["temperature_2m_min"][0]
    precip_sum = d["precipitation_sum"][0]

    width = 40
    line  = "─" * width

    print(f"\n┌{line}┐")
    print(f"│{'今日の天気':^{width-2}}│")
    print(f"├{line}┤")
    print(f"│  📍 {city:<{width-5}}│")
    print(f"│  📅 {now.year}年{now.month}月{now.day}日（{weekday}）{'':<{width-22}}│")
    print(f"├{line}┤")
    print(f"│  {icon}{desc:<{width-4}}│")
    print(f"│  🌡️  現在  {temp:>5.1f}°C  （体感 {feels:.1f}°C）{'':<3}│")
    print(f"│  🔺 最高  {temp_max:>5.1f}°C   🔻 最低  {temp_min:.1f}°C{'':<3}│")
    print(f"├{line}┤")
    print(f"│  💧 湿度      {humidity:>3}%{'':<{width-15}}│")
    print(f"│  💨 風速   {wind:>5.1f} km/h{'':<{width-17}}│")
    print(f"│  ☔ 降水量  {precip_sum:>5.1f} mm（現在 {precip:.1f} mm）{'':<2}│")
    print(f"└{line}┘\n")


def main() -> None:
    print("📡 位置情報を取得中...")
    try:
        lat, lon, city = get_location()
    except (URLError, KeyError) as e:
        print(f"❌ 位置情報の取得に失敗しました: {e}")
        sys.exit(1)

    print(f"🌤️  天気データを取得中... ({city})")
    try:
        data = get_weather(lat, lon)
    except (URLError, KeyError) as e:
        print(f"❌ 天気データの取得に失敗しました: {e}")
        sys.exit(1)

    print_weather(city, data)


if __name__ == "__main__":
    main()
