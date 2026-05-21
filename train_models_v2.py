"""
train_models_v2.py — Entraînement modèles App V2
=================================================
Approche : modélisation séparée Non transbordé + Transbordé

Marchandises :
  - Non transbordé (National + Transit) : SARIMA(1,0,0)(0,1,0)12 train 2015-2025
  - Transbordé                           : Moyenne 2024-2025 (constante)
  - Total                                = NT + Transbordé
  - Axes NT : Top-down clés N-1

Conteneurs : identique App V1 (reutilise)
Escales    : identique App V1 (reutilise)

Usage  : python train_models_v2.py
Sortie : models_v2.pkl  +  series_v2.pkl
"""

import pandas as pd
import numpy as np
import pickle
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# 0. CONFIG
# ─────────────────────────────────────────────────────────────────
FICHIER_DONNEES = "data_prevision_Marchandise.xlsx"
OUTPUT_MDL      = "models_v2.pkl"
OUTPUT_SER      = "series_v2.pkl"

ANNEE_DEBUT     = 2015
ANNEE_FIN       = 2025
ANNEES_PROFIL   = [2023, 2024, 2025]

AXES_NT = {
    "sens"             : ["Import", "Export"],
    "composante"       : ["March. generales", "Prod. petroliers", "Prod. de peche"],
    "conteneurisation" : ["Conteneurise", "Non conteneurise"],
}
SEGS_NT = [
    "Import", "Export",
    "March. generales", "Prod. petroliers", "Prod. de peche",
    "Conteneurise", "Non conteneurise",
]

# Labels affichage (avec accents)
SEGS_NT_LABEL = {
    "Import"           : "Import",
    "Export"           : "Export",
    "March. generales" : "March. g\u00e9n\u00e9rales",
    "Prod. petroliers" : "Prod. p\u00e9troliers",
    "Prod. de peche"   : "Prod. de p\u00eache",
    "Conteneurise"     : "Conteneuris\u00e9",
    "Non conteneurise" : "Non conteneuris\u00e9",
}

# ─────────────────────────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────────────────────────
print("=" * 65)
print("TRAIN_MODELS_V2 — Port d'Abidjan (NT + Transb. separes)")
print("=" * 65)

df = pd.read_excel(FICHIER_DONNEES)
df = df[~df["Sens_Trafic"].astype(str).str.startswith("Filtres")]
df = df.dropna(subset=["Date", "Poids_march(tonnes)", "Sens_Trafic"])
df["Date"]      = pd.to_datetime(df["Date"])
df["annee"]     = df["Date"].dt.year
df["mois"]      = df["Date"].dt.month
df["mois_date"] = df["Date"].dt.to_period("M").dt.to_timestamp()
df = df[df["annee"] <= ANNEE_FIN]

COL_VOL  = "Poids_march(tonnes)"
COL_SENS = "Sens_Trafic"
COL_CAT  = "CATEGORIE PRODUITS"
COL_DEST = "Destination"

print(f"\n[1] Donnees chargees : {len(df):,} lignes")

# ─────────────────────────────────────────────────────────────────
# 2. SERIES MENSUELLES
# ─────────────────────────────────────────────────────────────────
IDX = pd.date_range(f"{ANNEE_DEBUT}-01-01", f"{ANNEE_FIN}-12-01", freq="MS")

def build(mask):
    s = (df[mask].groupby("mois_date")[COL_VOL].sum() / 1e6)
    return s.reindex(IDX).fillna(0)

mask_nt  = df[COL_DEST] != "Transbordement"
s_transb = build(df[COL_DEST] == "Transbordement")
s_nt_tot = build(mask_nt)
s_total  = s_nt_tot + s_transb

s_import = build(mask_nt & (df[COL_SENS] == "Import"))
s_export = build(mask_nt & (df[COL_SENS] == "Export"))

s_march = build(mask_nt & df[COL_CAT].isin(["MARCHANDISES GENERALES"]))
s_petr  = build(mask_nt & df[COL_CAT].isin(["PRODUITS PETROLIERS"]))
s_peche = build(mask_nt & df[COL_CAT].str.contains("PECHE|P.CHE", na=False, regex=True))


s_cont    = build(mask_nt & df[COL_CAT].isin(["MARCHANDISES GENERALES"]))
s_noncont = build(mask_nt & df[COL_CAT].str.contains("PETROLIERS|PECHE|P.CHE", na=False, regex=True))


