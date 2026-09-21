import streamlit as st
from core.data_loader import load_uploaded_data
from core.profiler import profile_dataframe

st.set_page_config(page_title='InsightAI', page_icon='📊', layout='wide', initial_sidebar_state='expanded')

with open('assets/styles.css', encoding='utf-8') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.sidebar.markdown('## ✦ InsightAI')
st.sidebar.caption('AI-Powered Data Analytics Platform')

uploaded = st.sidebar.file_uploader('Upload CSV or Excel', type=['csv', 'xlsx', 'xls'])

st.markdown('<div class="hero"><div><div class="eyebrow">INTELLIGENT DATA ANALYTICS</div><h1>InsightAI</h1><p>Upload your data, explore it visually, and turn raw numbers into actionable insights.</p></div></div>', unsafe_allow_html=True)

if uploaded:
    try:
        df = load_uploaded_data(uploaded)
        profile = profile_dataframe(df)
        st.success(f'Loaded {uploaded.name}')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Rows', f"{profile['rows']:,}")
        c2.metric('Columns', f"{profile['columns']:,}")
        c3.metric('Missing Values', f"{profile['missing_pct']:.1f}%")
        c4.metric('Duplicate Rows', f"{profile['duplicates']:,}")

        st.markdown('### Dataset Preview')
        st.dataframe(df.head(100), use_container_width=True, height=420)

        st.markdown('### Data Profile')
        st.dataframe(profile['column_profile'], use_container_width=True)
    except Exception as exc:
        st.error(f'Could not load the dataset: {exc}')
else:
    st.markdown('### Start with a dataset')
    a, b, c = st.columns(3)
    a.markdown('**01 · Upload**\n\nCSV or Excel file')
    b.markdown('**02 · Explore**\n\nProfile, quality and statistics')
    c.markdown('**03 · Analyze**\n\nAI insights and interactive analytics')
    st.info('Use the sidebar to upload a CSV or Excel file. A sample dataset is included in the repository for testing.')
