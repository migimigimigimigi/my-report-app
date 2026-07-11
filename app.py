import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="가정통신문 자동 생성 웹앱", layout="wide")

st.title("📝 중학교 1학기말 개별 가정통신문 자동 생성기")
st.markdown("홀랜드 진로검사 결과와 교사의 관찰 특징을 조합하여 가정통신문 문구를 생성합니다.")

# 1. session_state 초기화
if "merged_df" not in st.session_state:
    st.session_state.merged_df = None
if "student_notes" not in st.session_state:
    st.session_state.student_notes = {}
if "student_results" not in st.session_state:
    st.session_state.student_results = {}

# 2. 파일 업로드 사이드바
st.sidebar.header("📁 데이터 파일 업로드")
holland_file = st.sidebar.file_uploader("1. 진로홀랜드 CSV 파일 업로드", type=["csv"])
base_file = st.sidebar.file_uploader("2. 통합 문서1 CSV 파일 업로드", type=["csv"])

# 파일이 둘 다 업로드되었을 때 병합 수행
if holland_file and base_file and st.session_state.merged_df is None:
    try:
        # 한글 깨짐 방지를 위해 인코딩을 유연하게 처리
        try:
            df_holland = pd.read_csv(holland_file, encoding='utf-8')
        except UnicodeDecodeError:
            df_holland = pd.read_csv(holland_file, encoding='cp949')
            
        try:
            df_base = pd.read_csv(base_file, encoding='utf-8')
        except UnicodeDecodeError:
            df_base = pd.read_csv(base_file, encoding='cp949')
        
        # 공백 제거 및 이름 매칭 준비
        df_holland['이름'] = df_holland['이름'].astype(str).str.strip()
        df_base['성명'] = df_base['성명'].astype(str).str.strip()
        
        # [핵심 수정] '적합한직업' 컬럼이 없는 경우 예외 처리 및 유연한 매칭
        if '적합한직업' not in df_holland.columns:
            # 혹시 유사한 이름의 컬럼이 있는지 확인
            possible_cols = [c for c in df_holland.columns if '직업' in c or '진로' in c]
            if possible_cols:
                # 가장 유사한 첫 번째 컬럼을 '적합한직업'으로 복사해서 사용
                df_holland['적합한직업'] = df_holland[possible_cols[0]]
            else:
                # 아예 직업 관련 컬럼이 없으면 빈 텍스트나 기본값으로 생성하여 KeyError 방지
                df_holland['적합한직업'] = "관련 진로"

        # 필요한 컬럼 안전하게 추출
        holland_cols = ['이름', '담임 선생님용 생기부 참고자료 단축형', '적합한직업']
        df_holland_sub = df_holland[holland_cols].drop_duplicates(subset=['이름'])
        
        # 통합 문서1 기준으로 left join 병합
        merged = pd.merge(df_base, df_holland_sub, left_on='성명', right_on='이름', how='left')
        
        # 기존 가통 컬럼 비어있으면 초기화
        if '1학기 개별가통' not in merged.columns:
            merged['1학기 개별가통'] = ""
        else:
            merged['1학기 개별가통'] = merged['1학기 개별가통'].fillna("")
            
        st.session_state.merged_df = merged
        
        # 기존 데이터 복구용 세션 초기화
        for idx, row in merged.iterrows():
            name = row['성명']
            if pd.notna(row['1학기 개별가통']) and row['1학기 개별가통'] != "":
                st.session_state.student_results[name] = row['1학기 개별가통']
                
    except Exception as e:
        st.error(f"파일을 읽고 병합하는 중 오류가 발생했습니다: {e}")

