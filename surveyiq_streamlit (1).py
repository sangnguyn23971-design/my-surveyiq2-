import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(
    page_title="SurveyIQ – Phân tích khảo sát",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html,[class*="css"]{font-family:'Segoe UI',sans-serif}
.kpi-box{background:#f9f8f5;border:1px solid #dcd9d5;border-radius:10px;padding:16px 20px;margin-bottom:4px}
.kpi-val{font-size:2rem;font-weight:700;color:#01696f;line-height:1.2}
.kpi-lbl{font-size:.72rem;text-transform:uppercase;color:#7a7974;letter-spacing:.07em}
.kpi-sub{font-size:.8rem;color:#7a7974;margin-top:4px}
.insight-box{background:#edeae5;border-left:4px solid #01696f;border-radius:8px;padding:14px 16px;margin:6px 0}
.ins-fact{font-size:.88rem;color:#28251d}
.ins-sw{font-size:.85rem;color:#01696f;font-weight:600;margin-top:6px}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
COLORS = ["#01696f","#da7101","#d19900","#006494","#7a39bb","#a12c7b","#437a22","#4f98a3"]

def split_val(v):
    if pd.isna(v): return []
    s = str(v).strip()
    if not s or s.lower() in ["nan","none"]: return []
    for sep in [";","|"]:
        if sep in s:
            return [x.strip() for x in s.split(sep) if x.strip()]
    return [s]

def detect_type(series):
    nn = series.dropna().astype(str).str.strip()
    nn = nn[nn.str.len()>0]
    if nn.empty: return "open"
    if nn.str.contains(r"[;|]", regex=True).any(): return "multiple"
    try:
        pd.to_numeric(nn)
        return "numeric"
    except: pass
    n_u = nn.nunique()
    if n_u <= 12: return "single"
    if n_u > 40: return "open"
    return "multiple"

def freq_table(series):
    tokens = []
    for v in series.dropna():
        tokens += split_val(v)
    if not tokens:
        return pd.DataFrame(columns=["Đáp án","Số lượng","Tỷ lệ %"])
    s = pd.Series(tokens)
    cnt = s.value_counts()
    base = len(series.dropna())
    df = pd.DataFrame({"Đáp án": cnt.index, "Số lượng": cnt.values})
    df["Tỷ lệ %"] = (df["Số lượng"] / base * 100).round(1)
    return df.reset_index(drop=True)

def highlight_30(df):
    def fn(row):
        bg = "background-color:#cedcd8;font-weight:600" if row["Tỷ lệ %"] >= 30 else ""
        return [bg]*len(row)
    return df.style.apply(fn, axis=1)

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [("df",None),("seg_col",None),("seg_map",{})]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 SurveyIQ")
    st.caption("Phân tích khảo sát khách hàng")
    st.divider()
    uploaded = st.file_uploader("Tải file .csv / .xlsx", type=["csv","xlsx","xls"])
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            else:
                df_raw = pd.read_excel(uploaded, engine="openpyxl")
            st.session_state.df = df_raw
            st.success(f"✅ {uploaded.name} · {len(df_raw):,} dòng")
        except Exception as e:
            st.error(f"Lỗi: {e}")
    st.divider()
    page = st.radio("Menu", [
        "🏠 Dashboard",
        "📋 Tần suất câu hỏi",
        "👥 So sánh Segment",
        "🔀 Cross-tab",
        "😣 Nỗi đau & Bận rộn",
        "🧑 Persona Builder",
        "💡 Auto Insights",
        "⚙️ Cấu hình Segment",
    ], label_visibility="collapsed")

df = st.session_state.df

def no_data():
    st.info("👆 Tải file .xlsx hoặc .csv ở thanh bên trái để bắt đầu.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("Dashboard tổng quan")
    if df is None: no_data()

    q_stats, total_opts = [], 0
    type_cnt = dict(single=0, multiple=0, open=0, numeric=0)
    for col in df.columns:
        t = detect_type(df[col])
        type_cnt[t] += 1
        ft = freq_table(df[col])
        total_opts += len(ft)
        top = ft.iloc[0] if not ft.empty else None
        q_stats.append({
            "col": col, "type": t,
            "top": top["Đáp án"] if top is not None else "–",
            "pct": top["Tỷ lệ %"] if top is not None else 0,
        })

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("👥 Respondents", f"{len(df):,}")
    c2.metric("❓ Câu hỏi", len(df.columns))
    c3.metric("🗂️ Đáp án unique", total_opts)
    c4.metric("🏷️ Segments", len(st.session_state.seg_map) or "Chưa cấu hình")

    st.divider()
    cl, cr = st.columns([3,2])

    with cl:
        st.subheader("Phân bố loại câu hỏi")
        type_df = pd.DataFrame({
            "Loại": ["Single","Multiple","Mở","Numeric"],
            "Số lượng": [type_cnt["single"],type_cnt["multiple"],type_cnt["open"],type_cnt["numeric"]],
        })
        chart = alt.Chart(type_df).mark_arc(innerRadius=60).encode(
            theta=alt.Theta("Số lượng:Q"),
            color=alt.Color("Loại:N", scale=alt.Scale(range=COLORS)),
            tooltip=["Loại","Số lượng"]
        ).properties(height=260)
        st.altair_chart(chart, use_container_width=True)

    with cr:
        st.subheader("Top 5 câu hỏi nổi bật")
        top5 = sorted([q for q in q_stats if q["pct"]>0], key=lambda x:-x["pct"])[:5]
        for q in top5:
            lbl = q["col"][:45]+"…" if len(q["col"])>45 else q["col"]
            st.markdown(f"**{lbl}**")
            st.caption(f"→ _{q['top'][:50]}_ · **{q['pct']:.1f}%**")

    st.divider()
    st.subheader("Auto Insight nhanh")
    strong = sorted([q for q in q_stats if q["pct"]>=55], key=lambda x:-x["pct"])[:4]
    if not strong:
        st.info("Không tìm thấy đáp án chiếm ≥55%. Thử upload file có câu hỏi lựa chọn đơn.")
    for q in strong:
        st.markdown(f"""<div class="insight-box">
<div class="ins-fact">📌 <b>Fact:</b> <b>{q['pct']:.1f}%</b> chọn <em>"{q['top']}"</em> cho <em>"{q['col'][:65]}"</em></div>
<div class="ins-sw">→ So what: Đây là ưu tiên/ nỗi đau phổ biến nhất — cần đưa vào định vị & thông điệp chính.</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TẦN SUẤT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Tần suất câu hỏi":
    st.title("Tần suất đáp án theo câu hỏi")
    if df is None: no_data()

    col_sel = st.selectbox("Chọn câu hỏi", df.columns.tolist())
    thresh = st.slider("Highlight đáp án ≥ (%)", 10, 80, 30)
    ft = freq_table(df[col_sel])
    if ft.empty:
        st.warning("Câu hỏi này không có dữ liệu.")
        st.stop()

    cl, cr = st.columns([3,2])
    with cl:
        chart = alt.Chart(ft.head(20)).mark_bar(color="#01696f").encode(
            x=alt.X("Tỷ lệ %:Q", title="Tỷ lệ %"),
            y=alt.Y("Đáp án:N", sort="-x", title=""),
            tooltip=["Đáp án","Số lượng","Tỷ lệ %"],
            color=alt.condition(
                alt.datum["Tỷ lệ %"] >= thresh,
                alt.value("#da7101"), alt.value("#01696f")
            )
        ).properties(height=max(300, len(ft.head(20))*34))
        st.altair_chart(chart, use_container_width=True)
    with cr:
        st.dataframe(highlight_30(ft), use_container_width=True, hide_index=True)
    st.caption(f"Base n = {len(df[col_sel].dropna())} | Màu cam = đáp án ≥ {thresh}%")

# ══════════════════════════════════════════════════════════════════════════════
# SEGMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👥 So sánh Segment":
    st.title("So sánh đáp án theo Segment")
    if df is None: no_data()
    if not st.session_state.seg_col or not st.session_state.seg_map:
        st.warning("Vào ⚙️ Cấu hình Segment trước.")
        st.stop()

    seg_col = st.session_state.seg_col
    seg_map = st.session_state.seg_map

    def get_seg(row):
        v = str(row[seg_col]).strip()
        for s,vals in seg_map.items():
            if v in vals: return s
        return "Khác"

    df["_seg"] = df.apply(get_seg, axis=1)
    q_sel = st.selectbox("Chọn câu hỏi", [c for c in df.columns if c!="_seg"])
    thresh = st.slider("Highlight ≥ (%)", 10, 80, 30, key="s2")

    top_opts = freq_table(df[q_sel]).head(12)["Đáp án"].tolist()
    records = []
    for seg in list(seg_map.keys())+["Khác"]:
        sub = df[df["_seg"]==seg]
        n = max(len(sub), 1)
        for v in sub[q_sel].dropna():
            for tok in split_val(v):
                if tok in top_opts:
                    records.append({"Segment":seg,"Đáp án":tok,"n":n})

    if not records:
        st.info("Không có dữ liệu để so sánh."); st.stop()

    rec_df = pd.DataFrame(records)
    grp = rec_df.groupby(["Segment","Đáp án","n"]).size().reset_index(name="count")
    grp["Tỷ lệ %"] = (grp["count"]/grp["n"]*100).round(1)

    chart = alt.Chart(grp).mark_bar().encode(
        x=alt.X("Đáp án:N", title=""),
        y=alt.Y("Tỷ lệ %:Q"),
        color=alt.Color("Segment:N", scale=alt.Scale(range=COLORS)),
        xOffset="Segment:N",
        tooltip=["Segment","Đáp án","Tỷ lệ %"]
    ).properties(height=380)
    st.altair_chart(chart, use_container_width=True)

    pvt = grp.pivot_table(index="Đáp án", columns="Segment", values="Tỷ lệ %", aggfunc="first").fillna(0).reset_index()
    pvt.columns.name = None
    st.dataframe(pvt, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# CROSS-TAB
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔀 Cross-tab":
    st.title("Cross-tab — chéo 2 câu hỏi")
    if df is None: no_data()

    cols = df.columns.tolist()
    c1,c2 = st.columns(2)
    col_r = c1.selectbox("Câu hỏi hàng", cols, key="ctr")
    col_c = c2.selectbox("Câu hỏi cột", [c for c in cols if c!=col_r], key="ctc")

    top_r = freq_table(df[col_r]).head(8)["Đáp án"].tolist()
    top_c = freq_table(df[col_c]).head(8)["Đáp án"].tolist()

    mat = pd.DataFrame(0, index=top_r, columns=top_c)
    for i in df.index:
        rv = split_val(df.loc[i,col_r])
        cv = split_val(df.loc[i,col_c])
        for r in rv:
            for c in cv:
                if r in top_r and c in top_c:
                    mat.loc[r,c] += 1

    mat_pct = (mat/len(df)*100).round(1)
    mat_long = mat_pct.reset_index().melt(id_vars="index", var_name=col_c, value_name="Tỷ lệ %")
    mat_long = mat_long.rename(columns={"index": col_r})

    heat = alt.Chart(mat_long).mark_rect().encode(
        x=alt.X(f"{col_c}:N", title=col_c[:30]),
        y=alt.Y(f"{col_r}:N", title=col_r[:30]),
        color=alt.Color("Tỷ lệ %:Q", scale=alt.Scale(scheme="tealblues")),
        tooltip=[col_r, col_c, "Tỷ lệ %"]
    ).properties(height=360)
    text = heat.mark_text(baseline="middle").encode(
        text=alt.Text("Tỷ lệ %:Q", format=".1f"),
        color=alt.value("white")
    )
    st.altair_chart(heat+text, use_container_width=True)
    st.dataframe(mat_pct, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# NỖI ĐAU
# ══════════════════════════════════════════════════════════════════════════════
elif page == "😣 Nỗi đau & Bận rộn":
    st.title("Nỗi đau & Bận rộn (Likert rating)")
    if df is None: no_data()

    pain_cols = st.multiselect("Chọn câu hỏi rating (1–5)", df.columns.tolist())
    if not pain_cols:
        st.info("Chọn 2–10 câu rating để vẽ biểu đồ."); st.stop()

    rows = []
    for col in pain_cols:
        m = pd.to_numeric(df[col], errors="coerce").dropna().mean()
        if not np.isnan(m):
            rows.append({"Câu hỏi": col[:50], "Mean": round(m,2)})

    if not rows:
        st.warning("Không tính được mean. Kiểm tra lại cột có phải kiểu số 1-5 không."); st.stop()

    md = pd.DataFrame(rows).sort_values("Mean", ascending=False)
    chart = alt.Chart(md).mark_bar().encode(
        x=alt.X("Mean:Q", scale=alt.Scale(domain=[0,5])),
        y=alt.Y("Câu hỏi:N", sort="-x"),
        color=alt.Color("Mean:Q", scale=alt.Scale(scheme="oranges")),
        tooltip=["Câu hỏi","Mean"]
    ).properties(height=max(300, len(pain_cols)*44))
    st.altair_chart(chart, use_container_width=True)
    st.caption("Mean cao = nỗi đau thường xuyên hơn (thang 1–5)")

    if st.session_state.seg_col and st.session_state.seg_map:
        seg_col = st.session_state.seg_col
        seg_map = st.session_state.seg_map
        def get_seg(row):
            v = str(row[seg_col]).strip()
            for s,vals in seg_map.items():
                if v in vals: return s
            return "Khác"
        df["_seg"] = df.apply(get_seg, axis=1)
        st.subheader("So sánh theo Segment")
        segs = []
        for seg in list(seg_map.keys())+["Khác"]:
            sub = df[df["_seg"]==seg]
            for col in pain_cols:
                m = pd.to_numeric(sub[col], errors="coerce").dropna().mean()
                if not np.isnan(m):
                    segs.append({"Segment":seg,"Câu hỏi":col[:40],"Mean":round(m,2)})
        if segs:
            sd = pd.DataFrame(segs)
            c2 = alt.Chart(sd).mark_bar().encode(
                x=alt.X("Câu hỏi:N", title=""),
                y=alt.Y("Mean:Q"),
                color=alt.Color("Segment:N", scale=alt.Scale(range=COLORS)),
                xOffset="Segment:N",
                tooltip=["Segment","Câu hỏi","Mean"]
            ).properties(height=380)
            st.altair_chart(c2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PERSONA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧑 Persona Builder":
    st.title("Persona Builder")
    if df is None: no_data()
    if not st.session_state.seg_col or not st.session_state.seg_map:
        st.warning("Cần cấu hình Segment trước."); st.stop()

    seg_col = st.session_state.seg_col
    seg_map = st.session_state.seg_map
    def get_seg(row):
        v = str(row[seg_col]).strip()
        for s,vals in seg_map.items():
            if v in vals: return s
        return "Khác"
    df["_seg"] = df.apply(get_seg, axis=1)

    p_cols = st.multiselect("Chọn câu hỏi hình thành persona (3–8 câu)", df.columns.tolist(), max_selections=8)
    if not p_cols:
        st.info("Chọn câu hỏi để xây dựng chân dung từng segment."); st.stop()

    for seg in list(seg_map.keys())+["Khác"]:
        sub = df[df["_seg"]==seg]
        if len(sub)==0: continue
        with st.expander(f"🏷️ {seg}  ·  n={len(sub)}", expanded=True):
            cs = st.columns(min(3,len(p_cols)))
            for i, col in enumerate(p_cols):
                ft = freq_table(sub[col])
                with cs[i%len(cs)]:
                    st.caption(f"**{col[:38]}**")
                    if ft.empty:
                        st.write("–")
                    else:
                        top = ft.iloc[0]
                        st.markdown(f"**{top['Đáp án']}** `{top['Tỷ lệ %']:.1f}%`")
                        for _, r in ft.iloc[1:3].iterrows():
                            st.markdown(f"<span style='color:#7a7974;font-size:.82rem'>{r['Đáp án']} · {r['Tỷ lệ %']:.1f}%</span>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Auto Insights":
    st.title("Auto Insights — Fact → Insight → So what")
    if df is None: no_data()

    thresh = st.slider("Ngưỡng % để coi là insight", 20, 70, 40)
    top_n = st.slider("Số insight hiển thị", 3, 20, 10)

    insights = []
    for col in df.columns:
        ft = freq_table(df[col])
        if ft.empty: continue
        top = ft.iloc[0]
        if top["Tỷ lệ %"] >= thresh:
            insights.append({
                "col": col, "ans": top["Đáp án"],
                "pct": top["Tỷ lệ %"],
                "type": "Dominance" if top["Tỷ lệ %"]>=60 else "Concentration"
            })

    insights = sorted(insights, key=lambda x:-x["pct"])[:top_n]
    if not insights:
        st.info("Không tìm thấy đáp án nào vượt ngưỡng."); st.stop()

    for ins in insights:
        clr = "#01696f" if ins["type"]=="Dominance" else "#da7101"
        st.markdown(f"""<div class="insight-box" style="border-left-color:{clr}">
<span style="font-size:.7rem;text-transform:uppercase;color:{clr};font-weight:600">{ins['type']} · {ins['pct']:.1f}%</span><br>
<div class="ins-fact">📌 <b>Fact:</b> <b>{ins['pct']:.1f}%</b> chọn <em>"{ins['ans']}"</em> cho <em>"{ins['col'][:65]}"</em></div>
<div class="ins-sw">→ So what: Ưu tiên/nỗi đau phổ biến nhất — đưa vào chiến lược định vị & thông điệp chính.</div>
</div><br>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CẤU HÌNH SEGMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Cấu hình Segment":
    st.title("Cấu hình Segment")
    if df is None: no_data()

    seg_col = st.selectbox("Câu hỏi phân loại (biến segment)", df.columns.tolist())
    st.session_state.seg_col = seg_col
    unique_vals = df[seg_col].dropna().astype(str).str.strip().unique().tolist()

    n_segs = st.number_input("Số segment", 1, 8, 3)
    seg_map = {}
    for i in range(int(n_segs)):
        c1,c2 = st.columns([1,3])
        name = c1.text_input(f"Tên #{i+1}", value=f"S{i+1}", key=f"sn{i}")
        vals = c2.multiselect(f"Giá trị {name}", unique_vals, key=f"sv{i}")
        if name and vals:
            seg_map[name] = vals

    if st.button("✅ Lưu cấu hình", type="primary"):
        st.session_state.seg_map = seg_map
        st.success(f"Đã lưu {len(seg_map)} segment: {', '.join(seg_map.keys())}")
