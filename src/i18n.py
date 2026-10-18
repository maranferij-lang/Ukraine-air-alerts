"""Text for `predict.py --lang {en,uk}` and the forecast map: English (the default, the strings the scripts always printed) and Ukrainian.

Oblast names: OBLAST_UK is a hand-written list, not a translation. For our 24 units it is checked by scripts/check_forecast_map.py against the Ukrainian state names the
Ukraine Alarm API itself uses (src/ukrainealarm.UK_TO_OURS, the table the data pipeline maps the API's names with) and against the names in the saved API files; Crimea and Sevastopol
are the official names and are not in our data (the check says so).

T(key, lang, **fields) fills a string by name. Error messages, refusals that name a command, and `--help` stay English.
"""

OBLAST_UK = {  # our unit name -> the name as the API writes it (full form)
    "Cherkaska oblast": "Черкаська область", "Chernihivska oblast": "Чернігівська область", "Chernivetska oblast": "Чернівецька область",
    "Dnipropetrovska oblast": "Дніпропетровська область", "Donetska oblast": "Донецька область", "Ivano-Frankivska oblast": "Івано-Франківська область",
    "Kharkivska oblast": "Харківська область", "Khersonska oblast": "Херсонська область", "Khmelnytska oblast": "Хмельницька область",
    "Kirovohradska oblast": "Кіровоградська область", "Kyiv City": "м. Київ", "Kyivska oblast": "Київська область", "Lvivska oblast": "Львівська область",
    "Mykolaivska oblast": "Миколаївська область", "Odeska oblast": "Одеська область", "Poltavska oblast": "Полтавська область", "Rivnenska oblast": "Рівненська область",
    "Sumska oblast": "Сумська область", "Ternopilska oblast": "Тернопільська область", "Vinnytska oblast": "Вінницька область", "Volynska oblast": "Волинська область",
    "Zakarpatska oblast": "Закарпатська область", "Zaporizka oblast": "Запорізька область", "Zhytomyrska oblast": "Житомирська область",
}
NOT_MODELLED_UK = {"Luhansk": "Луганська область", "Crimea": "Автономна Республіка Крим", "Sevastopol": "м. Севастополь"}  # the three units the map draws as "no data"
MONTHS_UK = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]  # genitive, for "5 вересня"
LANGS = ("en", "uk")


UK_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def sort_key(name, lang="en"):
    """Alphabetical order of a short name in its language (Ukrainian: і, ї and є are where the alphabet puts them, not at the end of the code table)."""
    if lang != "uk":
        return name
    return [UK_ALPHABET.index(c) if c in UK_ALPHABET else -1 for c in name.lower()]


def short_name(full, lang="en"):
    """The name used on the map and in the tables: "Kharkivska" / "Харківська", "Kyiv City" / "м. Київ"."""
    if lang == "uk":
        full = OBLAST_UK.get(full) or NOT_MODELLED_UK.get(full) or full
        return full[:-len(" область")] if full.endswith(" область") else full
    return full.replace(" oblast", "")


def full_name(full, lang="en"):
    """The full name: "Kharkivska oblast" / "Харківська область"."""
    return (OBLAST_UK.get(full) or full) if lang == "uk" else full


def unit_full_name(name, lang="en"):
    """Full names of the three grey units: "Crimea" / "Автономна Республіка Крим"."""
    return NOT_MODELLED_UK[name] if lang == "uk" else name


def map_unit_name(name, lang="en"):
    """Names of the three grey units on the map: Crimea, Luhansk, Sevastopol."""
    if lang == "uk":
        return {"Crimea": "Крим", "Luhansk": "Луганська", "Sevastopol": "м. Севастополь"}[name]
    return name