series = {
    "Total"            : s_total,
    "NT"               : s_nt_tot,
    "Transbordement"   : s_transb,
    "Import"           : s_import,
    "Export"           : s_export,
    "March. generales" : s_march,
    "Prod. petroliers" : s_petr,
    "Prod. de peche"   : s_peche,
    "Conteneurise"     : s_cont,
    "Non conteneurise" : s_noncont,
}

def ann(s, yr):
    return float(s[s.index.year == yr].sum())

print(f"[2] Series mensuelles construites : {len(series)} series")
print(f"\n    {'Annee':<6} {'Total':>8} {'NT':>8} {'Transb':>8}")
print("    " + "-"*32)
for yr in range(ANNEE_DEBUT, ANNEE_FIN + 1):
    print(f"    {yr}   {ann(s_total,yr):>8.3f} {ann(s_nt_tot,yr):>8.3f} {ann(s_transb,yr):>8.3f}")

# ─────────────────────────────────────────────────────────────────
# 3. MODELE NT — SARIMA(1,0,0)(0,1,0)12
# ─────────────────────────────────────────────────────────────────
print(f"\n[3] Modele NON TRANSBORNE — SARIMA(1,0,0)(0,1,0)12 ...")

y_nt      = np.array([ann(s_nt_tot, yr) for yr in range(ANNEE_DEBUT, ANNEE_FIN+1)],
                     dtype=float)
y_mens_nt = s_nt_tot.reindex(IDX).fillna(0).values.astype(float)

def sarima_fit(y, s=12):
    """SARIMA(1,0,0)(0,1,0)12 : AR(1) sur diff saisonniere."""
    yd = y[s:] - y[:-s]
    n  = len(yd)
    X  = np.column_stack([yd[:-1], np.ones(n-1)])
    yy = yd[1:]
    from numpy.linalg import lstsq
    coeffs, _, _, _ = lstsq(X, yy, rcond=None)
    phi_val, c_val = float(coeffs[0]), float(coeffs[1])
    fitted  = X @ coeffs
    rmse_m  = float(np.sqrt(np.mean((yy - fitted)**2)))
    return phi_val, c_val, rmse_m

phi_nt, c_nt, rmse_m_nt = sarima_fit(y_mens_nt)
rmse_nt = rmse_m_nt * np.sqrt(12)

# WMAPE LOO annuel (2019-2025)
def sarima_forecast_mens(y, phi, c, h_months, s=12):
    yd     = y[s:] - y[:-s]
    yd_ext = list(yd)
    y_ext  = list(y)
    for _ in range(h_months):
        new_yd = c + phi * yd_ext[-1]
        yd_ext.append(new_yd)
        y_ext.append(max(new_yd + y_ext[-s], 0))
    return np.array(y_ext[-h_months:])

errs = []
for yr_test in range(2019, ANNEE_FIN + 1):
    n_train = (yr_test - ANNEE_DEBUT) * 12
    if n_train < 36: continue
    try:
        phi_t, c_t, _ = sarima_fit(y_mens_nt[:n_train])
        fc_t = sarima_forecast_mens(y_mens_nt[:n_train], phi_t, c_t, h_months=12)
        fc_a = float(fc_t.sum())
        real = float(s_nt_tot[s_nt_tot.index.year == yr_test].sum())
        if real > 0:
            errs.append(abs(real - fc_a) / real)
    except:
        pass
wmape_nt = float(np.mean(errs) * 100) if errs else 999.0

print(f"    phi={phi_nt:.4f}  c={c_nt:.4f}  WMAPE={wmape_nt:.1f}%  RMSE_ann={rmse_nt:.3f} Mt")

# ─────────────────────────────────────────────────────────────────
# 4. TRANSBORNE — Moyenne 2024-2025
# ─────────────────────────────────────────────────────────────────
transb_2024 = ann(s_transb, 2024)
transb_2025 = ann(s_transb, 2025)
transb_moy  = (transb_2024 + transb_2025) / 2.0

print(f"\n[4] TRANSBORNE — Moyenne 2024-2025")
print(f"    2024 = {transb_2024:.3f} Mt")
print(f"    2025 = {transb_2025:.3f} Mt")
print(f"    Moyenne = {transb_moy:.3f} Mt/an")