# 3. 데이터가 로드된 이후의 UI 프로세스
if st.session_state.merged_df is not None:
    df = st.session_state.merged_df
    student_list = df['성명'].tolist()
    
    # 사이드바에서 학생 선택
    st.sidebar.markdown("---")
    selected_student = st.sidebar.selectbox("🧑‍🎓 학생 명단 선택", student_list)
    
    # 현재 선택된 학생의 데이터 행 추출
    student_row = df[df['성명'] == selected_student].iloc[0]
    
    # 데이터 매칭 정보 안전하게 가져오기 (결측치 처리 포함)
    holland_short = student_row.get('담임 선생님용 생기부 참고자료 단축형', '정보 없음')
    if pd.isna(holland_short): holland_short = "진로 특성"
        
    job_recommend = student_row.get('적합한직업', '추천 직업 정보 없음')
    if pd.isna(job_recommend): job_recommend = "해당 분야"
    
    # 메인 화면 UI 구성
    st.subheader(f"📍 {selected_student} 학생 기록 중")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.info("💡 **홀랜드 검사 참고 자료**")
        st.markdown(f"**[진로코드 단축형 내용]**\n\n{holland_short}")
        st.markdown(f"**[추천 진로/직업]**\n\n`{job_recommend}`")
        
    with col2:
        saved_note = st.session_state.student_notes.get(selected_student, "")
        teacher_input = st.text_area(
            "✍️ 실제 학급 역할 및 관찰 특징 입력",
            value=saved_note,
            placeholder="예시: 학급의 환경미화 부장으로서 교실 환경 정리에 책임감을 가지고 주도적으로 참여함",
            key=f"input_{selected_student}"
        )
        st.session_state.student_notes[selected_student] = teacher_input
        
        if st.button("✨ 문구 생성 및 반영", type="primary"):
            if not teacher_input.strip():
                st.warning("교사의 관찰 특징을 입력해주세요.")
            else:
                # 필수 준수 템플릿 양식 적용
                generated_text = (
                    f"{selected_student} 학생은 {teacher_input.strip()}. "
                    f"진로 시간에 실시한 홀랜드 검사 결과는 {str(holland_short).strip()} 하는 것으로 나타났습니다. "
                    f"따라서 {str(job_recommend).strip()} 등의 진로 분야가 어울린진다고 제안되었습니다. "
                    f"그러니 검사 결과를 충분히 활용하여 이번 여름 방학 때 진로에 대해 충분히 의논해보는 귀한 시간이 되어 보시기 바랍니다."
                )
                
                st.session_state.student_results[selected_student] = generated_text
                st.success("문구가 성공적으로 생성되어 데이터프레임에 반영되었습니다!")

    # 현재 학생의 생성 문구 확인
    st.markdown("---")
    st.write("### 🔍 현재 학생 생성 문구 미리보기")
    current_result = st.session_state.student_results.get(selected_student, "아직 생성된 문구가 없습니다. 오른쪽에서 문구를 생성해주세요.")
    st.code(current_result, language="text")
    
    # 데이터프레임에 실시간 반영
    for name, text in st.session_state.student_results.items():
        df.loc[df['성명'] == name, '1학기 개별가통'] = text
        
    # 전체 진행 상황 표시
    st.markdown("---")
    completed_count = len(st.session_state.student_results)
    total_count = len(student_list)
    st.write(f"📊 **전체 작성 진행도:** {completed_count} / {total_count} 명 완료")
    st.progress(completed_count / total_count)
    
    # 4. 전체 저장 및 다운로드 기능
    st.subheader("💾 최종 결과물 다운로드")
    
    export_df = df.copy()
    # 원본 파일 틀 유지를 위해 임시 추가된 홀랜드 데이터 컬럼들 삭제
    columns_to_drop = ['이름', '담임 선생님용 생기부 참고자료 단축형', '적합한직업']
    for col in columns_to_drop:
        if col in export_df.columns:
            export_df = export_df.drop(columns=[col])
            
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='1학기 개별가통 결과')
    processed_data = output.getvalue()
    
    st.download_button(
        label="📥 엑셀(.xlsx) 파일로 전체 다운로드",
        data=processed_data,
        file_name="1학기_말_개별가정통신문_결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    with st.expander("👀 현재까지 채워진 전체 표 확인하기"):
        st.dataframe(export_df)

else:
    st.info("👈 웹앱을 시작하려면 왼쪽 사이드바에서 두 개의 CSV 데이터 파일(`26-진로홀랜드.csv`, `통합 문서1.csv`)을 업로드해 주세요.")
