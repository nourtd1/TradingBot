"""Tests de sentitrade/recherche/moteur.py : scénarios calculés à la main.

Pour isoler l'exécution, les signaux de la stratégie sont injectés (unittest.mock.patch de la
fonction de signal) ; les prix sont fabriqués. Montants attendus calculés dans les commentaires.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np
import pandas as pd

from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.donnees import construire_univers

T = pd.Timestamp


def info(contrat=100.0, point=0.01, vmin=0.01, pas=0.01, vmax=100.0, profit="USD", base="XAU",
         swap_mode=0, swap_long=0.0, swap_short=0.0, triple=3):
    return {"digits": 2, "point": point, "trade_contract_size": contrat, "volume_min": vmin, "volume_step": pas,
            "volume_max": vmax, "currency_profit": profit, "currency_base": base, "currency_margin": base,
            "swap_mode": swap_mode, "swap_long": swap_long, "swap_short": swap_short, "swap_rollover3days": triple,
            "trade_calc_mode": 2}


def stats(p50):
    return {"global": {"p50": p50}, "par_heure": {str(h): {"p50": p50} for h in range(24)}}


def bougies(index, o, h, l, c, spread=0):
    n = len(index)
    df = pd.DataFrame({"open": np.asarray(o, float), "high": np.asarray(h, float), "low": np.asarray(l, float),
                       "close": np.asarray(c, float), "tick_volume": np.full(n, 100, np.int64),
                       "spread": np.full(n, spread, np.int64), "real_volume": np.zeros(n, np.int64)},
                      index=pd.DatetimeIndex(index, name="time"))
    return df


def univers(symboles: dict):
    """symboles[nom] = (classe, info, stats, {tf: df})."""
    brut = {nom: {"nom_broker": nom, "classe": c, "info": i, "spread_stats": s, "bougies": b}
            for nom, (c, i, s, b) in symboles.items()}
    return construire_univers(brut)


def fabrique_s1(par_longueur: dict, atr=10.0):
    """par_longueur[nb de bougies] = (entrees {i: sens}, sorties [i]) : le symbole est reconnu par la
    longueur de sa série (chaque symbole d'un test a une longueur différente, ou les mêmes signaux)."""
    def f(df, p):
        e, s = par_longueur[len(df)]
        out = pd.DataFrame(index=df.index)
        out["entree_long"] = [e.get(i) == 1 for i in range(len(df))]
        out["entree_court"] = [e.get(i) == -1 for i in range(len(df))]
        out["sortie_long"] = [i in s for i in range(len(df))]
        out["sortie_court"] = [i in s for i in range(len(df))]
        out["atr"] = atr
        out["pret"] = True
        return out
    return f


S1 = st.strategie_base("S1")
JOURS = pd.bdate_range("2024-01-05", periods=8)   # ven 05, lun 08, mar 09, mer 10, jeu 11, ven 12, ...


class TestExecutionD1(unittest.TestCase):

    def test_gap_a_travers_le_stop(self):
        # spread médian 20 points = 0.20 $ ; glissement marché 0.10, stop 0.20 ; contrat 100.
        # Entrée lundi : 1000 + 0.20 + 0.10 = 1000.30 ; stop = 1000.30 - 2 x 10 = 980.30.
        # Perte par lot = (20 + 0.20) x 100 = 2020 $ ; 0,5 % de 10 000 = 50 $ -> 0.0247 -> 0.02 lot.
        # Mardi ouvre à 970 (sous le stop) : sortie à 970 - 0.20 = 969.80.
        # P&L = (969.80 - 1000.30) x 100 x 0.02 = -61.00 $.
        idx = JOURS[:3]
        d1 = bougies(idx, [1000, 1000, 970], [1001, 1005, 975], [999, 995, 960], [1000, 1000, 965], spread=10)
        u = univers({"XAUUSD": ("metaux", info(), stats(20), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({3: ({0: 1}, [])})):
            r = mo.simuler(u, S1)
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertAlmostEqual(t["prix_entree"], 1000.30)
        self.assertAlmostEqual(t["stop_initial"], 980.30)
        self.assertAlmostEqual(t["lots"], 0.02)
        self.assertEqual(t["raison_sortie"], "stop_gap")
        self.assertAlmostEqual(t["prix_sortie"], 969.80)
        self.assertAlmostEqual(t["pnl_net_usd"], -61.0, places=6)
        self.assertAlmostEqual(r.equity["equity"].iloc[-1], 10000 - 61.0, places=6)
        # risque initial = 0.02 x 2020 = 40.4 $ -> R = -61 / 40.4
        self.assertAlmostEqual(t["r_multiple"], -61.0 / 40.4, places=6)

    def test_stop_touche_dans_la_journee_et_pire_prix(self):
        # Mardi : ouverture 1000 (au-dessus du stop 980.30), plus bas 975 : sortie 980.30 - 0.20 = 980.10.
        idx = JOURS[:3]
        d1 = bougies(idx, [1000, 1000, 1000], [1001, 1005, 1002], [999, 995, 975], [1000, 1000, 990], spread=10)
        u = univers({"XAUUSD": ("metaux", info(), stats(20), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({3: ({0: 1}, [])})):
            r = mo.simuler(u, S1)
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertAlmostEqual(t["prix_sortie"], 980.10)
        self.assertAlmostEqual(t["pnl_net_usd"], (980.10 - 1000.30) * 100 * 0.02, places=6)
        # Lundi : pire prix = plus bas 995 -> (995 - 1000.30) x 2 = -10.60 $
        lundi = r.equity.loc[T("2024-01-08")]
        self.assertAlmostEqual(lundi["equity_pire"], 10000 - 10.60, places=6)
        self.assertAlmostEqual(lundi["equity"], 10000 + (1000 - 1000.30) * 2, places=6)

    def test_swap_triple_le_mercredi(self):
        # Swap long -10 points/nuit = -10 x 0.01 x 100 = -10 $ par lot ; 0.02 lot -> -0.20 $ par nuit.
        # Entrée lundi, sortie vendredi à l'ouverture (signal jeudi) : nuits lun x1, mar x1, mer x3, jeu x1
        # = 6 x -0.20 = -1.20 $. Prix plats : entrée 1000.30, sortie 1000 - 0.10 = 999.90 -> -0.80 $.
        idx = JOURS[:6]
        d1 = bougies(idx, [1000] * 6, [1000] * 6, [1000] * 6, [1000] * 6, spread=10)
        i = info(swap_mode=1, swap_long=-10.0, swap_short=-10.0, triple=3)
        u = univers({"XAUUSD": ("metaux", i, stats(20), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({6: ({0: 1}, [4])})):
            r = mo.simuler(u, S1)
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "signal_sortie")
        self.assertEqual(t["sortie_a"], T("2024-01-12"))
        self.assertAlmostEqual(t["swaps_usd"], -1.20, places=9)
        self.assertAlmostEqual(t["pnl_prix_usd"], -0.80, places=9)
        self.assertAlmostEqual(t["pnl_net_usd"], -2.00, places=9)

    def test_pnl_usdjpy_converti(self):
        # USDJPY : contrat 100 000, point 0.001, spread médian 10 points = 0.010, glissement marché 0.005.
        # Entrée (ouverture mar.) 150.000 + 0.010 + 0.005 = 150.015 ; stop 150.015 - 2 x 1.0 = 148.015.
        # Taux du jour = 1 / clôture de la veille = 1/150 ; perte par lot = 2.010 x 100 000 / 150 = 1340 $
        # -> 50 / 1340 = 0.0373 -> 0.03 lot. Sortie (signal mer.) à l'ouverture jeu. 152 - 0.005 = 151.995,
        # convertie au taux du jeudi = 1 / 151 (clôture du mercredi).
        # P&L = (151.995 - 150.015) x 100 000 x 0.03 / 151 = 5940 / 151 = 39.33775 $.
        idx = JOURS[1:5]
        d1 = bougies(idx, [150, 150, 150.5, 152], [150, 150.5, 151.2, 152.2], [150, 149.5, 150.2, 151.8],
                     [150, 150, 151, 152])
        i = info(contrat=100000.0, point=0.001, profit="JPY", base="USD")
        u = univers({"USDJPY": ("forex", i, stats(10), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({4: ({0: 1}, [2])}, atr=1.0)):
            r = mo.simuler(u, S1)
        t = r.trades.iloc[0]
        self.assertAlmostEqual(t["prix_entree"], 150.015)
        self.assertAlmostEqual(t["lots"], 0.03)
        self.assertAlmostEqual(t["prix_sortie"], 151.995)
        self.assertAlmostEqual(t["pnl_net_usd"], 5940 / 151, places=6)
        self.assertAlmostEqual(t["risque_usd"], 0.03 * 2.010 * 100000 / 150, places=6)

    def test_sous_le_minimum_refuse_et_compte(self):
        # Indice : contrat 1, lots min 1 / pas 1 ; stop 2 x 100 = 200 $ par lot -> 0.25 lot -> 0 : refus.
        idx = JOURS[:3]
        d1 = bougies(idx, [1000] * 3, [1000] * 3, [1000] * 3, [1000] * 3)
        u = univers({"US500": ("indices", info(contrat=1.0, vmin=1.0, pas=1.0), stats(0), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({3: ({0: 1, 1: 1}, [])}, atr=100.0)):
            r = mo.simuler(u, S1)
        self.assertEqual(len(r.trades), 0)
        self.assertEqual(r.compteurs.get("refus:lot_inferieur_minimum"), 2)
        self.assertEqual(int((~r.tentatives["accepte"]).sum()), 2)

    def test_plafond_de_risque_ouvert_4_pourcent(self):
        # 9 indices, spread 0, stop 2 x 50 = 100 $ par lot -> 0.5 lot = 50 $ = 0,5 % exactement.
        # 8 positions = 4,0 % (autorisé) ; la 9e (ordre alphabétique : IDXI) dépasserait : refusée.
        idx = JOURS[:3]
        syms = {}
        for k in "ABCDEFGHI":
            d1 = bougies(idx, [1000] * 3, [1000] * 3, [1000] * 3, [1000] * 3)
            syms[f"IDX{k}"] = ("indices", info(contrat=1.0, base="USD"), stats(0), {"D1": d1})
        u = univers(syms)
        with mock.patch.object(st, "signaux_s1", fabrique_s1({3: ({0: 1}, [])}, atr=50.0)):
            r = mo.simuler(u, S1)
        self.assertEqual(sorted(r.trades["symbole"]), [f"IDX{k}" for k in "ABCDEFGH"])
        self.assertTrue((r.trades["lots"] == 0.5).all())
        self.assertEqual(r.compteurs.get("refus:plafond_risque_ouvert"), 1)

    def test_plafond_de_levier(self):
        # Stop très serré : 2 x 0.1 = 0.2 $ par lot -> 250 lots au risque, soit 250 000 $ de notionnel.
        # Plafond : 10 x 10 000 = 100 000 $ -> 100 lots. Le second symbole n'a plus de levier : refusé.
        idx = JOURS[:3]
        syms = {n: ("indices", info(contrat=1.0, vmax=1000.0, base="USD"), stats(0),
                    {"D1": bougies(idx, [1000] * 3, [1000] * 3, [1000] * 3, [1000] * 3)}) for n in ("IDXA", "IDXB")}
        u = univers(syms)
        with mock.patch.object(st, "signaux_s1", fabrique_s1({3: ({0: 1}, [])}, atr=0.1)):
            r = mo.simuler(u, S1)
        self.assertEqual(list(r.trades["symbole"]), ["IDXA"])
        self.assertAlmostEqual(r.trades.iloc[0]["lots"], 100.0)
        self.assertEqual(r.compteurs.get("taille_reduite:plafond_levier"), 1)
        self.assertEqual(r.compteurs.get("refus:plafond_levier"), 1)


def m15_jour(jour, lignes, spread=0):
    """lignes = [(hh:mm, o, h, l, c)] -> DataFrame M15."""
    idx = [T(f"{jour} {x[0]}") for x in lignes]
    return bougies(idx, [x[1] for x in lignes], [x[2] for x in lignes], [x[3] for x in lignes],
                   [x[4] for x in lignes], spread)


def univers_s4(nom, m15, classe, i, s):
    from sentitrade.data import reechantillonner
    return univers({nom: (classe, i, s, {"M15": m15, "D1": reechantillonner(m15, "D")})})


class TestS4(unittest.TestCase):
    JOUR = "2024-01-09"

    def _eurusd(self, apres):
        rng = [("10:00", 1.1000, 1.1010, 1.0995, 1.1005), ("10:15", 1.1005, 1.1008, 1.0990, 1.1000),
               ("10:30", 1.1000, 1.1006, 1.0992, 1.1003), ("10:45", 1.1003, 1.1009, 1.0996, 1.1005)]
        return m15_jour(self.JOUR, rng + apres)

    def test_oco_premier_declenche_annule_l_autre(self):
        # Range : haut 1.1010, bas 1.0990 ; spread médian 10 points = 0.0001 = glissement stop.
        # 11:00 : Ask max = 1.1012 + 0.0001 >= 1.1010 -> achat à 1.1010 + 0.0001 = 1.1011.
        # Perte par lot = (0.0020 + 2 x 0.0001) x 100 000 = 220 $ -> 50/220 = 0.227 -> 0.22 lot.
        # 11:15 : plus bas 1.0985 <= 1.0990 -> stop à 1.0990 - 0.0001 = 1.0989 (la vente-stop était annulée).
        # P&L = (1.0989 - 1.1011) x 100 000 x 0.22 = -48.40 $.
        m15 = self._eurusd([("11:00", 1.1005, 1.1012, 1.1000, 1.1008), ("11:15", 1.1008, 1.1009, 1.0985, 1.0986),
                            ("11:30", 1.0986, 1.0987, 1.0970, 1.0975)])
        u = univers_s4("EURUSD", m15, "forex", info(contrat=100000.0, point=0.00001, base="EUR"), stats(10))
        r = mo.simuler(u, st.strategie_base("S4"))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual(t["sens"], 1)
        self.assertAlmostEqual(t["prix_entree"], 1.1011)
        self.assertAlmostEqual(t["lots"], 0.22)
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertAlmostEqual(t["prix_sortie"], 1.0989)
        self.assertAlmostEqual(t["pnl_net_usd"], -48.40, places=6)

    def test_deux_niveaux_dans_la_meme_bougie_hypothese_defavorable(self):
        m15 = self._eurusd([("11:00", 1.1000, 1.1015, 1.0985, 1.1000)])
        u = univers_s4("EURUSD", m15, "forex", info(contrat=100000.0, point=0.00001, base="EUR"), stats(10))
        r = mo.simuler(u, st.strategie_base("S4"))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop_meme_bougie")
        self.assertAlmostEqual(t["pnl_net_usd"], (1.0989 - 1.1011) * 100000 * 0.22, places=6)

    def test_sortie_forcee_2155_forex(self):
        apres = [("11:00", 1.1005, 1.1012, 1.1000, 1.1008)]
        for h in range(11, 23):
            for m in (0, 15, 30, 45):
                if (h, m) > (11, 0):
                    apres.append((f"{h:02d}:{m:02d}", 1.1008, 1.1009, 1.1007, 1.1008))
        m15 = self._eurusd(apres)
        u = univers_s4("EURUSD", m15, "forex", info(contrat=100000.0, point=0.00001, base="EUR"), stats(10))
        r = mo.simuler(u, st.strategie_base("S4"))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "cloture_forcee")
        self.assertEqual(t["sortie_a"], T(f"{self.JOUR} 21:45"))   # bougie qui contient 21:55
        self.assertAlmostEqual(t["prix_sortie"], 1.1008 - 0.00005)  # Bid - 0,5 x spread médian

    def test_sortie_forcee_2245_indice_et_echeance(self):
        # US500 : range 16:30-17:15 ; aucun déclenchement avant 19:45 (échéance 22:45 - 3 h) : ordres
        # annulés ; un second jour : déclenchement à 17:30 et sortie forcée à 22:45.
        def jour(d, declenche):
            l = [("16:30", 5000, 5005, 4995, 5000), ("16:45", 5000, 5004, 4996, 5000),
                 ("17:00", 5000, 5003, 4997, 5000), ("17:15", 5000, 5002, 4998, 5000)]
            for h in range(17, 23):
                for m in (0, 15, 30, 45):
                    if (h, m) >= (17, 30):
                        if declenche and (h, m) == (17, 30):
                            l.append((f"{h:02d}:{m:02d}", 5000, 5006, 4999, 5004))
                        elif not declenche and (h, m) == (20, 0):
                            l.append((f"{h:02d}:{m:02d}", 5000, 5010, 4999, 5000))   # après l'échéance
                        else:
                            l.append((f"{h:02d}:{m:02d}", 5004 if declenche else 5000, 5004.5 if declenche else 5001,
                                      5003.5 if declenche else 4999, 5004 if declenche else 5000))
            return m15_jour(d, l)
        m15 = pd.concat([jour("2024-01-09", False), jour("2024-01-10", True)])
        u = univers_s4("US500", m15, "indices", info(contrat=1.0, base="USD"), stats(50))
        r = mo.simuler(u, st.strategie_base("S4"))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual(t["entree_a"], T("2024-01-10 17:30"))
        self.assertEqual(t["sortie_a"], T("2024-01-10 22:45"))
        self.assertEqual(t["raison_sortie"], "cloture_forcee")
        self.assertEqual(r.compteurs.get("annulation:echeance"), 1)

    def test_range_trop_etroit_ignore(self):
        m15 = self._eurusd([("11:00", 1.1005, 1.1012, 1.1000, 1.1008)])
        # spread médian 800 points = 0.008 : 3 x 0.008 > range 0.002 -> jour ignoré
        u = univers_s4("EURUSD", m15, "forex", info(contrat=100000.0, point=0.00001, base="EUR"), stats(800))
        r = mo.simuler(u, st.strategie_base("S4"))
        self.assertEqual(len(r.trades), 0)
        self.assertEqual(r.compteurs.get("jour_ignore:range_trop_etroit"), 1)


def fabrique_s2(drapeaux: dict, vols: dict, signe=1.0, atr=1.0):
    def f(df, p, crypto):
        n = len(df)
        out = pd.DataFrame(index=df.index)
        out["reequilibrer"] = [i in drapeaux for i in range(n)]
        out["signe"] = signe
        out["vol"] = [vols.get(i, 0.10) for i in range(n)]
        out["atr"] = atr
        out["pret"] = True
        return out
    return f


class TestS2(unittest.TestCase):

    def test_reequilibrage_seulement_au_dela_de_25_pourcent(self):
        # N = 1, equity 10 000 (prix plats, aucun coût), notionnel d'un lot 1000 $.
        # Semaine 1 : vol 10 % -> 0.10 x 10 000 / (1000 x 0.10) = 10 lots.
        # Semaine 2 : vol 8 % -> 12.5 lots : écart 25 % exactement -> PAS de rééquilibrage.
        # Semaine 3 : vol 7.99 % -> 12.515... -> 12.51 lots : écart 25,1 % -> rééquilibrage à 12.51.
        # Semaine 4 : vol 9.5 % -> 10.526 -> 10.52 : écart 15,9 % -> rien.
        idx = pd.bdate_range("2024-01-08", periods=20)          # 4 semaines, lundis aux indices 0, 5, 10, 15
        d1 = bougies(idx, [1000] * 20, [1000] * 20, [1000] * 20, [1000] * 20)
        u = univers({"IDXA": ("indices", info(contrat=1.0, base="USD"), stats(0), {"D1": d1})})
        with mock.patch.object(st, "signaux_s2", fabrique_s2({0: 1, 5: 1, 10: 1, 15: 1},
                                                             {0: 0.10, 5: 0.08, 10: 0.0799, 15: 0.095})):
            r = mo.simuler(u, st.strategie_base("S2"))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertAlmostEqual(t["lots"], 12.51)
        self.assertEqual(t["ajustements"], 1)
        self.assertEqual(t["raison_sortie"], "fin_periode")
        self.assertEqual(r.nb_reequilibrages, 4)

    def test_retournement_et_stop_puis_a_plat(self):
        # Semaine 1 : long 10 lots, stop = 1000 - 4 x 1 = 996. Mardi : plus bas 990 -> stop à 996.
        # Reste à plat jusqu'au lundi suivant, où il rouvre.
        idx = pd.bdate_range("2024-01-08", periods=10)
        lows = [1000] * 10
        lows[1] = 990
        d1 = bougies(idx, [1000] * 10, [1000] * 10, lows, [1000] * 10)
        u = univers({"IDXA": ("indices", info(contrat=1.0, base="USD"), stats(0), {"D1": d1})})
        with mock.patch.object(st, "signaux_s2", fabrique_s2({0: 1, 5: 1}, {})):
            r = mo.simuler(u, st.strategie_base("S2"))
        self.assertEqual(list(r.trades["raison_sortie"]), ["stop", "fin_periode"])
        self.assertEqual(r.trades.iloc[1]["entree_a"], T("2024-01-15"))
        self.assertAlmostEqual(r.trades.iloc[0]["pnl_net_usd"], -4.0 * 10, places=9)


class TestGardeEtCombinaison(unittest.TestCase):

    def test_arret_15_date_mais_non_bloquant(self):
        # Contrat 100, ATR 1 : stop à 2 $ -> 200 $ par lot -> 0.25 lot (notionnel 25 000 $).
        # Mardi ouvre à 930 : gap à travers le stop, perte 0.25 x 100 x 70 = 1 750 $ = -17,5 % :
        # arrêt -15 % daté ce jour-là, mais la simulation continue et prend le signal suivant.
        idx = JOURS[:6]
        o = [1000, 1000, 930, 930, 930, 930]
        d1 = bougies(idx, o, o, o, o)
        u = univers({"IDXA": ("indices", info(contrat=100.0, base="USD"), stats(0), {"D1": d1})})
        with mock.patch.object(st, "signaux_s1", fabrique_s1({6: ({0: 1, 3: 1}, [])}, atr=1.0)):
            r = mo.simuler(u, S1)
        self.assertEqual(len(r.trades), 2)
        self.assertAlmostEqual(r.trades.iloc[0]["pnl_net_usd"], -1750.0, places=6)
        self.assertEqual(r.date_arret, T("2024-01-09"))
        # 2e trade : 0,5 % de 8 250 = 41.25 $ / 200 $ -> 0.2 lot
        self.assertAlmostEqual(r.trades.iloc[1]["lots"], 0.2)
        self.assertEqual(r.trades.iloc[1]["entree_a"], T("2024-01-11"))

    def test_combinaison_additionne_les_equity(self):
        idx = JOURS[:3]
        eq1 = pd.DataFrame({"equity": [5000.0, 5100.0, 5200.0], "equity_pire": [5000.0, 5050, 5150],
                            "balance": [5000.0] * 3}, index=idx)
        eq2 = pd.DataFrame({"equity": [4900.0, 5000.0], "equity_pire": [4800.0, 4950],
                            "balance": [5000.0] * 2}, index=idx[1:])
        vide = pd.DataFrame(columns=mo.COLONNES_TRADES)

        def res(eq):
            return mo.ResultatSimulation("S", "base", 5000.0, eq, vide, pd.DataFrame(columns=mo.COLONNES_EVENEMENTS),
                                         pd.DataFrame(columns=mo.COLONNES_TENTATIVES), {}, {}, {}, None, None)
        c = mo.combiner([res(eq1), res(eq2)], "S1+S2")
        self.assertEqual(list(c.equity["equity"]), [10000.0, 10000.0, 10200.0])
        self.assertEqual(list(c.equity["equity_pire"]), [10000.0, 9850.0, 10100.0])
        self.assertEqual(c.capital_initial, 10000.0)


class TestOutils(unittest.TestCase):
    def test_plancher_lots(self):
        self.assertEqual(mo.plancher_lots(0.29, 0.01), 0.29)
        self.assertEqual(mo.plancher_lots(0.0299999, 0.01), 0.02)
        self.assertEqual(mo.plancher_lots(12.515, 0.01), 12.51)
        self.assertEqual(mo.plancher_lots(-1, 0.01), 0.0)
        self.assertEqual(mo.plancher_lots(float("nan"), 0.01), 0.0)


if __name__ == "__main__":
    unittest.main()
