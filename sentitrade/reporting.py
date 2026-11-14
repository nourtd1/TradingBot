"""Rapport de backtest : métriques, références, IS/OOS, sensibilité, Monte Carlo, verdict.

Contrat : docs/SPEC_TECHNIQUE.md §6 (critères de décision PRÉ-ENREGISTRÉS : ils
sont recopiés tels quels dans `calculer_verdict` et ne doivent pas être
modifiés après avoir vu des résultats) et docs/GARDE_FOUS.md §5 (honnêteté).

Toutes les sections produisent des dictionnaires sérialisables en JSON
(`resume.json`), pour que le CLI puisse découper un long calcul en plusieurs
commandes. `rediger_rapport(resume)` écrit le rapport en français à partir de
ce seul dictionnaire.

Conventions :
- R d'un trade = pnl / (lots × perte_par_lot réelle à l'entrée), colonne `r_multiple` ;
- un trade gagnant a un pnl > 0 ; les autres (pnl <= 0) sont perdants ;
- drawdown : sur l'equity à la clôture de chaque bougie d'exécution (prix du marché).
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from sentitrade.backtest import (ResultatBacktest, executer_backtest, pnl_sortie,
                                 preparer_marche, simuler_trade, _fenetre)
from sentitrade.risk_manager import calculer_taille_lot, decouper_volume

GRAINE_REFERENCE = 20261113
GRAINE_MONTE_CARLO = 20261114
TIRAGES_REFERENCE = 200
PERMUTATIONS_MONTE_CARLO = 1000
PART_IS = 0.60

# Grille de sensibilité de la spec §6 (pour information : on ne choisit pas « le meilleur »).
GRILLE_SL_PLAFOND = (3.0, 5.0, 8.0, 12.0)
GRILLE_MODE_ENTREE = ("bord", "milieu")
GRILLE_VALIDITE = (4, 8, 16)
GRILLE_SPREAD_MAX = (0.30, 0.50)

# Seuils du verdict (spec §6) — NE PAS MODIFIER après avoir vu des résultats.
SEUIL_TRADES_TOTAL = 100
SEUIL_TRADES_OOS = 40
SEUIL_ESPERANCE_OOS = 0.10
SEUIL_PF_OOS = 1.2
SEUIL_DD_MAX = 15.0
SEUIL_DD_MC_P95 = 25.0
PERCENTILE_REF_GO = 90
PERCENTILE_REF_NOGO = 75
SEUIL_PLAFONDS_POSITIFS = 3


def _f(x) -> Optional[float]:
    """float JSON-compatible (None pour NaN)."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x):
        return None
    return x


# --------------------------------------------------------------------------- métriques

def metriques_trades(trades: pd.DataFrame) -> dict:
    """Statistiques de la série de trades (en R et en $)."""
    n = int(len(trades))
    res = {"nb_trades": n}
    if n == 0:
        res.update({k: None for k in ("taux_reussite", "gain_moyen_r", "perte_moyenne_r", "esperance_r",
                                      "esperance_usd", "ecart_type_r", "t_stat", "profit_factor",
                                      "serie_perdante_max", "pnl_total", "r_total")})
        res["serie_perdante_max"] = 0
        return res
    pnl = trades["pnl"].to_numpy(dtype=float)
    r = trades["r_multiple"].to_numpy(dtype=float)
    gagnant = pnl > 0
    gains, pertes = pnl[gagnant].sum(), pnl[~gagnant].sum()
    if pertes < 0:
        pf = gains / -pertes
    else:
        pf = float("inf") if gains > 0 else None
    ecart = float(np.std(r, ddof=1)) if n >= 2 else None
    t_stat = (float(r.mean()) / (ecart / math.sqrt(n))) if ecart else None
    serie = meilleure = 0
    for g in gagnant:
        serie = 0 if g else serie + 1
        meilleure = max(meilleure, serie)
    res.update({
        "taux_reussite": float(gagnant.mean()),
        "gain_moyen_r": _f(r[gagnant].mean()) if gagnant.any() else None,
        "perte_moyenne_r": _f(r[~gagnant].mean()) if (~gagnant).any() else None,
        "esperance_r": float(r.mean()),
        "esperance_usd": float(pnl.mean()),
        "ecart_type_r": ecart,
        "t_stat": t_stat,
        "profit_factor": pf,
        "serie_perdante_max": int(meilleure),
        "pnl_total": float(pnl.sum()),
        "r_total": float(r.sum()),
    })
    return res


def drawdown(equity: pd.Series) -> tuple:
    """(drawdown max en %, drawdown max en $, plus longue durée sous le plus haut en jours)."""
    if equity is None or len(equity) == 0:
        return 0.0, 0.0, 0.0
    e = equity.to_numpy(dtype=float)
    pic = np.maximum.accumulate(e)
    dd = (pic - e) / pic
    k = int(np.argmax(dd))
    t = equity.index.values.astype("datetime64[ns]").view(np.int64)
    est_pic = e >= pic
    dernier_pic = np.where(est_pic, t, np.iinfo(np.int64).min)
    dernier_pic = np.maximum.accumulate(dernier_pic)
    duree = (t - dernier_pic).max() / (86400 * 1e9)
    return float(dd[k] * 100), float(pic[k] - e[k]), float(duree)


def metriques_equity(equity: pd.Series, balance_initiale: float, debut, fin) -> dict:
    """Rendement, CAGR, drawdown, Sharpe journalier (sur l'equity de fin de journée)."""
    finale = float(equity.iloc[-1]) if len(equity) else float(balance_initiale)
    rendement = finale / balance_initiale - 1.0
    annees = max((pd.Timestamp(fin) - pd.Timestamp(debut)).days / 365.25, 1e-9) if debut is not None else None
    cagr = (finale / balance_initiale) ** (1.0 / annees) - 1.0 if annees and finale > 0 else None
    dd_pct, dd_usd, dd_jours = drawdown(equity)
    sharpe = None
    if len(equity):
        jour = equity.groupby(equity.index.normalize()).last()
        rend = jour.pct_change()
        rend.iloc[0] = jour.iloc[0] / balance_initiale - 1.0
        if len(rend) >= 2 and float(rend.std(ddof=1)) > 0:
            sharpe = float(rend.mean() / rend.std(ddof=1) * math.sqrt(252))
    return {"balance_finale": finale, "rendement_total_pct": rendement * 100,
            "cagr_pct": None if cagr is None else cagr * 100, "dd_max_pct": dd_pct, "dd_max_usd": dd_usd,
            "dd_duree_jours": dd_jours, "sharpe_journalier": sharpe}


