"""
forecast_engine_conteneurs.py — Moteur de prévision conteneurs Port d'Abidjan
==============================================================================
Étape 1 : Prévision Total annuel (Holt amortie, train 2023-2025)
Étape 2 : Ventilation mensuelle (profil saisonnier 2023-2025)
Étape 3 : Répartition par terminal (Top-down clés N-1)
Étape 4 : Répartition par destination (Top-down clés N-1)
          dont Transbordé = TC2 (constant) + Habituel (Holt)

Usage    : python forecast_engine_conteneurs.py
Prérequis: train_models_conteneurs.py doit avoir été exécuté
Sortie   : forecasts_conteneurs.pkl
"""

import numpy as np
import pickle
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# 0. CONFIG
# ─────────────────────────────────────────────────────────────────
INPUT_MDL = "models_conteneurs_v2.pkl"
INPUT_SER = "series_conteneurs_v2.pkl"
OUTPUT_FC = "forecasts_conteneurs_v2.pkl"
ANNEE_MAX = 2040

# ─────────────────────────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────────────────────────
print("=" * 65)
print("FORECAST_ENGINE_CONTENEURS — Port d'Abidjan")
print("=" * 65)

with open(INPUT_MDL, 'rb') as f: mdl = pickle.load(f)
with open(INPUT_SER, 'rb') as f: series = pickle.load(f)

ANNEE_FIN   = mdl['annee_fin']
ANNEE_DEBUT = mdl['annee_debut']
SEGS_TERM   = mdl['segs_term']
SEGS_DEST   = mdl['segs_dest']
profil      = mdl['profil_saisonnier']
parts_term  = mdl['parts_term']
parts_dest  = mdl['parts_dest']
noms_m      = mdl['noms_mois']
H           = ANNEE_MAX - ANNEE_FIN

print(f"\n[1] Modèles chargés")
print(f"    Total     : NT (pilote) + TC2 constant + Habituel résiduel")
print(f"    Non transb: α={mdl['params_nt'][0]:.2f} β={mdl['params_nt'][1]:.2f} "
      f"φ={mdl['params_nt'][2]:.2f}  WMAPE={mdl['wmape_nt']:.1f}%")
print(f"    Transb TC2: constant = {mdl['transb_tc2_2025']:,} TEU/an")
print(f"    Transb hab: résiduel = Total - (NT + TC2)")



# ─────────────────────────────────────────────────────────────────
# 2. FONCTION HOLT AMORTIE
# ─────────────────────────────────────────────────────────────────
def holt_damped(y, alpha, beta, phi, h=1):
    n = len(y)
    L = np.zeros(n); T = np.zeros(n)
    L[0] = y[0]; T[0] = y[1] - y[0]
    for t in range(1, n):
        L[t] = alpha * y[t] + (1 - alpha) * (L[t-1] + phi * T[t-1])
        T[t] = beta * (L[t] - L[t-1]) + (1 - beta) * phi * T[t-1]
    fc = np.array([L[-1] + sum(phi**j * T[-1] for j in range(1, i+1))
                   for i in range(1, h + 1)])
    fitted = np.array([L[t-1] + phi * T[t-1] for t in range(1, n)])
    return fc, fitted, L, T

# ─────────────────────────────────────────────────────────────────
# 3. TOTAL = NT + TC2 constant + Habituel résiduel
# ─────────────────────────────────────────────────────────────────
print(f"\n[2] Architecture Option A : Total = NT (pilote) + TC2 constant + Habituel résiduel")
print(f"    NT : Holt amorti WMAPE={mdl['wmape_nt']:.1f}%  TC2 : {mdl['transb_tc2_2025']:,} EVP/an constant")

# ─────────────────────────────────────────────────────────────────
# 4. PRÉVISIONS NON TRANSBORDÉ
# ─────────────────────────────────────────────────────────────────
fc_nt_raw, _, _, _ = holt_damped(
    mdl['y_nt'], *mdl['params_nt'], h=H)
fc_nt = np.round(fc_nt_raw).astype(int)

# ─────────────────────────────────────────────────────────────────
# 5. PRÉVISIONS TRANSBORDÉ TC2 (constant)
# ─────────────────────────────────────────────────────────────────
fc_tc2 = np.array([mdl['transb_tc2_2025']] * H)

# ─────────────────────────────────────────────────────────────────
# 6. TRANSBORDÉ HABITUEL = RÉSIDUEL (pas de modèle)
# Calculé comme : Total - (Non transb. + Transb. TC2) → voir boucle
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# 7. PRÉVISIONS COMPLÈTES : mensuel + top-down récursif
# ─────────────────────────────────────────────────────────────────
print(f"\n[3] Ventilation mensuelle + Top-down récursif ...")

# Clés initiales = parts réelles 2025
parts_td_term = {ANNEE_FIN: parts_term[ANNEE_FIN]}
parts_td_dest = {ANNEE_FIN: parts_dest[ANNEE_FIN]}
ratio_tot_nt  = mdl.get('ratio_tot_nt', {ANNEE_FIN: 1.4398})

