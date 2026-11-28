"""Layer 2B / 4B: Multilingual vulgarity & prohibited-goods guardrails.

Covers English, Hindi (Romanized/Hinglish + Devanagari), and Urdu (Romanized +
Perso-Arabic/Nastaliq script) without false positives on genuine Kashmiri/Indian
handicraft vocabulary (e.g., 'peacock', 'walnut', 'carved knife box', 'brass',
'glass', 'classic', 'wine red', 'ivory cream', 'chikankari', 'Dar', 'Butt').
"""
from __future__ import annotations

import re
import unicodedata

from app.modules.guardrails.schemas import FieldIssue, GuardrailOutcome

ZERO_WIDTH_JOINER_RE = re.compile(r"[\u200b\u200d\u200e\u200f\u2060\ufeff]")
ZWNJ_RE = re.compile(r"\u200c+")
DEVANAGARI_NUKTA_RE = re.compile(r"\u093c")
ARABIC_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640]")

LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
OBFUSCATED_SPAN_RE = re.compile(r"[A-Za-z0-9@$!*._#]{3,}")
SPACED_LETTERS_RE = re.compile(
    r"(?<![A-Za-z])(?:[A-Za-z](?:[\s._*-]+[A-Za-z]){2,})(?![A-Za-z])"
)
NON_WORD_TOKEN_RE = re.compile(r"[^\w\u0600-\u06FF\u0900-\u097F]+", re.UNICODE)

# Catches asterisk/symbol-masked profanity or contraband like f*ck, sh*t, b!tch, bh*sdi, d**ru
MASKED_VULGAR_PATTERNS = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"\bf[*_#]+\w*ck\w*\b",
        r"\bfu[*_#]+k\w*\b",
        r"\bsh[*_#!]+t\w*\b",
        r"\bb[*_#!]+tch\w*\b",
        r"\bc[*_#]+nt\w*\b",
        r"\bp[*_#0]+rn\w*\b",
        r"\bm[*_@a]+d[*_@a]+rch[*_0o]+d\w*\b",
        r"\bbh[*_e]*nch[*_0o]+d\w*\b",
        r"\bbh[*_0o]+sd[*_#!i]*k?e?\b",
        r"\bch[*_u]+t[*_#!i]*y[ae]\b",
        r"\bg[*_@a]+nd[u]?\b",
        r"\br[*_@a]+nd[i]?\b",
    )
)
MASKED_PROHIBITED_PATTERNS = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"\bd[*_@a]+ru\b",
        r"\bsh[*_@a]+r[*_@a]+b\b",
    )
)

LEET_TRANS = str.maketrans({
    "@": "a",
    "$": "s",
    "!": "i",
    "1": "i",
    "0": "o",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
})


def _normalize_urdu_arabic(text: str) -> str:
    text = ARABIC_DIACRITICS_RE.sub("", text)
    return (
        text.replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ئ", "ی")
        .replace("ك", "ک")
        .replace("ه", "ہ")
        .replace("ھ", "ہ")
        .replace("ۂ", "ہ")
        .replace("ۃ", "ہ")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
    )


def _normalize_common(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text or "")
    cleaned = ZERO_WIDTH_JOINER_RE.sub("", cleaned)
    cleaned = ZWNJ_RE.sub(" ", cleaned)
    cleaned = DEVANAGARI_NUKTA_RE.sub("", cleaned)
    return _normalize_urdu_arabic(cleaned)


