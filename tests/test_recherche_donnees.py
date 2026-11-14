"""Tests de sentitrade/recherche/donnees.py et couts.py : verrou du hold-out, format, conversions, coûts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from sentitrade.recherche import couts as co
from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.donnees import (FIN_CONTROLE, FIN_DEVELOPPEMENT, Convertisseur, ErreurConversion,
                                          ErreurDonnees, charger_univers, construire_univers, jours)
from sentitrade.recherche.synthetique import ecrire_univers, generer_brut, generer_univers

SYMS = ["EURUSD", "USDJPY", "GER40", "BTCUSD"]


class TestVerrouHoldOut(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.brut = generer_brut(debut="2025-06-01", fin="2026-11-13 23:59", graine=2, symboles=SYMS, annees_m15=1.4)
        ecrire_univers(cls.brut, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_par_defaut_rien_apres_le_2025_11_13(self):
        u = charger_univers(self.tmp.name)
        self.assertFalse(u.controle_final)
        for nom, d in u.symboles.items():
            for tf, df in d.bougies.items():
                self.assertLessEqual(df.index.max(), FIN_DEVELOPPEMENT, f"{nom} {tf}")
        self.assertEqual(u.symboles["EURUSD"].bougies["H1"].index.max(), pd.Timestamp("2025-11-13 23:00"))
        self.assertEqual(u.symboles["EURUSD"].bougies["M15"].index.max(), pd.Timestamp("2025-11-13 23:45"))

    def test_controle_final_explicite(self):
        u = charger_univers(self.tmp.name, controle_final=True)
        self.assertTrue(u.controle_final)
        self.assertGreater(u.symboles["EURUSD"].bougies["D1"].index.max(), pd.Timestamp("2026-11-01"))
        self.assertLessEqual(u.symboles["EURUSD"].bougies["D1"].index.max(), FIN_CONTROLE)
        dev = u.tronquer(FIN_DEVELOPPEMENT)
        self.assertFalse(dev.controle_final)
        self.assertEqual(dev.signature(), charger_univers(self.tmp.name).signature())

    def test_univers_en_memoire_aussi_verrouille(self):
        u = construire_univers(self.brut)
        self.assertLessEqual(max(df.index.max() for d in u.symboles.values() for df in d.bougies.values()),
                             FIN_DEVELOPPEMENT)
        u2 = generer_univers(debut="2025-10-01", graine=1, symboles=["EURUSD"], annees_m15=0)
        self.assertLessEqual(u2.symboles["EURUSD"].bougies["M15"].index.max(), FIN_DEVELOPPEMENT)

    def test_format_ecrit_relu(self):
        meta = json.loads((Path(self.tmp.name) / "univers.json").read_text(encoding="utf-8"))
        self.assertEqual(set(meta["symboles"]), set(SYMS))
        self.assertEqual(meta["symboles"]["GER40"]["classe"], "indices")
        entete = (Path(self.tmp.name) / "EURUSD" / "D1.csv").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(entete, "time,open,high,low,close,tick_volume,spread,real_volume")
        self.assertFalse((Path(self.tmp.name) / "USDJPY" / "M15.csv").exists())
        u = charger_univers(self.tmp.name, controle_final=True)
        pd.testing.assert_frame_equal(u.symboles["USDJPY"].bougies["H1"], self.brut["USDJPY"]["bougies"]["H1"],
                                      check_freq=False)

    def test_symbole_illisible_exclu_sans_bloquer(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_univers({k: self.brut[k] for k in ("EURUSD", "GER40")}, d)
            (Path(d) / "GER40" / "symbol_info.json").write_text("{pas du json", encoding="utf-8")
            u = charger_univers(d)
            self.assertIn("GER40", u.exclus)
            self.assertIn("EURUSD", u.symboles)

    def test_univers_json_absent(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ErreurDonnees):
                charger_univers(d)


class TestConversion(unittest.TestCase):

    def test_taux_veille_et_inverse(self):
        u = generer_univers(debut="2024-01-01", fin="2024-03-01", graine=4, symboles=["EURUSD", "USDJPY"], h1=False)
        conv = Convertisseur(u)
        d1 = u.symboles["USDJPY"].bougies["D1"]
        j = jours(d1.index)
        tx = conv.taux("JPY", j)
        self.assertTrue(np.isnan(tx[0]))                              # aucune clôture antérieure
        self.assertAlmostEqual(tx[5], 1.0 / d1["close"].iloc[4])       # clôture de la veille, inversée
        e = u.symboles["EURUSD"].bougies["D1"]
        self.assertAlmostEqual(conv.taux("EUR", jours(e.index))[3], e["close"].iloc[2])
        self.assertTrue((conv.taux("USD", j) == 1.0).all())
        with self.assertRaises(ErreurConversion):
            conv.taux("GBP", j)

    def test_devise_non_convertible_exclut_le_symbole(self):
        u = generer_univers(debut="2023-01-01", fin="2024-03-01", graine=4, symboles=["GER40", "UK100", "EURUSD"],
                            h1=False)
        series, exclus, _ = mo.preparer_series(u, st.strategie_base("S1"))
        self.assertIn("UK100", exclus)          # GBP sans GBPUSD
        self.assertIn("GBP", exclus["UK100"])
        self.assertEqual(sorted(s.nom for s in series), ["EURUSD", "GER40"])


def _info(**k):
    base = {"point": 0.01, "trade_contract_size": 100.0, "swap_mode": 1, "swap_long": -10.0, "swap_short": 2.0,
            "swap_rollover3days": 3, "currency_profit": "USD", "currency_base": "XAU", "currency_margin": "XAU",
            "trade_calc_mode": 4}
    base.update(k)
    return base


STATS = {"global": {"p50": 20.0}, "par_heure": {**{str(h): {"p50": 20.0} for h in range(24)}, "0": {"p50": None},
                                                "1": {"p50": 50.0}}}


class TestCouts(unittest.TestCase):

    def test_spread_effectif_et_glissements(self):
        c = co.construire_couts(_info(), STATS)
        self.assertAlmostEqual(c.p50_global, 0.20)
        self.assertAlmostEqual(c.glissement_marche, 0.10)
        self.assertAlmostEqual(c.glissement_stop, 0.20)
        s = c.spread_heures(np.array([10, 30, 10]), np.array([5, 5, 1]))
        np.testing.assert_allclose(s, [0.20, 0.30, 0.50])
        # heure sans médiane (None) -> médiane globale
        self.assertAlmostEqual(c.spread_heures(np.array([0]), np.array([0]))[0], 0.20)
        d = co.construire_couts(_info(), STATS, co.ParametresCouts.doubles())
        self.assertAlmostEqual(d.glissement_stop, 0.40)
        self.assertAlmostEqual(d.spread_heures(np.array([30]), np.array([5]))[0], 0.60)

    def test_spread_ouverture_d1_premiere_bougie_h1(self):
        c = co.construire_couts(_info(), STATS)
        d1 = pd.DataFrame({"spread": [10, 10]}, index=pd.DatetimeIndex(["2024-01-08", "2024-01-09"]))
        h1 = pd.DataFrame({"spread": [80, 5, 10]},
                          index=pd.DatetimeIndex(["2024-01-08 01:00", "2024-01-08 02:00", "2024-01-09 01:00"]))
        ouv, barre = co.spreads_d1(d1, h1, c)
        np.testing.assert_allclose(ouv, [0.80, 0.50])          # max(H1 de 01:00, médiane de 01:00 = 50 pts)
        np.testing.assert_allclose(barre, [0.20, 0.20])

    def test_modes_de_swap(self):
        self.assertAlmostEqual(co.construire_couts(_info(), STATS).swap_par_lot(1, 2000, 1900), -10.0)   # points
        self.assertAlmostEqual(co.construire_couts(_info(), STATS).swap_par_lot(-1, 2000, 1900), 2.0)
        c2 = co.construire_couts(_info(swap_mode=2, swap_long=-3.0), STATS)
        self.assertEqual((c2.swap_par_lot(1, 2000, 0), c2.devise_swap()), (-3.0, "XAU"))
        c4 = co.construire_couts(_info(swap_mode=4, swap_long=-7.5), STATS)
        self.assertEqual((c4.swap_par_lot(1, 2000, 0), c4.devise_swap()), (-7.5, "USD"))
        c5 = co.construire_couts(_info(swap_mode=5, swap_long=-3.6), STATS)
        self.assertAlmostEqual(c5.swap_par_lot(1, 2000, 1000), 100 * 2000 * -3.6 / 100 / 360)
        c6 = co.construire_couts(_info(swap_mode=6, swap_long=-3.6), STATS)
        self.assertAlmostEqual(c6.swap_par_lot(1, 2000, 1000), 100 * 1000 * -3.6 / 100 / 360)
        # coûts doublés : seul un swap débiteur double
        d = co.construire_couts(_info(), STATS, co.ParametresCouts.doubles())
        self.assertAlmostEqual(d.swap_par_lot(1, 2000, 0), -20.0)
        self.assertAlmostEqual(d.swap_par_lot(-1, 2000, 0), 2.0)
        # compte cent : contrat / 100 ; swap en argent par lot / 100
        cc = co.construire_couts(_info(swap_mode=4, swap_long=-7.5), STATS, facteur_contrat=0.01)
        self.assertAlmostEqual(cc.contrat, 1.0)
        self.assertAlmostEqual(cc.swap_par_lot(1, 2000, 0), -0.075)

    def test_mode_non_gere_bloque_le_symbole(self):
        for m in (7, 8, 99, None):
            with self.assertRaises(co.ErreurSwap):
                co.construire_couts(_info(swap_mode=m), STATS)
        with self.assertRaises(co.ErreurCouts):
            co.construire_couts(_info(trade_calc_mode=1), STATS)
        with self.assertRaises(co.ErreurCouts):
            co.construire_couts(_info(), {})
        u = generer_univers(debut="2023-01-01", fin="2024-03-01", graine=4, symboles=["EURUSD", "XAUUSD"], h1=False)
        u.symboles["XAUUSD"].info["swap_mode"] = 7
        series, exclus, _ = mo.preparer_series(u, st.strategie_base("S1"))
        self.assertIn("swap_mode 7", exclus["XAUUSD"])
        self.assertEqual([s.nom for s in series], ["EURUSD"])

    def test_nuit_triple(self):
        c = co.construire_couts(_info(swap_rollover3days=3), STATS)
        self.assertEqual(c.multiplicateur_nuit(2), 3)          # mercredi (weekday 2)
        self.assertEqual(c.multiplicateur_nuit(4), 1)
        self.assertEqual(co.jour_mt5_vers_python(5), 4)        # vendredi
        self.assertEqual(co.jour_mt5_vers_python(0), 6)        # dimanche


if __name__ == "__main__":
    unittest.main()
