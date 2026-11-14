"""Tests de scripts/check_env.py : section MetaTrader 5 (faux module), réseau (serveur local), rapport."""
from __future__ import annotations

import contextlib
import http.server
import io
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import scripts.check_env as ce
from tests.fakes.fake_mt5 import LOGIN_FICTIF, NOM_FICTIF, FauxMT5, symbole_fictif

MAINTENANT = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)


def silencieux():
    return contextlib.redirect_stdout(io.StringIO())


class TestSectionMT5(unittest.TestCase):
    def verifier(self, faux):
        r = ce.Rapport()
        with silencieux():
            ce.verifier_mt5(r, {"MetaTrader5": faux})
        return r, "\n".join(r.lignes)

    def test_terminal_ok(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        r, texte = self.verifier(faux)
        self.assertTrue(r.bilans)
        self.assertTrue(all(ok for ok, _ in r.bilans), r.bilans)
        for attendu in ("build 5200", "Algo Trading : activé", "type de compte : démo", "devise du compte : USD",
                        "levier : 1:100", "hedging", "symbole de l'or trouvé : XAUUSD", "décimales : 2",
                        "taille du contrat : 100.0", "volume min : 0.01", "spread actuel : 25 points"):
            self.assertIn(attendu, texte)
        self.assertEqual(faux.appels[-1][0], "shutdown")

    def test_jamais_login_nom_ni_chemins(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        _, texte = self.verifier(faux)
        self.assertNotIn(str(LOGIN_FICTIF), texte)
        self.assertNotIn(NOM_FICTIF, texte)

    def test_terminal_ferme(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, terminal_ouvert=False)
        r, texte = self.verifier(faux)
        self.assertIn("ouvre MetaTrader 5 et connecte-toi au compte démo", texte)
        self.assertIn("-10003", texte)
        self.assertEqual([ok for ok, _ in r.bilans], [False])
        self.assertEqual(faux.appels[-1][0], "shutdown")

    def test_algo_trading_desactive(self):
        r, texte = self.verifier(FauxMT5(maintenant_utc=MAINTENANT, algo_trading=False))
        self.assertIn("[!!] bouton Algo Trading : DÉSACTIVÉ", texte)
        self.assertIn(False, [ok for ok, _ in r.bilans])

    def test_pas_connecte(self):
        r, texte = self.verifier(FauxMT5(maintenant_utc=MAINTENANT, connecte=False))
        self.assertIn("connexion au serveur du broker : NON", texte)
        self.assertIn(False, [ok for ok, _ in r.bilans])

    def test_compte_reel_avertit(self):
        r, texte = self.verifier(FauxMT5(maintenant_utc=MAINTENANT, trade_mode=2))
        self.assertIn("[!!] type de compte : RÉEL", texte)
        self.assertTrue(any(not ok and "RÉEL" in t for ok, t in r.bilans))

    def test_devise_non_usd(self):
        r, _ = self.verifier(FauxMT5(maintenant_utc=MAINTENANT, devise="EUR"))
        self.assertTrue(any(not ok and "EUR" in t for ok, t in r.bilans))

    def test_netting_accepte(self):
        r, texte = self.verifier(FauxMT5(maintenant_utc=MAINTENANT, margin_mode=0))
        self.assertIn("netting", texte)
        self.assertTrue(all(ok for ok, _ in r.bilans))

    def test_or_introuvable(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[symbole_fictif("EURUSD", currency_base="EUR"),
                                                            symbole_fictif("XAUEUR", currency_profit="EUR")])
        r, texte = self.verifier(faux)
        self.assertIn("aucun symbole or/dollar", texte)
        self.assertIn("XAUEUR", texte)
        self.assertTrue(any(not ok and "Observation du marché" in t for ok, t in r.bilans))

    def test_module_absent_hors_windows(self):
        r = ce.Rapport()
        with silencieux(), mock.patch.object(ce, "EST_WINDOWS", False):
            ce.verifier_mt5(r, {})
        self.assertIn("[--]", "\n".join(r.lignes))
        self.assertEqual(r.bilans, [])


class TestChoixSymbole(unittest.TestCase):
    def test_priorites(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[
            symbole_fictif("XAUUSD.p"),
            symbole_fictif("XAUUSD", visible=True, trade_mode=0),
            symbole_fictif("XAUUSD.ecn", visible=True),
            symbole_fictif("XAUUSD_perso", visible=True, custom=True)])
        faux.initialize()
        nom, candidats, explication = ce.choisir_symbole_or(faux)
        self.assertEqual(nom, "XAUUSD.ecn")  # tradable et visible avant le nom le plus court
        self.assertNotIn("XAUUSD_perso", candidats)  # symbole personnalisé ignoré
        self.assertIn("plusieurs", explication)

    def test_gold(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[symbole_fictif("GOLD")])
        faux.initialize()
        self.assertEqual(ce.choisir_symbole_or(faux)[0], "GOLD")

    def test_action_gold_ignoree(self):
        # Cas réel MetaQuotes-Demo (2026-11-13) : GOLD = action Barrick Gold, visible et tradable.
        action = dict(currency_base="USD", currency_profit="USD", path="Nasdaq\\Stock\\GOLD",
                      description="Barrick Gold Corp", trade_contract_size=1.0, visible=True)
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[
            symbole_fictif("GOLD", **action), symbole_fictif("XAUUSD", visible=False)])
        faux.initialize()
        nom, candidats, _ = ce.choisir_symbole_or(faux)
        self.assertEqual(nom, "XAUUSD")
        self.assertEqual(candidats, ["XAUUSD"])
        # seule, l'action n'est jamais prise pour de l'or
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[symbole_fictif("GOLD", **action)])
        faux.initialize()
        self.assertIsNone(ce.choisir_symbole_or(faux)[0])

    def test_repli_sans_devise_de_base(self):
        faux = FauxMT5(maintenant_utc=MAINTENANT, symboles=[
            symbole_fictif("XAUUSD.r", currency_base=""), symbole_fictif("GOLDX", currency_base="")])
        faux.initialize()
        self.assertEqual(ce.choisir_symbole_or(faux)[1], ["XAUUSD.r"])

    def test_libelles(self):
        self.assertEqual(ce.texte_trade_mode(0), ("demo", "démo"))
        self.assertEqual(ce.texte_trade_mode(2)[0], "reel")
        self.assertEqual(ce.texte_margin_mode(2)[0], "hedging")
        self.assertEqual(ce.texte_margin_mode(0)[0], "netting")
        self.assertTrue(ce.texte_margin_mode(None)[0].startswith("inconnu"))