def _collapse_repeats_gt2(token: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1", token)


def _collapse_all_repeats(token: str) -> str:
    return re.sub(r"(.)\1+", r"\1", token)


# ---------------------------------------------------------------------------
# 1. Vulgar / Profane / Obscene / Abusive Terms (English, Hindi, Urdu)
# ---------------------------------------------------------------------------
_ROMAN_VULGAR_TOKENS: frozenset[str] = frozenset({
    # English profanity, slurs & sexually explicit slang
    "fuck", "fucker", "fuckers", "fucking", "fucked", "fucks", "fuckoff",
    "motherfucker", "motherfuckers", "motherfucking", "mofo",
    "shit", "shits", "shitty", "bullshit", "horseshit", "dipshit",
    "bitch", "bitches", "bitching", "bitchy",
    "bastard", "bastards",
    "asshole", "assholes", "arsehole", "arseholes", "dumbass", "jackass", "badass",
    "dick", "dicks", "dickhead", "dickheads",
    "cock", "cocks", "cocksucker", "cocksuckers",
    "pussy", "pussies", "cunt", "cunts", "twat", "wanker", "bollocks", "douchebag",
    "whore", "whores", "slut", "sluts", "slutty", "prostitute", "prostitution",
    "blowjob", "handjob", "rimjob", "boobjob", "footjob",
    "masturbate", "masturbation", "orgasm", "ejaculate", "cumshot", "jizz",
    "boobs", "tits", "titties", "penis", "vagina", "clitoris", "scrotum", "testicles",
    "dildo", "vibrator", "porn", "porno", "pornography", "hentai", "xxx", "nsfw", "erotica",
    "nude", "nudes", "rape", "rapist", "raping",
    "nigger", "niggers", "nigga", "niggas", "faggot", "faggots", "retard", "retarded",

    # Romanized Hindi / Hinglish & Urdu vulgar / abusive slang
    "madarchod", "maadarchod", "maderchod", "madarchodh", "madarchoot", "madarjat", "madarjaat",
    "bhenchod", "behenchod", "behanchod", "bahenchod", "bhainchod", "bhenchodd",
    "penchod", "painchod", "phenchod", "bhenchot", "machod", "maachod", "betichod", "baapchod",
    "bhosdike", "bhosadi", "bhosdi", "bhosda", "bhosad", "bhosdika", "bhosadiwala", "bhosdiwala",
    "bhonsdike", "bhonsda", "bhonsdi", "bsdk", "bkl", "mkc",
    "chutiya", "chutiye", "chutiyapa", "chutiyapanti", "chootiya", "chootiye", "chutiyaa",
    "chut", "choot", "chutmar", "chootmar", "chutmari", "chutmarike", "chodu", "chod", "chodna", "chodne",
    "chudai", "chudwana", "chudwa",
    "lund", "lunn", "lauda", "laude", "loda", "lode", "lavda", "lavde", "lawda", "lawde",
    "louda", "loude", "lora", "loray", "lulli",
    "gaand", "gand", "gandu", "gaandu", "gandmara", "gaandmara", "gandmasti", "gandfat", "gandfattu",
    "bund", "bundmara",
    "randi", "raand", "randwa", "randikhana", "randibaaz",
    "harami", "haraami", "haramzada", "haraamzada", "haramzadi", "haramzaday", "haramjada",
    "haramkhor", "haraamkhor",
    "kamina", "kameena", "kamine", "kameene", "kaminey", "kamini", "kameeni",
    "kuttiya", "bhadwa", "bhadwe", "bhadva", "bhadve", "bharwa", "bharwe", "bhadwi", "bharwi",
    "jhaant", "jhant", "jhaantu", "jhantu", "jhaat", "jhatu",
    "chinal", "chinaal", "gashti", "gasti", "kanjar", "kanjari",
    "phuddi", "phudda", "fuddi", "fudda", "phudi", "fudi", "kuss",
    "chuchi", "chuchiya", "mamme", "boobe",
    "tatte", "tatto", "muth", "mutth", "muthal", "muthmar",
    "beghairat", "begairat", "begaairat", "laanati", "lanti",
    "suwar", "khotay", "khotey", "hijda",
})

_ROMAN_VULGAR_PHRASES: tuple[str, ...] = (
    "son of a bitch",
    "piece of shit",
    "fuck off",
    "fuck you",
    "mother fucker",
    "suck my dick",
    "blow job",
    "hand job",
    "ma ki chut",
    "maa ki chut",
    "ma ka bhosda",
    "maa ka bhosda",
    "bhen ke lode",
    "behen ke lode",
    "bhen ki chut",
    "behen ki chut",
    "bhen di",
    "teri maa",
    "teri behan",
    "teri pain",
    "ullu ka pattha",
    "suar ki aulad",
    "kutte ki aulad",
    "kutta kamina",
    "haram ki aulad",
    "gand mara",
    "gaand mara",
)

_DEVANAGARI_VULGAR_TERMS: frozenset[str] = frozenset({
    "मादरचोद", "मदरचोद", "मादरचोत",
    "बहनचोद", "भैनचोद", "बेटीचोद",
    "भोसडी", "भोसडीके", "भोसडा", "भोसद", "भोसडीवाला",
    "भडवा", "भडवे", "भड़वा", "भड़वे",
    "चूतिया", "चूतिये", "चूतियापा", "चूत", "चूतड",
    "लंड", "लौडा", "लौडे", "लोडा", "लोडे", "लवडा", "लवडे",
    "गांड", "गांडू", "गाण्ड", "गाण्डू", "गांडमारा",
    "रंडी", "रांड", "रंडवा", "रंडीखाना",
    "हरामी", "हरामजादा", "हरामजादी", "हरामखोर",
    "कमीना", "कमीने", "कमीनी", "कुत्तिया",
    "झांट", "झांटू", "झाँट",
    "चोद", "चोदना", "चोदू", "चुदाई", "चुदवाना",
    "टट्टी", "मुठ", "मुठल", "गश्ती", "कंजरी", "कंजर", "चूची", "चिनाल",
    "मां की चूत", "बहन के लोडे", "तेरी मां", "कुत्ते की औलाद", "सूअर की औलाद",
})

_URDU_VULGAR_TERMS: frozenset[str] = frozenset(
    _normalize_urdu_arabic(term)
    for term in (
        "حرامزادہ", "حرام زادہ", "حرامزادی", "حرامی", "حرامخور", "حرام خور",
        "کمینہ", "کمینی", "کمینے", "کنجر", "کنجری", "گشتی", "رنڈی", "رانڈ",
        "بھڑوا", "بھڑوے", "بھوسڑی", "بھوسڑا", "چوتیا", "چوتیہ", "چوت",
        "لنڈ", "لولا", "لوڑا", "لوڑے", "گانڈ", "گانڈو", "پھدی", "پھدا",
        "چود", "چدائی", "ماں چود", "بہن چود", "پین چود", "بے غیرت", "بیغیرت",
        "کتیا", "لعنتی", "چوچی", "ماں کی چوت", "تیری ماں", "تیری بہن",
    )
)

# ---------------------------------------------------------------------------
# 2. Prohibited / Regulated / Non-Handicraft Contraband (English, Hindi, Urdu)
# ---------------------------------------------------------------------------
_ROMAN_PROHIBITED_TOKENS: frozenset[str] = frozenset({
    # Alcohol & desi/country liquor (note: bare 'wine' excluded due to 'Wine Red' textile color)
    "daaru", "daru", "daaroo", "daroo", "desidaaru", "desidaru",
    "sharab", "sharaab", "shraab", "desisharab", "tharra", "kachidaru", "kachchidaru",
    "liquor", "alcohol", "alcoholic", "booze", "moonshine", "toddy",
    "whisky", "whiskey", "vodka", "tequila", "bourbon", "scotch",
    "brandy", "cognac", "champagne", "beer", "lager",
    # Tobacco, vapes, narcotics & controlled substances
    "ganja", "charas", "bhang", "hashish", "marijuana", "cannabis", "weed",
    "cocaine", "heroin", "opium", "afeem", "afim", "meth", "methamphetamine",
    "mdma", "ecstasy", "lsd", "smack", "chitta", "ketamine", "fentanyl",
    "narcotic", "narcotics",
    "cigarette", "cigarettes", "beedi", "bidi", "gutkha", "gutka", "khaini",
    "tobacco", "nicotine", "vape", "vaping", "ecigarette", "sheesha", "shisha",
    "chillum", "chilam", "bong",
    # Firearms, ammunition & explosives (note: 'knife' excluded for 'carved knife box')
    "pistol", "revolver", "rifle", "shotgun", "handgun", "firearm", "firearms",
    "ak47", "ammunition", "bullets", "gunpowder", "explosive", "explosives",
    "grenade", "bomb", "detonator", "dynamite", "rdx", "tnt", "gun", "guns",
    # Illegal wildlife / banned heritage materials (note: bare 'ivory' excluded for 'Ivory Cream' color)
    "shahtoosh", "chiru", "pangolin",
    # Adult explicit merchandise
    "dildo", "vibrator", "condom", "condoms", "viagra", "cialis", "kamagra",
})

_ROMAN_PROHIBITED_PHRASES: tuple[str, ...] = (
    "desi daaru",
    "desi daru",
    "desi sharab",
    "desi sharaab",
    "kachi daru",
    "kachchi daru",
    "country liquor",
    "mahua liquor",
    "desi wine",
    "homemade wine",
    "paan masala",
    "pan masala",
    "e-cigarette",
    "hookah tobacco",
    "hookah flavor",
    "ak-47",
    "machine gun",
    "elephant ivory",
    "real ivory",
    "ivory tusk",
    "rhino horn",
    "tiger skin",
    "leopard skin",
    "snake skin",
    "sex toy",
    "sex toys",
    "adult toy",
    "adult toys",
    "fake currency",
    "counterfeit currency",
    "fake gi tag",
    "forged certificate",
)

_DEVANAGARI_PROHIBITED_TERMS: frozenset[str] = frozenset({
    "दारू", "देसी दारू", "कच्ची दारू", "शराब", "देसी शराब", "अल्कोहल", "व्हिस्की", "वोदका", "बीयर",
    "गांजा", "चरस", "भांग", "अफीम", "हेरोइन", "कोकीन", "स्मैक", "नशा", "नशीला",
    "गुटखा", "तंबाकू", "सिगरेट", "बीड़ी", "खैनी", "चिलम",
    "बंदूक", "पिस्तौल", "कारतूस", "बम", "बारूद", "विस्फोटक",
    "शहतूश", "हाथी दांत", "हाथीदांत",
})

_URDU_PROHIBITED_TERMS: frozenset[str] = frozenset(
    _normalize_urdu_arabic(term)
    for term in (
        "شراب", "دیسی شراب", "دارو", "دیسی دارو", "الکوہل", "وہسکی", "بیئر",
        "چرس", "بھنگ", "افیون", "گانجا", "ہیروئن", "کوکین", "نشہ",
        "تمباکو", "سگریٹ", "گٹکا", "بیڑی", "چلم",
        "بندوق", "پستول", "گولی بارود", "بم", "بارود",
        "شہتوش", "ہاتھی دانت",
    )
)

# Precompute repeat-collapsed forms of single-token Roman vocabularies
_ROMAN_VULGAR_ALL: frozenset[str] = frozenset(
    _ROMAN_VULGAR_TOKENS
    | {_collapse_all_repeats(t) for t in _ROMAN_VULGAR_TOKENS if len(_collapse_all_repeats(t)) >= 3}
)
_ROMAN_PROHIBITED_ALL: frozenset[str] = frozenset(
    _ROMAN_PROHIBITED_TOKENS
    | {_collapse_all_repeats(t) for t in _ROMAN_PROHIBITED_TOKENS if len(_collapse_all_repeats(t)) >= 3}
)

_ROMAN_VULGAR_PHRASE_PATTERNS = tuple(
    re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE) for p in _ROMAN_VULGAR_PHRASES
)
_ROMAN_PROHIBITED_PHRASE_PATTERNS = tuple(
    re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE) for p in _ROMAN_PROHIBITED_PHRASES
)


