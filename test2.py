import streamlit as st
import pandas as pd


# =====================================================================
# [담당자 1 - Module A] 데이터 파싱 및 정제 함수
# =====================================================================

# 요일을 숫자의 '십의 자리'로 바꾸기 위한 전역 사전(딕셔너리)
DAY_MAP = {"월": 10, "화": 20, "수": 30, "목": 40, "금": 50}
REVERSE_DAY_MAP = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금"}


def code_to_korean(code):
    """
    숫자 코드(예: 11)를 사람이 읽기 쉬운 한글(예: '월1교시')로 바꾸는 함수입니다.
    """
    day_prefix = code // 10  # 10으로 나눈 몫 -> 요일 번호 (1~5)
    period = code % 10       # 10으로 나눈 나머지 -> 교시 번호 (1~9)
    day_char = REVERSE_DAY_MAP.get(day_prefix, "?")
    return f"{day_char}{period}교시"


def process_data(df):
    """
    모든 수업이 '주 1회(3시간 연강 또는 1시간)'라는 규칙을 활용해
    시작 교시와 학점(수업 시간)만으로 아주 간단하게 숫자 리스트를 만듭니다.
    - 3시간(3학점) 수업 예: '월1~3' -> 시작코드 11부터 3개 연속 + 교수번호 -> [11, 12, 13, 101]
    - 1시간(1학점) 수업 예: '금5'   -> 시작코드 55부터 1개 + 교수번호      -> [55, 130]
    """
    processed_df = df.copy()

    # 1단계: 등장하는 교수님들에게 101번부터 순서대로 고유 번호 부여하기
    prof_map = {}
    unique_profs = processed_df["교수명"].dropna().unique()
    prof_number = 101
    for prof in unique_profs:
        prof_map[str(prof).strip()] = prof_number
        prof_number += 1

    # 2단계: 시작 교시와 학점(1 또는 3)을 이용해 한 줄로 수치화 리스트 만들기
    all_numeric_lists = []

    for _, row in processed_df.iterrows():
        time_str = str(row["시간표"]).strip()   # 예: "월1~3" 또는 "금5"
        credit = int(row["학점"])               # 학점 = 수업 시간 (3시간 또는 1시간)
        prof_name = str(row["교수명"]).strip()

        day_char = time_str[0]                  # 첫 번째 글자: 요일 (예: '월')
        start_period = int(time_str[1])         # 두 번째 글자: 시작 교시 (예: 1)

        # 시작 교시 코드 계산 (예: 월1 -> 10 + 1 = 11)
        start_code = DAY_MAP[day_char] + start_period
        prof_code = prof_map.get(prof_name, 999)

        # 시작 코드부터 학점(3시간 또는 1시간)만큼 연속된 숫자를 만들고 마지막에 교수 번호 추가!
        numeric_codes = list(range(start_code, start_code + credit)) + [prof_code]
        all_numeric_lists.append(numeric_codes)

    # 완성된 숫자 리스트를 데이터프레임의 새 열로 저장
    processed_df["수치화_시간표"] = all_numeric_lists

    # 3단계: 같은 과목명·같은 시간대라도 교수님으로 구분할 수 있도록 선택용 이름 만들기
    processed_df["강좌선택명"] = (
        processed_df["과목명"]
        + " ("
        + processed_df["교수명"]
        + " | "
        + processed_df["시간표"]
        + ")"
    )

    return processed_df


# =====================================================================
# [담당자 2 - Module B] 시간표 충돌 검사 함수
# =====================================================================

def check_conflicts(selected_df):
    """
    선택한 과목들 사이에 겹치는 수업 시간이 있는지 검사하는 함수입니다.
    초보자도 이해하기 쉽게 단순 리스트와 2중 for문으로 비교합니다.
    """
    has_conflict = False
    messages = []

    courses = selected_df.to_dict("records")
    num_courses = len(courses)

    # 과목 A와 과목 B를 1:1로 짝지어 비교
    for i in range(num_courses):
        for j in range(i + 1, num_courses):
            course_a = courses[i]
            course_b = courses[j]

            # 실제 수업 시간인 100 미만의 두 자리 숫자(교시 코드)만 꺼내어 겹치는지 비교
            overlap_codes = []
            for code in course_a["수치화_시간표"]:
                if code < 100 and code in course_b["수치화_시간표"]:
                    overlap_codes.append(code)

            # 겹치는 시간 코드가 하나라도 있다면 충돌 발생!
            if len(overlap_codes) > 0:
                has_conflict = True
                overlap_codes.sort()

                korean_times = []
                for c in overlap_codes:
                    korean_times.append(code_to_korean(c))
                overlap_str = ", ".join(korean_times)

                name_a = f"{course_a['과목명']}({course_a['교수명']})"
                name_b = f"{course_b['과목명']}({course_b['교수명']})"
                msg = f"'{name_a}' 강의와 '{name_b}' 강의가 [{overlap_str}]에 중복됩니다!"
                messages.append(msg)

    return has_conflict, messages