def ventilations(trades: pd.DataFrame) -> dict:
    """Ventilation par année, mois, sens, heure d'entrée et raison de sortie (listes de dicts)."""
    if len(trades) == 0:
        return {k: [] for k in ("annee", "mois", "sens", "heure", "raison_sortie")}
    t = trades.copy()
    entree = pd.to_datetime(t["entree_a"])
    cles = {
        "annee": entree.dt.year.astype(str),
        "mois": entree.dt.strftime("%Y-%m"),
        "sens": t["sens"].map({1: "long", -1: "short"}),
        "heure": entree.dt.hour.map(lambda h: f"{h:02d}h"),
        "raison_sortie": t["raison_sortie"],
    }
    res = {}
    for nom, cle in cles.items():
        g = t.groupby(cle.values)
        tab = pd.DataFrame({
            "nb": g.size(),
            "taux_reussite": g["pnl"].apply(lambda x: float((x > 0).mean())),
            "esperance_r": g["r_multiple"].mean(),
            "r_total": g["r_multiple"].sum(),
            "pnl_total": g["pnl"].sum(),
        }).sort_index()
        res[nom] = [{"cle": str(k), **{c: _f(v) if c != "nb" else int(v) for c, v in ligne.items()}}
                    for k, ligne in tab.iterrows()]
    return res


def mois_perdants(trades: pd.DataFrame) -> tuple:
    """(nombre de mois avec trades, nombre de mois à pnl < 0)."""
    if len(trades) == 0:
        return 0, 0
    pnl = trades.groupby(pd.to_datetime(trades["sortie_a"]).dt.strftime("%Y-%m"))["pnl"].sum()
    return int(len(pnl)), int((pnl < 0).sum())


def compter_evenements(evenements: pd.DataFrame) -> dict:
    """Comptes des setups créés, rejetés et annulés par raison."""
    if len(evenements) == 0:
        return {"nouveaux": 0, "entrees": 0, "rejets": {}, "annulations": {}, "remplacements": 0,
                "attentes_spread": 0}
    e = evenements
    return {
        "nouveaux": int((e["type"] == "nouveau").sum()),
        "entrees": int((e["type"] == "entree").sum()),
        "remplacements": int((e["type"] == "remplace").sum()),
        "attentes_spread": int(((e["type"] == "annule") & (e["raison"] == "spread_trop_large")).sum()),
        "rejets": {str(k): int(v) for k, v in e[e["type"] == "rejete"]["raison"].value_counts().items()},
        "annulations": {str(k): int(v) for k, v in e[e["type"] == "annule"]["raison"].value_counts().items()},
        "tp1_sans_partiel": int((e["type"] == "tp1_sans_partiel").sum()),
    }


def resumer_resultat(res: ResultatBacktest) -> dict:
    """Toutes les métriques d'un backtest (dictionnaire JSON)."""
    m = metriques_trades(res.trades)
    m.update(metriques_equity(res.equity, res.balance_initiale, res.debut, res.fin))
    nb_mois, nb_perdants = mois_perdants(res.trades)
    m.update({"nb_mois": nb_mois, "nb_mois_perdants": nb_perdants,
              "debut": str(res.debut), "fin": str(res.fin), "resolution": res.resolution,
              "balance_initiale": res.balance_initiale,
              # En mode évaluation (arrêt neutralisé), « arrêt » = franchissement daté sur l'equity.
              "arret_definitif": bool(res.arret_definitif or res.stats.get("date_franchissement_dd")),
              "mode_evaluation": not res.stats.get("arret_definitif_actif", True),
              "raison_arret": res.raison_arret,
              "date_arret": next((str(d.instant) for d in res.historique_garde if d.type == "drawdown_max"),
                                 res.stats.get("date_franchissement_dd")),
              "stats": {k: (int(v) if isinstance(v, (int, np.integer)) else v) for k, v in res.stats.items()}})
    # Critère 4 : on retient le drawdown le plus défavorable, celui mesuré au pire prix des bougies.
    dd_adv = res.stats.get("dd_max_adverse_pct")
    m["dd_max_cloture_pct"] = m.get("dd_max_pct")
    if dd_adv is not None and (m.get("dd_max_pct") is None or dd_adv > m["dd_max_pct"]):
        m["dd_max_pct"] = float(dd_adv)
    return m


# --------------------------------------------------------------------------- références

def buy_and_hold(bougies: pd.DataFrame, debut=None, fin=None, point: float = 0.01) -> dict:
    """Achat de l'or au premier open (Ask) de la fenêtre, conservé jusqu'à la dernière clôture (Bid), sans levier."""
    b = _fenetre(bougies, debut, fin)
    if len(b) == 0:
        return {"rendement_pct": None, "dd_max_pct": None}
    achat = float(b["open"].iloc[0] + b["spread"].iloc[0] * float(point))
    vente = float(b["close"].iloc[-1])
    dd_pct, _, dd_jours = drawdown(cours_journalier(b))
    return {"rendement_pct": (vente / achat - 1) * 100, "dd_max_pct": dd_pct, "dd_duree_jours": dd_jours,
            "prix_debut": achat, "prix_fin": vente}


def cours_journalier(bougies: pd.DataFrame, debut=None, fin=None) -> pd.Series:
    """Dernière clôture (Bid) de chaque date serveur de la fenêtre."""
    b = _fenetre(bougies, debut, fin)
    return b["close"].groupby(b.index.normalize()).last()


