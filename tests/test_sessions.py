"""Tests de sentitrade/sessions.py : jours, heures d'entrée, clôture forcée (spec §3)."""
from __future__ import annotations

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from sentitrade.config import Config
from sentitrade.sessions import doit_cloturer, est_heure_entree, est_jour_autorise

CFG = Config()  # 09:00 / 21:00 / 21:55, lundi-vendredi
T = pd.Timestamp


class TestSessions(unittest.TestCase):
    def test_jour_autorise(self):
        # 2024-01-01 est un lundi
        attendu = [True, True, True, True, True, False, False]
        for i, ok in enumerate(attendu):
            self.assertIs(est_jour_autorise(T("2024-01-01 12:00") + pd.Timedelta(days=i), CFG), ok)

    def test_heure_entree_bornes(self):
        cas = {
            "2024-01-02 08:59:59": False,
            "2024-01-02 09:00:00": True,
            "2024-01-02 15:30:00": True,
            "2024-01-02 20:59:59": True,
            "2024-01-02 21:00:00": False,
            "2024-01-02 21:55:00": False,
            "2024-01-02 00:00:00": False,
            "2024-01-06 10:00:00": False,  # samedi
            "2024-01-07 10:00:00": False,  # dimanche
        }
        for t, ok in cas.items():
            with self.subTest(t):
                self.assertIs(est_heure_entree(T(t), CFG), ok)

    def test_cloture_forcee(self):
        cas = {
            "2024-01-02 21:54:59": False,
            "2024-01-02 21:55:00": True,
            "2024-01-02 23:30:00": True,
            "2024-01-03 00:00:00": False,
            "2024-01-06 22:00:00": True,  # tout jour
        }
        for t, ok in cas.items():
            with self.subTest(t):
                self.assertIs(doit_cloturer(T(t), CFG), ok)

    def test_cloture_option_depuis(self):
        ouverture = T("2024-01-02 20:30")
        self.assertFalse(doit_cloturer(T("2024-01-02 21:00"), CFG, depuis=ouverture))
        # trou de données : la première bougie suivante est le lendemain à 01:00
        self.assertTrue(doit_cloturer(T("2024-01-03 01:00"), CFG, depuis=ouverture))
        self.assertFalse(doit_cloturer(T("2024-01-03 01:00"), CFG))
        idx = pd.DatetimeIndex(["2024-01-02 21:00", "2024-01-03 01:00"])
        np.testing.assert_array_equal(doit_cloturer(idx, CFG, depuis=ouverture), [False, True])

    def test_vectorise_identique_au_scalaire(self):
        idx = pd.date_range("2024-01-01", "2024-01-15", freq="7min")
        for f in (est_jour_autorise, est_heure_entree, doit_cloturer):
            with self.subTest(f.__name__):
                vect = f(idx, CFG)
                self.assertIsInstance(vect, np.ndarray)
                self.assertEqual(vect.dtype, bool)
                np.testing.assert_array_equal(vect, [f(t, CFG) for t in idx])
                serie = f(pd.Series(idx, index=np.arange(len(idx))), CFG)
                np.testing.assert_array_equal(serie.to_numpy(), vect)

    def test_types_acceptes(self):
        self.assertTrue(est_heure_entree(datetime(2024, 1, 2, 10, 0), CFG))
        self.assertTrue(est_heure_entree(T("2024-01-02 10:00"), CFG.strategie))
        cfg = CFG.avec(debut_session="08:30", derniere_entree="20:15", cloture_forcee="21:00",
                       jours_autorises=(0, 6))
        self.assertTrue(est_heure_entree(T("2024-01-07 08:30"), cfg))   # dimanche autorisé
        self.assertFalse(est_heure_entree(T("2024-01-02 10:00"), cfg))  # mardi interdit
        self.assertFalse(est_heure_entree(T("2024-01-01 20:15"), cfg))
        self.assertTrue(doit_cloturer(T("2024-01-01 21:00"), cfg))

    def test_horodatage_avec_fuseau_refuse(self):
        with self.assertRaises(ValueError):
            est_heure_entree(T("2024-01-02 10:00", tz="UTC"), CFG)
        with self.assertRaises(ValueError):
            est_heure_entree(pd.date_range("2024-01-02", periods=3, freq="h", tz="UTC"), CFG)


if __name__ == "__main__":
    unittest.main()
