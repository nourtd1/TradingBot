"""Métriques, références, robustesse, petit capital et verdicts (RECHERCHE_PLAN §6-7).

Les seuils de §7 sont recopiés tels quels dans `SEUILS` et ne doivent JAMAIS être assouplis.
Une valeur manquante (section non calculée, aucune donnée) rend le critère KO : on ne retient
jamais une hypothèse sur un critère non vérifié.

Définitions (interprétations prudentes, signalées dans le rapport) :
- rendements journaliers : variation de l'equity de clôture entre deux jours de cotation
  consécutifs du calendrier unifié (le premier par rapport au capital initial) ;
- annualisation : √(nombre d'observations par an), mesuré sur la période (≈ 252 sans crypto,
  ≈ 365 avec) ; Sharpe sans taux sans risque (plus exigeant quand les taux sont positifs) ;
- t-stat = moyenne / écart-type (ddof = 1) × √n ;
- drawdown « au pire prix » : (plus haut de l'equity de clôture jusqu'à la veille - equity au
  pire prix du jour) / ce plus haut, combiné au drawdown de clôture ;
- année civile complète : l'évaluation couvre le 1er janvier (début au plus tard le 5 janvier,
  ou equity connue l'année précédente) et la fin au moins le 24 décembre ;
- « au moins la moitié des symboles contribuent positivement » : sur TOUS les symboles simulés
  de la stratégie (un symbole sans trade ne compte pas comme positif) ;
- référence passive : panier équipondéré achat-conservation des mêmes symboles (rééquilibré
  chaque jour, rendements des prix SANS frais ni swap : référence plus exigeante), même
  calendrier ; « même risque » = mis à la volatilité de la stratégie, ce qui ne change pas son
  Sharpe ; on compare les Sharpe (stratégie strictement meilleure). S3 : Sharpe de US500 seul ;
- capital minimum (§6) : pour chaque signal, capital nécessaire pour prendre le lot MINIMUM avec
  un risque ≤ 2 % ET un levier ≤ 10 ; le minimum est le plus petit capital qui couvre au moins 95 %
  des signaux ;
- bootstrap par blocs de 20 jours : 5000 tirages de 12 mois de rendements journaliers du
  développement, blocs contigus tirés uniformément avec remise ; on garde le 5e centile.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

SEUILS = {
    "annees_min_d1": 8.0, "annees_min_s4": 4.0, "trades_min": 100,
    "sharpe_min": 0.5, "tstat_min": 2.5, "dd_max_pct": 15.0, "annees_positives_min_pct": 60.0,
    "sharpe_variantes_min": 0.3, "sharpe_couts_doubles_min": 0.3, "part_symboles_positifs_min": 0.5,
    "controle_dd_max_pct": 15.0, "controle_percentile": 5.0,
}
RISQUE_MAX_PETIT_CAPITAL = 0.02
LEVIER_PETIT_CAPITAL = 10.0
PART_SIGNAUX = 0.95
BLOC_BOOTSTRAP = 20
TIRAGES_BOOTSTRAP = 5000
GRAINE_BOOTSTRAP = 20261113


def _f(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def rendements(equity: pd.DataFrame, capital: float) -> pd.Series:
    e = equity["equity"]
    return e / e.shift(1).fillna(capital) - 1.0


def annees(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 0.0
    return (index[-1] - index[0]).days / 365.25


def drawdowns(equity: pd.DataFrame, capital: float) -> tuple:
    """(dd de clôture max %, dd au pire prix max %, date du pire)."""
    if not len(equity):
        return None, None, None
    e = equity["equity"].to_numpy(dtype=float)
    p = equity["equity_pire"].to_numpy(dtype=float)
    pic = np.maximum.accumulate(np.concatenate([[capital], e]))
    dd_c = (pic[1:] - e) / pic[1:]
    dd_p = (pic[:-1] - p) / pic[:-1]
    dd = np.maximum(dd_c, dd_p)
    k = int(np.argmax(dd))
    return float(dd_c.max() * 100), float(dd.max() * 100), equity.index[k]


def annees_civiles(equity: pd.DataFrame, capital: float) -> dict:
    """{année: rendement} sur les années civiles complètes."""
    if not len(equity):
        return {}
    e = equity["equity"]
    fin_annee = e.groupby(e.index.year).last()
    debut, fin = e.index[0], e.index[-1]
    out = {}
    for y in fin_annee.index:
        if y == fin.year and fin < pd.Timestamp(year=y, month=12, day=24):
            continue
        if (y - 1) in fin_annee.index:
            ref = fin_annee[y - 1]
        elif debut <= pd.Timestamp(year=y, month=1, day=5):
            ref = capital
        else:
            continue
        out[int(y)] = float(fin_annee[y] / ref - 1.0)
    return out


def metriques(res, capital: Optional[float] = None) -> dict:
    """Métriques d'une `ResultatSimulation` (dictionnaire sérialisable)."""
    capital = res.capital_initial if capital is None else capital
    eq = res.equity
    tr = res.trades
    out = {"nb_trades": int(len(tr)), "debut": str(eq.index[0].date()) if len(eq) else None,
           "fin": str(eq.index[-1].date()) if len(eq) else None}
    if len(eq) < 3:
        out.update({"annees": annees(eq.index), "sharpe": None, "tstat": None, "cagr_pct": None,
                    "rendement_total_pct": None, "dd_cloture_pct": None, "dd_pire_pct": None,
                    "pct_annees_positives": None, "annees_civiles": {}})
    else:
        r = rendements(eq, capital)
        n = len(r)
        a = annees(eq.index)
        obs = n / a if a > 0 else 252.0
        sd = float(r.std(ddof=1))
        moy = float(r.mean())
        sharpe = moy / sd * math.sqrt(obs) if sd > 0 else None
        tstat = moy / sd * math.sqrt(n) if sd > 0 else None
        fin = float(eq["equity"].iloc[-1])
        cagr = (fin / capital) ** (1 / a) - 1 if a > 0 and fin > 0 else (-1.0 if fin <= 0 else None)
        ddc, ddp, date_dd = drawdowns(eq, capital)
        ac = annees_civiles(eq, capital)
        out.update({
            "annees": a, "obs_par_an": obs, "sharpe": sharpe, "tstat": tstat,
            "rendement_moyen_jour": moy, "vol_annuelle_pct": sd * math.sqrt(obs) * 100,
            "cagr_pct": None if cagr is None else cagr * 100, "rendement_total_pct": (fin / capital - 1) * 100,
            "equity_finale": fin, "dd_cloture_pct": ddc, "dd_pire_pct": ddp, "date_dd_max": str(date_dd.date()),
            "annees_civiles": {str(k): v * 100 for k, v in ac.items()},
            "pct_annees_positives": (100.0 * sum(v > 0 for v in ac.values()) / len(ac)) if ac else None})
    if len(tr):
        out["pct_gagnants"] = float((tr["pnl_net_usd"] > 0).mean() * 100)
        out["r_moyen"] = _f(tr["r_multiple"].mean())
        out["swaps_usd"] = float(tr["swaps_usd"].sum())
        out["couts_execution_usd"] = float(tr["couts_execution_usd"].sum())
        out["commissions_usd"] = float(tr["commissions_usd"].sum())
        out["duree_moyenne_barres"] = float(tr["barres"].mean())
    contrib = {s: 0.0 for s in res.symboles}
    nb_par_sym = {s: 0 for s in res.symboles}
    if len(tr):
        for s, v in tr.groupby("symbole")["pnl_net_usd"].sum().items():
            contrib[s] = float(v)
        for s, v in tr.groupby("symbole").size().items():
            nb_par_sym[s] = int(v)
    par_classe: Dict[str, float] = {}
    for s, v in contrib.items():
        c = res.symboles[s]
        par_classe[c] = par_classe.get(c, 0.0) + v
    out["contribution_symboles"] = contrib
    out["trades_par_symbole"] = nb_par_sym
    out["contribution_classes"] = par_classe
    out["nb_symboles"] = len(contrib)
    out["nb_symboles_positifs"] = int(sum(v > 0 for v in contrib.values()))
    out["part_symboles_positifs"] = (out["nb_symboles_positifs"] / len(contrib)) if contrib else None
    refus = {k.split(":", 1)[1]: v for k, v in res.compteurs.items() if k.startswith("refus:")}
    out["refus"] = refus
    out["nb_refus"] = int(sum(refus.values()))
    nb_signaux = len(res.tentatives)
    out["nb_signaux"] = int(nb_signaux)
    out["compteurs"] = dict(res.compteurs)
    out["date_arret_15"] = str(res.date_arret) if res.date_arret is not None else None
    out["exclus"] = dict(res.exclus)
    out["nb_reequilibrages"] = int(res.nb_reequilibrages)
    return out