# =====================================================================
# [담당자 3 - Module C] 공강 시간 분석 및 활동 추천 함수
# =====================================================================

def analyze_free_time(selected_df):
    """
    요일별로 수업 교시를 오름차순 정렬한 뒤,
    수업과 수업 사이에 비어있는 '공강 시간'을 계산하고 맞춤형 활동을 추천합니다.
    """
    day_names = {1: "월요일", 2: "화요일", 3: "수요일", 4: "목요일", 5: "금요일"}
    day_periods = {1: [], 2: [], 3: [], 4: [], 5: []}

    # 1단계: 선택한 과목들의 시간 코드를 요일별로 모으기
    for code_list in selected_df["수치화_시간표"]:
        for code in code_list:
            if code < 100:  # 마지막 숫자인 교수 번호(101~)는 제외
                day_num = code // 10
                period_num = code % 10
                if day_num in day_periods:
                    day_periods[day_num].append(period_num)

    max_gap = 0
    daily_free_list = []

    # 2단계: 요일별로 교시를 순서대로 정렬하고 수업 사이 빈 시간(차이) 계산하기
    for day_num, periods in day_periods.items():
        if len(periods) >= 2:
            sorted_periods = sorted(list(set(periods)))

            for i in range(len(sorted_periods) - 1):
                current_p = sorted_periods[i]
                next_p = sorted_periods[i + 1]

                # 인접한 두 교시 사이의 빈 시간 계산 (연강이면 차이가 1이라 gap = 0)
                gap = next_p - current_p - 1

                if gap > 0:
                    day_name = day_names[day_num]
                    free_start = current_p + 1
                    free_end = next_p - 1

                    if free_start == free_end:
                        gap_desc = f"{day_name} {free_start}교시 ({gap}시간 공강)"
                    else:
                        gap_desc = f"{day_name} {free_start}~{free_end}교시 ({gap}시간 연속 공강)"

                    daily_free_list.append(gap_desc)

                    if gap > max_gap:
                        max_gap = gap

    # 3단계: 최대 연속 공강 시간에 따른 추천 활동 결정
    if max_gap == 0:
        recommendation = "수업 사이 빈 공강 시간이 없습니다! 압축적인 시간표네요. 건강을 위해 간단한 간식을 챙겨 다니세요."
    elif max_gap == 1:
        recommendation = "최대 1시간 공강이 있습니다. 학생식당에서 여유롭게 식사하거나 카페에서 커피 한 잔 하며 다음 수업을 준비하기 좋습니다."
    elif max_gap == 2:
        recommendation = "최대 2시간 연속 공강이 있습니다. 중앙도서관 열람실에서 과제를 미리 해결하거나, 교내 헬스장/휴게실을 이용해 보세요."
    else:
        recommendation = f"최대 {max_gap}시간의 긴 연속 공강이 있습니다! 도서관 팀플/스터디 모임을 잡거나, 교내 근로장학 또는 어학 특강 수강을 강력히 추천합니다."

    return max_gap, daily_free_list, recommendation


# =====================================================================
# [담당자 4 - Module D] 시간표 표 만들기 & 메인 화면 구성 (위에서 아래로 순서대로 실행)
# =====================================================================

def create_timetable_grid(selected_df):
    """
    선택한 과목들을 요일(열)과 1~9교시(행) 기준의 시간표 표(DataFrame)로 만듭니다.
    """
    days = ["월", "화", "수", "목", "금"]
    periods = [f"{i}교시" for i in range(1, 10)]

    grid_df = pd.DataFrame("", index=periods, columns=days)
    num_to_day = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금"}

    for _, row in selected_df.iterrows():
        cell_text = f"{row['과목명']} ({row['교수명']})"

        for code in row["수치화_시간표"]:
            if code < 100:  # 시간 코드만 시간표에 표시
                day_num = code // 10
                period_num = code % 10

                if day_num in num_to_day and 1 <= period_num <= 9:
                    day_col = num_to_day[day_num]
                    period_row = f"{period_num}교시"

                    if grid_df.loc[period_row, day_col] != "":
                        grid_df.loc[period_row, day_col] += f" / [충돌!] {cell_text}"
                    else:
                        grid_df.loc[period_row, day_col] = cell_text

    return grid_df


# --- 여기부터 웹 페이지 화면이 위에서 아래로 순서대로 그려집니다 ---

st.set_page_config(page_title="수강 시간표 대시보드", layout="wide")

