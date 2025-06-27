import streamlit as st
import pandas as pd
import re
from io import BytesIO
from supabase import create_client, Client

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Excel Filter App - Supabase", layout="wide")
st.title("📊 ข้อมูล - งบประมาณ ปี 2561-2568 จาก Supabase")

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

st.markdown("### 📄 ตารางข้อมูล")
# ลบคอลัมน์ไม่มีชื่อ
filtered_df = filtered_df.drop(columns=[col for col in filtered_df.columns if not col or "unnamed" in str(col).lower()], errors="ignore")

# แสดงเฉพาะคอลัมน์ที่ต้องการ
filtered_df = filtered_df[required_columns]

st.dataframe(filtered_df, use_container_width=True)


# --- Excel Download ---
def to_excel_bytes(df_to_export):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_to_export.to_excel(writer, index=False)
    return output.getvalue()

col_up, spacer, col_dl = st.columns([1,2,1])

with col_dl:
    if not filtered_df.empty:
        st.download_button(
            label="📥 ดาวน์โหลดข้อมูลที่กรองเป็น Excel",
            data=to_excel_bytes(filtered_df),
            file_name="filtered_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with spacer:
    st.write("")

with col_up:
    st.markdown("📤 อัปโหลด Excel เพื่อเพิ่มข้อมูล")
    uploaded_file = st.file_uploader("เลือกไฟล์ Excel", type=["xlsx"])
    if uploaded_file:
        try:
            uploaded_df = pd.read_excel(uploaded_file)
            missing_cols = [col for col in required_columns if col not in uploaded_df.columns]
            if missing_cols:
                st.error(f"❌ คอลัมน์เหล่านี้หายไปจากไฟล์ที่อัปโหลด: {', '.join(missing_cols)}")
            else:
                for _, row in uploaded_df.iterrows():
                    data = row.to_dict()
                    supabase.table(TABLE_NAME).insert(data).execute()
                st.success(f"✅ เพิ่มข้อมูล {len(uploaded_df)} แถวลงใน Supabase เรียบร้อยแล้ว")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดขณะอ่านไฟล์: {e}")