S = {
    # ---- predict.py --at: status lines
    "st_train": {"en": "TRAINING PERIOD: the models were fitted on data up to {cutoff}, which includes this hour and what followed it. These numbers are not forecasts.",
                 "uk": "ПЕРІОД НАВЧАННЯ: моделі навчено на даних до {cutoff}, які містять цю годину і те, що було після неї. Ці числа не є прогнозами."},
    "st_after_all": {"en": "After the end of training ({cutoff}): the models never saw this hour, so this is a real forecast, inside the 24-day test window.",
                     "uk": "Після завершення навчання ({cutoff}): моделі цієї години не бачили, тож це справжній прогноз, у межах 24-денного тестового вікна."},
    "st_after_some": {"en": "After the end of training ({cutoff}): the models never saw this hour, so this is a real forecast. It is a test row for H = {tested}; for H = {rest} the window touches the feed outage or passes the end of the data, so it is not scored.",
                      "uk": "Після завершення навчання ({cutoff}): моделі цієї години не бачили, тож це справжній прогноз. Для H = {tested} це рядок тестової вибірки; для H = {rest} вікно зачіпає збій джерела даних або виходить за кінець даних, тому його не оцінюють."},
    "st_after_none": {"en": "After the end of training ({cutoff}): the models never saw this hour, but it is outside the 24-day test window (its window or the 24h before it touches the feed outage, or the data ends).",
                      "uk": "Після завершення навчання ({cutoff}): моделі цієї години не бачили, але вона поза 24-денним тестовим вікном (її вікно або попередні 24 години зачіпають збій джерела даних, або дані закінчуються)."},
    "st_short": {"en": "Less than 7 days of data before this hour: the history features are incomplete.",
                 "uk": "Менше ніж 7 днів даних до цієї години: ознаки історії неповні."},
    "st_out_in": {"en": "This hour is inside the masked official feed outage ({outages}): alert data are missing or incomplete, so the inputs and the outcome are not reliable.",
                  "uk": "Ця година припадає на замаскований збій офіційного джерела даних ({outages}): дані про тривоги відсутні або неповні, тому вхідні дані та результат ненадійні."},
    "st_out_24": {"en": "The last 24 hours overlap the feed outage ({outages}): the 6h/24h features and the time since the last alert come from partial data, and no training or test row has inputs like these. Treat the numbers with care.",
                  "uk": "Останні 24 години перетинаються зі збоєм джерела даних ({outages}): ознаки за 6/24 години та час від останньої тривоги обчислено за неповними даними, а жоден рядок навчання чи тесту не має таких вхідних даних. Ставтеся до чисел обережно."},
    "st_out_7": {"en": "The 7-day lookback overlaps the feed outage ({outages}): those features are computed over the observed hours only, as on Sep 4-5 in the test window.",
                 "uk": "7-денне вікно історії перетинається зі збоєм джерела даних ({outages}): ці ознаки обчислено лише за спостережені години, як 4–5 вересня в тестовому вікні."},
    "round_note": {"en": "Forecasts are made on the hour: using {t:%H:%M} UTC, the last whole hour before {ts:%H:%M:%S} UTC.",
                   "uk": "Прогнози робляться на початку години: використано {t:%H:%M} UTC, останню повну годину перед {ts:%H:%M:%S} UTC."},
    # ---- predict.py --at: sentences and tables
    "when": {"en": "{hm} Kyiv time on {day} {month}", "uk": "{hm} за київським часом, {day} {month}"},
    "one_head": {"en": "{name}, {when}: {p1} chance a new alert starts within 1 hour, {p3} within 3, {p6} within 6.",
                 "uk": "{name}, {when}: ймовірність, що почнеться нова тривога, — {p1} протягом 1 години, {p3} протягом 3, {p6} протягом 6."},
    "one_started": {"en": "It did start, {gap} later", "uk": "Вона справді почалася через {gap}"},
    "one_started_down": {"en": " (the feed was down for part of this window, so the real start may be earlier).",
                         "uk": " (джерело даних на частину цього вікна не працювало, тож справжній початок міг бути раніше)."},
    "one_none": {"en": "No new alert started within 6 hours", "uk": "Нова тривога протягом 6 годин не почалася"},
    "one_next": {"en": "; the next came {gap} later.", "uk": "; наступна була через {gap}."},
    "one_unknown": {"en": "What happened next is not known (the data ends or the feed was down).",
                    "uk": "Що було далі, невідомо (дані закінчуються або джерело не працювало)."},
    "all_text": {"en": "All {n} oblasts, {when}: chance that a new alert starts within 1, 3 and 6 hours (table below). Highest within 1 hour: {names}.{outcome}",
                 "uk": "Усі області ({n}), {when}: ймовірність, що протягом 1, 3 і 6 годин почнеться нова тривога (таблиця нижче). Найвища протягом 1 години: {names}.{outcome}"},
    "all_outcome": {"en": " A new alert did start within 1 hour in {k} of {n} oblasts.", "uk": " Нова тривога справді почалася протягом 1 години в {k} з {n} областей."},
    "span_min": {"en": "{n} minutes", "uk": "{n} хв"},
    "span_hm": {"en": "{h} h {m:02d} min", "uk": "{h} год {m:02d} хв"},
    "span_dh": {"en": "{d} days {h} h", "uk": "{d} дн. {h} год"},
    "training_note": {"en": "This hour was part of the training data, so this is not a real forecast.", "uk": "Ця година входила до навчальних даних, тож це не справжній прогноз."},
    "all_oblasts": {"en": "All oblasts", "uk": "Усі області"},
    "at_header": {"en": "{who}, origin {t:%Y-%m-%d %H:%M} UTC ({hm} Kyiv time)", "uk": "{who}, година прогнозу {t:%Y-%m-%d %H:%M} UTC ({hm} за київським часом)"},
    "inputs": {"en": "Inputs: only alerts known at {t:%H:%M} UTC; neighbours from the hour before. Target: a new alert starts within the next H hours.",
               "uk": "Вхідні дані: лише тривоги, відомі станом на {t:%H:%M} UTC; сусідні області — за попередню годину. Ціль: протягом наступних H годин починається нова тривога."},
    "columns_help": {"en": "Columns per H: model = LightGBM probability; yday = same hour yesterday; freq = train frequency; now = same as now (one column for all H);\nhappened = a new alert started (n/a: after the end of the data or in the feed outage).\n",
                     "uk": "Стовпці для кожного H: модель = ймовірність LightGBM; вчора = та сама година вчора; частота = частота з навчальних даних; зараз = як зараз (один стовпець для всіх H);\nсталося = чи почалася нова тривога (н/д: після кінця даних або під час збою джерела).\n"},
    "col_oblast": {"en": "oblast", "uk": "область"},
    "col_now": {"en": "now", "uk": "зараз"},
    "col_model": {"en": "{H}h model", "uk": "{H} год модель"},
    "col_yday": {"en": "{H}h yday", "uk": "{H} год вчора"},
    "col_freq": {"en": "{H}h freq", "uk": "{H} год частота"},
    "col_happened": {"en": "{H}h happened", "uk": "{H} год сталося"},
    "yes": {"en": "yes", "uk": "так"},
    "no": {"en": "no", "uk": "ні"},
    "na": {"en": "n/a", "uk": "н/д"},
    "under_alert_at": {"en": "Under alert at {t:%H:%M} UTC: {yn}.\n", "uk": "Тривога о {t:%H:%M} UTC: {yn}.\n"},
    "one_cols": {"en": ["new alert within", "model", "same as now", "same hour yesterday", "train frequency", "happened"],
                 "uk": ["нова тривога протягом", "модель", "як зараз", "та сама година вчора", "навчальна частота", "сталося"]},
    "one_h": {"en": "{H} h", "uk": "{H} год"},
    "na_note": {"en": "n/a: the window is after the end of the data or touches the feed outage.", "uk": "н/д: вікно після кінця даних або зачіпає збій джерела."},
    "next_alert": {"en": "\nNext new alert after {t:%H:%M} UTC: {nxt:%Y-%m-%d %H:%M} UTC, {after} later{caveat}.",
                   "uk": "\nНаступна нова тривога після {t:%H:%M} UTC: {nxt:%Y-%m-%d %H:%M} UTC, через {after}{caveat}."},
    "next_caveat": {"en": " (the feed was down {outages}, so an earlier alert may be missing)", "uk": " (джерело не працювало {outages}, тож попередня тривога могла бути пропущена)"},
    "no_next": {"en": "\nNo new alert after this hour before the official data ends.", "uk": "\nПісля цієї години до кінця офіційних даних нових тривог немає."},
    "map_written": {"en": "Map written to {path}.", "uk": "Карту записано в {path}."},
    "map_not_written": {"en": "Map not written: {err}", "uk": "Карту не записано: {err}"},
    # ---- live_api.py --now
    "live_head": {"en": "Live forecast from the Ukraine Alarm API for the hour starting {t:%Y-%m-%d %H:%M} UTC ({hm} Kyiv time), the last completed hour: the chance that a NEW alert starts within the next 1, 3 and 6 hours. Only what the API reported by that hour is used; alerts that started later are not. {model_text}",
                  "uk": "Прогноз у реальному часі за даними Ukraine Alarm API для години, що починається {t:%Y-%m-%d %H:%M} UTC ({hm} за київським часом), останньої завершеної години: ймовірність того, що протягом наступних 1, 3 і 6 годин почнеться НОВА тривога. Використано лише те, що API повідомило до цієї години; тривоги, які почалися пізніше, не враховано. {model_text}"},
    "model_v1": {"en": "Model: LightGBM v1, trained on official data to 2026-08-07, not retrained (--model v2 for the newer one).",
                 "uk": "Модель: LightGBM v1, навчена на офіційних даних до 2026-08-07, без донавчання (--model v2 — новіша)."},
    "model_v2": {"en": "Model: LightGBM v2, trained on the combined official + API data (to 2026-10-17 for this forecast), the same features and settings as v1 (--model v1 for the older one).",
                 "uk": "Модель: LightGBM v2, навчена на об'єднаних офіційних даних і даних API (до 2026-10-17 для цього прогнозу), ті самі ознаки й налаштування, що й у v1 (--model v1 — старіша)."},
    "map_live": {"en": "Live forecast from the Ukraine Alarm API. ", "uk": "Прогноз у реальному часі за даними Ukraine Alarm API. "},
    "map_replay": {"en": "Replay of a past hour from the official data, not a live forecast. Model: LightGBM v1 (round 13), trained on official data to 2026-08-07.",
                   "uk": "Відтворення минулої години за офіційними даними, а не прогноз у реальному часі. Модель: LightGBM v1 (раунд 13), навчена на офіційних даних до 2026-08-07."},
    "ago_now": {"en": "just now", "uk": "щойно"},
    "ago_min": {"en": "{n:.0f} min before now", "uk": "{n:.0f} хв тому"},
    "ago_h": {"en": "{n:.1f} h before now", "uk": "{n:.1f} год тому"},
    "fresh_head": {"en": "Freshness: now is {now:%Y-%m-%d %H:%M} UTC. The newest alert start in the API is {start:%Y-%m-%d %H:%M} UTC ({ago})",
                   "uk": "Свіжість даних: зараз {now:%Y-%m-%d %H:%M} UTC. Найновіший початок тривоги в API — {start:%Y-%m-%d %H:%M} UTC ({ago})"},
    "fresh_end": {"en": ", the newest end {end:%Y-%m-%d %H:%M} UTC", "uk": ", найновіший кінець — {end:%Y-%m-%d %H:%M} UTC"},
    "fresh_upd": {"en": "; its active-alerts list was last updated {upd:%Y-%m-%d %H:%M} UTC ({ago})", "uk": "; список активних тривог востаннє оновлено {upd:%Y-%m-%d %H:%M} UTC ({ago})"},
    "fresh_tail": {"en": ". A quiet spell and an API that is behind look the same from here.", "uk": ". Затишшя і відставання API звідси виглядають однаково."},
    "left_out": {"en": "Left out: alerts in districts that are not in our raion list: {names}.", "uk": "Не враховано: тривоги в районах, яких немає в нашому списку районів: {names}."},
    "cal_v1": {"en": "the forward test (41 days, 2026-09-07 to 10-17, same models)", "uk": "прямому тесті (41 день, 2026-09-07 – 10-17, ті самі моделі)"},
    "cal_v2": {"en": "the v2 test window (20 days, 2026-09-28 to 10-17)", "uk": "тестовому вікні v2 (20 днів, 2026-09-28 – 10-17)"},
    "cal_low": {"en": "a bit low", "uk": "трохи занижені"},
    "cal_high": {"en": "a bit high", "uk": "трохи завищені"},
    "cal_mid": {"en": "about right on average", "uk": "в середньому майже правильні"},
    "cal_item": {"en": "{p:.3f} against {o:.3f} at {H} h", "uk": "{p:.3f} проти {o:.3f} на {H} год"},
    "cal_note": {"en": "Note: in {label} the model predicted {word} (mean predicted against observed): {items}. Nothing is recalibrated{tail}",
                 "uk": "Примітка: у {label} модель давала {word} ймовірності (середній прогноз проти спостереженого): {items}. Нічого не перекалібровано{tail}"},
    "cal_tail_low": {"en": "; read the probabilities as slightly low.", "uk": "; читайте ймовірності як трохи занижені."},
    "cal_tail": {"en": ".", "uk": "."},
    "above_help": {"en": "'above' = at or above the frozen threshold (max F1 on the last train week): {thr}. Sorted by the 1 h probability.",
                   "uk": "'вище' = не нижче за зафіксований поріг (максимум F1 за останній тиждень навчання): {thr}. Відсортовано за ймовірністю на 1 год."},
    "thr_item": {"en": "{H} h {v:.3f}", "uk": "{H} год {v:.3f}"},
    "live_cols": {"en": ["oblast", "alert now", "1 h", "above", "3 h", "above ", "6 h", "above  "],
                  "uk": ["область", "тривога зараз", "1 год", "вище", "3 год", "вище ", "6 год", "вище  "]},
    "logged": {"en": "\nLogged {n} forecasts (24 oblasts x 3 horizons) to {path}.", "uk": "\nЗаписано прогнозів: {n} (24 області × 3 горизонти) у {path}."},
    # ---- the map page
    "pg_title": {"en": "Air-raid alert forecast map", "uk": "Карта прогнозу повітряних тривог"},
    "pg_aria": {"en": "Map of Ukraine by oblast coloured by the probability of a new air-raid alert; every oblast can be selected with the keyboard",
                "uk": "Карта України по областях, пофарбована за ймовірністю нової повітряної тривоги; кожну область можна вибрати з клавіатури"},
    "pg_nodata": {"en": "no data", "uk": "немає даних"},
    "pg_bins": {"en": ["under 10%", "10 to 25%", "25 to 50%", "50 to 75%", "75% and over"], "uk": ["менше 10%", "10–25%", "25–50%", "50–75%", "75% і більше"]},
    "pg_lg_nd": {"en": "no data (not modelled)", "uk": "немає даних (не моделюється)"},
    "pg_lg_above": {"en": "at or above the frozen threshold", "uk": "не нижче зафіксованого порога"},
    "pg_lg_below": {"en": "below it", "uk": "нижче нього"},
    "pg_lg_alert": {"en": "under alert at the origin hour", "uk": "тривога на годину прогнозу"},
    "pg_thr_item": {"en": "{h} h: {v:.3f}", "uk": "{h} год: {v:.3f}"},
    "pg_h2": {"en": "All oblasts", "uk": "Усі області"},
    "pg_th": {"en": ["Oblast", "Alert at origin hour", "1 h", "3 h", "6 h"], "uk": ["Область", "Тривога на годину прогнозу", "1 год", "3 год", "6 год"]},
    "pg_alert_yes": {"en": "under alert", "uk": "тривога"},
    "pg_alert_no": {"en": "no", "uk": "ні"},
    "pg_above": {"en": "above", "uk": "вище"},
    "pg_below": {"en": "below", "uk": "нижче"},
    "pg_footer": {"en": "A study model, not for safety decisions: follow the official alerts.", "uk": "Навчальна модель, не для рішень щодо безпеки: слідкуйте за офіційними сповіщеннями про тривогу."},
    # ---- the map page (round 19: product page; the Ukrainian text is the default)
    "pg_thr": {"en": "Frozen thresholds (maximum F1 on the last training or validation week, never on test data): {thr}.",
               "uk": "Зафіксовані пороги (максимум F1 за останній тиждень навчання чи валідації, ніколи не за тестовими даними): {thr}."},
    "ui_brand": {"en": "Alert forecast", "uk": "Прогноз тривог"},
    "ui_sentence": {"en": "Chance that a new air-raid alert starts in an oblast within 1, 3 or 6 hours",
                    "uk": "Ймовірність, що в області почнеться нова повітряна тривога протягом 1, 3 або 6 годин"},
    "ui_how": {"en": "How to read", "uk": "Як читати"},
    "ui_how_title": {"en": "How to read this map", "uk": "Як читати карту"},
    "ui_how_items": {"en": [["Colour", "The colour of an oblast is the probability that a NEW alert starts in it within the chosen 1, 3 or 6 hours after the origin hour. The lighter the oblast, the higher the probability: from dark blue (under 10%) to near white (75% and over)."],
                            ["\u25b2 and \u25bd", "\u25b2 means the probability is at or above the model's frozen threshold, \u25bd that it is below. Each horizon has its own threshold (the maximum of F1 on the last training or validation week, never on test data)."],
                            ["! = alert", "The red \"!\" means an alert is running in the oblast at the origin hour, not at the moment you open the page."],
                            ["Selecting", "Click an oblast (or Tab to it and press Enter) to see the three horizons and how the forecast changed over the last runs. Esc clears the selection."],
                            ["Grey hatched areas", "Not modelled: Crimea and Luhansk oblast (no data)."],
                            ["Freshness", "The \"Data\" pill shows how long ago this page was made. The older it is, the less it tells you: run predict.py --now again."]],
                   "uk": [["Колір", "Колір області — ймовірність того, що в ній почнеться НОВА тривога протягом обраних 1, 3 або 6 годин після години прогнозу. Чим світліша область, тим вища ймовірність: від темно-синього (менше 10%) до майже білого (75% і більше)."],
                          ["\u25b2 і \u25bd", "\u25b2 — ймовірність не нижча за зафіксований поріг моделі, \u25bd — нижча. Поріг свій для кожного горизонту (максимум F1 за останній тиждень навчання чи валідації, ніколи не за тестовими даними)."],
                          ["! — тривога", "Червоний знак «!» — в області триває тривога на годину прогнозу, а не на мить відкриття сторінки."],
                          ["Вибір", "Натисніть на область (або Tab і Enter), щоб побачити три горизонти й те, як змінювався прогноз за останні прогони. Esc знімає вибір."],
                          ["Сірі штриховані області", "Не моделюються: Крим і Луганська область (немає даних)."],
                          ["Свіжість", "Позначка «Дані» показує, скільки минуло від створення цієї сторінки. Чим довше, тим менше вона каже: запустіть predict.py --now ще раз."]]},
    "ui_about": {"en": "About the data and the model", "uk": "Про дані й модель"},
    "ui_close": {"en": "Close", "uk": "Закрити"},
    "ui_fresh_live": {"en": "Data: {ago}", "uk": "Дані: {ago}"},
    "ui_fresh_static": {"en": "Data: made {made:%H:%M} UTC", "uk": "Дані: створено {made:%H:%M} UTC"},
    "ui_replay_pill": {"en": "Replay of a past hour", "uk": "Відтворення минулої години"},
    "ui_ago": {"en": ["just now", "{n} min ago", "{n} h ago", "{n} d ago"], "uk": ["щойно", "{n} хв тому", "{n} год тому", "{n} дн. тому"]},
    "ui_stale": {"en": "Out of date: run predict.py --now again", "uk": "Застаріло: запустіть predict.py --now ще раз"},
    "ui_origin": {"en": "Origin hour: {hm} Kyiv, {t:%Y-%m-%d %H:%M} UTC", "uk": "Година прогнозу: {hm} (Київ), {t:%Y-%m-%d %H:%M} UTC"},
    "ui_model": {"en": "model {model}", "uk": "модель {model}"},
    "ui_seg": {"en": "Forecast horizon", "uk": "Горизонт прогнозу"},
    "ui_seg_item": {"en": "{H} h", "uk": "{H} год"},
    "ui_top_title": {"en": "Highest probability", "uk": "Найвища ймовірність"},
    "ui_top_sub": {"en": "within {H} h \u00b7 click an oblast for details", "uk": "протягом {H} год \u00b7 натисніть на область"},
    "ui_all": {"en": "All oblasts", "uk": "Усі області"},
    "ui_back": {"en": "\u2190 All oblasts", "uk": "\u2190 Усі області"},
    "ui_big_cap": {"en": "chance of a new alert within {H} h", "uk": "ймовірність нової тривоги протягом {H} год"},
    "ui_thr_above": {"en": "at or above the threshold {thr}", "uk": "не нижче порога {thr}"},
    "ui_thr_below": {"en": "below the threshold {thr}", "uk": "нижче порога {thr}"},
    "ui_bars": {"en": "Three horizons", "uk": "Три горизонти"},
    "ui_bars_legend": {"en": "\u2502 model threshold", "uk": "\u2502 поріг моделі"},
    "ui_alert_yes": {"en": "Alert running (at the origin hour)", "uk": "Тривога триває (на годину прогнозу)"},
    "ui_alert_no": {"en": "No alert (at the origin hour)", "uk": "Тривоги немає (на годину прогнозу)"},
    "ui_hist_title": {"en": "How the forecast changed, {H} h", "uk": "Як змінювався прогноз, {H} год"},
    "ui_hist_n": {"en": "last {n} runs, up to {last}", "uk": "останні прогони: {n}, до {last}"},
    "ui_hist_none": {"en": "No earlier runs yet: the chart appears after the next predict.py --now runs.",
                     "uk": "Ще немає попередніх прогонів: графік з'явиться після наступних запусків predict.py --now."},
    "ui_hist_replay": {"en": "This is a replay of a past hour: there is no run history.", "uk": "Це відтворення минулої години: історії прогонів немає."},
    "ui_hist_thr": {"en": "threshold", "uk": "поріг"},
    "ui_nodata_detail": {"en": "{name}: no data (not modelled)", "uk": "{name}: немає даних (не моделюється)"},
    "ui_sheet": {"en": "Details", "uk": "Деталі"},
    "ui_noscript": {"en": "The map needs JavaScript; every number is in the table below.", "uk": "Для карти потрібен JavaScript; усі числа є в таблиці нижче."},
    "ui_rel_above": {"en": "at or above the threshold", "uk": "не нижче порога"},
    "ui_rel_below": {"en": "below the threshold", "uk": "нижче порога"},
    "ui_rank": {"en": "rank {n}", "uk": "місце {n}"},
    "pg_warn_prefixes": {"en": ("TRAINING",), "uk": ("ПЕРІОД НАВЧАННЯ",)},
}


def T(key, lang="en", **fields):
    """The text for `key` in `lang`, filled with `fields`; lists and tuples are returned as they are."""
    v = S[key][lang]
    return v.format(**fields) if isinstance(v, str) else v
