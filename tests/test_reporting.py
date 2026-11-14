"""Tests de sentitrade/reporting.py : métriques calculées à la main, Monte Carlo, références, verdict (spec §6)."""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from sentitrade import reporting as rp
from sentitrade.backtest import executer_backtest
from sentitrade.config import Config, SymboleSpec
from sentitrade.strategy import preparer_signaux
from sentitrade.synthetique import generer_jeu

T = pd.Timestamp
CFG = Config()
SPEC = SymboleSpec()


def trades_manuels():
    """5 trades : R = +1, -1, -1, +0.5, +2 ; P&L = +10, -10, -10, +5, +20 $."""
    return pd.DataFrame({
        "entree_a": pd.to_datetime(["2025-01-06 10:05", "2025-01-06 14:00", "2025-02-03 10:30",
                                    "2025-02-04 16:00", "2026-03-02 10:00"]),
        "sortie_a": pd.to_datetime(["2025-01-06 11:00", "2025-01-06 15:00", "2025-02-03 11:30",
                                    "2025-02-04 17:00", "2026-03-02 21:55"]),
        "sens": [1, -1, 1, 1, -1],
        "pnl": [10.0, -10.0, -10.0, 5.0, 20.0],
        "r_multiple": [1.0, -1.0, -1.0, 0.5, 2.0],
        "raison_sortie": ["stop_breakeven", "stop", "stop", "cloture_forcee", "stop_breakeven"],
    })


class TestMetriques(unittest.TestCase):

    def test_metriques_trades_a_la_main(self):
        m = rp.metriques_trades(trades_manuels())
        self.assertEqual(m["nb_trades"], 5)
        self.assertAlmostEqual(m["taux_reussite"], 0.6)
        self.assertAlmostEqual(m["gain_moyen_r"], (1 + 0.5 + 2) / 3)
        self.assertAlmostEqual(m["perte_moyenne_r"], -1.0)
        self.assertAlmostEqual(m["esperance_r"], 0.3)
        self.assertAlmostEqual(m["esperance_usd"], 3.0)
        self.assertAlmostEqual(m["profit_factor"], 35.0 / 20.0)
        self.assertEqual(m["serie_perdante_max"], 2)
        ecart = np.std([1, -1, -1, 0.5, 2], ddof=1)
        self.assertAlmostEqual(m["ecart_type_r"], ecart)
        self.assertAlmostEqual(m["t_stat"], 0.3 / (ecart / math.sqrt(5)))
        self.assertAlmostEqual(m["r_total"], 1.5)

    def test_sans_trade_et_sans_perte(self):
        self.assertEqual(rp.metriques_trades(trades_manuels().iloc[:0])["nb_trades"], 0)
        gagnants = trades_manuels().iloc[[0, 4]]
        self.assertTrue(math.isinf(rp.metriques_trades(gagnants)["profit_factor"]))

    def test_drawdown_a_la_main(self):
        eq = pd.Series([100.0, 110.0, 99.0, 105.0, 120.0, 90.0],
                       index=pd.date_range("2025-01-01", periods=6, freq="D"))
        dd_pct, dd_usd, duree = rp.drawdown(eq)
        self.assertAlmostEqual(dd_pct, 25.0)        # (120 - 90) / 120
        self.assertAlmostEqual(dd_usd, 30.0)
        self.assertAlmostEqual(duree, 2.0)          # sous le plus haut du 02/01 au 04/01

    def test_metriques_equity(self):
        idx = pd.DatetimeIndex([T("2025-01-01 21:00"), T("2025-07-01 21:00"), T("2026-01-01 21:00")])
        eq = pd.Series([3000.0, 2700.0, 3300.0], index=idx)
        m = rp.metriques_equity(eq, 3000.0, T("2025-01-01"), T("2026-01-01 06:00"))
        self.assertAlmostEqual(m["rendement_total_pct"], 10.0)
        annees = (T("2026-01-01 06:00") - T("2025-01-01")).days / 365.25
        self.assertAlmostEqual(m["cagr_pct"], (1.1 ** (1 / annees) - 1) * 100)
        self.assertAlmostEqual(m["dd_max_pct"], 10.0)
        r = np.array([0.0, -0.1, 3300 / 2700 - 1])
        self.assertAlmostEqual(m["sharpe_journalier"], r.mean() / r.std(ddof=1) * math.sqrt(252))

    def test_ventilations_et_mois(self):
        v = rp.ventilations(trades_manuels())
        sens = {l["cle"]: l for l in v["sens"]}
        self.assertEqual(sens["long"]["nb"], 3)
        self.assertAlmostEqual(sens["long"]["esperance_r"], 0.5 / 3)
        self.assertAlmostEqual(sens["short"]["pnl_total"], 10.0)
        annees = {l["cle"]: l["nb"] for l in v["annee"]}
        self.assertEqual(annees, {"2025": 4, "2026": 1})
        heures = {l["cle"]: l["nb"] for l in v["heure"]}
        self.assertEqual(heures["10h"], 3)
        raisons = {l["cle"]: l["r_total"] for l in v["raison_sortie"]}
        self.assertAlmostEqual(raisons["stop"], -2.0)
        self.assertEqual(rp.mois_perdants(trades_manuels()), (3, 1))   # 2025-01 : 0 ; 2025-02 : -5 ; 2026-03 : +20

    def test_buy_and_hold(self):
        idx = pd.date_range("2025-01-06 10:00", periods=4, freq="1D")
        b = pd.DataFrame({"open": [100.0, 110, 90, 99], "high": [101.0, 111, 91, 100],
                          "low": [99.0, 109, 89, 98], "close": [100.0, 110, 90, 99.0], "spread": [100, 0, 0, 0]},
                         index=idx)
        r = rp.buy_and_hold(b, point=0.01)
        self.assertAlmostEqual(r["prix_debut"], 101.0)           # Ask = 100 + 100 points × 0.01
        self.assertAlmostEqual(r["rendement_pct"], (99.0 / 101.0 - 1) * 100)
        self.assertAlmostEqual(r["dd_max_pct"], (110 - 90) / 110 * 100)

    def test_coupure_is_oos(self):
        self.assertEqual(rp.date_coupure("2023-01-01", "2026-01-01"), T("2024-10-19"))
        self.assertEqual(rp.date_coupure("2025-01-01", "2025-01-11"), T("2025-01-07"))