def _extract_roman_candidates(normalized: str) -> set[str]:
    candidates: set[str] = set()

    for m in LATIN_TOKEN_RE.finditer(normalized):
        tok = m.group(0).lower()
        candidates.add(tok)
        stripped_digits = tok.strip("0123456789")
        if len(stripped_digits) >= 3:
            candidates.add(stripped_digits)
        candidates.add(_collapse_repeats_gt2(tok))
        collapsed = _collapse_all_repeats(tok)
        if len(collapsed) >= 3:
            candidates.add(collapsed)

    # Obfuscated chunks such as f*ck, f.u.c.k, m@d@rch0d, d@aru, bh0sdi
    for m in OBFUSCATED_SPAN_RE.finditer(normalized):
        raw = m.group(0).lower()
        if not any(ch in raw for ch in "@$!*._#") and not (
            any(c.isalpha() for c in raw) and any(c.isdigit() for c in raw)
        ):
            continue
        deleet = raw.translate(LEET_TRANS)
        alpha_only = re.sub(r"[^a-z0-9]", "", deleet)
        if len(alpha_only) >= 3:
            candidates.add(alpha_only)
            candidates.add(_collapse_repeats_gt2(alpha_only))
            collapsed = _collapse_all_repeats(alpha_only)
            if len(collapsed) >= 3:
                candidates.add(collapsed)

    # Spaced single-letter evasion: "f u c k", "d a a r u"
    for m in SPACED_LETTERS_RE.finditer(normalized):
        joined = re.sub(r"[\s._*-]+", "", m.group(0)).lower()
        if len(joined) >= 3:
            candidates.add(joined)
            candidates.add(_collapse_repeats_gt2(joined))
            collapsed = _collapse_all_repeats(joined)
            if len(collapsed) >= 3:
                candidates.add(collapsed)

    return candidates


