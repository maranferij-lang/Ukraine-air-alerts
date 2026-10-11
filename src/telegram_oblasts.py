"""Which of our 24 units does a Ukrainian-language threat post mention?

Matching is on word STARTS, never on substrings: a pattern only fires at the beginning of a word (the
character before it is not a letter, digit, apostrophe or hyphen). That is what the volunteer feed's
parser got wrong: "прилуцький" contains "луцьк" (Lutsk, Volyn) and a Lviv pattern fired inside
"подільський". Here "луцьк" cannot fire inside "прилуцький", and nothing maps the district word
"подільський" at all (Podilskyi districts and the town of Podilsk exist in several oblasts).

Rules:
  - text is lower-cased and apostrophes are unified;
  - PHRASES come first and are blanked out after matching: hyphenated or multi-word place names whose
    halves would otherwise match another oblast ("кам'янець-подільський" is Khmelnytskyi, not
    Vinnytsia; "переяслав-хмельницький" is Kyiv oblast, not Khmelnytskyi);
  - every other hyphen then becomes a space, so "Харків-Київ" gives both;
  - patterns are oblast name stems plus the main cities. Ambiguous names that exist in several oblasts
    (Тростянець, Первомайськ, Золочів, Ямпіль, Покровське, Олександрівка, Михайлівка, ...) are left out;
  - a place belongs to the oblast it is in administratively (Славутич: Kyiv oblast).
Oblast names are those of the alert data. Crimea, Luhansk and occupied-only places give no unit.
"""
import re

KYIV_CITY, KYIV = "Kyiv City", "Kyivska oblast"

