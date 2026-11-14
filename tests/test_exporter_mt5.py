"""Tests de scripts/exporter_donnees_mt5.py avec le faux module MetaTrader5."""
from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np

import scripts.exporter_donnees_mt5 as ex
from sentitrade.config import SymboleSpec
from tests.fakes.fake_mt5 import DTYPE_RATES, LOGIN_FICTIF, NOM_FICTIF, FauxMT5, symbole_fictif

MAINTENANT = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)  # un mercredi
EN_TETE = "time,open,high,low,close,tick_volume,spread,real_volume"
LIGNE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+,\d+,\d+$")
DUREES = {"M1": 60, "M15": 900, "H1": 3600}
CODES = {"M1": 1, "M15": 15, "H1": 16385}


class BaseExport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_export_mt5_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.donnees, self.logs = self.tmp / "mt5", self.tmp / "logs"
        patch = mock.patch.object(ex, "_dormir", lambda s: None)
        patch.start()
        self.addCleanup(patch.stop)

    def exporter(self, faux, *options, annees="0.25"):
        argv = ["--annees", annees, "--dossier", str(self.donnees), "--logs", str(self.logs), *options]
        sortie = io.StringIO()
        with mock.patch.dict(sys.modules, {"MetaTrader5": faux}), contextlib.redirect_stdout(sortie):
            code = ex.main(argv, maintenant=MAINTENANT)
        rapports = sorted(self.logs.glob("export_mt5_*.txt"))
        self.assertEqual(len(rapports), 1, "un rapport doit être écrit dans logs/")
        return code, rapports[0].read_text(encoding="utf-8")

    def lire_json(self, nom):
        return json.loads((self.donnees / nom).read_text(encoding="utf-8"))