# ─────────────────────────────────────────────────────────────────
# 5. PROFIL SAISONNIER Transb (2023-2025)
# ─────────────────────────────────────────────────────────────────
print(f"\n[5] Profil saisonnier Transb (2023-2025) ...")
parts_sais_tr = {}
for yr in ANNEES_PROFIL:
    sub = s_transb[s_transb.index.year == yr]
    tot = sub.sum()
    parts_sais_tr[yr] = sub.values / tot * 100 if tot > 0 else np.ones(12) * (100/12)
profil_tr = np.mean([parts_sais_tr[yr] for yr in ANNEES_PROFIL], axis=0)

noms_m = ["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"]
print(f"    Profil Tr : {' '.join(f'{v:.1f}%' for v in profil_tr)}")

# ─────────────────────────────────────────────────────────────────
# 6. CLES DE REPARTITION NT
# ─────────────────────────────────────────────────────────────────
print(f"\n[6] Cles de repartition NT ...")
parts_nt = {}
for yr in range(ANNEE_DEBUT, ANNEE_FIN + 1):
    tot_yr = ann(s_nt_tot, yr)
    if tot_yr == 0:
        continue
    parts_nt[yr] = {seg: ann(series[seg], yr) / tot_yr * 100
                    for seg in SEGS_NT}

print(f"    Parts NT 2025 :")
for seg in SEGS_NT:
    label = SEGS_NT_LABEL.get(seg, seg)
    print(f"      {label:<25} : {parts_nt[ANNEE_FIN].get(seg, 0):.2f}%")

# Verification coherence
for axe, segs in AXES_NT.items():
    total_parts = sum(parts_nt[ANNEE_FIN].get(s, 0) for s in segs)
    ok = "OK" if abs(total_parts - 100) < 0.1 else f"ERREUR={total_parts:.1f}%"
    print(f"      Somme {axe:<20}: {total_parts:.2f}%  {ok}")

# ─────────────────────────────────────────────────────────────────
# 7. HISTORIQUE ANNUEL
# ─────────────────────────────────────────────────────────────────
ann_nt  = {yr: ann(s_nt_tot, yr)  for yr in range(ANNEE_DEBUT, ANNEE_FIN+1)}
ann_tr  = {yr: ann(s_transb, yr)  for yr in range(ANNEE_DEBUT, ANNEE_FIN+1)}
ann_tot = {yr: ann(s_total,  yr)  for yr in range(ANNEE_DEBUT, ANNEE_FIN+1)}

# ─────────────────────────────────────────────────────────────────
# 8. SAUVEGARDE
# ─────────────────────────────────────────────────────────────────
model_data = {
    # Modele NT — SARIMA(1,0,0)(0,1,0)12
    "modele_nt"     : "SARIMA(1,0,0)(0,1,0)12",
    "phi_nt"        : phi_nt,
    "c_nt"          : c_nt,
    "wmape_nt"      : wmape_nt,
    "rmse_nt"       : rmse_nt,
    "rmse_m_nt"     : rmse_m_nt,
    "y_nt"          : y_nt,
    "y_mens_nt"     : y_mens_nt,
    # Transb. constant
    "transb_2024"   : transb_2024,
    "transb_2025"   : transb_2025,
    "transb_moy"    : transb_moy,
    # Profil saisonnier
    "profil_tr"     : profil_tr,
    "annees_profil" : ANNEES_PROFIL,
    # Cles NT
    "parts_nt"      : parts_nt,
    "segs_nt"       : SEGS_NT,
    "segs_nt_label" : SEGS_NT_LABEL,
    "axes_nt"       : AXES_NT,
    # Historique
    "ann_nt"        : ann_nt,
    "ann_tr"        : ann_tr,
    "ann_tot"       : ann_tot,
    # Metadonnees
    "annee_debut"   : ANNEE_DEBUT,
    "annee_fin"     : ANNEE_FIN,
    "noms_mois"     : noms_m,
}

with open(OUTPUT_MDL, "wb") as f:
    pickle.dump(model_data, f)
with open(OUTPUT_SER, "wb") as f:
    pickle.dump(series, f)

print(f"\n[7] Fichiers sauvegardes :")
print(f"    -> {OUTPUT_MDL}")
print(f"    -> {OUTPUT_SER}")
print(f"\n{'='*65}")
print(f"Entrai nement V2 termine")
print(f"  NT      : SARIMA(1,0,0)(0,1,0)12 (WMAPE={wmape_nt:.1f}%)  train 2015-2025")
print(f"  Transb. : Moyenne 2024-2025 = {transb_moy:.3f} Mt/an")
print(f"  Total   = NT + Transborde")
print(f"{'='*65}")