class TestLibrairies(unittest.TestCase):
    LIBS = [("json", "json-stdlib", "test", True),
            ("MetaTrader5", "MetaTrader5", "pilotage du terminal MetaTrader 5", False)]

    def test_mt5_absent_hors_windows_informatif(self):
        r = ce.Rapport()
        with silencieux(), mock.patch.object(ce, "LIBRAIRIES", self.LIBS), \
                mock.patch.object(ce, "EST_WINDOWS", False), mock.patch.dict(sys.modules, {"MetaTrader5": None}):
            modules = ce.verifier_librairies(r)
        self.assertNotIn("MetaTrader5", modules)
        self.assertTrue(any(l.startswith("[--] MetaTrader5") for l in r.lignes))
        self.assertEqual(r.bilans, [(True, "Librairies 1/1")])

    def test_mt5_absent_sous_windows_est_un_echec(self):
        r = ce.Rapport()
        with silencieux(), mock.patch.object(ce, "LIBRAIRIES", self.LIBS), \
                mock.patch.object(ce, "EST_WINDOWS", True), mock.patch.dict(sys.modules, {"MetaTrader5": None}):
            ce.verifier_librairies(r)
        self.assertFalse(r.bilans[0][0])
        self.assertIn("MetaTrader5", r.bilans[0][1])

    def test_mt5_present(self):
        r = ce.Rapport()
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        vraie_version = ce.metadata.version

        def version_hermetique(nom):
            # Sur un PC où le vrai paquet MetaTrader5 est installé, metadata renverrait
            # sa version : on force la lecture de __version__ du faux module.
            if nom == "MetaTrader5":
                raise ce.metadata.PackageNotFoundError(nom)
            return vraie_version(nom)

        with silencieux(), mock.patch.object(ce, "LIBRAIRIES", self.LIBS), \
                mock.patch.object(ce.metadata, "version", version_hermetique), \
                mock.patch.dict(sys.modules, {"MetaTrader5": faux}):
            modules = ce.verifier_librairies(r)
        self.assertIs(modules["MetaTrader5"], faux)
        self.assertTrue(any(l.startswith("[OK] MetaTrader5") and "5.0.5200" in l for l in r.lignes))


