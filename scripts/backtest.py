#!/usr/bin/env python3
"""Backtest de SentiTrade et rapport complet (docs/SPEC_TECHNIQUE.md §5-6).

Exemples :
    python scripts/backtest.py --donnees data/mt5 --sortie reports/2026-11-13
    python scripts/backtest.py --synthetique --graine 7 --debut 2023-01-02 --fin 2026-01-01 \\
        --sortie reports/_demo_synthetique
    # découper un long calcul en plusieurs commandes (moins de 10 minutes chacune) :
    python scripts/backtest.py --donnees data/mt5 --sortie reports/x --sections base,references
    python scripts/backtest.py --donnees data/mt5 --sortie reports/x --sections isoos,sensibilite,montecarlo

Fichiers écrits dans --sortie : rapport.md, trades.csv, evenements.csv,
equity.png, drawdown.png, equity.csv (equity de fin de journée), resume.json.
Les sections déjà calculées avec les MÊMES données et paramètres (signature
dans resume.json) sont conservées d'une commande à l'autre ; si la signature
change, tout est recalculé.
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

from sentitrade import reporting as rp  # noqa: E402
from sentitrade.backtest import choisir_resolution, executer_backtest  # noqa: E402
from sentitrade.config import CHEMIN_CONFIG, SymboleSpec, charger_config  # noqa: E402
from sentitrade.data import charger_bougies  # noqa: E402
from sentitrade.strategy import preparer_signaux  # noqa: E402

SECTIONS = ("base", "references", "isoos", "sensibilite", "montecarlo")
ECHAUFFEMENT_JOURS = 150      # historique laissé aux indicateurs (ADR 100 jours, EMA 150 bougies H1)


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp, dt.date, dt.datetime)):
        return str(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and np.isinf(o):
        return None
    return str(o)


def _propre(x):
    """Remplace inf/NaN par None (JSON strict)."""
    if isinstance(x, dict):
        return {str(k): _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_propre(v) for v in x]
    if isinstance(x, float) and (np.isnan(x) or np.isinf(x)):
        return "infini" if (isinstance(x, float) and np.isinf(x) and x > 0) else None
    return x


def _infini(x):
    """Inverse de _propre pour les profit factors : "infini" -> inf."""
    if isinstance(x, dict):
        return {k: _infini(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_infini(v) for v in x]
    return float("inf") if x == "infini" else x


def charger_donnees(dossier: Path):
    """(m1 ou None, m15, h1, spec, spread_plancher ou None, description)."""
    def trouver(suffixe):
        fichiers = sorted(dossier.glob(f"*_{suffixe}.csv"))
        if len(fichiers) > 1:
            raise SystemExit(f"Plusieurs fichiers *_{suffixe}.csv dans {dossier} : {[f.name for f in fichiers]}")
        return fichiers[0] if fichiers else None
    f15, fh1, fm1 = trouver("M15"), trouver("H1"), trouver("M1")
    if f15 is None or fh1 is None:
        raise SystemExit(f"Fichiers *_M15.csv et *_H1.csv introuvables dans {dossier}")
    print(f"Chargement de {f15.name}, {fh1.name}" + (f", {fm1.name}" if fm1 else " (pas de M1)") + " ...", flush=True)
    m15, h1 = charger_bougies(f15), charger_bougies(fh1)
    m1 = charger_bougies(fm1) if fm1 else None
    info = dossier / "symbol_info.json"
    if info.exists():
        spec = SymboleSpec.depuis_json(info)
    else:
        print("ATTENTION : symbol_info.json absent, caractéristiques XAUUSD par défaut.", flush=True)
        spec = SymboleSpec()
    plancher, source_plancher = None, None
    stats = dossier / "spread_stats.json"
    if stats.exists():
        d = json.loads(stats.read_text(encoding="utf-8"))
        glob_p50 = (d.get("global") or {}).get("p50")
        par_heure = d.get("par_heure") or {}
        valeurs = []
        for h in range(24):
            v = (par_heure.get(str(h)) or {}).get("p50")
            valeurs.append(float(v if v is not None else (glob_p50 or 0.0)))
        plancher = valeurs
        source_plancher = f"médiane du spread des ticks par heure, spread_stats.json ({len(d.get('jours', []))} jours)"
    return m1, m15, h1, spec, plancher, source_plancher, f"données MT5 ({f15.name.rsplit('_', 1)[0]}, {dossier})"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Backtest SentiTrade et rapport GO / NO-GO.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--donnees", help="dossier des fichiers MT5 (data/mt5)")
    src.add_argument("--synthetique", action="store_true", help="marche aléatoire synthétique (test du moteur)")
    p.add_argument("--graine", type=int, default=1, help="graine des données synthétiques")
    p.add_argument("--debut", help="début de la période simulée (AAAA-MM-JJ)")
    p.add_argument("--fin", help="fin de la période simulée, exclue (AAAA-MM-JJ)")
    p.add_argument("--sortie", required=True, help="dossier du rapport (ex. reports/2026-11-13)")
    p.add_argument("--sections", default=",".join(SECTIONS), help=f"sections à calculer parmi {','.join(SECTIONS)}")
    p.add_argument("--config", default=str(CHEMIN_CONFIG))
    p.add_argument("--balance", type=float, default=3000.0)
    p.add_argument("--resolution", default="auto", choices=("auto", "m1", "m15"))
    p.add_argument("--sans-plancher-spread", action="store_true",
                   help="ne pas relever le spread des bougies à la médiane de spread_stats.json")
    args = p.parse_args(argv)

    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    inconnues = set(sections) - set(SECTIONS)
    if inconnues:
        raise SystemExit(f"Sections inconnues : {sorted(inconnues)} (possibles : {', '.join(SECTIONS)})")
    sortie = Path(args.sortie)
    if not sortie.is_absolute():
        sortie = RACINE / sortie
    sortie.mkdir(parents=True, exist_ok=True)
    cfg = charger_config(args.config)
    t0 = time.perf_counter()

    if args.synthetique:
        from sentitrade.synthetique import generer_jeu
        debut = pd.Timestamp(args.debut or "2023-01-02")
        fin = pd.Timestamp(args.fin) if args.fin else debut + pd.DateOffset(years=3)
        print(f"Génération des données synthétiques (graine {args.graine}) ...", flush=True)
        m1, m15, h1 = generer_jeu(debut - pd.Timedelta(days=ECHAUFFEMENT_JOURS), fin, args.graine)
        spec, plancher, source_plancher = SymboleSpec(), None, None
        source = f"données synthétiques (marche aléatoire, graine {args.graine})"
    else:
        dossier = Path(args.donnees)
        if not dossier.is_absolute():
            dossier = RACINE / dossier
        m1, m15, h1, spec, plancher, source_plancher, source = charger_donnees(dossier)
        if args.sans_plancher_spread:
            plancher, source_plancher = None, None
        debut = pd.Timestamp(args.debut) if args.debut else \
            (m15.index[0].normalize() + pd.Timedelta(days=ECHAUFFEMENT_JOURS))
        fin = pd.Timestamp(args.fin) if args.fin else m15.index[-1].normalize() + pd.Timedelta(days=1)
    t_chargement = time.perf_counter() - t0

    resolution = choisir_resolution(m1, m15, debut, fin, args.resolution)
    signature = {"source": source, "debut": str(debut), "fin": str(fin), "balance": args.balance,
                 "resolution": resolution, "config": json.loads(json.dumps(
                     {"strategie": vars(cfg.strategie), "risque": vars(cfg.risque),
                      "execution": vars(cfg.execution)}, default=_json)),
                 "spec": vars(spec), "spread_plancher": plancher,
                 "nb_m15": int(len(m15)), "dernier_m15": str(m15.index[-1]),
                 "nb_m1": int(0 if m1 is None else len(m1))}
    signature_hash = hashlib.sha256(json.dumps(signature, sort_keys=True, default=_json).encode()).hexdigest()[:16]

    chemin_resume = sortie / "resume.json"
    resume = {}
    if chemin_resume.exists():
        try:
            ancien = _infini(json.loads(chemin_resume.read_text(encoding="utf-8")))
            if ancien.get("signature") == signature_hash:
                resume = ancien
            else:
                print("Données ou paramètres différents de resume.json : tout est recalculé.", flush=True)
        except (ValueError, OSError):
            resume = {}
    resume["signature"] = signature_hash
    resume["meta"] = {"source": source, "synthetique": bool(args.synthetique),
                      "graine": args.graine if args.synthetique else None, "symbole": spec.nom,
                      "debut": str(debut), "fin": str(fin), "resolution": resolution,
                      "balance_initiale": args.balance, "genere_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                      "strategie": signature["config"]["strategie"], "risque": signature["config"]["risque"],
                      "execution": signature["config"]["execution"], "spread_plancher": plancher,
                      "spread_plancher_source": source_plancher}
    temps = resume.setdefault("temps", {})
    temps["chargement_donnees"] = t_chargement

    t = time.perf_counter()
    signaux = preparer_signaux(m15, h1, cfg, spec)
    temps["signaux"] = time.perf_counter() - t
    kw = dict(spread_plancher=plancher)
    bougies_exec = m1 if resolution == "m1" else m15

    def ecrire():
        resume["verdict"] = rp.calculer_verdict(resume)
        chemin_resume.write_text(json.dumps(_propre(resume), indent=1, ensure_ascii=False, default=_json),
                                 encoding="utf-8")
        (sortie / "rapport.md").write_text(rp.rediger_rapport(resume), encoding="utf-8")

    base_res = None

    def calculer_base():
        nonlocal base_res
        t1 = time.perf_counter()
        base_res = executer_backtest(m1, m15, h1, cfg, spec, args.balance, debut, fin, resolution,
                                     signaux=signaux, arret_definitif_actif=False, **kw)
        b = rp.resumer_resultat(base_res)
        b["ventilations"] = rp.ventilations(base_res.trades)
        b["evenements"] = rp.compter_evenements(base_res.evenements)
        resume["base"] = b
        base_res.trades.to_csv(sortie / "trades.csv", index=False)
        base_res.evenements.to_csv(sortie / "evenements.csv", index=False)
        eq = base_res.equity_journaliere
        eq.to_csv(sortie / "equity.csv", header=True)
        refs = resume.setdefault("references", {})
        refs["buy_and_hold"] = rp.buy_and_hold(bougies_exec, debut, fin, spec.point)
        rp.tracer_graphiques(eq, sortie, rp.cours_journalier(bougies_exec, debut, fin), args.balance,
                             "(données synthétiques)" if args.synthetique else "",
                             date_arret=resume["base"].get("date_arret"))
        temps["base"] = time.perf_counter() - t1

    def trades_base() -> pd.DataFrame:
        if base_res is not None:
            return base_res.trades
        return pd.read_csv(sortie / "trades.csv")

    besoin_base = any(s in sections for s in ("base", "references", "montecarlo"))
    if "base" in sections or (besoin_base and not (resume.get("base") and (sortie / "trades.csv").exists())):
        print("Section base ...", flush=True)
        calculer_base()
        ecrire()
        print(f"  {resume['base']['nb_trades']} trades, {temps['base']:.1f} s", flush=True)

    if "references" in sections:
        print("Section references (tendance seule, 200 tirages) ...", flush=True)
        t1 = time.perf_counter()
        tr = trades_base()
        esp = float(tr["r_multiple"].mean()) if len(tr) else None
        ts = rp.reference_tendance_seule(bougies_exec, signaux, cfg, spec, len(tr),
                                         tr["distance_sl_reelle"].to_numpy(dtype=float) if len(tr) else np.array([]),
                                         debut, fin, resolution, args.balance, esperance_strategie=esp, **kw)
        refs = resume.setdefault("references", {})
        refs["buy_and_hold"] = rp.buy_and_hold(bougies_exec, debut, fin, spec.point)
        refs["tendance_seule"] = ts
        temps["references"] = time.perf_counter() - t1
        ecrire()
        print(f"  {temps['references']:.1f} s", flush=True)

    if "isoos" in sections:
        print("Section isoos ...", flush=True)
        t1 = time.perf_counter()
        resume["isoos"] = rp.executer_is_oos(m1, m15, h1, cfg, spec, args.balance, debut, fin, resolution,
                                             signaux=signaux, **kw)
        temps["isoos"] = time.perf_counter() - t1
        ecrire()
        print(f"  {temps['isoos']:.1f} s", flush=True)

    if "sensibilite" in sections:
        print("Section sensibilite ...", flush=True)
        t1 = time.perf_counter()
        resume["sensibilite"] = rp.executer_sensibilite(m1, m15, h1, cfg, spec, args.balance, debut, fin,
                                                        resolution, is_oos_base=resume.get("isoos"), **kw)
        temps["sensibilite"] = time.perf_counter() - t1
        ecrire()
        print(f"  {temps['sensibilite']:.1f} s", flush=True)

    if "montecarlo" in sections:
        print("Section montecarlo ...", flush=True)
        t1 = time.perf_counter()
        tb = trades_base()
        resume["montecarlo"] = rp.monte_carlo(
            tb["r_multiple"].to_numpy(dtype=float), cfg.risque.risque_par_trade_pct,
            fractions_risque=(tb["risque_montant"] / tb["balance_avant"]).to_numpy(dtype=float))
        temps["montecarlo"] = time.perf_counter() - t1
        ecrire()
        print(f"  {temps['montecarlo']:.1f} s", flush=True)

    temps["total_commande"] = time.perf_counter() - t0
    ecrire()
    v = resume["verdict"]
    print(f"Verdict : {v['decision']}")
    for c in v["criteres"]:
        print(f"  {c['numero']}. {c['nom']} : {c['valeur']} (seuil {c['seuil']}) -> "
              f"{'OK' if c['ok'] else 'KO'}")
    print(f"Rapport : {sortie / 'rapport.md'}  ({temps['total_commande']:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
