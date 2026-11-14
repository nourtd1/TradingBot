"""Configuration de SentiTrade — contrat partagé par tous les modules.

Le fichier config/config.json a quatre sections (symbole, strategie, risque,
execution) dont les clés portent exactement les noms des champs ci-dessous.
Une clé inconnue est une erreur : une faute de frappe ne doit jamais être
ignorée en silence.

Unités : tous les prix et distances sont en unités de prix (dollars pour
XAUUSD), jamais en points. La conversion points <-> prix se fait uniquement
avec SymboleSpec.point, à la frontière avec MT5.

Heures : heure du SERVEUR du broker (celle des bougies MT5), format "HH:MM".
Aucun secret ici : les identifiants MT5 vivent dans %USERPROFILE%\\.tradingbot\\.env.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CHEMIN_CONFIG = RACINE / "config" / "config.json"
CHEMIN_SYMBOLE = RACINE / "data" / "mt5" / "symbol_info.json"


@dataclass(frozen=True)
class StrategieConfig:
    ema_periode: int = 50                 # EMA de tendance sur H1
    pente_ema_barres: int = 3             # haussière si EMA[t] > EMA[t-3] (bougies H1 clôturées)
    debut_session: str = "09:00"          # première entrée possible
    derniere_entree: str = "21:00"        # dernière entrée possible (CDC : 22h, mais clôture forcée 21h55)
    cloture_forcee: str = "21:55"         # tout est fermé à cette heure
    jours_autorises: tuple = (0, 1, 2, 3, 4)  # lundi=0 ... vendredi=4
    fvg_ecart_min: float = 0.0            # taille minimale du vide (0 = règle du CDC)
    mode_entree: str = "bord"             # "bord" = plus haut de la bougie 1 (CDC) ; "milieu" = variante
    validite_setup_barres: int = 8        # durée de vie d'un setup en bougies M15
    sl_marge_fixe: float = 0.0            # marge ajoutée au spread derrière la structure
    sl_plafond: float = 5.0               # distance de SL max ; au-delà le setup est rejeté
    tp1_r: float = 1.0                    # TP1 à 1R
    tp1_fraction: float = 0.5             # part fermée à TP1
    spread_max: float = 0.30              # spread max au moment de l'entrée (30 points à 2 décimales)
    adr_periode: int = 14
    adr_reference: int = 100
    adr_ratio_min: float = 0.5
    adr_ratio_max: float = 2.0

    def heure(self, nom: str) -> time:
        """Convertit un champ "HH:MM" (debut_session, derniere_entree, cloture_forcee) en datetime.time."""
        h, m = getattr(self, nom).split(":")
        return time(int(h), int(m))


@dataclass(frozen=True)
class RisqueConfig:
    risque_par_trade_pct: float = 1.0     # % de la balance perdu si le SL est touché
    perte_jour_max_pct: float = 3.0       # au-delà : plus d'entrée jusqu'au lendemain (heure serveur)
    drawdown_max_pct: float = 15.0        # au-delà : arrêt complet, redémarrage manuel
    levier_effectif_max: float = 10.0     # valeur notionnelle / balance
    positions_max: int = 1
    exiger_lot_divisible: bool = True     # refuser si le lot ne peut pas être coupé en deux à TP1


@dataclass(frozen=True)
class ExecutionConfig:
    glissement_entree: float = 0.05       # glissement défavorable à l'entrée (prix)
    glissement_stop: float = 0.10         # glissement défavorable sur un stop touché (prix)
    commission_par_lot: float = 0.0       # aller-retour, en devise du compte


@dataclass(frozen=True)
class SymboleSpec:
    """Caractéristiques du symbole chez le broker (data/mt5/symbol_info.json)."""
    nom: str = "XAUUSD"
    digits: int = 2
    point: float = 0.01
    taille_contrat: float = 100.0         # onces par lot
    volume_min: float = 0.01
    volume_pas: float = 0.01
    volume_max: float = 100.0
    stops_level_points: int = 0           # distance minimale SL/prix imposée par le broker

    def points_vers_prix(self, points: float) -> float:
        return points * self.point

    @classmethod
    def depuis_json(cls, chemin: Path | str = CHEMIN_SYMBOLE) -> "SymboleSpec":
        """Lit symbol_info.json écrit par scripts/exporter_donnees_mt5.py (noms d'attributs MT5)."""
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
        return cls(
            nom=d["name"],
            digits=int(d["digits"]),
            point=float(d["point"]),
            taille_contrat=float(d["trade_contract_size"]),
            volume_min=float(d["volume_min"]),
            volume_pas=float(d["volume_step"]),
            volume_max=float(d["volume_max"]),
            stops_level_points=int(d.get("trade_stops_level", 0)),
        )


@dataclass(frozen=True)
class Config:
    symbole: str = "XAUUSD"
    strategie: StrategieConfig = field(default_factory=StrategieConfig)
    risque: RisqueConfig = field(default_factory=RisqueConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    def avec(self, **changements) -> "Config":
        """Copie modifiée pour les tests de sensibilité : avec(sl_plafond=8.0, ...).

        Chaque nom est cherché dans strategie, risque puis execution.
        """
        sections = {"strategie": self.strategie, "risque": self.risque, "execution": self.execution}
        par_section: dict = {k: {} for k in sections}
        for nom, valeur in changements.items():
            cible = next((s for s, obj in sections.items()
                          if nom in {f.name for f in dataclasses.fields(obj)}), None)
            if cible is None:
                raise KeyError(f"paramètre inconnu : {nom}")
            par_section[cible][nom] = valeur
        nouvelle = dataclasses.replace(
            self, **{s: dataclasses.replace(sections[s], **v) for s, v in par_section.items() if v})
        valider(nouvelle)
        return nouvelle


def _construire(classe, donnees: dict, section: str):
    connus = {f.name for f in dataclasses.fields(classe)}
    inconnus = set(donnees) - connus
    if inconnus:
        raise ValueError(f"config.json, section '{section}' : clé(s) inconnue(s) {sorted(inconnus)}")
    if "jours_autorises" in donnees:
        donnees = {**donnees, "jours_autorises": tuple(donnees["jours_autorises"])}
    return classe(**donnees)


def valider(cfg: Config) -> None:
    """Refuse toute configuration hors des garde-fous (docs/GARDE_FOUS.md)."""
    s, r = cfg.strategie, cfg.risque
    erreurs = []
    if not 0 < r.risque_par_trade_pct <= 2.0:
        erreurs.append("risque_par_trade_pct doit être dans ]0, 2]")
    if not 0 < r.perte_jour_max_pct <= 10.0:
        erreurs.append("perte_jour_max_pct doit être dans ]0, 10]")
    if not 0 < r.drawdown_max_pct <= 30.0:
        erreurs.append("drawdown_max_pct doit être dans ]0, 30]")
    if not 0 < r.levier_effectif_max <= 30.0:
        erreurs.append("levier_effectif_max doit être dans ]0, 30]")
    if r.positions_max != 1:
        erreurs.append("positions_max doit valoir 1 (cahier des charges)")
    if s.mode_entree not in ("bord", "milieu"):
        erreurs.append("mode_entree doit être 'bord' ou 'milieu'")
    if not 0 < s.tp1_fraction < 1:
        erreurs.append("tp1_fraction doit être dans ]0, 1[")
    for nom in ("sl_plafond", "spread_max", "tp1_r"):
        if getattr(s, nom) <= 0:
            erreurs.append(f"{nom} doit être > 0")
    for nom in ("ema_periode", "pente_ema_barres", "validite_setup_barres", "adr_periode", "adr_reference"):
        if int(getattr(s, nom)) < 1:
            erreurs.append(f"{nom} doit être >= 1")
    if not 0 < s.adr_ratio_min < 1 < s.adr_ratio_max:
        erreurs.append("il faut 0 < adr_ratio_min < 1 < adr_ratio_max")
    if not set(s.jours_autorises) <= set(range(7)):
        erreurs.append("jours_autorises : valeurs de 0 (lundi) à 6 (dimanche)")
    try:
        if not s.heure("debut_session") < s.heure("derniere_entree") < s.heure("cloture_forcee"):
            erreurs.append("il faut debut_session < derniere_entree < cloture_forcee")
    except (ValueError, AttributeError):
        erreurs.append("heures au format HH:MM attendues")
    if erreurs:
        raise ValueError("Configuration refusée :\n - " + "\n - ".join(erreurs))


def charger_config(chemin: Path | str = CHEMIN_CONFIG) -> Config:
    brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    inconnues = set(brut) - {"symbole", "strategie", "risque", "execution", "_commentaire"}
    if inconnues:
        raise ValueError(f"config.json : section(s) inconnue(s) {sorted(inconnues)}")
    cfg = Config(
        symbole=brut.get("symbole", "XAUUSD"),
        strategie=_construire(StrategieConfig, brut.get("strategie", {}), "strategie"),
        risque=_construire(RisqueConfig, brut.get("risque", {}), "risque"),
        execution=_construire(ExecutionConfig, brut.get("execution", {}), "execution"),
    )
    valider(cfg)
    return cfg