def metriques_courtes(m: dict) -> dict:
    cles = ("sharpe", "tstat", "cagr_pct", "dd_pire_pct", "nb_trades", "pct_annees_positives",
            "part_symboles_positifs", "rendement_total_pct")
    return {k: m.get(k) for k in cles}


# --------------------------------------------------------------------------- références

def _serie_prix(univers, s: str, dates: pd.DatetimeIndex) -> pd.Series:
    d1 = univers.symboles[s].tf("D1")
    c = d1["close"].copy()
    c.index = c.index.normalize()
    c = c[~c.index.duplicated(keep="last")]
    return c.reindex(c.index.union(dates)).ffill().reindex(dates)


def reference_passive(univers, symboles, dates: pd.DatetimeIndex, vol_strategie_pct: Optional[float] = None,
                      nom: str = "panier") -> dict:
    """Achat-conservation équipondéré (rééquilibré chaque jour), sans frais, sur `dates`."""
    symboles = [s for s in symboles if s in univers.symboles]
    if not symboles or len(dates) < 3:
        return {"nom": nom, "sharpe": None, "symboles": symboles}
    rets = []
    for s in symboles:
        p = _serie_prix(univers, s, dates)
        rets.append(p.pct_change())
    m = pd.concat(rets, axis=1).mean(axis=1, skipna=True).iloc[1:].fillna(0.0)
    a = annees(dates)
    obs = len(m) / a if a > 0 else 252.0
    sd = float(m.std(ddof=1))
    sharpe = float(m.mean() / sd * math.sqrt(obs)) if sd > 0 else None
    out = {"nom": nom, "symboles": symboles, "sharpe": sharpe, "vol_annuelle_pct": sd * math.sqrt(obs) * 100,
           "rendement_total_pct": float(((1 + m).prod() - 1) * 100)}
    if vol_strategie_pct and sd > 0:
        k = vol_strategie_pct / 100 / (sd * math.sqrt(obs))
        mk = m * k
        out["rendement_annualise_meme_risque_pct"] = float(((1 + mk).prod() ** (1 / a) - 1) * 100) if a > 0 else None
    out["courbe"] = (1 + m).cumprod()
    return out


