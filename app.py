import streamlit as st
import pandas as pd
import re
from io import BytesIO
from supabase import create_client, Client

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Excel Filter App - Supabase", layout="wide")
st.markdown("<h2>📊 ฐานข้อมูลโครงการ ของส่วนส่งเสริมและถ่ายทอดเทคโนโลยี</h2>", unsafe_allow_html=True)
st.markdown("<p style='font-size:16px'>ข้อมูลปี 2561–2568 จาก Supabase</p>", unsafe_allow_html=True)

# --- เชื่อมต่อ Supabase ---
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "budgets"

# --- โหลดข้อมูลจาก Supabase ---
@st.cache_data(ttl=0, show_spinner="📡 กำลังโหลดข้อมูลจาก Supabase...")
def load_data():
    page_size = 1000
    offset = 0
    all_data = []

    while True:
        response = supabase.table(TABLE_NAME).select("*").range(offset, offset + page_size - 1).execute()
        batch = response.data
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return pd.DataFrame(all_data)

df = load_data()

# --- ตรวจสอบคอลัมน์ ---
required_columns = ["ลำดับ", "โครงการ", "รูปแบบงบประมาณ", "ปีงบประมาณ", "หน่วยงาน",
                    "สถานที่", "หมู่ที่", "ตำบล", "อำเภอ", "จังหวัด"]
if not all(col in df.columns for col in required_columns):
    st.error("ตาราง Supabase ไม่มีคอลัมน์ที่ต้องการ หรือชื่อคอลัมน์ไม่ถูกต้อง")
    st.stop()

# --- ฟังก์ชัน ---
def extract_number(s):
    match = re.search(r"\d+", str(s))
    return int(match.group()) if match else float('inf')

def get_options(df, col_name):
    opts = df[col_name].dropna().unique().tolist()
    if col_name == "ปีงบประมาณ":
        opts = sorted([str(x) for x in opts])
    elif col_name == "หน่วยงาน":
        opts = sorted(opts, key=extract_number)
    else:
        opts.sort()
    return ["ทั้งหมด"] + opts

filtered_for_options = df.copy()

# --- ตัวกรอง ---
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    budget_options = get_options(filtered_for_options, "รูปแบบงบประมาณ")
    selected_budget = st.selectbox("💰 รูปแบบงบประมาณ", budget_options, key="budget_select")
    if selected_budget != "ทั้งหมด":
        filtered_for_options = filtered_for_options[filtered_for_options["รูปแบบงบประมาณ"] == selected_budget]

with col2:
    year_options = get_options(filtered_for_options, "ปีงบประมาณ")
    selected_year = st.selectbox("📅 ปีงบประมาณ", year_options, key="year_select")
    if selected_year != "ทั้งหมด":
        filtered_for_options = filtered_for_options[filtered_for_options["ปีงบประมาณ"].astype(str) == selected_year]

with col3:
    project_options = get_options(filtered_for_options, "โครงการ")
    selected_project = st.selectbox("📌 โครงการ", project_options, key="project_select")
    if selected_project != "ทั้งหมด":
        filtered_for_options = filtered_for_options[filtered_for_options["โครงการ"] == selected_project]

with col4:
    department_options = get_options(filtered_for_options, "หน่วยงาน")
    default_departments = st.session_state.get("dept_select", ["ทั้งหมด"])
    valid_defaults = [d for d in default_departments if d in department_options]
    if not valid_defaults:
        valid_defaults = ["ทั้งหมด"]
    selected_departments = st.multiselect("🏢 หน่วยงาน", department_options, default=valid_defaults, key="dept_select")
    if "ทั้งหมด" not in selected_departments:
        filtered_for_options = filtered_for_options[filtered_for_options["หน่วยงาน"].isin(selected_departments)]

# --- กรองข้อมูล ---
filtered_df = df.copy()

if selected_budget != "ทั้งหมด":
    filtered_df = filtered_df[filtered_df["รูปแบบงบประมาณ"] == selected_budget]

if selected_year != "ทั้งหมด":
    filtered_df = filtered_df[filtered_df["ปีงบประมาณ"].astype(str) == selected_year]