class TestMonteCarlo(unittest.TestCase):

    def test_permutations_a_la_main(self):
        mc = rp.monte_carlo(np.array([-1.0, -1.0, 1.0, 1.0]), 1.0, permutations=1000, graine=1)
        self.assertTrue(mc["disponible"])
        self.assertAlmostEqual(mc["rendement_final_pct"], (0.99 ** 2 * 1.01 ** 2 - 1) * 100)
        # pire ordre : deux pertes d'affilée => 1 - 0.99² = 1.99 % ; meilleur ordre : 1 %
        self.assertAlmostEqual(mc["dd_max"], (1 - 0.99 ** 2) * 100)
        self.assertGreaterEqual(mc["dd_p5"], 1.0 - 1e-9)
        self.assertLessEqual(mc["dd_p95"], mc["dd_max"] + 1e-9)

    def test_reproductible_et_vide(self):
        r = np.random.default_rng(0).normal(0, 1, 200)
        self.assertEqual(rp.monte_carlo(r, 1.0), rp.monte_carlo(r, 1.0))
        self.assertFalse(rp.monte_carlo(np.array([]), 1.0)["disponible"])


def resume_type(esp_oos=0.2, pf_oos=1.5, n_total=150, n_oos=60, dd=10.0, dd_mc=20.0, esp_tot=0.25,
                p75=0.0, p90=0.05, plafonds=(0.1, 0.1, 0.1, 0.1), couts=(0.05, 0.05), synthetique=False):
    sens = [{"groupe": "sl_plafond x mode_entree", "mode_entree": "bord", "sl_plafond": sl, "libelle": f"sl={sl}",
             "esp_is": e, "esp_oos": e, "est_base": sl == 5.0, "nb_is": 50, "nb_oos": 40, "pf_oos": 1.3,
             "esp_total": e, "dd_is": 5, "dd_oos": 5, "arret_is": False, "arret_oos": False}
            for sl, e in zip((3.0, 5.0, 8.0, 12.0), plafonds)]
    sens += [{"groupe": "sl_plafond x mode_entree", "mode_entree": "milieu", "sl_plafond": 5.0, "libelle": "milieu",
              "esp_is": -1.0, "esp_oos": -1.0, "est_base": False, "nb_is": 1, "nb_oos": 1, "pf_oos": 0.1,
              "esp_total": -1.0, "dd_is": 5, "dd_oos": 5, "arret_is": False, "arret_oos": False},
             {"groupe": "couts", "mode_entree": "bord", "sl_plafond": 5.0, "libelle": "coûts doublés",
              "esp_is": couts[0], "esp_oos": couts[1], "est_base": False, "nb_is": 50, "nb_oos": 40, "pf_oos": 1.1,
              "esp_total": 0.0, "dd_is": 5, "dd_oos": 5, "arret_is": False, "arret_oos": False}]
    return {
        "meta": {"synthetique": synthetique, "graine": 1},
        "base": {"nb_trades": n_total, "esperance_r": esp_tot, "dd_max_pct": dd},
        "isoos": {"coupure": "2025-01-01", "is": {"nb_trades": n_total - n_oos, "esperance_r": 0.3},
                  "oos": {"nb_trades": n_oos, "esperance_r": esp_oos, "profit_factor": pf_oos}},
        "references": {"tendance_seule": {"disponible": True, "p75": p75, "p90": p90}},
        "montecarlo": {"disponible": True, "dd_p95": dd_mc},
        "sensibilite": sens,
    }