# 왼쪽 사이드바 칸을 넓히고 선택된 과목이 스크롤 없이 다 보이게 하는 스타일
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 430px !important;
        max-width: 460px !important;
    }
    [data-baseweb="select"] > div {
        max-height: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📅 수강 시간표 충돌 검사 및 공강 시각화 대시보드")

# 1. 사이드바: 엑셀 파일 업로드
st.sidebar.header("📂 1. 교과목 엑셀 파일 업로드")
uploaded_file = st.sidebar.file_uploader(
    "개설 교과목 Excel(.xlsx) 또는 CSV 파일을 업로드하세요:",
    type=["xlsx", "csv"],
)

if uploaded_file is None:
    st.info("👈 먼저 왼쪽 사이드바에서 **`수강편람_40과목.xlsx`** 파일을 업로드해 주세요!")
else:
    # 파일 확장자에 맞게 읽어오기
    if uploaded_file.name.endswith(".csv"):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)

    # [담당자 1 함수 호출] 데이터 가공 및 수치화 변환
    processed_df = process_data(raw_df)

    # 2. 사이드바: 수강할 강의 선택 (장바구니 - 처음에는 아무 과목도 선택되지 않은 빈 상태)
    st.sidebar.header("🛒 2. 수강 과목 장바구니 담기")
    course_list = processed_df["강좌선택명"].tolist()

    selected_courses = st.sidebar.multiselect(
        "수강할 강의 선택 (과목명 | 교수명 | 시간표):",
        options=course_list,
        default=[],
    )

    # 선택한 과목만 추려내기
    selected_df = processed_df[processed_df["강좌선택명"].isin(selected_courses)]

    # 사이드바 하단: 내가 담은 과목 표로 한눈에 보여주기
    st.sidebar.markdown("---")
    st.sidebar.subheader(
        f"✅ 내가 담은 과목 ({len(selected_df)}과목 / 총 {selected_df['학점'].sum()}학점)"
    )
    if not selected_df.empty:
        st.sidebar.table(
            selected_df[["과목명", "교수명", "학점", "시간표", "수치화_시간표"]].reset_index(drop=True)
        )
    else:
        st.sidebar.info("아직 장바구니에 담긴 과목이 없습니다.")

    # 3. 오른쪽 메인 화면: 충돌 검사, 주간 시간표, 공강 분석
    if not selected_df.empty:
        # [담당자 2 함수 호출] 충돌 검사
        has_conflict, msgs = check_conflicts(selected_df)

        if has_conflict:
            st.error("🚨 **시간표가 겹칩니다! 아래 충돌 내역을 확인하세요.**")
            for m in msgs:
                st.error(f"- {m}")
        else:
            st.success("✅ 충돌 없이 깔끔한 시간표입니다!")
    else:
        has_conflict = False
        st.info("👈 왼쪽 사이드바 장바구니에서 수강할 과목을 선택하면 아래 시간표에 채워집니다.")

    # 화면을 좌우 2칸으로 나누어 왼쪽엔 시간표(처음엔 빈 시간표), 오른쪽엔 공강 분석 배치
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("🗓️ 나의 주간 시간표 (1~9교시)")
        timetable_grid = create_timetable_grid(selected_df)
        st.dataframe(timetable_grid, use_container_width=True, height=360)

    with col2:
        st.subheader("⏳ 공강 시간 분석 및 추천")
        if selected_df.empty:
            st.write("과목을 1개 이상 선택하면 학점과 공강 분석 결과가 여기에 표시됩니다.")
        elif has_conflict:
            st.warning("먼저 시간표 충돌을 해결해야 정확한 공강 시간을 분석할 수 있습니다.")
        else:
            # [담당자 3 함수 호출] 공강 시간 분석
            max_gap, daily_free_list, recommendation = analyze_free_time(selected_df)

            metric_col1, metric_col2 = st.columns(2)
            metric_col1.metric("총 신청 학점", f"{selected_df['학점'].sum()} 학점")
            metric_col2.metric("최대 연속 공강", f"{max_gap} 시간")

            st.markdown("**📌 요일별 수업 사이 공강 내역:**")
            if daily_free_list:
                for item in daily_free_list:
                    st.write(f"- {item}")
            else:
                st.write("- 수업과 수업 사이에 끼어있는 공강이 없습니다.")

            st.info(f"💡 **맞춤형 활동 추천:**\n\n{recommendation}")

    # 4. 화면 맨 아래: 전체 40개 개설 교과목 목록 표시
    st.divider()
    st.subheader(f"📋 전체 개설 교과목 목록 (총 {len(processed_df)}개 강좌)")
    st.caption(
        "수치화_시간표 열의 앞 숫자들은 연속된 수업 교시(3학점=3개, 1학점=1개)이고, 마지막 숫자는 교수고유번호(101~)입니다."
    )
    display_cols = ["과목명", "교수명", "이수구분", "학점", "시간표", "수치화_시간표"]
    st.dataframe(processed_df[display_cols], use_container_width=True, height=420)
