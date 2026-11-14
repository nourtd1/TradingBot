#!/usr/bin/env python3
"""Vérification de l'environnement SentiTrade (MetaTrader 5).

Contrôle la version de Python, les librairies, les calculs de base
(numpy/pandas), les fuseaux horaires, l'accès à internet (PyPI pour les
mises à jour, Telegram et Discord pour les alertes) et, si le module
MetaTrader5 est installé, le terminal MetaTrader 5 : connexion, bouton
Algo Trading, type de compte et symbole de l'or.

Usage :
    python scripts/check_env.py               # vérification complète
    python scripts/check_env.py --no-network  # sans les tests réseau

Le rapport est affiché puis enregistré dans logs/check_env_<os>_<date>.txt.
Code de sortie : 0 si tout est OK, 1 s'il y a au moins un point à regarder.

Compatible Python 3.10 à 3.13. Les tests réseau n'utilisent que la
bibliothèque standard : ils fonctionnent même si l'installation a échoué.
Ce fichier ne dépend que de la bibliothèque standard ; ses fonctions MT5
(choix du symbole de l'or, libellés) sont réutilisées par
scripts/exporter_donnees_mt5.py.

Confidentialité : le numéro de compte (login), le nom du titulaire et le
mot de passe ne sont JAMAIS lus pour être affichés ni écrits.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_LOGS = RACINE / "logs"
PYTHON_MIN, PYTHON_MAX = (3, 10), (3, 13)
DELAI_RESEAU_S = 8
USER_AGENT = "Mozilla/5.0 (SentiTrade check_env)"
EST_WINDOWS = sys.platform == "win32"

# (module à importer, nom pip, rôle, obligatoire hors Windows)
LIBRAIRIES = [
    ("numpy", "numpy", "calcul numérique", True),
    ("pandas", "pandas", "séries temporelles, backtests", True),
    ("yaml", "PyYAML", "fichiers de configuration", True),
    ("matplotlib", "matplotlib", "graphiques des rapports", True),
    ("requests", "requests", "HTTP, alertes", True),
    ("dotenv", "python-dotenv", "chargement des secrets", True),
    ("MetaTrader5", "MetaTrader5", "pilotage du terminal MetaTrader 5", False),
]

# (nom, URL, rôle, codes HTTP d'erreur qui prouvent quand même que le serveur répond)
SOURCES = [
    ("PyPI", "https://pypi.org/pypi/MetaTrader5/json", "installation et mises à jour des librairies", ()),
    ("Telegram", "https://api.telegram.org/bot0/getMe", "alertes Telegram", (401, 404)),
    ("Discord", "https://discord.com/api/v10/gateway", "alertes Discord", ()),
]

# Libellés des énumérations MT5 (valeurs de la documentation MetaQuotes).
# Code ASCII (pour les fichiers JSON) et texte affiché.
TRADE_MODE_COMPTE = {0: ("demo", "démo"), 1: ("concours", "concours"), 2: ("reel", "RÉEL")}
MARGIN_MODE_COMPTE = {0: ("netting", "netting"), 1: ("exchange", "bourse (exchange)"),
                      2: ("hedging", "hedging")}
SYMBOL_TRADE_MODE_FULL = 4


class Rapport:
    """Affiche au fil de l'eau et garde tout pour le fichier de rapport."""

    def __init__(self) -> None:
        self.lignes: list[str] = []
        self.bilans: list[tuple[bool, str]] = []

    def ecrire(self, texte: str = "") -> None:
        print(texte, flush=True)
        self.lignes.append(texte)

    def titre(self, texte: str) -> None:
        self.ecrire()
        self.ecrire(f"=== {texte} ===")

    def bilan(self, ok: bool, texte: str) -> None:
        self.bilans.append((ok, texte))


def _marque(ok: bool) -> str:
    return "[OK]" if ok else "[!!]"


# --------------------------------------------------------------------------- #
# Outils MetaTrader 5 partagés (bibliothèque standard uniquement)
# --------------------------------------------------------------------------- #
def texte_trade_mode(valeur) -> tuple[str, str]:
    """(code ASCII, texte affiché) du type de compte : démo, concours ou réel."""
    try:
        return TRADE_MODE_COMPTE[int(valeur)]
    except (KeyError, TypeError, ValueError):
        return (f"inconnu_{valeur}", f"inconnu ({valeur})")