# (regex without word-start anchor) per unit; "ob" in the pattern list means oblast-level stems
STEMS = {
    "Cherkaska oblast": [r"черкас", r"черкащин", r"умань", r"канів", r"смілу?\b", r"сміли\b", r"сміл[аі]\b",
                         r"золотонош", r"звенигородк", r"шпол[аиіу]\b", r"корсунь", r"черкасс"],
    "Chernihivska oblast": [r"чернігів", r"чернигов", r"ніжин", r"прилук", r"прилуц", r"бахмач", r"борзн",
                            r"корюківк", r"бобровиц", r"новгород-сіверськ", r"ріп[кo]", r"козелець", r"носівк", r"городн[яіюї]\b"],
    "Chernivetska oblast": [r"чернівц", r"чернівецьк", r"буковин"],
    "Dnipropetrovska oblast": [r"дніпропетров", r"дніпро(?![а-яіїєґ])", r"дніпр[ауі](?![а-яіїєґ])", r"дніпром",
                               r"днепр(?!опетров)", r"днепропетров", r"криворіж", r"нікопол", r"марганц",
                               r"павлоград", r"кам'?янськ", r"синельників", r"новомосковськ", r"верхньодніпров",
                               r"тернівк", r"підгородн"],
    "Donetska oblast": [r"донеччин", r"донецьк", r"донбас", r"краматорськ", r"слов'?янськ", r"костянтинівк",
                        r"покровськ", r"мирноград", r"добропіл", r"бахмут", r"авдіївк", r"маріуп", r"торецьк",
                        r"дружківк", r"часів яр", r"сіверськ"],
    "Ivano-Frankivska oblast": [r"івано-франківськ", r"франківськ", r"франківщин", r"прикарпат", r"калуш", r"коломи",
                                r"надвірн", r"болехів", r"долин[аиіу]\b", r"яремч"],
    "Kharkivska oblast": [r"харків", r"харьков", r"куп'?янськ", r"ізюм", r"чугуїв", r"балаклі", r"лозов[аіуоє]",
                          r"вовчанськ", r"богодухів", r"зміїв", r"мереф", r"дергач", r"красноград", r"барвінків",
                          r"липц[іиюя]\b", r"печеніг", r"борова\b", r"золоч(?:ів)?\b-харк"],
    "Khersonska oblast": [r"херсон", r"каховк", r"гола пристань", r"голої пристані", r"скадовськ", r"берислав",
                          r"генічеськ", r"олешк", r"цюрупинськ", r"чаплинк"],
    "Khmelnytska oblast": [r"хмельницьк", r"хмельниччин", r"хмельничин", r"шепетівк", r"славут(?!ич)", r"нетішин", r"старокостянтинів",
                           r"ізяслав", r"волочиськ", r"красилів", r"полонн[аеиіу]\b", r"деражн", r"білогір'?"],
    "Kirovohradska oblast": [r"кіровоград", r"кропивницьк", r"олександрі[яюїєй]", r"знам'?янк", r"світловодськ",
                             r"голованівськ", r"новоукраїнк", r"гайворон", r"долинськ"],
    KYIV_CITY: [r"київ(?![а-яіїєґ])", r"києв", r"киев(?![щ])", r"київськ(?=[а-яіїєґ]*\s+район)"],
    KYIV: [r"київщин", r"київськ(?![а-яіїєґ]*\s+район)", r"бровар", r"борис[пп][іо]л", r"ірпін", r"ірпен", r"васильків", r"василькова", r"фастів", r"фастова",
           r"обухів", r"обухов", r"гостомел", r"українк", r"ржищів", r"козин",  r"вишгород", r"яготин", r"баришівк", r"згурівк", r"іванків", r"чорнобил", r"сквир",
           r"славутич", r"буч[аіуи]\b", r"бучею", r"переяслав", r"вишневе\b", r"боярк", r"макарів", r"димер"],
    "Lvivska oblast": [r"львів", r"львов", r"дрогобич", r"стрий", r"червоноград", r"борислав", r"трускавец",
                       r"трускавець", r"самбір", r"жовкв", r"броди(?![а-яіїєґ])", r"сокал[ьяю]", r"радехів"],
    "Mykolaivska oblast": [r"миколаїв(?!к)", r"миколаївщин", r"миколаївськ", r"николаев(?!к)", r"вознесенськ",
                           r"южноукраїнськ", r"очаків", r"баштанк", r"снігурівк", r"врадіївк", r"доманівк", r"казанк"],
    "Odeska oblast": [r"одес", r"одещин", r"ізмаїл", r"рені(?![а-яіїєґ])", r"кілі[яюїє]", r"татарбунар", r"арциз",
                      r"роздільн", r"білгород-дністровськ", r"чорноморськ", r"болград", r"біляївк", r"вилков"],
    "Poltavska oblast": [r"полтав", r"кременчу", r"лубн", r"миргород", r"лохвиц", r"гадяч", r"зіньків", r"пирятин",
                         r"хорол", r"решетилівк", r"карлівк", r"шишак", r"горішн[іє] плавн", r"горішніх плавн"],
    "Rivnenska oblast": [r"рівне(?![а-яіїєґ])", r"рівного", r"рівному", r"рівненщин", r"рівненськ", r"дубн[оа]\b",
                         r"дубні\b", r"здолбунів", r"костопіл", r"вараш", r"кузнецовськ", r"радивилів", r"острог",
                         r"корець", r"сарн(?:и|ах|ам|ами)(?![а-яіїєґ])", r"сарненськ"],
    "Sumska oblast": [r"суми(?![а-яіїєґ])", r"сумах", r"сумам", r"сумщин", r"сумськ", r"сум(?![а-яіїєґ])",
                      r"сумы", r"конотоп", r"шостк", r"охтирк", r"глухів", r"ромн[иіа]\b", r"лебедин", r"краснопілл",
                      r"білопілл", r"путивл", r"кролевец", r"буринь", r"недригайлів", r"середина-буд"],
    "Ternopilska oblast": [r"тернопіл", r"тернопільщин", r"чортків", r"кременець", r"кременц", r"бережан", r"збараж",
                           r"бучач", r"заліщик", r"підгайц", r"теребовл", r"монастириськ"],
    "Vinnytska oblast": [r"вінниц", r"вінниччин", r"вінничин", r"винниц", r"жмеринк", r"могилів-подільськ", r"козятин", r"гайсин",
                         r"тульчин", r"хмільник", r"бершад", r"липовець", r"калинівк", r"іллінці", r"немирів",
                         r"ладижин", r"піщан[ка]"],
    "Volynska oblast": [r"волин", r"нововолин", r"луцьк", r"ковел[ьяю]", r"володимир-волинськ", r"горохів", r"ківерц",
                        r"камінь-каширськ", r"любомл", r"іваничі", r"маневичі", r"луцк"],
    "Zakarpatska oblast": [r"закарпат", r"ужгород", r"мукачев", r"берегів", r"хуст", r"виноградів", r"рахів", r"тячів",
                           r"свалявк", r"чоп(?![а-яіїєґ])"],
    "Zaporizka oblast": [r"запоріж", r"запоріз", r"запорож", r"мелітопол", r"бердянськ", r"енергодар", r"оріхів", r"василівк",
                         r"токмак", r"пологи(?![а-яіїєґ])", r"гуляйпол", r"кам'?янка-дніпровськ"],
    "Zhytomyrska oblast": [r"житомир", r"бердичів", r"коростен", r"новоград-волинськ", r"малин(?:а|у|і|ом|ськ)?(?![а-яіїєґ])",
                           r"овруч", r"радомишл", r"чуднів", r"брусилів", r"баранівк", r"олевськ", r"емільчин",
                           r"попільн", r"ружин", r"коростишів"],
}

