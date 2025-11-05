import streamlit as st

class LoanCalculator:
    SEOUL_GU = [
        "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
        "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
        "관악구", "서초구", "강남구", "송파구", "강동구",
    ]
  
    STRESS_SPREAD = 3.0 
    LOAN_TYPE_WEIGHTS = {
        "완전 고정금리": 0.00,           # 순수 고정: 스트레스 금리 미적용
        "변동형(5년 미만 변동주기)": 1.00, # 변동형: 100%
        "5년 혼합형(고정 5년 후 변동)": 0.80,  # 혼합형(예: 5년) : 80%
        "5년 주기형(5년마다 재산정)": 0.40,    # 주기형(예: 5년) : 40%
    }
    
    def __init__(self):
        self.inputs = {}
        self.results = {}

    @staticmethod
    def fmt_man(man : float) -> str :
        """금액을 '00억 00만' 형태로 포맷팅"""
        uk, rem = divmod(int(man), 10_000)
        return f"{uk}억 {rem}만" if uk and rem else f"{uk}억" if uk else f"{rem}만"
    
    def get_user_inputs(self):
        """사용자 입력값 수집"""
        with st.container():
            st.header("📊 리빙핏 예산 계산기")
            st.caption("주택구입목적 주택담보대출만 해당됩니다.  \n(생활안정자금 목적 주택담보대출X)")
            col1, col2 = st.columns(2)

            with col1:
                self.inputs['house_price_uk'] = st.text_input(
                    "구매하려는 주택 가격 (억원)",
                    placeholder="예 : 8.5"
                )
                self.inputs['annual_income_man'] = st.text_input(
                    "연소득 (만원)",
                    placeholder="예 : 3000"
                )
                self.inputs['loan_term_years'] = st.text_input(
                    "대출기간 (년)",
                    placeholder="30"
                )
                self.inputs['existing_annual_pay_man'] = st.text_input(
                    "기존 대출의 연간 원리금 상환액 (만원)",
                    placeholder="예 : 420"
                )
                self.inputs['loan_type'] = st.selectbox(
                    "대출 금리 유형",
                    list(self.LOAN_TYPE_WEIGHTS.keys()),
                    index=2  # 기본값: 5년 혼합형
                )


            with col2:
                self.inputs['location'] = st.selectbox(
                    "구매하려는 주택 위치 (서울 25개 자치구)",
                    self.SEOUL_GU
                )
                self.inputs['interest_rate'] = st.text_input(
                    "금리 (%)",
                    placeholder="2.5"
                )
                st.caption(
                    "※ 스트레스 금리(+3.0%p)가 포함되어 계산됩니다."
                    "대출 유형별 적용 비중이 다르게 계산됩니다."
                )
                self.inputs['homeownership'] = st.radio(
                    "현재 주택 보유 여부",
                    options=["생애 최초 구매", "0(처분 조건부 1주택자)", "1주택 이상"],
                    horizontal=False
                )

                # cash_man 입력 처리
                cash_input = st.text_input("주택 구매 가능 현금 (만원)", "0")
                try:
                    self.inputs['cash_man'] = float(cash_input) if cash_input else 0.0
                except ValueError:
                    st.warning("현금 입력값이 유효하지 않습니다. 0으로 처리됩니다.")
                    self.inputs['cash_man'] = 0.0

    def _house_price_uk(self) -> float:
        try:
            return float(self.inputs.get('house_price_uk') or 0.0)
        except ValueError:
            return 0.0

    def _dynamic_cap_man(self) -> tuple[int, str]:
        """
        주택가격 구간별 대출한도(만원)와 안내문구 반환
        ≤15억 → 6억, 15~25억 → 4억, >25억 → 2억
        """
        hp_uk = self._house_price_uk()
        if hp_uk <= 15:
            cap_man, label = 60_000, "주택가격 15억원 이하 → 최대 6억원 한도 [25.10.15 시행]"
        elif hp_uk <= 25:
            cap_man, label = 40_000, "주택가격 15억 초과 25억원 이하 → 최대 4억원 한도 [25.10.15 시행]"
        else:
            cap_man, label = 20_000, "주택가격 25억원 초과 → 최대 2억원 한도 [25.10.15 시행]"
        return cap_man, label

    def calculate_ltv_loan(self):
        """LTV 기준 대출 가능액 계산 (서울 전 지역 규제지역으로 변경)"""
        homeownership = self.inputs['homeownership']
        house_price_man = self._house_price_uk() * 10_000  # 억→만원

        if homeownership == "생애 최초 구매":
            ltv_limit = 0.70
        elif homeownership == "0(처분 조건부 1주택자)":
            ltv_limit = 0.40
        else:
            ltv_limit = 0.00

        loan_amount = house_price_man * ltv_limit
        return ltv_limit, loan_amount

    def calculate_dsr_loan(self, ltv_loan):
        """DSR 기준 대출 가능액 계산"""
        # 입력값 변환
        try:
            annual_income = float(self.inputs['annual_income_man'] or 0)
            existing_pay = float(self.inputs['existing_annual_pay_man'] or 0)
            loan_term = int(self.inputs['loan_term_years'] or 0)
            interest = float(self.inputs['interest_rate'] or 0)
        except ValueError:
            return 0

        # 상품유형 적용비중
        loan_type = self.inputs.get('loan_type', "변동형(5년 미만 변동주기)") #기본값 : 가장 보수적인 가정
        weight = self.LOAN_TYPE_WEIGHTS.get(loan_type, 1.00)
    
        # 스트레스 금리 = 기존금리 + (가산치 × 적용비중)
        stress_add = self.STRESS_SPREAD * weight       # 예: 3.0 × 0.80 = 2.4%p
        stress_rate = interest + stress_add            # 최종 DSR 계산용 금리(%)

        # DSR 허용 상환액 계산
        max_annual_pay = annual_income * stress_rate
        available_pay = max(max_annual_pay - existing_pay, 0)

        # 월 상환액 계산 (만원 → 원 변환)
        monthly_payment_won = (available_pay / 12) * 10_000  # 원 단위

        r = (stress_rate / 100) / 12  # 월 이자율
        n = loan_term * 12  # 총 개월 수

        # 대출 가능액 계산
        if monthly_payment_won <= 0 or r <= 0 or n <= 0:
            return 0

        # 원리금 균등상환 공식 적용
        if r == 0:  # 이자가 없는 경우
            max_loan_won = monthly_payment_won * n
        else:
            max_loan_won = monthly_payment_won * (1 - (1 + r) ** -n) / r

        # 원 → 만원 변환
        max_loan_man = max_loan_won / 10_000
        return min(ltv_loan, max_loan_man)

    def calculate_loan_results(self):
        """대출 관련 최종 결과 계산 - 반환 값 보장"""
        try:
            ltv_limit, ltv_loan = self.calculate_ltv_loan()
            dsr_loan = self.calculate_dsr_loan(ltv_loan)
            cap_man, cap_label = self._dynamic_cap_man()
            possible_loan = min(dsr_loan, cap_man)
            is_capped = dsr_loan > cap_man

            # 결과값을 명시적으로 반환
            return {
                'ltv_limit': ltv_limit,
                'ltv_loan': ltv_loan,
                'dsr_loan': dsr_loan,
                'possible_loan': possible_loan,
                'is_capped': is_capped,
                'cap_label': cap_label,
                'cap_value_man': cap_man,
                'total_cost': possible_loan + self.inputs['cash_man']
            }

        except Exception as e:
            st.error(f"계산 오류 발생: {str(e)}")
            return {
                'ltv_limit': 0,
                'ltv_loan': 0,
                'dsr_loan': 0,
                'possible_loan': 0,
                'is_capped': False,
                'reg_text': "계산 오류",
                'total_cost': self.inputs.get('cash_man', 0)
            }

    def show_loan_results(self):
        """대출 결과 출력 - 안정성 강화 버전"""
        if not st.button("💰 계산하기"):
            return

        # 계산 결과를 지역 변수로 먼저 받기
        results = self.calculate_loan_results()

        self.results = results

        # 박스1: 계산 결과 출력
        st.success(
            f"LTV = {results['ltv_limit'] * 100:.0f}% / DSR = 40%\n\n"
            f"• LTV 기준 대출가능액: {self.fmt_man(results['ltv_loan'])}\n\n"
            f"• DSR 기준 대출가능액: {self.fmt_man(results['dsr_loan'])}\n\n"
            f"• 대출 가능 금액: {self.fmt_man(results['possible_loan'])}\n\n"
            f"💡 주택 구매 가능 현금: {self.fmt_man(self.inputs['cash_man'])}\n"
            f"→ **총 구매 가능 비용: {self.fmt_man(results['total_cost'])}**"
        )

        # 박스2: LTV 관련 규제 안내
        with st.expander("📌 LTV · 규제 상세 정보", expanded=True):
            homeownership = self.inputs['homeownership']

            if homeownership == "생애 최초 구매":
                st.markdown("**생애최초구입자**")
                st.markdown("수도권, 규제지역 내 생애최초 주택구입 목적 주담대 강화 : **LTV 70%**, 6개월 이내 전입 의무. [25.10.15 시행]")
            elif homeownership == "0(처분 조건부 1주택자)":
                st.markdown("**0(처분 조건부 1주택자)**")
                st.markdown(
                    "주택담보대출 실행일로부터 **6개월 내 기존 주택 처분(명의 이전 완료)** 및 증빙 필요. 위반 시 **기한의 이익 상실(대출금 즉시 회수)**, "
                    "**향후 3년간 주택 관련 대출 제한**. [25.10.15 시행]"
                )
                st.markdown("※서울시 25개 자치구 규제지역으로 지정 **LTV 40%** 적용.")
            else:
                st.markdown("**1주택 이상**")
                st.markdown("다주택자 방지 : 추가 **주택** 구입 목적 주택담보대출 금지(**LTV 0%**). [25.10.15 시행]")
                st.markdown("6개월 내 처분 후 추가 주택을 구매 예정이라면 '0(처분 조건부 1주택자)'를 선택하세요.")

            st.markdown("---")
            st.markdown("**가격 구간별 대출한도 상한**")
            st.markdown(
                f"- 현재 적용 상한: **{results['cap_label']}**  \n"
                f"- (참고) 수도권·규제지역 주택구입목적 주담대는 가격 구간별 상한을 적용합니다.  "
                f"**{self.fmt_man(results['cap_value_man'])}** 한도 내에서만 실행됩니다."
            )
            if results['is_capped']:
                st.info("DSR/LTV 산출액이 가격구간 상한을 초과하여, 상한으로 제한되었습니다.")

        # 박스3: DSR 관련 규제 안내
        with st.expander("📌 DSR · 규제 상세 정보", expanded=True):
            st.markdown("**스트레스 금리 적용 내역**")
            applied = self.STRESS_SPREAD * self.LOAN_TYPE_WEIGHTS[self.inputs['loan_type']]
            st.markdown(
                f"- 선택 유형: **{self.inputs['loan_type']}**  \n"
                f"- 적용비중: **{self.LOAN_TYPE_WEIGHTS[self.inputs['loan_type']]*100:.0f}%**  \n"
                f"- 가산치: **{self.STRESS_SPREAD:.1f}%p × {self.LOAN_TYPE_WEIGHTS[self.inputs['loan_type']]*100:.0f}% "
                f"= {applied:.2f}%p**  \n"
                f"- DSR 계산 금리: **입력금리 + 가산치 = {float(self.inputs['interest_rate'] or 0) + applied:.2f}%**"
            )
        
        # 이미지 표시
        # 0) 2024 거래 기록
        st.caption ("아래 자료는 2024년 아파트 매매 실거래가 자료입니다. 해당 기간 거래 기록이 없는 행정동은 '0원'으로 표시되었습니다.")
        # 1) 선택된 자치구별 평균 실거래가
        loc = self.inputs.get("location", "")
        gu_images = f"images2/{loc}_실거래가_평균(2024).png"
        try:
            st.image(gu_images, caption=f"{loc}_실거래가_평균(2024)", use_container_width=True)
        except FileNotFoundError:
            st.warning(f"지역별 이미지 파일을 찾을 수 없습니다: {gu_images}")
        # 2) 서울시 전체 평균 실거래가
        seoul_img = "images2/서울시_실거래가_평균(2024).png"
        st.image(seoul_img, caption="서울시_실거래가_평균(2024)", use_container_width=True)



        # self.results에 저장
        self.results = results

