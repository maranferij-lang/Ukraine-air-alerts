"""Where each of the 24 units is: its administrative centre (latitude, longitude), written by hand (round 22).

Used for the weather points (one per unit) and to say which neighbours lie east or south of an oblast (src/features_extra.py).
Approximate to about 0.01 degrees; nothing here needs more. Kyiv City and Kyivska oblast share Kyiv, so neither is east or south of the other.
"""
CENTRES = {
    "Cherkaska oblast": (49.44, 32.06),          # Cherkasy
    "Chernihivska oblast": (51.50, 31.29),       # Chernihiv
    "Chernivetska oblast": (48.29, 25.94),       # Chernivtsi
    "Dnipropetrovska oblast": (48.46, 35.05),    # Dnipro
    "Donetska oblast": (48.02, 37.80),           # Donetsk
    "Ivano-Frankivska oblast": (48.92, 24.71),   # Ivano-Frankivsk
    "Kharkivska oblast": (49.99, 36.23),         # Kharkiv
    "Khersonska oblast": (46.64, 32.62),         # Kherson
    "Khmelnytska oblast": (49.42, 26.98),        # Khmelnytskyi
    "Kirovohradska oblast": (48.51, 32.26),      # Kropyvnytskyi
    "Kyiv City": (50.45, 30.52),                 # Kyiv
    "Kyivska oblast": (50.45, 30.52),            # Kyiv (the oblast's administrative centre)
    "Lvivska oblast": (49.84, 24.03),            # Lviv
    "Mykolaivska oblast": (46.97, 31.99),        # Mykolaiv
    "Odeska oblast": (46.48, 30.73),             # Odesa
    "Poltavska oblast": (49.59, 34.55),          # Poltava
    "Rivnenska oblast": (50.62, 26.25),          # Rivne
    "Sumska oblast": (50.91, 34.80),             # Sumy
    "Ternopilska oblast": (49.55, 25.59),        # Ternopil
    "Vinnytska oblast": (49.23, 28.47),          # Vinnytsia
    "Volynska oblast": (50.75, 25.33),           # Lutsk
    "Zakarpatska oblast": (48.62, 22.30),        # Uzhhorod
    "Zaporizka oblast": (47.84, 35.14),          # Zaporizhzhia
    "Zhytomyrska oblast": (50.25, 28.66),        # Zhytomyr
}


def upwind_neighbours(neighbours):
    """{oblast: [neighbours whose centre is east (larger longitude) or south (smaller latitude) of its own]} from a {oblast: [neighbours]} map."""
    out = {}
    for ob, nbs in neighbours.items():
        lat0, lon0 = CENTRES[ob]
        out[ob] = [n for n in nbs if CENTRES[n][1] > lon0 or CENTRES[n][0] < lat0]
    return out