class TestVerdict(unittest.TestCase):

    def test_go(self):
        v = rp.calculer_verdict(resume_type())
        self.assertEqual(v["decision"], "GO")
        self.assertEqual(len(v["criteres"]), 6)
        self.assertTrue(all(c["ok"] for c in v["criteres"]))

    def test_nogo_esperance_oos_negative_ou_nulle(self):
        for esp in (0.0, -0.05):
            v = rp.calculer_verdict(resume_type(esp_oos=esp))
            self.assertEqual(v["decision"], "NO-GO")
            self.assertFalse(v["criteres"][1]["ok"])

    def test_nogo_sous_le_75e_percentile(self):
        v = rp.calculer_verdict(resume_type(esp_tot=0.04, p75=0.05, p90=0.10))
        self.assertEqual(v["decision"], "NO-GO")
        self.assertFalse(v["criteres"][4]["ok"])

    def test_nogo_sans_trade_oos(self):
        self.assertEqual(rp.calculer_verdict(resume_type(n_oos=0, esp_oos=None, pf_oos=None))["decision"], "NO-GO")

    def test_a_creuser(self):
        cas = {
            "trop peu de trades OOS": dict(n_oos=39),
            "espérance OOS positive mais < 0.10": dict(esp_oos=0.09),
            "profit factor OOS < 1.2": dict(pf_oos=1.19),
            "drawdown > 15 %": dict(dd=15.01),
            "Monte Carlo p95 > 25 %": dict(dd_mc=25.5),
            "entre p75 et p90": dict(esp_tot=0.07, p75=0.05, p90=0.08),
            "2 plafonds sur 4": dict(plafonds=(0.1, 0.1, -0.01, -0.2)),
            "coûts doublés négatifs en OOS": dict(couts=(0.05, -0.01)),
        }
        for nom, kw in cas.items():
            with self.subTest(nom):
                v = rp.calculer_verdict(resume_type(**kw))
                self.assertEqual(v["decision"], "À CREUSER")
                self.assertEqual(sum(1 for c in v["criteres"] if not c["ok"]), 1)

    def test_seuils_inclus(self):
        # Valeurs exactement au seuil : >= 100 / >= 40, >= 0.10 R, >= 1.2, <= 15 %, <= 25 % => OK.
        v = rp.calculer_verdict(resume_type(n_total=100, n_oos=40, esp_oos=0.10, pf_oos=1.2, dd=15.0, dd_mc=25.0))
        self.assertEqual(v["decision"], "GO")
        # 3 plafonds sur 4 suffisent ; espérance égale au p90 ne suffit pas (strictement au-dessus).
        self.assertEqual(rp.calculer_verdict(resume_type(plafonds=(0.1, 0.1, 0.1, -0.1)))["decision"], "GO")
        self.assertEqual(rp.calculer_verdict(resume_type(esp_tot=0.05, p90=0.05))["decision"], "À CREUSER")

    def test_incomplet(self):
        r = resume_type()
        del r["montecarlo"]
        v = rp.calculer_verdict(r)
        self.assertEqual(v["decision"], "INCOMPLET")
        self.assertIn("montecarlo", v["sections_manquantes"])
        self.assertIsNone(v["criteres"][3]["ok"])

    @staticmethod
    def pour_rapport(**kw):
        """resume_type complété des champs que le rapport affiche."""
        r = resume_type(**kw)
        r["base"].update({"debut": "2023-01-02 00:00:00", "fin": "2026-01-01 00:00:00", "balance_initiale": 3000.0,
                          "taux_reussite": 0.5, "esperance_usd": 7.5, "rendement_total_pct": 12.0,
                          "balance_finale": 3360.0, "nb_mois": 30, "nb_mois_perdants": 9})
        r["montecarlo"].update({"permutations": 1000, "nb_trades": 150, "risque_pct": 1.0, "graine": 1,
                                "dd_p50": 10.0, "dd_max": 30.0, "rendement_final_pct": 12.0,
                                "bootstrap_rendement_p5": -5.0, "bootstrap_rendement_p95": 30.0,
                                "bootstrap_proba_perte": 0.1})
        r["references"]["tendance_seule"].update({"tirages": 200, "trades_par_tirage": 150, "graine": 1, "p50": -0.1,
                                                  "percentile_strategie": 99.0})
        return r

    def test_rapport_affiche_criteres_et_bandeau(self):
        r = self.pour_rapport(synthetique=True, esp_oos=-0.1)
        texte = rp.rediger_rapport(r)
        self.assertTrue(texte.startswith("# ⚠ DONNÉES SYNTHÉTIQUES — ce rapport ne dit rien sur la rentabilité réelle"))
        self.assertIn("**Verdict : NO-GO.**", texte)
        self.assertIn("| 2 | Espérance hors échantillon (OOS), après coûts | -0.100 R | >= +0.10 R | KO |", texte)
        self.assertIn("| 3 | Profit factor hors échantillon | 1.50 | >= 1.2 | OK |", texte)
        self.assertNotIn("DONNÉES SYNTHÉTIQUES", rp.rediger_rapport(self.pour_rapport()))