def reference_tendance_seule(bougies: pd.DataFrame, signaux: pd.DataFrame, cfg, spec, nb_trades: int,
                             distances: np.ndarray, debut=None, fin=None, resolution: str = "m1",
                             balance: float = 3000.0, tirages: int = TIRAGES_REFERENCE,
                             graine: int = GRAINE_REFERENCE, spread_plancher=None,
                             esperance_strategie: Optional[float] = None) -> dict:
    """Référence « tendance seule » (spec §6).

    Entrées au marché à des clôtures M15 tirées au hasard dans la session
    (`heure_entree_ok`), dans le sens de la tendance H1 (≠ 0), à l'open (Ask
    pour un long, Bid pour un short, + glissement) de la première bougie
    d'exécution de la période suivante, si son spread <= spread_max. SL tiré
    dans `distances` (distances réelles des trades de la stratégie), TP1 à
    `tp1_r` × SL, mêmes sorties (`simuler_trade`), même taille (risque sur
    `balance`). Pas de filtre ADR (c'est la « tendance seule »). Chaque tirage
    compte `nb_trades` trades indépendants ; on renvoie la distribution de
    l'espérance par tirage.
    """
    s, ex = cfg.strategie, cfg.execution
    distances = np.asarray(distances, dtype=float)
    distances = distances[np.isfinite(distances) & (distances > 0)]
    if nb_trades < 1 or len(distances) == 0:
        return {"disponible": False, "raison": "aucun trade de la stratégie : référence non calculable"}
    b = _fenetre(bougies, debut, fin)
    marche = preparer_marche(b, cfg, spec, resolution, spread_plancher)
    sig = _fenetre(signaux, debut, fin)
    sig = sig[sig["heure_entree_ok"].to_numpy() & (sig["tendance"].to_numpy() != 0)]
    C = sig.index.values.astype("datetime64[ns]").view(np.int64)
    m = np.searchsorted(marche.temps, C, side="left")
    ok = m < len(marche)
    m_sur = np.where(ok, m, 0)
    ok &= marche.temps[m_sur] < C + 15 * 60 * 10 ** 9
    ok &= marche.heure_entree[m_sur] & ~marche.cloture[m_sur]
    ok &= marche.sp[m_sur] <= float(s.spread_max) + 1e-9
    candidats = m[ok]
    sens_c = sig["tendance"].to_numpy()[ok]
    if len(candidats) == 0:
        return {"disponible": False, "raison": "aucune clôture M15 candidate"}
    rng = np.random.default_rng(int(graine))
    contrat, ge = float(spec.taille_contrat), float(ex.glissement_entree)
    commission = float(ex.commission_par_lot)
    cache_taille: dict = {}
    esperances, tous_r = [], []
    refus = 0
    for _ in range(int(tirages)):
        remplacer = len(candidats) < nb_trades
        choix = rng.choice(len(candidats), size=nb_trades, replace=remplacer)
        d_tires = rng.choice(distances, size=nb_trades, replace=True)
        r_tirage = []
        for c_idx, d in zip(choix, d_tires):
            i = int(candidats[c_idx])
            sens = int(sens_c[c_idx])
            prix = float(marche.o[i] + marche.sp[i]) + ge if sens > 0 else float(marche.o[i]) - ge
            sl = prix - sens * d
            tp1 = prix + sens * float(s.tp1_r) * d
            perte = d * contrat + commission
            cle = (round(perte, 6), round(prix, 2))
            if cle not in cache_taille:
                t = calculer_taille_lot(balance, cfg.risque, perte, prix * contrat, spec)
                lots_tp1 = decouper_volume(t.lots, s.tp1_fraction, spec)[0] if t.accepte else 0.0
                cache_taille[cle] = (t.accepte, t.lots, lots_tp1)
            accepte, lots, lots_tp1 = cache_taille[cle]
            if not accepte:
                refus += 1
                continue
            sim = simuler_trade(marche, i, sens, prix, sl, tp1, lots, lots_tp1, cfg, spec)
            pnl = sum(pnl_sortie(sens, prix, p, v, cfg, spec) for (_, p, v, _) in sim.sorties)
            r_tirage.append(pnl / (lots * perte))
        if r_tirage:
            esperances.append(float(np.mean(r_tirage)))
            tous_r.extend(r_tirage)
    if not esperances:
        return {"disponible": False, "raison": "toutes les tailles refusées"}
    e = np.asarray(esperances)
    res = {"disponible": True, "tirages": int(tirages), "trades_par_tirage": int(nb_trades),
           "graine": int(graine), "nb_candidats": int(len(candidats)), "refus_taille": int(refus),
           "esperance_moyenne": float(e.mean()), "p50": float(np.percentile(e, 50)),
           "p75": float(np.percentile(e, PERCENTILE_REF_NOGO)), "p90": float(np.percentile(e, PERCENTILE_REF_GO)),
           "p95": float(np.percentile(e, 95)), "esperance_par_trade": float(np.mean(tous_r)),
           "esperances": [float(x) for x in e]}
    if esperance_strategie is not None:
        res["percentile_strategie"] = float(100.0 * ((e < esperance_strategie).mean()
                                                     + 0.5 * (e == esperance_strategie).mean()))
    return res


# --------------------------------------------------------------------------- IS / OOS, sensibilité

def date_coupure(debut, fin, part: float = PART_IS) -> pd.Timestamp:
    """Coupure IS/OOS : debut + part × (fin - debut), arrondie à minuit (jour entier)."""
    d, f = pd.Timestamp(debut), pd.Timestamp(fin)
    return (d + (f - d) * part).normalize()


def _esp(res: ResultatBacktest) -> Optional[float]:
    return _f(res.trades["r_multiple"].mean()) if len(res.trades) else None


def executer_is_oos(m1, m15, h1, cfg, spec, balance, debut, fin, resolution, spread_plancher=None,
                    signaux=None) -> dict:
    """Deux backtests indépendants (balance initiale chacun) : [debut, coupure[ et [coupure, fin[."""
    coupure = date_coupure(debut, fin)
    res = {"coupure": str(coupure)}
    for nom, (d, f) in (("is", (debut, coupure)), ("oos", (coupure, fin))):
        r = executer_backtest(m1, m15, h1, cfg, spec, balance, d, f, resolution, signaux=signaux,
                              spread_plancher=spread_plancher, arret_definitif_actif=False)
        res[nom] = resumer_resultat(r)
        res[nom]["_r"] = r.trades["r_multiple"].to_numpy(dtype=float).tolist()
    return res


def configurations_sensibilite(cfg) -> list:
    """(groupe, libellé, config) de la grille de la spec §6."""
    ex = cfg.execution
    lignes = []
    for mode in GRILLE_MODE_ENTREE:
        for sl in GRILLE_SL_PLAFOND:
            lignes.append(("sl_plafond x mode_entree", f"sl_plafond={sl:g}, {mode}",
                           cfg.avec(sl_plafond=sl, mode_entree=mode)))
    for v in GRILLE_VALIDITE:
        lignes.append(("validite_setup_barres", f"validite={v}", cfg.avec(validite_setup_barres=v)))
    for sp in GRILLE_SPREAD_MAX:
        lignes.append(("spread_max", f"spread_max={sp:.2f}", cfg.avec(spread_max=sp)))
    lignes.append(("couts", "coûts doublés", cfg.avec(glissement_entree=2 * ex.glissement_entree,
                                                       glissement_stop=2 * ex.glissement_stop)))
    return lignes