# --------------------------------------------------------------------------- bootstrap

def bootstrap_12_mois(r: np.ndarray, obs_par_an: float, bloc: int = BLOC_BOOTSTRAP,
                      tirages: int = TIRAGES_BOOTSTRAP, graine: int = GRAINE_BOOTSTRAP) -> np.ndarray:
    """Rendements sur 12 mois obtenus en recollant des blocs de `bloc` jours consécutifs."""
    r = np.asarray(r, dtype=float)
    L = int(round(obs_par_an))
    if len(r) < bloc or L <= 0:
        return np.array([])
    rng = np.random.default_rng(graine)
    nb = int(math.ceil(L / bloc))
    debuts = rng.integers(0, len(r) - bloc + 1, size=(tirages, nb))
    idx = (debuts[:, :, None] + np.arange(bloc)[None, None, :]).reshape(tirages, nb * bloc)[:, :L]
    return np.prod(1.0 + r[idx], axis=1) - 1.0


def resume_bootstrap(res) -> dict:
    eq = res.equity
    if len(eq) < BLOC_BOOTSTRAP + 2:
        return {"p5_pct": None, "nb_tirages": 0}
    r = rendements(eq, res.capital_initial).to_numpy()
    obs = len(r) / annees(eq.index) if annees(eq.index) > 0 else 252.0
    b = bootstrap_12_mois(r, obs)
    return {"p5_pct": float(np.percentile(b, SEUILS["controle_percentile"]) * 100), "p50_pct": float(np.median(b) * 100),
            "nb_tirages": int(len(b)), "bloc_jours": BLOC_BOOTSTRAP, "jours_par_an": obs}


# --------------------------------------------------------------------------- petit capital