def ann_hist(seg, yr):
    s = series[seg]
    return int(s[s.index.year == yr].sum())

forecasts = {}

# Stocker historique
for yr in range(ANNEE_DEBUT, ANNEE_FIN + 1):
    tot_yr   = mdl['ann_total'][yr]
    mens_yr  = series['Total'][series['Total'].index.year == yr].values.astype(int)
    segs_t_yr = {g: series[g][series[g].index.year == yr].values.astype(int)
                 for g in SEGS_TERM}
    segs_d_yr = {
        'Non transb.'     : series['Non transb.'][series['Non transb.'].index.year == yr].values.astype(int),
        'Transbordé'      : series['Transbordé'][series['Transbordé'].index.year == yr].values.astype(int),
        'Transb. TC2'     : series['Transb. TC2'][series['Transb. TC2'].index.year == yr].values.astype(int),
        'Transb. habituel': series['Transb. habituel'][series['Transb. habituel'].index.year == yr].values.astype(int),
    }
    forecasts[('historique', yr)] = {
        'annuel'          : tot_yr,
        'mensuel'         : mens_yr,
        'segments_term'   : segs_t_yr,
        'segments_dest'   : segs_d_yr,
    }

# Prévisions 2026-2040
for i, yr in enumerate(range(ANNEE_FIN+1, ANNEE_MAX+1)):
    # ── Step 1 : NT prévu (pilote) ──
    nt_ann_pre = int(fc_nt[i])
    tc2_ann_pre = int(fc_tc2[i])

    # IC sur NT (le pilote)
    rmse_nt_val = mdl['rmse_nt']
    lo_ann  = int(round(nt_ann_pre - 1.96 * rmse_nt_val * np.sqrt(i+1)))
    hi_ann  = int(round(nt_ann_pre + 1.96 * rmse_nt_val * np.sqrt(i+1)))

    # ── Step 2 : Mensuel NT ──
    nt_mens_pre = np.round(nt_ann_pre * profil / 100).astype(int)
    diff_nt_pre = nt_ann_pre - nt_mens_pre.sum()
    if diff_nt_pre != 0: nt_mens_pre[np.argmax(profil)] += diff_nt_pre

    # TC2 mensuel
    tc2_mens_pre = np.round(tc2_ann_pre * profil / 100).astype(int)
    diff_tc2_pre = tc2_ann_pre - tc2_mens_pre.sum()
    if diff_tc2_pre != 0: tc2_mens_pre[np.argmax(profil)] += diff_tc2_pre

    # Total = NT × ratio[cle_annee]
    # Le ratio est lu depuis les clés persistantes (défaut = N-1)
    cle_ratio = cle_cnt if 'cle_cnt' in dir() else ANNEE_FIN
    r = ratio_tot_nt.get(cle_ratio, ratio_tot_nt.get(ANNEE_FIN, 1.4398))
    tot_ann_pre = int(round(nt_ann_pre * r))

    # ── Ventilation mensuelle Total provisoire ──
    mens = np.round(tot_ann_pre * profil / 100).astype(int)
    diff = tot_ann_pre - mens.sum()
    if diff != 0:
        mens[np.argmax(profil)] += diff

    mens_lo = np.round(lo_ann * profil / 100).astype(int)
    mens_hi = np.round(hi_ann * profil / 100).astype(int)

    # ── Top-down terminal (clés N-1) ──
    cle_t = parts_td_term[yr - 1]
    segs_term = {}
    for g in SEGS_TERM:
        sv = np.round(mens * cle_t[g] / 100).astype(int)
        segs_term[g] = sv

    # Ajustement arrondi terminal : forcer somme segments = total mensuel
    seg_dom_t = SEGS_TERM[1]  # TC2 = segment dominant en 2025+
    for m in range(12):
        ecart_m = mens[m] - sum(segs_term[g][m] for g in SEGS_TERM)
        if ecart_m != 0:
            segs_term[seg_dom_t][m] += ecart_m

    # Mise à jour clés terminaux + ratio
    parts_td_term[yr] = {
        g: segs_term[g].sum() / tot_ann_pre * 100 for g in SEGS_TERM
    }
    ratio_tot_nt[yr] = round(tot_ann_pre / nt_ann_pre, 6) if nt_ann_pre > 0 else 1.0

    # ── Destination : modèles indépendants + résiduel ──
    segs_dest = {}

    # Non transbordé : modèle Holt amortie indépendant (WMAPE=3.8%)
    nt_ann  = nt_ann_pre
    nt_mens = nt_mens_pre.copy()

    # Transbordé TC2 : constant 2025
    tc2_ann  = tc2_ann_pre
    tc2_mens = tc2_mens_pre.copy()

    # Transbordé habituel = Total - (Non transb. + Transb. TC2)
    th_mens = mens - nt_mens - tc2_mens
    th_mens = np.maximum(th_mens, 0)  # sécurité : pas de négatifs

    # Transbordé total = TC2 + habituel
    transb_mens = tc2_mens + th_mens

    # Ajustement final : forcer Non transb. + Transb. = Total
    # (absorber les écarts d'arrondi sur Non transb.)
    ecart_dest = mens - nt_mens - transb_mens
    if np.any(ecart_dest != 0):
        for m in range(12):
            nt_mens[m] += ecart_dest[m]

    segs_dest['Non transb.']      = nt_mens
    segs_dest['Transbordé']       = transb_mens
    segs_dest['Transb. TC2']      = tc2_mens
    segs_dest['Transb. habituel'] = th_mens

    # Total final = NT + TC2 + Hab (cohérent par construction)
    tot_ann = nt_ann + tc2_ann + int(th_mens.sum())
    # Recalculer mensuel total cohérent
    mens = nt_mens + transb_mens

    # Mise à jour clés destination (pour compatibilité)
    parts_td_dest[yr] = {
        'Non transb.'     : nt_mens.sum()      / tot_ann * 100,
        'Transbordé'      : transb_mens.sum()  / tot_ann * 100,
        'Transb. TC2'     : tc2_mens.sum()     / tot_ann * 100,
        'Transb. habituel': th_mens.sum()      / tot_ann * 100,
    }

    forecasts[yr] = {
        'annuel'          : tot_ann,
        'annuel_nt'       : nt_ann,
        'ic_lo'           : lo_ann,
        'ic_hi'           : hi_ann,
        'mensuel'         : mens,
        'mensuel_lo'      : mens_lo,
        'mensuel_hi'      : mens_hi,
        'segments_term'   : segs_term,
        'segments_dest'   : segs_dest,
        'parts_td_term'   : {g: round(parts_td_term[yr][g], 4) for g in SEGS_TERM},
        'parts_td_dest'   : {k: round(parts_td_dest[yr][k], 4) for k in parts_td_dest[yr]},
        'cle_annee'       : yr - 1,
        'transb_tc2_ann'  : tc2_ann,
        'transb_hab_ann'  : int(th_mens.sum()),  # Résiduel : Total - (NT + TC2)
    }

    # Vérification
    check_t = sum(segs_term[g].sum() for g in SEGS_TERM)
    check_d = segs_dest['Non transb.'].sum() + segs_dest['Transbordé'].sum()
    print(f"    {yr} : Total={tot_ann:>10,}  "
          f"ΣTerminaux={check_t:>10,} (écart={check_t-tot_ann:+d})  "
          f"ΣDest={check_d:>10,} (écart={check_d-tot_ann:+d})")

