"""Plancher de spread et retrait des journées figées (décisions de l'architecte, 14/11/2026)."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from sentitrade.recherche.couts import construire_couts
from sentitrade.recherche.donnees import retirer_jours_figes

INFO = {"swap_mode": 1, "point": 0.00001, "trade_contract_size": 100000.0, "swap_long": -5.0,
        "swap_short": 1.0, "swap_rollover3days": 3, "currency_profit": "USD", "currency_base": "EUR",
        "trade_calc_mode": 0}


class TestPlancher(unittest.TestCase):
    def test_mediane_nulle_relevee(self):
        stats = {"global": {"p50": 0}, "par_heure": {str(h): {"p50": 0} for h in range(24)}}
        c = construire_couts({**INFO, "spread_plancher_prix": 0.00008}, stats)
        self.assertAlmostEqual(c.p50_global, 0.00008, places=12)
        self.assertTrue(np.allclose(c.p50_heure, 0.00008))
        self.assertAlmostEqual(c.glissement_marche, 0.00004, places=12)

    def test_mediane_superieure_conservee(self):
        stats = {"global": {"p50": 20}, "par_heure": {"3": {"p50": 50}}}
        c = construire_couts({**INFO, "spread_plancher_prix": 0.00008}, stats)
        self.assertAlmostEqual(c.p50_global, 0.0002, places=12)
        self.assertAlmostEqual(c.p50_heure[3], 0.0005, places=12)


class TestJoursFiges(unittest.TestCase):
    def test_retrait(self):
        idx = pd.date_range("2024-12-05 01:00", periods=23, freq="h").append(
            pd.date_range("2024-12-06 01:00", periods=23, freq="h"))
        h = np.r_[np.full(23, 100.0), np.linspace(100, 101, 23) + 0.5]
        l = np.r_[np.full(23, 100.0), np.linspace(100, 101, 23) - 0.5]
        h1 = pd.DataFrame({"open": l, "high": h, "low": l, "close": l}, index=idx)
        d1 = pd.DataFrame({"open": [100.0, 100.0], "high": [100.0, 101.5], "low": [100.0, 99.5],
                           "close": [100.0, 101.0]}, index=pd.DatetimeIndex(["2024-12-05", "2024-12-06"]))
        propres, n = retirer_jours_figes({"H1": h1, "D1": d1})
        self.assertEqual(n, 1)
        self.assertEqual(list(propres["D1"].index), [pd.Timestamp("2024-12-06")])
        self.assertTrue((propres["H1"].index.normalize() == pd.Timestamp("2024-12-06")).all())


if __name__ == "__main__":
    unittest.main()
