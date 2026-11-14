"""Cycle 2 du programme de recherche (docs/RECHERCHE_PLAN_CYCLE2.md) : calculs par section.

Ce module ne fait que des calculs ; la ligne de commande est dans `scripts/recherche.py --cycle 2`.

- `NOMS` : C1, C2 et la combinaison déclarée P (C1 + C2 + S3, un tiers du capital chacune).
- Sections (comme au cycle 1) : `base` (simulation à 10 000 $, référence « même méthode toujours
  acheteuse », bootstrap), `robustesse` (variantes voisines du plan, coûts doublés), `capital`
  (capital minimum, 20 $ sur compte standard et compte cent).
- P n'est évaluée (et même calculée) que si au moins une composante est RETENUE SEULE avec les critères
  du cycle 2 (`evaluabilite_p`) ; S3 est alors jugée comme au cycle 1, avec t-stat >= 3,0.
- Nouveaux marchés (plan §5) : `symboles_nouveaux` garde les symboles dont le nom générique est absent
  de l'univers de référence.

Interprétations prudentes propres à P (signalées dans le rapport) :
- variantes voisines de P : P où UNE composante est remplacée par l'une de ses variantes voisines
  (3 de C1, 3 de C2, 3 de S3 : 9 versions), toutes doivent avoir un Sharpe >= 0,3 ;
- coûts doublés de P : les trois composantes à coûts doublés ;
- référence de P : le plus grand Sharpe des références de ses composantes ;
- capital minimum de P : chaque composante n'a qu'un tiers du capital, le besoin de chaque signal est
  donc multiplié par 3.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from sentitrade.recherche import evaluation as ev
from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.couts import ParametresCouts

NOMS = ("C1", "C2", "P")
NOMS_REFERENCES = {"C1": "C1 toujours long (même risque 0,5 %, même stop 3 ATR)",
                   "C2": "C2 toujours long (même cible de volatilité, même stop 4 ATR)"}


def _ref_courte(m: dict, nom: str) -> dict:
    cles = ("sharpe", "tstat", "dd_pire_pct", "cagr_pct", "rendement_total_pct", "vol_annuelle_pct", "nb_trades",
            "debut", "fin")
    out = {k: m.get(k) for k in cles}
    out["nom"] = nom
    return out


def simuler(univers, code: str, capital: float = mo.CAPITAL_INITIAL, **kwargs) -> mo.ResultatSimulation:
    if code == "P":
        return mo.simuler_p(univers, capital, **kwargs)
    return mo.simuler(univers, st.strategie_base(code), capital, **kwargs)


def section_base(univers, code: str, capital: float = mo.CAPITAL_INITIAL):
    """(résultat, métriques, référence, bootstrap, résultat de la référence ou None) pour C1 ou C2.
    P : la référence est calculée par `reference_p` à partir des sections déjà enregistrées."""
    res = simuler(univers, code, capital)
    m = ev.metriques(res)
    bs = ev.resume_bootstrap(res)
    if code == "P":
        return res, m, None, bs, None
    rref = mo.simuler(univers, st.reference_toujours_long(code), capital, journal_complet=False)
    ref = _ref_courte(ev.metriques(rref), NOMS_REFERENCES[code])
    return res, m, ref, bs, rref


def variantes(code: str) -> list:
    """[(nom, stratégie remplaçante)] : variantes voisines (pour P, une composante remplacée à la fois)."""
    if code == "P":
        return [(f"{v.code} {v.variante}", v) for c in mo.COMPOSANTES_P for v in st.variantes_voisines(c)]
    return [(v.variante, v) for v in st.variantes_voisines(code)]


def section_robustesse(univers, code: str, capital: float = mo.CAPITAL_INITIAL) -> dict:
    rb = {"variantes": {}}
    for nom, v in variantes(code):
        if code == "P":
            r = mo.simuler_p(univers, capital, remplacement=v, journal_complet=False)
        else:
            r = mo.simuler(univers, v, capital, journal_complet=False)
        rb["variantes"][nom] = ev.metriques_courtes(ev.metriques(r))
    rc = simuler(univers, code, capital, params_couts=ParametresCouts.doubles(), journal_complet=False)
    rb["couts_doubles"] = ev.metriques_courtes(ev.metriques(rc))
    return rb


def _tentatives_capital(code: str, tentatives: pd.DataFrame) -> pd.DataFrame:
    if code != "P" or tentatives is None or not len(tentatives):
        return tentatives
    t = tentatives.copy()
    k = float(len(mo.COMPOSANTES_P))      # chaque composante ne dispose que d'un tiers du capital
    t["perte_par_lot_usd"] = t["perte_par_lot_usd"] * k
    t["notionnel_par_lot_usd"] = t["notionnel_par_lot_usd"] * k
    return t


def section_capital(univers, code: str, base_res: Optional[mo.ResultatSimulation] = None) -> dict:
    if base_res is None:
        base_res = simuler(univers, code, mo.CAPITAL_INITIAL, journal_complet=False)
    t = _tentatives_capital(code, base_res.tentatives)
    cap = {"minimum_standard": ev.capital_minimum(t, 1.0), "minimum_cent": ev.capital_minimum(t, 0.01)}
    cap["sim_20_standard"] = ev.resume_petit_capital(simuler(univers, code, 20.0, journal_complet=False))
    cap["sim_20_cent"] = ev.resume_petit_capital(simuler(univers, code, 20.0, facteur_contrat=0.01,
                                                         journal_complet=False))
    return cap


# --------------------------------------------------------------------------- S3 composante et règle de P

def section_base_s3(univers, capital: float = mo.CAPITAL_INITIAL) -> dict:
    """S3 exactement comme au cycle 1 (même code), avec la référence du cycle 1 (US500 acheté et conservé)."""
    res = mo.simuler(univers, st.strategie_base("S3"), capital, journal_complet=False)
    m = ev.metriques(res)
    ref = ev.reference_passive(univers, ["US500"], res.equity.index, m.get("vol_annuelle_pct"),
                               "US500 acheté et conservé")
    ref.pop("courbe", None)
    return {"base": m, "reference": ref}


def section_robustesse_s3(univers, capital: float = mo.CAPITAL_INITIAL) -> dict:
    rb = {"variantes": {}}
    for v in st.variantes_voisines("S3"):
        rb["variantes"][v.variante] = ev.metriques_courtes(ev.metriques(mo.simuler(univers, v, capital,
                                                                                   journal_complet=False)))
    rc = mo.simuler(univers, st.strategie_base("S3"), capital, params_couts=ParametresCouts.doubles(),
                    journal_complet=False)
    rb["couts_doubles"] = ev.metriques_courtes(ev.metriques(rc))
    return rb


def _complet(s: Optional[dict]) -> bool:
    return bool(s) and "base" in s and "robustesse" in s


def verdicts_composantes(resume: dict) -> dict:
    """Verdicts RECALCULÉS à partir des mesures enregistrées (on ne se fie à aucun drapeau stocké)."""
    strategies = resume.get("strategies") or {}
    out = {}
    for code in ("C1", "C2"):
        s = strategies.get(code)
        out[code] = ev.verdict_strategie_cycle2(code, s.get("base"), s.get("robustesse"), s.get("reference")) \
            if s else None
    s3 = (resume.get("composantes") or {}).get("S3")
    out["S3"] = ev.verdict_s3_cycle2(s3.get("base"), s3.get("robustesse"), s3.get("reference")) if s3 else None
    return out


def evaluabilite_p(resume: dict) -> tuple:
    """(évaluable, raison). Plan cycle 2 : P n'est évaluée que si AU MOINS UNE composante est retenue seule."""
    v = verdicts_composantes(resume)
    retenues = [c for c in mo.COMPOSANTES_P if v.get(c) and v[c]["retenue"]]
    if retenues:
        return True, f"composante(s) retenue(s) seule(s) : {', '.join(retenues)}"
    strategies = resume.get("strategies") or {}
    sources = {"C1": strategies.get("C1"), "C2": strategies.get("C2"),
               "S3": (resume.get("composantes") or {}).get("S3")}
    manquantes = [c for c in mo.COMPOSANTES_P if not _complet(sources[c])]
    if manquantes:
        return False, ("verdicts des composantes incomplets (" + ", ".join(manquantes) + " : sections base et "
                       "robustesse nécessaires) ; aucune composante retenue pour l'instant")
    return False, "aucune composante (C1, C2, S3) n'est retenue seule : règle du plan, P n'est pas évaluée"