class TestExportComplet(unittest.TestCase):
    """Un seul export de bout en bout (historique téléchargé progressivement), vérifié sous tous les angles."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="test_export_mt5_"))
        cls.donnees, cls.logs = cls.tmp / "mt5", cls.tmp / "logs"
        cls.faux = FauxMT5(maintenant_utc=MAINTENANT, jours_historique=200, telechargement_lent=True)
        argv = ["--annees", "0.25", "--dossier", str(cls.donnees), "--logs", str(cls.logs)]
        with mock.patch.object(ex, "_dormir", lambda s: None), \
                mock.patch.dict(sys.modules, {"MetaTrader5": cls.faux}), \
                contextlib.redirect_stdout(io.StringIO()):
            cls.code = ex.main(argv, maintenant=MAINTENANT)
        cls.rapport = next(cls.logs.glob("export_mt5_*.txt")).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def lire_json(self, nom):
        return json.loads((self.donnees / nom).read_text(encoding="utf-8"))

    def test_code_de_sortie_et_fichiers(self):
        self.assertEqual(self.code, 0, self.rapport)
        for nom in ("XAUUSD_M1.csv", "XAUUSD_M15.csv", "XAUUSD_H1.csv", "symbol_info.json", "spread_stats.json"):
            self.assertTrue((self.donnees / nom).is_file(), nom)
        self.assertEqual(list(self.donnees.glob("*.tmp")), [], "aucun fichier temporaire ne doit rester")
        self.assertIn("EXPORT TERMIN", self.rapport)

    def test_format_csv_exact(self):
        for tf in DUREES:
            texte = (self.donnees / f"XAUUSD_{tf}.csv").read_bytes().decode("ascii")
            self.assertNotIn("\r", texte)
            lignes = texte.splitlines()
            self.assertEqual(lignes[0], EN_TETE)
            for ligne in lignes[1:50] + lignes[-50:]:
                self.assertRegex(ligne, LIGNE)

    def test_barres_completes_triees_sans_doublon_ni_bougie_en_cours(self):
        debut = int((MAINTENANT - timedelta(days=365.25 * 0.25)).timestamp())
        for tf, duree in DUREES.items():
            temps = np.genfromtxt(self.donnees / f"XAUUSD_{tf}.csv", delimiter=",", skip_header=1,
                                  usecols=0, dtype="U19")
            secondes = temps.astype("datetime64[s]").astype("int64")
            attendu = self.faux._toutes_barres(CODES[tf])
            attendu = attendu[(attendu >= debut) & (attendu + duree <= self.faux.maintenant_serveur)]
            np.testing.assert_array_equal(secondes, attendu, err_msg=tf)
            self.assertTrue((np.diff(secondes) > 0).all(), tf)

    def test_heure_serveur_sans_fuseau(self):
        # dernière bougie M1 complète = 15:59 heure serveur (UTC+2), pas 13:59 UTC
        derniere = (self.donnees / "XAUUSD_M1.csv").read_text().splitlines()[-1]
        self.assertTrue(derniere.startswith("2026-11-11 15:59:00,"), derniere)

    def test_tranches_chevauchantes_et_retry(self):
        appels = [a for a in self.faux.appels if a[0] == "copy_rates_range" and a[2] == 1]
        self.assertGreaterEqual(len(appels), 4)
        # plusieurs tranches, qui se recouvrent : la plus ancienne commence avant la fin de la suivante
        bornes = sorted({(a[3], a[4]) for a in appels})
        for (a1, b1), (a2, b2) in zip(bornes, bornes[1:]):
            self.assertLess(a2, b1, "les tranches doivent se chevaucher")
        for a in appels:
            self.assertIsNotNone(a[3].tzinfo, "dates demandées en UTC")
        # la 1re réponse (téléchargement en cours) a été redemandée
        self.assertGreater(len(appels), len(bornes))

    def test_symbol_select_avant_tout(self):
        noms = [a[0] for a in self.faux.appels]
        i_select = noms.index("symbol_select")
        for nom in ("symbol_info", "symbol_info_tick", "copy_rates_range", "copy_ticks_range"):
            self.assertGreater(noms.index(nom), i_select, nom)
        self.assertEqual(noms[-1], "shutdown")

    def test_symbol_info_json(self):
        spec = SymboleSpec.depuis_json(self.donnees / "symbol_info.json")
        self.assertEqual((spec.nom, spec.digits, spec.point, spec.taille_contrat), ("XAUUSD", 2, 0.01, 100.0))
        self.assertEqual((spec.volume_min, spec.volume_pas, spec.volume_max), (0.01, 0.01, 100.0))
        d = self.lire_json("symbol_info.json")
        for cle in ex.ATTRIBUTS_OBLIGATOIRES:
            self.assertIn(cle, d)
        self.assertEqual(d["export"]["decalage_serveur_utc_heures"], 2)
        self.assertTrue(d["export"]["decalage_fiable"])
        self.assertEqual(d["export"]["build_terminal"], 5200)
        self.assertEqual(d["export"]["date_utc"], "2026-11-11 14:00:00")
        self.assertEqual(set(d["compte"]), {"currency", "leverage", "margin_mode", "trade_mode", "company", "server"})
        self.assertEqual(d["compte"]["margin_mode"], "hedging")
        self.assertEqual(d["compte"]["trade_mode"], "demo")

    def test_spread_stats(self):
        s = self.lire_json("spread_stats.json")
        self.assertEqual(s["unite"], "points")
        self.assertEqual(s["nb_jours"], 10)
        self.assertEqual(set(s["par_heure"]), {str(h) for h in range(24)})
        for h in range(24):
            ph = s["par_heure"][str(h)]
            self.assertEqual((ph["p50"], ph["p90"], ph["p99"]), (10 + h, 10 + h, 10 + h), h)
        self.assertEqual(s["global"]["max"], 33)
        self.assertEqual(s["global"]["nb_ticks"], s["nb_ticks"])
        self.assertNotIn("ticks", s)  # pas de ticks bruts

    def test_aucune_donnee_personnelle(self):
        textes = [p.read_text(encoding="utf-8", errors="replace") for p in self.donnees.iterdir()]
        textes.append(self.rapport)
        for texte in textes:
            self.assertNotIn(str(LOGIN_FICTIF), texte)
            self.assertNotIn(NOM_FICTIF, texte)
            self.assertNotIn('"login"', texte)
            self.assertNotIn('"name": "Jean', texte)


class TestExportCasParticuliers(BaseExport):
    def test_terminal_ferme(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, terminal_ouvert=False)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("ouvre MetaTrader 5 et connecte-toi au compte démo", rapport)
        self.assertIn("IPC initialize failed", rapport)
        self.assertFalse(self.donnees.exists() and any(self.donnees.iterdir()))
        self.assertEqual(faux.appels[-1][0], "shutdown")

    def test_module_absent(self):
        sortie = io.StringIO()
        with mock.patch.dict(sys.modules, {"MetaTrader5": None}), contextlib.redirect_stdout(sortie):
            code = ex.main(["--dossier", str(self.donnees), "--logs", str(self.logs)], maintenant=MAINTENANT)
        self.assertEqual(code, 1)
        self.assertIn("INSTALLER.bat", sortie.getvalue())

    def test_terminal_pas_connecte(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, connecte=False)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("pas connecté au serveur", rapport)
        self.assertEqual(faux.appels[-1][0], "shutdown")

    def test_historique_tronque_par_max_bars(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, jours_historique=200, maxbars=20_000)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("historique M1 TRONQUÉ", rapport)
        self.assertIn("Max bars in chart", rapport)
        self.assertIn("Unlimited", rapport)
        self.assertIn("rouvrir MetaTrader 5", rapport)
        d = self.lire_json("symbol_info.json")
        self.assertTrue(d["export"]["timeframes"]["M1"]["tronque"])
        self.assertFalse(d["export"]["timeframes"]["M15"]["tronque"])
        self.assertTrue((self.donnees / "XAUUSD_M15.csv").is_file())

    def test_historique_court_chez_le_broker(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, jours_historique=40)
        code, rapport = self.exporter(faux, annees="0.5")
        self.assertEqual(code, 0, rapport)  # rien à corriger côté utilisateur
        self.assertIn("[--] historique H1 TRONQUÉ", rapport)
        self.assertIn("ne semble pas fournir plus d'historique", rapport)

    def test_compte_reel_signale(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, trade_mode=2)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("Compte RÉEL détecté", rapport)
        self.assertEqual(self.lire_json("symbol_info.json")["compte"]["trade_mode"], "reel")

    def test_plusieurs_candidats_visible_retenu(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[
            symbole_fictif("XAUUSD.p"),
            symbole_fictif("XAUUSDm", visible=True, select=True),
            symbole_fictif("XAUUSD.x", visible=True, select=True, trade_mode=0),
            symbole_fictif("XAUEUR", visible=True, select=True, currency_profit="EUR")])
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 0, rapport)
        self.assertIn("plusieurs symboles de l'or", rapport)
        self.assertIn("XAUUSDm retenu", rapport)
        self.assertTrue((self.donnees / "XAUUSDm_H1.csv").is_file())
        self.assertEqual(SymboleSpec.depuis_json(self.donnees / "symbol_info.json").nom, "XAUUSDm")

    def test_symbole_gold(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[
            symbole_fictif("GOLDEUR", currency_profit="EUR"), symbole_fictif("GOLD", visible=True)])
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 0, rapport)
        self.assertTrue((self.donnees / "GOLD_M15.csv").is_file())

    def test_symbole_demande_introuvable(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        code, rapport = self.exporter(faux, "--symbole", "OR_INEXISTANT")
        self.assertEqual(code, 1)
        self.assertIn("impossible de sélectionner le symbole OR_INEXISTANT", rapport)
        self.assertIn("XAUUSD", rapport)

    def test_symbole_demande_cache_est_selectionne(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[symbole_fictif("XAUUSD.p")])
        code, rapport = self.exporter(faux, "--symbole", "XAUUSD.p")
        self.assertEqual(code, 0, rapport)
        self.assertIn(("symbol_select", "XAUUSD.p", True), faux.appels)

    def test_symbol_select_echoue_mais_symbole_visible(self):
        # MT5 réel build 6317 : symbol_select renvoie False ("Out of memory") alors que le
        # symbole est déjà dans l'Observation du marché : l'export doit continuer.
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[symbole_fictif("XAUUSD", visible=True, select=True)])
        faux.selectionnes.add("XAUUSD")
        with mock.patch.object(faux, "symbol_select", return_value=False):
            code, rapport = self.exporter(faux, "--symbole", "XAUUSD")
        self.assertEqual(code, 0, rapport)
        self.assertIn("déjà visible : on continue", rapport)
        self.assertTrue((self.donnees / "XAUUSD_M15.csv").is_file())

    def test_action_gold_jamais_exportee_comme_or(self):
        action = symbole_fictif("GOLD", currency_base="USD", path="Nasdaq\\Stock\\GOLD", visible=True)
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[action, symbole_fictif("XAUUSD")])
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 0, rapport)
        self.assertTrue((self.donnees / "XAUUSD_M15.csv").is_file())
        self.assertFalse((self.donnees / "GOLD_M15.csv").exists())

    def test_marche_ferme_decalage_non_fiable(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, marche_ouvert=False)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 0, rapport)
        self.assertIn("NON FIABLE", rapport)
        self.assertFalse(self.lire_json("symbol_info.json")["export"]["decalage_fiable"])

    def test_annees_invalides(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        code, rapport = self.exporter(faux, annees="0")
        self.assertEqual(code, 1)
        self.assertIn("--annees", rapport)


class TestOutils(unittest.TestCase):
    def test_tranches_mensuelles(self):
        debut = datetime(2026, 1, 15, 10, tzinfo=timezone.utc)
        fin = datetime(2026, 4, 3, tzinfo=timezone.utc)
        tr = ex.tranches_mensuelles(debut, fin)
        self.assertEqual(tr[0][1], fin)          # la plus récente d'abord
        self.assertEqual(tr[-1][0], debut)
        self.assertEqual(len(tr), 4)
        for (a_recent, _), (_, b_ancien) in zip(tr, tr[1:]):
            self.assertEqual(b_ancien - a_recent, timedelta(days=1))  # chevauchement d'un jour

    def test_trous_anormaux(self):
        def ep(s):
            return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())
        t = [ep("2026-11-06 23:00"),   # vendredi
             ep("2026-11-09 01:00"),   # lundi : week-end normal
             ep("2026-11-10 10:00"),
             ep("2026-11-12 10:00"),   # 2 jours : pas anormal
             ep("2026-11-19 10:00")]   # jeudi suivant : 5 jours hors week-end
        trous = ex.trous_anormaux(np.array(t), 3600)
        self.assertEqual(len(trous), 1)
        self.assertTrue(trous[0][0].startswith("2026-11-12 11:00"))
        self.assertAlmostEqual(trous[0][2], 5.0)

    def test_preparer_barres_dedoublonne_et_filtre(self):
        a = np.zeros(3, dtype=DTYPE_RATES)
        a["time"] = [0, 60, 120]
        for c in ("open", "high", "low", "close"):
            a[c] = 10.0
        b = a.copy()
        b["time"] = [60, 120, 180]
        b["high"][2] = 9.0  # incohérent : high < open
        df, infos = ex.preparer_barres([b, a], 2, 60, heure_serveur_now=None)
        self.assertEqual(list(df["time"].astype("int64") // 10**9), [0, 60, 120])
        self.assertEqual(infos["invalides_retirees"], 1)
        df, infos = ex.preparer_barres([a], 2, 60, heure_serveur_now=150)
        self.assertEqual(infos["en_cours_retirees"], 1)
        self.assertEqual(len(df), 2)

    def test_nom_fichier_symbole(self):
        self.assertEqual(ex.nom_fichier_symbole("XAU/USD*"), "XAU_USD_")
        self.assertEqual(ex.nom_fichier_symbole("XAUUSD.p"), "XAUUSD.p")


if __name__ == "__main__":
    unittest.main()
