import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

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
# 슬라이더와 숫자 입력칸을 session_state로 서로 동기화
if "year_range" not in st.session_state:
    st.session_state["year_range"] = (min_year, max_year)
    st.session_state["start_year"] = min_year
    st.session_state["end_year"] = max_year


def _sync_from_slider():
    s, e = st.session_state["year_range"]
    st.session_state["start_year"] = s
    st.session_state["end_year"] = e


def _sync_from_inputs():
    s = st.session_state["start_year"]
    e = st.session_state["end_year"]
    if s > e:  # 시작 > 끝이면 서로 맞바꿈
        s, e = e, s
    st.session_state["start_year"] = s
    st.session_state["end_year"] = e
    st.session_state["year_range"] = (s, e)


def _reset_range():
    """Esc: 가장 큰 범위로 되돌리고 그래프 클릭 선택도 초기화"""
    st.session_state["year_range"] = (min_year, max_year)
    st.session_state["start_year"] = min_year
    st.session_state["end_year"] = max_year
    st.session_state["first_click"] = None
    st.session_state["chart_ver"] += 1


def _shift_start(delta):
    """Shift+←/→: 시작 연도 ∓1 (최솟값~끝 연도 사이로 제한)"""
    e = st.session_state["end_year"]
    s = max(min_year, min(st.session_state["start_year"] + delta, e))
    st.session_state["start_year"] = s
    st.session_state["year_range"] = (s, e)


def _shift_end(delta):
    """Ctrl+←/→: 끝 연도 ∓1 (시작 연도~최댓값 사이로 제한)"""
    s = st.session_state["start_year"]
    e = min(max_year, max(st.session_state["end_year"] + delta, s))
    st.session_state["end_year"] = e
    st.session_state["year_range"] = (s, e)


st.session_state.setdefault("first_click", None)  # 그래프에서 첫 번째로 클릭한 연도
st.session_state.setdefault("chart_ver", 0)  # 그래프 선택 상태를 초기화하기 위한 key 번호

# 그래프 클릭으로 정해진 구간을 위젯이 만들어지기 전에 반영
if "pending_range" in st.session_state:
    _s, _e = st.session_state.pop("pending_range")
    st.session_state["year_range"] = (_s, _e)
    st.session_state["start_year"] = _s
    st.session_state["end_year"] = _e

st.sidebar.header("설정")
st.sidebar.slider(
    "연도 범위",
    min_value=min_year,
    max_value=max_year,
    key="year_range",
    on_change=_sync_from_slider,
)
col_start, col_end = st.sidebar.columns(2)
col_start.number_input(
    "시작 연도",
    min_value=min_year,
    max_value=max_year,
    step=1,
    key="start_year",
    on_change=_sync_from_inputs,
)
col_end.number_input(
    "끝 연도",
    min_value=min_year,
    max_value=max_year,
    step=1,
    key="end_year",
    on_change=_sync_from_inputs,
)

# 단축키와 연결된 버튼 (버튼을 직접 눌러도 같은 동작)
st.sidebar.button(
    "전체 범위로 (Esc)", on_click=_reset_range, use_container_width=True
)
st.sidebar.button(
    "시작 연도 -1 (Shift+←)",
    on_click=_shift_start,
    args=(-1,),
    use_container_width=True,
)
st.sidebar.button(
    "시작 연도 +1 (Shift+→)",
    on_click=_shift_start,
    args=(1,),
    use_container_width=True,
)
st.sidebar.button(
    "끝 연도 -1 (Ctrl+←)",
    on_click=_shift_end,
    args=(-1,),
    use_container_width=True,
)
st.sidebar.button(
    "끝 연도 +1 (Ctrl+→)",
    on_click=_shift_end,
    args=(1,),
    use_container_width=True,
)