class TestSurDonneesSynthetiques(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.m1, cls.m15, cls.h1 = generer_jeu("2024-01-01", "2025-01-01", 21)
        cls.sig = preparer_signaux(cls.m15, cls.h1, CFG, SPEC)
        cls.debut, cls.fin = T("2024-06-03"), T("2025-01-01")
        cls.res = executer_backtest(cls.m1, cls.m15, cls.h1, CFG, SPEC, 3000.0, cls.debut, cls.fin, signaux=cls.sig)

    def test_resume_complet_et_json(self):
        import json
        b = rp.resumer_resultat(self.res)
        self.assertEqual(b["nb_trades"], len(self.res.trades))
        self.assertAlmostEqual(b["balance_finale"], self.res.balance_finale, places=6)
        json.dumps(b)
        ev = rp.compter_evenements(self.res.evenements)
        self.assertEqual(ev["entrees"], len(self.res.trades))

    def test_reference_tendance_seule(self):
        tr = self.res.trades
        self.assertGreater(len(tr), 10)
        kw = dict(debut=self.debut, fin=self.fin, resolution="m1", tirages=30, graine=7,
                  esperance_strategie=float(tr["r_multiple"].mean()))
        a = rp.reference_tendance_seule(self.m1, self.sig, CFG, SPEC, len(tr), tr["distance_sl_reelle"], **kw)
        b = rp.reference_tendance_seule(self.m1, self.sig, CFG, SPEC, len(tr), tr["distance_sl_reelle"], **kw)
        self.assertTrue(a["disponible"])
        self.assertEqual(a, b)                                  # graine fixe => reproductible
        self.assertEqual(len(a["esperances"]), 30)
        self.assertLessEqual(a["p50"], a["p75"])
        self.assertLessEqual(a["p75"], a["p90"])
        self.assertTrue(0 <= a["percentile_strategie"] <= 100)
        # Marche aléatoire : la référence ne gagne pas non plus (moyenne de tous les trades tirés).
        self.assertLess(a["esperance_par_trade"], 0.15)
        self.assertFalse(rp.reference_tendance_seule(self.m1, self.sig, CFG, SPEC, 0, [], **kw)["disponible"])

    def test_is_oos_et_sensibilite(self):
        io = rp.executer_is_oos(self.m1, self.m15, self.h1, CFG, SPEC, 3000.0, self.debut, self.fin, "m1",
                                signaux=self.sig)
        coupure = T(io["coupure"])
        self.assertEqual(coupure, rp.date_coupure(self.debut, self.fin))
        self.assertEqual(io["is"]["fin"], str(coupure))
        self.assertEqual(io["oos"]["debut"], str(coupure))
        configs = rp.configurations_sensibilite(CFG)
        self.assertEqual(len(configs), 8 + 3 + 2 + 1)
        couts = configs[-1][2].execution
        self.assertAlmostEqual(couts.glissement_entree, 2 * CFG.execution.glissement_entree)
        self.assertAlmostEqual(couts.glissement_stop, 2 * CFG.execution.glissement_stop)

    def test_graphiques(self):
        with tempfile.TemporaryDirectory() as d:
            rp.tracer_graphiques(self.res.equity_journaliere, d, rp.cours_journalier(self.m1, self.debut, self.fin))
            self.assertGreater((Path(d) / "equity.png").stat().st_size, 1000)
            self.assertGreater((Path(d) / "drawdown.png").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