def _matches_script_terms(normalized: str, terms: frozenset[str]) -> bool:
    tokens = {tok for tok in NON_WORD_TOKEN_RE.split(normalized) if tok}
    if tokens & terms:
        return True
    ws_collapsed = " ".join(normalized.split())
    for term in terms:
        if " " in term and re.search(
            rf"(?<![\w\u0600-\u06FF\u0900-\u097F]){re.escape(term)}(?![\w\u0600-\u06FF\u0900-\u097F])",
            ws_collapsed,
        ):
            return True
    return False


def validate_content_policy(field: str, value: str | None) -> list[FieldIssue]:
    """Validate text against English/Hindi/Urdu vulgarity and prohibited-item policies."""
    if not value or not value.strip():
        return []

    normalized = _normalize_common(value)
    lowered_ws = " ".join(normalized.lower().split())
    candidates = _extract_roman_candidates(normalized)

    vulgar_hit = bool(
        (candidates & _ROMAN_VULGAR_ALL)
        or any(pat.search(lowered_ws) for pat in _ROMAN_VULGAR_PHRASE_PATTERNS)
        or any(pat.search(lowered_ws) for pat in MASKED_VULGAR_PATTERNS)
        or _matches_script_terms(normalized, _DEVANAGARI_VULGAR_TERMS)
        or _matches_script_terms(normalized, _URDU_VULGAR_TERMS)
    )

    prohibited_hit = bool(
        (candidates & _ROMAN_PROHIBITED_ALL)
        or any(pat.search(lowered_ws) for pat in _ROMAN_PROHIBITED_PHRASE_PATTERNS)
        or any(pat.search(lowered_ws) for pat in MASKED_PROHIBITED_PATTERNS)
        or _matches_script_terms(normalized, _DEVANAGARI_PROHIBITED_TERMS)
        or _matches_script_terms(normalized, _URDU_PROHIBITED_TERMS)
    )

    issues: list[FieldIssue] = []
    if vulgar_hit:
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_VULGAR_OR_ABUSIVE_CONTENT",
                severity=GuardrailOutcome.BLOCK,
                message=(
                    f"Field '{field}' contains vulgar, profane, or abusive language "
                    "(English/Hindi/Urdu) and is blocked by ASIGS content guardrails."
                ),
            )
        )
    if prohibited_hit:
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_PROHIBITED_OR_ILLEGAL_GOODS",
                severity=GuardrailOutcome.BLOCK,
                message=(
                    f"Field '{field}' references prohibited or non-handicraft regulated items "
                    "(alcohol, tobacco, narcotics, weapons, or banned wildlife) and cannot be listed on HunarLink."
                ),
            )
        )
    return issues
