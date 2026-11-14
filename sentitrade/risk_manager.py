"""Gestion du risque de SentiTrade : taille de position, découpage à TP1, garde-fous du compte.

Contrat : docs/SPEC_TECHNIQUE.md, section 4. Règles mères : docs/GARDE_FOUS.md, section 2.

Pourquoi ce module est le plus critique du projet : l'or est traité en CFD, donc
à levier. Une erreur de taille (un facteur 10, un arrondi vers le haut, une
division par un flottant mal représenté) peut faire perdre en un trade ce que la
stratégie gagne en un an. Les principes appliqués partout ci-dessous :

1. **Dans le doute, on ne trade pas.** Une entrée invalide (zéro, négatif, NaN,
   infini, type inattendu) ne lève jamais d'exception dans le calcul de taille :
   elle produit un refus (``accepte=False``) avec une raison explicite. Une
   exception au milieu de la boucle du bot pourrait laisser un état incohérent ;
   un refus propre est journalisé et la boucle continue sans risque.
2. **On n'arrondit jamais une taille vers le haut.** Toutes les opérations de
   taille sont faites en ``decimal.Decimal`` construit à partir de ``repr`` des
   flottants (la valeur décimale que l'humain a écrite : 0.07 vaut 0.07 et non
   0.07000000000000000666...), avec un contexte qui arrondit vers le bas. En
   flottant pur, ``0.29 / 0.01`` vaut 28.999999999999996 et ``0.06 / 0.01`` vaut
   5.999999999999999 : on perdrait un pas à tort, et dans d'autres cas on en
   gagnerait un à tort.
3. **Défense en profondeur.** Même si ``config.valider`` a déjà vérifié les
   paramètres, ce module revérifie les bornes dont dépend la taille : une
   configuration fabriquée à la main (``dataclasses.replace``) ne doit pas
   pouvoir contourner les garde-fous.

Dépendances : bibliothèque standard uniquement (le module tourne aussi dans le
bot réel, sous Windows / Python 3.12).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, InvalidOperation, localcontext
from typing import Any, List, Optional, Tuple

# Bornes de défense en profondeur, alignées sur config.valider (sentitrade/config.py).
# Les modifier ici ET là-bas, et uniquement avec la validation de l'utilisateur.
RISQUE_PAR_TRADE_MAX_PCT = 2.0
LEVIER_EFFECTIF_MAX_ABSOLU = 30.0

# Tolérance relative de la garantie testée (SPEC §4.6) : lots × perte_par_lot ≤ risque_montant × (1 + 1e-9).
TOLERANCE_RELATIVE = 1e-9

# Précision des calculs décimaux (largement supérieure aux 17 chiffres d'un flottant).
_PRECISION = 50

# Raisons possibles (chaînes courtes, stables : le rapport les compte).
RAISON_OK = "ok"
RAISON_PLAFOND_LEVIER = "plafond_levier"          # accepté, mais le levier a limité la taille
RAISON_PLAFOND_VOLUME_MAX = "plafond_volume_max"  # accepté, mais volume_max a limité la taille
RAISON_LOT_INFERIEUR_MINIMUM = "lot_inferieur_minimum"
RAISON_LOT_NON_DIVISIBLE = "lot_non_divisible"
PREFIXE_ENTREE_INVALIDE = "entree_invalide:"      # suivi du nom du champ fautif

# Raisons de GardeRisque.peut_ouvrir.
RAISON_ARRET_DEFINITIF = "arret_definitif"
RAISON_PERTE_JOUR_MAX = "perte_jour_max"

# Types de déclenchements enregistrés dans GardeRisque.historique.
DECL_PERTE_JOUR = "perte_jour"
DECL_DRAWDOWN_MAX = "drawdown_max"
DECL_REINITIALISATION = "reinitialisation"
DECL_EQUITY_INVALIDE = "equity_invalide"
DECL_BALANCE_INVALIDE = "balance_invalide"


# ---------------------------------------------------------------------------
# Outils numériques
# ---------------------------------------------------------------------------

def _nombre_positif(valeur: Any) -> Optional[Decimal]:
    """Convertit en Decimal un nombre fini strictement positif, sinon renvoie None.

    Pourquoi refuser les booléens et les chaînes : ``True`` vaut 1 en Python et
    ``float("3000")`` réussit ; ce sont presque toujours des erreurs de câblage
    qu'il vaut mieux refuser que d'interpréter.
    """
    if isinstance(valeur, (bool, str, bytes)):
        return None
    try:
        f = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(f) or f <= 0.0:
        return None
    try:
        # repr donne la plus courte écriture décimale qui redonne exactement ce flottant.
        return Decimal(repr(f))
    except (InvalidOperation, ValueError):
        return None


def _plancher_au_pas(valeur: Decimal, pas: Decimal) -> Tuple[int, Decimal]:
    """Nombre entier de pas contenus dans ``valeur`` (arrondi vers le bas) et le volume correspondant."""
    n = int((valeur / pas).to_integral_value(rounding=ROUND_FLOOR))
    if n < 0:
        n = 0
    return n, pas * n


def _vers_float(d: Decimal) -> float:
    """Decimal -> float (le flottant le plus proche ; 0.07 redonne exactement le flottant 0.07)."""
    return float(d)


# ---------------------------------------------------------------------------
# Taille de position
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultatTaille:
    """Résultat du calcul de taille (gelé : une décision ne se modifie pas après coup).

    - ``accepte`` : True si un ordre de ``lots`` peut être envoyé.
    - ``lots`` : volume retenu, multiple exact de ``volume_pas`` (0.0 si refus).
    - ``risque_montant`` : **budget** de risque autorisé, ``balance × risque_par_trade_pct / 100``
      (en devise du compte). C'est la borne de la garantie
      ``lots × perte_par_lot ≤ risque_montant × (1 + 1e-9)``. 0.0 si les entrées sont invalides.
    - ``risque_pct`` : risque **réellement engagé** par la position retenue, en % de la balance
      (``lots × perte_par_lot / balance × 100``). Toujours ≤ ``risque_par_trade_pct`` ; il est plus
      petit quand l'arrondi, le levier ou ``volume_max`` ont réduit la taille. 0.0 si refus.
    - ``levier_effectif`` : ``lots × notionnel_par_lot / balance``. 0.0 si refus.
    - ``raison`` : ``ok``, ``plafond_levier``, ``plafond_volume_max`` (acceptés),
      ``lot_inferieur_minimum``, ``lot_non_divisible``, ``entree_invalide:<champ>`` (refus).
    """
    accepte: bool
    lots: float
    risque_montant: float
    risque_pct: float
    levier_effectif: float
    raison: str


def _refus(raison: str, risque_montant: float = 0.0) -> ResultatTaille:
    return ResultatTaille(accepte=False, lots=0.0, risque_montant=risque_montant,
                          risque_pct=0.0, levier_effectif=0.0, raison=raison)


def calculer_taille_lot(balance: float, cfg_risque: Any, perte_par_lot: float,
                        notionnel_par_lot: float, spec: Any) -> ResultatTaille:
    """Calcule le volume (en lots) d'un trade selon SPEC §4. Ne lève jamais d'exception.

    Paramètres :
    - ``balance`` : balance du compte (devise du compte). C'est la base du risque, comme le
      demande GARDE_FOUS §2 (« 1 % du capital »).
    - ``cfg_risque`` : ``RisqueConfig`` (``risque_par_trade_pct``, ``levier_effectif_max``,
      ``exiger_lot_divisible``).
    - ``perte_par_lot`` : perte pour 1 lot si le SL est touché, **commission incluse**
      (``distance_sl × taille_contrat + commission_par_lot`` dans le backtest ;
      ``mt5.order_calc_profit`` + commission dans le bot). Pourquoi inclure la commission :
      sinon un trade stoppé coûte plus que le 1 % promis.
    - ``notionnel_par_lot`` : valeur d'un lot, ``prix × taille_contrat``.
    - ``spec`` : ``SymboleSpec`` (``volume_min``, ``volume_pas``, ``volume_max``).

    Étapes et leur raison d'être :

    1. Validation : tout champ ≤ 0, NaN, infini ou d'un type inattendu donne
       ``entree_invalide:<champ>``. Un NaN qui traverserait le calcul pourrait produire
       n'importe quoi ; un refus est toujours sûr. ``risque_par_trade_pct`` > 2 et
       ``levier_effectif_max`` > 30 sont refusés aussi (mêmes bornes que ``config.valider``),
       ainsi que ``volume_max < volume_min`` (spécification du symbole incohérente).
    2. Lot brut = ``min(budget / perte_par_lot, levier_max × balance / notionnel_par_lot, volume_max)``.
       Le premier terme borne la perte si le SL est touché ; le second borne l'exposition
       (un SL très serré donnerait sinon une position énorme, exposée au gap et au
       glissement, que le SL ne protège plus vraiment) ; le troisième respecte le broker.
    3. Arrondi **vers le bas** au ``volume_pas``, en décimal exact. On n'arrondit jamais vers
       le haut : un pas de trop, c'est un risque supérieur au budget.
    4. Refus ``lot_inferieur_minimum`` si le lot arrondi est sous ``volume_min``. On ne remonte
       jamais au minimum du broker : si le minimum dépasse le budget, le trade n'a pas lieu.
       Refus ``lot_non_divisible`` si ``exiger_lot_divisible`` et lot < 2 × ``volume_min`` :
       la gestion prévoit de fermer une partie à TP1 et de laisser courir le reste ; une
       position insécable changerait le profil du trade testé en backtest.
    5. Contrôle final redondant (en décimal puis en flottant) des deux garanties ; s'il
       échouait (cela ne doit pas arriver), on retire un pas plutôt que de dépasser.
    """
    try:
        return _calculer_taille_lot(balance, cfg_risque, perte_par_lot, notionnel_par_lot, spec)
    except Exception as exc:  # filet de sécurité : jamais d'exception, refus explicite
        return _refus(PREFIXE_ENTREE_INVALIDE + "exception_" + type(exc).__name__)


def _calculer_taille_lot(balance, cfg_risque, perte_par_lot, notionnel_par_lot, spec) -> ResultatTaille:
    manquant = object()

    def lire(objet, nom):
        return getattr(objet, nom, manquant) if objet is not None else manquant

    champs = [
        ("balance", balance),
        ("perte_par_lot", perte_par_lot),
        ("notionnel_par_lot", notionnel_par_lot),
        ("risque_par_trade_pct", lire(cfg_risque, "risque_par_trade_pct")),
        ("levier_effectif_max", lire(cfg_risque, "levier_effectif_max")),
        ("volume_min", lire(spec, "volume_min")),
        ("volume_pas", lire(spec, "volume_pas")),
        ("volume_max", lire(spec, "volume_max")),
    ]
    v = {}
    for nom, brut in champs:
        d = None if brut is manquant else _nombre_positif(brut)
        if d is None:
            return _refus(PREFIXE_ENTREE_INVALIDE + nom)
        v[nom] = d

    if v["risque_par_trade_pct"] > Decimal(repr(RISQUE_PAR_TRADE_MAX_PCT)):
        return _refus(PREFIXE_ENTREE_INVALIDE + "risque_par_trade_pct")
    if v["levier_effectif_max"] > Decimal(repr(LEVIER_EFFECTIF_MAX_ABSOLU)):
        return _refus(PREFIXE_ENTREE_INVALIDE + "levier_effectif_max")
    if v["volume_max"] < v["volume_min"]:
        return _refus(PREFIXE_ENTREE_INVALIDE + "volume_max")

    # Absent ou illisible => True : l'option la plus prudente (refuser les lots insécables).
    exiger = lire(cfg_risque, "exiger_lot_divisible")
    exiger = True if exiger is manquant else bool(exiger)

    bal, pct = v["balance"], v["risque_par_trade_pct"]
    perte, notionnel = v["perte_par_lot"], v["notionnel_par_lot"]
    levier_max = v["levier_effectif_max"]
    vmin, pas, vmax = v["volume_min"], v["volume_pas"], v["volume_max"]

    with localcontext() as ctx:
        ctx.prec = _PRECISION
        ctx.rounding = ROUND_FLOOR  # toutes les grandeurs sont > 0 : chaque arrondi réduit
        budget = bal * pct / Decimal(100)
        lot_risque = budget / perte
        expo_max = levier_max * bal
        lot_levier = expo_max / notionnel
        lot_brut = min(lot_risque, lot_levier, vmax)

        if lot_brut == lot_risque:
            raison_ok = RAISON_OK
        elif lot_brut == lot_levier:
            raison_ok = RAISON_PLAFOND_LEVIER
        else:
            raison_ok = RAISON_PLAFOND_VOLUME_MAX

        n, lots = _plancher_au_pas(lot_brut, pas)

        # Contrôle redondant en décimal exact : jamais au-dessus du budget, du levier, du max.
        while n > 0 and (lots * perte > budget or lots * notionnel > expo_max or lots > vmax):
            n -= 1
            lots = pas * n

        budget_f = _vers_float(budget)
        lots_f = _vers_float(lots)
        bal_f = _vers_float(bal)
        perte_f = _vers_float(perte)
        notionnel_f = _vers_float(notionnel)
        levier_f = _vers_float(levier_max)
        # Contrôle redondant en flottant (ce que verra l'appelant), avec la tolérance du contrat.
        while n > 0 and (lots_f * perte_f > budget_f * (1 + TOLERANCE_RELATIVE)
                         or lots_f * notionnel_f > levier_f * bal_f * (1 + TOLERANCE_RELATIVE)):
            n -= 1
            lots = pas * n
            lots_f = _vers_float(lots)

        if lots < vmin:
            return _refus(RAISON_LOT_INFERIEUR_MINIMUM, budget_f)
        if exiger and lots < vmin * 2:
            return _refus(RAISON_LOT_NON_DIVISIBLE, budget_f)

        risque_pct = _vers_float(lots * perte * Decimal(100) / bal)
        levier = _vers_float(lots * notionnel / bal)

    return ResultatTaille(accepte=True, lots=lots_f, risque_montant=budget_f,
                          risque_pct=risque_pct, levier_effectif=levier, raison=raison_ok)


# ---------------------------------------------------------------------------
# Découpage à TP1
# ---------------------------------------------------------------------------

def decouper_volume(lots: float, fraction: float, spec: Any) -> Tuple[float, float]:
    """Partage une position en ``(a_fermer, restant)`` pour la sortie partielle à TP1 (SPEC §4).

    ``a_fermer`` = ``lots × fraction`` arrondi **vers le bas** au ``volume_pas`` ; ``restant`` =
    ``lots - a_fermer``. Les deux parts doivent être ≥ ``volume_min`` (sinon le broker refuse
    l'ordre ou laisse un reliquat impossible à gérer) ; si c'est impossible, on renvoie
    ``(0.0, lots)`` : on ne ferme rien et la position continue avec son SL d'origine.

    Pourquoi arrondir la part fermée vers le bas plutôt que vers le haut : les deux sont
    neutres pour le risque (le SL du reste passe au breakeven), mais on garde la règle
    unique du module (jamais vers le haut) et le comportement est identique dans le
    backtest et le bot. Exemples avec un pas de 0.01 et ``fraction = 0.5`` :
    0.06 → (0.03, 0.03) ; 0.05 → (0.02, 0.03) ; 0.01 → (0.0, 0.01).

    Entrées invalides (lots ou fraction non finis, lots ≤ 0, fraction hors ]0, 1[, spec
    illisible) : aucune exception, on renvoie ``(0.0, lots)`` (ou ``(0.0, 0.0)`` si ``lots``
    n'est même pas un nombre) ; « ne rien fermer » est l'action qui n'envoie aucun ordre.
    """
    try:
        lots_f = float(lots)
    except Exception:
        return (0.0, 0.0)
    if isinstance(lots, bool) or not math.isfinite(lots_f):
        return (0.0, 0.0)
    try:
        d_lots = _nombre_positif(lots_f)
        d_frac = _nombre_positif(fraction)
        vmin = _nombre_positif(getattr(spec, "volume_min", None))
        pas = _nombre_positif(getattr(spec, "volume_pas", None))
        if d_lots is None or d_frac is None or vmin is None or pas is None or d_frac >= 1:
            return (0.0, lots_f)
        with localcontext() as ctx:
            ctx.prec = _PRECISION
            ctx.rounding = ROUND_FLOOR
            _, a_fermer = _plancher_au_pas(d_lots * d_frac, pas)
            restant = d_lots - a_fermer
            if a_fermer < vmin or restant < vmin:
                return (0.0, lots_f)
            return (_vers_float(a_fermer), _vers_float(restant))
    except Exception:
        return (0.0, lots_f)


# ---------------------------------------------------------------------------
# Garde-fous du compte
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Declenchement:
    """Une entrée de l'historique de GardeRisque, pour le rapport et le journal.

    ``type`` parmi ``perte_jour`` (valeur = perte du jour en %), ``drawdown_max`` (valeur =
    drawdown en % depuis le pic), ``reinitialisation`` (valeur = nouveau pic),
    ``equity_invalide`` / ``balance_invalide`` (valeur = la valeur reçue, convertie en
    float si possible, sinon NaN).
    """
    instant: Any
    type: str
    valeur: float


def _float_ou_nan(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


class GardeRisque:
    """Garde-fous du compte : perte journalière maximale et drawdown maximal (GARDE_FOUS §2).

    - **Perte du jour.** Si ``(balance_debut_jour - equity) / balance_debut_jour ≥
      perte_jour_max_pct / 100``, plus aucune nouvelle position jusqu'au prochain appel de
      ``nouvelle_journee`` avec une date différente. Pourquoi bloquer pour toute la journée
      même si l'equity remonte : une série de pertes signale souvent un marché que la
      stratégie lit mal ce jour-là ; on n'essaie pas de « se refaire ». La condition est
      vérifiée à chaque observation d'equity (``mettre_a_jour`` et ``peut_ouvrir``) : un
      creux touché puis effacé entre deux signaux déclenche quand même le blocage.
    - **Drawdown maximal.** Le pic d'equity observé (initialement la balance initiale) est
      suivi en continu. Si ``(pic - equity) / pic ≥ drawdown_max_pct / 100``, **arrêt
      définitif** : il survit à ``nouvelle_journee`` et ne se lève que par
      ``reinitialiser_arret()``, c'est-à-dire par une décision humaine. Pourquoi : un
      drawdown de 15 % dit que la stratégie ne se comporte plus comme en test ; le bot ne
      doit pas décider seul de continuer.
    - Sans ``nouvelle_journee`` initiale, la référence du jour est la balance initiale.

    Les comparaisons de seuil sont faites en décimal exact (à partir de ``repr`` des
    flottants) pour qu'une perte de exactement 3 % déclenche bien le blocage (« ≥ »).

    Choix prudents (non écrits dans la spec, signalés) :
    - ``nouvelle_journee`` appelée deux fois avec la même date (ou une date antérieure) ne
      remet pas la référence à zéro : sinon un redémarrage en cours de journée effacerait
      le blocage journalier.
    - ``nouvelle_journee`` observe aussi la balance pour le drawdown (le pic suit
      ``max(pic, balance)``) : une balance est une valeur réalisée, ignorer sa baisse serait
      moins prudent.
    - Une equity invalide (NaN, ≤ 0, infini) ne met rien à jour, est journalisée, et
      ``peut_ouvrir`` refuse. Une balance de début de jour invalide bloque la journée.
    - L'état vit en mémoire : le bot réel devra le persister (arrêt définitif, pic,
      référence du jour), sinon un simple redémarrage du programme lèverait l'arrêt.
    """

    def __init__(self, cfg_risque: Any, balance_initiale: float) -> None:
        """Lève ``ValueError`` si la configuration ou la balance initiale est invalide.

        Ici une exception est voulue : c'est le démarrage, avant tout trade ; un bot qui ne
        sait pas mesurer ses pertes ne doit pas démarrer.
        """
        perte_jour = _nombre_positif(getattr(cfg_risque, "perte_jour_max_pct", None))
        dd_max = _nombre_positif(getattr(cfg_risque, "drawdown_max_pct", None))
        bal = _nombre_positif(balance_initiale)
        if perte_jour is None or perte_jour >= 100:
            raise ValueError("GardeRisque : perte_jour_max_pct doit être un nombre dans ]0, 100[")
        if dd_max is None or dd_max >= 100:
            raise ValueError("GardeRisque : drawdown_max_pct doit être un nombre dans ]0, 100[")
        if bal is None:
            raise ValueError("GardeRisque : balance_initiale doit être un nombre fini > 0")
        self._cfg = cfg_risque
        self._seuil_jour = perte_jour / Decimal(100)
        self._seuil_dd = dd_max / Decimal(100)
        self.balance_initiale: float = float(balance_initiale)
        self._pic: Decimal = bal
        self._ref_jour: Decimal = bal
        self._date_jour: Any = None
        self._dernier_equity: Decimal = bal
        self._bloque_jour: bool = False
        self.arret_definitif: bool = False
        self.raison_arret: str = ""
        self._historique: List[Declenchement] = []

    # --- consultation -------------------------------------------------------

    @property
    def historique(self) -> Tuple[Declenchement, ...]:
        """Déclenchements dans l'ordre (copie non modifiable)."""
        return tuple(self._historique)

    @property
    def pic_equity(self) -> float:
        return float(self._pic)

    @property
    def balance_debut_jour(self) -> float:
        return float(self._ref_jour)

    @property
    def date_jour(self) -> Any:
        return self._date_jour

    @property
    def bloque_jour(self) -> bool:
        """True si la perte journalière maximale a été atteinte aujourd'hui."""
        return self._bloque_jour

    # --- cycle de vie -------------------------------------------------------

    def nouvelle_journee(self, date: Any, balance: float) -> None:
        """Fixe la référence du jour (balance de début de journée) et lève le blocage journalier.

        Sans effet si ``date`` est égale ou antérieure à la date en cours (voir la note de la
        classe). L'arrêt définitif n'est jamais levé ici.
        """
        if self._date_jour is not None:
            try:
                if not date > self._date_jour:
                    return
            except TypeError:
                if date == self._date_jour:
                    return
        self._date_jour = date
        bal = _nombre_positif(balance)
        if bal is None:
            # Impossible de mesurer la perte du jour : on ne trade pas aujourd'hui.
            self._bloque_jour = True
            self._historique.append(Declenchement(date, DECL_BALANCE_INVALIDE, _float_ou_nan(balance)))
            return
        self._ref_jour = bal
        self._bloque_jour = False
        self._observer(date, bal)

    def mettre_a_jour(self, instant: Any, equity: float) -> None:
        """Observe l'equity (au prix du marché) : met à jour le pic et vérifie les deux limites."""
        eq = _nombre_positif(equity)
        if eq is None:
            self._historique.append(Declenchement(instant, DECL_EQUITY_INVALIDE, _float_ou_nan(equity)))
            return
        self._observer(instant, eq)

    def peut_ouvrir(self, instant: Any, equity: float) -> Tuple[bool, str]:
        """Autorise-t-on une nouvelle position maintenant ? Renvoie ``(autorise, raison)``.

        Observe d'abord l'equity (comme ``mettre_a_jour``) pour qu'une limite franchie depuis
        la dernière mise à jour soit prise en compte. Raisons : ``ok``, ``arret_definitif``,
        ``perte_jour_max``, ``entree_invalide:equity``.
        Ne vérifie pas le nombre de positions ouvertes (``positions_max``) : c'est à
        l'appelant de le faire.
        """
        eq = _nombre_positif(equity)
        if eq is None:
            self._historique.append(Declenchement(instant, DECL_EQUITY_INVALIDE, _float_ou_nan(equity)))
            if self.arret_definitif:
                return (False, RAISON_ARRET_DEFINITIF)
            return (False, PREFIXE_ENTREE_INVALIDE + "equity")
        self._observer(instant, eq)
        if self.arret_definitif:
            return (False, RAISON_ARRET_DEFINITIF)
        if self._bloque_jour:
            return (False, RAISON_PERTE_JOUR_MAX)
        return (True, RAISON_OK)

    def reinitialiser_arret(self, nouveau_pic: Optional[float] = None) -> None:
        """Lève l'arrêt définitif. À n'appeler que sur décision humaine explicite.

        Le pic repart de ``nouveau_pic`` s'il est fourni et valide, sinon de la dernière
        equity observée : sans cela, la mise à jour suivante redéclencherait l'arrêt
        immédiatement. Le blocage journalier éventuel n'est pas levé (il tombe à la
        prochaine journée).
        """
        pic = _nombre_positif(nouveau_pic) if nouveau_pic is not None else None
        self._pic = pic if pic is not None else self._dernier_equity
        self.arret_definitif = False
        self.raison_arret = ""
        self._historique.append(Declenchement(None, DECL_REINITIALISATION, float(self._pic)))

    # --- interne ------------------------------------------------------------

    def _observer(self, instant: Any, eq: Decimal) -> None:
        self._dernier_equity = eq
        if eq > self._pic:
            self._pic = eq
        with localcontext() as ctx:
            ctx.prec = _PRECISION
            # Perte du jour : comparaison exacte perte ≥ référence × seuil.
            perte = self._ref_jour - eq
            if not self._bloque_jour and perte >= self._ref_jour * self._seuil_jour:
                self._bloque_jour = True
                self._historique.append(Declenchement(
                    instant, DECL_PERTE_JOUR, float(perte * 100 / self._ref_jour)))
            # Drawdown depuis le pic.
            baisse = self._pic - eq
            if not self.arret_definitif and baisse >= self._pic * self._seuil_dd:
                dd_pct = float(baisse * 100 / self._pic)
                self.arret_definitif = True
                self.raison_arret = (f"drawdown_max : {dd_pct:.2f} % depuis le pic "
                                     f"{float(self._pic):.2f} (equity {float(eq):.2f})")
                self._historique.append(Declenchement(instant, DECL_DRAWDOWN_MAX, dd_pct))
