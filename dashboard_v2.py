"""
dashboard_v2.py — Dashboard Streamlit · App V2
Port Autonome d'Abidjan · Approche NT + Transbordé séparés
===========================================================
Marchandises : modèles NT (Holt simple) + Transbordé (cst) séparés
Escales      : identique App V1
Conteneurs   : identique App V1
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pickle
import sys
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# 0. CONFIG PAGE
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Port d'Abidjan — Prévisions V2",
    page_icon="🚢", layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# 1. CSS
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
section[data-testid="stSidebar"]{background:#1a1a18;}
section[data-testid="stSidebar"] *{color:#e0dfd6 !important;}
section[data-testid="stSidebar"] .stRadio label{
    background:rgba(255,255,255,0.08);border-radius:6px;
    padding:4px 10px;margin:2px 0;display:block;font-size:0.88rem;}
section[data-testid="stSidebar"] .stRadio label:hover{
    background:rgba(255,255,255,0.15);}
section[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.2);}
.kpi{background:#f8f8f6;border-radius:10px;padding:14px 16px;
     text-align:center;margin-bottom:4px;}
.kpi-label{font-size:11px;color:#73726c;margin-bottom:4px;}
.kpi-value{font-size:22px;font-weight:500;color:#2c2c2a;}
.kpi-sub{font-size:11px;color:#888780;margin-top:2px;}
.warn{background:#faeeda;border-left:3px solid #BA7517;padding:8px 12px;
      border-radius:4px;font-size:12px;color:#633806;margin:6px 0;}
.badge{display:inline-block;padding:3px 10px;border-radius:6px;
       font-size:11px;font-weight:500;margin-bottom:6px;}
.badge-nt{background:rgba(29,158,117,0.12);color:#085041;}
.badge-tr{background:rgba(200,126,26,0.12);color:#7A4A00;}
.badge-tot{background:rgba(21,99,160,0.12);color:#0C447C;}
.badge-td{background:rgba(29,158,117,0.12);color:#085041;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# 2. CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────────────────────────────
@st.cache_resource
def load_all():
    # Marchandises V2
    with open("forecasts_v2.pkl","rb") as f:
        fc_v2 = pickle.load(f)
    forecasts_v2 = fc_v2["forecasts"]
    meta_v2      = fc_v2["meta"]
    with open("series_v2.pkl","rb") as f:
        series_v2 = pickle.load(f)

    # Escales (app1)
    with open("forecasts_escales.pkl","rb") as f:
        esc_raw = pickle.load(f)
    fc_esc  = esc_raw["forecasts"]
    mdl_esc = esc_raw["meta"]
    with open("series_escales.pkl","rb") as f:
        ser_esc = pickle.load(f)

    # Conteneurs (app1)
    with open("forecasts_conteneurs_v2.pkl","rb") as f:
        cnt_raw = pickle.load(f)
    fc_cnt  = cnt_raw["forecasts"]
    mdl_cnt = cnt_raw["meta"]
    with open("series_conteneurs_v2.pkl","rb") as f:
        ser_cnt = pickle.load(f)

    return forecasts_v2, meta_v2, series_v2, fc_esc, mdl_esc, ser_esc, fc_cnt, mdl_cnt, ser_cnt

try:
    forecasts_v2, meta_v2, series_v2, \
    fc_esc, mdl_esc, ser_esc, \
    fc_cnt, mdl_cnt, ser_cnt = load_all()
except Exception as e:
    st.error(f"Erreur chargement : {e}")
    st.stop()

ANNEE_DEBUT    = meta_v2["annee_debut"]
ANNEE_FIN      = meta_v2["annee_fin"]
ANNEE_MIN_FC   = ANNEE_FIN + 1
ANNEE_MAX_FC   = meta_v2["annee_max"]
NOMS_M         = meta_v2["noms_mois"]
SEGS_NT        = meta_v2["segs_nt"]
AXES_NT        = meta_v2["axes_nt"]

AXES_LABEL = {
    "sens"             : "Sens (Import / Export)",
    "composante"       : "Composante (March.gén / Pétr / Pêche)",
    "conteneurisation" : "Conteneurisation (Cont. / Non cont.)",
}

# ─────────────────────────────────────────────────────────────────
# 3. HELPERS
# ─────────────────────────────────────────────────────────────────
def kpi(col, label, value, sub=""):
    col.markdown(f"""<div class="kpi">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def plo(fig, title="", h=380):
    fig.update_layout(height=h, margin=dict(l=10,r=10,t=30,b=10),
                      title=title, title_font_size=13,
                      legend=dict(orientation="h",y=-0.15),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor="#E8EFF6")
    fig.update_yaxes(showgrid=True, gridcolor="#E8EFF6")
    st.plotly_chart(fig, use_container_width=True)

def badge(txt, cls):
    st.markdown(f'<span class="badge {cls}">{txt}</span>', unsafe_allow_html=True)

def ann_hist(seg, yr):
    s = series_v2.get(seg)
    if s is None: return 0
    return float(s[s.index.year==yr].sum())

def cnt_total_dyn(yr, cle=None):
    """Calcule le Total conteneurs dynamiquement via ratio NT × ratio[cle]."""
    if yr <= mdl_cnt["annee_fin"] if mdl_cnt else 2025:
        return mdl_cnt["ann_total"][yr] if mdl_cnt else 0
    fc = fc_cnt.get(yr, {})
    nt_ann = fc.get("annuel_nt", fc.get("annuel", 0))
    if nt_ann == 0: return fc.get("annuel", 0)
    ratio_map = mdl_cnt.get("ratio_tot_nt", {}) if mdl_cnt else {}
    cle_ref = cle or (mdl_cnt["annee_fin"] if mdl_cnt else 2025)
    r = ratio_map.get(cle_ref, ratio_map.get(
        mdl_cnt["annee_fin"] if mdl_cnt else 2025, 1.4398))
    return int(round(nt_ann * r))

