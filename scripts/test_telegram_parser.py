"""Tests for src/telegram_oblasts.py: python scripts/test_telegram_parser.py

The first block is the upstream bug that must not come back: the volunteer feed's substring matching
sent "подільський" to Lviv and "прилуцький" to Volyn."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_inputs
from src.telegram_features import threat_flags
from src.telegram_oblasts import UNITS, mentioned

K, KC = "Kyivska oblast", "Kyiv City"
CASES = [
    # the two upstream substring bugs
    ("Подільський район", set()),
    ("БпЛА на Подільський район", set()),
    ("Прилуцький район", {"Chernihivska oblast"}),
    ("Ударні БпЛА на Прилуки.", {"Chernihivska oblast"}),
    ("БпЛА на Луцьк", {"Volynska oblast"}),
    ("Луцький район, курс на захід", {"Volynska oblast"}),
    # oblast vs city stems
    ("БпЛА на Київ з півдня", {KC}), ("БпЛА на Київщину", {K}), ("Київщина: групи БпЛА", {K}),
    ("Київська область, Бровари", {K}), ("повз Києва", {KC}),
    ("Дніпровський район Києва", {KC}), ("БпЛА на Дніпро", {"Dnipropetrovska oblast"}),
    ("Дніпропетровщина: БпЛА на Павлоград", {"Dnipropetrovska oblast"}),
    # hyphenated compounds do not leak into other oblasts
    ("Кам'янець-Подільський", {"Khmelnytska oblast"}), ("Кам’янець-Подільський район", {"Khmelnytska oblast"}),
    ("Переяслав-Хмельницький", {K}), ("Могилів-Подільський", {"Vinnytska oblast"}),
    ("Новоград-Волинський", {"Zhytomyrska oblast"}), ("Володимир-Волинський", {"Volynska oblast"}),
    ("Івано-Франківськ", {"Ivano-Frankivska oblast"}), ("Білгород-Дністровський", {"Odeska oblast"}),
    ("Харків-Київ", {"Kharkivska oblast", KC}),
    # near misses that must stay empty
    ("Сумно", set()), ("Миколаївка", set()), ("Тростянець", set()), ("Малинівка", set()),
    ("рівно о 5:00", set()), ("Бучач", {"Ternopilska oblast"}), ("Буча", {K}),
    ("Славута", {"Khmelnytska oblast"}), ("Славутич", {K}),
    # declensions
    ("Харківщина", {"Kharkivska oblast"}), ("на Харківщині", {"Kharkivska oblast"}),
    ("Вінничині курс н.п.Тростянець", {"Vinnytska oblast"}), ("у Запорізькій області", {"Zaporizka oblast"}),
    ("БпЛА на Запоріжжя", {"Zaporizka oblast"}), ("Миколаївщина", {"Mykolaivska oblast"}),
    ("по Одесі", {"Odeska oblast"}), ("Одещина", {"Odeska oblast"}), ("в Сумах", {"Sumska oblast"}),
    ("Сумщина, Охтирка", {"Sumska oblast"}), ("Чернігівщина: повз Славутич ➡️ Київщини", {"Chernihivska oblast", K}),
    ("Донеччину та Запорізьку область", {"Donetska oblast", "Zaporizka oblast"}),
    ("Херсонщина, Нова Каховка", {"Khersonska oblast"}), ("Кривий Ріг", {"Dnipropetrovska oblast"}),
    ("Біла Церква", {K}), ("Рівне", {"Rivnenska oblast"}), ("Закарпаття, Ужгород", {"Zakarpatska oblast"}),
    ("Крим, Луганськ", set()),
    # genitive alternations and dropped apostrophes seen in the posts
    ("Реактивні БпЛА в напрямку Борисполя з півдня.", {K}), ("Реактивний БпЛА у напрямку Обухова/Українки", {K}),
    ("у напрямку Гостомеля", {K}), ("БпЛА на Камянське.", {"Dnipropetrovska oblast"}),
    ("Реактивні БпЛА в р-ні. Бобровиці курс південний.", {"Chernihivska oblast"}), ("Ірпеня", {K}),
]


FLAGS = [  # (text, flags expected)
    ("🚀КР на півночі Херсонщини в напрямку Миколаївщини.", {"tg_missile"}),
    ("Крилаті ракети повз Шаргород", {"tg_missile"}),
    ("Ракета на півночі Чернігівщини, вектор - Київ", {"tg_missile"}),
    ("🚀Швидкісні цілі у Запорізькій області", {"tg_missile"}), ("Швидкісна ціль на Харків!", {"tg_missile"}),
    ("☄️ Загроза застосування балістичного озброєння з півночі.", {"tg_ballistic"}),
    ("Кинджал на Одещину", {"tg_ballistic", "tg_missile"}),
    ("🚀 Пуски КАБ на Харківщині.", {"tg_kab"}), ("КАБи на північ Сумщини!", {"tg_kab"}),
    ("Пуски керованих авіаційних бомб ворожою тактичною авіацією", {"tg_kab"}),
    ("Активність ворожої тактичної авіації на східному напрямку", {"tg_kab"}),
    ("🛵 БпЛА на Харків з півночі.", set()), ("Реактивний БпЛА на Київщину", set()), ("Кабмін ухвалив рішення", set()),
    ("📢 Відбій загрози застосування балістичного озброєння.", set()),
    ("Відбій загрози для Миколаївської області. 🚀КР на Одещину", {"tg_missile"}),
    ("⚡️ ЗБИТО/ПОДАВЛЕНО 26 РАКЕТ ТА 515 ВОРОЖИХ БПЛА", set()),
]


flags = threat_flags


def main():
    bad = [(t, want, mentioned(t)) for t, want in CASES if mentioned(t) != want]
    for t, want, got in bad:
        print(f"FAIL {t!r}: wanted {sorted(want)}, got {sorted(got)}")
    bad_flags = [(t, want, flags(t)) for t, want in FLAGS if flags(t) != want]
    for t, want, got in bad_flags:
        print(f"FAIL flags {t!r}: wanted {sorted(want)}, got {sorted(got)}")
    assert not bad_flags, f"{len(bad_flags)} of {len(FLAGS)} flag cases failed"
    names = set(load_inputs()[0]["oblast"].unique())
    assert set(UNITS) == names, (set(UNITS) ^ names)
    assert not bad, f"{len(bad)} of {len(CASES)} cases failed"
    print(f"ok: {len(CASES)} oblast cases and {len(FLAGS)} threat-flag cases; the parser knows exactly the {len(UNITS)} units of the alert data")


if __name__ == "__main__":
    main()
