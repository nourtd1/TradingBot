"""Rapport en français du cycle 2 (docs/RECHERCHE_PLAN_CYCLE2.md), à partir du seul `resume.json`."""
from __future__ import annotations

from sentitrade.recherche.evaluation import SEUILS_CYCLE2
from sentitrade.recherche.rapport import NOMS_CLASSES, RAISONS, _ligne, _n, _phrase_petit_capital
from sentitrade.recherche.strategies import DESCRIPTIONS

INTERPRETATIONS_CYCLE2 = [
    "Conventions du cycle 1 inchangées : signal à la clôture D1, exécution à l'ouverture suivante, coûts du plan "
    "§4 (plancher de spread, journées figées retirées), risque §5, garde -3 %/jour, arrêt -15 % daté.",
    "C1, jour J : dernier lundi-vendredi du mois calendaire (jours fériés ignorés). L'ordre part à la clôture "
    "d'une bougie dont le jour ouvré suivant est J (J-1 pour la variante « entrée J-1 ») ; il ne vaut QUE pour "
    "l'ouverture de ce jour-là : si la bougie suivante reçue porte une autre date (férié, donnée manquante), "
    "l'ordre est annulé et compté (« ordres annulés, jour d'entrée absent ») ; on n'entre jamais en retard.",
    "C1 : si la veille de J manque dans les données, aucune clôture n'a J pour jour ouvré suivant : pas "
    "d'entrée ce mois-là (deviner un jour férié à l'avance serait de l'anticipation).",
    "C1, sortie : à l'ouverture qui suit la clôture de la 3e bougie D1 REÇUE du nouveau mois (2e pour la "
    "variante « sortie 3e jour »). Stop 3 ATR20 (de la veille) sous le prix d'entrée ; une position stoppée "
    "attend le mois suivant. Risque 0,5 %, plafonds de risque ouvert (4 %) et de levier (10) appliqués.",
    "Référence de C1 (critère 7) : mêmes indices, toujours long, même risque (0,5 %) et même stop (3 ATR). La "
    "position est renouvelée chaque mois à l'instant exact où C1 entre (sortie et rachat à la même ouverture, "
    "au risque de 0,5 % de l'equity du moment), et rachetée à l'ouverture qui suit un stop. Elle paie donc le "
    "même aller-retour mensuel que C1 : la différence mesurée est celle du moment de détention (et des swaps).",
    "C2 : mécanique de S2 (cible de volatilité 10 %/√N, N = symboles dont le signal est calculable, levier "
    "10, rééquilibrage au-delà de 25 %, stop 4 ATR puis à plat jusqu'au rééquilibrage suivant, plafond de "
    "risque ouvert de 4 % non appliqué). Signal 1 si la clôture est STRICTEMENT au-dessus de la SMA, sinon 0 "
    "(la position est fermée) ; jamais de vente. Décision à la dernière clôture de la semaine ISO (du mois "
    "calendaire pour la variante mensuelle), exécution à l'ouverture suivante.",
    "C2, univers : indices, métaux, et les classes « énergies » et « crypto » si elles existent ; jamais le "
    "forex ; la classe « matières premières » n'est pas citée par le plan et n'est pas incluse. Crypto : "
    "volatilité × √365.",
    "Référence de C2 (critère 7) : même calcul avec le signal forcé à 1 dès que la SMA existe (même période, "
    "même N, même cible de volatilité, même stop). Critère : Sharpe plus élevé ET pire baisse au plus égale "
    "aux 2/3 de celle de la référence.",
    "P = C1 + C2 + S3 : chaque composante est simulée séparément sur un tiers du capital (tailles de lots "
    "réalistes pour ce tiers), et le rendement journalier de P est la moyenne des rendements des trois "
    "composantes (poids constants d'un tiers, comme un compte unique où chacune dimensionne sur le tiers de "
    "l'equity totale). Un jour sans bougie pour une composante, son rendement vaut 0. Pire prix : moyenne "
    "des rendements au pire prix (pires instants supposés simultanés).",
    "P n'est évaluée, et même calculée, que si au moins une composante est retenue SEULE avec les critères "
    "du cycle 2 ; S3 est alors jugée exactement comme au cycle 1 (référence US500) mais avec t-stat >= 3,0.",
    "P, robustesse : 9 versions où une seule composante est remplacée par l'une de ses variantes voisines ; "
    "coûts doublés sur les trois composantes ; part des symboles positifs appliquée aussi à P (prudence). "
    "Critère 7 de P : Sharpe plus élevé que la MEILLEURE des références de ses composantes.",
    "P, capital minimum : chaque composante ne dispose que d'un tiers du capital, le besoin de chaque signal "
    "est multiplié par 3.",
    "Nouveaux marchés (plan §5) : un symbole est « nouveau » si son nom générique est absent de l'univers de "
    "référence (univers.json de référence et univers du développement du cycle 2, symboles exclus compris). "
    "L'univers du nouveau broker est chargé en entier (pour les conversions en USD) mais les finalistes ne "
    "tradent que les nouveaux symboles de leurs classes, sur la période de développement seulement. Sharpe "
    "négatif : échec bloquant ; aucun nouveau marché ou Sharpe non calculable : non concluant, donc bloquant.",
]