def executer_sensibilite(m1, m15, h1, cfg, spec, balance, debut, fin, resolution, spread_plancher=None,
                         is_oos_base: Optional[dict] = None) -> list:
    """Chaque configuration de la grille, en IS et en OOS séparés (même coupure que l'IS/OOS)."""
    cache: dict = {}
    if is_oos_base is not None:
        cache[repr(cfg)] = is_oos_base
    lignes = []
    for groupe, libelle, c in configurations_sensibilite(cfg):
        cle = repr(c)
        if cle not in cache:
            cache[cle] = executer_is_oos(m1, m15, h1, c, spec, balance, debut, fin, resolution, spread_plancher)
        io = cache[cle]
        r_tous = np.asarray(io["is"]["_r"] + io["oos"]["_r"], dtype=float)
        lignes.append({
            "groupe": groupe, "libelle": libelle, "sl_plafond": c.strategie.sl_plafond,
            "mode_entree": c.strategie.mode_entree, "est_base": cle == repr(cfg),
            "nb_is": io["is"]["nb_trades"], "nb_oos": io["oos"]["nb_trades"],
            "esp_is": io["is"]["esperance_r"], "esp_oos": io["oos"]["esperance_r"],
            "pf_oos": io["oos"]["profit_factor"],
            "esp_total": _f(r_tous.mean()) if len(r_tous) else None,
            "dd_is": io["is"]["dd_max_pct"], "dd_oos": io["oos"]["dd_max_pct"],
            "arret_is": io["is"]["arret_definitif"], "arret_oos": io["oos"]["arret_definitif"],
        })
    return lignes


# --------------------------------------------------------------------------- Monte Carlo

def monte_carlo(r: np.ndarray, risque_pct: float, permutations: int = PERMUTATIONS_MONTE_CARLO,
                graine: int = GRAINE_MONTE_CARLO, fractions_risque=None) -> dict:
    """Permutations de la séquence des R (spec §6) : distribution du drawdown max et du rendement final.

    Equity composée : E_k = E_{k-1} × (1 + R_k × risque_pct / 100), drawdown sur
    l'equity après chaque trade. Le rendement final d'une permutation est
    identique pour toutes (produit commutatif) : on l'indique, et on ajoute à
    titre d'information un bootstrap (tirage avec remise) pour sa dispersion.
    """
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return {"disponible": False, "raison": "aucun trade"}
    # Audit 2026-11-13 : si fournies, les fractions de risque RÉELLES de chaque trade
    # (risque engagé / balance avant le trade) remplacent le risque nominal, permutées
    # avec leur R (le plafond de levier réduit souvent le risque sous 1 %).
    if fractions_risque is not None:
        f = np.asarray(fractions_risque, dtype=float)
        if f.shape != r.shape or not np.isfinite(f).all():
            raise ValueError("monte_carlo : fractions_risque invalides")
        risque_pct = float(np.mean(f) * 100.0)
    else:
        f = float(risque_pct) / 100.0
    rng = np.random.default_rng(int(graine))
    facteurs = np.maximum(1.0 + r * f, 1e-12)

    def stats(matrice):
        eq = np.cumprod(matrice, axis=1)
        eq = np.concatenate([np.ones((eq.shape[0], 1)), eq], axis=1)
        pic = np.maximum.accumulate(eq, axis=1)
        dd = ((pic - eq) / pic).max(axis=1) * 100
        return dd, (eq[:, -1] - 1) * 100

    perm = np.stack([facteurs[rng.permutation(len(r))] for _ in range(int(permutations))])
    dd, fin = stats(perm)
    boot = facteurs[rng.integers(0, len(r), size=(int(permutations), len(r)))]
    dd_b, fin_b = stats(boot)
    pct = lambda x, q: float(np.percentile(x, q))
    return {"disponible": True, "permutations": int(permutations), "graine": int(graine),
            "risque_pct": float(risque_pct), "nb_trades": int(len(r)),
            "dd_p5": pct(dd, 5), "dd_p50": pct(dd, 50), "dd_p95": pct(dd, 95), "dd_max": float(dd.max()),
            "rendement_final_pct": float(fin[0]),
            "bootstrap_rendement_p5": pct(fin_b, 5), "bootstrap_rendement_p50": pct(fin_b, 50),
            "bootstrap_rendement_p95": pct(fin_b, 95), "bootstrap_dd_p95": pct(dd_b, 95),
            "bootstrap_proba_perte": float((fin_b < 0).mean())}


# --------------------------------------------------------------------------- verdict

def _critere(numero, nom, valeur, seuil, ok, detail=""):
    return {"numero": numero, "nom": nom, "valeur": valeur, "seuil": seuil,
            "ok": None if ok is None else bool(ok), "detail": detail}


def _fmt(x, d=2, suffixe=""):
    if x is None:
        return "n.d."
    if isinstance(x, float) and math.isinf(x):
        return "infini"
    return f"{x:.{d}f}{suffixe}"