class _Gestionnaire(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        codes = {"/ok": 200, "/introuvable": 404, "/interdit": 403}
        code = codes.get(self.path, 500)
        corps = b'{"ok": true}'
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):  # silencieux
        pass


class TestReseau(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Gestionnaire)
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        # port fermé : on en réserve un puis on le libère
        tmp = http.server.HTTPServer(("127.0.0.1", 0), _Gestionnaire)
        cls.port_ferme = tmp.server_address[1]
        tmp.server_close()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def test_acces(self):
        sources = [("A", f"{self.base}/ok", "role A", ()),
                   ("B", f"{self.base}/introuvable", "role B", (401, 404)),
                   ("C", f"{self.base}/interdit", "role C", ()),
                   ("D", f"http://127.0.0.1:{self.port_ferme}/", "role D", ())]
        r = ce.Rapport()
        with silencieux(), mock.patch.object(ce, "SOURCES", sources), mock.patch.object(ce, "DELAI_RESEAU_S", 3):
            res = ce.verifier_reseau(r)
        self.assertEqual([x["ok"] for x in res], [True, True, False, False])
        self.assertIn("HTTP 403", res[2]["etat"])
        self.assertIn("inaccessible", res[3]["etat"])
        self.assertEqual(r.bilans, [(True, "Accès internet 2/4 : A, B")])

    def test_aucun_acces(self):
        sources = [("D", f"http://127.0.0.1:{self.port_ferme}/", "role D", ())]
        r = ce.Rapport()
        with silencieux(), mock.patch.object(ce, "SOURCES", sources), mock.patch.object(ce, "DELAI_RESEAU_S", 3):
            ce.verifier_reseau(r)
        self.assertFalse(r.bilans[0][0])
        self.assertIn("pare-feu", r.bilans[0][1])

    def test_sources_reelles(self):
        noms = [s[0] for s in ce.SOURCES]
        self.assertEqual(noms, ["PyPI", "Telegram", "Discord"])
        for s in ce.SOURCES:
            self.assertTrue(s[1].startswith("https://"))


class TestMain(unittest.TestCase):
    def test_rapport_complet_sans_reseau(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_check_env_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        faux = FauxMT5(maintenant_utc=MAINTENANT)
        with silencieux(), mock.patch.object(ce, "DOSSIER_LOGS", tmp), \
                mock.patch.dict(sys.modules, {"MetaTrader5": faux}):
            code = ce.main(["--no-network"])
        self.assertIn(code, (0, 1))
        rapports = list(tmp.glob("check_env_*.txt"))
        self.assertEqual(len(rapports), 1)
        texte = rapports[0].read_text(encoding="utf-8")
        for section in ("=== Python ===", "=== Librairies ===", "=== Réseau ===", "=== Terminal MetaTrader 5 ===",
                        "=== RÉSUMÉ ==="):
            self.assertIn(section, texte)
        self.assertIn("[OK] Symbole de l'or : XAUUSD", texte)
        self.assertNotIn(str(LOGIN_FICTIF), texte)
        self.assertNotIn(NOM_FICTIF, texte)
        self.assertNotIn("ccxt", texte)


if __name__ == "__main__":
    unittest.main()
