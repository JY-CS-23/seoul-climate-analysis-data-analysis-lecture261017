import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CSV_PATH = "seoul_temperature.csv"
EXCLUDE_YEARS = [1907, 2026]          # 일수가 적은 연도
MISSING_YEARS = [1950, 1951, 1952, 1953]  # 결측이 있는 연도
MA_WINDOW = 5

st.set_page_config(page_title="서울 기온 분석", page_icon="🌡️", layout="wide")


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    # utf-8-sig: 컬럼명 앞의 BOM(﻿) 제거
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]

    # 날짜 값 앞뒤 탭/공백 제거 후 날짜형으로 변환
    df["날짜"] = pd.to_datetime(df["날짜"].astype(str).str.strip(), errors="coerce")
    df = df.dropna(subset=["날짜"])

    df["연도"] = df["날짜"].dt.year
    df = df[~df["연도"].isin(EXCLUDE_YEARS)].copy()
    return df


def build_yearly(df: pd.DataFrame) -> pd.DataFrame:
    """연도별 평균기온, 결측 연도 처리, 5년 이동평균 계산"""
    yearly = df.groupby("연도")["평균기온(℃)"].mean().rename("연평균").to_frame()
    all_years = range(int(yearly.index.min()), int(yearly.index.max()) + 1)
    yearly = yearly.reindex(all_years)
    yearly.index.name = "연도"

    # 결측 구간은 꺾은선에서 제외 (NaN), 원래 값은 x 표시용으로 따로 보관
    yearly["이상치"] = yearly["연평균"].where(yearly.index.isin(MISSING_YEARS))
    yearly["꺾은선"] = yearly["연평균"].where(~yearly.index.isin(MISSING_YEARS))

    # 연속된 연도 인덱스 위에서 이동평균 계산 → 결측 연도가 낀 창은 NaN이 되어
    # 결측 구간 앞뒤 연도를 섞어 평균내지 않고, 선도 끊긴 채로 표시됨
    yearly["이동평균"] = yearly["꺾은선"].rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    return yearly.reset_index()


# ---------------------------------------------------------------- 데이터 로드
try:
    df = load_data(CSV_PATH)
except FileNotFoundError:
    st.error(f"'{CSV_PATH}' 파일을 app.py와 같은 폴더에 넣어주세요.")
    st.stop()

yearly = build_yearly(df)
min_year, max_year = int(yearly["연도"].min()), int(yearly["연도"].max())

# ---------------------------------------------------------------- 사이드바
st.sidebar.header("설정")
year_range = st.sidebar.slider(
    "연도 범위",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)
include_missing = st.sidebar.checkbox(
    "결측 구간(1950~1953) 통계에 포함", value=False
)
st.sidebar.caption(
    "1907년, 2026년은 데이터 일수가 적어 제외했습니다."
)

start, end = year_range

# ---------------------------------------------------------------- 본문
st.title("🌡️ 서울 연도별 기온 변화")

view = yearly[(yearly["연도"] >= start) & (yearly["연도"] <= end)]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=view["연도"],
        y=view["꺾은선"],
        mode="lines+markers",
        name="연평균기온",
        line=dict(color="#4C78A8", width=1.5),
        marker=dict(size=4),
        connectgaps=False,
        hovertemplate="%{x}년: %{y:.2f}℃<extra>연평균</extra>",
    )
)
fig.add_trace(
    go.Scatter(
        x=view["연도"],
        y=view["이동평균"],
        mode="lines",
        name=f"{MA_WINDOW}년 이동평균",
        line=dict(color="#E45756", width=3),
        connectgaps=False,
        hovertemplate="%{x}년: %{y:.2f}℃<extra>5년 이동평균</extra>",
    )
)
outliers = view.dropna(subset=["이상치"])
if not outliers.empty:
    fig.add_trace(
        go.Scatter(
            x=outliers["연도"],
            y=outliers["이상치"],
            mode="markers",
            name="이상치(결측 구간)",
            marker=dict(symbol="x", size=11, color="black", line=dict(width=2)),
            hovertemplate="%{x}년: %{y:.2f}℃<extra>결측 구간</extra>",
        )
    )
fig.update_layout(
    xaxis_title="연도",
    yaxis_title="평균기온 (℃)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=520,
    margin=dict(l=20, r=20, t=40, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- 선택 구간 통계
sel = df[(df["연도"] >= start) & (df["연도"] <= end)]
if not include_missing:
    sel = sel[~sel["연도"].isin(MISSING_YEARS)]

st.subheader(f"{start}년 ~ {end}년 통계")

if sel.empty:
    st.warning("선택한 구간에 표시할 데이터가 없습니다.")
else:
    max_row = sel.loc[sel["최고기온(℃)"].idxmax()]
    min_row = sel.loc[sel["최저기온(℃)"].idxmin()]

    c1, c2, c3 = st.columns(3)
    c1.metric("평균기온", f"{sel['평균기온(℃)'].mean():.2f} ℃")
    c2.metric(
        "최고기온",
        f"{max_row['최고기온(℃)']:.1f} ℃",
        help=f"관측일: {max_row['날짜']:%Y-%m-%d}",
    )
    c3.metric(
        "최저기온",
        f"{min_row['최저기온(℃)']:.1f} ℃",
        help=f"관측일: {min_row['날짜']:%Y-%m-%d}",
    )
    st.caption(
        f"최고·최저기온 관측일 — 최고: {max_row['날짜']:%Y-%m-%d}, "
        f"최저: {min_row['날짜']:%Y-%m-%d}"
    )

with st.expander("연도별 데이터 보기"):
    st.dataframe(
        view[["연도", "연평균", "이동평균"]].round(2),
        use_container_width=True,
        hide_index=True,
    )