def calculer_verdict(resume: dict) -> dict:
    """Verdict GO / NO-GO / À CREUSER (spec §6), avec chaque critère (valeur, seuil, OK/KO).

    Règles (pré-enregistrées) :
    GO si les 6 critères sont remplis. NO-GO si l'espérance OOS <= 0 ou si
    l'espérance est sous le 75e percentile de la référence « tendance seule ».
    Sinon À CREUSER. Choix prudents signalés : une valeur non calculable
    (section manquante, aucun trade) rend le critère KO ; sans aucun trade OOS,
    l'espérance OOS est traitée comme <= 0 (NO-GO). Si des sections manquent et
    qu'aucune condition de NO-GO n'est établie, le verdict est INCOMPLET.
    """
    base = resume.get("base") or {}
    isoos = resume.get("isoos") or {}
    ref = (resume.get("references") or {}).get("tendance_seule") or {}
    mc = resume.get("montecarlo") or {}
    sens = resume.get("sensibilite")
    oos = isoos.get("oos") or {}
    manquantes = [s for s in ("base", "references", "isoos", "sensibilite", "montecarlo") if not resume.get(s)]

    n_total = base.get("nb_trades")
    n_oos = oos.get("nb_trades")
    esp_oos = oos.get("esperance_r")
    pf_oos = oos.get("profit_factor")
    esp_tot = base.get("esperance_r")
    dd = base.get("dd_max_pct")
    dd_mc = mc.get("dd_p95") if mc.get("disponible") else None
    p90 = ref.get("p90") if ref.get("disponible") else None
    p75 = ref.get("p75") if ref.get("disponible") else None

    criteres = []
    ok1 = None if n_total is None or n_oos is None else (n_total >= SEUIL_TRADES_TOTAL and n_oos >= SEUIL_TRADES_OOS)
    criteres.append(_critere(1, "Nombre de trades (total / hors échantillon)",
                             f"{n_total if n_total is not None else 'n.d.'} / {n_oos if n_oos is not None else 'n.d.'}",
                             f">= {SEUIL_TRADES_TOTAL} / >= {SEUIL_TRADES_OOS}", ok1))
    ok2 = None if esp_oos is None else esp_oos >= SEUIL_ESPERANCE_OOS
    criteres.append(_critere(2, "Espérance hors échantillon (OOS), après coûts", _fmt(esp_oos, 3, " R"),
                             f">= +{SEUIL_ESPERANCE_OOS:.2f} R", ok2))
    ok3 = None if pf_oos is None else pf_oos >= SEUIL_PF_OOS
    criteres.append(_critere(3, "Profit factor hors échantillon", _fmt(pf_oos, 2), f">= {SEUIL_PF_OOS}", ok3))
    ok4 = None if dd is None or dd_mc is None else (dd <= SEUIL_DD_MAX and dd_mc <= SEUIL_DD_MC_P95)
    criteres.append(_critere(4, "Drawdown max (période) / 95e percentile Monte Carlo",
                             f"{_fmt(dd, 1, ' %')} / {_fmt(dd_mc, 1, ' %')}",
                             f"<= {SEUIL_DD_MAX:.0f} % / <= {SEUIL_DD_MC_P95:.0f} %", ok4))
    ok5 = None if esp_tot is None or p90 is None else esp_tot > p90
    criteres.append(_critere(5, "Espérance au-dessus du 90e percentile de « tendance seule »",
                             f"{_fmt(esp_tot, 3, ' R')} (p90 = {_fmt(p90, 3, ' R')})", "> p90", ok5))
    ok6, val6 = None, "n.d."
    if sens:
        plafonds = [l for l in sens if l["mode_entree"] == "bord" and l["groupe"] == "sl_plafond x mode_entree"]
        positifs = sum(1 for l in plafonds if l["esp_is"] is not None and l["esp_oos"] is not None
                       and l["esp_is"] > 0 and l["esp_oos"] > 0)
        couts = next((l for l in sens if l["groupe"] == "couts"), None)
        couts_ok = bool(couts and couts["esp_is"] is not None and couts["esp_oos"] is not None
                        and couts["esp_is"] > 0 and couts["esp_oos"] > 0)
        ok6 = positifs >= SEUIL_PLAFONDS_POSITIFS and couts_ok
        val6 = f"plafonds de SL : {positifs}/4 ; coûts doublés : {'oui' if couts_ok else 'non'}"
    criteres.append(_critere(6, "Robustesse : espérance > 0 en IS et en OOS pour les plafonds de SL 3/5/8/12 $ (mode bord) et avec coûts doublés",
                             val6, f">= {SEUIL_PLAFONDS_POSITIFS}/4 plafonds ; coûts doublés : oui", ok6))

    nogo_raisons = []
    if isoos:
        if n_oos == 0 or esp_oos is None:
            nogo_raisons.append("aucun trade hors échantillon (espérance OOS non mesurable, traitée comme <= 0)")
        elif esp_oos <= 0:
            nogo_raisons.append(f"espérance hors échantillon <= 0 ({esp_oos:+.3f} R)")
    if esp_tot is not None and p75 is not None and esp_tot < p75:
        nogo_raisons.append(f"espérance ({esp_tot:+.3f} R) sous le 75e percentile de la référence ({p75:+.3f} R)")
    if base and n_total == 0:
        nogo_raisons.append("aucun trade sur la période")

    if nogo_raisons:
        decision = "NO-GO"
    elif manquantes:
        decision = "INCOMPLET"
    elif all(c["ok"] for c in criteres):
        decision = "GO"
    else:
        decision = "À CREUSER"
    return {"decision": decision, "criteres": criteres, "raisons_nogo": nogo_raisons,
            "sections_manquantes": manquantes}


# --------------------------------------------------------------------------- graphiques