LIMITES_CYCLE2 = [
    "Les leçons du cycle 1 viennent des mêmes données de développement : la preuve décisive reste le contrôle "
    "final (une seule fois), les nouveaux marchés et au moins 3 mois de démo.",
    "Seuls les swaps ACTUELS sont connus ; ils sont appliqués à tout l'historique (les positions de C1 durent "
    "environ 4 jours, celles de C2 des semaines ou des mois).",
    "Les jours fériés ne sont connus que par l'absence de bougie ; C1 calcule J sur le calendrier lundi-vendredi.",
    "Les nouveaux symboles d'un autre broker n'ont pas de plancher de spread fixé à l'avance : leur coût repose "
    "sur leurs statistiques de spread mesurées.",
    "Le moteur ne modélise ni appel de marge, ni rejet d'ordre, ni distance minimale de stop.",
    "Résultats passés : même une hypothèse confirmée ne garantit rien ; elle ne mène qu'à la démo.",
]

NOMS_KO = {1: "trop peu de données ou de trades", 2: "Sharpe trop faible", 3: "t-stat trop faible (< 3,0)",
           4: "pire baisse trop forte", 5: "trop peu d'années positives", 6: "pas assez robuste",
           7: "pas mieux que la même méthode toujours acheteuse"}


def _raisons(v: dict) -> str:
    return ", ".join(NOMS_KO[k] for k in v.get("criteres_ko", []))


def _tableau_criteres(v: dict) -> list:
    L = [_ligne("n°", "critère (plan cycle 2 §3)", "valeur", "seuil", "résultat"),
         _ligne("---", "---", "---", "---", "---")]
    for c in v.get("criteres", []):
        L.append(_ligne(c["numero"], c["nom"], c["valeur"], c["seuil"], "OK" if c["ok"] else "KO"))
    return L


