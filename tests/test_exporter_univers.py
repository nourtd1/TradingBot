"""Tests de scripts/exporter_univers_mt5.py avec le faux module MetaTrader5."""
from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np

import scripts.exporter_univers_mt5 as eu
from sentitrade.config import SymboleSpec
from tests.fakes.fake_mt5 import LOGIN_FICTIF, NOM_FICTIF, FauxMT5, symbole_fictif, symboles_broker_etendu

MAINTENANT = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)  # un mercredi
EN_TETE = "time,open,high,low,close,tick_volume,spread,real_volume"
LIGNE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+,\d+,\d+$")
DUREES = {"D1": 86400, "H1": 3600, "M15": 900}
CODES = {"D1": 16408, "H1": 16385, "M15": 15}
CONFIG = Path(__file__).resolve().parents[1] / "config" / "univers_symboles.json"
SIX_M15 = {"XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "GER40"}
# génériques ajoutés pour le nouveau broker (RECHERCHE_PLAN_CYCLE2 §5) : absents du broker_fictif
NOUVEAUX = {"XPTUSD", "XPDUSD", "COPPER", "EU50", "FRA40", "AUS200", "HK50", "ESP35", "US2000",
            "USOIL", "UKOIL", "NGAS", "LTCUSD", "XRPUSD", "SOLUSD"}
CLES_UNIVERS = ["genere_le_utc", "serveur", "societe", "decalage_serveur_utc_heures", "decalage_fiable",
                "decalage_mesure_le_utc", "build_terminal", "symboles", "absents"]


def fx(nom, base, profit, **champs):
    d = dict(currency_base=base, currency_profit=profit, currency_margin=base, digits=5, point=0.00001,
             trade_tick_size=0.00001, trade_contract_size=100000.0, trade_calc_mode=0,
             description=f"{base} vs {profit}", path=f"Forex\\{nom}", swap_mode=1)
    d.update(champs)
    return symbole_fictif(nom, **d)


def indice(nom, profit, description, **champs):
    d = dict(currency_base=profit, currency_profit=profit, currency_margin=profit, digits=2, point=0.01,
             trade_contract_size=1.0, trade_calc_mode=2, description=description, path=f"Indices\\{nom}")
    d.update(champs)
    return symbole_fictif(nom, **d)


def action(nom, description, chemin, **champs):
    d = dict(currency_base="USD", currency_profit="USD", currency_margin="USD", trade_contract_size=1.0,
             volume_min=1.0, volume_step=1.0, trade_calc_mode=32, description=description, path=chemin)
    d.update(champs)
    return symbole_fictif(nom, **d)


def broker_fictif(**sur):
    """Un broker plausible : suffixe .p sur le forex, l'action GOLD, un ETF « US500 »,
    pas de NZDUSD ni de JP225."""
    vis = dict(visible=True, select=True)
    symboles = [
        fx("EURUSD.p", "EUR", "USD", **vis), fx("GBPUSD.p", "GBP", "USD"), fx("USDJPY.p", "USD", "JPY", digits=3),
        fx("AUDUSD.p", "AUD", "USD"), fx("USDCAD.p", "USD", "CAD"), fx("USDCHF.p", "USD", "CHF"),
        symbole_fictif("XAUUSD.p", path="Metals\\XAUUSD.p", **vis),
        symbole_fictif("XAGUSD.p", currency_base="XAG", description="Silver vs US Dollar",
                       path="Metals\\XAGUSD.p", digits=3, point=0.001),
        action("GOLD", "Barrick Gold Corp", "Nasdaq\\Stock\\GOLD", visible=True, select=True),
        action("US500", "US 500 ETF Trust", "NYSE\\ETF\\US500", trade_calc_mode=2),
        indice("US500.cash", "USD", "US 500 Cash Index", **vis),
        indice("USTEC", "USD", "US Tech 100 Index"),
        indice("US30", "USD", "Wall Street 30"),
        indice("DE40", "EUR", "Germany 40 Index", swap_mode=5),
        indice("UK100", "GBP", "UK 100 Index"),
        symbole_fictif("BTCUSD", currency_base="BTC", description="Bitcoin vs US Dollar", path="Crypto\\BTCUSD",
                       trade_contract_size=1.0, **vis),
        symbole_fictif("ETHUSD", currency_base="ETH", description="Ethereum vs US Dollar",
                       path="Crypto\\ETHUSD", trade_contract_size=1.0),
    ]
    options = dict(maintenant_utc=MAINTENANT, jours_historique=500, symboles=symboles)
    options.update(sur)
    return FauxMT5(**options)


def config_avec(chemin: Path, forcer: dict) -> Path:
    d = json.loads(CONFIG.read_text(encoding="utf-8"))
    d["forcer"] = forcer
    chemin.write_text(json.dumps(d), encoding="utf-8")
    return chemin


def lancer(faux, dossier: Path, logs: Path, *options, config: Path = CONFIG):
    argv = ["--annees", "1", "--annees-m15", "0.1", "--dossier", str(dossier), "--logs", str(logs),
            "--config", str(config), *options]
    with mock.patch.object(eu.ex, "_dormir", lambda s: None), \
            mock.patch.dict(sys.modules, {"MetaTrader5": faux}), \
            contextlib.redirect_stdout(io.StringIO()):
        return eu.main(argv, maintenant=MAINTENANT)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_univers_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dossier, self.logs = self.tmp / "univers", self.tmp / "logs"

    def exporter(self, faux, *options, config=CONFIG):
        code = lancer(faux, self.dossier, self.logs, *options, config=config)
        rapports = sorted(self.logs.glob("export_univers_*.txt"))
        self.assertEqual(len(rapports), 1, "un rapport doit être écrit dans logs/")
        return code, rapports[0].read_text(encoding="utf-8")

    def univers(self):
        return json.loads((self.dossier / "univers.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Résolution des noms (sans export)
# --------------------------------------------------------------------------- #
class TestAlias(unittest.TestCase):
    def test_suffixes_et_prefixes(self):
        oui = [("EURUSD", "EURUSD"), ("EURUSD.p", "EURUSD"), ("eurusd.p", "EURUSD"), ("EURUSDm", "EURUSD"),
               ("EURUSD.ecn", "EURUSD"), ("EURUSD-", "EURUSD"), ("EURUSD_i", "EURUSD"), ("EURUSDpro", "EURUSD"),
               ("#US30", "US30"), ("US500Cash", "US500"), ("US500-cash", "US500"), ("S&P500", "S&P500"),
               ("SP500.cash", "S&P500"), ("EUR/USD", "EURUSD"), ("GER40.", "GER40"), ("CL", "CL"),
               ("CL.cash", "CL"), ("#CL", "CL"), ("XTIUSD.ecn", "XTIUSD"), ("BTCUSDT", "BTCUSD")]
        non = [("US300", "US30"), ("GER400", "GER40"), ("EURUSDABCDEF", "EURUSD"), ("XEURUSD", "EURUSD"),
               ("EURUS", "EURUSD"), ("EURUSD.abcdefghijk", "EURUSD"), ("US30X1", "US30"),
               ("CLB", "CL"), ("CLOROX", "CL"), ("CLDEC", "CL")]
        for nom, alias in oui:
            self.assertTrue(eu.correspond_alias(nom, alias), (nom, alias))
        for nom, alias in non:
            self.assertFalse(eu.correspond_alias(nom, alias), (nom, alias))


class TestResolution(unittest.TestCase):
    def setUp(self):
        self.config = eu.charger_config(CONFIG)
        self.mt5 = FauxMT5(maintenant_utc=MAINTENANT)

    def resoudre(self, symboles, *gens, forcer=None):
        config = dict(self.config, forcer=forcer or {})
        return eu.resoudre(self.mt5, symboles, config, list(gens) or list(config["symboles"]))

    def test_config_livree_couvre_le_plan(self):
        attendu = {"forex": {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"},
                   "metaux": {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "COPPER"},
                   "crypto": {"BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "SOLUSD"},
                   "indices": {"US500", "NAS100", "US30", "GER40", "UK100", "JP225",
                               "EU50", "FRA40", "AUS200", "HK50", "ESP35", "US2000"},
                   "energies": {"USOIL", "UKOIL", "NGAS"}}
        for classe, gens in attendu.items():
            self.assertEqual({g for g, s in self.config["symboles"].items() if s["classe"] == classe}, gens)
        self.assertEqual(self.config["forcer"], {})

    def test_config_retrocompatible(self):
        """Les 17 génériques du cycle 1 gardent leur classe, leurs alias et leurs devises."""
        s = self.config["symboles"]
        self.assertEqual(s["XAUUSD"]["alias"], ["XAUUSD", "GOLD"])
        self.assertEqual(s["GER40"]["profit"], ["EUR"])
        self.assertEqual(s["BTCUSD"]["base"], ["BTC", "XBT"])
        self.assertEqual(s["BTCUSD"]["profit"], ["USD"])
        self.assertEqual(s["US500"]["mots_cles"][0], "S&P")
        for gen in ("US500", "XAUUSD", "EURUSD", "BTCUSD"):
            self.assertEqual(s[gen]["mots_exclus"], [])

    def test_broker_complet(self):
        choix, absents, journal = self.resoudre(broker_fictif().symboles.values())
        noms = {g: s.name for g, s in choix.items()}
        self.assertEqual(noms["EURUSD"], "EURUSD.p")
        self.assertEqual(noms["XAUUSD"], "XAUUSD.p")
        self.assertEqual(noms["US500"], "US500.cash")
        self.assertEqual(noms["NAS100"], "USTEC")
        self.assertEqual(noms["GER40"], "DE40")
        self.assertEqual(set(absents), {"NZDUSD", "JP225"} | NOUVEAUX)
        self.assertIn("introuvable", absents["JP225"])
        # nouveau générique introuvable : absent avec la raison, jamais un choix au hasard
        self.assertIn("introuvable", absents["USOIL"])
        self.assertIn("XTIUSD", absents["USOIL"])

    def test_action_gold_rejetee(self):
        choix, absents, journal = self.resoudre([action("GOLD", "Barrick Gold Corp", "Nasdaq\\Stock\\GOLD")],
                                                "XAUUSD")
        self.assertEqual(choix, {})
        self.assertIn("XAUUSD", absents)
        self.assertTrue(any("GOLD rejeté" in l and "action" in l for l in journal["XAUUSD"]), journal)

    def test_action_gold_meme_sans_path_rejetee_par_les_devises(self):
        s = action("GOLD", "Barrick Gold", "", trade_calc_mode=2)
        choix, absents, _ = self.resoudre([s], "XAUUSD")
        self.assertIn("devises USD/USD", absents["XAUUSD"] + " ".join(_["XAUUSD"]))

    def test_etf_us500_rejete(self):
        etf = action("US500", "US 500 ETF Trust", "NYSE\\ETF\\US500", trade_calc_mode=2)
        etf2 = indice("SPX500", "USD", "SPDR S&P 500 ETF", path="Indices\\SPX500")
        choix, absents, journal = self.resoudre([etf, etf2], "US500")
        self.assertEqual(choix, {})
        self.assertEqual(len(journal["US500"]), 2)
        bon = indice("US500.cash", "USD", "US 500 Cash Index")
        choix, _, _ = self.resoudre([etf, etf2, bon], "US500")
        self.assertEqual(choix["US500"].name, "US500.cash")

    def test_indice_mauvaise_devise_ou_pas_un_indice(self):
        choix, absents, _ = self.resoudre([indice("GER40", "USD", "Germany 40 Index")], "GER40")
        self.assertIn("GER40", absents)
        choix, absents, _ = self.resoudre([indice("US30", "USD", "Quelque chose", path="Divers\\US30")], "US30")
        self.assertIn("US30", absents)
        choix, _, _ = self.resoudre([indice("JPN225", "JPY", "Japan 225")], "JP225")
        self.assertEqual(choix["JP225"].name, "JPN225")

    def test_devises_incoherentes_rejetees(self):
        cas = [("EURUSD", fx("EURUSD", "EUR", "JPY")), ("XAGUSD", fx("XAGUSD", "XAU", "USD")),
               ("BTCUSD", fx("BTCUSD", "BTC", "USDT")), ("BTCUSD", fx("BTCUSDT", "BTC", "USDT")),
               ("EURUSD", fx("EURUSD", "", ""))]
        for gen, s in cas:
            choix, absents, _ = self.resoudre([s], gen)
            self.assertEqual(choix, {}, s.name)
            self.assertIn(gen, absents)
        choix, _, _ = self.resoudre([fx("SILVER", "XAG", "USD"), fx("XBTUSD", "XBT", "USD")], "XAGUSD", "BTCUSD")
        self.assertEqual({g: s.name for g, s in choix.items()}, {"XAGUSD": "SILVER", "BTCUSD": "XBTUSD"})

    def test_visible_tradable_puis_nom_court(self):
        cache = fx("EURUSD", "EUR", "USD")
        visible = fx("EURUSD.p", "EUR", "USD", visible=True)
        choix, _, journal = self.resoudre([cache, visible], "EURUSD")
        self.assertEqual(choix["EURUSD"].name, "EURUSD.p")
        self.assertTrue(any("retenu : EURUSD.p" in l for l in journal["EURUSD"]))
        non_tradable = fx("EURUSDm", "EUR", "USD", visible=True, trade_mode=0)
        choix, _, _ = self.resoudre([non_tradable, cache], "EURUSD")
        self.assertEqual(choix["EURUSD"].name, "EURUSD")
        choix, _, _ = self.resoudre([fx("EURUSD.ecn", "EUR", "USD"), fx("EURUSD", "EUR", "USD")], "EURUSD")
        self.assertEqual(choix["EURUSD"].name, "EURUSD")

    def test_ambiguite_absent(self):
        choix, absents, _ = self.resoudre([fx("EURUSD.a", "EUR", "USD", visible=True),
                                           fx("EURUSD.b", "EUR", "USD", visible=True)], "EURUSD")
        self.assertEqual(choix, {})
        self.assertIn("ambigu", absents["EURUSD"])
        self.assertIn("forcer", absents["EURUSD"])

    def test_forcer_prioritaire(self):
        a, b = fx("EURUSD", "EUR", "USD", visible=True), fx("EURO_DOLLAR", "", "", visible=False)
        choix, absents, journal = self.resoudre([a, b], "EURUSD", forcer={"EURUSD": "EURO_DOLLAR"})
        self.assertEqual(choix["EURUSD"].name, "EURO_DOLLAR")
        self.assertTrue(any("forcer" in l for l in journal["EURUSD"]))

    def test_forcer_introuvable_ou_action_refuse(self):
        gold = action("GOLD", "Barrick Gold Corp", "Nasdaq\\Stock\\GOLD")
        xau = symbole_fictif("XAUUSD")
        choix, absents, _ = self.resoudre([gold, xau], "XAUUSD", forcer={"XAUUSD": "GOLD"})
        self.assertEqual(choix, {})
        self.assertIn("refusé", absents["XAUUSD"])
        choix, absents, _ = self.resoudre([xau], "XAUUSD", forcer={"XAUUSD": "XAUUSD.x"})
        self.assertIn("introuvable", absents["XAUUSD"])
        choix, absents, _ = self.resoudre([xau], "XAUUSD", forcer={"XAUUSD": "XAUUSD"})
        self.assertEqual(choix["XAUUSD"].name, "XAUUSD")

    def test_custom_rejete(self):
        choix, absents, _ = self.resoudre([fx("EURUSD", "EUR", "USD", custom=True)], "EURUSD")
        self.assertIn("EURUSD", absents)

    def test_libelles_et_tranches(self):
        self.assertEqual(eu.texte_swap_mode(None, 1), "SYMBOL_SWAP_MODE_POINTS")
        self.assertEqual(eu.texte_swap_mode(None, 99), "INCONNU_99")
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        faux.SYMBOL_SWAP_MODE_CURRENCY_PROFIT = 9
        self.assertEqual(eu.texte_swap_mode(faux, 9), "SYMBOL_SWAP_MODE_CURRENCY_PROFIT")
        self.assertEqual(eu.texte_calc_mode(None, 32), "SYMBOL_CALC_MODE_EXCH_STOCKS")
        t = eu.tranches_annuelles(datetime(2020, 6, 1, tzinfo=timezone.utc), datetime(2023, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(len(t), 4)
        self.assertEqual(t[0][1], datetime(2023, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(t[-1][0], datetime(2020, 6, 1, tzinfo=timezone.utc))
        for (a1, b1), (a2, b2) in zip(t[1:], t[:-1]):
            self.assertLess(a2, b1, "les tranches doivent se chevaucher")

    def test_config_invalide(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_univers_cfg_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with self.assertRaises(eu.ex.ErreurExport):
            eu.charger_config(config_avec(tmp / "c.json", {"FOO": "BAR"}))
        (tmp / "c2.json").write_text("{pas du json", encoding="utf-8")
        with self.assertRaises(eu.ex.ErreurExport):
            eu.charger_config(tmp / "c2.json")


# --------------------------------------------------------------------------- #
# Export complet
# --------------------------------------------------------------------------- #
class TestExportComplet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="test_univers_"))
        cls.dossier, cls.logs = cls.tmp / "univers", cls.tmp / "logs"
        cls.faux = broker_fictif()
        cls.code = lancer(cls.faux, cls.dossier, cls.logs)
        cls.rapport = next(cls.logs.glob("export_univers_*.txt")).read_text(encoding="utf-8")
        cls.univers = json.loads((cls.dossier / "univers.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_code_et_format_univers(self):
        self.assertEqual(self.code, 0, self.rapport)
        u = self.univers
        self.assertEqual(list(u), CLES_UNIVERS)
        self.assertEqual(u["genere_le_utc"], "2026-11-11 14:00:00")
        self.assertEqual(u["serveur"], "BrokerExemple-Demo")
        self.assertEqual(u["societe"], "Broker Exemple Ltd")
        self.assertEqual(u["decalage_serveur_utc_heures"], 2)
        self.assertIs(u["decalage_fiable"], True)
        self.assertEqual(u["decalage_mesure_le_utc"], "2026-11-11 14:00:00")
        self.assertEqual(u["build_terminal"], 5200)
        self.assertEqual(set(u["absents"]), {"NZDUSD", "JP225"} | NOUVEAUX)
        self.assertEqual(len(u["symboles"]), 15)
        for gen, e in u["symboles"].items():
            self.assertEqual(set(e), {"nom_broker", "classe", "dossier", "trade_mode_texte", "timeframes"}, gen)
            self.assertEqual(e["dossier"], gen)
            self.assertEqual(e["trade_mode_texte"], "complet", gen)
            self.assertIn(e["classe"], ("forex", "metaux", "indices", "crypto"))
            attendu = {"D1", "H1", "M15"} if gen in SIX_M15 else {"D1", "H1"}
            self.assertEqual(set(e["timeframes"]), attendu, gen)
            for tf, v in e["timeframes"].items():
                self.assertEqual(set(v), {"barres", "premiere", "derniere"})
                self.assertRegex(v["premiere"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
        self.assertEqual(u["symboles"]["XAUUSD"]["nom_broker"], "XAUUSD.p")
        self.assertEqual(u["symboles"]["US500"]["nom_broker"], "US500.cash")
        self.assertEqual(u["symboles"]["XAUUSD"]["classe"], "metaux")

    def test_fichiers_par_symbole(self):
        for gen in self.univers["symboles"]:
            fichiers = {p.name for p in (self.dossier / gen).iterdir()}
            attendu = {"D1.csv", "H1.csv", "symbol_info.json", "spread_stats.json"}
            if gen in SIX_M15:
                attendu.add("M15.csv")
            self.assertEqual(fichiers, attendu, gen)
        self.assertEqual(sorted(p.name for p in self.dossier.iterdir() if p.name.startswith(".")), [])
        self.assertFalse((self.dossier / "NZDUSD").exists())

    def test_format_csv_et_barres(self):
        for gen in ("EURUSD", "US500", "BTCUSD"):
            e = self.univers["symboles"][gen]
            for tf, v in e["timeframes"].items():
                texte = (self.dossier / gen / f"{tf}.csv").read_bytes().decode("ascii")
                self.assertNotIn("\r", texte)
                lignes = texte.splitlines()
                self.assertEqual(lignes[0], EN_TETE)
                for ligne in lignes[1:30] + lignes[-30:]:
                    self.assertRegex(ligne, LIGNE)
                self.assertEqual(len(lignes) - 1, v["barres"])
                self.assertTrue(lignes[1].startswith(v["premiere"]))
                self.assertTrue(lignes[-1].startswith(v["derniere"]))
                t = np.array([l[:19] for l in lignes[1:]], dtype="datetime64[s]").astype("int64")
                self.assertTrue((np.diff(t) > 0).all(), (gen, tf))
                self.assertLessEqual(int(t[-1]) + DUREES[tf], self.faux.maintenant_serveur, "bougie en cours")
                attendu = self.faux._toutes_barres(CODES[tf])
                attendu = attendu[attendu + DUREES[tf] <= self.faux.maintenant_serveur]
                self.assertEqual(int(t[-1]), int(attendu[-1]), (gen, tf))
        # dernière D1 complète = mardi 10/11 (le mercredi est en cours) ; M15 limitée à ~0,1 an
        d1 = (self.dossier / "EURUSD" / "D1.csv").read_text().splitlines()
        self.assertTrue(d1[-1].startswith("2026-11-10 00:00:00,"), d1[-1])
        m15 = self.univers["symboles"]["EURUSD"]["timeframes"]["M15"]
        self.assertGreaterEqual(m15["premiere"], "2026-09-30")
        self.assertLess(self.univers["symboles"]["EURUSD"]["timeframes"]["H1"]["premiere"], "2025-11-12")

    def test_d1_par_tranches_annuelles(self):
        appels = [a for a in self.faux.appels if a[0] == "copy_rates_range" and a[1] == "EURUSD.p" and a[2] == 16408]
        self.assertLessEqual(len({(a[3], a[4]) for a in appels}), 3)
        for a in appels:
            self.assertIsNotNone(a[3].tzinfo)

    def test_symbol_info(self):
        for gen in ("EURUSD", "XAUUSD", "GER40"):
            chemin = self.dossier / gen / "symbol_info.json"
            d = json.loads(chemin.read_text(encoding="utf-8"))
            for champ in ("name", "description", "path", "digits", "point", "trade_contract_size", "volume_min",
                          "volume_step", "volume_max", "trade_tick_size", "trade_tick_value", "currency_base",
                          "currency_profit", "currency_margin", "trade_calc_mode", "trade_mode", "trade_stops_level",
                          "swap_mode", "swap_long", "swap_short", "swap_rollover3days", "spread", "spread_float",
                          "swap_mode_texte"):
                self.assertIn(champ, d, (gen, champ))
            spec = SymboleSpec.depuis_json(chemin)
            self.assertEqual(spec.nom, self.univers["symboles"][gen]["nom_broker"])
        d = json.loads((self.dossier / "GER40" / "symbol_info.json").read_text(encoding="utf-8"))
        self.assertEqual(d["swap_mode_texte"], "SYMBOL_SWAP_MODE_INTEREST_CURRENT")
        self.assertEqual(d["currency_profit"], "EUR")
        self.assertNotIn("compte", d)

    def test_spread_stats(self):
        # (le faux arrondit l'ask à 2 décimales : on vérifie sur l'or, point 0.01)
        s = json.loads((self.dossier / "XAUUSD" / "spread_stats.json").read_text(encoding="utf-8"))
        self.assertEqual(s["symbole"], "XAUUSD.p")
        self.assertEqual(s["unite"], "points")
        self.assertEqual(set(s["par_heure"]), {str(h) for h in range(24)})
        self.assertEqual(s["par_heure"]["14"]["p50"], 24.0)  # 10 + heure serveur

    def test_rapport_lisible(self):
        r = self.rapport
        self.assertIn("GOLD rejeté", r)
        self.assertIn("US500 rejeté", r)
        self.assertIn("EURUSD  -> EURUSD.p", r)
        self.assertIn("NZDUSD  ABSENT", r)
        self.assertIn("décalage heure serveur - UTC : +2 h", r)
        for gen in ("EURUSD", "US500", "BTCUSD"):
            self.assertIn(f"=== {gen} ", r)
        self.assertIn("RÉSUMÉ", r)
        self.assertIn("TERMINÉ", r)

    def test_aucune_donnee_personnelle(self):
        textes = [p.read_text(encoding="utf-8") for p in self.tmp.rglob("*") if p.is_file()]
        self.assertTrue(textes)
        for t in textes:
            self.assertNotIn(str(LOGIN_FICTIF), t)
            self.assertNotIn(NOM_FICTIF, t)
            self.assertNotIn("password", t.lower())

    def test_shutdown_et_observation_du_marche_restauree(self):
        self.assertEqual(self.faux.appels[-1][0], "shutdown")
        # les symboles ajoutés par l'export sont retirés ; ceux déjà visibles restent
        self.assertIn("EURUSD.p", self.faux.selectionnes)
        self.assertNotIn("GBPUSD.p", self.faux.selectionnes)
        self.assertIn(("symbol_select", "GBPUSD.p", False), self.faux.appels)
        self.assertNotIn(("symbol_select", "EURUSD.p", False), self.faux.appels)


class TestCasParticuliers(Base):
    def test_symbole_en_echec_n_arrete_pas_les_autres(self):
        faux = broker_fictif(rates_en_echec={"USDJPY.p"})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,USDJPY,US500")
        self.assertEqual(code, 0, rapport)
        u = self.univers()
        self.assertEqual(set(u["symboles"]), {"EURUSD", "US500"})
        self.assertIn("USDJPY.p", u["absents"]["USDJPY"])
        self.assertFalse((self.dossier / "USDJPY").exists())
        self.assertFalse(any(p.name.startswith(".") for p in self.dossier.iterdir()))

    def test_exception_sur_un_symbole(self):
        faux = broker_fictif()
        original = faux.copy_rates_range

        def copie(symbol, *args):
            if symbol == "BTCUSD":
                raise RuntimeError("panne simulée")
            return original(symbol, *args)

        faux.copy_rates_range = copie
        code, rapport = self.exporter(faux, "--symboles", "BTCUSD,ETHUSD")
        self.assertEqual(code, 0, rapport)
        u = self.univers()
        self.assertIn("panne simulée", u["absents"]["BTCUSD"])
        self.assertIn("ETHUSD", u["symboles"])
        self.assertEqual(faux.appels[-1][0], "shutdown")

    def test_classe_entierement_en_echec_code_1(self):
        faux = broker_fictif(rates_en_echec={"BTCUSD", "ETHUSD"})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,BTCUSD,ETHUSD")
        self.assertEqual(code, 1)
        self.assertIn("[!!] crypto : 0/2", rapport)
        self.assertIn("EURUSD", self.univers()["symboles"])

    def test_classe_absente_chez_le_broker_code_0(self):
        faux = broker_fictif()
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,JP225")
        self.assertEqual(code, 0, rapport)
        self.assertIn("indices : aucun symbole chez ce broker", rapport)

    def test_symbol_select_false_mais_visible(self):
        faux = broker_fictif(select_en_echec={"EURUSD.p"})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD")
        self.assertEqual(code, 0, rapport)
        self.assertIn("déjà visible : on continue", rapport)
        self.assertIn("Out of memory", rapport)
        self.assertTrue((self.dossier / "EURUSD" / "D1.csv").is_file())

    def test_symbol_select_false_et_cache(self):
        faux = broker_fictif(select_en_echec={"GBPUSD.p"})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,GBPUSD")
        self.assertEqual(code, 0, rapport)
        self.assertIn("Observation du marché", self.univers()["absents"]["GBPUSD"])

    def test_export_partiel_conserve_les_autres(self):
        self.exporter(broker_fictif(), "--symboles", "EURUSD,US500")
        for p in self.logs.glob("*"):
            p.unlink()
        code, rapport = self.exporter(broker_fictif(), "--symboles", "BTCUSD")
        self.assertEqual(code, 0, rapport)
        self.assertEqual(set(self.univers()["symboles"]), {"EURUSD", "US500", "BTCUSD"})
        # sans --symboles : univers réécrit entièrement
        for p in self.logs.glob("*"):
            p.unlink()
        code, _ = self.exporter(broker_fictif(rates_en_echec={"EURUSD.p"}), "--symboles", "EURUSD")
        self.assertIn("EURUSD", self.univers()["absents"])
        self.assertNotIn("EURUSD", self.univers()["symboles"])
        self.assertIn("BTCUSD", self.univers()["symboles"])

    def test_forcer_dans_la_config(self):
        cfg = config_avec(self.tmp / "cfg.json", {"US500": "US500.cash", "EURUSD": "GBPUSD.p"})
        code, rapport = self.exporter(broker_fictif(), "--symboles", "EURUSD,US500", config=cfg)
        u = self.univers()
        self.assertEqual(u["symboles"]["US500"]["nom_broker"], "US500.cash")
        self.assertIn("refusé", u["absents"]["EURUSD"])

    def test_marche_ferme_bougie_en_cours_retiree_prudemment(self):
        faux = broker_fictif(marche_ouvert=False)
        code, rapport = self.exporter(faux, "--symboles", "EURUSD")
        u = self.univers()
        self.assertIs(u["decalage_fiable"], False)
        dernier_tick = faux.maintenant_serveur - 40 * 3600
        for tf, v in u["symboles"]["EURUSD"]["timeframes"].items():
            fin = np.datetime64(v["derniere"]).astype("datetime64[s]").astype("int64") + DUREES[tf]
            self.assertLessEqual(int(fin), dernier_tick, tf)

    def test_reexport_remplace_le_dossier(self):
        faux = broker_fictif()
        self.exporter(faux, "--symboles", "EURUSD")
        (self.dossier / "EURUSD" / "vieux.txt").write_text("x", encoding="utf-8")
        for p in self.logs.glob("*"):
            p.unlink()
        code, rapport = self.exporter(broker_fictif(), "--symboles", "EURUSD")
        self.assertEqual(code, 0, rapport)
        self.assertFalse((self.dossier / "EURUSD" / "vieux.txt").exists())
        self.assertTrue((self.dossier / "EURUSD" / "D1.csv").is_file())
        self.assertEqual([p.name for p in self.dossier.iterdir() if p.name.startswith(".")], [])

    def test_lister(self):
        faux = broker_fictif()
        code = lancer(faux, self.dossier, self.logs, "--lister")
        self.assertEqual(code, 0)
        listes = list(self.logs.glob("symboles_broker_*.txt"))
        self.assertEqual(len(listes), 1)
        texte = listes[0].read_text(encoding="utf-8")
        for s in faux.symboles.values():
            self.assertIn(s.name, texte)
        self.assertIn("Nasdaq\\Stock\\GOLD", texte)
        self.assertIn("Barrick Gold Corp", texte)
        self.assertIn("XAUUSD  -> XAUUSD.p", texte)
        self.assertIn("JP225   -> ABSENT", texte)
        self.assertNotIn(str(LOGIN_FICTIF), texte)
        self.assertNotIn(NOM_FICTIF, texte)
        self.assertFalse(self.dossier.exists(), "--lister n'exporte rien")
        self.assertFalse(any(a[0] == "copy_rates_range" for a in faux.appels))

    def test_symbole_generique_inconnu(self):
        code, rapport = self.exporter(broker_fictif(), "--symboles", "EURUSD,FOO")
        self.assertEqual(code, 1)
        self.assertIn("FOO", rapport)
        self.assertFalse((self.dossier / "univers.json").exists())

    def test_terminal_ferme(self):
        faux = broker_fictif(terminal_ouvert=False)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("impossible de joindre le terminal", rapport)
        self.assertFalse((self.dossier / "univers.json").exists())

    def test_module_absent(self):
        with mock.patch.dict(sys.modules, {"MetaTrader5": None}), contextlib.redirect_stdout(io.StringIO()):
            code = eu.main(["--dossier", str(self.dossier), "--logs", str(self.logs)], maintenant=MAINTENANT)
        self.assertEqual(code, 1)
        self.assertIn("INSTALLER.bat", next(self.logs.glob("export_univers_*.txt")).read_text(encoding="utf-8"))

    def test_symbols_get_global_indisponible_repli_par_alias(self):
        faux = broker_fictif()
        original = faux.symbols_get
        faux.symbols_get = lambda group=None: None if group is None else original(group=group)
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,XAUUSD")
        self.assertEqual(code, 0, rapport)
        self.assertEqual(self.univers()["symboles"]["XAUUSD"]["nom_broker"], "XAUUSD.p")


# --------------------------------------------------------------------------- #
# Nouveau broker : crypto, énergies, autres indices et métaux
# --------------------------------------------------------------------------- #
def broker_etendu(**sur):
    options = dict(maintenant_utc=MAINTENANT, jours_historique=60, symboles=symboles_broker_etendu(),
                   serveur="BrokerRegule-Demo", societe="Broker Regule Ltd")
    options.update(sur)
    return FauxMT5(**options)


def energie(nom, description, chemin, profit="USD", **champs):
    d = dict(currency_base="USD", currency_profit=profit, currency_margin=profit, trade_contract_size=1000.0,
             description=description, path=chemin)
    d.update(champs)
    return symbole_fictif(nom, **d)


class TestEcheance(unittest.TestCase):
    def test_noms_dates(self):
        for nom, date in (("CL-DEC26", "DEC26"), ("CLDEC26", "DEC26"), ("WTI_MAR2027", "MAR2027"),
                          ("BRENT-Z6", "Z6"), ("CL.2612", "2612"), ("NGAS_JAN", "JAN"), ("GER40.24", "24")):
            self.assertEqual(eu.echeance_dans_nom(nom), date, nom)

    def test_noms_continus(self):
        for nom in ("HK50", "US30", "DE40", "JPN225", "AUS200", "ESP35", "SPA35", "US2000", "NAS100", "EU50",
                    "STOXX50", "F40", "#US30", ".DE40", "US500.cash", "EURUSD.p", "XAUUSD_i", "UKOIL.cash",
                    "OILCash", "BTCUSD.ecn", "WTI.f", "US500-cash", "XNGUSD", "NOV100"):
            self.assertIsNone(eu.echeance_dans_nom(nom), nom)


class TestResolutionEtendue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = eu.charger_config(CONFIG)
        cls.mt5 = FauxMT5(maintenant_utc=MAINTENANT)
        cls.choix, cls.absents, cls.journal = eu.resoudre(cls.mt5, symboles_broker_etendu(), cls.config,
                                                          list(cls.config["symboles"]))

    def resoudre(self, symboles, *gens, forcer=None):
        config = dict(self.config, forcer=forcer or {})
        return eu.resoudre(self.mt5, symboles, config, list(gens))

    def test_correspondances(self):
        noms = {g: s.name for g, s in self.choix.items()}
        attendu = {"USOIL": "XTIUSD", "UKOIL": "XBRUSD", "NGAS": "XNGUSD", "EU50": "STOXX50", "FRA40": "FRA40",
                   "AUS200": "AUS200", "HK50": "HK50", "ESP35": "SPA35", "US2000": "US2000", "XPTUSD": "XPTUSD",
                   "XPDUSD": "XPDUSD", "COPPER": "COPPER", "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
                   "LTCUSD": "LTCUSD", "XRPUSD": "XRPUSD", "NAS100": "USTEC", "GER40": "DE40", "JP225": "JPN225"}
        for gen, nom in attendu.items():
            self.assertEqual(noms.get(gen), nom, (gen, self.absents.get(gen), self.journal.get(gen)))
        self.assertEqual(set(self.absents), {"SOLUSD"})
        self.assertEqual(self.choix["USOIL"].name, "XTIUSD")

    def test_pieges_energie_rejetes(self):
        j = "\n".join(self.journal["USOIL"])
        self.assertRegex(j, r"USOIL rejeté : action ou ETF \(description « United States Oil Fund ETF »\)")
        self.assertRegex(j, r"CL-DEC26 rejeté : contrat à échéance daté \(« DEC26 »")
        self.assertRegex(j, r"OILCash rejeté : évoque un autre instrument \(« BRENT »")
        # WTI.f (à échéance, sans date dans le nom) est valide mais passe après le CFD continu
        self.assertIn("retenu : XTIUSD parmi 2 candidats valides (autres : WTI.f)", j)

    def test_crypto_devises_et_trust(self):
        self.assertIn("devises SOL/USDT au lieu de SOL/USD", " ".join(self.journal["SOLUSD"]))
        self.assertIn("introuvable", self.absents["SOLUSD"])
        self.assertTrue(any("BITCOIN.US rejeté : action ou ETF" in l for l in self.journal["BTCUSD"]))
        choix, absents, _ = self.resoudre([symbole_fictif("BTCUSDT", currency_base="BTC", currency_profit="USD",
                                                          description="Bitcoin", path="Crypto\\BTCUSDT")], "BTCUSD")
        self.assertEqual(choix["BTCUSD"].name, "BTCUSDT")
        choix, absents, _ = self.resoudre([symbole_fictif("ETHUSD", currency_base="BTC", currency_profit="USD",
                                                          path="Crypto\\ETHUSD")], "ETHUSD")
        self.assertIn("ETHUSD", absents)

    def test_indice_non_tradable_signale(self):
        self.assertTrue(any("SPA35 n'est pas tradable" in l and "désactivé" in l for l in self.journal["ESP35"]))

    def test_validation_energies(self):
        # mauvaise devise de cotation
        choix, absents, _ = self.resoudre([energie("XTIUSD", "WTI Crude", "Energies\\XTIUSD", profit="EUR")], "USOIL")
        self.assertIn("USOIL", absents)
        # rien n'évoque une énergie
        choix, absents, j = self.resoudre([energie("XTIUSD", "Quelque chose", "Divers\\XTIUSD")], "USOIL")
        self.assertIn("n'évoquent une énergie", " ".join(j["USOIL"]))
        # path d'énergie mais description imprécise : accepté, avec un avertissement
        choix, absents, j = self.resoudre([energie("CL", "", "Energies\\CL")], "USOIL")
        self.assertEqual(choix["USOIL"].name, "CL")
        self.assertTrue(any(l.startswith("attention : la description ne précise pas") for l in j["USOIL"]))
        # le Brent n'est jamais pris pour du WTI, ni l'inverse
        choix, absents, _ = self.resoudre([energie("WTI", "Brent Crude Oil", "Energies\\WTI")], "USOIL")
        self.assertIn("USOIL", absents)
        choix, absents, _ = self.resoudre([energie("BRENT", "WTI Light Sweet", "Energies\\BRENT")], "UKOIL")
        self.assertIn("UKOIL", absents)
        # gaz naturel : pas l'essence
        choix, absents, _ = self.resoudre([energie("NGAS", "Gasoline RBOB", "Energies\\NGAS")], "NGAS")
        self.assertIn("NGAS", absents)

    def test_cuivre_par_mots_cles(self):
        choix, absents, j = self.resoudre([symbole_fictif("COPPER", currency_base="USD", currency_profit="USD",
                                                          description="Divers", path="CFD\\COPPER")], "COPPER")
        self.assertIn("COPPER", absents)
        self.assertIn("la description ne contient ni COPPER", " ".join(j["COPPER"]))
        choix, absents, _ = self.resoudre([action("COPPER", "Southern Copper Corp", "NYSE\\Stock\\SCCO")], "COPPER")
        self.assertIn("COPPER", absents)

    def test_echeance_signalee_sans_date(self):
        wti = energie("WTI.f", "WTI Crude Oil Futures", "Futures\\WTI.f", trade_calc_mode=1, expiration_time=1797379200)
        choix, absents, j = self.resoudre([wti], "USOIL")
        self.assertEqual(choix["USOIL"].name, "WTI.f")
        self.assertTrue(any("attention : contrat à échéance (expiration le 2026-12-" in l for l in j["USOIL"]), j)

    def test_forcer_contrat_date_ou_etf_refuse(self):
        symboles = symboles_broker_etendu()
        choix, absents, _ = self.resoudre(symboles, "USOIL", forcer={"USOIL": "CL-DEC26"})
        self.assertIn("refusé : contrat à échéance daté", absents["USOIL"])
        choix, absents, _ = self.resoudre(symboles, "USOIL", forcer={"USOIL": "USOIL"})
        self.assertIn("refusé : action ou ETF", absents["USOIL"])
        choix, absents, j = self.resoudre(symboles, "USOIL", forcer={"USOIL": "WTI.f"})
        self.assertEqual(choix["USOIL"].name, "WTI.f")
        self.assertTrue(any(l.startswith("attention : contrat à") for l in j["USOIL"]))

    def test_warrant_et_fonds_rejetes(self):
        w = symbole_fictif("XAUUSD", path="Warrants\\XAUUSD")
        f = symbole_fictif("XAGUSD", currency_base="XAG", description="iShares Silver Trust")
        for gen, s in (("XAUUSD", w), ("XAGUSD", f)):
            choix, absents, j = self.resoudre([s], gen)
            self.assertIn(gen, absents)
            self.assertIn("action ou ETF", " ".join(j[gen]))


class TestDecalage(unittest.TestCase):
    def test_choisir_decalage(self):
        f = {"decalage": 2, "fiable": True, "dernier_tick": "x", "dernier_tick_epoch": 100}
        a = {"decalage": -4, "fiable": False, "dernier_tick": "a", "dernier_tick_epoch": 50}
        b = {"decalage": 1, "fiable": False, "dernier_tick": "b", "dernier_tick_epoch": 90}
        mort = {"decalage": -4383, "fiable": False, "dernier_tick": "m", "dernier_tick_epoch": 10}
        self.assertEqual(eu.choisir_decalage([a, f, b])["decalage"], 2)
        r = eu.choisir_decalage([a, b, mort])
        self.assertEqual((r["decalage"], r["fiable"]), (1, False))
        self.assertIsNone(eu.choisir_decalage([mort])["decalage"])
        self.assertIsNone(eu.choisir_decalage([])["decalage"])
        self.assertFalse(eu.decalage_plausible(15))
        self.assertFalse(eu.decalage_plausible(-13))
        self.assertTrue(eu.decalage_plausible(-12) and eu.decalage_plausible(14))

    def test_decalage_a_ecrire(self):
        maintenant = datetime(2026, 11, 14, 5, tzinfo=timezone.utc)
        inconnu = {"decalage": None, "fiable": False}
        non_fiable = {"decalage": -6, "fiable": False}
        fiable = {"decalage": 3, "fiable": True}
        ancien_fiable = {"decalage_serveur_utc_heures": 2, "decalage_fiable": True,
                         "decalage_mesure_le_utc": "2026-11-13 12:00:00"}
        ancien_mort = {"decalage_serveur_utc_heures": -4383, "decalage_fiable": False}
        d, note = eu.decalage_a_ecrire(non_fiable, ancien_fiable, True, maintenant)
        self.assertEqual((d["decalage"], d["fiable"], d["mesure_le"]), (2, True, "2026-11-13 12:00:00"))
        self.assertIn("conservé", note)
        d, _ = eu.decalage_a_ecrire(fiable, ancien_fiable, True, maintenant)
        self.assertEqual((d["decalage"], d["fiable"]), (3, True))
        d, note = eu.decalage_a_ecrire(non_fiable, ancien_fiable, False, maintenant)  # export complet
        self.assertEqual((d["decalage"], d["fiable"], note), (-6, False, None))
        d, _ = eu.decalage_a_ecrire(inconnu, ancien_mort, True, maintenant)
        self.assertIsNone(d["decalage"])
        d, note = eu.decalage_a_ecrire(inconnu, {"decalage_serveur_utc_heures": -6, "decalage_fiable": False,
                                                 "genere_le_utc": "2026-11-14 05:40:58"}, True, maintenant)
        self.assertEqual((d["decalage"], d["fiable"], d["mesure_le"]), (-6, False, "2026-11-14 05:40:58"))
        self.assertIn("NON fiable", note)
        d, _ = eu.decalage_a_ecrire({"decalage": -4383, "fiable": False}, {}, False, maintenant)
        self.assertEqual((d["decalage"], d["mesure_le"]), (None, None))


class TestNouveauBroker(Base):
    def test_export_complet_etendu(self):
        faux = broker_etendu()
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 0, rapport)
        u = self.univers()
        self.assertEqual(list(u), CLES_UNIVERS)
        self.assertEqual((u["serveur"], u["societe"]), ("BrokerRegule-Demo", "Broker Regule Ltd"))
        self.assertEqual(set(u["absents"]), {"SOLUSD"})
        self.assertEqual(len(u["symboles"]), 31)
        self.assertEqual(u["symboles"]["USOIL"]["classe"], "energies")
        self.assertEqual(u["symboles"]["USOIL"]["nom_broker"], "XTIUSD")
        self.assertEqual(u["symboles"]["ESP35"]["trade_mode_texte"], "désactivé")
        self.assertEqual(u["symboles"]["HK50"]["trade_mode_texte"], "complet")
        info = json.loads((self.dossier / "ESP35" / "symbol_info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["trade_mode_texte"], "désactivé")
        for gen in ("USOIL", "UKOIL", "NGAS", "BTCUSD", "HK50", "COPPER"):
            self.assertTrue((self.dossier / gen / "spread_stats.json").is_file(), gen)
            self.assertTrue((self.dossier / gen / "D1.csv").is_file(), gen)
        self.assertIn("[OK] énergies : 3/3 symbole(s) exporté(s)", rapport)
        self.assertIn("[OK] crypto : 4/5 symbole(s) exporté(s)", rapport)
        self.assertIn("SPA35 n'est PAS tradable sur ce compte", rapport)
        self.assertIn("[!!] pas tradable sur ce compte (trade_mode « désactivé »)", rapport)
        self.assertIn("Serveur : BrokerRegule-Demo (Broker Regule Ltd)", rapport)
        self.assertIn("CL-DEC26 rejeté", rapport)
        textes = [p.read_text(encoding="utf-8") for p in self.tmp.rglob("*") if p.is_file()]
        for t in textes:
            self.assertNotIn(str(LOGIN_FICTIF), t)
            self.assertNotIn(NOM_FICTIF, t)

    def test_week_end_crypto_donne_un_decalage_fiable(self):
        faux = broker_etendu(marche_ouvert=False, cotent_toujours={"BTCUSD"})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,BTCUSD")
        u = self.univers()
        self.assertEqual((u["decalage_serveur_utc_heures"], u["decalage_fiable"]), (2, True))
        self.assertIn("rejetée(s), hors de [-12, +14] h : -38 h", rapport)

    def test_decalage_le_plus_plausible_garde(self):
        # marché fermé : 3 mesures non fiables ; on garde celle du tick le plus récent (XAUUSD, +1 h)
        faux = broker_etendu(marche_ouvert=False, ticks_figes={"EURUSD": 6 * 3600, "XAUUSD": 3600 + 120,
                                                               "GBPUSD": 3 * 3600})
        code, rapport = self.exporter(faux, "--symboles", "EURUSD,GBPUSD,XAUUSD")
        u = self.univers()
        self.assertEqual((u["decalage_serveur_utc_heures"], u["decalage_fiable"]), (1, False))
        self.assertIn("mesure la plus plausible gardée : +1 h", rapport)

    def test_symbole_mort_jamais_retenu_pour_le_decalage(self):
        # cas réel UK100 : dernier tick vieux de 6 mois -> -4383 h écrit autrefois dans univers.json
        faux = broker_etendu(ticks_figes={"UK100": 183 * 86400})
        code, rapport = self.exporter(faux, "--symboles", "UK100")
        u = self.univers()
        self.assertIsNone(u["decalage_serveur_utc_heures"])
        self.assertIs(u["decalage_fiable"], False)
        self.assertIsNone(u["decalage_mesure_le_utc"])

    def test_export_partiel_ne_degrade_pas_le_decalage(self):
        self.exporter(broker_etendu(), "--symboles", "EURUSD")
        self.assertEqual((self.univers()["decalage_serveur_utc_heures"], self.univers()["decalage_fiable"]), (2, True))
        for p in self.logs.glob("*"):
            p.unlink()
        faux = broker_etendu(marche_ouvert=False, ticks_figes={"UK100": 183 * 86400, "GBPUSD": 3 * 3600})
        code, rapport = self.exporter(faux, "--symboles", "GBPUSD,UK100")
        u = self.univers()
        self.assertEqual((u["decalage_serveur_utc_heures"], u["decalage_fiable"]), (2, True))
        self.assertEqual(u["decalage_mesure_le_utc"], "2026-11-11 14:00:00")
        self.assertIn("décalage fiable déjà mesuré (+2 h", rapport)
        self.assertEqual(set(u["symboles"]), {"EURUSD", "GBPUSD"})
        self.assertIn("UK100", u["absents"])  # dernier tick plus vieux que l'historique : aucune bougie

    def test_export_partiel_et_ancien_decalage_aberrant(self):
        self.dossier.mkdir(parents=True)
        (self.dossier / "univers.json").write_text(json.dumps({
            "genere_le_utc": "2026-11-14 05:37:12", "serveur": "BrokerRegule-Demo", "societe": "Broker Regule Ltd",
            "decalage_serveur_utc_heures": -4383, "decalage_fiable": False, "build_terminal": 6317,
            "symboles": {}, "absents": {}}), encoding="utf-8")
        code, rapport = self.exporter(broker_etendu(ticks_figes={"UK100": 183 * 86400}), "--symboles", "UK100")
        self.assertIsNone(self.univers()["decalage_serveur_utc_heures"])

    def test_autre_serveur_refuse(self):
        self.exporter(broker_etendu(), "--symboles", "EURUSD")
        avant = (self.dossier / "univers.json").read_text(encoding="utf-8")
        for p in self.logs.glob("*"):
            p.unlink()
        code, rapport = self.exporter(broker_fictif(), "--symboles", "EURUSD")
        self.assertEqual(code, 1)
        self.assertIn("contient l'export du serveur « BrokerRegule-Demo »", rapport)
        self.assertIn("--dossier data/univers_", rapport)
        self.assertEqual((self.dossier / "univers.json").read_text(encoding="utf-8"), avant)
        # --lister reste possible
        self.assertEqual(lancer(broker_fictif(), self.dossier, self.logs, "--lister"), 0)

    def test_dossier_ancien_sans_serveur_refuse(self):
        self.dossier.mkdir(parents=True)
        ancien = json.dumps({"genere_le_utc": "2026-11-14 05:40:58", "decalage_serveur_utc_heures": -6,
                             "decalage_fiable": False, "build_terminal": 6317,
                             "symboles": {"EURUSD": {"nom_broker": "EURUSD"}}, "absents": {}})
        (self.dossier / "univers.json").write_text(ancien, encoding="utf-8")
        code, rapport = self.exporter(broker_etendu())
        self.assertEqual(code, 1)
        self.assertIn("ne dit pas de quel serveur il vient", rapport)
        self.assertEqual((self.dossier / "univers.json").read_text(encoding="utf-8"), ancien)
        self.assertEqual([p.name for p in self.dossier.iterdir()], ["univers.json"])

    def test_nom_de_dossier(self):
        code = lancer(broker_etendu(), self.tmp / "autre", self.logs)
        self.assertEqual(code, 1)
        self.assertFalse((self.tmp / "autre").exists())
        self.assertIn("univers_<nom>", next(self.logs.glob("export_univers_*.txt")).read_text(encoding="utf-8"))
        for nom in ("univers", "univers_icm", "univers_broker-2"):
            self.assertTrue(eu.MOTIF_DOSSIER.match(nom), nom)
        for nom in ("univers_", "univers_a b", "mt5", "univers2"):
            self.assertFalse(eu.MOTIF_DOSSIER.match(nom), nom)

    def test_dossier_relatif_a_la_racine(self):
        argv = ["--annees", "1", "--annees-m15", "0.1", "--dossier", "data/univers_test", "--logs", str(self.logs),
                "--symboles", "BTCUSD"]
        with mock.patch.object(eu, "RACINE", self.tmp), mock.patch.object(eu.ex, "_dormir", lambda s: None), \
                mock.patch.dict(sys.modules, {"MetaTrader5": broker_etendu()}), \
                contextlib.redirect_stdout(io.StringIO()):
            code = eu.main(argv, maintenant=MAINTENANT)
        self.assertEqual(code, 0)
        u = json.loads((self.tmp / "data" / "univers_test" / "univers.json").read_text(encoding="utf-8"))
        self.assertEqual(set(u["symboles"]), {"BTCUSD"})


    def test_option_terminal(self):
        faux = broker_etendu()
        appels = []
        original = faux.initialize

        def initialize(*args, **kwargs):
            appels.append(kwargs)
            return original(*args, **kwargs)

        faux.initialize = initialize
        chemin = "C:\\Program Files\\Broker MT5\\terminal64.exe"
        code, rapport = self.exporter(faux, "--symboles", "EURUSD", "--terminal", chemin)
        self.assertEqual(code, 0, rapport)
        self.assertEqual(appels, [{"path": chemin}])

    def test_compte_reel_refuse(self):
        faux = broker_etendu(trade_mode=2)
        code, rapport = self.exporter(faux)
        self.assertEqual(code, 1)
        self.assertIn("compte RÉEL connecté", rapport)
        self.assertFalse(self.dossier.exists())
        self.assertFalse(any(a[0] == "copy_rates_range" for a in faux.appels))

if __name__ == "__main__":
    unittest.main()
