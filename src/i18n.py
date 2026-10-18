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
    "pg_h1": {"en": "Chance that a new air-raid alert starts, per oblast", "uk": "Імовірність початку нової повітряної тривоги, по областях"},
    "pg_sub": {"en": "Origin hour <b>{t:%Y-%m-%d %H:%M} UTC</b> ({hm} Kyiv time) · page made {made:%Y-%m-%d %H:%M} UTC · model <b>{model}</b> ({version})",
               "uk": "Година прогнозу <b>{t:%Y-%m-%d %H:%M} UTC</b> ({hm} за київським часом) · сторінку створено {made:%Y-%m-%d %H:%M} UTC · модель <b>{model}</b> ({version})"},
    "pg_note": {"en": "{model_text} The colour is the probability that a NEW alert starts within the next 1, 3 or 6 hours after the origin hour (switch below). Under alert = at the origin hour, not at the moment you open this page.",
                "uk": "{model_text} Колір — це ймовірність того, що протягом 1, 3 або 6 годин після години прогнозу почнеться НОВА тривога (перемикач нижче). «Тривога» — це стан на годину прогнозу, а не на момент відкриття цієї сторінки."},
    "pg_tab": {"en": "within {H} {unit}", "uk": "протягом {H} {unit}"},
    "pg_unit1": {"en": "hour", "uk": "години"},
    "pg_unit3": {"en": "hours", "uk": "годин"},
    "pg_aria": {"en": "Map of Ukraine by oblast coloured by the probability of a new air-raid alert; the same numbers are in the table below the map",
                "uk": "Карта України по областях, пофарбована за ймовірністю нової повітряної тривоги; ті самі числа є в таблиці під картою"},
    "pg_nodata": {"en": "no data", "uk": "немає даних"},
    "pg_bins": {"en": ["under 10%", "10 to 25%", "25 to 50%", "50 to 75%", "75% and over"], "uk": ["менше 10%", "10–25%", "25–50%", "50–75%", "75% і більше"]},
    "pg_lg_nd": {"en": "no data (not modelled)", "uk": "немає даних (не моделюється)"},
    "pg_lg_above": {"en": "at or above the frozen threshold", "uk": "не нижче зафіксованого порога"},
    "pg_lg_below": {"en": "below it", "uk": "нижче нього"},
    "pg_lg_alert": {"en": "under alert at the origin hour", "uk": "тривога на годину прогнозу"},
    "pg_thr": {"en": "Frozen thresholds (maximum F1 on the last training or validation week, never on test data): {thr}. Colour bins are the same for all three horizons.",
               "uk": "Зафіксовані пороги (максимум F1 за останній тиждень навчання чи валідації, ніколи не за тестовими даними): {thr}. Колірні інтервали однакові для всіх трьох горизонтів."},
    "pg_thr_item": {"en": "{h} h: {v:.3f}", "uk": "{h} год: {v:.3f}"},
    "pg_h2": {"en": "All oblasts", "uk": "Усі області"},
    "pg_th": {"en": ["Oblast", "Alert at origin hour", "1 h", "3 h", "6 h"], "uk": ["Область", "Тривога на годину прогнозу", "1 год", "3 год", "6 год"]},
    "pg_alert_yes": {"en": "under alert", "uk": "тривога"},
    "pg_alert_no": {"en": "no", "uk": "ні"},
    "pg_above": {"en": "above", "uk": "вище"},
    "pg_below": {"en": "below", "uk": "нижче"},
    "pg_footer": {"en": "A study model, not for safety decisions: follow the official alerts.", "uk": "Навчальна модель, не для рішень щодо безпеки: слідкуйте за офіційними сповіщеннями про тривогу."},
    "pg_panel_default": {"en": "Hover over an oblast, or tap it, to see its numbers here.", "uk": "Наведіть курсор на область або торкніться її, щоб побачити тут її числа."},
    "pg_panel_alert": {"en": "under alert at the origin hour", "uk": "тривога на годину прогнозу"},
    "pg_panel_calm": {"en": "no alert at the origin hour", "uk": "тривоги на годину прогнозу немає"},
    "pg_panel_h": {"en": "{h} h {p:.3f} ({rel} {thr:.3f})", "uk": "{h} год {p:.3f} ({rel} {thr:.3f})"},
    "pg_panel_at": {"en": "at or above the threshold", "uk": "не нижче порога"},
    "pg_panel_under": {"en": "below the threshold", "uk": "нижче порога"},
    "pg_panel_nohas": {"en": "This browser cannot show the details on hover; the table below the map has every number.", "uk": "Цей браузер не показує подробиць при наведенні; усі числа є в таблиці під картою."},
    "pg_panel_nodata": {"en": "no data (not modelled)", "uk": "немає даних (не моделюється)"},
    "pg_warn_prefixes": {"en": ("TRAINING",), "uk": ("ПЕРІОД НАВЧАННЯ",)},
}


def T(key, lang="en", **fields):
    """The text for `key` in `lang`, filled with `fields`; lists and tuples are returned as they are."""
    v = S[key][lang]
    return v.format(**fields) if isinstance(v, str) else v
