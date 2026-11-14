"""Rapport en français (rapport.md) et graphiques d'equity du programme de recherche.

`rediger_rapport(resume)` n'utilise que le dictionnaire `resume.json` : un rapport peut être
réécrit après chaque section du calcul.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from sentitrade.recherche.evaluation import SEUILS
from sentitrade.recherche.strategies import DESCRIPTIONS

NOMS_CLASSES = {"forex": "forex", "metaux": "métaux", "indices": "indices", "crypto": "crypto",
                "energies": "énergies", "matieres": "matières premières"}
RAISONS = {
    "lot_inferieur_minimum": "lot minimum du broker trop gros pour le risque autorisé",
    "plafond_risque_ouvert": "plafond de 4 % de risque ouvert atteint",
    "plafond_levier": "plafond de levier 10 atteint",
    "perte_jour_max": "perte du jour de -3 % atteinte",
    "conversion_indisponible": "conversion en USD impossible ce jour-là",
}

INTERPRETATIONS = [
    "Signal à la clôture, exécution à l'ouverture suivante du même symbole ; sur une même ouverture, toutes "
    "les sorties passent avant les entrées, et les entrées sont traitées dans l'ordre alphabétique des symboles "
    "(cela compte seulement quand un plafond est atteint).",
    "Spread à l'ouverture d'une bougie D1 : le plus grand du spread de la bougie D1, du spread de la première "
    "bougie H1 du jour et de la médiane de spread de cette heure-là (le premier tick du jour est souvent cher).",
    "Bougies D1 : l'ordre des prix dans la journée est inconnu ; un stop touché dans la journée est exécuté au "
    "stop moins un glissement, au prix d'ouverture en cas de gap ; l'equity « au pire prix » prend en même temps "
    "le pire prix de toutes les positions.",
    "Référence de la perte journalière (-3 %) : equity à minuit (une perte latente d'avant minuit n'est pas une "
    "perte du jour). L'arrêt à -15 % est daté mais ne stoppe pas la simulation (mode évaluation).",
    "Risque ouvert : risque initial en USD des positions (perte au stop, glissement compris), plus les ordres S4 "
    "en attente. Le plafond de 4 % s'applique aussi à S2, par réduction proportionnelle des positions "
    "rééquilibrées (comme le plafond de levier).",
    "S2 : rééquilibrage à l'ouverture de la première bougie de chaque semaine ISO avec les valeurs de la clôture "
    "précédente ; N = symboles dont le signal est calculable ; le stop de 4 ATR est posé à l'ouverture de la "
    "position et n'est pas déplacé par un ajustement de taille ; « changements de position » = positions "
    "ouvertes (les ajustements de taille ne sont pas comptés).",
    "S3 : la sortie après 10 bougies se fait à l'ouverture qui suit la 10e clôture en position (bougie d'entrée "
    "comprise).",
    "S4 : ordres valables sur les bougies entièrement avant l'échéance ; si les deux niveaux sont touchés dans la "
    "même bougie, on suppose le pire (entrée puis stop dans la même bougie) ; l'objectif 2R (variante) vaut 2 × "
    "la hauteur du range et n'est jamais pris dans la bougie d'entrée ; la clôture forcée se fait à l'ouverture "
    "de la bougie M15 qui contient 21:55 ou 22:45 (21:45 ou 22:45) ; taille calculée à la pose des ordres.",
    "Coûts doublés : spread et glissements × 2, swaps × 2 quand ils coûtent (un swap créditeur n'est pas doublé).",
    "Conversion en USD au cours de clôture de la veille de la paire de conversion (cours connu pendant tout le "
    "jour) ; une devise non convertible exclut le symbole.",
    "Swap : nuit facturée si le symbole a coté ce jour-là et que la position est ouverte à la clôture ; nuit "
    "triple le jour swap_rollover3days ; pour la crypto, cela peut compter le week-end deux fois (prudent).",
    "Années civiles complètes seulement ; un symbole sans trade ne compte pas comme « contribuant positivement ».",
    "Référence passive : panier équipondéré des mêmes symboles, sans frais ni swap (référence plus exigeante) ; "
    "S3 : US500 seul. On compare les Sharpe (la mise au même risque ne change pas le Sharpe).",
    "Capital minimum : plus petit capital qui permet de prendre au moins 95 % des signaux au lot minimum avec "
    "un risque <= 2 % ET un levier <= 10 (un signal répété plusieurs jours compte à chaque fois).",
]

LIMITES = [
    "Seuls les swaps ACTUELS sont connus ; ils sont appliqués à tout l'historique.",
    "Les médianes de spread viennent des 10 derniers jours ouvrés (mesurés pendant la période de contrôle) ; "
    "ce sont des paramètres de coût, pas des prix.",
    "S4 : les ouvertures de New York (16:30 serveur) sont décalées d'une heure 2 à 3 semaines par an "
    "(changements d'heure américains), comme prévu par le plan.",
    "Le moteur ne modélise ni appel de marge, ni rejet d'ordre par le broker, ni distance minimale de stop, ni "
    "jours fériés autrement que par l'absence de bougie.",
    "Résultats passés : même une hypothèse confirmée ne garantit rien ; elle ne mène qu'au paper trading.",
]


def _n(x, d=2, suffixe=""):
    if x is None:
        return "n.d."
    try:
        return f"{float(x):,.{d}f}".replace(",", " ") + suffixe
    except (TypeError, ValueError):
        return str(x)


def _ligne(*c):
    return "| " + " | ".join(str(x) for x in c) + " |"


def _raisons_ko(v: dict) -> str:
    noms = {1: "trop peu de données ou de trades", 2: "Sharpe trop faible", 3: "t-stat trop faible",
            4: "pire baisse trop forte", 5: "trop peu d'années positives", 6: "pas assez robuste",
            7: "pas mieux que la référence passive"}
    return ", ".join(noms[k] for k in v.get("criteres_ko", []))


def _phrase_petit_capital(cap: Optional[dict]) -> str:
    if not cap:
        return "faisabilité avec 20 $ non calculée"
    cs, cc = cap.get("minimum_standard", {}).get("capital_min"), cap.get("minimum_cent", {}).get("capital_min")
    if cs is None:
        return "faisabilité avec 20 $ non calculable (aucun signal)"
    if cs <= 20:
        return f"jouable avec 20 $ sur un compte standard (minimum {_n(cs, 0)} $)"
    if cc is not None and cc <= 20:
        return (f"pas jouable avec 20 $ sur un compte standard (il faudrait {_n(cs, 0)} $) ; jouable seulement "
                f"sur un compte cent (minimum {_n(cc, 2)} $)")
    return (f"pas jouable avec 20 $ : il faudrait {_n(cs, 0)} $ sur un compte standard"
            + (f" et {_n(cc, 0)} $ sur un compte cent" if cc is not None else ""))


def rediger_rapport(resume: dict) -> str:
    meta = resume.get("meta", {})
    strategies = resume.get("strategies", {})
    vg = resume.get("verdict_global") or {}
    L = []
    L.append("# Programme de recherche multi-marchés — rapport")
    L.append("")
    L.append(f"_Généré le {meta.get('genere_le', '?')} — source : {meta.get('source', '?')} — plan : "
             "docs/RECHERCHE_PLAN.md (règles et critères fixés avant les données)._")
    if meta.get("synthetique"):
        L.append("")
        L.append("> **Données synthétiques** : ce rapport teste le moteur, il ne dit RIEN des vrais marchés.")
    L.append("")
    L.append("## En bref")
    L.append("")
    cf = resume.get("controle_final")
    if cf:
        L.append(f"**Contrôle final : {cf.get('decision_globale', '?')}.**")
        for nom, r in (cf.get("finalistes") or {}).items():
            L.append(f"- {nom} : {r['verdict']['decision']} (rendement 12 mois {_n(r.get('rendement_12m_pct'), 1, ' %')}, "
                     f"5e centile attendu {_n(r.get('p5_pct'), 1, ' %')}, pire baisse {_n(r.get('dd_pire_pct'), 1, ' %')}).")
        L.append("")
    L.append(f"**Verdict du développement : {vg.get('decision', 'incomplet (sections manquantes)')}.** "
             f"{vg.get('explication', '')}")
    L.append("")
    for code in sorted(strategies):
        s = strategies[code]
        v = s.get("verdict") or {}
        b = s.get("base") or {}
        if not v:
            L.append(f"- **{code}** : non calculée.")
            continue
        txt = f"- **{code}** ({DESCRIPTIONS.get(code, '')}) : **{v.get('decision')}**"
        if not v.get("retenue"):
            txt += f" — {_raisons_ko(v)}"
        if b.get("sharpe") is not None and b["sharpe"] > 3:
            txt += " — ATTENTION : résultat trop beau, présumé faux (GARDE_FOUS §5)"
        txt += (f". Sharpe {_n(b.get('sharpe'))}, {_n(b.get('cagr_pct'), 1, ' %')} par an, pire baisse "
                f"{_n(b.get('dd_pire_pct'), 1, ' %')}, {b.get('nb_trades', 'n.d.')} trades. "
                f"Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : "
                f"{_phrase_petit_capital(s.get('capital'))}.")
        L.append(txt)
    L.append("")
    L.append("**Avec 20 $** : une stratégie n'est jouable que si 20 $ permettent de prendre le lot minimum du broker "
             "en risquant au plus 2 % par position sur au moins 95 % des signaux. Sinon, elle n'est PAS jouable "
             "en réel avec ce capital, même si elle est rentable sur 10 000 $.")
    L.append("")
    L.append("Rappel : un backtest ne garantit rien. Même une hypothèse confirmée ne mène qu'au paper trading "
             "(docs/GARDE_FOUS.md §1).")
    L.append("")

    # Conditions
    L.append("## Conditions du test")
    L.append("")
    L.append(f"- Développement : jusqu'au {meta.get('fin_developpement', '2025-11-13')} inclus. Le contrôle final "
             "(2025-11-14 → 2026-11-13) est verrouillé dès le chargement des données"
             + (" et a été utilisé (voir plus bas)." if cf else " et n'a PAS été regardé."))
    L.append(f"- Capital simulé : {_n(meta.get('capital', 10000), 0)} $ ; risque 0,5 % par position (S1, S3, S4), "
             "S2 en ciblage de volatilité ; risque ouvert <= 4 % ; levier <= 10 ; une position par symbole ; "
             "garde -3 %/jour active ; arrêt -15 % daté mais non bloquant.")
    L.append("- Coûts : spread = max(spread de la bougie, médiane horaire) ; achat à l'Ask ; glissement 0,5 × spread "
             "médian au marché, 1 × sur stops et ordres stop ; gap à travers un stop exécuté à l'ouverture ; swaps "
             "selon swap_mode (×3 le jour prévu) ; commission 0 ; P&L converti en USD au cours du jour.")
    u = meta.get("univers") or {}
    if u:
        par_classe = {}
        for nom, c in (u.get("symboles") or {}).items():
            par_classe.setdefault(c, []).append(nom)
        L.append("- Univers : " + " ; ".join(f"{NOMS_CLASSES.get(c, c)} : {', '.join(sorted(v))}"
                                             for c, v in sorted(par_classe.items())))
        if u.get("absents"):
            L.append("- Absents chez le broker (retirés) : " + " ; ".join(f"{k} ({v})" for k, v in u["absents"].items()))
        if u.get("exclus"):
            L.append("- Exclus (données ou coûts inutilisables) : " + " ; ".join(f"{k} ({v})" for k, v in u["exclus"].items()))
    L.append("")

    for code in sorted(strategies):
        L.extend(_section_strategie(code, strategies[code]))

    if cf:
        L.append("## Contrôle final (calculé une seule fois)")
        L.append("")
        L.append(f"_Calculé le {cf.get('calcule_le', '?')}. Ne plus jamais le relancer pour ces hypothèses._")
        L.append("")
        for nom, r in (cf.get("finalistes") or {}).items():
            L.append(f"### {nom} : {r['verdict']['decision']}")
            L.append("")
            L.append(_ligne("n°", "critère", "valeur", "seuil", "résultat"))
            L.append(_ligne("---", "---", "---", "---", "---"))
            for c in r["verdict"]["criteres"]:
                L.append(_ligne(c["numero"], c["nom"], c["valeur"], c["seuil"], "OK" if c["ok"] else "KO"))
            L.append("")
            L.append(f"Période {r.get('debut')} → {r.get('fin')}, {r.get('nb_trades')} trades, Sharpe "
                     f"{_n(r.get('sharpe'))}.")
            L.append("")

    L.append("## Interprétations prudentes des règles du plan")
    L.append("")
    for x in INTERPRETATIONS:
        L.append(f"- {x}")
    L.append("")
    L.append("## Limites connues")
    L.append("")
    for x in LIMITES:
        L.append(f"- {x}")
    L.append("")
    t = resume.get("temps") or {}
    if t:
        L.append("## Temps de calcul (dernière commande)")
        L.append("")
        L.append(", ".join(f"{k} {v:.1f} s" for k, v in t.items() if isinstance(v, (int, float))))
        L.append("")
    return "\n".join(L)


def _section_strategie(code: str, s: dict) -> list:
    L = [f"## {code} — {DESCRIPTIONS.get(code, '')}", ""]
    v = s.get("verdict") or {}
    b = s.get("base") or {}
    if v:
        L.append(f"**{v.get('decision')}**")
        L.append("")
        L.append(_ligne("n°", "critère (plan §7)", "valeur", "seuil", "résultat"))
        L.append(_ligne("---", "---", "---", "---", "---"))
        for c in v["criteres"]:
            L.append(_ligne(c["numero"], c["nom"], c["valeur"], c["seuil"], "OK" if c["ok"] else "KO"))
        L.append("")
    if b and b.get("sharpe") is not None and b["sharpe"] > 3:
        L.append("**ATTENTION : résultat « trop beau » (Sharpe > 3). Il est présumé faux jusqu'à preuve du "
                 "contraire (docs/GARDE_FOUS.md §5) : anticipation, surapprentissage ou coûts oubliés.**")
        L.append("")
    if b:
        L.append(_ligne("mesure", "valeur"))
        L.append(_ligne("---", "---:"))
        lignes = [
            ("Période évaluée", f"{b.get('debut')} → {b.get('fin')} ({_n(b.get('annees'), 1)} ans)"),
            ("Symboles simulés", f"{b.get('nb_symboles')}"),
            ("Trades / signaux refusés", f"{b.get('nb_trades')} / {b.get('nb_refus')}"),
            ("Gagnants", _n(b.get("pct_gagnants"), 1, " %")),
            ("Résultat moyen par trade", _n(b.get("r_moyen"), 3, " R")),
            ("Rendement total", _n(b.get("rendement_total_pct"), 1, " %")),
            ("Rendement annualisé (CAGR)", _n(b.get("cagr_pct"), 2, " %")),
            ("Volatilité annualisée", _n(b.get("vol_annuelle_pct"), 1, " %")),
            ("Sharpe", _n(b.get("sharpe"))), ("t-stat", _n(b.get("tstat"))),
            ("Pire baisse (clôture / pire prix)", f"{_n(b.get('dd_cloture_pct'), 1, ' %')} / {_n(b.get('dd_pire_pct'), 1, ' %')}"),
            ("Années civiles positives", _n(b.get("pct_annees_positives"), 0, " %")),
            ("Swaps payés (-) ou reçus (+)", _n(b.get("swaps_usd"), 0, " $")),
            ("Spread et glissements payés", _n(b.get("couts_execution_usd"), 0, " $")),
            ("Arrêt -15 % (daté, non bloquant)", b.get("date_arret_15") or "jamais atteint"),
        ]
        if code == "S2":
            lignes.append(("Rééquilibrages hebdomadaires", str(b.get("nb_reequilibrages"))))
        for k, val in lignes:
            L.append(_ligne(k, val))
        L.append("")
        if b.get("refus"):
            L.append("Signaux non pris : " + " ; ".join(f"{RAISONS.get(k, k)} : {n}" for k, n in b["refus"].items()) + ".")
            L.append("")
        ign = {k.split(":", 1)[1]: n for k, n in (b.get("compteurs") or {}).items() if k.startswith("jour_ignore:")}
        if ign:
            L.append("Jours ignorés (S4) : " + " ; ".join(f"{k} : {n}" for k, n in ign.items()) + ".")
            L.append("")
        if b.get("exclus"):
            L.append("Symboles exclus pour cette stratégie : " + " ; ".join(f"{k} ({x})" for k, x in b["exclus"].items()))
            L.append("")
        ref = s.get("reference") or {}
        if ref:
            L.append(f"Référence passive ({ref.get('nom')}) : Sharpe {_n(ref.get('sharpe'))}, rendement total "
                     f"{_n(ref.get('rendement_total_pct'), 1, ' %')} sans frais ; au même risque que la stratégie : "
                     f"{_n(ref.get('rendement_annualise_meme_risque_pct'), 2, ' %')} par an.")
            L.append("")
        cl = b.get("contribution_classes") or {}
        if cl:
            L.append("Contribution par classe : " + " ; ".join(f"{NOMS_CLASSES.get(k, k)} {_n(x, 0, ' $')}"
                                                               for k, x in sorted(cl.items())) + ".")
            L.append("")
        cs = b.get("contribution_symboles") or {}
        if cs:
            nb = b.get("trades_par_symbole") or {}
            L.append(_ligne("symbole", "trades", "résultat net"))
            L.append(_ligne("---", "---:", "---:"))
            for k in sorted(cs):
                L.append(_ligne(k, nb.get(k, 0), _n(cs[k], 0, " $")))
            L.append("")
        ac = b.get("annees_civiles") or {}
        if ac:
            L.append("Par année : " + " ; ".join(f"{k} {_n(x, 1, ' %')}" for k, x in sorted(ac.items())) + ".")
            L.append("")
        bs = s.get("bootstrap") or {}
        if bs.get("p5_pct") is not None:
            L.append(f"Bootstrap (blocs de 20 jours, {bs.get('nb_tirages')} tirages) : 5e centile du rendement sur "
                     f"12 mois {_n(bs['p5_pct'], 1, ' %')}, médiane {_n(bs.get('p50_pct'), 1, ' %')} (seuil du contrôle final).")
            L.append("")
    rb = s.get("robustesse")
    if rb:
        L.append("Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :")
        L.append("")
        L.append(_ligne("version", "Sharpe", "t-stat", "CAGR", "pire baisse", "trades"))
        L.append(_ligne("---", "---:", "---:", "---:", "---:", "---:"))
        for nom, m in list((rb.get("variantes") or {}).items()) + [("coûts doublés", rb.get("couts_doubles") or {})]:
            L.append(_ligne(nom, _n(m.get("sharpe")), _n(m.get("tstat")), _n(m.get("cagr_pct"), 2, " %"),
                            _n(m.get("dd_pire_pct"), 1, " %"), m.get("nb_trades")))
        L.append("")
    info = s.get("info_autres_classes")
    if info:
        L.append("Pour information seulement (hors critères) — même test sur les autres classes : "
                 f"Sharpe {_n(info.get('sharpe'))}, t-stat {_n(info.get('tstat'))}, {info.get('nb_trades')} trades.")
        L.append("")
    cap = s.get("capital")
    if cap:
        ms, mc = cap.get("minimum_standard") or {}, cap.get("minimum_cent") or {}
        L.append("Petit capital (plan §6) :")
        L.append("")
        L.append(f"- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : "
                 f"**{_n(ms.get('capital_min'), 0, ' $')}** sur un compte standard, **{_n(mc.get('capital_min'), 2, ' $')}** "
                 f"sur un compte cent ({ms.get('nb_signaux')} signaux).")
        for nom, k in (("compte standard", "sim_20_standard"), ("compte cent", "sim_20_cent")):
            x = cap.get(k) or {}
            if x:
                L.append(f"- Simulation à 20 $ sur un {nom} : {x.get('nb_trades')} trades pris sur {x.get('nb_signaux')} "
                         f"signaux ; capital final {_n(x.get('equity_finale'), 2, ' $')} ; pire baisse "
                         f"{_n(x.get('dd_pire_pct'), 1, ' %')}.")
        L.append(f"- Conclusion : {_phrase_petit_capital(cap)}.")
        L.append("")
    return L


def tracer_equity(courbes: dict, chemin, titre: str, capital: float = 10_000.0) -> None:
    """Un graphique : {libellé: Series d'equity indexée par date}."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for nom, s in courbes.items():
        if s is not None and len(s):
            ax.plot(s.index, s.values, lw=1.2 if "référence" not in nom else 0.9,
                    ls="-" if "référence" not in nom else "--", label=nom)
    ax.axhline(capital, color="grey", lw=0.8, ls=":")
    ax.set_title(titre)
    ax.set_ylabel("USD")
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(Path(chemin), dpi=100)
    plt.close(fig)