def capital_minimum(tentatives: pd.DataFrame, facteur_contrat: float = 1.0) -> dict:
    """Capital pour prendre >= 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10)."""
    if tentatives is None or not len(tentatives):
        return {"capital_min": None, "nb_signaux": 0}
    t = tentatives
    ok = np.isfinite(t["perte_par_lot_usd"]) & np.isfinite(t["notionnel_par_lot_usd"])
    t = t[ok]
    if not len(t):
        return {"capital_min": None, "nb_signaux": 0}
    vmin = t["volume_min"].to_numpy(dtype=float)
    besoin = np.maximum(vmin * t["perte_par_lot_usd"].to_numpy() * facteur_contrat / RISQUE_MAX_PETIT_CAPITAL,
                        vmin * t["notionnel_par_lot_usd"].to_numpy() * facteur_contrat / LEVIER_PETIT_CAPITAL)
    par_sym = pd.Series(besoin).groupby(t["symbole"].to_numpy()).median().to_dict()
    # plus petit capital C tel que la part des signaux avec besoin <= C soit >= 95 %
    k = max(1, int(math.ceil(PART_SIGNAUX * len(besoin) - 1e-9)))
    return {"capital_min": float(np.sort(besoin)[k - 1]),
            "nb_signaux": int(len(besoin)), "mediane_par_symbole": {k: float(v) for k, v in par_sym.items()},
            "part_signaux_jouables_20": float((besoin <= 20.0).mean())}


def resume_petit_capital(res) -> dict:
    m = metriques(res)
    return {"capital_initial": res.capital_initial, "nb_trades": m["nb_trades"], "nb_signaux": m["nb_signaux"],
            "nb_refus": m["nb_refus"], "refus": m["refus"], "equity_finale": m.get("equity_finale"),
            "rendement_total_pct": m.get("rendement_total_pct"), "dd_pire_pct": m.get("dd_pire_pct"),
            "part_signaux_pris": (m["nb_trades"] / m["nb_signaux"]) if m["nb_signaux"] else None}


# --------------------------------------------------------------------------- verdicts

def _critere(numero, nom, valeur, seuil, ok, detail=""):
    return {"numero": numero, "nom": nom, "valeur": valeur, "seuil": seuil, "ok": bool(ok), "detail": detail}


def _fmt(x, d=2, suffixe=""):
    return "n.d." if x is None else f"{x:.{d}f}{suffixe}"


def verdict_strategie(code: str, base: Optional[dict], robustesse: Optional[dict], reference: Optional[dict]) -> dict:
    """Les 7 critères du plan §7 (sans assouplissement). Retenue si TOUS sont OK."""
    S = SEUILS
    base = base or {}
    crit = []
    an_min = S["annees_min_s4"] if code == "S4" else S["annees_min_d1"]
    a, n = base.get("annees"), base.get("nb_trades")
    crit.append(_critere(1, "Assez de données (années / trades)", f"{_fmt(a, 1)} ans / {n if n is not None else 'n.d.'}",
                         f">= {an_min:.0f} ans / >= {S['trades_min']}",
                         a is not None and n is not None and a >= an_min and n >= S["trades_min"]))
    sh = base.get("sharpe")
    crit.append(_critere(2, "Sharpe annualisé après coûts", _fmt(sh), f">= {S['sharpe_min']}",
                         sh is not None and sh >= S["sharpe_min"]))
    t = base.get("tstat")
    crit.append(_critere(3, "t-stat du rendement journalier moyen", _fmt(t), f">= {S['tstat_min']}",
                         t is not None and t >= S["tstat_min"]))
    dd = base.get("dd_pire_pct")
    crit.append(_critere(4, "Drawdown max au pire prix", _fmt(dd, 1, " %"), f"<= {S['dd_max_pct']:.0f} %",
                         dd is not None and dd <= S["dd_max_pct"]))
    pa = base.get("pct_annees_positives")
    crit.append(_critere(5, "Années civiles positives", _fmt(pa, 0, " %"), f">= {S['annees_positives_min_pct']:.0f} %",
                         pa is not None and pa >= S["annees_positives_min_pct"]))
    # 6. robustesse
    rb = robustesse or {}
    variantes = rb.get("variantes") or {}
    cd = (rb.get("couts_doubles") or {}).get("sharpe")
    sh_var = {k: (v or {}).get("sharpe") for k, v in variantes.items()}
    ok_var = bool(sh_var) and all(v is not None and v >= S["sharpe_variantes_min"] for v in sh_var.values())
    ok_cd = cd is not None and cd >= S["sharpe_couts_doubles_min"]
    textes = [f"variantes : {', '.join(f'{k} {_fmt(v)}' for k, v in sh_var.items()) or 'non calculées'}",
              f"coûts doublés : {_fmt(cd)}"]
    ok6 = ok_var and ok_cd
    seuil6 = f"variantes >= {S['sharpe_variantes_min']} ; coûts doublés >= {S['sharpe_couts_doubles_min']}"
    if code in ("S1", "S2", "S4"):
        ps = base.get("part_symboles_positifs")
        textes.append(f"symboles positifs : {base.get('nb_symboles_positifs', 'n.d.')}/{base.get('nb_symboles', 'n.d.')}")
        ok6 = ok6 and ps is not None and ps >= S["part_symboles_positifs_min"]
        seuil6 += " ; >= 50 % des symboles positifs"
    crit.append(_critere(6, "Robustesse", " ; ".join(textes), seuil6, ok6))
    ref = (reference or {}).get("sharpe")
    nom_ref = (reference or {}).get("nom", "référence")
    crit.append(_critere(7, f"Mieux que la référence passive ({nom_ref})", f"{_fmt(sh)} contre {_fmt(ref)}",
                         "Sharpe > référence", sh is not None and ref is not None and sh > ref))
    retenue = all(c["ok"] for c in crit)
    return {"criteres": crit, "retenue": retenue,
            "decision": "RETENUE pour le contrôle final" if retenue else "REJETÉE",
            "criteres_ko": [c["numero"] for c in crit if not c["ok"]]}