class QualitativeScorer:
    SEOUL_GU = [
        "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
        "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
        "관악구", "서초구", "강남구", "송파구", "강동구",
    ]

    def __init__(self):
        self.inputs = {}
        self.scores = {}
        self.score = 0.0

    def get_qualitative_inputs(self):
        """정성적 요인 입력 수집"""
        with st.container():
            st.header("🏡 나의 리빙핏 스코어는?")
            self.inputs['current_location'] = st.selectbox(
                "현재 거주 중인 지역 (서울 25개 자치구)",
                self.SEOUL_GU
            )
            self.inputs['moving_location'] = st.selectbox(
                "이사가려는 지역 (서울 25개 자치구)",
                self.SEOUL_GU
            )
            self.inputs['current_house_disposition'] = st.radio(
                "현재 거주지를 어떻게 처리할 예정입니까?",
                ["매각", "전·월세", "계속 거주", "현재 전·월세 거주 중"],
                horizontal=False
            )
            self.inputs['school_or_job_here'] = st.radio(
                "직장 / 학교가 이사가려는 지역에 위치합니까?",
                ["예", "아니오"],
                horizontal=True
            )
            self.inputs['stay_period'] = st.radio(
                "이사 후 예상 거주 기간",
                ["2년 이하", "2~4년", "4~10년", "10년 이상"],
                horizontal=False
            )
            self.inputs['has_subscription'] = st.radio(
                "청약 통장 보유 여부",
                ["있음", "없음"],
                horizontal=True
            )

    def calculate_livingfit_score(self):
        """리빙핏 스코어 계산"""
        scores = {
            'location': 100 if self.inputs['current_location'] == self.inputs['moving_location'] else 50,
            'disposition': {
                "매각": 75,
                "전·월세": 50,
                "계속 거주": 25,
                "현재 전·월세 거주 중": 100
            }[self.inputs['current_house_disposition']],
            'job_school': 100 if self.inputs['school_or_job_here'] == "예" else 50,
            'stay': {
                "2년 이하": 25,
                "2~4년": 50,
                "4~10년": 75,
                "10년 이상": 100
            }[self.inputs['stay_period']],
            'subscription': 100 if self.inputs['has_subscription'] == "있음" else 50,
        }

        weights = {
            'location': 0.25,
            'disposition': 0.25,
            'job_school': 0.20,
            'stay': 0.20,
            'subscription': 0.10,    
        }

        # (3) self.scores, self.score에 결과 저장
        self.scores = scores
        self.score = sum(scores[k] * weights[k] for k in scores)  # ── 수정

        return self.score, self.scores


    def show_livingfit_results(self):
        """리빙핏 스코어 결과 출력"""
        if not st.button("🧮 리빙핏 스코어 계산하기"):
            return

        try:
            score, scores = self.calculate_livingfit_score()
        except Exception as e:
            st.error(f"점수 계산 오류: {str(e)}")
            return

        # 적합도 판정
        if score >= 80:
            verdict, img = "매우 적합", "very_good.png"
        elif score >= 60:
            verdict, img = "적합", "good.png"
        elif score >= 40:
            verdict, img = "보통", "so_so.png"
        elif score >= 20:
            verdict, img = "부적합", "bad.png"
        else:
            verdict, img = "매우 부적합", "very_bad.png"

        # 결과 출력
        st.image(f"./images/{img}", use_container_width=True)
        st.success(
            f"나의 리빙핏 스코어는 **{score:.1f}점 / 100점**\n"
            f"→ **{verdict}**"
        )

        # 상세 점수 표시
        with st.info("항목별 점수 상세"):
            comments = {
                (80,100): "매우 안정적인 조건의 실수요자로 판단됩니다. 대부분의 정책 기준에 부합하여 주택 구매를 적극 검토할 수 있습니다.",
                (60,79): "현재 조건에서 주택 구매가 비교적 안정적입니다. 실수요로 판단될 가능성이 높습니다. 다만, 과도한 대출 비율에는 유의해야 합니다.",
                (40,59): "일정 조건에서는 주택 구매가 가능하나, 주의가 필요합니다. 청약 통장 등의 제도를 활용할 것을 추천합니다.",
                (20,39): "주택 구매 요건이 충분하지 않습니다. 실수요 요건 충족이 미흡하기 때문에 신중한 접근이 필요합니다.",
                (0,19): "현재 상황에서 주택 구매는 매우 위험합니다. 실수요 가능성이 매우 낮아 정책상 규제나 금융 리스크에 크게 노출될 수 있습니다.",
            }
            for (low, high), text in comments.items():
                if low <= score <= high:
                    st.info(text)
                    break

class LivingFitApp:
    def __init__(self):
        st.set_page_config(page_title="리빙핏 스코어", page_icon="🏠", layout="centered")
        st.title("🏠 주택 금융 건전성 자가 진단")
        st.caption("내 집 마련을 위한 금융 건전성 가이드")

        self.loan_calculator = LoanCalculator()
        self.qual_scorer = QualitativeScorer()

    def run(self):
        # 1) 대출 파트
        #   ① 입력 받기
        self.loan_calculator.get_user_inputs()
        #   ② “계산하기” 버튼 누를 때 계산하고 출력하기
        self.loan_calculator.show_loan_results()

        # 3) 정성적 파트
        self.qual_scorer.get_qualitative_inputs()
        self.qual_scorer.show_livingfit_results()

if __name__ == "__main__":
    LivingFitApp().run()