def texte_margin_mode(valeur) -> tuple[str, str]:
    """(code ASCII, texte affiché) du mode de compte : netting ou hedging."""
    try:
        return MARGIN_MODE_COMPTE[int(valeur)]
    except (KeyError, TypeError, ValueError):
        return (f"inconnu_{valeur}", f"inconnu ({valeur})")


def est_compte_reel(mt5, account) -> bool:
    return int(getattr(account, "trade_mode", -1)) == int(getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", 2))


def erreur_mt5(mt5) -> str:
    """Dernière erreur MT5 sous forme lisible, sans jamais lever d'exception."""
    try:
        err = mt5.last_error()
    except Exception as e:  # module cassé
        return f"last_error() indisponible ({type(e).__name__})"
    try:
        code, message = err
        return f"code {code} : {message}"
    except (TypeError, ValueError):
        return str(err)


def _est_or_en_usd(s) -> bool:
    """Vrai si le symbole est l'or (once) coté en dollars.

    Correction du 2026-11-13 (constaté sur MetaQuotes-Demo) : « GOLD » peut être
    l'ACTION Barrick Gold (path Nasdaq\\Stock\\GOLD, devise de base USD). On exige
    donc currency_base == "XAU" et currency_profit == "USD" ; le nom ne suffit plus.
    Repli, seulement si le broker ne renseigne pas currency_base : nom contenant
    XAUUSD, profit en USD, et path qui ne désigne pas une action.
    """
    nom = str(getattr(s, "name", "")).upper()
    base = str(getattr(s, "currency_base", "") or "").upper()
    profit = str(getattr(s, "currency_profit", "") or "").upper()
    chemin = str(getattr(s, "path", "") or "").upper()
    if profit != "USD" or "STOCK" in chemin or "SHARE" in chemin or "EQUIT" in chemin:
        return False
    if base:
        return base == "XAU"
    return "XAUUSD" in nom


def choisir_symbole_or(mt5) -> tuple[str | None, list[str], str]:
    """Cherche le symbole de l'or contre dollar chez le broker.

    Interroge symbols_get("*XAU*") puis symbols_get("GOLD*"). Parmi les
    symboles or/USD, préfère celui qui est tradable (trade_mode FULL), puis
    visible dans l'Observation du marché, puis le nom le plus court.
    Renvoie (nom choisi ou None, noms des candidats or/USD, explication).
    """
    trouves: dict = {}
    for motif in ("*XAU*", "GOLD*"):
        try:
            res = mt5.symbols_get(group=motif)
        except Exception:
            res = None
        for s in res or ():
            if not getattr(s, "custom", False):
                trouves.setdefault(str(s.name), s)
    candidats = [s for s in trouves.values() if _est_or_en_usd(s)]
    if not candidats:
        autres = ", ".join(sorted(trouves)) or "aucun"
        return None, [], (f"aucun symbole or/dollar trouvé (symboles contenant XAU ou GOLD : {autres}). "
                          "Ajoute l'or dans l'Observation du marché ou indique son nom avec --symbole.")
    full = int(getattr(mt5, "SYMBOL_TRADE_MODE_FULL", SYMBOL_TRADE_MODE_FULL))

    def priorite(s):
        tradable = int(getattr(s, "trade_mode", full)) == full
        visible = bool(getattr(s, "visible", False))
        return (not tradable, not visible, len(s.name), s.name)

    candidats.sort(key=priorite)
    noms = [s.name for s in candidats]
    choisi = candidats[0]
    if len(candidats) == 1:
        explication = f"symbole de l'or trouvé : {choisi.name}"
    else:
        qualites = []
        if int(getattr(choisi, "trade_mode", full)) == full:
            qualites.append("tradable")
        if getattr(choisi, "visible", False):
            qualites.append("visible")
        pourquoi = " et ".join(qualites) or "nom le plus simple"
        explication = (f"plusieurs symboles de l'or trouvés ({', '.join(noms)}) : {choisi.name} retenu "
                       f"({pourquoi}). Pour en imposer un autre : --symbole NOM")
    return choisi.name, noms, explication


# --------------------------------------------------------------------------- #
# Vérifications locales
# --------------------------------------------------------------------------- #
def verifier_python(r: Rapport) -> None:
    r.titre("Python")
    version = (sys.version_info.major, sys.version_info.minor)
    est_64_bits = sys.maxsize > 2**32
    r.ecrire(f"Version    : {platform.python_version()} ({'64' if est_64_bits else '32'} bits)")
    r.ecrire(f"Exécutable : {sys.executable}")
    r.ecrire(f"Système    : {platform.platform()}")
    ok = PYTHON_MIN <= version <= PYTHON_MAX and est_64_bits
    detail = "" if ok else (
        f" -> il faut un Python 64 bits entre {PYTHON_MIN[0]}.{PYTHON_MIN[1]}"
        f" et {PYTHON_MAX[0]}.{PYTHON_MAX[1]}"
    )
    r.bilan(ok, f"Python {platform.python_version()}{detail}")


def _version(module, nom_pip: str) -> str:
    try:
        return metadata.version(nom_pip)
    except metadata.PackageNotFoundError:
        return str(getattr(module, "__version__", "?"))


def verifier_librairies(r: Rapport) -> dict:
    r.titre("Librairies")
    modules: dict = {}
    manquantes: list[str] = []
    total = 0
    for module, nom_pip, role, partout in LIBRAIRIES:
        try:
            m = importlib.import_module(module)
        except Exception as e:  # absente, ou installation cassée
            if not partout and not EST_WINDOWS:
                r.ecrire(f"[--] {nom_pip:<14} {'absent':<12} {role} (normal : n'existe que sous Windows)")
                continue
            total += 1
            manquantes.append(nom_pip)
            r.ecrire(f"[!!] {nom_pip:<14} {'absent':<12} {role} ({type(e).__name__})")
            continue
        total += 1
        modules[module] = m
        r.ecrire(f"[OK] {nom_pip:<14} {_version(m, nom_pip):<12} {role}")
    detail = f" -> manquantes : {', '.join(manquantes)} (relance INSTALLER.bat)" if manquantes else ""
    r.bilan(not manquantes, f"Librairies {total - len(manquantes)}/{total}{detail}")
    return modules


def verifier_calculs(r: Rapport, modules: dict) -> None:
    r.titre("Calculs numpy / pandas")
    if "numpy" not in modules or "pandas" not in modules:
        r.ecrire("[!!] numpy ou pandas absent : test impossible")
        r.bilan(False, "Calculs numpy/pandas : librairies absentes")
        return
    np, pd = modules["numpy"], modules["pandas"]
    try:
        serie = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        moyenne = serie.rolling(3).mean()
        assert int(moyenne.isna().sum()) == 2, "moyenne mobile : mauvais nombre de valeurs vides"
        assert np.allclose(moyenne.iloc[2:].to_numpy(), [2.0, 3.0, 4.0]), "moyenne mobile fausse"
        ema = serie.ewm(span=3, adjust=False).mean()
        assert np.allclose(ema.to_numpy(), [1.0, 1.5, 2.25, 3.125, 4.0625]), "EMA fausse"

        rng = np.random.default_rng(42)
        prix = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 10_000)))
        index = pd.date_range("2024-01-01", periods=prix.size, freq="h", tz="UTC")
        cloture = pd.Series(prix, index=index)
        rendements = cloture.pct_change().dropna()
        assert len(rendements) == 9_999, "rendements : mauvaise longueur"
        assert bool(np.isfinite(rendements.to_numpy()).all()), "rendements non finis"
        bougies = cloture.resample("1D").ohlc()
        assert len(bougies) == 417, "rééchantillonnage journalier : mauvais nombre de bougies"
        assert bool((bougies["high"] >= bougies["low"]).all()), "bougies incohérentes"
    except Exception as e:
        r.ecrire(f"[!!] {type(e).__name__} : {e}")
        r.bilan(False, f"Calculs numpy/pandas -> {e}")
        return
    r.ecrire("[OK] moyenne mobile, EMA, rendements, rééchantillonnage OHLC")
    r.bilan(True, "Calculs numpy/pandas")