def rediger_rapport_cycle2(resume: dict) -> str:
    meta = resume.get("meta", {})
    strategies = resume.get("strategies", {})
    vg = resume.get("verdict_global") or {}
    L = ["# Programme de recherche — cycle 2 — rapport", ""]
    L.append(f"_Généré le {meta.get('genere_le', '?')} — source : {meta.get('source', '?')} — plan : "
             "docs/RECHERCHE_PLAN_CYCLE2.md (règles et critères fixés avant les calculs)._")
    if meta.get("synthetique"):
        L += ["", "> **Données synthétiques** : ce rapport teste le moteur, il ne dit RIEN des vrais marchés."]
    L += ["", "## En bref", ""]
    cf = resume.get("controle_final")
    if cf:
        L.append(f"**Contrôle final : {cf.get('decision_globale', '?')}.**")
        for nom, r in (cf.get("finalistes") or {}).items():
            L.append(f"- {nom} : {r['verdict']['decision']} (rendement 12 mois {_n(r.get('rendement_12m_pct'), 1, ' %')}, "
                     f"5e centile attendu {_n(r.get('p5_pct'), 1, ' %')}, pire baisse {_n(r.get('dd_pire_pct'), 1, ' %')}).")
        L.append("")
    nm = resume.get("nouveaux_marches")
    if nm:
        L.append("**Test des nouveaux marchés (bloquant si Sharpe négatif) :**")
        for nom, r in (nm.get("finalistes") or {}).items():
            L.append(f"- {nom} : {r['verdict']['decision']} (Sharpe {_n(r.get('sharpe'))}, "
                     f"{r.get('nb_trades')} trades sur {', '.join(r.get('symboles') or []) or 'aucun symbole'}).")
        L.append("")
    L.append(f"**Verdict du développement (cycle 2) : {vg.get('decision', 'incomplet (sections manquantes)')}.** "
             f"{vg.get('explication', '')}")
    L.append("")
    for code in ("C1", "C2", "P"):
        if code not in strategies:
            continue
        s = strategies[code]
        v = s.get("verdict") or {}
        b = s.get("base") or {}
        if v.get("decision") == "NON ÉVALUÉE":
            L.append(f"- **{code}** ({DESCRIPTIONS[code]}) : **NON ÉVALUÉE** — {v.get('raison', '')}.")
            continue
        txt = f"- **{code}** ({DESCRIPTIONS[code]}) : **{v.get('decision', 'non calculée')}**"
        if v and not v.get("retenue"):
            txt += f" — {_raisons(v)}"
        if b.get("sharpe") is not None and b["sharpe"] > 3:
            txt += " — ATTENTION : résultat trop beau, présumé faux (GARDE_FOUS §5)"
        txt += (f". Sharpe {_n(b.get('sharpe'))}, t-stat {_n(b.get('tstat'))}, {_n(b.get('cagr_pct'), 1, ' %')} "
                f"par an, pire baisse {_n(b.get('dd_pire_pct'), 1, ' %')}, {b.get('nb_trades', 'n.d.')} trades. "
                f"Faisabilité avec 20 $ (taille des positions seulement) : {_phrase_petit_capital(s.get('capital'))}.")
        L.append(txt)
    L += ["", "**Ce que « retenue » veut dire** : seulement que l'hypothèse passe les critères sur les données déjà "
          "connues. Il reste le contrôle final (12 mois jamais regardés, une seule fois), le test sur des marchés "
          "jamais vus et au moins 3 mois de démo. Un backtest ne garantit rien.", ""]

    L += ["## Conditions du test", ""]
    L.append(f"- Développement : jusqu'au {meta.get('fin_developpement', '2025-11-13')} inclus. Le contrôle final "
             "(2025-11-14 → 2026-11-13) est verrouillé dès le chargement"
             + (" et a été utilisé (voir plus bas)." if cf else " et n'a PAS été regardé."))
    L.append(f"- Critères : ceux du cycle 1 avec t-stat >= {SEUILS_CYCLE2['tstat_min']:.1f} et la référence « même "
             "méthode toujours acheteuse » (critère 7).")
    L.append(f"- Capital simulé : {_n(meta.get('capital', 10000), 0)} $ ; C1 : 0,5 % de risque par position ; C2 : "
             "cible de volatilité ; P : un tiers du capital par composante. Coûts complets (spread, glissements, "
             "swaps, conversion en USD) comme au cycle 1.")
    u = meta.get("univers") or {}
    if u:
        par_classe = {}
        for nom, c in (u.get("symboles") or {}).items():
            par_classe.setdefault(c, []).append(nom)
        L.append("- Univers chargé : " + " ; ".join(f"{NOMS_CLASSES.get(c, c)} : {', '.join(sorted(v))}"
                                                    for c, v in sorted(par_classe.items())))
        if u.get("absents"):
            L.append("- Absents chez le broker : " + " ; ".join(f"{k} ({v})" for k, v in u["absents"].items()))
        if u.get("exclus"):
            L.append("- Exclus : " + " ; ".join(f"{k} ({v})" for k, v in u["exclus"].items()))
    L.append("")

    for code in ("C1", "C2", "P"):
        if code in strategies:
            L.extend(_section(code, strategies[code]))
    s3 = (resume.get("composantes") or {}).get("S3")
    if s3:
        v = s3.get("verdict") or {}
        b = s3.get("base") or {}
        L += ["## S3 jugée seule avec les critères du cycle 2 (sert seulement à décider si P est évaluée)", "",
              f"**{v.get('decision', 'incomplet')}** — Sharpe {_n(b.get('sharpe'))}, t-stat {_n(b.get('tstat'))}, "
              f"pire baisse {_n(b.get('dd_pire_pct'), 1, ' %')}, {b.get('nb_trades', 'n.d.')} trades.", ""]
        if v.get("criteres"):
            L += _tableau_criteres(v) + [""]

    if cf:
        L += ["## Contrôle final (calculé une seule fois)", "",
              f"_Calculé le {cf.get('calcule_le', '?')}. Ne plus jamais le relancer pour ces hypothèses._", ""]
        for nom, r in (cf.get("finalistes") or {}).items():
            L += [f"### {nom} : {r['verdict']['decision']}", "", _ligne("n°", "critère", "valeur", "seuil", "résultat"),
                  _ligne("---", "---", "---", "---", "---")]
            for c in r["verdict"]["criteres"]:
                L.append(_ligne(c["numero"], c["nom"], c["valeur"], c["seuil"], "OK" if c["ok"] else "KO"))
            L += ["", f"Période {r.get('debut')} → {r.get('fin')}, {r.get('nb_trades')} trades, Sharpe "
                      f"{_n(r.get('sharpe'))}.", ""]
    if nm:
        L += ["## Nouveaux marchés (plan cycle 2 §5)", "",
              f"_Calculé le {nm.get('calcule_le', '?')} sur {nm.get('source', '?')}, période de développement "
              "seulement._", "",
              "Nouveaux symboles (absents de l'univers de référence) : "
              + (", ".join(f"{k} ({NOMS_CLASSES.get(c, c)})" for k, c in sorted((nm.get("nouveaux") or {}).items()))
                 or "aucun") + ".", ""]
        L += [_ligne("finaliste", "symboles tradés", "trades", "Sharpe", "t-stat", "pire baisse", "décision"),
              _ligne("---", "---", "---:", "---:", "---:", "---:", "---")]
        for nom, r in (nm.get("finalistes") or {}).items():
            L.append(_ligne(nom, ", ".join(r.get("symboles") or []) or "aucun", r.get("nb_trades"), _n(r.get("sharpe")),
                            _n(r.get("tstat")), _n(r.get("dd_pire_pct"), 1, " %"), r["verdict"]["decision"]))
        L.append("")

    L += ["## Interprétations prudentes des règles du plan", ""]
    L += [f"- {x}" for x in INTERPRETATIONS_CYCLE2] + [""]
    L += ["## Limites connues", ""]
    L += [f"- {x}" for x in LIMITES_CYCLE2] + [""]
    t = resume.get("temps") or {}
    if t:
        L += ["## Temps de calcul (dernière commande)", "",
              ", ".join(f"{k} {v:.1f} s" for k, v in t.items() if isinstance(v, (int, float))), ""]
    return "\n".join(L)