def verdict_global(verdicts: dict) -> dict:
    """Phase de développement. Retenues -> attente du contrôle final ; aucune -> NO-GO pour ce cycle."""
    retenues = [k for k, v in verdicts.items() if v.get("retenue")]
    if retenues:
        return {"decision": "EN ATTENTE DU CONTRÔLE FINAL", "retenues": retenues,
                "explication": "Ces hypothèses passent tous les critères de développement. Elles ne sont PAS encore "
                               "jouables : il faut d'abord les figer puis les calculer une seule fois sur le contrôle "
                               "final (--controle-final), puis 4 semaines de paper trading."}
    return {"decision": "NO-GO", "retenues": [],
            "explication": "Aucune hypothèse ne remplit tous les critères fixés à l'avance. On n'engage pas d'argent. "
                           "Toute nouvelle idée devient une hypothèse d'un PROCHAIN cycle, testée sur de nouvelles "
                           "données de contrôle (« À CREUSER »), sans réutiliser celles-ci."}


def verdict_controle(rendement_12m_pct: Optional[float], p5_pct: Optional[float], dd_pire_pct: Optional[float]) -> dict:
    S = SEUILS
    c1 = _critere(1, "Rendement du contrôle final au-dessus du 5e centile du développement (bootstrap)",
                  f"{_fmt(rendement_12m_pct, 1, ' %')} (5e centile {_fmt(p5_pct, 1, ' %')})", ">= 5e centile",
                  rendement_12m_pct is not None and p5_pct is not None and rendement_12m_pct >= p5_pct)
    c2 = _critere(2, "Drawdown du contrôle final au pire prix", _fmt(dd_pire_pct, 1, " %"),
                  f"<= {S['controle_dd_max_pct']:.0f} %", dd_pire_pct is not None and dd_pire_pct <= S["controle_dd_max_pct"])
    ok = c1["ok"] and c2["ok"]
    return {"criteres": [c1, c2], "confirmee": ok, "decision": "GO paper trading" if ok else "NO-GO"}


# =========================================================================== cycle 2
# docs/RECHERCHE_PLAN_CYCLE2.md §3 : critères du cycle 1 (§7) avec t-stat >= 3,0 et la référence
# « même méthode toujours acheteuse ». Rien d'autre ne change ; rien n'est assoupli.

SEUILS_CYCLE2 = dict(SEUILS, tstat_min=3.0, ratio_dd_reference_c2=2.0 / 3.0)


