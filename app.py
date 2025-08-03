import streamlit as st
st.set_page_config(page_title="리빙핏 스코어", page_icon="🏠", layout="centered")

st.title("🏠 리빙핏 스코어")
st.caption("내 집 마련을 위한 금융 건전성 가이드")

# ────────────────────────────────────────────────────────────
# INPUT ▼
# ────────────────────────────────────────────────────────────

st.header("📊 기본 정보 입력")

# 서울 25개 자치구 목록
seoul_gu = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
    "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
    "관악구", "서초구", "강남구", "송파구", "강동구",
]

col1, col2 = st.columns(2)

with col1:
    # 1) 주택 가격 (억 원 단위 입력 → 만원 단위로 변환)
    house_price_uk = st.text_input(
        "구매하려는 주택 가격 (억원)",
        placeholder="예 : 8.5",  # 8억 5천만원
    )

    # 이후 계산에서 그대로 쓰던 house_price_man(만원)을 유지하기 위해 변환
    house_price_man = float(house_price_uk or 0) * 10_000

    # 4) 연소득 (만원 단위)
    annual_income_man = st.text_input(
        "연소득 (만원)",
        placeholder = "예 : 3000",
    )

    # 6) 대출기간 (년)
    loan_term_years = st.text_input(
        "대출기간 (년)",
        placeholder = "3",
    )

with col2:
    # 2) 주택 위치 (텍스트)
    location = st.selectbox(
        "구매하려는 주택 위치 (서울 25개 자치구)",
        seoul_gu,
        index=0,  # 기본값: 강남구
    )

    # 5) 기존 대출의 **연간** 원리금 상환액 (만원 단위)
    existing_annual_pay_man = st.text_input(
        "기존 대출의 연간 원리금 상환액 (만원)",
        placeholder="예 : 420",  # 1년 동안 갚는 원리금 총액을 만원 단위로 입력
    )

    # 7) 금리 (%)
    interest_rate = st.text_input(
        "금리 (%)",
        placeholder = "2.5",
    )

    # 3) 주택 보유 여부 (라디오)
    homeownership = st.radio(
        "현재 주택 보유 여부",
        options=["생애 최초 구매", "0(처분 조건부 1주택자)", "1주택 이상"],
        horizontal=False,
    )

# ────────────────────────────────────────────────────────────
# LTV 한도 계산 ▼
# ────────────────────────────────────────────────────────────
non_regulated = {
    "노원구", "도봉구", "강북구", "금천구", "관악구", "구로구", "중랑구"
}

# 주택 보유·지역별 LTV 상한
if homeownership == "생애 최초 구매":
    ltv_limit = 0.70
elif homeownership == "0(처분 조건부 1주택자)":
    ltv_limit = 0.70 if location in non_regulated else 0.50
else:  # "1+"
    ltv_limit = 0.00

# ↓ 이후 계산식에서 고정값 대신 ltv_limit 사용
# 주택 보유·지역별 LTV 상한
if homeownership == "생애 최초 구매":
    ltv_limit = 0.70
elif homeownership == "0(처분 조건부 1주택자)":
    ltv_limit = 0.70 if location in non_regulated else 0.50
else:  # "1주택 이상"
    ltv_limit = 0.00

# ➤ LTV 기준 대출가능액(만원) 계산
house_price_val        = float(house_price_man or 0)
loan_amount_ltv_man    = house_price_val * ltv_limit     # 만원 단위


# ────────────────────────────────────────────────────────────
# DSR 40 % 한도 기반 최대 대출가능액 계산 ▼
# ────────────────────────────────────────────────────────────
DSR_LIMIT = 0.40

annual_income_val       = float(annual_income_man       or 0)
existing_annual_pay_val = float(existing_annual_pay_man or 0)
loan_term_val           = int(loan_term_years           or 0)
interest_val            = float(interest_rate           or 0)

stress_rate = interest_val + 1.5  # %

# 새 대출 연간 상환액 함수
def annual_payment_man(principal_man, rate_pct, term_years):
    if principal_man == 0 or term_years == 0:
        return 0.0
    r = rate_pct / 100 / 12
    n = term_years * 12
    if r == 0:
        return principal_man / term_years
    m_won = principal_man * 10_000 * r / (1 - (1 + r) ** -n)
    return m_won * 12 / 10_000  # 만원 단위

# ① 기존 대출 연간 상환액
old_pay_man = existing_annual_pay_val

# ② DSR 상한이 허용하는 연간 상환 여력
max_annual_pay_man   = annual_income_val * DSR_LIMIT
avail_annual_pay_man = max(max_annual_pay_man - old_pay_man, 0)

# ③ 월 상환 여력(원) → 최대 대출가능액(만원)
P_won = avail_annual_pay_man / 12 * 10_000     # 월 상환 가능액
r     = stress_rate / 100 / 12
n     = loan_term_val * 12

if P_won == 0 or r == 0 or n == 0:
    max_loan_dsr_man = 0
else:
    max_loan_won   = P_won * (1 - (1 + r) ** -n) / r
    max_loan_dsr_man = max_loan_won / 10_000

# ④ 두 규제 중 작은 값을 실제 한도로
possible_loan_man = min(loan_amount_ltv_man, max_loan_dsr_man)


# ➤ 금액을 “00억 00만” 형태로 바꾸는 헬퍼
def fmt_man(man):
    uk  = int(man) // 10_000        # 억
    rem = int(man) % 10_000         # 만
    if uk and rem:
        return f"{uk}억 {rem}만"
    elif uk:      # 만원이 0
        return f"{uk}억"
    else:
        return f"{rem}만"