# multi-word and hyphenated names matched (and removed) before the stems; unit or None to just blank them
PHRASES = {
    r"кам'?янець-подільськ[а-яіїєґ]*": "Khmelnytska oblast",
    r"переяслав-хмельницьк[а-яіїєґ]*": KYIV,
    r"білгород-дністровськ[а-яіїєґ]*": "Odeska oblast",
    r"новгород-сіверськ[а-яіїєґ]*": "Chernihivska oblast",
    r"новоград-волинськ[а-яіїєґ]*": "Zhytomyrska oblast",
    r"могилів-подільськ[а-яіїєґ]*": "Vinnytska oblast",
    r"володимир-волинськ[а-яіїєґ]*": "Volynska oblast",
    r"кам'?янка-дніпровськ[а-яіїєґ]*": "Zaporizka oblast",
    r"камінь-каширськ[а-яіїєґ]*": "Volynska oblast",
    r"івано-франківськ[а-яіїєґ]*": "Ivano-Frankivska oblast",
    r"кривий ріг|кривого рогу|кривому розі|кривим рогом|кривий рогу": "Dnipropetrovska oblast",
    r"біл(?:а|ої|у|ій|ою) церкв[аиіуоюе]|біл(?:а|ої|у|ій|ою) церк[а-я]*": KYIV,
    r"мал[аоуіи] виск[аиіуою]": "Kirovohradska oblast",
    r"нов(?:ий|ого|ому|им) буг[аоуі]?": "Mykolaivska oblast",
    r"дніпровськ[а-яіїєґ]* район[а-яіїєґ]* києва|дніпровськ[а-яіїєґ]* район[а-яіїєґ]* м\. києва": KYIV_CITY,
}

APOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "‘": "'", "´": "'"})
_PHRASES = [(re.compile(r"(?<![\w'-])(?:" + p + ")", re.I), u) for p, u in PHRASES.items()]
_STEMS = [(u, re.compile(r"(?<![\w'-])(?:" + "|".join(ps) + ")", re.I)) for u, ps in STEMS.items()]
_HYPHEN = re.compile(r"(?<=\w)-(?=\w)")
UNITS = sorted(STEMS)


def mentioned(text):
    """Set of units named in a post (word-start matching, see module docstring)."""
    t = text.lower().translate(APOS)
    found = set()
    for rx, unit in _PHRASES:
        for m in rx.finditer(t):
            found.add(unit)
        t = rx.sub(" ", t)
    t = _HYPHEN.sub(" ", t)
    for unit, rx in _STEMS:
        if rx.search(t):
            found.add(unit)
    return found


def explain(text):
    """[(unit, matched text)] for display: what exactly triggered each unit (after the phrase step)."""
    t = text.lower().translate(APOS)
    out = []
    for rx, unit in _PHRASES:
        out += [(unit, m.group(0)) for m in rx.finditer(t)]
        t = rx.sub(" ", t)
    t = _HYPHEN.sub(" ", t)
    for unit, rx in _STEMS:
        m = rx.search(t)
        if m:
            end = m.end()
            while end < len(t) and (t[end].isalpha() or t[end] in "'"):
                end += 1
            out.append((unit, t[m.start():end]))
    return out