def _criteres_communs(code: str, base: dict, robustesse: Optional[dict], seuils: dict, part_symboles: bool) -> list:
    """Critères 1 à 6 (identiques au cycle 1, seuils de `seuils`)."""
    S = seuils
    crit = []
    a, n = base.get("annees"), base.get("nb_trades")
    crit.append(_critere(1, "Assez de données (années / trades)", f"{_fmt(a, 1)} ans / {n if n is not None else 'n.d.'}",
                         f">= {S['annees_min_d1']:.0f} ans / >= {S['trades_min']}",
                         a is not None and n is not None and a >= S["annees_min_d1"] and n >= S["trades_min"]))
    sh = base.get("sharpe")
    crit.append(_critere(2, "Sharpe annualisé après coûts", _fmt(sh), f">= {S['sharpe_min']}",
                         sh is not None and sh >= S["sharpe_min"]))
    t = base.get("tstat")
    crit.append(_critere(3, "t-stat du rendement journalier moyen", _fmt(t), f">= {S['tstat_min']}",
                         t is not None and t >= S["tstat_min"]))
    dd = base.get("dd_pire_pct")
    crit.append(_critere(4, "Drawdown max au pire prix", _fmt(dd, 1, " %"), f"<= {S['dd_max_pct']:.0f} %",
                         dd is not None and dd <= S["dd_max_pct"]))
    pa = base.get("pct_annees_positives")
    crit.append(_critere(5, "Années civiles positives", _fmt(pa, 0, " %"), f">= {S['annees_positives_min_pct']:.0f} %",
                         pa is not None and pa >= S["annees_positives_min_pct"]))
    rb = robustesse or {}
    variantes = rb.get("variantes") or {}
    cd = (rb.get("couts_doubles") or {}).get("sharpe")
    sh_var = {k: (v or {}).get("sharpe") for k, v in variantes.items()}
    ok_var = bool(sh_var) and all(v is not None and v >= S["sharpe_variantes_min"] for v in sh_var.values())
    ok_cd = cd is not None and cd >= S["sharpe_couts_doubles_min"]
    textes = [f"variantes : {', '.join(f'{k} {_fmt(v)}' for k, v in sh_var.items()) or 'non calculées'}",
              f"coûts doublés : {_fmt(cd)}"]
    ok6 = ok_var and ok_cd
    seuil6 = f"variantes >= {S['sharpe_variantes_min']} ; coûts doublés >= {S['sharpe_couts_doubles_min']}"
    if part_symboles:
        ps = base.get("part_symboles_positifs")
        textes.append(f"symboles positifs : {base.get('nb_symboles_positifs', 'n.d.')}/{base.get('nb_symboles', 'n.d.')}")
        ok6 = ok6 and ps is not None and ps >= S["part_symboles_positifs_min"]
        seuil6 += " ; >= 50 % des symboles positifs"
    crit.append(_critere(6, "Robustesse", " ; ".join(textes), seuil6, ok6))
    return crit


def _conclure(crit: list) -> dict:
    retenue = all(c["ok"] for c in crit)
    return {"criteres": crit, "retenue": retenue,
            "decision": "RETENUE pour le contrôle final" if retenue else "REJETÉE",
            "criteres_ko": [c["numero"] for c in crit if not c["ok"]]}


def verdict_strategie_cycle2(code: str, base: Optional[dict], robustesse: Optional[dict],
                             reference: Optional[dict]) -> dict:
    """Critères du plan cycle 2 §3 pour C1, C2 et P (P : seulement si elle est évaluable, voir `cycle2`).

    Critère 7 :
    - C1 : Sharpe STRICTEMENT supérieur à celui de la référence « toujours long, même risque » ;
    - C2 : Sharpe strictement supérieur ET drawdown au pire prix <= 2/3 de celui de la référence
      « toujours long, même cible de volatilité » ;
    - P (interprétation prudente, signalée) : Sharpe strictement supérieur au PLUS GRAND des Sharpe des
      références de ses composantes (C1 et C2 toujours long, US500 acheté et conservé pour S3).
    Critère 6 : la part des symboles positifs s'applique à C1 et C2 (plan) et, par prudence, à P.
    Une valeur manquante rend le critère KO."""
    S = SEUILS_CYCLE2
    base = base or {}
    crit = _criteres_communs(code, base, robustesse, S, part_symboles=True)
    ref = reference or {}
    sh, rsh = base.get("sharpe"), ref.get("sharpe")
    nom_ref = ref.get("nom", "référence")
    ok_sh = sh is not None and rsh is not None and sh > rsh
    if code == "C2":
        dd, rdd = base.get("dd_pire_pct"), ref.get("dd_pire_pct")
        lim = rdd * S["ratio_dd_reference_c2"] if rdd is not None else None
        ok_dd = dd is not None and lim is not None and dd <= lim
        crit.append(_critere(7, f"Mieux que la référence ({nom_ref})",
                             f"Sharpe {_fmt(sh)} contre {_fmt(rsh)} ; pire baisse {_fmt(dd, 1, ' %')} contre "
                             f"{_fmt(rdd, 1, ' %')} (2/3 = {_fmt(lim, 1, ' %')})",
                             "Sharpe > référence ET pire baisse <= 2/3 de celle de la référence", ok_sh and ok_dd))
    else:
        crit.append(_critere(7, f"Mieux que la référence ({nom_ref})", f"{_fmt(sh)} contre {_fmt(rsh)}",
                             "Sharpe > référence", ok_sh))
    return _conclure(crit)


