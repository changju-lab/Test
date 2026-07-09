import json
import os
import ssl
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import certifi
import pytz
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL = "gpt-4o-mini"
DEFAULT_SYSTEM = (
    "You are a helpful assistant with access to tools. "
    "Use tools when needed for time, weather, or stock questions. "
    "Answer in Korean."
)

CITY_TZ = {
    "서울": "Asia/Seoul",
    "seoul": "Asia/Seoul",
    "뉴욕": "America/New_York",
    "new york": "America/New_York",
    "도쿄": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "런던": "Europe/London",
    "london": "Europe/London",
}

WEATHER_CODES = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분적으로 흐림",
    3: "흐림",
    45: "안개",
    48: "짙은 안개",
    51: "이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    80: "소나기",
    81: "소나기",
    82: "강한 소나기",
    95: "뇌우",
}


# --- Tool 함수 (3.4 Tool_Calling 실습) ---


def _fetch_json(url: str) -> dict:
    """Windows SSL 오류 우회를 위해 certifi 인증서 사용"""
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, timeout=10, context=context) as response:
        return json.loads(response.read().decode())


def get_city_time_basic() -> str:
    """도시 현재 시간을 반환(기본 버전: 시간대 미반영)"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_city_time_tz(city: str) -> str:
    """pytz로 도시별 시간대를 반영해 현재 시간 반환"""
    key = city.strip().lower()
    tz_name = CITY_TZ.get(key)
    if not tz_name:
        return json.dumps({"error": f"지원하지 않는 도시: {city}"}, ensure_ascii=False)

    now = datetime.now(pytz.timezone(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(
        {"city": city, "timezone": tz_name, "current_time": now},
        ensure_ascii=False,
    )


def get_us_stock_price(ticker: str) -> str:
    """yfinance로 미국 주식 가격 조회"""
    symbol = ticker.strip().upper()
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")
        if hist.empty:
            return json.dumps({"error": f"{symbol} 데이터가 없습니다."}, ensure_ascii=False)

        latest = hist.iloc[-1]
        prev_close = float(latest["Close"]) if "Close" in latest else None
        open_price = float(latest["Open"]) if "Open" in latest else None

        return json.dumps(
            {
                "ticker": symbol,
                "open": round(open_price, 2) if open_price is not None else None,
                "close": round(prev_close, 2) if prev_close is not None else None,
                "currency": "USD",
                "source": "yfinance",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def get_weather(city: str) -> str:
    """Open-Meteo API로 도시 현재 날씨 조회 (API 키 불필요)"""
    try:
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": city.strip(), "count": 1, "language": "ko", "format": "json"})
        )
        geo_data = _fetch_json(geo_url)

        results = geo_data.get("results")
        if not results:
            return json.dumps({"error": f"도시를 찾을 수 없습니다: {city}"}, ensure_ascii=False)

        place = results[0]
        lat = place["latitude"]
        lon = place["longitude"]
        place_name = place.get("name", city)
        country = place.get("country", "")

        weather_url = (
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "auto",
                }
            )
        )
        weather_data = _fetch_json(weather_url)

        current = weather_data["current"]
        code = int(current.get("weather_code", -1))

        return json.dumps(
            {
                "city": place_name,
                "country": country,
                "temperature_c": current.get("temperature_2m"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "condition": WEATHER_CODES.get(code, f"코드 {code}"),
                "observed_at": current.get("time"),
                "source": "open-meteo",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


TOOL_FUNCTIONS = {
    "get_city_time_basic": get_city_time_basic,
    "get_city_time_tz": get_city_time_tz,
    "get_us_stock_price": get_us_stock_price,
    "get_weather": get_weather,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_city_time_basic",
            "description": "현재 시간을 반환합니다. (로컬 PC 시간 기준)",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_city_time_tz",
            "description": "도시의 시간대를 반영해 현재 시간을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "도시 이름 (예: 서울, 뉴욕)"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_stock_price",
            "description": "미국 주식 티커를 입력받아 최근 주가 정보를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "주식 티커 (예: AAPL, TSLA)"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "도시 이름을 입력받아 현재 날씨(기온, 습도, 풍속, 날씨 상태)를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "도시 이름 (예: 서울, 부산, Tokyo)"}},
                "required": ["city"],
            },
        },
    },
]


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("`.env` 파일에 `OPENAI_API_KEY=sk-...` 를 설정하세요.")
        st.stop()
    return OpenAI(api_key=api_key)


def assistant_message_to_dict(message) -> dict:
    data = {"role": message.role}
    if message.content:
        data["content"] = message.content
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return data


def run_agent(client: OpenAI, messages: list[dict], temperature: float) -> tuple[str, list[str]]:
    """Tool Calling 루프 — tool 실행 로그와 최종 답변 반환"""
    tool_logs: list[str] = []

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=temperature,
            messages=messages,
            tools=TOOLS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or "", tool_logs

        messages.append(assistant_message_to_dict(message))

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments or "{}")
            result = TOOL_FUNCTIONS[fn_name](**fn_args)
            tool_logs.append(f"{fn_name}({fn_args}) → {result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": DEFAULT_SYSTEM}]


def main() -> None:
    st.set_page_config(page_title="Tool Calling 챗봇", page_icon="🛠️")
    st.title("🛠️ Tool Calling 챗봇")
    st.caption("3.4 Tool Calling 실습 — 시간 · 날씨 · 주식 조회")

    init_session_state()
    client = get_client()

    with st.sidebar:
        st.header("설정")
        temperature = st.slider("temperature", 0.0, 1.0, 0.1, 0.1)
        system_prompt = st.text_area("system 메시지", DEFAULT_SYSTEM, height=120)

        st.subheader("사용 가능한 Tool")
        st.markdown(
            "- `get_city_time_basic` — 로컬 현재 시각\n"
            "- `get_city_time_tz` — 도시별 시각 (서울·뉴욕·도쿄·런던)\n"
            "- `get_us_stock_price` — 미국 주식 (AAPL, TSLA 등)\n"
            "- `get_weather` — 도시 현재 날씨"
        )

        if st.button("대화 초기화"):
            st.session_state.messages = [{"role": "system", "content": system_prompt}]
            st.rerun()

    st.session_state.messages[0] = {"role": "system", "content": system_prompt}

    for message in st.session_state.messages:
        if message["role"] in ("system", "tool"):
            continue
        if message["role"] == "assistant" and not message.get("content"):
            continue
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("메시지를 입력하세요 (예: 서울 날씨 알려줘)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("도구 확인 중..."):
                answer, tool_logs = run_agent(client, st.session_state.messages, temperature)

            if tool_logs:
                with st.expander("🔧 Tool 호출 내역"):
                    for log in tool_logs:
                        st.code(log)

            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