def _section(code: str, s: dict) -> list:
    L = [f"## {code} — {DESCRIPTIONS.get(code, '')}", ""]
    v = s.get("verdict") or {}
    if v.get("decision") == "NON ÉVALUÉE":
        return L + [f"**NON ÉVALUÉE** : {v.get('raison', '')}. Règle du plan : la combinaison n'est jugée que si au "
                    "moins une de ses composantes est retenue seule ; elle n'a donc pas été calculée.", ""]
    b = s.get("base") or {}
    if v:
        L += [f"**{v.get('decision')}**", ""] + _tableau_criteres(v) + [""]
    if b.get("sharpe") is not None and b["sharpe"] > 3:
        L += ["**ATTENTION : résultat « trop beau » (Sharpe > 3), présumé faux jusqu'à preuve du contraire "
              "(docs/GARDE_FOUS.md §5).**", ""]
    if b:
        L += [_ligne("mesure", "valeur"), _ligne("---", "---:")]
        lignes = [
            ("Période évaluée", f"{b.get('debut')} → {b.get('fin')} ({_n(b.get('annees'), 1)} ans)"),
            ("Symboles simulés", f"{b.get('nb_symboles')}"),
            ("Trades / signaux refusés", f"{b.get('nb_trades')} / {b.get('nb_refus')}"),
            ("Gagnants", _n(b.get("pct_gagnants"), 1, " %")),
            ("Rendement total", _n(b.get("rendement_total_pct"), 1, " %")),
            ("Rendement annualisé (CAGR)", _n(b.get("cagr_pct"), 2, " %")),
            ("Volatilité annualisée", _n(b.get("vol_annuelle_pct"), 1, " %")),
            ("Sharpe / t-stat", f"{_n(b.get('sharpe'))} / {_n(b.get('tstat'))}"),
            ("Pire baisse (clôture / pire prix)", f"{_n(b.get('dd_cloture_pct'), 1, ' %')} / {_n(b.get('dd_pire_pct'), 1, ' %')}"),
            ("Années civiles positives", _n(b.get("pct_annees_positives"), 0, " %")),
            ("Swaps payés (-) ou reçus (+)", _n(b.get("swaps_usd"), 0, " $")),
            ("Spread et glissements payés", _n(b.get("couts_execution_usd"), 0, " $")),
            ("Arrêt -15 % (daté, non bloquant)", b.get("date_arret_15") or "jamais atteint"),
        ]
        ann = {k.split(":", 1)[1]: n for k, n in (b.get("compteurs") or {}).items() if k.startswith("annulation:")}
        if ann.get("jour_entree_absent"):
            lignes.append(("Ordres annulés, jour d'entrée absent des données", str(ann["jour_entree_absent"])))
        if code == "C2":
            lignes.append(("Rééquilibrages hebdomadaires", str(b.get("nb_reequilibrages"))))
        L += [_ligne(k, x) for k, x in lignes] + [""]
        if b.get("refus"):
            L += ["Signaux non pris : " + " ; ".join(f"{RAISONS.get(k, k)} : {n}" for k, n in b["refus"].items()) + ".", ""]
        if b.get("exclus"):
            L += ["Symboles exclus : " + " ; ".join(f"{k} ({x})" for k, x in b["exclus"].items()), ""]
        ref = s.get("reference") or {}
        if ref:
            if code == "P":
                comp = ref.get("composantes") or {}
                L += [f"Référence ({ref.get('nom')}) : Sharpe {_n(ref.get('sharpe'))} ; références des composantes : "
                      + ", ".join(f"{k} {_n(x)}" for k, x in comp.items()) + ".", ""]
            else:
                L += [f"Référence ({ref.get('nom')}), coûts compris : Sharpe {_n(ref.get('sharpe'))}, t-stat "
                      f"{_n(ref.get('tstat'))}, {_n(ref.get('cagr_pct'), 2, ' %')} par an, pire baisse "
                      f"{_n(ref.get('dd_pire_pct'), 1, ' %')}, {ref.get('nb_trades')} trades.", ""]
        cl = b.get("contribution_classes") or {}
        if cl:
            L += ["Contribution par classe : " + " ; ".join(f"{NOMS_CLASSES.get(k, k)} {_n(x, 0, ' $')}"
                                                            for k, x in sorted(cl.items())) + ".", ""]
        cs = b.get("contribution_symboles") or {}
        if cs:
            nb = b.get("trades_par_symbole") or {}
            L += [_ligne("symbole", "trades", "résultat net"), _ligne("---", "---:", "---:")]
            L += [_ligne(k, nb.get(k, 0), _n(cs[k], 0, " $")) for k in sorted(cs)] + [""]
        ac = b.get("annees_civiles") or {}
        if ac:
            L += ["Par année : " + " ; ".join(f"{k} {_n(x, 1, ' %')}" for k, x in sorted(ac.items())) + ".", ""]
        bs = s.get("bootstrap") or {}
        if bs.get("p5_pct") is not None:
            L += [f"Bootstrap (blocs de 20 jours, {bs.get('nb_tirages')} tirages) : 5e centile du rendement sur 12 mois "
                  f"{_n(bs['p5_pct'], 1, ' %')}, médiane {_n(bs.get('p50_pct'), 1, ' %')} (seuil du contrôle final).", ""]
    rb = s.get("robustesse")
    if rb:
        L += ["Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :", "",
              _ligne("version", "Sharpe", "t-stat", "CAGR", "pire baisse", "trades"),
              _ligne("---", "---:", "---:", "---:", "---:", "---:")]
        for nom, m in list((rb.get("variantes") or {}).items()) + [("coûts doublés", rb.get("couts_doubles") or {})]:
            L.append(_ligne(nom, _n(m.get("sharpe")), _n(m.get("tstat")), _n(m.get("cagr_pct"), 2, " %"),
                            _n(m.get("dd_pire_pct"), 1, " %"), m.get("nb_trades")))
        L.append("")
    cap = s.get("capital")
    if cap:
        ms, mc = cap.get("minimum_standard") or {}, cap.get("minimum_cent") or {}
        L += ["Petit capital (plan §6 du cycle 1) :", "",
              f"- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : "
              f"**{_n(ms.get('capital_min'), 0, ' $')}** sur un compte standard, **{_n(mc.get('capital_min'), 2, ' $')}** "
              f"sur un compte cent ({ms.get('nb_signaux')} signaux)."]
        for nom, k in (("compte standard", "sim_20_standard"), ("compte cent", "sim_20_cent")):
            x = cap.get(k) or {}
            if x:
                L.append(f"- Simulation à 20 $ sur un {nom} : {x.get('nb_trades')} trades pris sur {x.get('nb_signaux')} "
                         f"signaux ; capital final {_n(x.get('equity_finale'), 2, ' $')} ; pire baisse "
                         f"{_n(x.get('dd_pire_pct'), 1, ' %')}.")
        L += [f"- Conclusion : {_phrase_petit_capital(cap)}.", ""]
    return L