def verifier_fuseaux(r: Rapport, modules: dict) -> None:
    r.titre("Fuseaux horaires")
    try:
        from zoneinfo import ZoneInfo  # a besoin du paquet tzdata sous Windows (installé avec pandas)

        ete = dt.datetime(2024, 6, 1, 12, 0, tzinfo=dt.timezone.utc)
        hiver = dt.datetime(2024, 1, 15, 12, 0, tzinfo=dt.timezone.utc)
        new_york, paris = ZoneInfo("America/New_York"), ZoneInfo("Europe/Paris")
        assert ete.astimezone(new_york).hour == 8 and hiver.astimezone(new_york).hour == 7, "New York"
        assert ete.astimezone(paris).hour == 14 and hiver.astimezone(paris).hour == 13, "Paris"
        if "pandas" in modules:
            t = modules["pandas"].Timestamp("2024-06-01 12:00", tz="UTC").tz_convert("America/New_York")
            assert t.hour == 8, "conversion pandas"
    except Exception as e:
        r.ecrire(f"[!!] {type(e).__name__} : {e}")
        r.bilan(False, f"Fuseaux horaires -> {type(e).__name__} : {e}")
        return
    local = dt.datetime.now().astimezone()
    r.ecrire("[OK] base des fuseaux disponible, heures d'été et d'hiver correctes")
    r.ecrire(f"     fuseau de cette machine : {local.tzname()} (UTC{local:%z})")
    r.bilan(True, "Fuseaux horaires")