def tracer_graphiques(equity_jour: pd.Series, dossier, buy_hold: Optional[pd.Series] = None,
                      balance_initiale: float = 3000.0, titre: str = "", date_arret=None) -> None:
    """equity.png et drawdown.png (matplotlib, backend Agg). `date_arret` : trait vertical à l'arrêt définitif."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path
    dossier = Path(dossier)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(equity_jour.index, equity_jour.values, color="#1f5fa8", lw=1.4, label="Stratégie (equity)")
    if buy_hold is not None and len(buy_hold):
        bh = buy_hold / buy_hold.iloc[0] * balance_initiale
        ax.plot(bh.index, bh.values, color="#c9a227", lw=1.0, alpha=0.8, label="Or acheté et conservé (même capital)")
    ax.axhline(balance_initiale, color="grey", lw=0.8, ls="--")
    if date_arret is not None:
        ax.axvline(pd.Timestamp(date_arret), color="#b23a3a", lw=1.0, ls=":", label="arrêt définitif (-15 %)")
    ax.set_title(f"Évolution du capital {titre}".strip())
    ax.set_ylabel("USD")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(dossier / "equity.png", dpi=110)
    plt.close(fig)

    e = equity_jour.to_numpy(dtype=float)
    dd = -(np.maximum.accumulate(e) - e) / np.maximum.accumulate(e) * 100 if len(e) else e
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.fill_between(equity_jour.index, dd, 0, color="#b23a3a", alpha=0.6)
    ax.axhline(-SEUIL_DD_MAX, color="black", lw=0.8, ls="--", label=f"limite d'arrêt -{SEUIL_DD_MAX:.0f} %")
    if date_arret is not None:
        ax.axvline(pd.Timestamp(date_arret), color="black", lw=1.0, ls=":", label="arrêt définitif")
    ax.set_title(f"Baisse depuis le plus haut (drawdown, fin de journée) {titre}".strip())
    ax.set_ylabel("%")
    ax.legend(loc="lower left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(dossier / "drawdown.png", dpi=110)
    plt.close(fig)


# --------------------------------------------------------------------------- rapport

def _usd(x) -> str:
    """Montant arrondi au dollar, milliers séparés par une espace : 3 000."""
    return "n.d." if x is None else f"{x:,.0f}".replace(",", " ")


def _ligne(*cellules):
    return "| " + " | ".join(str(c) for c in cellules) + " |"


def _pct(x, d=1):
    return _fmt(None if x is None else x * 100, d, " %")


def _tableau_ventilation(lignes, titre_cle):
    if not lignes:
        return ["_aucun trade_", ""]
    out = [_ligne(titre_cle, "trades", "réussite", "espérance (R)", "total (R)", "P&L ($)"),
           _ligne("---", "---:", "---:", "---:", "---:", "---:")]
    for l in lignes:
        out.append(_ligne(l["cle"], l["nb"], _pct(l["taux_reussite"], 0), _fmt(l["esperance_r"], 3),
                          _fmt(l["r_total"], 1), _fmt(l["pnl_total"], 2)))
    return out + [""]


LIBELLES_SORTIE = {"stop": "stop touché (perte)", "stop_breakeven": "runner sorti au point d'entrée",
                   "cloture_forcee": "clôture forcée 21h55", "arret_definitif": "arrêt définitif (-15 %)",
                   "fin_donnees": "fin des données", "tp1": "TP1"}

EXPLICATION_VERDICT = {
    "GO": "Tous les critères fixés à l'avance sont remplis. Cela autorise seulement l'étape suivante "
          "(paper trading pendant au moins 4 semaines), pas l'argent réel.",
    "NO-GO": "La stratégie ne montre pas d'avantage exploitable. Elle retourne en recherche ; on n'engage pas d'argent.",
    "À CREUSER": "Ni preuve d'avantage, ni échec net : certains critères ne sont pas remplis. "
                 "On n'engage pas d'argent ; il faut comprendre pourquoi avant toute suite.",
    "INCOMPLET": "Toutes les sections n'ont pas été calculées : le verdict n'est pas encore rendu.",
}


def rediger_rapport(resume: dict) -> str:
    """Rapport Markdown en français à partir de `resume` (contenu de resume.json)."""
    meta = resume.get("meta", {})
    base = resume.get("base")
    verdict = resume.get("verdict") or calculer_verdict(resume)
    io = resume.get("isoos")
    refs = resume.get("references") or {}
    mc = resume.get("montecarlo")
    sens = resume.get("sensibilite")
    L = []
    if meta.get("synthetique"):
        L += ["# ⚠ DONNÉES SYNTHÉTIQUES — ce rapport ne dit rien sur la rentabilité réelle",
              "",
              "> Les prix de ce rapport sont une **marche aléatoire générée par ordinateur** (graine "
              f"{meta.get('graine')}), sans aucun avantage exploitable. Il sert uniquement à vérifier que le "
              "moteur de backtest fonctionne et qu'il ne « trouve » pas de gains là où il n'y en a pas.",
              ""]
    L += [f"# Rapport de backtest SentiTrade — {meta.get('symbole', 'XAUUSD')}", "",
          f"_Généré le {meta.get('genere_le', '')} — source : {meta.get('source', '')}_", ""]

    # ---- résumé en langage simple
    d = verdict["decision"]
    L += ["## En bref", "", f"**Verdict : {d}.** {EXPLICATION_VERDICT.get(d, '')}", ""]
    if verdict.get("raisons_nogo"):
        L += ["Raisons du NO-GO : " + " ; ".join(verdict["raisons_nogo"]) + ".", ""]
    if base:
        n = base["nb_trades"]
        puces = [f"Période simulée : du {base['debut'][:10]} au {base['fin'][:10]}, capital de départ "
                 f"{_usd(base['balance_initiale'])} $."]
        if n:
            puces.append(f"{n} trades, dont {_pct(base['taux_reussite'], 0)} gagnants. En moyenne, un trade a "
                         f"rapporté {base['esperance_r']:+.2f} fois le montant risqué ({base['esperance_usd']:+.2f} $).")
        else:
            puces.append("Aucun trade sur la période.")
        puces.append(f"Résultat : {base['rendement_total_pct']:+.1f} % au total "
                     f"(capital final {_usd(base['balance_finale'])} $), pire baisse depuis un plus haut "
                     f"{base['dd_max_pct']:.1f} %.")
        bh = refs.get("buy_and_hold")
        if bh and bh.get("rendement_pct") is not None:
            puces.append(f"Pour comparer, acheter de l'or et le garder aurait donné {bh['rendement_pct']:+.1f} % "
                         f"(pire baisse {bh['dd_max_pct']:.1f} %).")
        ts = refs.get("tendance_seule") or {}
        if ts.get("disponible") and ts.get("percentile_strategie") is not None:
            puces.append(f"Face à des entrées tirées au hasard dans le sens de la tendance (même gestion), la "
                         f"stratégie fait mieux que {ts['percentile_strategie']:.0f} % des tirages "
                         f"(il faudrait plus de 90 % pour un GO).")
        if base.get("arret_definitif"):
            puces.append(f"**Le compte a atteint la limite de -15 % depuis son plus haut** "
                         f"({(base.get('date_arret') or '')[:10]}) : le bot réel se serait arrêté ce jour-là."
                         + (" Pour juger la stratégie sur toute la période, le backtest a continué au-delà."
                            if base.get("mode_evaluation") else ""))
        if n and n < 100:
            puces.append(f"**Moins de 100 trades : résultat non significatif statistiquement.**")
        trop_beau = []
        if base.get("sharpe_journalier") is not None and base["sharpe_journalier"] > 3:
            trop_beau.append(f"Sharpe {base['sharpe_journalier']:.1f} > 3")
        if base.get("nb_mois", 0) >= 3 and base.get("nb_mois_perdants") == 0:
            trop_beau.append("aucun mois perdant")
        if trop_beau:
            puces.append("**Résultat « trop beau » (" + ", ".join(trop_beau) + ") : présumé faux jusqu'à preuve "
                         "du contraire (anticipation, frais oubliés, surapprentissage).**")
        L += [f"- {p}" for p in puces] + [""]
    L += ["Rappel : un backtest ne garantit rien. Même un GO ne mène qu'au paper trading "
          "(docs/GARDE_FOUS.md §1).", ""]

    # ---- verdict détaillé
    L += ["## Verdict : critères fixés à l'avance (spec §6)", "",
          _ligne("n°", "critère", "valeur", "seuil", "résultat"), _ligne("---", "---", "---", "---", "---")]
    for c in verdict["criteres"]:
        r = "OK" if c["ok"] else ("KO" if c["ok"] is False else "KO (non calculé)")
        L.append(_ligne(c["numero"], c["nom"], c["valeur"], c["seuil"], r))
    L += ["", "Règle : **GO** si les 6 critères sont OK ; **NO-GO** si l'espérance OOS est <= 0 ou sous le 75e "
          "percentile de la référence « tendance seule » ; sinon **À CREUSER**.", ""]
    if verdict.get("sections_manquantes"):
        L += ["Sections non calculées : " + ", ".join(verdict["sections_manquantes"]) + ".", ""]

    # ---- paramètres
    if meta:
        ex, ri, st = meta.get("execution", {}), meta.get("risque", {}), meta.get("strategie", {})
        L += ["## Conditions du test", "",
              f"- Période : {meta.get('debut', '')[:10]} → {meta.get('fin', '')[:10]} (fin exclue) ; indicateurs "
              "calculés sur tout l'historique disponible, y compris avant la période.",
              f"- Résolution d'exécution : **{(meta.get('resolution') or '').upper()}**"
              + ("" if meta.get("resolution") == "m1" else " — les données M1 ne couvrent pas la période : "
                 "exécution sur bougies M15, moins précise (ordre des prix dans la bougie inconnu)."),
              f"- Capital initial : {_usd(meta.get('balance_initiale', 3000))} $ (compte en USD).",
              f"- Coûts : spread réel de chaque bougie"
              + (f", avec un plancher par heure ({meta.get('spread_plancher_source')})" if meta.get("spread_plancher") else "")
              + f" ; glissement à l'entrée et sur TP1/clôture {ex.get('glissement_entree')} $ ; glissement sur stop "
              f"{ex.get('glissement_stop')} $ ; commission {ex.get('commission_par_lot')} $ par lot aller-retour. "
              "Pas de swap (positions fermées le jour même).",
              f"- Risque : {ri.get('risque_par_trade_pct')} % par trade, perte journalière max "
              f"{ri.get('perte_jour_max_pct')} %, arrêt à {ri.get('drawdown_max_pct')} % de drawdown, levier effectif "
              f"max {ri.get('levier_effectif_max')}.",
              f"- Stratégie : EMA {st.get('ema_periode')} H1, entrées {st.get('debut_session')}-{st.get('derniere_entree')}, "
              f"clôture {st.get('cloture_forcee')}, entrée « {st.get('mode_entree')} », SL plafonné à "
              f"{st.get('sl_plafond')} $, TP1 à {st.get('tp1_r')} R ({st.get('tp1_fraction')} de la position), setup "
              f"valable {st.get('validite_setup_barres')} bougies M15, spread max {st.get('spread_max')} $.", ""]

    # ---- résultats détaillés
    if base:
        L += ["## Résultats détaillés (période complète)", "",
              _ligne("mesure", "valeur"), _ligne("---", "---:")]
        rows = [("Nombre de trades", base["nb_trades"]),
                ("Taux de réussite", _pct(base.get("taux_reussite"))),
                ("Gain moyen (trades gagnants)", _fmt(base.get("gain_moyen_r"), 3, " R")),
                ("Perte moyenne (trades perdants)", _fmt(base.get("perte_moyenne_r"), 3, " R")),
                ("Espérance par trade", f"{_fmt(base.get('esperance_r'), 3, ' R')} / {_fmt(base.get('esperance_usd'), 2, ' $')}"),
                ("t de Student de l'espérance", _fmt(base.get("t_stat"), 2)),
                ("Profit factor", _fmt(base.get("profit_factor"), 2)),
                ("Rendement total", _fmt(base.get("rendement_total_pct"), 1, " %")),
                ("Rendement annualisé (CAGR)", _fmt(base.get("cagr_pct"), 1, " %")),
                ("Drawdown max", f"{_fmt(base.get('dd_max_pct'), 1, ' %')} ({_fmt(base.get('dd_max_usd'), 0, ' $')})"),
                ("Plus longue période sous le plus haut", _fmt(base.get("dd_duree_jours"), 0, " jours")),
                ("Plus longue série de trades perdants", base.get("serie_perdante_max")),
                ("Sharpe (journalier, annualisé)", _fmt(base.get("sharpe_journalier"), 2)),
                ("Mois perdants / mois avec trades", f"{base.get('nb_mois_perdants')} / {base.get('nb_mois')}"),
                ("Arrêt définitif (-15 %)", "oui, le " + (base.get("date_arret") or "")[:10] if base.get("arret_definitif") else "non")]
        L += [_ligne(a, b) for a, b in rows] + [""]
        v = base.get("ventilations", {})
        for cle, titre, entete in (("annee", "Par année", "année"), ("mois", "Par mois", "mois"),
                                   ("sens", "Long / short", "sens"),
                                   ("heure", "Par heure d'entrée (heure serveur)", "heure"),
                                   ("raison_sortie", "Par raison de sortie", "sortie")):
            lignes = v.get(cle, [])
            if cle == "raison_sortie":
                lignes = [{**l, "cle": LIBELLES_SORTIE.get(l["cle"], l["cle"])} for l in lignes]
            L += [f"### {titre}", ""] + _tableau_ventilation(lignes, entete)
        ev = base.get("evenements", {})
        stt = base.get("stats", {})
        L += ["### Setups, rejets et blocages", "",
              f"- Setups créés : {ev.get('nouveaux', 0)} ; remplacés par un FVG plus récent : {ev.get('remplacements', 0)} ; "
              f"entrées : {ev.get('entrees', 0)}.",
              f"- FVG rejetés (dans le sens de la tendance, en session) : "
              + (", ".join(f"{k} {v}" for k, v in ev.get("rejets", {}).items()) or "aucun") + ".",
              f"- Setups annulés : " + (", ".join(f"{k} {v}" for k, v in ev.get("annulations", {}).items()) or "aucun") + ".",
              f"- Entrées annulées car le spread dépassait le maximum au moment du toucher (CDC §3.4) : {ev.get('attentes_spread', 0)}.",
              f"- TP1 atteint sans fermeture partielle possible (lot indivisible, SL passé au point d'entrée) : "
              f"{ev.get('tp1_sans_partiel', 0)}.",
              f"- Jours de semaine bloqués par le filtre ADR : {stt.get('jours_bloques_adr', 'n.d.')} sur "
              f"{stt.get('jours_trades_possibles', 'n.d.')} ; journées bloquées par la perte journalière max : "
              f"{stt.get('jours_bloques_perte_jour', 0)}.", ""]

    # ---- références
    L += ["## Comparaison avec deux références", ""]
    bh = refs.get("buy_and_hold")
    if bh and bh.get("rendement_pct") is not None:
        L += [f"**Achat-conservation de l'or** sur la même période : {bh['rendement_pct']:+.1f} % "
              f"(de {bh['prix_debut']:.2f} à {bh['prix_fin']:.2f}), drawdown max {bh['dd_max_pct']:.1f} %. "
              "Sans levier ; la stratégie, elle, est à levier et ne garde jamais de position la nuit.", ""]
    ts = refs.get("tendance_seule")
    if ts and ts.get("disponible"):
        L += [f"**« Tendance seule »** ({ts['tirages']} tirages de {ts['trades_par_tirage']} trades, graine "
              f"{ts['graine']}) : entrées au marché à des clôtures M15 tirées au hasard en session, dans le sens de la "
              "tendance H1, SL tiré parmi les distances de SL de la stratégie, mêmes sorties, même risque.", "",
              _ligne("espérance par tirage", "valeur"), _ligne("---", "---:"),
              _ligne("médiane", _fmt(ts["p50"], 3, " R")), _ligne("75e percentile", _fmt(ts["p75"], 3, " R")),
              _ligne("90e percentile", _fmt(ts["p90"], 3, " R")),
              _ligne("stratégie", _fmt(base.get("esperance_r") if base else None, 3, " R")),
              _ligne("percentile de la stratégie", _fmt(ts.get("percentile_strategie"), 0, " %")), ""]
    elif ts:
        L += [f"« Tendance seule » : non calculée ({ts.get('raison', '')}).", ""]
    else:
        L += ["« Tendance seule » : section non calculée.", ""]

    # ---- IS/OOS
    L += ["## Dans l'échantillon / hors échantillon (60 % / 40 %)", ""]
    if io:
        L += [f"Coupure le {io['coupure'][:10]}. Deux simulations indépendantes, chacune avec {_usd(base['balance_initiale'] if base else 3000)} $ "
              "au départ. Aucun paramètre n'a été optimisé.", "",
              _ligne("mesure", "IS (60 % initiaux)", "OOS (40 % finaux)"), _ligne("---", "---:", "---:")]
        a, b = io["is"], io["oos"]
        for nom, cle, d_, suf in (("Trades", "nb_trades", 0, ""), ("Taux de réussite", "taux_reussite", None, ""),
                                  ("Espérance (R)", "esperance_r", 3, ""), ("Espérance ($)", "esperance_usd", 2, ""),
                                  ("Profit factor", "profit_factor", 2, ""), ("Rendement", "rendement_total_pct", 1, " %"),
                                  ("Drawdown max", "dd_max_pct", 1, " %"), ("Sharpe", "sharpe_journalier", 2, "")):
            if d_ is None:
                L.append(_ligne(nom, _pct(a.get(cle)), _pct(b.get(cle))))
            elif d_ == 0:
                L.append(_ligne(nom, a.get(cle), b.get(cle)))
            else:
                L.append(_ligne(nom, _fmt(a.get(cle), d_, suf), _fmt(b.get(cle), d_, suf)))
        L.append(_ligne("Arrêt définitif", "oui" if a.get("arret_definitif") else "non",
                        "oui" if b.get("arret_definitif") else "non"))
        L.append("")
    else:
        L += ["Section non calculée.", ""]

    # ---- sensibilité
    L += ["## Sensibilité aux paramètres (pour information)", "",
          "On ne choisit pas « le meilleur » réglage : une stratégie solide reste correcte quand on bouge un peu ses "
          "paramètres. Chaque ligne = deux simulations (IS et OOS) ; `*` = réglage de base.", ""]
    if sens:
        L += [_ligne("réglage", "trades IS", "trades OOS", "espérance IS (R)", "espérance OOS (R)", "PF OOS",
                     "espérance totale (R)", "arrêt -15 %"),
              _ligne("---", "---:", "---:", "---:", "---:", "---:", "---:", "---")]
        for l in sens:
            arret = ", ".join(x for x, f in (("IS", l["arret_is"]), ("OOS", l["arret_oos"])) if f) or "non"
            L.append(_ligne(("* " if l["est_base"] else "") + l["libelle"], l["nb_is"], l["nb_oos"],
                            _fmt(l["esp_is"], 3), _fmt(l["esp_oos"], 3), _fmt(l["pf_oos"], 2),
                            _fmt(l["esp_total"], 3), arret))
        L.append("")
    else:
        L += ["Section non calculée.", ""]

    # ---- Monte Carlo
    L += ["## Monte Carlo (ordre des trades)", ""]
    if mc and mc.get("disponible"):
        L += [f"{mc['permutations']} permutations de la séquence des {mc['nb_trades']} R obtenus (risque "
              f"{mc['risque_pct']} % par trade, capital composé, graine {mc['graine']}). Cela montre la baisse "
              "qu'on aurait pu subir avec les mêmes trades dans un autre ordre.", "",
              _ligne("drawdown max", "valeur"), _ligne("---", "---:"),
              _ligne("médiane", _fmt(mc["dd_p50"], 1, " %")), _ligne("95e percentile", _fmt(mc["dd_p95"], 1, " %")),
              _ligne("pire cas", _fmt(mc["dd_max"], 1, " %")), "",
              f"Le rendement final est le même pour toutes les permutations ({mc['rendement_final_pct']:+.1f} %). "
              f"À titre d'information, un tirage avec remise (bootstrap) donne un rendement final entre "
              f"{mc['bootstrap_rendement_p5']:+.1f} % et {mc['bootstrap_rendement_p95']:+.1f} % (5e-95e percentiles), "
              f"avec {mc['bootstrap_proba_perte'] * 100:.0f} % de chances de finir en perte.", ""]
    elif mc:
        L += [f"Non calculé ({mc.get('raison', '')}).", ""]
    else:
        L += ["Section non calculée.", ""]

    # ---- hypothèses
    L += ["## Hypothèses de simulation (prudentes) et limites", "",
          "- Aucune anticipation : un signal à la clôture d'une bougie M15 n'est exécutable qu'à partir de la bougie "
          "suivante ; tendance H1 et filtre ADR n'utilisent que des bougies clôturées.",
          "- Entrée au marché par le bot quand le prix touche le niveau (Ask pour un achat, Bid pour une vente), au niveau ou "
          "à l'ouverture si le prix a sauté au-delà, plus le glissement.",
          "- Dans une même bougie, si le stop et le TP1 sont tous deux possibles, on suppose que le **stop** est touché "
          "d'abord. Le TP1 n'est jamais pris sur la bougie d'entrée ; le stop, si.",
          "- Le stop au point d'entrée posé après TP1 n'est actif qu'à partir de la bougie suivante.",
          "- Un gap au-delà du stop sort au prix d'ouverture (pire que le stop), plus le glissement.",
          "- Si le prix d'entrée réel est déjà au-delà du stop au moment du toucher, le setup est annulé (le broker "
          "refuserait l'ordre).",
          "- La garde de risque voit l'equity au pire prix de chaque bougie, puis à la clôture. Après un arrêt définitif, "
          "la position est fermée à l'ouverture de la bougie suivante et plus rien n'est tradé.",
          "- Le R d'un trade = résultat / (lots × perte par lot si le stop est touché, commission comprise).",
          "- Limites : pas de requotes ni de refus d'ordre, pas de latence au-delà du glissement fixe, spread de la "
          "bougie supposé valable toute la bougie, pas de swap ni de frais de financement, données du broker "
          "supposées exactes. En résolution M15, l'ordre des prix dans la bougie est inconnu.", ""]
    temps = resume.get("temps", {})
    if temps:
        L += ["## Temps de calcul", "", _ligne("section", "secondes"), _ligne("---", "---:")]
        L += [_ligne(k, f"{v:.1f}") for k, v in temps.items()] + [""]
    return "\n".join(L)
