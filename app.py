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

# 초기화 버튼 제공
if st.sidebar.button("🔄 파일 다시 업로드하기 (초기화)"):
    st.session_state.merged_df = None
    st.session_state.student_notes = {}
    st.session_state.student_results = {}
    st.rerun()

# 2. 파일 업로드 사이드바
st.sidebar.header("📁 데이터 파일 업로드")
holland_file = st.sidebar.file_uploader("1. 진로홀랜드 CSV 파일 업로드", type=["csv"])
base_file = st.sidebar.file_uploader("2. 통합 문서1 CSV 파일 업로드", type=["csv"])

# 파일을 유연하게 읽는 함수 (콤마/탭/인코딩 자동 분석)
def safe_read_csv(uploaded_file):
    if uploaded_file is None:
        return None
    bytes_data = uploaded_file.getvalue()
    if not bytes_data.strip():
        st.error(f"⚠️ {uploaded_file.name} 파일이 비어 있습니다.")
        return None
        
    # 시도할 인코딩과 구분자 조합
    encodings = ['utf-8', 'cp949', 'utf-8-sig', 'euc-kr']
    separators = [',', '\t', ';']
    
    for enc in encodings:
        for sep in separators:
            try:
                # 데이터를 처음부터 다시 읽기 위해 BytesIO 사용
                df = pd.read_csv(io.BytesIO(bytes_data), encoding=enc, sep=sep)
                if not df.empty and len(df.columns) > 1:
                    return df
            except Exception:
                continue
                
    # 만약 일반 CSV 로드 실패 시, Excel 포맷일 가능성 대비 안전망
    try:
        df = pd.read_excel(io.BytesIO(bytes_data))
        if not df.empty:
            return df
    except Exception:
        pass
        
    return None

# 파일이 둘 다 업로드되었을 때 병합 수행
if holland_file and base_file and st.session_state.merged_df is None:
    with st.spinner("파일을 분석하고 매칭하는 중입니다..."):
        df_holland = safe_read_csv(holland_file)
        df_base = safe_read_csv(base_file)
        
        if df_holland is None:
            st.error("❌ '진로홀랜드' 파일에서 열(Column)을 추출하지 못했습니다. 파일이 비어있거나 올바른 데이터 형식이 아닙니다.")
        elif df_base is None:
            st.error("❌ '통합 문서1' 파일에서 열(Column)을 추출하지 못했습니다. 파일이 비어있거나 올바른 데이터 형식이 아닙니다.")
        else:
            try:
                # 컬럼명 문자열 정제 및 공백 제거
                df_holland.columns = df_holland.columns.astype(str).str.strip()
                df_base.columns = df_base.columns.astype(str).str.strip()
                
                # --- [이름/성명 컬럼 자동 탐색] ---
                holland_name_col = None
                for col in ['이름', '성명', '학생명', '이 름', '이름/성명']:
                    if col in df_holland.columns:
                        holland_name_col = col
                        break
                if holland_name_col is None:
                    # '이름' 글자가 포함된 열 탐색
                    for col in df_holland.columns:
                        if '이름' in col or '성명' in col:
                            holland_name_col = col
                            break
                    if holland_name_col is None:
                        holland_name_col = df_holland.columns[4] if len(df_holland.columns) > 4 else df_holland.columns[0]
                        
                base_name_col = None
                for col in ['성명', '이름', '학생명', '성 명']:
                    if col in df_base.columns:
                        base_name_col = col
                        break
                if base_name_col is None:
                    for col in df_base.columns:
                        if '성명' in col or '이름' in col:
                            base_name_col = col
                            break
                    if base_name_col is None:
                        base_name_col = df_base.columns[3] if len(df_base.columns) > 3 else df_base.columns[0]

                # 기준 키 생성
                df_holland['match_name'] = df_holland[holland_name_col].astype(str).str.strip()
                df_base['match_name'] = df_base[base_name_col].astype(str).str.strip()
                df_base['성명'] = df_base[base_name_col] # UI 일관성 보장
                
                # --- [단축형 및 직업 데이터 컬럼 탐색] ---
                short_text_col = None
                for col in df_holland.columns:
                    if '단축형' in col or '참고자료' in col:
                        short_text_col = col
                        break
                if short_text_col is None:
                    # 열 인덱스로 백업 탐색
                    short_text_col = df_holland.columns[8] if len(df_holland.columns) > 8 else df_holland.columns[-1]
                    
                job_col = None
                for col in df_holland.columns:
                    if '직업' in col or '진로' in col or '학과' in col:
                        job_col = col
                        break
                
                # 안전한 매칭 임시용 DataFrame 구축
                df_holland_sub = pd.DataFrame()
                df_holland_sub['match_name'] = df_holland['match_name']
                df_holland_sub['단축형_데이터'] = df_holland[short_text_col] if short_text_col in df_holland.columns else "진로 특성"
                
                if job_col and job_col in df_holland.columns:
                    df_holland_sub['직업_데이터'] = df_holland[job_col]
                else:
                    # 만약 파일 뒷부분에 텍스트가 섞여있다면 첫 줄에서 역추적
                    df_holland_sub['직업_데이터'] = "관련 진로 분야"
                
                df_holland_sub = df_holland_sub.drop_duplicates(subset=['match_name'])
                
                # 최종 병합
                merged = pd.merge(df_base, df_holland_sub, on='match_name', how='left')
                
                # 가통 저장 열 보장
                if '1학기 개별가통' not in merged.columns:
                    merged['1학기 개별가통'] = ""
                else:
                    merged['1학기 개별가통'] = merged['1학기 개별가통'].fillna("")
                    
                st.session_state.merged_df = merged
                
                for idx, row in merged.iterrows():
                    name = row['성명']
                    if pd.notna(row['1학기 개별가통']) and str(row['1학기 개별가통']).strip() != "":
                        st.session_state.student_results[name] = row['1학기 개별가통']
                        
            except Exception as e:
                st.error(f"⚙️ 데이터 병합 프로세스 중 에러 발생: {e}")

# 3. 메인 프로세스 UI
if st.session_state.merged_df is not None:
    df = st.session_state.merged_df
    student_list = df['성명'].dropna().unique().tolist()
    
    st.sidebar.markdown("---")
    selected_student = st.sidebar.selectbox("🧑‍🎓 학생 명단 선택", student_list)
    
    student_row = df[df['성명'] == selected_student].iloc[0]
    
    holland_short = student_row.get('단축형_데이터', '진로 특성')
    if pd.isna(holland_short) or str(holland_short).strip() == "": holland_short = "진로 특성"
        
    job_recommend = student_row.get('직업_데이터', '추천 직업')
    if pd.isna(job_recommend) or str(job_recommend).strip() == "": job_recommend = "해당 분야"
    
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
                generated_text = (
                    f"{selected_student} 학생은 {teacher_input.strip()}. "
                    f"진로 시간에 실시한 홀랜드 검사 결과는 {str(holland_short).strip()} 하는 것으로 나타났습니다. "
                    f"따라서 {str(job_