# --------------------------------------------------------------------------- #
# Vérifications réseau
# --------------------------------------------------------------------------- #
def _interroger(nom: str, url: str, role: str, codes_ok=()) -> dict:
    res = {"nom": nom, "role": role, "ok": False}
    requete = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    debut = time.time()
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_RESEAU_S) as reponse:
            reponse.read(65536)
    except urllib.error.HTTPError as e:
        latence = round((time.time() - debut) * 1000)
        if e.code in codes_ok:
            res.update(ok=True, etat=f"OK, le serveur répond ({latence} ms)")
        elif e.code == 429:
            res.update(ok=True, etat="accessible, mais limite de requêtes atteinte (HTTP 429)")
        elif e.code in (403, 451):
            res["etat"] = f"refusé (HTTP {e.code} : blocage géographique ou réseau probable)"
        else:
            res["etat"] = f"refusé (HTTP {e.code})"
        return res
    except (urllib.error.URLError, OSError) as e:  # DNS, pare-feu, proxy, délai dépassé...
        res["etat"] = f"inaccessible ({str(getattr(e, 'reason', e))[:90]})"
        return res
    latence = round((time.time() - debut) * 1000)
    res.update(ok=True, etat=f"OK, {latence} ms")
    return res


def verifier_reseau(r: Rapport) -> list[dict]:
    r.titre("Accès à internet")
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        resultats = list(pool.map(lambda s: _interroger(*s), SOURCES))
    for res in resultats:
        r.ecrire(f"{'[OK]' if res['ok'] else '[--]'} {res['nom']:<10} {res['etat']} - {res['role']}")
    accessibles = [res for res in resultats if res["ok"]]
    noms = ", ".join(res["nom"] for res in accessibles) or "aucun"
    conseil = "" if accessibles else " -> vérifie la connexion internet, le pare-feu ou le VPN"
    r.bilan(bool(accessibles), f"Accès internet {len(accessibles)}/{len(resultats)} : {noms}{conseil}")
    return resultats