def ann_fc(yr, key):
    return forecasts_v2.get(yr, {}).get(key, 0)

# ─────────────────────────────────────────────────────────────────
# 4. INITIALISATION SESSION STATE (clés persistantes)
# ─────────────────────────────────────────────────────────────────
if "cle_march_v2" not in st.session_state:
    st.session_state["cle_march_v2"] = ANNEE_FIN
if "cle_esc_v2" not in st.session_state:
    st.session_state["cle_esc_v2"] = ANNEE_FIN
if "cle_cnt_v2" not in st.session_state:
    st.session_state["cle_cnt_v2"] = ANNEE_FIN

# ─────────────────────────────────────────────────────────────────
# 5. SIDEBAR
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # ── LOGO + TITRE ─────────────────────────────────────────────
    try:
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.image("logo_PAA.jpg", use_container_width=True)
    except Exception:
        pass
    st.markdown(
        "<div style='text-align:center;font-weight:700;font-size:15px;"
        "color:#e0dfd6;margin-top:4px;'>Port Autonome d'Abidjan</div>"
        "<div style='text-align:center;color:#a0a098;font-size:11px;"
        "margin-top:2px;'>Prévisions de trafic · V2</div>"
        "<div style='text-align:center;color:#888780;font-size:10px;"
        "margin-bottom:4px;font-style:italic;'>NT + Transbordé séparés</div>",
        unsafe_allow_html=True)
    st.markdown("---")

    module = st.radio("", [
        "📦 Marchses", "🚢 Escales", "📦 Conteneurs"
    ], label_visibility="collapsed", key="module_v2",
       horizontal=True)

    st.markdown("---")

    # Valeurs par défaut clés
    cle_march = st.session_state.get("cle_march_v2_val", ANNEE_FIN) or ANNEE_FIN
    cle_esc   = st.session_state.get("cle_esc_v2_val",   ANNEE_FIN) or ANNEE_FIN
    cle_cnt   = st.session_state.get("cle_cnt_v2_val",   ANNEE_FIN) or ANNEE_FIN

    # ── Marchandises ─────────────────────────────────────────────
    if module == "📦 Marchses":
        page = st.radio("", [
            "KPIs globaux",
            "Analyse historique",
            "Prévisions court terme",
            "Prévisions long terme",
            "Analyse par axe NT",
        ], label_visibility="collapsed", key="page_march_v2")

        st.markdown("---")
        st.markdown("**Clé de répartition NT**")
        annees_m = list(range(ANNEE_FIN, ANNEE_DEBUT-1, -1))
        if "cle_march_v2_val" not in st.session_state:
            st.session_state["cle_march_v2_val"] = ANNEE_FIN
        def _save_m(): st.session_state["cle_march_v2_val"] = st.session_state["cle_march_v2_sel"]
        idx_m = annees_m.index(st.session_state["cle_march_v2_val"]) \
                if st.session_state["cle_march_v2_val"] in annees_m else 0
        st.selectbox("Année de référence NT", annees_m,
                     index=idx_m, key="cle_march_v2_sel",
                     on_change=_save_m,
                     help="Clé pour ventiler le Non transbordé entre axes. Par défaut N-1.")
        cle_march = st.session_state["cle_march_v2_val"]
        if cle_march != ANNEE_FIN:
            st.caption(f"⚠️ Clé {cle_march} au lieu de {ANNEE_FIN} (N-1)")

    # ── Escales ──────────────────────────────────────────────────
    elif module == "🚢 Escales":
        page = st.radio("", [
            "Escales — KPIs",
            "Escales — Historique",
            "Escales — Prévisions CT",
            "Escales — Prévisions LT",
            "Escales — Par terminal",
        ], label_visibility="collapsed", key="page_esc_v2")

        st.markdown("---")
        st.markdown("**Clé de répartition**")
        if mdl_esc:
            annees_e = list(range(mdl_esc["annee_fin"], mdl_esc["annee_debut"]-1, -1))
        else:
            annees_e = [ANNEE_FIN]
        if "cle_esc_v2_val" not in st.session_state:
            st.session_state["cle_esc_v2_val"] = annees_e[0]
        def _save_e(): st.session_state["cle_esc_v2_val"] = st.session_state["cle_esc_v2_sel"]
        idx_e = annees_e.index(st.session_state["cle_esc_v2_val"]) \
                if st.session_state["cle_esc_v2_val"] in annees_e else 0
        st.selectbox("Année de référence", annees_e,
                     index=idx_e, key="cle_esc_v2_sel",
                     on_change=_save_e,
                     help="Clé pour ventiler entre terminaux. Par défaut N-1.")
        cle_esc = st.session_state["cle_esc_v2_val"]
        if cle_esc != annees_e[0]:
            st.caption(f"⚠️ Clé {cle_esc} au lieu de {annees_e[0]} (N-1)")

    # ── Conteneurs ───────────────────────────────────────────────
    else:
        page = st.radio("", [
            "Conteneurs — KPIs",
            "Conteneurs — Historique",
            "Conteneurs — Prévisions CT",
            "Conteneurs — Prévisions LT",
            "Conteneurs — Par segment",
        ], label_visibility="collapsed", key="page_cnt_v2")

        st.markdown("---")
        st.markdown("**Clé de répartition**")
        if mdl_cnt:
            annees_c = list(range(mdl_cnt["annee_fin"], mdl_cnt["annee_debut"]-1, -1))
        else:
            annees_c = [ANNEE_FIN]
        if "cle_cnt_v2_val" not in st.session_state:
            st.session_state["cle_cnt_v2_val"] = annees_c[0]
        def _save_c(): st.session_state["cle_cnt_v2_val"] = st.session_state["cle_cnt_v2_sel"]
        idx_c = annees_c.index(st.session_state["cle_cnt_v2_val"]) \
                if st.session_state["cle_cnt_v2_val"] in annees_c else 0
        st.selectbox("Année de référence", annees_c,
                     index=idx_c, key="cle_cnt_v2_sel",
                     on_change=_save_c,
                     help="Clé pour ventiler entre terminaux. Par défaut N-1.")
        cle_cnt = st.session_state["cle_cnt_v2_val"]
        if cle_cnt != annees_c[0]:
            st.caption(f"⚠️ Clé {cle_cnt} au lieu de {annees_c[0]} (N-1)")

    # ── Horizon + exports ────────────────────────────────────────
    st.markdown("---")
    horizon = st.slider("Horizon (ans)", 1, 15, 5, key="horizon_v2")
    annee_cible = ANNEE_MIN_FC + horizon - 1

    st.markdown("---")
    st.markdown("**Exports Excel**")
    try:
        from generate_tableau_v2 import generate_xlsx_lt_v2, generate_xlsx_ct_v2
        cle_m = st.session_state.get("cle_march_v2_val", ANNEE_FIN) or ANNEE_FIN
        cle_e = st.session_state.get("cle_esc_v2_val",   ANNEE_FIN) or ANNEE_FIN
        cle_c = st.session_state.get("cle_cnt_v2_val",   ANNEE_FIN) or ANNEE_FIN

        buf_lt = generate_xlsx_lt_v2(
            forecasts_v2=forecasts_v2, meta_v2=meta_v2, series_v2=series_v2,
            fc_esc=fc_esc, mdl_esc=mdl_esc,
            fc_cnt=fc_cnt, mdl_cnt=mdl_cnt,
            annee_max_data=ANNEE_FIN, annee_min_fc=ANNEE_MIN_FC,
            horizon=horizon, cle_march=cle_m, cle_esc=cle_e, cle_cnt=cle_c)
        lbl_lt = f"📥 Long terme ({ANNEE_MIN_FC}–{annee_cible})"
        if cle_m!=ANNEE_FIN or cle_e!=ANNEE_FIN or cle_c!=ANNEE_FIN:
            lbl_lt += " ⚙️"
        st.download_button(lbl_lt, buf_lt,
            file_name=f"PAA_V2_LT_{ANNEE_MIN_FC}_{annee_cible}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)

        buf_ct = generate_xlsx_ct_v2(
            forecasts_v2=forecasts_v2, meta_v2=meta_v2, series_v2=series_v2,
            fc_esc=fc_esc, mdl_esc=mdl_esc,
            fc_cnt=fc_cnt, mdl_cnt=mdl_cnt,
            annee_max_data=ANNEE_FIN, annee_fc=ANNEE_MIN_FC,
            cle_march=cle_m, cle_esc=cle_e, cle_cnt=cle_c)
        lbl_ct = f"📥 Court terme ({ANNEE_MIN_FC})"
        if cle_m!=ANNEE_FIN or cle_e!=ANNEE_FIN or cle_c!=ANNEE_FIN:
            lbl_ct += " ⚙️"
        st.download_button(lbl_ct, buf_ct,
            file_name=f"PAA_V2_CT_{ANNEE_MIN_FC}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    except Exception as ex:
        st.warning(f"Exports indisponibles : {ex}")

# ─────────────────────────────────────────────────────────────────
# 6. PAGES MARCHANDISES V2
# ─────────────────────────────────────────────────────────────────
COULEURS = {"NT":"#1563A0","Transb":"#C87E1A","Total":"#0D2B45"}

if module == "📦 Marchses":

    yrs_hist = list(range(ANNEE_DEBUT, ANNEE_FIN+1))
    yrs_fc   = list(range(ANNEE_MIN_FC, annee_cible+1))

    nt_hist  = [ann_hist("NT",yr) for yr in yrs_hist]
    tr_hist  = [ann_hist("Transbordement",yr) for yr in yrs_hist]
    tot_hist = [nt+tr for nt,tr in zip(nt_hist,tr_hist)]

    nt_fc    = [ann_fc(yr,"annuel_nt")  for yr in yrs_fc]
    tr_fc    = [ann_fc(yr,"annuel_tr")  for yr in yrs_fc]
    tot_fc   = [ann_fc(yr,"annuel_tot") for yr in yrs_fc]

    # ── KPIs ─────────────────────────────────────────────────────
    if page == "KPIs globaux":
        st.markdown(f"## 📦 Marchandises V2 — KPIs · {ANNEE_FIN}")
        badge("Non transbordé — SARIMA(1,0,0)(0,1,0)12", "badge-nt")
        badge("Transbordé — Moyenne 2024-2025", "badge-tr")
        badge(f"Total = NT + Transb.", "badge-tot")

        c1,c2,c3 = st.columns(3)
        kpi(c1,"Non transbordé 2025",f"{nt_hist[-1]:.3f} Mt",
            f"National + Transit")
        kpi(c2,"Transbordé 2025",f"{tr_hist[-1]:.3f} Mt",
            f"Moyenne 2024-2025 = {meta_v2['transb_moy']:.3f} Mt/an")
        kpi(c3,"Total 2025",f"{tot_hist[-1]:.3f} Mt",
            "NT + Transbordé")

        st.markdown("---")
        c4,c5,c6 = st.columns(3)
        nt26 = ann_fc(ANNEE_MIN_FC,"annuel_nt")
        tr26 = ann_fc(ANNEE_MIN_FC,"annuel_tr")
        tot26 = ann_fc(ANNEE_MIN_FC,"annuel_tot")
        lo26  = ann_fc(ANNEE_MIN_FC,"ic_lo_nt")
        hi26  = ann_fc(ANNEE_MIN_FC,"ic_hi_nt")
        kpi(c4,f"NT prévu {ANNEE_MIN_FC}",f"{nt26:.3f} Mt",
            f"SARIMA · WMAPE={meta_v2['wmape_nt']:.1f}%  IC95%: [{lo26:.2f} – {hi26:.2f}]")
        kpi(c5,f"Transbordé prévu {ANNEE_MIN_FC}",f"{tr26:.3f} Mt",
            "Constante (moy. 2024-2025)")
        kpi(c6,f"Total prévu {ANNEE_MIN_FC}",f"{tot26:.3f} Mt",
            f"+{(tot26/tot_hist[-1]-1)*100:.1f}% vs {ANNEE_FIN}")

        st.markdown("---")
        st.markdown("#### Évolution 2015–2025")
        fig = go.Figure()
        fig.add_bar(x=yrs_hist, y=nt_hist, name="Non transbordé",
                    marker_color=COULEURS["NT"], opacity=0.85)
        fig.add_bar(x=yrs_hist, y=tr_hist, name="Transbordé",
                    marker_color=COULEURS["Transb"], opacity=0.85)
        fig.update_layout(barmode="stack")
        plo(fig,"Marchandises : NT vs Transbordé (Mt)")

    # ── Historique ───────────────────────────────────────────────
    elif page == "Analyse historique":
        st.markdown(f"## 📦 Marchandises V2 — Historique 2015–{ANNEE_FIN}")

        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_scatter(x=yrs_hist, y=nt_hist,  name="Non transbordé",
                            line=dict(color=COULEURS["NT"],  width=2.5), mode="lines+markers")
            fig.add_scatter(x=yrs_hist, y=tr_hist,  name="Transbordé",
                            line=dict(color=COULEURS["Transb"], width=2.5), mode="lines+markers")
            fig.add_scatter(x=yrs_hist, y=tot_hist, name="Total",
                            line=dict(color=COULEURS["Total"], width=2, dash="dot"),
                            mode="lines+markers")
            plo(fig,"Trafic global (Mt)")
        with c2:
            # Part Transbordé dans le Total
            parts_tr = [tr/tot*100 if tot>0 else 0
                        for tr,tot in zip(tr_hist,tot_hist)]
            fig2 = go.Figure()
            fig2.add_scatter(x=yrs_hist, y=parts_tr, name="Part Transbordé",
                             line=dict(color=COULEURS["Transb"],width=2.5),
                             mode="lines+markers")
            fig2.update_yaxes(ticksuffix="%")
            plo(fig2,"Part du Transbordé dans le Total (%)")

        st.markdown("---")
        # Tableau historique
        rows = []
        for yr in yrs_hist:
            nt = ann_hist("NT",yr); tr = ann_hist("Transbordement",yr)
            tot = nt+tr
            pt = tr/tot*100 if tot>0 else 0
            rows.append({"Année":yr, "Non transbordé (Mt)":round(nt,3),
                         "Transbordé (Mt)":round(tr,3),
                         "Total (Mt)":round(tot,3),
                         "Part Transb. (%)":round(pt,1)})
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

    # ── Court terme ──────────────────────────────────────────────
    elif page == "Prévisions court terme":
        st.markdown(f"## 📦 Marchandises V2 — Court terme {ANNEE_MIN_FC}")

        fc_yr = forecasts_v2.get(ANNEE_MIN_FC, {})
        m_nt  = fc_yr.get("mensuel_nt",  np.zeros(12))
        m_tr  = fc_yr.get("mensuel_tr",  np.zeros(12))
        m_tot = fc_yr.get("mensuel_tot", np.zeros(12))
        m_lo  = fc_yr.get("mensuel_nt_lo", np.zeros(12))
        m_hi  = fc_yr.get("mensuel_nt_hi", np.zeros(12))

        c1,c2,c3 = st.columns(3)
        kpi(c1,"Total NT annuel",f"{sum(m_nt):.3f} Mt","Non transbordé")
        kpi(c2,"Total Transb. annuel",f"{sum(m_tr):.3f} Mt","Constant")
        kpi(c3,"Total général annuel",f"{sum(m_tot):.3f} Mt","NT + Transb.")

        fig = go.Figure()
        fig.add_bar(x=NOMS_M, y=list(m_nt), name="Non transbordé",
                    marker_color=COULEURS["NT"], opacity=0.85)
        fig.add_bar(x=NOMS_M, y=list(m_tr), name="Transbordé",
                    marker_color=COULEURS["Transb"], opacity=0.85)
        fig.add_scatter(x=NOMS_M, y=list(m_hi), name="IC95% NT haut",
                        line=dict(color="#90CAF9",dash="dash"), mode="lines")
        fig.add_scatter(x=NOMS_M, y=list(m_lo), name="IC95% NT bas",
                        line=dict(color="#90CAF9",dash="dash"),
                        fill="tonexty", fillcolor="rgba(144,202,249,0.15)",
                        mode="lines")
        fig.update_layout(barmode="stack")
        plo(fig,f"Prévisions mensuelles {ANNEE_MIN_FC} (Mt)")

        st.markdown("---")
        # Tableau CT
        rows = []
        for m in range(12):
            rows.append({
                "Mois"           : NOMS_M[m],
                "NT (Mt)"        : round(float(m_nt[m]),3),
                "Transb. (Mt)"   : round(float(m_tr[m]),3),
                "Total (Mt)"     : round(float(m_tot[m]),3),
                "IC95 NT bas"    : round(float(m_lo[m]),3),
                "IC95 NT haut"   : round(float(m_hi[m]),3),
            })
        df_ct = pd.DataFrame(rows)
        tot_row = {"Mois":"TOTAL",
                   "NT (Mt)":round(sum(m_nt),3),
                   "Transb. (Mt)":round(sum(m_tr),3),
                   "Total (Mt)":round(sum(m_tot),3),
                   "IC95 NT bas":round(sum(m_lo),3),
                   "IC95 NT haut":round(sum(m_hi),3)}
        df_ct = pd.concat([df_ct, pd.DataFrame([tot_row])], ignore_index=True)
        st.dataframe(df_ct.set_index("Mois"), use_container_width=True)

    # ── Long terme ───────────────────────────────────────────────
    elif page == "Prévisions long terme":
        st.markdown(f"## 📦 Marchandises V2 — Long terme {ANNEE_MIN_FC}–{annee_cible}")

        yrs_all = yrs_hist + yrs_fc
        nt_all  = nt_hist  + nt_fc
        tr_all  = tr_hist  + tr_fc
        tot_all = tot_hist + tot_fc

        lo_fc = [ann_fc(yr,"ic_lo_nt") for yr in yrs_fc]
        hi_fc = [ann_fc(yr,"ic_hi_nt") for yr in yrs_fc]

        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_scatter(x=yrs_hist, y=nt_hist, name="NT réalisé",
                            line=dict(color=COULEURS["NT"],width=2.5), mode="lines+markers")
            fig.add_scatter(x=yrs_fc, y=nt_fc, name="NT prévu",
                            line=dict(color=COULEURS["NT"],width=2,dash="dash"),
                            mode="lines+markers")
            fig.add_scatter(x=yrs_fc, y=hi_fc, name="IC95% haut",
                            line=dict(color="#90CAF9",width=0), mode="lines",
                            showlegend=False)
            fig.add_scatter(x=yrs_fc, y=lo_fc, name="IC95% bas",
                            line=dict(color="#90CAF9",width=0), mode="lines",
                            fill="tonexty", fillcolor="rgba(144,202,249,0.18)",
                            showlegend=False)
            plo(fig,"Non transbordé (Mt)")
        with c2:
            fig2 = go.Figure()
            fig2.add_scatter(x=yrs_hist, y=tr_hist, name="Transb. réalisé",
                             line=dict(color=COULEURS["Transb"],width=2.5),
                             mode="lines+markers")
            fig2.add_scatter(x=yrs_fc, y=tr_fc, name="Transb. prévu (cst)",
                             line=dict(color=COULEURS["Transb"],width=2,dash="dash"),
                             mode="lines+markers")
            plo(fig2,"Transbordé (Mt)")

        fig3 = go.Figure()
        fig3.add_scatter(x=yrs_hist, y=tot_hist, name="Total réalisé",
                         line=dict(color=COULEURS["Total"],width=2.5),
                         mode="lines+markers")
        fig3.add_scatter(x=yrs_fc, y=tot_fc, name="Total prévu",
                         line=dict(color=COULEURS["Total"],width=2,dash="dash"),
                         mode="lines+markers")
        plo(fig3,"Total général (Mt)")

        st.markdown("---")
        # Tableau LT
        rows = []
        for yr in yrs_fc:
            nt=ann_fc(yr,"annuel_nt"); tr=ann_fc(yr,"annuel_tr")
            tot=ann_fc(yr,"annuel_tot")
            lo=ann_fc(yr,"ic_lo_nt"); hi=ann_fc(yr,"ic_hi_nt")
            rows.append({"Année":yr,"NT (Mt)":round(nt,3),
                         "Transb. (Mt)":round(tr,3),"Total (Mt)":round(tot,3),
                         "IC95 NT bas":round(lo,3),"IC95 NT haut":round(hi,3),
                         "∆ NT vs 2025":f"{(nt/nt_hist[-1]-1)*100:+.1f}%",
                         "∆ Tot vs 2025":f"{(tot/tot_hist[-1]-1)*100:+.1f}%"})
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

    # ── Analyse par axe NT ───────────────────────────────────────
    elif page == "Analyse par axe NT":
        col_ax, col_yr2 = st.columns([2,1])
        with col_ax:
            axe_key = st.selectbox("Axe d'analyse",
                                   list(AXES_LABEL.keys()),
                                   format_func=lambda x: AXES_LABEL[x],
                                   key="axe_v2")
        with col_yr2:
            yr_axe = st.selectbox("Année",
                                  list(range(ANNEE_MIN_FC, annee_cible+1)),
                                  key="yr_axe_v2")

        st.markdown(f"## 📦 Marchandises V2 — {AXES_LABEL[axe_key]} · {yr_axe}")
        badge("Top-down sur Non transbordé uniquement", "badge-nt")

        segs = AXES_NT[axe_key]
        fc_yr = forecasts_v2.get(yr_axe, {})
        segs_m = fc_yr.get("segs_nt", {})

        # Parts clé choisie
        parts_cle = meta_v2["parts_nt"].get(cle_march,
                    meta_v2["parts_nt"].get(ANNEE_FIN, {}))

        # KPIs par segment
        cols = st.columns(len(segs))
        for ci, seg in enumerate(segs):
            v_m = segs_m.get(seg, np.zeros(12))
            v_ann = float(v_m.sum()) if hasattr(v_m,"sum") else 0
            p = parts_cle.get(seg, 0)
            kpi(cols[ci], seg, f"{v_ann:.3f} Mt",
                f"{p:.2f}% du NT (clé {cle_march})")

        # Graphique mensuel
        fig = go.Figure()
        colors = ["#1563A0","#C87E1A","#0D7A55","#8B44AC","#E53935"]
        for ci, seg in enumerate(segs):
            v_m = segs_m.get(seg, np.zeros(12))
            fig.add_bar(x=NOMS_M, y=list(v_m), name=seg,
                        marker_color=colors[ci % len(colors)], opacity=0.85)
        fig.update_layout(barmode="stack")
        plo(fig,f"Répartition {AXES_LABEL[axe_key]} · {yr_axe} (Mt)")

        st.markdown("---")
        # Tableau annuel par segment
        rows = []
        for yr in yrs_fc:
            row = {"Année":yr}
            fc_y = forecasts_v2.get(yr,{})
            sm = fc_y.get("segs_nt",{})
            for seg in segs:
                v = sm.get(seg, np.zeros(12))
                row[seg] = round(float(v.sum()) if hasattr(v,"sum") else 0, 3)
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

# ─────────────────────────────────────────────────────────────────
# 7. PAGES ESCALES (identiques app1 — réutilisées)
# ─────────────────────────────────────────────────────────────────
elif module == "🚢 Escales":
    yr_last  = mdl_esc["annee_fin"] if mdl_esc else ANNEE_FIN
    wmape    = mdl_esc["wmape"] if mdl_esc else 0
    ann_hist_esc = mdl_esc["ann_total_hist"] if mdl_esc else {}
    parts_esc    = mdl_esc["parts_terminaux"] if mdl_esc else {}
    SEGS_ESC = list(parts_esc.get(yr_last, {}).keys()) if parts_esc else []

    def esc_ann(yr):
        if yr <= yr_last: return ann_hist_esc.get(yr, 0)
        return fc_esc.get(yr, {}).get("annuel", 0)

    yrs_h_e = list(range(mdl_esc["annee_debut"] if mdl_esc else ANNEE_DEBUT, yr_last+1))
    yrs_f_e = list(range(ANNEE_MIN_FC, annee_cible+1))

    if page == "Escales — KPIs":
        st.markdown(f"## 🚢 Escales — KPIs · {yr_last}")
        c1,c2,c3 = st.columns(3)
        kpi(c1,f"Total {yr_last}",f"{esc_ann(yr_last):,}",
            f"Holt amorti · WMAPE={wmape:.1f}%")
        kpi(c2,f"Prévu {ANNEE_MIN_FC}",
            f"{fc_esc.get(ANNEE_MIN_FC,{}).get('annuel',0):,}",
            f"IC95%: [{fc_esc.get(ANNEE_MIN_FC,{}).get('ic_lo',0):,} – "
            f"{fc_esc.get(ANNEE_MIN_FC,{}).get('ic_hi',0):,}]")
        kpi(c3,"Modèle",f"WMAPE={wmape:.1f}%","Holt amorti train 2015-2025")

        st.markdown("---")
        st.markdown("#### Évolution historique")
        fig = go.Figure()
        fig.add_scatter(x=yrs_h_e, y=[esc_ann(yr) for yr in yrs_h_e],
                        name="Réalisé", line=dict(color="#1563A0",width=2.5),
                        mode="lines+markers")
        plo(fig,"Nombre total d'escales")

        with st.expander("Parts par terminal (clé choisie)"):
            pt = parts_esc.get(cle_esc, parts_esc.get(yr_last, {}))
            rows = [{"Terminal":k,"Part (%)":round(v,2)} for k,v in
                    sorted(pt.items(), key=lambda x:-x[1])]
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True)
            if cle_esc != yr_last:
                st.caption(f"⚠️ Clé {cle_esc} utilisée")

    elif page == "Escales — Historique":
        st.markdown(f"## 🚢 Escales — Historique")
        fig = go.Figure()
        fig.add_scatter(x=yrs_h_e, y=[esc_ann(yr) for yr in yrs_h_e],
                        name="Réalisé", line=dict(color="#1563A0",width=2.5),
                        mode="lines+markers")
        plo(fig,"Nombre d'escales 2015–2025")

        rows = [{"Année":yr,"Escales":esc_ann(yr)} for yr in yrs_h_e]
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

    elif page == "Escales — Prévisions CT":
        st.markdown(f"## 🚢 Escales — Court terme {ANNEE_MIN_FC}")
        fc_e = fc_esc.get(ANNEE_MIN_FC, {})
        mens = fc_e.get("mensuel", np.zeros(12))
        c1,c2 = st.columns(2)
        kpi(c1,f"Total prévu {ANNEE_MIN_FC}",f"{int(sum(mens)):,}","Holt amorti")
        kpi(c2,"IC 95%",
            f"[{fc_e.get('ic_lo',0):,} – {fc_e.get('ic_hi',0):,}]","Annuel")
        fig = go.Figure()
        fig.add_bar(x=NOMS_M, y=[int(v) for v in mens],
                    marker_color="#1563A0", opacity=0.85, name="Escales")
        plo(fig,f"Prévisions mensuelles {ANNEE_MIN_FC}")
        rows = [{"Mois":NOMS_M[m],"Escales prévues":int(mens[m])} for m in range(12)]
        st.dataframe(pd.DataFrame(rows).set_index("Mois"), use_container_width=True)

    elif page == "Escales — Prévisions LT":
        st.markdown(f"## 🚢 Escales — Long terme {ANNEE_MIN_FC}–{annee_cible}")
        ann_f = [fc_esc.get(yr,{}).get("annuel",0) for yr in yrs_f_e]
        lo_f  = [fc_esc.get(yr,{}).get("ic_lo",0)  for yr in yrs_f_e]
        hi_f  = [fc_esc.get(yr,{}).get("ic_hi",0)  for yr in yrs_f_e]
        fig = go.Figure()
        fig.add_scatter(x=yrs_h_e, y=[esc_ann(yr) for yr in yrs_h_e],
                        name="Réalisé", line=dict(color="#1563A0",width=2.5),
                        mode="lines+markers")
        fig.add_scatter(x=yrs_f_e, y=ann_f, name="Prévu",
                        line=dict(color="#1563A0",width=2,dash="dash"),
                        mode="lines+markers")
        fig.add_scatter(x=yrs_f_e, y=hi_f,
                        line=dict(color="#90CAF9",width=0), mode="lines",
                        showlegend=False)
        fig.add_scatter(x=yrs_f_e, y=lo_f,
                        line=dict(color="#90CAF9",width=0), mode="lines",
                        fill="tonexty", fillcolor="rgba(144,202,249,0.18)",
                        showlegend=False, name="IC95%")
        plo(fig,"Nombre total d'escales")
        rows = [{"Année":yr,"Prévu":fc_esc.get(yr,{}).get("annuel",0),
                 "IC95 bas":fc_esc.get(yr,{}).get("ic_lo",0),
                 "IC95 haut":fc_esc.get(yr,{}).get("ic_hi",0)} for yr in yrs_f_e]
        st.dataframe(pd.DataFrame(rows).set_index("Année"), use_container_width=True)

    elif page == "Escales — Par terminal":
        st.markdown(f"## 🚢 Escales — Par terminal")
        col_y = st.selectbox("Année", yrs_f_e, key="yr_esc_term_v2")
        fc_e = fc_esc.get(col_y, {})
        ann_e = fc_e.get("annuel", 0)
        segs_e = fc_e.get("segments", {})
        pt_cle = parts_esc.get(cle_esc, parts_esc.get(yr_last, {}))

        rows = []
        for term in sorted(pt_cle.keys(), key=lambda x:-pt_cle[x]):
            p = pt_cle[term]
            v = int(round(ann_e * p / 100))
            rows.append({"Terminal":term,
                         f"Prévu {col_y}":v,
                         f"Part {cle_esc} (%)":round(p,2)})
        fig = go.Figure()
        fig.add_bar(x=[r["Terminal"] for r in rows],
                    y=[r[f"Prévu {col_y}"] for r in rows],
                    marker_color="#1563A0", opacity=0.85)
        plo(fig,f"Escales par terminal — {col_y}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if cle_esc != yr_last:
            st.caption(f"⚠️ Clé {cle_esc} utilisée au lieu de {yr_last}")

# ─────────────────────────────────────────────────────────────────
# 8. PAGES CONTENEURS (identiques app1)
# ─────────────────────────────────────────────────────────────────
elif module == "📦 Conteneurs":
    yr_last_c  = mdl_cnt["annee_fin"]  if mdl_cnt else ANNEE_FIN
    err_tot    = mdl_cnt["err_tot"]    if mdl_cnt else 0
    wmape_nt_c = mdl_cnt["wmape_nt"]   if mdl_cnt else 0
    ann_hist_c = mdl_cnt["ann_total_hist"] if mdl_cnt else {}
    parts_term = mdl_cnt["parts_term"] if mdl_cnt else {}
    parts_dest = mdl_cnt["parts_dest"] if mdl_cnt else {}

    def cnt_ann(yr, key="total"):
        if yr <= yr_last_c: return ann_hist_c.get(yr, 0)
        return fc_cnt.get(yr, {}).get(f"annuel_{key}" if key!="total" else "annuel", 0)

    yrs_h_c = list(range(mdl_cnt["annee_debut"] if mdl_cnt else ANNEE_DEBUT, yr_last_c+1))
    yrs_f_c = list(range(ANNEE_MIN_FC, annee_cible+1))

    if page == "Conteneurs — KPIs":
        st.markdown(f"## 📦 Conteneurs — KPIs · {yr_last_c}")
        c1,c2,c3,c4 = st.columns(4)
        kpi(c1,f"Total {yr_last_c}",f"{ann_hist_c.get(yr_last_c,0):,} EVP",
            f"NT (Holt amorti WMAPE={wmape_nt_c:.1f}%) × ratio")
        kpi(c2,f"Non transb. {yr_last_c}",
            f"{ser_cnt.get('Non transb.',pd.Series()).reindex([pd.Timestamp(yr_last_c,12,1)]).sum():,.0f} EVP",
            f"WMAPE={wmape_nt_c:.1f}%")
        kpi(c3,f"Prévu {ANNEE_MIN_FC}",
            f"{cnt_total_dyn(ANNEE_MIN_FC, cle_cnt):,} EVP",
            f"NT × ratio {cle_cnt}")
        kpi(c4,"Transb. TC2","Constant",
            f"{mdl_cnt.get('transb_tc2_2025',0):,} EVP/an")

        st.markdown("---")
        fig = go.Figure()
        fig.add_scatter(x=yrs_h_c, y=[ann_hist_c.get(yr,0) for yr in yrs_h_c],
                        name="Réalisé", line=dict(color="#C87E1A",width=2.5),
                        mode="lines+markers")
        plo(fig,"Total conteneurs (EVP)")

    elif page == "Conteneurs — Historique":
        st.markdown("## 📦 Conteneurs — Historique")
        SEGS_C = ["Non transb.","Transbordé","Transb. TC2","Transb. habituel"]
        fig = go.Figure()
        clrs_c = ["#1563A0","#C87E1A","#0D7A55","#8B44AC"]
        for si, seg in enumerate(SEGS_C):
            s = ser_cnt.get(seg)
            if s is None: continue
            yy = list(range(ANNEE_DEBUT, yr_last_c+1))
            vv = [int(s[s.index.year==yr].sum()) for yr in yy]
            fig.add_scatter(x=yy, y=vv, name=seg,
                            line=dict(color=clrs_c[si],width=2),
                            mode="lines+markers")
        plo(fig,"Conteneurs par destination (EVP)")
        rows = []
        for yr in yrs_h_c:
            row = {"Année":yr, "Total":ann_hist_c.get(yr,0)}
            for seg in SEGS_C:
                s = ser_cnt.get(seg)
                row[seg] = int(s[s.index.year==yr].sum()) if s is not None else 0
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

    elif page == "Conteneurs — Prévisions CT":
        st.markdown(f"## 📦 Conteneurs — Court terme {ANNEE_MIN_FC}")
        fc_c = fc_cnt.get(ANNEE_MIN_FC, {})
        mens_c = fc_c.get("mensuel", np.zeros(12))
        # Recalibrer le mensuel selon le ratio de la clé choisie
        tot_dyn = cnt_total_dyn(ANNEE_MIN_FC, cle_cnt)
        nt_ann_c = fc_c.get("annuel_nt", int(sum(mens_c)))
        if nt_ann_c > 0 and int(sum(mens_c)) > 0:
            factor = tot_dyn / int(sum(mens_c))
            mens_c = np.round(np.array(mens_c, dtype=float) * factor).astype(int)
        c1,c2 = st.columns(2)
        kpi(c1,f"Total prévu {ANNEE_MIN_FC}",f"{int(sum(mens_c)):,} EVP",
            f"NT × ratio {cle_cnt}")
        kpi(c2,"Transb. TC2",f"{mdl_cnt.get('transb_tc2_2025',0):,} EVP",
            "Constant 2025")
        fig = go.Figure()
        fig.add_bar(x=NOMS_M, y=[int(v) for v in mens_c],
                    marker_color="#C87E1A", opacity=0.85)
        plo(fig,f"Conteneurs mensuels {ANNEE_MIN_FC} (EVP)")
        rows = [{"Mois":NOMS_M[m],"EVP prévus":int(mens_c[m])} for m in range(12)]
        st.dataframe(pd.DataFrame(rows).set_index("Mois"), use_container_width=True)

    elif page == "Conteneurs — Prévisions LT":
        st.markdown(f"## 📦 Conteneurs — Long terme {ANNEE_MIN_FC}–{annee_cible}")
        ann_fc_c = [cnt_total_dyn(yr, cle_cnt) for yr in yrs_f_c]
        fig = go.Figure()
        fig.add_scatter(x=yrs_h_c, y=[ann_hist_c.get(yr,0) for yr in yrs_h_c],
                        name="Réalisé", line=dict(color="#C87E1A",width=2.5),
                        mode="lines+markers")
        fig.add_scatter(x=yrs_f_c, y=ann_fc_c, name="Prévu",
                        line=dict(color="#C87E1A",width=2,dash="dash"),
                        mode="lines+markers")
        plo(fig,"Total conteneurs (EVP)")
        rows = [{"Année":yr,
                 "NT (EVP)": fc_cnt.get(yr,{}).get("annuel_nt",0),
                 "Total (EVP)": cnt_total_dyn(yr, cle_cnt),
                 "Transb. total": cnt_total_dyn(yr, cle_cnt) - fc_cnt.get(yr,{}).get("annuel_nt",0),
                 "Transb. TC2": fc_cnt.get(yr,{}).get("transb_tc2_ann",0),
                 "∆ vs 2025": f"{(cnt_total_dyn(yr,cle_cnt)/ann_hist_c.get(yr_last_c,1)-1)*100:+.1f}%"}
                for yr in yrs_f_c]
        st.dataframe(pd.DataFrame(rows).set_index("Année"),
                     use_container_width=True)

    elif page == "Conteneurs — Par segment":
        st.markdown(f"## 📦 Conteneurs — Par segment")
        col_y2 = st.selectbox("Année", yrs_f_c, key="yr_cnt_seg_v2")
        fc_c = fc_cnt.get(col_y2, {})
        pt_c = parts_term.get(cle_cnt, parts_term.get(yr_last_c, {}))
        ann_c = cnt_total_dyn(col_y2, cle_cnt)
        rows = []
        for term in sorted(pt_c.keys(), key=lambda x:-pt_c[x]):
            p = pt_c[term]
            v = int(round(ann_c * p / 100))
            rows.append({"Terminal":term,
                         f"Prévu {col_y2}":v,
                         f"Part {cle_cnt} (%)":round(p,2)})
        fig = go.Figure()
        fig.add_bar(x=[r["Terminal"] for r in rows],
                    y=[r[f"Prévu {col_y2}"] for r in rows],
                    marker_color="#C87E1A", opacity=0.85)
        plo(fig,f"Conteneurs par terminal — {col_y2}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if cle_cnt != yr_last_c:
            st.caption(f"⚠️ Clé {cle_cnt} utilisée au lieu de {yr_last_c}")