def verdict_s3_cycle2(base: Optional[dict], robustesse: Optional[dict], reference: Optional[dict]) -> dict:
    """S3 jugée SEULE avec les critères du cycle 2 (pour savoir si P est évaluable) : exactement les critères
    du cycle 1 pour S3 (référence US500 acheté et conservé, pas de critère de part des symboles), avec la
    t-stat >= 3,0 du cycle 2."""
    S = SEUILS_CYCLE2
    base = base or {}
    crit = _criteres_communs("S3", base, robustesse, S, part_symboles=False)
    sh, rsh = base.get("sharpe"), (reference or {}).get("sharpe")
    crit.append(_critere(7, f"Mieux que la référence passive ({(reference or {}).get('nom', 'référence')})",
                         f"{_fmt(sh)} contre {_fmt(rsh)}", "Sharpe > référence",
                         sh is not None and rsh is not None and sh > rsh))
    return _conclure(crit)


def verdict_non_evaluee(raison: str) -> dict:
    return {"criteres": [], "retenue": False, "decision": "NON ÉVALUÉE", "criteres_ko": [], "raison": raison}


def verdict_global_cycle2(verdicts: dict) -> dict:
    retenues = [k for k, v in verdicts.items() if v.get("retenue")]
    if retenues:
        return {"decision": "EN ATTENTE DU CONTRÔLE FINAL", "retenues": retenues,
                "explication": "Ces hypothèses passent tous les critères de développement du cycle 2. Elles ne sont PAS "
                               "jouables : il faut choisir au plus deux finalistes (P compte pour un), les figer, les "
                               "calculer UNE SEULE FOIS sur le contrôle final, passer le test des nouveaux marchés, "
                               "puis au moins 3 mois de démo."}
    return {"decision": "NO-GO", "retenues": [],
            "explication": "Aucune hypothèse du cycle 2 ne remplit tous les critères fixés à l'avance. On n'engage pas "
                           "d'argent et le contrôle final reste sous clé."}


def verdict_controle_cycle2(rendement_12m_pct: Optional[float], p5_pct: Optional[float],
                            dd_pire_pct: Optional[float]) -> dict:
    """Plan cycle 2 §4 : mêmes conditions que le cycle 1 ; la suite est le test des nouveaux marchés (§5)
    puis au moins 3 mois de démo (§6)."""
    v = verdict_controle(rendement_12m_pct, p5_pct, dd_pire_pct)
    v["decision"] = ("CONFIRMÉE (suite : test des nouveaux marchés, puis au moins 3 mois de démo)"
                     if v["confirmee"] else "NON CONFIRMÉE — NO-GO")
    return v


def verdict_nouveaux_marches(sharpe: Optional[float], nb_symboles: int) -> dict:
    """Plan cycle 2 §5, règle bloquante : Sharpe < 0 sur les nouveaux marchés => ne passe pas en démo.
    Interprétation prudente : sans nouveau marché ou sans Sharpe calculable, le test n'a pas pu être fait ;
    il reste BLOQUANT (on ne passe pas en démo sur un test manquant)."""
    if not nb_symboles or sharpe is None:
        return {"ok": False, "decision": "NON CONCLUANT — bloquant (aucun nouveau marché ou Sharpe non calculable)",
                "valeur": _fmt(sharpe), "seuil": ">= 0"}
    ok = sharpe >= 0.0
    return {"ok": bool(ok), "valeur": _fmt(sharpe), "seuil": ">= 0",
            "decision": "OK (informatif) : peut passer en démo si le contrôle final est confirmé" if ok
            else "ÉCHEC bloquant : Sharpe négatif sur les nouveaux marchés, pas de démo"}
