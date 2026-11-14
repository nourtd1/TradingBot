"""Tests de sentitrade/recherche/evaluation.py : métriques et verdicts sur cas fabriqués, bootstrap,
capital minimum, et tests statistiques du moteur complet (marche aléatoire / tendance injectée)."""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from sentitrade.recherche import evaluation as ev
from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.synthetique import generer_univers


def resultat(equity, pire=None, trades=None, symboles=None, capital=10000.0, tentatives=None):
    idx = pd.bdate_range("2010-01-01", periods=len(equity))
    eq = pd.DataFrame({"equity": equity, "equity_pire": pire if pire is not None else equity,
                       "balance": equity}, index=idx)
    tr = trades if trades is not None else pd.DataFrame(columns=mo.COLONNES_TRADES)
    return mo.ResultatSimulation("S1", "base", capital, eq, tr, pd.DataFrame(columns=mo.COLONNES_EVENEMENTS),
                                 tentatives if tentatives is not None else pd.DataFrame(columns=mo.COLONNES_TENTATIVES),
                                 {"refus:lot_inferieur_minimum": 3}, {}, symboles or {}, idx[0], None)


class TestMetriques(unittest.TestCase):

    def test_sharpe_tstat_dd_a_la_main(self):
        # rendements alternés +1 % / -0,5 % sur 4 jours
        e = [10100.0, 10049.5, 10149.995, 10099.245025]
        r = np.array([0.01, -0.005, 0.01, -0.005])
        pire = [10000.0, 9900.0, 10149.995, 10099.245025]
        m = ev.metriques(resultat(e, pire))
        annees = (pd.bdate_range("2010-01-01", periods=4)[-1] - pd.Timestamp("2010-01-01")).days / 365.25
        obs = 4 / annees
        self.assertAlmostEqual(m["sharpe"], r.mean() / r.std(ddof=1) * math.sqrt(obs), places=6)
        self.assertAlmostEqual(m["tstat"], r.mean() / r.std(ddof=1) * 2, places=6)
        # DD au pire prix : jour 2, plus haut de la veille 10100, pire 9900 -> 1,98 %
        self.assertAlmostEqual(m["dd_pire_pct"], 200 / 10100 * 100, places=6)
        self.assertAlmostEqual(m["dd_cloture_pct"], 50.5 / 10100 * 100, places=6)
        self.assertEqual(m["refus"], {"lot_inferieur_minimum": 3})

    def test_annees_civiles_completes(self):
        idx = pd.bdate_range("2010-03-01", "2013-06-28")
        e = pd.Series(np.linspace(10000, 13000, len(idx)), index=idx)
        eq = pd.DataFrame({"equity": e, "equity_pire": e, "balance": e})
        ac = ev.annees_civiles(eq, 10000)
        self.assertEqual(sorted(ac), [2011, 2012])          # 2010 et 2013 incomplètes
        self.assertAlmostEqual(ac[2011], e[e.index.year == 2011].iloc[-1] / e[e.index.year == 2010].iloc[-1] - 1)

    def test_contributions_par_symbole_et_classe(self):
        tr = pd.DataFrame({"symbole": ["A", "A", "B"], "pnl_net_usd": [10.0, -4.0, -1.0], "r_multiple": [1, -1, -1],
                           "swaps_usd": 0.0, "couts_execution_usd": 0.0, "commissions_usd": 0.0, "barres": 1})
        m = ev.metriques(resultat([10000.0, 10005.0, 10005.0], trades=tr,
                                  symboles={"A": "forex", "B": "indices", "C": "indices"}))
        self.assertEqual(m["contribution_symboles"], {"A": 6.0, "B": -1.0, "C": 0.0})
        self.assertEqual(m["contribution_classes"], {"forex": 6.0, "indices": -1.0})
        self.assertAlmostEqual(m["part_symboles_positifs"], 1 / 3)   # un symbole sans trade n'est pas positif


def base_ok(**k):
    b = {"annees": 10.0, "nb_trades": 150, "sharpe": 0.8, "tstat": 3.0, "dd_pire_pct": 12.0,
         "pct_annees_positives": 70.0, "part_symboles_positifs": 0.6, "nb_symboles": 10, "nb_symboles_positifs": 6}
    b.update(k)
    return b


ROB_OK = {"variantes": {"a": {"sharpe": 0.4}, "b": {"sharpe": 0.31}}, "couts_doubles": {"sharpe": 0.35}}
REF = {"nom": "panier", "sharpe": 0.5}


