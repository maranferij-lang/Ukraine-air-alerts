"""Tests for src/telegram_oblasts.py: python scripts/test_telegram_parser.py

The first block is the upstream bug that must not come back: the volunteer feed's substring matching
sent "подільський" to Lviv and "прилуцький" to Volyn."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_inputs
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


def main():
    bad = [(t, want, mentioned(t)) for t, want in CASES if mentioned(t) != want]
    for t, want, got in bad:
        print(f"FAIL {t!r}: wanted {sorted(want)}, got {sorted(got)}")
    names = set(load_inputs()[0]["oblast"].unique())
    assert set(UNITS) == names, (set(UNITS) ^ names)
    assert not bad, f"{len(bad)} of {len(CASES)} cases failed"
    print(f"ok: {len(CASES)} cases; the parser knows exactly the {len(UNITS)} units of the alert data")


if __name__ == "__main__":
    main()
