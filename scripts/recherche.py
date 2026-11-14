#!/usr/bin/env python3
"""Programme de recherche multi-marchés (docs/RECHERCHE_PLAN.md) : calcul et rapport.

Exemples :
    python scripts/recherche.py --donnees data/univers --sortie reports/recherche_2026-11-20
    python scripts/recherche.py --synthetique --graine 1 --sortie reports/recherche_demo_synthetique
    # découper en commandes de moins de 10 minutes (résultats intermédiaires conservés) :
    python scripts/recherche.py --donnees data/univers --sortie reports/x --strategies S1,S2 --sections base
    python scripts/recherche.py --donnees data/univers --sortie reports/x --strategies S1,S2 --sections robustesse,capital
    # contrôle final, UNE SEULE FOIS, après avoir figé les finalistes (au plus deux, ou "S1+S2") :
    python scripts/recherche.py --donnees data/univers --sortie reports/x --controle-final --finalistes S1,S2

Sections : base (simulation à 10 000 $, références, bootstrap ; S3 aussi sur les autres classes pour
information), robustesse (variantes voisines, coûts doublés), capital (capital minimum, 20 $ sur
compte standard et compte cent).

Fichiers écrits dans --sortie : rapport.md, resume.json, trades_<S>.csv, equity_<S>.csv,
equity_<S>.png, equity.png. Les résultats déjà calculés avec les MÊMES données (signature dans
resume.json) sont conservés d'une commande à l'autre ; sinon tout est recalculé.

Contrôle final : refusé sans --finalistes, refusé si un finaliste n'a pas été RETENU dans le
resume.json de --sortie (mêmes données de développement), refusé s'il a déjà été calculé.
Il calcule uniquement la période 2025-11-14 → 2026-11-13 des finalistes et le critère de confirmation.

CYCLE 2 (docs/RECHERCHE_PLAN_CYCLE2.md), dans un dossier de sortie SÉPARÉ du cycle 1 :
    python scripts/recherche.py --cycle 2 --donnees data/univers --sortie reports/recherche_cycle2_<date>
    python scripts/recherche.py --cycle 2 --donnees data/univers --sortie reports/x --strategies C1,C2 --sections base
    python scripts/recherche.py --cycle 2 --synthetique --graine 1 --sortie reports/recherche_cycle2_demo_synthetique
    # contrôle final, UNE SEULE FOIS (au plus deux finalistes, P compte pour un) :
    python scripts/recherche.py --cycle 2 --donnees data/univers --sortie reports/x --controle-final --finalistes C1,P
    # nouveaux marchés d'un autre broker (seulement les symboles absents de la référence, développement seulement) :
    python scripts/recherche.py --cycle 2 --nouveaux-marches --reference-univers data/univers \
        --donnees data/univers_<broker> --sortie reports/x --finalistes C1
Stratégies du cycle 2 : C1, C2 et P (C1 + C2 + S3) ; P n'est calculée que si au moins une composante est
retenue seule (S3 est alors jugée avec les critères du cycle 2, section « composantes » de resume.json).
Les verrous du contrôle final sont les mêmes qu'au cycle 1. Un dossier du cycle 1 n'est jamais réutilisé
par le cycle 2, ni l'inverse.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sentitrade.recherche import evaluation as ev  # noqa: E402
from sentitrade.recherche import moteur as mo  # noqa: E402
from sentitrade.recherche import rapport as rp  # noqa: E402
from sentitrade.recherche import strategies as st  # noqa: E402
from sentitrade.recherche.couts import ParametresCouts  # noqa: E402
from sentitrade.recherche.donnees import (DEBUT_CONTROLE, FIN_CONTROLE, FIN_DEVELOPPEMENT,  # noqa: E402
                                          charger_univers)

SECTIONS = ("base", "robustesse", "capital")
VERSION_MOTEUR = "recherche-1"
VERSION_CYCLE2 = "recherche-cycle2-1"
CAPITAL = mo.CAPITAL_INITIAL
FINALISTES_POSSIBLES = ("S1", "S2", "S3", "S4", "S1+S2")


def _json(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (pd.Timestamp, dt.date, dt.datetime)):
        return str(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _propre(x):
    if isinstance(x, dict):
        return {str(k): _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_propre(v) for v in x]
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def _signature(univers, graine=None, version=VERSION_MOTEUR) -> str:
    sig = {"version": version, "univers": univers.signature(), "graine": graine}
    return hashlib.sha256(json.dumps(sig, sort_keys=True, default=_json).encode()).hexdigest()[:16]


def _charger(args, controle_final: bool):
    if args.synthetique:
        from sentitrade.recherche.synthetique import SPECS, SPECS_SUPPLEMENTAIRES, generer_univers
        print(f"Génération de l'univers synthétique (graine {args.graine}) ...", flush=True)
        extra = {}
        if getattr(args, "tournant", False):
            extra["tournant_mois"] = TOURNANT_SYNTHETIQUE
        if getattr(args, "nouveaux_marches", False):      # « nouveau broker » : symboles supplémentaires
            extra["symboles"] = list(SPECS) + list(SPECS_SUPPLEMENTAIRES)
        return generer_univers(controle_final=controle_final, graine=args.graine,
                               tendance={"amplitude": 0.5, "periode_jours": 900} if args.tendance else None, **extra)
    dossier = Path(args.donnees)
    if not dossier.is_absolute():
        dossier = RACINE / dossier
    print(f"Chargement de l'univers {dossier} ...", flush=True)
    return charger_univers(dossier, controle_final=controle_final)


TOURNANT_SYNTHETIQUE = 0.0015      # --tournant (synthétique) : +0,15 % par jour de J à J+3 sur les indices


def _reference(univers, code, res, base_m):
    dates = res.equity.index
    if code == "S3":
        ref = ev.reference_passive(univers, ["US500"], dates, base_m.get("vol_annuelle_pct"), "US500 acheté et conservé")
    else:
        ref = ev.reference_passive(univers, sorted(res.symboles), dates, base_m.get("vol_annuelle_pct"),
                                   "panier équipondéré acheté et conservé")
    return ref


def _ecrire(resume, sortie):
    for code, s in resume.get("strategies", {}).items():
        s["verdict"] = ev.verdict_strategie(code, s.get("base"), s.get("robustesse"), s.get("reference"))
    if resume.get("strategies"):
        complet = all(all(k in s for k in ("base", "robustesse", "capital")) for s in resume["strategies"].values())
        resume["verdict_global"] = ev.verdict_global({k: s["verdict"] for k, s in resume["strategies"].items()})
        if not complet:
            resume["verdict_global"]["explication"] = ("(Calcul incomplet : des sections manquent ; un critère non "
                                                       "calculé compte comme KO.) " + resume["verdict_global"]["explication"])
    (sortie / "resume.json").write_text(json.dumps(_propre(resume), indent=1, ensure_ascii=False, default=_json),
                                        encoding="utf-8")
    (sortie / "rapport.md").write_text(rp.rediger_rapport(resume), encoding="utf-8")


def _graphique_global(resume, sortie):
    courbes = {}
    for code in sorted(resume.get("strategies", {})):
        f = sortie / f"equity_{code}.csv"
        if f.exists():
            e = pd.read_csv(f, index_col=0, parse_dates=True)["equity"]
            courbes[code] = e
    if courbes:
        rp.tracer_equity(courbes, sortie / "equity.png", "Equity des 4 hypothèses (10 000 $ au départ)", CAPITAL)


def developpement(args, sortie: Path, codes: list, sections: list) -> int:
    t0 = time.perf_counter()
    univers = _charger(args, controle_final=False)
    temps = {"chargement": time.perf_counter() - t0}
    signature = _signature(univers, args.graine if args.synthetique else None)
    chemin = sortie / "resume.json"
    resume = {}
    if chemin.exists():
        try:
            ancien = json.loads(chemin.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            ancien = {}
        if not isinstance(ancien, dict):
            ancien = {}
        if ancien.get("cycle") == 2:
            raise SystemExit(f"{chemin} contient des résultats du CYCLE 2 : choisir un autre --sortie pour le cycle 1.")
        if ancien.get("signature") == signature:
            resume = ancien
        else:
            print("Données ou moteur différents de resume.json : tout est recalculé.", flush=True)
    if resume.get("controle_final"):
        print("ATTENTION : le contrôle final a déjà été calculé dans ce dossier ; le développement ne doit plus "
              "être modifié pour ces hypothèses.", flush=True)
    resume["signature"] = signature
    resume["meta"] = {
        "source": univers.source, "synthetique": bool(args.synthetique), "graine": args.graine if args.synthetique else None,
        "genere_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "capital": CAPITAL,
        "fin_developpement": str(FIN_DEVELOPPEMENT.date()),
        "univers": {"symboles": {k: v.classe for k, v in univers.symboles.items()}, "exclus": univers.exclus,
                    "absents": univers.absents}}
    resume["temps"] = temps
    strategies = resume.setdefault("strategies", {})
    for code in codes:
        s = strategies.setdefault(code, {})
        base_res = None
        if "base" in sections or ("capital" in sections and "base" not in s):
            print(f"{code} : base ...", flush=True)
            t = time.perf_counter()
            base_res = mo.simuler(univers, st.strategie_base(code), CAPITAL)
            m = ev.metriques(base_res)
            s["base"] = m
            ref = _reference(univers, code, base_res, m)
            courbe = ref.pop("courbe", None)
            s["reference"] = ref
            s["bootstrap"] = ev.resume_bootstrap(base_res)
            base_res.trades.to_csv(sortie / f"trades_{code}.csv", index=False)
            base_res.equity.to_csv(sortie / f"equity_{code}.csv")
            courbes = {f"{code} (equity)": base_res.equity["equity"]}
            if courbe is not None and len(courbe):
                courbes[f"référence : {ref['nom']} (même capital, sans frais)"] = courbe * CAPITAL
            rp.tracer_equity(courbes, sortie / f"equity_{code}.png",
                             f"{code} — {st.DESCRIPTIONS[code]}" + (" (données synthétiques)" if args.synthetique else ""),
                             CAPITAL)
            if code == "S3":
                autres = tuple(c for c in ("forex", "metaux", "crypto"))
                ri = mo.simuler(univers, st.strategie_base("S3").avec_classes(autres), CAPITAL, journal_complet=False)
                s["info_autres_classes"] = ev.metriques_courtes(ev.metriques(ri))
            temps[f"{code}_base"] = time.perf_counter() - t
            _ecrire(resume, sortie)
            print(f"  {m['nb_trades']} trades, Sharpe {m['sharpe'] if m['sharpe'] is None else round(m['sharpe'], 2)}, "
                  f"{temps[f'{code}_base']:.1f} s", flush=True)
        if "robustesse" in sections:
            print(f"{code} : robustesse ...", flush=True)
            t = time.perf_counter()
            rb = {"variantes": {}}
            for v in st.variantes_voisines(code):
                rv = mo.simuler(univers, v, CAPITAL, journal_complet=False)
                rb["variantes"][v.variante] = ev.metriques_courtes(ev.metriques(rv))
            rc = mo.simuler(univers, st.strategie_base(code), CAPITAL, params_couts=ParametresCouts.doubles(),
                            journal_complet=False)
            rb["couts_doubles"] = ev.metriques_courtes(ev.metriques(rc))
            s["robustesse"] = rb
            temps[f"{code}_robustesse"] = time.perf_counter() - t
            _ecrire(resume, sortie)
            print(f"  {temps[f'{code}_robustesse']:.1f} s", flush=True)
        if "capital" in sections:
            print(f"{code} : petit capital ...", flush=True)
            t = time.perf_counter()
            if base_res is None:
                base_res = mo.simuler(univers, st.strategie_base(code), CAPITAL, journal_complet=False)
            cap = {"minimum_standard": ev.capital_minimum(base_res.tentatives, 1.0),
                   "minimum_cent": ev.capital_minimum(base_res.tentatives, 0.01)}
            r20 = mo.simuler(univers, st.strategie_base(code), 20.0, journal_complet=False)
            r20c = mo.simuler(univers, st.strategie_base(code), 20.0, facteur_contrat=0.01, journal_complet=False)
            cap["sim_20_standard"] = ev.resume_petit_capital(r20)
            cap["sim_20_cent"] = ev.resume_petit_capital(r20c)
            s["capital"] = cap
            temps[f"{code}_capital"] = time.perf_counter() - t
            _ecrire(resume, sortie)
            print(f"  {temps[f'{code}_capital']:.1f} s", flush=True)
    temps["total_commande"] = time.perf_counter() - t0
    _graphique_global(resume, sortie)
    _ecrire(resume, sortie)
    vg = resume.get("verdict_global", {})
    print(f"Verdict du développement : {vg.get('decision')}")
    for code in sorted(strategies):
        v = strategies[code].get("verdict", {})
        print(f"  {code} : {v.get('decision')}" + (f" (critères KO : {v.get('criteres_ko')})" if v.get("criteres_ko") else ""))
        for c in v.get("criteres", []):
            print(f"     {c['numero']}. {c['nom']} : {c['valeur']} (seuil {c['seuil']}) -> {'OK' if c['ok'] else 'KO'}")
    print(f"Rapport : {sortie / 'rapport.md'}  ({temps['total_commande']:.1f} s)")
    return 0


def lire_finalistes(texte: str) -> list:
    """Valide --finalistes : au plus deux, parmi S1..S4 ou la combinaison "S1+S2" (SystemExit sinon)."""
    noms = [x.strip().upper() for x in (texte or "").split(",") if x.strip()]
    if not noms:
        raise SystemExit("--controle-final exige --finalistes (ex. --finalistes S1,S2 ou --finalistes S1+S2)")
    inconnus = [n for n in noms if n not in FINALISTES_POSSIBLES]
    if inconnus:
        raise SystemExit(f"Finalistes inconnus : {inconnus} (possibles : {', '.join(FINALISTES_POSSIBLES)})")
    if len(noms) > 2 or len(set(noms)) != len(noms):
        raise SystemExit("Au plus deux finalistes distincts (plan §7).")
    return noms


def controle_final(args, sortie: Path, finalistes: list) -> int:
    t0 = time.perf_counter()
    chemin = sortie / "resume.json"
    if not chemin.exists():
        raise SystemExit(f"{chemin} introuvable : lancer d'abord le développement complet dans ce dossier.")
    resume = json.loads(chemin.read_text(encoding="utf-8"))
    if resume.get("cycle") == 2:
        raise SystemExit("Ce dossier contient le cycle 2 : utiliser --cycle 2 --controle-final.")
    if resume.get("controle_final"):
        raise SystemExit("Le contrôle final a DÉJÀ été calculé dans ce dossier (le plan interdit de le recalculer). "
                         "Résultats : rapport.md, section « Contrôle final ».")
    complet = _charger(args, controle_final=True)
    dev = complet.tronquer(FIN_DEVELOPPEMENT)
    if _signature(dev, args.graine if args.synthetique else None) != resume.get("signature"):
        raise SystemExit("Les données de développement diffèrent de celles de resume.json : contrôle final refusé.")
    strategies = resume.get("strategies", {})
    for f in finalistes:
        parts = f.split("+")
        for p in parts:
            s = strategies.get(p) or {}
            # verdict RECALCULÉ à partir des mesures enregistrées (on ne se fie pas au seul drapeau « retenue »)
            v = ev.verdict_strategie(p, s.get("base"), s.get("robustesse"), s.get("reference")) if s else {}
            if not v.get("retenue"):
                raise SystemExit(f"Contrôle final refusé : {p} n'a pas été RETENUE en développement "
                                 f"({v.get('decision', 'non calculée')}).")
    print("Contrôle final : la période 2025-11-14 → 2026-11-13 est calculée UNE SEULE FOIS.", flush=True)
    out = {"calcule_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "finalistes": {}}
    for f in finalistes:
        rd = mo.simuler_finaliste(dev, f, CAPITAL, journal_complet=False)
        bs = ev.resume_bootstrap(rd)
        rh = mo.simuler_finaliste(complet, f, CAPITAL, debut=DEBUT_CONTROLE, fin=FIN_CONTROLE)
        m = ev.metriques(rh)
        r12 = m.get("rendement_total_pct")
        verdict = ev.verdict_controle(r12, bs.get("p5_pct"), m.get("dd_pire_pct"))
        rh.trades.to_csv(sortie / f"trades_controle_{f.replace('+', '_')}.csv", index=False)
        rh.equity.to_csv(sortie / f"equity_controle_{f.replace('+', '_')}.csv")
        out["finalistes"][f] = {"rendement_12m_pct": r12, "p5_pct": bs.get("p5_pct"), "dd_pire_pct": m.get("dd_pire_pct"),
                                "sharpe": m.get("sharpe"), "nb_trades": m.get("nb_trades"), "debut": m.get("debut"),
                                "fin": m.get("fin"), "verdict": verdict}
        print(f"  {f} : {verdict['decision']}", flush=True)
    tous = all(r["verdict"]["confirmee"] for r in out["finalistes"].values())
    out["decision_globale"] = ("GO paper trading (au moins 4 semaines en démo)" if tous else
                               "NO-GO pour les finalistes non confirmés" if any(
                                   r["verdict"]["confirmee"] for r in out["finalistes"].values()) else "NO-GO")
    resume["controle_final"] = out
    resume.setdefault("temps", {})["controle_final"] = time.perf_counter() - t0
    _ecrire(resume, sortie)
    print(f"Décision : {out['decision_globale']}. Rapport : {sortie / 'rapport.md'}")
    return 0


# =========================================================================== cycle 2

FINALISTES_CYCLE2 = ("C1", "C2", "P")


def _charger_resume_cycle2(sortie: Path, exiger: bool) -> dict:
    chemin = sortie / "resume.json"
    if not chemin.exists():
        if exiger:
            raise SystemExit(f"{chemin} introuvable : lancer d'abord le développement du cycle 2 dans ce dossier.")
        return {}
    try:
        resume = json.loads(chemin.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SystemExit(f"{chemin} illisible ({exc}) : refusé par prudence.")
    if not isinstance(resume, dict) or resume.get("cycle") != 2:
        raise SystemExit(f"{chemin} n'est pas un résultat du cycle 2 (dossier du cycle 1 ?) : choisir un autre "
                         "--sortie. Les résultats du cycle 1 ne sont jamais modifiés par le cycle 2.")
    return resume


def _ecrire_cycle2(resume, sortie):
    from sentitrade.recherche import cycle2 as c2
    from sentitrade.recherche.rapport_cycle2 import rediger_rapport_cycle2
    s3 = (resume.get("composantes") or {}).get("S3")
    if s3:
        s3["verdict"] = ev.verdict_s3_cycle2(s3.get("base"), s3.get("robustesse"), s3.get("reference"))
    strategies = resume.get("strategies", {})
    for code in list(strategies):
        if code == "P":
            ok, raison = c2.evaluabilite_p(resume)
            strategies["P"]["evaluable"] = ok
            strategies["P"]["raison_evaluabilite"] = raison
            if ok:
                strategies["P"]["reference"] = c2.reference_p(resume)
        strategies[code]["verdict"] = c2.verdict(code, resume)
    if strategies:
        resume["verdict_global"] = ev.verdict_global_cycle2({k: s["verdict"] for k, s in strategies.items()})
        incomplet = [k for k, s in strategies.items()
                     if s["verdict"].get("decision") != "NON ÉVALUÉE"
                     and not all(x in s for x in ("base", "robustesse", "capital"))]
        if incomplet:
            resume["verdict_global"]["explication"] = (
                f"(Calcul incomplet pour {', '.join(incomplet)} : un critère non calculé compte comme KO.) "
                + resume["verdict_global"]["explication"])
    (sortie / "resume.json").write_text(json.dumps(_propre(resume), indent=1, ensure_ascii=False, default=_json),
                                        encoding="utf-8")
    (sortie / "rapport.md").write_text(rediger_rapport_cycle2(resume), encoding="utf-8")


def _afficher_verdicts_cycle2(resume):
    vg = resume.get("verdict_global", {})
    print(f"Verdict du développement (cycle 2) : {vg.get('decision')}")
    for code, s in resume.get("strategies", {}).items():
        v = s.get("verdict", {})
        print(f"  {code} : {v.get('decision')}" + (f" ({v.get('raison')})" if v.get("raison") else "")
              + (f" (critères KO : {v.get('criteres_ko')})" if v.get("criteres_ko") else ""))
        for c in v.get("criteres", []):
            print(f"     {c['numero']}. {c['nom']} : {c['valeur']} (seuil {c['seuil']}) -> {'OK' if c['ok'] else 'KO'}")


def developpement_cycle2(args, sortie: Path, codes: list, sections: list) -> int:
    from sentitrade.recherche import cycle2 as c2
    t0 = time.perf_counter()
    ancien = _charger_resume_cycle2(sortie, exiger=False)
    univers = _charger(args, controle_final=False)
    temps = {"chargement": time.perf_counter() - t0}
    signature = _signature(univers, args.graine if args.synthetique else None, VERSION_CYCLE2)
    resume = {}
    if ancien:
        if ancien.get("signature") == signature:
            resume = ancien
        elif ancien.get("controle_final"):
            raise SystemExit("Le contrôle final du cycle 2 a déjà été calculé dans ce dossier avec d'autres données : "
                             "refus d'écraser ces résultats.")
        else:
            print("Données ou moteur différents de resume.json : tout est recalculé.", flush=True)
    if resume.get("controle_final"):
        print("ATTENTION : le contrôle final a déjà été calculé dans ce dossier ; le développement ne doit plus "
              "être modifié pour ces hypothèses.", flush=True)
    resume["cycle"] = 2
    resume["signature"] = signature
    resume["meta"] = {
        "source": univers.source, "synthetique": bool(args.synthetique), "graine": args.graine if args.synthetique else None,
        "genere_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "capital": CAPITAL, "plan": "docs/RECHERCHE_PLAN_CYCLE2.md",
        "fin_developpement": str(FIN_DEVELOPPEMENT.date()),
        "univers": {"symboles": {k: v.classe for k, v in univers.symboles.items()}, "exclus": univers.exclus,
                    "absents": univers.absents}}
    resume["temps"] = temps
    strategies = resume.setdefault("strategies", {})
    suffixe = " (données synthétiques)" if args.synthetique else ""

    def base_et_graphique(code, s):
        res, m, ref, bs, rref = c2.section_base(univers, code, CAPITAL)
        s["base"] = m
        if ref is not None:
            s["reference"] = ref
        s["bootstrap"] = bs
        res.trades.to_csv(sortie / f"trades_{code}.csv", index=False)
        res.equity.to_csv(sortie / f"equity_{code}.csv")
        courbes = {f"{code} (equity)": res.equity["equity"]}
        if rref is not None and len(rref.equity):
            courbes[f"référence : {ref['nom']}"] = rref.equity["equity"]
        rp.tracer_equity(courbes, sortie / f"equity_{code}.png", f"{code} — {st.DESCRIPTIONS[code]}{suffixe}", CAPITAL)
        return res, m

    def calculer(code, s):
        base_res = None
        if "base" in sections or ("capital" in sections and "base" not in s):
            print(f"{code} : base ...", flush=True)
            t = time.perf_counter()
            base_res, m = base_et_graphique(code, s)
            temps[f"{code}_base"] = time.perf_counter() - t
            _ecrire_cycle2(resume, sortie)
            print(f"  {m['nb_trades']} trades, Sharpe {m['sharpe'] if m['sharpe'] is None else round(m['sharpe'], 2)}, "
                  f"{temps[f'{code}_base']:.1f} s", flush=True)
        if "robustesse" in sections:
            print(f"{code} : robustesse ...", flush=True)
            t = time.perf_counter()
            s["robustesse"] = c2.section_robustesse(univers, code, CAPITAL)
            temps[f"{code}_robustesse"] = time.perf_counter() - t
            _ecrire_cycle2(resume, sortie)
            print(f"  {temps[f'{code}_robustesse']:.1f} s", flush=True)
        if "capital" in sections:
            print(f"{code} : petit capital ...", flush=True)
            t = time.perf_counter()
            s["capital"] = c2.section_capital(univers, code, base_res)
            temps[f"{code}_capital"] = time.perf_counter() - t
            _ecrire_cycle2(resume, sortie)
            print(f"  {temps[f'{code}_capital']:.1f} s", flush=True)

    for code in ("C1", "C2"):
        if code in codes:
            calculer(code, strategies.setdefault(code, {}))
    if "P" in codes:
        comp = resume.setdefault("composantes", {}).setdefault("S3", {})
        t = time.perf_counter()
        if "base" in sections or "base" not in comp:
            print("S3 (composante de P, critères du cycle 2) : base ...", flush=True)
            comp.update(c2.section_base_s3(univers, CAPITAL))
        if "robustesse" in sections or "robustesse" not in comp:
            print("S3 (composante de P, critères du cycle 2) : robustesse ...", flush=True)
            comp["robustesse"] = c2.section_robustesse_s3(univers, CAPITAL)
        temps["S3_composante"] = time.perf_counter() - t
        s = strategies.setdefault("P", {})
        ok, raison = c2.evaluabilite_p(resume)
        if ok:
            calculer("P", s)
        else:
            for k in ("base", "robustesse", "capital", "bootstrap", "reference"):
                s.pop(k, None)
            print(f"P : NON ÉVALUÉE — {raison}", flush=True)
        _ecrire_cycle2(resume, sortie)
    temps["total_commande"] = time.perf_counter() - t0
    courbes = {}
    for code in ("C1", "C2", "P"):
        f = sortie / f"equity_{code}.csv"
        if f.exists() and "base" in strategies.get(code, {}):
            courbes[code] = pd.read_csv(f, index_col=0, parse_dates=True)["equity"]
    if courbes:
        rp.tracer_equity(courbes, sortie / "equity.png", f"Equity des hypothèses du cycle 2 (10 000 $ au départ){suffixe}",
                         CAPITAL)
    _ecrire_cycle2(resume, sortie)
    _afficher_verdicts_cycle2(resume)
    print(f"Rapport : {sortie / 'rapport.md'}  ({temps['total_commande']:.1f} s)")
    return 0


def lire_finalistes_cycle2(texte: str) -> list:
    """Au plus deux finalistes distincts parmi C1, C2 et P (P compte pour un) ; SystemExit sinon."""
    noms = [x.strip().upper() for x in (texte or "").split(",") if x.strip()]
    if not noms:
        raise SystemExit("--finalistes est obligatoire (ex. --finalistes C1 ou --finalistes C1,P)")
    inconnus = [n for n in noms if n not in FINALISTES_CYCLE2]
    if inconnus:
        raise SystemExit(f"Finalistes inconnus : {inconnus} (possibles au cycle 2 : {', '.join(FINALISTES_CYCLE2)})")
    if len(noms) > 2 or len(set(noms)) != len(noms):
        raise SystemExit("Au plus deux finalistes distincts (plan cycle 2 §4, P compte pour un).")
    return noms


def _verifier_retenus_cycle2(resume: dict, finalistes: list, etape: str):
    from sentitrade.recherche import cycle2 as c2
    for f in finalistes:
        if f not in (resume.get("strategies") or {}):
            raise SystemExit(f"{etape} refusé : {f} n'a pas été calculée en développement.")
        v = c2.verdict(f, resume)          # RECALCULÉ à partir des mesures enregistrées
        if not v.get("retenue"):
            raise SystemExit(f"{etape} refusé : {f} n'a pas été RETENUE en développement ({v.get('decision')}).")


def controle_final_cycle2(args, sortie: Path, finalistes: list) -> int:
    from sentitrade.recherche import cycle2 as c2  # noqa: F401  (verdicts)
    t0 = time.perf_counter()
    resume = _charger_resume_cycle2(sortie, exiger=True)
    if resume.get("controle_final"):
        raise SystemExit("Le contrôle final du cycle 2 a DÉJÀ été calculé dans ce dossier (le plan interdit de le "
                         "recalculer). Résultats : rapport.md, section « Contrôle final ».")
    complet = _charger(args, controle_final=True)
    dev = complet.tronquer(FIN_DEVELOPPEMENT)
    if _signature(dev, args.graine if args.synthetique else None, VERSION_CYCLE2) != resume.get("signature"):
        raise SystemExit("Les données de développement diffèrent de celles de resume.json : contrôle final refusé.")
    _verifier_retenus_cycle2(resume, finalistes, "Contrôle final")
    print("Contrôle final du cycle 2 : la période 2025-11-14 → 2026-11-13 est calculée UNE SEULE FOIS.", flush=True)
    out = {"calcule_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "finalistes": {}}
    for f in finalistes:
        rd = mo.simuler_finaliste(dev, f, CAPITAL, journal_complet=False)
        bs = ev.resume_bootstrap(rd)
        rh = mo.simuler_finaliste(complet, f, CAPITAL, debut=DEBUT_CONTROLE, fin=FIN_CONTROLE)
        m = ev.metriques(rh)
        r12 = m.get("rendement_total_pct")
        verdict = ev.verdict_controle_cycle2(r12, bs.get("p5_pct"), m.get("dd_pire_pct"))
        rh.trades.to_csv(sortie / f"trades_controle_{f}.csv", index=False)
        rh.equity.to_csv(sortie / f"equity_controle_{f}.csv")
        out["finalistes"][f] = {"rendement_12m_pct": r12, "p5_pct": bs.get("p5_pct"), "dd_pire_pct": m.get("dd_pire_pct"),
                                "sharpe": m.get("sharpe"), "nb_trades": m.get("nb_trades"), "debut": m.get("debut"),
                                "fin": m.get("fin"), "verdict": verdict}
        print(f"  {f} : {verdict['decision']}", flush=True)
    conf = [r["verdict"]["confirmee"] for r in out["finalistes"].values()]
    out["decision_globale"] = ("CONFIRMÉ(S) : test des nouveaux marchés puis au moins 3 mois de démo" if all(conf) else
                               "NO-GO pour les finalistes non confirmés" if any(conf) else "NO-GO")
    resume["controle_final"] = out
    resume.setdefault("temps", {})["controle_final"] = time.perf_counter() - t0
    _ecrire_cycle2(resume, sortie)
    print(f"Décision : {out['decision_globale']}. Rapport : {sortie / 'rapport.md'}")
    return 0


def _noms_reference(args, resume: dict) -> set:
    """Noms génériques déjà « vus » : univers.json de --reference-univers (s'il est donné) et univers du
    développement du cycle 2 (symboles chargés ET exclus) enregistré dans resume.json."""
    noms = set()
    u = (resume.get("meta") or {}).get("univers") or {}
    noms |= set((u.get("symboles") or {}).keys()) | set((u.get("exclus") or {}).keys())
    if args.reference_univers:
        d = Path(args.reference_univers)
        if not d.is_absolute():
            d = RACINE / d
        chemin = d / "univers.json"
        try:
            meta = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"--reference-univers : {chemin} illisible ({exc})")
        noms |= set((meta.get("symboles") or {}).keys())
    return {n.upper() for n in noms}


def nouveaux_marches(args, sortie: Path, finalistes: list) -> int:
    from sentitrade.recherche import cycle2 as c2
    t0 = time.perf_counter()
    resume = _charger_resume_cycle2(sortie, exiger=True)
    _verifier_retenus_cycle2(resume, finalistes, "Test des nouveaux marchés")
    reference = _noms_reference(args, resume)
    univers = _charger(args, controle_final=False)          # période de développement seulement (verrou)
    nouveaux = c2.symboles_nouveaux(univers, reference)
    print(f"Nouveaux marchés (absents de la référence) : {', '.join(nouveaux) or 'aucun'}", flush=True)
    out = {"calcule_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": univers.source,
           "fin_developpement": str(FIN_DEVELOPPEMENT.date()), "reference": sorted(reference),
           "nouveaux": {s: univers.classe(s) for s in nouveaux}, "finalistes": {}}
    for f in finalistes:
        res = c2.simuler_nouveaux(univers, f, nouveaux, CAPITAL)
        m = ev.metriques(res)
        v = ev.verdict_nouveaux_marches(m.get("sharpe"), len(res.symboles))
        res.trades.to_csv(sortie / f"trades_nouveaux_marches_{f}.csv", index=False)
        if len(res.equity):
            res.equity.to_csv(sortie / f"equity_nouveaux_marches_{f}.csv")
            rp.tracer_equity({f"{f} (nouveaux marchés)": res.equity["equity"]},
                             sortie / f"equity_nouveaux_marches_{f}.png", f"{f} — nouveaux marchés", CAPITAL)
        out["finalistes"][f] = {"symboles": sorted(res.symboles), "sharpe": m.get("sharpe"), "tstat": m.get("tstat"),
                                "dd_pire_pct": m.get("dd_pire_pct"), "nb_trades": m.get("nb_trades"),
                                "debut": m.get("debut"), "fin": m.get("fin"), "annees": m.get("annees"),
                                "contribution_symboles": m.get("contribution_symboles"), "verdict": v}
        print(f"  {f} : {v['decision']} (Sharpe {m.get('sharpe')})", flush=True)
    resume["nouveaux_marches"] = out
    resume.setdefault("temps", {})["nouveaux_marches"] = time.perf_counter() - t0
    _ecrire_cycle2(resume, sortie)
    print(f"Rapport : {sortie / 'rapport.md'}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Programme de recherche multi-marchés (RECHERCHE_PLAN.md ; "
                                            "cycle 2 : RECHERCHE_PLAN_CYCLE2.md).")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--donnees", help="dossier de l'univers exporté (data/univers)")
    src.add_argument("--synthetique", action="store_true", help="univers synthétique (marche aléatoire)")
    p.add_argument("--graine", type=int, default=1, help="graine des données synthétiques")
    p.add_argument("--tendance", action="store_true", help="synthétique : injecter une tendance (test du moteur)")
    p.add_argument("--tournant", action="store_true",
                   help="synthétique, cycle 2 : injecter un effet « tournant du mois » sur les indices (test du moteur)")
    p.add_argument("--sortie", required=True, help="dossier du rapport (ex. reports/recherche_2026-11-20)")
    p.add_argument("--cycle", type=int, choices=(1, 2), default=None, help="1 (défaut) ou 2")
    p.add_argument("--strategies", default=None, help="cycle 1 : S1,S2,S3,S4 (défaut) ; cycle 2 : C1,C2,P (défaut)")
    p.add_argument("--sections", default=",".join(SECTIONS), help=f"parmi {','.join(SECTIONS)}")
    p.add_argument("--controle-final", action="store_true", help="calcule UNE FOIS le contrôle final des finalistes")
    p.add_argument("--finalistes", help="finalistes (au plus deux ; cycle 1 : S1,S2 ou S1+S2 ; cycle 2 : C1, C2, P)")
    p.add_argument("--nouveaux-marches", action="store_true",
                   help="cycle 2 : recalcule les finalistes sur les seuls symboles absents de --reference-univers")
    p.add_argument("--reference-univers", help="cycle 2 : univers de référence (data/univers) pour --nouveaux-marches")
    args = p.parse_args(argv)

    sortie = Path(args.sortie)
    if not sortie.is_absolute():
        sortie = RACINE / sortie
    if args.nouveaux_marches and args.cycle == 1:
        raise SystemExit("--nouveaux-marches appartient au cycle 2")
    cycle = 2 if args.nouveaux_marches else (args.cycle or 1)
    if cycle == 1:
        if args.reference_univers or args.tournant:
            raise SystemExit("--reference-univers et --tournant n'existent qu'au cycle 2 (--cycle 2)")
        if args.controle_final:
            finalistes = lire_finalistes(args.finalistes)
            sortie.mkdir(parents=True, exist_ok=True)
            return controle_final(args, sortie, finalistes)
        if args.finalistes:
            raise SystemExit("--finalistes n'a de sens qu'avec --controle-final")
        codes = [c.strip().upper() for c in (args.strategies or "S1,S2,S3,S4").split(",") if c.strip()]
        if not codes or any(c not in st.CODES for c in codes):
            raise SystemExit(f"Stratégies possibles : {', '.join(st.CODES)}")
        sections = [x.strip() for x in args.sections.split(",") if x.strip()]
        if not sections or any(x not in SECTIONS for x in sections):
            raise SystemExit(f"Sections possibles : {', '.join(SECTIONS)}")
        sortie.mkdir(parents=True, exist_ok=True)
        return developpement(args, sortie, codes, sections)

    # ---- cycle 2
    if args.controle_final and args.nouveaux_marches:
        raise SystemExit("--controle-final et --nouveaux-marches sont deux étapes distinctes : une à la fois.")
    if args.nouveaux_marches:
        if not args.reference_univers and not args.synthetique:
            raise SystemExit("--nouveaux-marches exige --reference-univers (ex. data/univers)")
        finalistes = lire_finalistes_cycle2(args.finalistes)
        return nouveaux_marches(args, sortie, finalistes)
    if args.reference_univers:
        raise SystemExit("--reference-univers n'a de sens qu'avec --nouveaux-marches")
    if args.controle_final:
        finalistes = lire_finalistes_cycle2(args.finalistes)
        return controle_final_cycle2(args, sortie, finalistes)
    if args.finalistes:
        raise SystemExit("--finalistes n'a de sens qu'avec --controle-final ou --nouveaux-marches")
    codes = [c.strip().upper() for c in (args.strategies or "C1,C2,P").split(",") if c.strip()]
    if not codes or any(c not in FINALISTES_CYCLE2 for c in codes):
        raise SystemExit(f"Stratégies possibles au cycle 2 : {', '.join(FINALISTES_CYCLE2)}")
    sections = [x.strip() for x in args.sections.split(",") if x.strip()]
    if not sections or any(x not in SECTIONS for x in sections):
        raise SystemExit(f"Sections possibles : {', '.join(SECTIONS)}")
    sortie.mkdir(parents=True, exist_ok=True)
    return developpement_cycle2(args, sortie, codes, sections)


if __name__ == "__main__":
    sys.exit(main())