# --------------------------------------------------------------------------- #
# Terminal MetaTrader 5
# --------------------------------------------------------------------------- #
def verifier_mt5(r: Rapport, modules: dict) -> None:
    r.titre("Terminal MetaTrader 5")
    mt5 = modules.get("MetaTrader5")
    if mt5 is None:
        if EST_WINDOWS:
            r.ecrire("[!!] module MetaTrader5 absent : section sautée (relance INSTALLER.bat)")
        else:
            r.ecrire("[--] module MetaTrader5 absent (normal hors Windows) : section sautée")
        return  # déjà compté dans le bilan des librairies
    try:
        ok = bool(mt5.initialize())
    except Exception as e:
        ok = False
        r.ecrire(f"[!!] initialize() a planté : {type(e).__name__} : {e}")
    try:
        if not ok:
            r.ecrire("[!!] Impossible de se connecter au terminal MetaTrader 5.")
            r.ecrire("     -> ouvre MetaTrader 5 et connecte-toi au compte démo, puis relance VERIFIER.bat")
            r.ecrire(f"     erreur MT5 : {erreur_mt5(mt5)}")
            r.bilan(False, "MetaTrader 5 : terminal injoignable -> ouvre MT5 et connecte-toi au compte démo")
            return
        _verifier_terminal(r, mt5)
        _verifier_compte(r, mt5)
        _verifier_symbole_or(r, mt5)
    except Exception as e:  # le module ne doit jamais faire planter la vérification
        r.ecrire(f"[!!] Erreur inattendue avec MetaTrader 5 : {type(e).__name__} : {e}")
        r.bilan(False, f"MetaTrader 5 : erreur inattendue ({type(e).__name__})")
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def _verifier_terminal(r: Rapport, mt5) -> None:
    info = mt5.terminal_info()
    if info is None:
        r.ecrire(f"[!!] terminal_info() sans réponse ({erreur_mt5(mt5)})")
        r.bilan(False, "MetaTrader 5 : informations du terminal indisponibles")
        return
    connecte = bool(getattr(info, "connected", False))
    algo = bool(getattr(info, "trade_allowed", False))
    build = getattr(info, "build", "?")
    r.ecrire(f"[OK] terminal joint (build {build}, société {getattr(info, 'company', '?')})")
    r.ecrire(f"{_marque(connecte)} connexion au serveur du broker : {'oui' if connecte else 'NON'}")
    if not connecte:
        r.ecrire("     -> dans MetaTrader 5 : Fichier > Connexion au compte de trading (File > Login to Trade Account)")
    r.bilan(connecte, "MetaTrader 5 : connecté au serveur" if connecte
            else "MetaTrader 5 : pas connecté au serveur du broker -> reconnecte-toi au compte démo")
    r.ecrire(f"{_marque(algo)} bouton Algo Trading : {'activé' if algo else 'DÉSACTIVÉ'}")
    if not algo:
        r.ecrire("     -> clique sur le bouton « Algo Trading » de la barre d'outils (il doit devenir vert)")
    r.bilan(algo, "MetaTrader 5 : Algo Trading activé" if algo
            else "MetaTrader 5 : bouton Algo Trading désactivé -> clique dessus dans la barre d'outils")
    maxbars = getattr(info, "maxbars", None)
    if maxbars is not None:
        r.ecrire(f"     nombre max de barres dans les graphiques : {maxbars}")


def _verifier_compte(r: Rapport, mt5) -> None:
    compte = mt5.account_info()
    if compte is None:
        r.ecrire(f"[!!] account_info() sans réponse ({erreur_mt5(mt5)})")
        r.ecrire("     -> connecte-toi au compte démo dans MetaTrader 5")
        r.bilan(False, "MetaTrader 5 : aucun compte connecté -> connecte-toi au compte démo")
        return
    # Volontairement : ni login, ni nom, ni mot de passe.
    _, mode = texte_trade_mode(getattr(compte, "trade_mode", None))
    _, marge = texte_margin_mode(getattr(compte, "margin_mode", None))
    devise = str(getattr(compte, "currency", "?"))
    reel = est_compte_reel(mt5, compte)
    r.ecrire(f"{_marque(not reel)} type de compte : {mode}")
    if reel:
        r.ecrire("     -> ATTENTION : compte RÉEL. La phase actuelle se fait UNIQUEMENT sur compte démo.")
        r.ecrire("        Connecte-toi au compte démo (Fichier > Connexion au compte de trading).")
    r.bilan(not reel, f"Compte {mode}" if not reel
            else "Compte RÉEL détecté -> la phase actuelle se fait uniquement en démo")
    usd = devise.upper() == "USD"
    r.ecrire(f"{_marque(usd)} devise du compte : {devise}")
    if not usd:
        r.bilan(False, f"Devise du compte {devise} -> le projet suppose un compte en USD")
    r.ecrire(f"     levier : 1:{getattr(compte, 'leverage', '?')}")
    r.ecrire(f"     mode de compte : {marge}" + ("" if marge == "hedging" else " (hedging conseillé, netting accepté)"))
    r.ecrire(f"     broker : {getattr(compte, 'company', '?')} | serveur : {getattr(compte, 'server', '?')}")