# ────────────────────────────────────────────────────────────
if st.button("💰 계산하기"):

    st.success(
        f"LTV = {ltv_limit*100:.0f}% / DSR = 40%\n\n"
        f"• LTV 기준 대출가능액: {fmt_man(loan_amount_ltv_man)}\n"
        f"• DSR 기준 대출가능액: {fmt_man(max_loan_dsr_man)}\n"
        f"→ 최종 대출가능액: **{fmt_man(possible_loan_man)}**"
    )

    if homeownership == "생애 최초 구매":
        st.warning(
            "6개월 내 전입 의무 부과. 이를 지키지 않을 시 **대출 회수** 및 "
            "**3년 간 주택 대출 제한** 대상이 될 수 있음"
        )
    elif homeownership == "1주택 이상":
        st.error("대출이 불가능합니다")


# ────────────────────────────────────────────────────────────
# 🏡 나의 리빙핏 스코어는? ▼   ― 정성적 요인 입력
# ────────────────────────────────────────────────────────────
st.header("🏡 나의 리빙핏 스코어는?")

# 1) 현재 거주지
current_location = st.selectbox(
    "현재 거주 중인 지역 (서울 25개 자치구)",
    seoul_gu,
    index=0,
)

# 2) 이사가려는 지역
moving_location = st.selectbox(
    "이사가려는 지역 (서울 25개 자치구)",
    seoul_gu,
    index=0,
)

# 3) 직장·학교 위치
school_or_job_here = st.radio(
    "직장 / 학교가 이사가려는 지역에 위치합니까?",
    ["예", "아니오"],
    horizontal=True,
)

# 4) 예상 거주 기간 (옵션 선택형)
stay_period = st.radio(
    "이사 후 예상 거주 기간",
    ["2년 이하", "2~4년", "4~10년", "10년 이상"],
    horizontal=False,
)


# 5) 현재 거주지 처리 방식
current_house_disposition = st.radio(
    "현재 거주지를 어떻게 처리할 예정입니까?",
    ["매각", "전·월세", "계속 거주", "현재 전·월세 거주 중"],
    horizontal=False,
)

# 6) 청약 통장 보유 여부
has_subscription = st.radio(
    "청약 통장 보유 여부",
    ["있음", "없음"],
    horizontal=True,
)
# ────────────────────────────────────────────────────────────
# 📝 정성적 요인 점수 계산  (가중치 적용 전)
# ────────────────────────────────────────────────────────────
# 1) 현재 거주지 = 이사가려는 곳?
score_location = 100 if current_location == moving_location else 50

# 2) 직장·학교 위치
score_job_school = 100 if school_or_job_here == "예" else 50

# 3) 예상 거주 기간
stay_score_map = {
    "2년 이하": 25,
    "2~4년": 50,
    "4~10년": 75,
    "10년 이상": 100,
}
score_stay = stay_score_map[stay_period]

# 4) 현재 거주지 처리 방식
disp_score_map = {
    "매각": 75,
    "전·월세": 50,
    "계속 거주": 25,
    "현재 전·월세 거주 중": 100,
}
score_disposition = disp_score_map[current_house_disposition]

# 5) 청약 통장
score_subscription = 100 if has_subscription == "있음" else 50

# 딕셔너리로 모아두면 가중치 적용이 편리합니다
raw_scores = {
    "location": score_location,
    "job_school": score_job_school,
    "stay": score_stay,
    "disposition": score_disposition,
    "subscription": score_subscription,
}

# ────────────────────────────────────────────────────────────
# 🎯 가중치 정의 (퍼센트 → 소수)
# ────────────────────────────────────────────────────────────
weights = {
    "location":     0.20,  # 현재 거주지 = 이사가려는 곳?
    "job_school":   0.27,  # 직장·학교 위치
    "stay":         0.20,  # 예상 거주 기간
    "disposition":  0.27,  # 현재 거주지 처리
    "subscription": 0.06,  # 청약 통장 보유
}

# ────────────────────────────────────────────────────────────
# 🧮 리빙핏 스코어 계산하기 버튼 ─ 클릭 시 결과 출력
if st.button("🧮 리빙핏 스코어 계산하기"):
    # 1) 가중치 적용
    livingfit_score = sum(raw_scores[k] * weights[k] for k in weights)

    # 2) 적합도 구간 판정 + 이미지 파일 매핑
    if livingfit_score >= 80:
        verdict = "매우 적합"
        img_file = "very_good.png"   # 예: ./images/very_good.png
    elif livingfit_score >= 60:
        verdict = "적합"
        img_file = "good.png"
    elif livingfit_score >= 40:
        verdict = "보통"
        img_file = "so_so.png"
    elif livingfit_score >= 20:
        verdict = "부적합"
        img_file = "bad.png"
    else:
        verdict = "매우 부적합"
        img_file = "very_bad.png"

    # 3) 결과에 맞는 이미지 표시
    st.image(f"./images/{img_file}", use_container_width=True)

    # 4) 결과 표시
    st.success(
        f"나의 리빙핏 스코어는 **{livingfit_score:.1f}점 / 100점**  \n"
        f"→ **{verdict}**"
    )

    # 5) (선택) 항목별 점수 상세
    with st.expander("항목별 점수 상세"):
        for k, v in raw_scores.items():
            st.write(f"- {k}: {v}점 × {weights[k]*100:.0f}% = {(v*weights[k]):.1f}점")