year_range = st.session_state["year_range"]
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
# 클릭 감지용 투명 트레이스: 모든 연도에 점을 하나씩 두어서,
# 결측 구간을 포함해 그래프 어디서든 마우스를 따라다니는 세로선 위를 클릭하면 그 연도가 잡히게 함
_ymid = view["연평균"].mean()
fig.add_trace(
    go.Scatter(
        x=view["연도"],
        y=[0 if pd.isna(_ymid) else _ymid] * len(view),
        mode="markers",
        marker=dict(size=1, opacity=0),
        hoverinfo="none",
        showlegend=False,
    )
)
fig.update_layout(
    xaxis_title="연도",
    yaxis_title="평균기온 (℃)",
    clickmode="event+select",
    hoverdistance=-1,  # 마우스에서 가장 가까운 연도를 항상 잡음
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=520,
    margin=dict(l=20, r=20, t=40, b=20),
)

# 클릭한 첫 번째 연도를 주황색 실선으로 표시 (마우스 오버 시 나타나는 점선과 구분)
first = st.session_state["first_click"]
if first is not None and start <= first <= end:
    fig.add_vline(
        x=first,
        line_dash="solid",
        line_color="#F58518",
        line_width=2,
        annotation_text=f"{first}년",
        annotation_position="top",
    )

event = st.plotly_chart(
    fig,
    use_container_width=True,
    on_select="rerun",
    selection_mode="points",
    key=f"temp_chart_{st.session_state['chart_ver']}",
)

if first is None:
    st.caption(
        "💡 그래프 위에 마우스를 올리면 해당 연도에 세로 점선이 생깁니다. "
        "그 점선 위를 클릭해 연도를 고르고, 두 번째 연도도 같은 방법으로 클릭하면 "
        "시작·끝 연도가 자동으로 지정됩니다."
    )
else:
    st.caption(
        f"💡 {first}년(주황색 선)을 선택했습니다. "
        "다른 연도의 점선 위를 클릭하면 구간이 지정됩니다."
    )
    if st.button("첫 번째 선택 취소"):
        st.session_state["first_click"] = None
        st.session_state["chart_ver"] += 1
        st.rerun()

# 그래프 클릭 처리: 첫 클릭은 기준 연도로 저장, 두 번째 클릭에서 구간 확정
points = event["selection"]["points"] if event else []
clicked = sorted({int(round(p["x"])) for p in points if p.get("x") is not None})
if clicked:
    new_range = None
    if len(clicked) >= 2:  # Shift+클릭 등으로 한 번에 두 점이 선택된 경우
        new_range = (clicked[0], clicked[-1])
    elif first is None:
        st.session_state["first_click"] = clicked[0]
    else:
        new_range = (min(first, clicked[0]), max(first, clicked[0]))

    if new_range:
        st.session_state["first_click"] = None
        st.session_state["pending_range"] = new_range
    st.session_state["chart_ver"] += 1  # 그래프를 새로 만들어 선택 표시를 지움
    st.rerun()

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

# ---------------------------------------------------------------- 키보드 단축키
# Esc: 전체 범위 / Shift+←,→: 시작 연도 -1,+1 / Ctrl+←,→: 끝 연도 -1,+1
# 사이드바의 해당 버튼을 대신 눌러주는 방식으로 동작
components.html(
    """
    <script>
    const win = window.parent;
    const doc = win.document;
    if (win.__tempKeyHandler) {
        doc.removeEventListener("keydown", win.__tempKeyHandler);
    }
    function clickButton(marker) {
        for (const b of doc.querySelectorAll("button")) {
            if (b.innerText && b.innerText.includes(marker)) {
                b.click();
                return;
            }
        }
    }
    win.__tempKeyHandler = function (e) {
        if (e.repeat) return;
        if (e.key === "Escape") {
            clickButton("(Esc)");
        } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
            const arrow = e.key === "ArrowLeft" ? "←" : "→";
            if (e.shiftKey && !e.ctrlKey) {
                e.preventDefault();
                clickButton("(Shift+" + arrow + ")");
            } else if (e.ctrlKey && !e.shiftKey) {
                e.preventDefault();
                clickButton("(Ctrl+" + arrow + ")");
            }
        }
    };
    doc.addEventListener("keydown", win.__tempKeyHandler);
    </script>
    """,
    height=0,
)