def _verifier_symbole_or(r: Rapport, mt5) -> None:
    nom, candidats, explication = choisir_symbole_or(mt5)
    if nom is None:
        r.ecrire(f"[!!] {explication}")
        r.bilan(False, "Symbole de l'or introuvable -> ajoute XAUUSD dans l'Observation du marché")
        return
    r.ecrire(f"[OK] {explication}")
    info = mt5.symbol_info(nom)
    if info is None:
        r.ecrire(f"[!!] symbol_info({nom}) sans réponse ({erreur_mt5(mt5)})")
        r.bilan(False, f"Symbole {nom} : caractéristiques indisponibles")
        return
    point = getattr(info, "point", None)
    spread = getattr(info, "spread", None)
    try:
        spread_txt = f"{spread} points = {float(spread) * float(point):.2f} $"
    except (TypeError, ValueError):
        spread_txt = f"{spread} points"
    r.ecrire(f"     décimales : {getattr(info, 'digits', '?')} | point : {point}")
    r.ecrire(f"     taille du contrat : {getattr(info, 'trade_contract_size', '?')} onces par lot")
    r.ecrire(f"     volume min : {getattr(info, 'volume_min', '?')} lot | pas : {getattr(info, 'volume_step', '?')} lot")
    r.ecrire(f"     spread actuel : {spread_txt}")
    r.bilan(True, f"Symbole de l'or : {nom}")


# --------------------------------------------------------------------------- #
def enregistrer(r: Rapport, maintenant: dt.datetime) -> Path:
    DOSSIER_LOGS.mkdir(parents=True, exist_ok=True)
    systeme = platform.system().lower() or "inconnu"
    chemin = DOSSIER_LOGS / f"check_env_{systeme}_{maintenant:%Y%m%d-%H%M%S}.txt"
    chemin.write_text("\n".join(r.lignes) + "\n", encoding="utf-8")
    return chemin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vérification de l'environnement SentiTrade")
    parser.add_argument("--no-network", action="store_true", help="sauter les tests réseau")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")  # console Windows : jamais de plantage d'affichage
    except Exception:
        pass

    r = Rapport()
    maintenant = dt.datetime.now(dt.timezone.utc)
    r.ecrire("SentiTrade - vérification de l'environnement")
    r.ecrire(f"Date : {maintenant:%Y-%m-%d %H:%M:%S} UTC | machine : {socket.gethostname()}")

    verifier_python(r)
    modules = verifier_librairies(r)
    verifier_calculs(r, modules)
    verifier_fuseaux(r, modules)
    if args.no_network:
        r.titre("Réseau")
        r.ecrire("[--] tests réseau désactivés (--no-network)")
    else:
        verifier_reseau(r)
    verifier_mt5(r, modules)

    r.titre("RÉSUMÉ")
    for ok, texte in r.bilans:
        r.ecrire(f"{_marque(ok)} {texte}")
    problemes = sum(1 for ok, _ in r.bilans if not ok)
    r.ecrire()
    if problemes == 0:
        r.ecrire("=> TOUT EST OK")
    else:
        r.ecrire(f"=> {problemes} point(s) à regarder. Claude peut lire ce rapport et t'expliquer quoi faire.")

    try:
        print(f"\nRapport enregistré : {enregistrer(r, maintenant)}")
    except OSError as e:
        print(f"\n[!!] Impossible d'enregistrer le rapport : {e}")
    return 0 if problemes == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