def reference_p(resume: dict) -> dict:
    """Référence de P : le plus grand Sharpe des références des composantes (interprétation prudente)."""
    strategies = resume.get("strategies") or {}
    refs = {"C1": (strategies.get("C1") or {}).get("reference"),
            "C2": (strategies.get("C2") or {}).get("reference"),
            "S3": ((resume.get("composantes") or {}).get("S3") or {}).get("reference")}
    sharpes = {k: (r or {}).get("sharpe") for k, r in refs.items()}
    if any(v is None for v in sharpes.values()):
        return {"nom": "références des composantes (incomplètes)", "sharpe": None, "composantes": sharpes}
    k = max(sharpes, key=lambda x: sharpes[x])
    return {"nom": f"meilleure référence des composantes : {k}", "sharpe": sharpes[k], "composantes": sharpes}


def verdict(code: str, resume: dict) -> dict:
    """Verdict cycle 2 recalculé de C1, C2 ou P (P : règle d'évaluabilité d'abord)."""
    if code == "P":
        ok, raison = evaluabilite_p(resume)
        if not ok:
            return ev.verdict_non_evaluee(raison)
    s = (resume.get("strategies") or {}).get(code) or {}
    ref = reference_p(resume) if code == "P" else s.get("reference")
    return ev.verdict_strategie_cycle2(code, s.get("base"), s.get("robustesse"), ref)


# --------------------------------------------------------------------------- nouveaux marchés (§5)

def symboles_nouveaux(univers, reference_noms) -> list:
    """Symboles de l'univers dont le NOM GÉNÉRIQUE est absent de l'univers de référence."""
    ref = {str(x).upper() for x in reference_noms}
    return sorted(s for s in univers.symboles if s.upper() not in ref)


def simuler_nouveaux(univers, code: str, nouveaux: list, capital: float = mo.CAPITAL_INITIAL):
    """Finaliste recalculé SANS AUCUN CHANGEMENT, seulement sur les nouveaux symboles (et ses classes)."""
    if code == "P":
        return mo.simuler_p(univers, capital, symboles=nouveaux)
    return mo.simuler(univers, st.restreindre(st.strategie_base(code), nouveaux), capital)
