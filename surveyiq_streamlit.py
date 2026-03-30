import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SurveyIQ – Phân tích khảo sát",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,700&display=swap');
  html, body, [class*="css"] { font-family: 'Satoshi', sans-serif; }
  h1,h2,h3 { font-family: 'Satoshi', sans-serif; }
  .metric-card {
    background: #f9f8f5;
    border: 1px solid #dcd9d5;
    border-radius: 10px;
    padding: 16px 20px;
  }
  .metric-val { font-size: 2rem; font-weight: 700; color: #01696f; }
  .metric-lbl { font-size: .75rem; text-transform: uppercase; color: #7a7974; letter-spacing:.06em; }
  .metric-sub { font-size: .8rem; color: #7a7974; margin-top:4px; }
  .insight-block {
    background: #edeae5;
    border-radius: 10px;
    padding: 16px;
    margin-top: 8px;
    border-left: 3px solid #01696f;
  }
  .insight-fact { font-size:.85rem; color:#28251d; }
  .insight-sowhat { font-size:.85rem; color:#01696f; font-weight:500; margin-top:8px; }
  .highlight-row { background:#cedcd8 !important; font-weight:600; }
  div[data-testid="stSidebarNav"] { display:none; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
COLORS = ["#01696f","#da7101","#d19900","#006494","#7a39bb","#a12c7b","#437a22","#4f98a3"]

def split_multi(val):
    """Split multi-select answers separated by ;|,"""
    if pd.isna(val): return []
    s = str(val).strip()
    if not s: return []
    for sep in [";","|",";"]:
        if sep in s:
            return [x.strip() for x in s.split(sep) if x.strip()]
    return [s]

def detect_type(series):
    """Heuristic: numeric / single / multiple / open"""
    non_null = series.dropna().astype(str).str.strip()
    non_null = non_null[non_null != ""]
    if non_null.empty: return "open"
    has_sep = non_null.str.contains(r"[;|]", regex=True).any()
    if has_sep: return "multiple"
    try:
        pd.to_numeric(non_null)
        return "numeric"
    except:
        pass
    n_unique = non_null.nunique()
    if n_unique <= 2: return "single"
    if n_unique <= 10: return "single"
    if n_unique > 30: return "open"
    return "multiple"

def freq_table(series):
    """Return frequency df for a column"""
    rows = []
    for v in series.dropna():
        for token in split_multi(v):
            rows.append(token)
    if not rows:
        return pd.DataFrame(columns=["Đáp án","Số lượng","Tỷ lệ %"])
    s = pd.Series(rows)
    counts = s.value_counts()
    total = len(series.dropna())
    df = pd.DataFrame({"Đáp án": counts.index, "Số lượng": counts.values})
    df["Tỷ lệ %"] = (df["Số lượng"] / total * 100).round(1)
    return df.reset_index(drop=True)

def highlight_top(df, threshold=30):
    def style_row(row):
        return ["background-color:#cedcd8;font-weight:600" if row["Tỷ lệ %"] >= threshold else "" for _ in row]
    return df.style.apply(style_row, axis=1)

# ── Session state ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "seg_col" not in st.session_state:
    st.session_state.seg_col = None
if "seg_map" not in st.session_state:
    st.session_state.seg_map = {}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 SurveyIQ")
    st.caption("Phân tích khảo sát khách hàng")
    st.divider()

    uploaded = st.file_uploader("Tải file dữ liệu", type=["csv","xlsx","xls"], label_visibility="collapsed")
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            else:
                df_raw = pd.read_excel(uploaded)
            st.session_state.df = df_raw
            st.success(f"✅ {uploaded.name}  ·  {len(df_raw):,} dòng")
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")

    st.divider()
    page = st.radio("Chuyển trang", [
        "🏠 Dashboard",
        "📋 Câu hỏi & Tần suất",
        "👥 Segment",
        "🔀 Cross-tab",
        "😣 Nỗi đau & Bận rộn",
        "🧑 Persona Builder",
        "💡 Auto Insights",
        "⚙️ Cấu hình Segment",
    ], label_visibility="collapsed")

df = st.session_state.df

# ── No data guard ─────────────────────────────────────────────────────────────
def no_data():
    st.info("👆 Tải file .xlsx hoặc .csv ở thanh bên trái để bắt đầu phân tích.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("Dashboard tổng quan")
    if df is None:
        no_data()
        st.stop()

    cols = df.columns.tolist()
    n_rows = len(df)
    n_cols = len(cols)

    # Count total distinct options
    total_opts = 0
    type_counts = {"single":0,"multiple":0,"open":0,"numeric":0}
    q_stats = []
    for col in cols:
        t = detect_type(df[col])
        type_counts[t] += 1
        ft = freq_table(df[col])
        top_row = ft.iloc[0] if not ft.empty else None
        q_stats.append({
            "col": col,
            "type": t,
            "n_options": len(ft),
            "top_answer": top_row["Đáp án"] if top_row is not None else "–",
            "top_pct": top_row["Tỷ lệ %"] if top_row is not None else 0
        })
        total_opts += len(ft)

    seg_count = len(st.session_state.seg_map)

    # KPIs
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("👥 Tổng respondents", f"{n_rows:,}", help="Số dòng dữ liệu hợp lệ")
    c2.metric("❓ Tổng câu hỏi", n_cols, help="Số cột trong file")
    c3.metric("🗂️ Tổng đáp án (unique)", total_opts, help="Tổng số đáp án phân biệt trên tất cả câu hỏi")
    c4.metric("🏷️ Segments", seg_count if seg_count else "Chưa cấu hình", help="Đến ⚙️ Cấu hình Segment để thiết lập")

    st.divider()
    cl, cr = st.columns([3,2])

    with cl:
        st.subheader("Phân bố loại câu hỏi")
        fig = px.pie(
            names=["Single choice","Multiple choice","Mở (text)","Numeric"],
            values=[type_counts["single"],type_counts["multiple"],type_counts["open"],type_counts["numeric"]],
            color_discrete_sequence=COLORS,
            hole=0.55,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=True, legend=dict(orientation="v",x=1,y=0.5), height=300, margin=dict(t=20,b=20,l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)

    with cr:
        st.subheader("Top 5 câu hỏi — đáp án dẫn đầu")
        top5 = sorted([q for q in q_stats if q["top_pct"]>0], key=lambda x:-x["top_pct"])[:5]
        for q in top5:
            col_short = q["col"][:40]+"…" if len(q["col"])>40 else q["col"]
            st.markdown(f"**{col_short}**")
            st.caption(f"→ _{q['top_answer'][:50]}_ — **{q['top_pct']:.1f}%**")

    st.divider()
    st.subheader("Auto Insight nhanh")
    strong = sorted([q for q in q_stats if q["top_pct"]>=60 and q["type"] in ["single","multiple"]], key=lambda x:-x["top_pct"])[:3]
    if not strong:
        st.info("Không tìm thấy câu hỏi có 1 đáp án chiếm ≥60%. Thử kiểm tra lại cấu trúc file.")
    else:
        for q in strong:
            with st.container():
                st.markdown(f"""<div class="insight-block">
                <div class="insight-fact">📌 <b>Fact:</b> {q["top_pct"]:.1f}% respondents chọn <em>"{q["top_answer"]}"</em> cho câu <em>"{q["col"][:60]}"</em></div>
                <div class="insight-sowhat">→ So what: Đây là ưu tiên/nỗi đau phổ biến nhất, cần được phản ánh trong định vị & thông điệp chính của sản phẩm/dịch vụ.</div>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CÂU HỎI & TẦN SUẤT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Câu hỏi & Tần suất":
    st.title("Câu hỏi & Tần suất đáp án")
    if df is None: no_data(); st.stop()

    col_selected = st.selectbox("Chọn câu hỏi", df.columns.tolist())
    threshold = st.slider("Highlight đáp án ≥ (%) ", 10, 80, 30)

    ft = freq_table(df[col_selected])
    if ft.empty:
        st.warning("Câu hỏi này không có đáp án nào được điền.")
        st.stop()

    c1, c2 = st.columns([3,2])
    with c1:
        st.subheader("Biểu đồ tần suất")
        fig = px.bar(
            ft.head(20), x="Tỷ lệ %", y="Đáp án",
            orientation="h", color="Tỷ lệ %",
            color_continuous_scale=["#dcd9d5","#01696f"],
            text="Tỷ lệ %",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, coloraxis_showscale=False,
                          height=max(300, len(ft.head(20))*36), margin=dict(l=0,r=20,t=20,b=20))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Bảng tần suất")
        styled = ft.style.apply(
            lambda row: ["background-color:#cedcd8;font-weight:600" if row["Tỷ lệ %"] >= threshold else "" for _ in row],
            axis=1
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption(f"Base n = {len(df[col_selected].dropna())} | Đáp án highlight ≥ {threshold}%")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SEGMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👥 Segment":
    st.title("Phân tích theo Segment")
    if df is None: no_data(); st.stop()
    if not st.session_state.seg_col or not st.session_state.seg_map:
        st.warning("Chưa cấu hình Segment. Vào ⚙️ Cấu hình Segment để thiết lập trước.")
        st.stop()

    seg_col = st.session_state.seg_col
    seg_map = st.session_state.seg_map

    def get_seg(row):
        v = str(row[seg_col]).strip()
        for seg, vals in seg_map.items():
            if v in vals: return seg
        return "Khác"

    df["_segment"] = df.apply(get_seg, axis=1)
    seg_names = [s for s in list(seg_map.keys())+["Khác"] if s in df["_segment"].unique()]

    q_selected = st.selectbox("Chọn câu hỏi để so sánh theo segment", [c for c in df.columns if c != "_segment"])
    threshold = st.slider("Highlight đáp án ≥ (%)", 10, 80, 30, key="seg_thresh")

    all_tokens = []
    for v in df[q_selected].dropna():
        all_tokens += split_multi(v)
    if not all_tokens:
        st.warning("Câu hỏi này không có dữ liệu.")
        st.stop()

    top_answers = pd.Series(all_tokens).value_counts().head(15).index.tolist()

    records = []
    for seg in seg_names:
        sub = df[df["_segment"]==seg]
        n = len(sub)
        for v in sub[q_selected].dropna():
            for tok in split_multi(v):
                if tok in top_answers:
                    records.append({"Segment":seg,"Đáp án":tok,"n_seg":n})

    if not records:
        st.info("Không có dữ liệu để so sánh."); st.stop()

    rec_df = pd.DataFrame(records)
    pivot = rec_df.groupby(["Segment","Đáp án"]).size().reset_index(name="count")
    seg_size = df.groupby("_segment").size().rename("n").reset_index().rename(columns={"_segment":"Segment"})
    pivot = pivot.merge(seg_size, on="Segment")
    pivot["Tỷ lệ %"] = (pivot["count"]/pivot["n"]*100).round(1)

    fig = px.bar(pivot, x="Đáp án", y="Tỷ lệ %", color="Segment",
                 barmode="group", color_discrete_sequence=COLORS,
                 text="Tỷ lệ %")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=420, margin=dict(l=0,r=0,t=20,b=60), xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Bảng so sánh chi tiết")
    pvt_wide = pivot.pivot_table(index="Đáp án", columns="Segment", values="Tỷ lệ %", aggfunc="first").fillna(0).reset_index()
    pvt_wide.columns.name = None

    def hl(row):
        styles=[]
        for v in row:
            try: styles.append("background-color:#cedcd8;font-weight:600" if float(v)>=threshold else "")
            except: styles.append("")
        return styles

    st.dataframe(pvt_wide.style.apply(hl, axis=1), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CROSS-TAB
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔀 Cross-tab":
    st.title("Cross-tab — chéo 2 câu hỏi")
    if df is None: no_data(); st.stop()

    cols_list = df.columns.tolist()
    col_row = st.selectbox("Câu hỏi hàng (Row)", cols_list, key="ct_row")
    col_col = st.selectbox("Câu hỏi cột (Column)", [c for c in cols_list if c!=col_row], key="ct_col")

    rows_tokens = df[col_row].dropna().apply(lambda x: split_multi(x))
    cols_tokens = df[col_col].dropna().apply(lambda x: split_multi(x))

    top_rows = pd.Series([t for ts in rows_tokens for t in ts]).value_counts().head(8).index.tolist()
    top_cols = pd.Series([t for ts in cols_tokens for t in ts]).value_counts().head(8).index.tolist()

    matrix = pd.DataFrame(0, index=top_rows, columns=top_cols)
    for i in df.index:
        rv = split_multi(df.loc[i,col_row]) if pd.notna(df.loc[i,col_row]) else []
        cv = split_multi(df.loc[i,col_col]) if pd.notna(df.loc[i,col_col]) else []
        for r in rv:
            for c in cv:
                if r in top_rows and c in top_cols:
                    matrix.loc[r,c] += 1

    n = len(df)
    matrix_pct = (matrix/n*100).round(1)

    fig = px.imshow(matrix_pct, text_auto=True, color_continuous_scale=["#f7f6f2","#01696f"],
                    labels=dict(x=col_col[:30], y=col_row[:30], color="Tỷ lệ %"), aspect="auto")
    fig.update_layout(height=400, margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Bảng số liệu (% trên tổng n)")
    st.dataframe(matrix_pct, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: NỖI ĐAU & BẬN RỘN
# ══════════════════════════════════════════════════════════════════════════════
elif page == "😣 Nỗi đau & Bận rộn":
    st.title("Nỗi đau & Bận rộn")
    if df is None: no_data(); st.stop()

    pain_cols = st.multiselect("Chọn các câu hỏi likert / rating đo nỗi đau", df.columns.tolist())
    if not pain_cols:
        st.info("Chọn 2–10 câu hỏi rating để vẽ biểu đồ so sánh."); st.stop()

    means = []
    for col in pain_cols:
        try:
            m = pd.to_numeric(df[col], errors="coerce").dropna().mean()
            means.append({"Câu hỏi": col[:50], "Mean": round(m,2)})
        except: pass

    if not means:
        st.warning("Không thể tính mean cho các câu này — kiểm tra lại đây có phải câu likert 1-5 không."); st.stop()

    mean_df = pd.DataFrame(means).sort_values("Mean", ascending=True)
    fig = px.bar(mean_df, x="Mean", y="Câu hỏi", orientation="h",
                 color="Mean", color_continuous_scale=["#dcd9d5","#da7101"],
                 text="Mean")
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(height=max(300, len(pain_cols)*50), coloraxis_showscale=False,
                      margin=dict(l=0,r=30,t=20,b=20))
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Câu hỏi có mean cao = nỗi đau thường xuyên hơn. Dùng kết quả này để ưu tiên thiết kế dịch vụ.")

    if st.session_state.seg_col and st.session_state.seg_map:
        seg_col = st.session_state.seg_col
        seg_map = st.session_state.seg_map
        def get_seg(row):
            v = str(row[seg_col]).strip()
            for seg, vals in seg_map.items():
                if v in vals: return seg
            return "Khác"
        df["_segment"] = df.apply(get_seg, axis=1)

        st.subheader("So sánh theo Segment")
        seg_means = []
        for seg in seg_map.keys():
            sub = df[df["_segment"]==seg]
            for col in pain_cols:
                m = pd.to_numeric(sub[col], errors="coerce").dropna().mean()
                if not np.isnan(m):
                    seg_means.append({"Segment":seg,"Câu hỏi":col[:45],"Mean":round(m,2)})
        if seg_means:
            sm_df = pd.DataFrame(seg_means)
            fig2 = px.bar(sm_df, x="Câu hỏi", y="Mean", color="Segment",
                          barmode="group", color_discrete_sequence=COLORS, text="Mean")
            fig2.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig2.update_layout(height=400, xaxis_tickangle=-30, margin=dict(l=0,r=0,t=20,b=80))
            st.plotly_chart(fig2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PERSONA BUILDER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧑 Persona Builder":
    st.title("Persona Builder")
    if df is None: no_data(); st.stop()
    if not st.session_state.seg_col or not st.session_state.seg_map:
        st.warning("Cần cấu hình Segment trước. Vào ⚙️ Cấu hình Segment."); st.stop()

    seg_col = st.session_state.seg_col
    seg_map = st.session_state.seg_map

    def get_seg(row):
        v = str(row[seg_col]).strip()
        for seg, vals in seg_map.items():
            if v in vals: return seg
        return "Khác"
    df["_segment"] = df.apply(get_seg, axis=1)

    persona_cols = st.multiselect("Chọn câu hỏi hình thành persona", df.columns.tolist(), max_selections=8)
    if not persona_cols:
        st.info("Chọn 3–8 câu hỏi để tổng hợp chân dung từng segment."); st.stop()

    for seg in list(seg_map.keys())+["Khác"]:
        sub = df[df["_segment"]==seg]
        if len(sub)==0: continue
        with st.expander(f"🏷️ {seg}  ·  n={len(sub)}", expanded=True):
            cs = st.columns(min(3, len(persona_cols)))
            for i, col in enumerate(persona_cols):
                ft = freq_table(sub[col])
                with cs[i % len(cs)]:
                    st.caption(col[:40])
                    if ft.empty:
                        st.write("–")
                    else:
                        top = ft.iloc[0]
                        st.markdown(f"**{top['Đáp án']}**  `{top['Tỷ lệ %']:.1f}%`")
                        for _, r in ft.iloc[1:3].iterrows():
                            st.markdown(f"<span style='color:#7a7974;font-size:.85rem'>{r['Đáp án']} · {r['Tỷ lệ %']:.1f}%</span>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AUTO INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Auto Insights":
    st.title("Auto Insights — Fact → Insight → So what")
    if df is None: no_data(); st.stop()

    threshold = st.slider("Ngưỡng % để báo cáo là insight", 20, 70, 40)
    top_n = st.slider("Số insight tối đa", 3, 20, 10)

    insights = []
    for col in df.columns:
        ft = freq_table(df[col])
        if ft.empty: continue
        top = ft.iloc[0]
        pct = top["Tỷ lệ %"]
        if pct >= threshold:
            itype = "Dominance" if pct >= 60 else "Concentration"
            insights.append({"col":col,"answer":top["Đáp án"],"pct":pct,"type":itype})

    insights = sorted(insights, key=lambda x:-x["pct"])[:top_n]

    if not insights:
        st.info("Không tìm thấy đáp án nào vượt ngưỡng đã chọn."); st.stop()

    for ins in insights:
        tag_color = "#01696f" if ins["type"]=="Dominance" else "#da7101"
        st.markdown(f"""<div class="insight-block" style="border-left-color:{tag_color}">
<span style="font-size:.7rem;text-transform:uppercase;color:{tag_color};font-weight:600">{ins['type']} · {ins['pct']:.1f}%</span><br>
<div class="insight-fact">📌 <b>Fact:</b> <b>{ins['pct']:.1f}%</b> respondents chọn <em>"{ins['answer']}"</em> cho câu hỏi <em>"{ins['col'][:70]}"</em></div>
<div class="insight-sowhat">→ So what: Đây là tín hiệu mạnh về ưu tiên/nỗi đau/hành vi phổ biến — cần được đưa vào chiến lược định vị, thiết kế dịch vụ hoặc thông điệp truyền thông.</div>
</div><br>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CẤU HÌNH SEGMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Cấu hình Segment":
    st.title("Cấu hình Segment")
    if df is None: no_data(); st.stop()

    st.markdown("Chọn câu hỏi phân loại và tick giá trị tương ứng với từng segment.")
    seg_col = st.selectbox("Câu hỏi phân loại (biến segment)", df.columns.tolist())
    st.session_state.seg_col = seg_col

    unique_vals = df[seg_col].dropna().astype(str).str.strip().unique().tolist()
    unique_vals = [v for v in unique_vals if v]

    st.markdown("**Gán giá trị cho từng segment** (có thể thêm nhiều segment):")
    n_segs = st.number_input("Số lượng segment", min_value=1, max_value=8, value=3)

    seg_map = {}
    for i in range(int(n_segs)):
        col1, col2 = st.columns([1,3])
        with col1:
            seg_name = st.text_input(f"Tên segment {i+1}", value=f"S{i+1}", key=f"seg_name_{i}")
        with col2:
            chosen = st.multiselect(f"Giá trị thuộc {seg_name}", unique_vals, key=f"seg_vals_{i}")
        if seg_name and chosen:
            seg_map[seg_name] = chosen

    if st.button("✅ Áp dụng cấu hình Segment", type="primary"):
        st.session_state.seg_map = seg_map
        st.success(f"Đã lưu {len(seg_map)} segment: {', '.join(seg_map.keys())}")
        if "_segment" in df.columns:
            df.drop(columns=["_segment"], inplace=True)