# ─────────────────────────────────────────────────────────────────
# 8. MÉTADONNÉES + SAUVEGARDE
# ─────────────────────────────────────────────────────────────────
meta = {
    'modele_total'     : 'NT (pilote) + TC2 constant + Habituel résiduel',
    'alpha_tot'        : None,
    'beta_tot'         : None,
    'phi_tot'          : None,
    'err_tot'          : None,
    'rmse_tot'         : mdl['rmse_nt'],
    'wmape_nt'         : mdl['wmape_nt'],
    'methode_transb_hab': 'Résiduel : Total - (Non transb. + Transb. TC2)',
    'transb_tc2_2025'  : mdl['transb_tc2_2025'],
    'profil_saisonnier': profil,
    'annees_profil'    : mdl['annees_profil'],
    'parts_term'       : parts_term,
    'parts_dest'       : parts_dest,
    'parts_td_term'    : parts_td_term,
    'parts_td_dest'    : parts_td_dest,
    'segs_term'        : SEGS_TERM,
    'segs_dest'        : SEGS_DEST,
    'annee_debut'      : ANNEE_DEBUT,
    'annee_fin'        : ANNEE_FIN,
    'annee_rupture'    : mdl['annee_rupture'],
    'annee_max'        : ANNEE_MAX,
    'noms_mois'        : noms_m,
    'ann_total_hist'   : mdl['ann_total'],
}

output = {'forecasts': forecasts, 'meta': meta}

with open(OUTPUT_FC, 'wb') as f:
    pickle.dump(output, f)

print(f"\n[4] Fichier sauvegardé : {OUTPUT_FC}")
print(f"\n{'='*65}")
print(f"✓ Prévisions générées — {ANNEE_FIN+1} à {ANNEE_MAX} ({H} ans)")
print(f"  Total     : NT x ratio[cle]  (NT WMAPE={mdl['wmape_nt']:.1f}%)")
print(f"  Non transb: Holt amortie (WMAPE={mdl['wmape_nt']:.1f}%)")
print(f"  Transb TC2: constant {mdl['transb_tc2_2025']:,} TEU/an")
print(f"  Transb hab: R\u00e9siduel Total - (Non transb. + Transb. TC2)")
print(f"  Terminaux : Top-down clés N-1 récursif")
print(f"{'='*65}")
