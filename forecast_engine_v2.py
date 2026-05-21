"""
forecast_engine_v2.py — Moteur de prevision App V2
===================================================
NT marchandises : SARIMA(1,0,0)(0,1,0)12 sur donnees mensuelles
Transborde      : Constante = moyenne 2024-2025
Total           = NT + Transborde
Axes NT         : Top-down cles N-1

Usage    : python forecast_engine_v2.py
Prerequis: train_models_v2.py doit avoir ete execute (models_v2.pkl + series_v2.pkl)
Sortie   : forecasts_v2.pkl
"""

import numpy as np
import pickle
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# 0. CONFIG
# ─────────────────────────────────────────────────────────────────
INPUT_MDL = "models_v2.pkl"
INPUT_SER = "series_v2.pkl"
OUTPUT_FC = "forecasts_v2.pkl"
ANNEE_MAX = 2040

# ─────────────────────────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────────────────────────
print("=" * 65)
print("FORECAST_ENGINE_V2 — Port d'Abidjan (NT + Transborde)")
print("=" * 65)

with open(INPUT_MDL, "rb") as f:
    mdl = pickle.load(f)
with open(INPUT_SER, "rb") as f:
    series = pickle.load(f)

ANNEE_FIN   = mdl["annee_fin"]
ANNEE_DEBUT = mdl["annee_debut"]
SEGS_NT     = mdl["segs_nt"]
AXES_NT     = mdl["axes_nt"]
profil_tr   = mdl["profil_tr"]
parts_nt    = mdl["parts_nt"]
noms_m      = mdl["noms_mois"]
H           = ANNEE_MAX - ANNEE_FIN
H_MENS      = H * 12

print(f"\n[1] Modele charge")
print(f"    NT      : {mdl['modele_nt']}")
print(f"              phi={mdl['phi_nt']:.4f}  c={mdl['c_nt']:.4f}  WMAPE={mdl['wmape_nt']:.1f}%")
print(f"    Transb. : Constante = {mdl['transb_moy']:.3f} Mt/an")

# ─────────────────────────────────────────────────────────────────
# 2. FONCTION SARIMA
# ─────────────────────────────────────────────────────────────────
def sarima_forecast_mens(y, phi, c, h_months, s=12):
    """Prevision h_months en avant — SARIMA(1,0,0)(0,1,0)12."""
    yd     = y[s:] - y[:-s]
    yd_ext = list(yd)
    y_ext  = list(y)
    for _ in range(h_months):
        new_yd = c + phi * yd_ext[-1]
        yd_ext.append(new_yd)
        new_y  = new_yd + y_ext[-s]
        y_ext.append(max(new_y, 0.0))
    return np.array(y_ext[-h_months:])

# ─────────────────────────────────────────────────────────────────
# 3. PREVISIONS NT — SARIMA mensuel → agregation annuelle
# ─────────────────────────────────────────────────────────────────
fc_mens_nt = sarima_forecast_mens(
    mdl["y_mens_nt"], mdl["phi_nt"], mdl["c_nt"], h_months=H_MENS)

fc_nt = np.array([fc_mens_nt[i*12:(i+1)*12].sum() for i in range(H)])
fc_nt = np.round(fc_nt, 3)

# IC annuel
rmse_nt  = float(mdl["rmse_nt"])
ic_lo_nt = np.round(fc_nt - 1.96 * rmse_nt * np.sqrt(np.arange(1, H+1)), 3)
ic_hi_nt = np.round(fc_nt + 1.96 * rmse_nt * np.sqrt(np.arange(1, H+1)), 3)

# Transborde constant
fc_tr  = np.array([float(mdl["transb_moy"])] * H)
fc_tot = np.round(fc_nt + fc_tr, 3)

print(f"\n[2] Previsions annuelles 2026-2030 :")
print(f"    {'Annee':>6} {'NT':>10} {'Transb':>10} {'Total':>10}")
print("    " + "-"*40)
for i, yr in enumerate(range(ANNEE_FIN+1, min(ANNEE_MAX+1, ANNEE_FIN+6))):
    print(f"    {yr}   {fc_nt[i]:>10.3f} {fc_tr[i]:>10.3f} {fc_tot[i]:>10.3f}")

# ─────────────────────────────────────────────────────────────────
# 4. VENTILATION MENSUELLE + TOP-DOWN NT
# ─────────────────────────────────────────────────────────────────
print(f"\n[3] Ventilation mensuelle + Top-down NT ...")

parts_td_nt = {ANNEE_FIN: dict(parts_nt[ANNEE_FIN])}
forecasts   = {}

# Historique
for yr in range(ANNEE_DEBUT, ANNEE_FIN+1):
    nt_yr  = float(mdl["ann_nt"][yr])
    tr_yr  = float(mdl["ann_tr"][yr])
    tot_yr = float(mdl["ann_tot"][yr])

    s_nt_s = series["NT"]
    s_tr_s = series["Transbordement"]
    mens_nt  = s_nt_s[s_nt_s.index.year == yr].values
    mens_tr  = s_tr_s[s_tr_s.index.year == yr].values
    mens_tot = mens_nt + mens_tr

    segs_yr = {}
    for seg in SEGS_NT:
        s_seg = series.get(seg)
        segs_yr[seg] = s_seg[s_seg.index.year == yr].values if s_seg is not None \
                       else np.zeros(12)

    forecasts[("historique", yr)] = {
        "annuel_nt"  : nt_yr,
        "annuel_tr"  : tr_yr,
        "annuel_tot" : tot_yr,
        "mensuel_nt" : mens_nt,
        "mensuel_tr" : mens_tr,
        "mensuel_tot": mens_tot,
        "segs_nt"    : segs_yr,
    }