if selected_project != "ทั้งหมด":
    filtered_df = filtered_df[filtered_df["โครงการ"] == selected_project]

if "ทั้งหมด" not in selected_departments:
    filtered_df = filtered_df[filtered_df["หน่วยงาน"].isin(selected_departments)]

if not filtered_df.empty:
    st.markdown(
        f"<div style='font-size:24px; color:#3178c6; background-color:#d0e7ff; padding:10px; border-radius:6px;'>"
        f"📈 พบข้อมูลทั้งหมด {len(filtered_df)} แห่ง</div>",
        unsafe_allow_html=True
    )
else:
    st.warning("⚠️ ไม่พบข้อมูลที่ตรงกับเงื่อนไขที่เลือก")

tab_table, tab_chart = st.tabs(["📄 ตารางข้อมูล", "📊 กราฟสรุป"])

with tab_table:
    filtered_df = filtered_df.drop(columns=["id"], errors="ignore")
    st.dataframe(filtered_df, use_container_width=True)
    
import plotly.express as px

with tab_chart:
    if not filtered_df.empty:
        st.markdown("### 📊 จำนวนโครงการในแต่ละปี")

        # เตรียมข้อมูล
        filtered_df["ปีงบประมาณ"] = filtered_df["ปีงบประมาณ"].astype(str)
        grouped = (
            filtered_df.groupby(["ปีงบประมาณ", "รูปแบบงบประมาณ"])
            .size()
            .reset_index(name="จำนวนโครงการ")
        )

        # สร้างกราฟพร้อมตัวเลขบนแท่ง
        fig = px.bar(
            grouped,
            x="ปีงบประมาณ",
            y="จำนวนโครงการ",
            color="รูปแบบงบประมาณ",
            barmode="group",
            text_auto=True,  # <-- โชว์จำนวนบนยอดแท่ง
            title="จำนวนโครงการในแต่ละปี"
        )

        # ปรับให้ legend อยู่ด้านล่างและชิดซ้าย
        fig.update_layout(
            height=450,
            margin=dict(l=20, r=20, t=50, b=100),
            legend=dict(
                title="",
                orientation="h",
                yanchor="bottom",
                y=-0.45,
                xanchor="left",
                x=0
            ),
            xaxis_title="ปีงบประมาณ",
            yaxis_title=None
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("ไม่มีข้อมูลที่จะแสดงในกราฟ")



# --- Excel Download ---
def to_excel_bytes(df_to_export):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_to_export.to_excel(writer, index=False)
    return output.getvalue()

col_up, spacer, col_dl = st.columns([2,3,1.5])

with col_dl:
    if not filtered_df.empty:
        st.markdown("📥 ดาวน์โหลดข้อมูลที่กรอง")
        st.download_button(
            label="💾 ดาวน์โหลดข้อมูลเป็น Excel",
            data=to_excel_bytes(filtered_df),
            file_name="filtered_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with spacer:
    st.write("")

with col_up:
    st.markdown("📤 อัปโหลด Excel เพื่อเพิ่มข้อมูล")
    uploaded_file = st.file_uploader("",type=["xlsx"])
    if uploaded_file:
        try:
            uploaded_df = pd.read_excel(uploaded_file)
            missing_cols = [col for col in required_columns if col not in uploaded_df.columns]
            if missing_cols:
                st.error(f"❌ คอลัมน์เหล่านี้หายไปจากไฟล์ที่อัปโหลด: {', '.join(missing_cols)}")
            else:
                supabase.table(TABLE_NAME).insert(uploaded_df.to_dict(orient="records")).execute()
                project_names = uploaded_df['โครงการ'].dropna().unique().tolist()
                sample_projects = ", ".join(project_names[:3])
                more_text = "..." if len(project_names) > 3 else ""
                st.success(f"✅ เพิ่มข้อมูล {len(uploaded_df)} แถวลงใน Supabase สำเร็จแล้ว")
                st.info(f"📌 โครงการที่เพิ่ม:\n{sample_projects}{more_text}")

                st.balloons()  # 🎈
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดขณะอ่านไฟล์: {e}")