class TestVerdict(unittest.TestCase):

    def test_tout_ok_retenue(self):
        v = ev.verdict_strategie("S1", base_ok(), ROB_OK, REF)
        self.assertTrue(v["retenue"], v)
        self.assertEqual(len(v["criteres"]), 7)

    def test_chaque_critere_peut_rejeter(self):
        cas = {1: dict(annees=7.9), 2: dict(sharpe=0.49), 3: dict(tstat=2.49), 4: dict(dd_pire_pct=15.01),
               5: dict(pct_annees_positives=59.9), 6: dict(part_symboles_positifs=0.49)}
        for num, k in cas.items():
            b = base_ok(**k)
            ref = {"sharpe": 0.1}
            v = ev.verdict_strategie("S1", b, ROB_OK, ref)
            self.assertFalse(v["retenue"], num)
            self.assertIn(num, v["criteres_ko"], num)
        v = ev.verdict_strategie("S1", base_ok(nb_trades=99), ROB_OK, REF)
        self.assertIn(1, v["criteres_ko"])
        rb = {"variantes": {"a": {"sharpe": 0.29}}, "couts_doubles": {"sharpe": 1.0}}
        self.assertIn(6, ev.verdict_strategie("S1", base_ok(), rb, REF)["criteres_ko"])
        rb = {"variantes": {"a": {"sharpe": 1.0}}, "couts_doubles": {"sharpe": 0.29}}
        self.assertIn(6, ev.verdict_strategie("S1", base_ok(), rb, REF)["criteres_ko"])
        self.assertIn(7, ev.verdict_strategie("S1", base_ok(sharpe=0.8), ROB_OK, {"sharpe": 0.8})["criteres_ko"])

    def test_seuils_limites_et_s4_s3(self):
        b = base_ok(sharpe=0.5, tstat=2.5, dd_pire_pct=15.0, pct_annees_positives=60.0, part_symboles_positifs=0.5)
        self.assertTrue(ev.verdict_strategie("S1", b, ROB_OK, {"sharpe": 0.49})["retenue"])
        self.assertTrue(ev.verdict_strategie("S4", base_ok(annees=4.0), ROB_OK, REF)["retenue"])
        self.assertFalse(ev.verdict_strategie("S4", base_ok(annees=3.99), ROB_OK, REF)["retenue"])
        # S3 : pas de critère sur les symboles
        self.assertTrue(ev.verdict_strategie("S3", base_ok(part_symboles_positifs=0.0), ROB_OK, REF)["retenue"])

    def test_valeur_manquante_ko(self):
        v = ev.verdict_strategie("S2", base_ok(), None, REF)
        self.assertEqual(v["criteres_ko"], [6])
        v = ev.verdict_strategie("S2", base_ok(tstat=None), ROB_OK, None)
        self.assertEqual(v["criteres_ko"], [3, 7])
        self.assertEqual(ev.verdict_global({"S1": v})["decision"], "NO-GO")
        ok = ev.verdict_strategie("S1", base_ok(), ROB_OK, REF)
        self.assertEqual(ev.verdict_global({"S1": ok, "S2": v})["retenues"], ["S1"])

    def test_verdict_controle(self):
        self.assertTrue(ev.verdict_controle(-2.0, -3.0, 10.0)["confirmee"])
        self.assertFalse(ev.verdict_controle(-4.0, -3.0, 10.0)["confirmee"])
        self.assertFalse(ev.verdict_controle(5.0, -3.0, 15.5)["confirmee"])
        self.assertFalse(ev.verdict_controle(None, -3.0, 1.0)["confirmee"])


class TestBootstrapEtCapital(unittest.TestCase):

    def test_bootstrap_rendement_constant(self):
        b = ev.bootstrap_12_mois(np.full(500, 0.001), 252, tirages=200)
        np.testing.assert_allclose(b, 1.001 ** 252 - 1)

    def test_bootstrap_blocs_contigus(self):
        r = np.zeros(400)
        r[100:120] = 0.01                                # un seul bloc de 20 jours à +1 %
        b = ev.bootstrap_12_mois(r, 20, bloc=20, tirages=3000, graine=1)
        valeurs = set(np.round(b, 10))
        self.assertIn(round(1.01 ** 20 - 1, 10), valeurs)   # bloc tiré exactement
        self.assertLessEqual(b.max(), 1.01 ** 20 - 1 + 1e-12)

    def test_capital_minimum(self):
        # 20 signaux : lot min 0.01 ; perte par lot 1000 $ (19 signaux) et 10 000 $ (1 signal).
        t = pd.DataFrame({"symbole": ["A"] * 20, "perte_par_lot_usd": [1000.0] * 19 + [10000.0],
                          "notionnel_par_lot_usd": [1000.0] * 20, "volume_min": 0.01})
        c = ev.capital_minimum(t)
        # besoin = 0.01 x 1000 / 0.02 = 500 $ (95 % des signaux) ; le 20e demande 5 000 $
        self.assertAlmostEqual(c["capital_min"], 500.0)
        self.assertAlmostEqual(ev.capital_minimum(t, 0.01)["capital_min"], 5.0)
        # levier : notionnel 200 000 $ par lot -> 0.01 lot = 2 000 $ -> 200 $ au levier 10 (< 500)
        t["notionnel_par_lot_usd"] = 2_000_000.0
        self.assertAlmostEqual(ev.capital_minimum(t)["capital_min"], 2000.0)


class TestStatistiquesDuMoteur(unittest.TestCase):
    """Preuves de bout en bout : pas d'avantage sur une marche aléatoire, avantage détecté s'il existe."""

    def test_marche_aleatoire_aucune_strategie_significative(self):
        u = generer_univers(debut="2012-01-01", graine=7,
                            symboles=["EURUSD", "GBPUSD", "XAUUSD", "US500", "NAS100", "GER40", "USDJPY"])
        for code in st.CODES:
            m = ev.metriques(mo.simuler(u, st.strategie_base(code), journal_complet=False))
            self.assertGreater(m["nb_trades"], 100, code)
            self.assertLess(m["tstat"], 2.0, code)
            v = ev.verdict_strategie(code, m, {"variantes": {}, "couts_doubles": {}}, {"sharpe": 0.0})
            self.assertFalse(v["retenue"], code)

    def test_tendance_injectee_s1_et_s2_positifs(self):
        u = generer_univers(debut="2012-01-01", graine=3, symboles=["USDJPY", "AUDUSD", "XAGUSD", "US30", "JP225"],
                            tendance={"amplitude": 0.5, "periode_jours": 900})
        for code in ("S1", "S2"):
            m = ev.metriques(mo.simuler(u, st.strategie_base(code), journal_complet=False))
            self.assertGreater(m["sharpe"], 0.5, code)
            self.assertGreater(m["tstat"], 2.0, code)
            self.assertGreater(m["rendement_total_pct"], 0.0, code)


if __name__ == "__main__":
    unittest.main()