# Previsions 2026-2040
for i, yr in enumerate(range(ANNEE_FIN+1, ANNEE_MAX+1)):
    nt_ann  = float(fc_nt[i])
    tr_ann  = float(fc_tr[i])
    tot_ann = float(fc_tot[i])
    lo_nt   = float(ic_lo_nt[i])
    hi_nt   = float(ic_hi_nt[i])

    # Mensuel NT depuis SARIMA
    idx_s   = i * 12
    mens_nt = np.round(fc_mens_nt[idx_s:idx_s+12], 3)
    diff_nt = round(nt_ann - float(mens_nt.sum()), 4)
    if abs(diff_nt) > 0.0005:
        mens_nt[int(np.argmax(mens_nt))] += diff_nt

    # Mensuel Transb (profil fixe)
    mens_tr = np.round(tr_ann * profil_tr / 100.0, 3)
    diff_tr = round(tr_ann - float(mens_tr.sum()), 4)
    if abs(diff_tr) > 0.0005:
        mens_tr[int(np.argmax(profil_tr))] += diff_tr

    # Total mensuel
    mens_tot = np.round(mens_nt + mens_tr, 3)

    # IC mensuel
    profil_mens = mens_nt / mens_nt.sum() if mens_nt.sum() > 0 \
                  else np.ones(12) / 12.0
    mens_nt_lo  = np.round(lo_nt * profil_mens, 3)
    mens_nt_hi  = np.round(hi_nt * profil_mens, 3)

    # Top-down NT -> axes (cles N-1)
    cle = parts_td_nt[yr - 1]
    segs_mens = {}
    for seg in SEGS_NT:
        sv = np.round(mens_nt * cle.get(seg, 0.0) / 100.0, 3)
        diff_s = round(nt_ann * cle.get(seg, 0.0) / 100.0 - float(sv.sum()), 4)
        if abs(diff_s) > 0.0005:
            sv[int(np.argmax(mens_nt))] += diff_s
        segs_mens[seg] = sv

    # Mise a jour cles pour annee suivante
    parts_td_nt[yr] = {
        seg: round(float(segs_mens[seg].sum()) / nt_ann * 100.0, 4)
        for seg in SEGS_NT
    }

    # Verification ecarts
    errs_axe = {}
    for axe, segs in AXES_NT.items():
        s_axe = round(sum(float(segs_mens[s].sum()) for s in segs) - nt_ann, 4)
        errs_axe[axe] = s_axe

    forecasts[yr] = {
        "annuel_nt"    : round(nt_ann, 3),
        "annuel_tr"    : round(tr_ann, 3),
        "annuel_tot"   : round(tot_ann, 3),
        "ic_lo_nt"     : round(lo_nt, 3),
        "ic_hi_nt"     : round(hi_nt, 3),
        "mensuel_nt"   : mens_nt,
        "mensuel_tr"   : mens_tr,
        "mensuel_tot"  : mens_tot,
        "mensuel_nt_lo": mens_nt_lo,
        "mensuel_nt_hi": mens_nt_hi,
        "segs_nt"      : segs_mens,
        "parts_td_nt"  : {s: round(parts_td_nt[yr][s], 4) for s in SEGS_NT},
        "cle_annee"    : yr - 1,
    }

    ecarts = " ".join(f"{k}={v:+.4f}" for k, v in errs_axe.items())
    print(f"    {yr}: NT={nt_ann:.3f} Tr={tr_ann:.3f} Tot={tot_ann:.3f}  ecarts({ecarts})")

# ─────────────────────────────────────────────────────────────────
# 5. METADONNEES + SAUVEGARDE
# ─────────────────────────────────────────────────────────────────
meta = {
    "modele_nt"    : mdl["modele_nt"],
    "phi_nt"       : mdl["phi_nt"],
    "c_nt"         : mdl["c_nt"],
    "wmape_nt"     : mdl["wmape_nt"],
    "rmse_nt"      : mdl["rmse_nt"],
    "transb_moy"   : mdl["transb_moy"],
    "transb_2024"  : mdl["transb_2024"],
    "transb_2025"  : mdl["transb_2025"],
    "profil_tr"    : profil_tr,
    "annees_profil": mdl["annees_profil"],
    "parts_nt"     : parts_nt,
    "parts_td_nt"  : parts_td_nt,
    "segs_nt"      : SEGS_NT,
    "segs_nt_label": mdl.get("segs_nt_label", {}),
    "axes_nt"      : AXES_NT,
    "annee_debut"  : ANNEE_DEBUT,
    "annee_fin"    : ANNEE_FIN,
    "annee_max"    : ANNEE_MAX,
    "noms_mois"    : noms_m,
    "ann_nt_hist"  : mdl["ann_nt"],
    "ann_tr_hist"  : mdl["ann_tr"],
    "ann_tot_hist" : mdl["ann_tot"],
}

output = {"forecasts": forecasts, "meta": meta}
with open(OUTPUT_FC, "wb") as f:
    pickle.dump(output, f)

print(f"\n[4] Fichier sauvegarde : {OUTPUT_FC}")
print(f"\n{'='*65}")
print(f"Previsions V2 generees — {ANNEE_FIN+1} a {ANNEE_MAX} ({H} ans)")
print(f"  NT      : {mdl['modele_nt']} (WMAPE={mdl['wmape_nt']:.1f}%)")
print(f"  Transb. : Constante {mdl['transb_moy']:.3f} Mt/an")
print(f"  Total   = NT + Transborde")
print(f"  Axes NT : Top-down cles N-1")
print(f"{'='*65}")
