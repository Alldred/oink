"""Weather-aware whimsical day lines for the dashboard."""

from __future__ import annotations

import random
from datetime import date, timedelta

from weather.client import WeatherData

# Sky buckets keyed from WMO codes (and a few weather overlays).
Bucket = str

# Day sentence covers 08:00–21:00. Flip to overnight at 20:00 so the
# evening line talks about tonight instead of the last hour of "the day".
DAY_START_HOUR = 8
DAY_END_HOUR = 21
OVERNIGHT_FLIP_HOUR = 20

# Swappable animal pools. Use {Wet}/{wet}, {Smug}/{smug}, etc. in templates.
# Capitalised form for sentence starts; lower form mid-sentence.
_WET = ("ducks", "frogs", "otters", "newts")
_SMUG = ("robins", "pigeons", "foxes", "hedgehogs")
_BOSS = ("ducks", "frogs", "otters", "cows", "sheep")
_HOT = ("bees", "birds", "butterflies", "squirrels")
_FOG = ("owls", "pigeons", "moles", "badgers")
_COLD = ("robins", "penguins", "foxes", "hedgehogs", "pigeons")
_PUDDLE = ("ducks", "frogs", "snails", "newts")

# Templates may include {Wet}, {wet}, {Smug}, … — filled at pick time.
_LINES: dict[Bucket, tuple[str, ...]] = {
    "clear": (
        "Hot out. {Hot} have booked the pavement",
        "Wear a hat. Then find a fridge. Then sit in it",
        "Sunny. Pigeons will take the credit",
        "The sun is out today. {Hot} are too busy to talk",
        "Clear skies. {Hot} are in charge until tea",
        "Warm day. Wear a hat. Then a bigger hat. Then give up",
        "Bright out. Ice cream is in big trouble",
        "Blue sky. {Hot} look extremely pleased",
        "Sunny. Perfect weather for doing absolutely nothing",
        "Hot pavement. {Hot} say stay put",
        "Clear and warm. Pigeons arranged this, apparently",
    ),
    "cloudy": (
        "Grey day. Sheep clouds are herding the town",
        "Cloudy. {Boss} say it's a sit-still day",
        "Wear a jumper. Then another. Then stare at the sky",
        "Soft cloud day. Pigeons look very official",
        "The day put on a woolly jumper",
        "Cloudy. {Smug} are taking notes",
        "Grey lid on the sky. {Boss} approve",
        "Not much sun. {Smug} still look busy",
    ),
    "fog": (
        "Foggy. {Fog} are running the bus stops",
        "Hard to see. Wear a coat. Then walk into a cloud",
        "Foggy. The town is playing hide and seek",
        "Soft morning. Pigeons know the way. Apparently",
        "Foggy. {Fog} prefer it this way",
        "Can't see much. Good day for {fog}",
        "Thick fog. {Fog} have the advantage",
    ),
    "drizzle": (
        "Drizzle. Snails have taken the footpaths",
        "The sky is dribbling on purpose",
        "Light wet. {Puddle} are queueing for the puddles",
        "Drizzle. Wear a coat. Then a second coat. Then laugh",
        "Rain so shy it's almost a rumour. Pigeons still claim it",
        "Tiny rain. {Wet} look quietly hopeful",
        "Drizzle. {Puddle} say this will do nicely",
        "Soft wet day. {Wet} are already outside",
    ),
    "showers": (
        "Rain later. Pigeons will pretend it was their idea",
        "Wear wellies. Then another pair. (You can't)",
        "A splash at tea time. {Wet} are already queuing",
        "Showers later. Pigeons arranged it, apparently",
        "Mostly dry… then a sneaky splash. {Wet} approve",
        "Puddles appear later. {Puddle} look ready",
        "Showers about. {Wet} have cleared their diaries",
        "A wet blip later. {Puddle} will be delighted",
        "Rain later. {Wet} are practising their smug faces",
        "Splash expected. Wear wellies. Then do a little dance",
    ),
    "heavy": (
        "Wet day. {Wet} have taken over",
        "It's pouring. {Wet} look very pleased",
        "Wear socks. Then dry socks. Then give up",
        "Heavy rain. {Wet} have claimed the roads",
        "The sky tipped its bucket over. {Wet} rule",
        "Soaking day. Pigeons will pretend it was their idea",
        "Proper wet. {Wet} declare a holiday",
        "It's chucking it down. {Puddle} are thrilled",
        "Heavy rain. Stay in, or join the {wet}",
        "Buckets of rain. {Wet} say come on in",
    ),
    "snow": (
        "Cold feathers falling down. {Cold} would love this",
        "Snowy. Wear a jumper. Then another. Then another?",
        "White day. {Smug} look far too pleased",
        "Snow about. Good day to spot antelope in coats",
        "Snow day. {Cold} are quietly celebrating",
        "White stuff. Wear a jumper. Then find a sled. Then invent one",
    ),
    "cold": (
        "Cold out. {Smug} look smug in tiny scarves",
        "Wear a jumper. Then another. Then another?",
        "Chilly. {Cold} say roll up and wait",
        "Cold. Breathing out makes you look like a dragon",
        "Nippy. Pigeons look rounder than usual",
        "Chilly. Wear a jumper. Then hug a radiator",
        "Cold out. {Cold} have the right idea",
        "Brisk. {Smug} pretend they meant to be out",
    ),
    "mild": (
        "Quiet weather. Pigeons are taking notes",
        "Mild day. {Boss} have no strong opinions",
        "Not much fuss today. {Smug} still look busy",
        "Gentle day. Wear a jumper. Or don't. Your call",
        "Mild. Good day for a slow walk and a biscuit",
        "Nothing dramatic. {Boss} are fine with that",
        "Soft day. Pigeons will take the credit anyway",
    ),
}

_INDOOR_BITS: tuple[str, ...] = (
    "eat biscuits",
    "sing songs",
    "learn piano",
    "teach the dog maths",
    "invent a dance",
    "draw a map of nowhere",
    "count the raindrops (good luck)",
    "make a tiny fort",
    "build a sock tower",
    "name all the clouds",
)

_ANTELOPE: tuple[str, ...] = (
    "Clear skies. Good day to spot antelope",
    "Quiet weather. Antelope may be about",
    "Mild and dry. Keep an eye out for antelope",
    "Soft day. Antelope prefer this sort of weather",
    "Cloudy. Antelope blend in better today",
)

_STORM_WAIT: tuple[str, ...] = (
    "Wait for the storm to pass",
    "Wait for the rain to finish",
    "Wait for the sky to calm down",
    "Wait for the thunder to get bored",
)


def remaining_daytime_hours(hour: int) -> range:
    """Hour indexes still ahead in the 8am–9pm window. Empty after the 8pm flip."""
    hour = int(hour)
    if hour < DAY_START_HOUR or hour >= OVERNIGHT_FLIP_HOUR:
        return range(0, 0)
    return range(hour, DAY_END_HOUR)


def is_overnight(hour: int) -> bool:
    """True from 8pm until 8am (the overnight sentence slot)."""
    hour = int(hour)
    return hour >= OVERNIGHT_FLIP_HOUR or hour < DAY_START_HOUR


def _slice_hours(series: tuple, hours: range) -> list:
    n = len(series)
    return [series[h] for h in hours if 0 <= h < n]


def _remaining_slot(weather: WeatherData, hour: int) -> tuple[list[int], float, float, float]:
    """Codes, precip sum, and temp range for the active slot's remaining hours.

    Until 8pm the day sentence looks ahead to 9pm. From 8pm the slot is
    overnight through 8am, which runs into tomorrow morning; after midnight
    it is today's pre-8am hours.
    """
    hour = int(hour)
    codes: list[int] = []
    precips: list[float] = []
    temps: list[float] = []

    def take(
        code_series: tuple,
        precip_series: tuple,
        temp_series: tuple,
        hours: range,
    ) -> None:
        codes.extend(int(c) for c in _slice_hours(code_series, hours))
        precips.extend(float(v) for v in _slice_hours(precip_series, hours))
        temps.extend(float(v) for v in _slice_hours(temp_series, hours))

    if DAY_START_HOUR <= hour < OVERNIGHT_FLIP_HOUR:
        take(
            weather.hourly_weather_code,
            weather.hourly_precipitation,
            weather.hourly_temperature,
            range(hour, DAY_END_HOUR),
        )
    elif hour >= OVERNIGHT_FLIP_HOUR:
        take(
            weather.hourly_weather_code,
            weather.hourly_precipitation,
            weather.hourly_temperature,
            range(hour, 24),
        )
        take(
            weather.hourly_weather_code_tomorrow,
            weather.hourly_precipitation_tomorrow,
            weather.hourly_temperature_tomorrow,
            range(0, DAY_START_HOUR),
        )
    else:
        take(
            weather.hourly_weather_code,
            weather.hourly_precipitation,
            weather.hourly_temperature,
            range(hour, DAY_START_HOUR),
        )

    if not codes and not precips:
        return (
            [int(weather.weather_code)],
            float(weather.precipitation_sum),
            float(weather.temperature_max),
            float(weather.temperature_min),
        )
    precip = sum(precips) if precips else 0.0
    t_max = max(temps) if temps else float(weather.temperature_max)
    t_min = min(temps) if temps else float(weather.temperature_min)
    if not codes:
        codes = [int(weather.weather_code)]
    return codes, precip, t_max, t_min


def sky_bucket(weather: WeatherData, hour: int = 0) -> Bucket:
    """Map the remainder of the active slot into a humour bucket.

    Until 8pm the sentence is the waking day (looking ahead to 9pm). From 8pm
    until 8am it is overnight. ``hour`` limits the look to hours still ahead,
    so a wet start can give way to a dry line once that weather has passed.
    """
    codes, precip, t_max, t_min = _remaining_slot(weather, hour)

    if any(c in (95, 96, 99) for c in codes):
        return "storm"
    if any(c in (71, 73, 75, 77, 85, 86) for c in codes):
        return "snow"
    if any(c in (65, 67, 82) for c in codes) or precip >= 8.0:
        return "heavy"
    if any(c in (80, 81) or 61 <= c <= 63 for c in codes) or (3.0 <= precip < 8.0):
        return "showers"
    if any(c in (51, 53, 55, 56, 57) for c in codes) or (0.2 <= precip < 3.0):
        return "drizzle"
    if any(c in (45, 48) for c in codes):
        return "fog"
    code = 3 if 3 in codes else 2 if 2 in codes else 1 if 1 in codes else 0
    if code in (0, 1) and t_max >= 24.0:
        return "clear"
    if code in (2, 3):
        return "cloudy"
    if t_max <= 8.0 or t_min <= 2.0:
        return "cold"
    if code in (0, 1):
        return "clear" if t_max >= 18.0 else "mild"
    return "mild"


def _strip_final_stop(text: str) -> str:
    """Drop a trailing full stop; keep ?, !, ), … etc."""
    text = text.rstrip()
    if text.endswith(".") and not text.endswith("..."):
        return text[:-1]
    return text


def _pick_animal(rng: random.Random, pool: tuple[str, ...]) -> tuple[str, str]:
    """Return (lowercase, Capitalised) animal from a pool."""
    animal = rng.choice(pool)
    return animal, animal[:1].upper() + animal[1:]


def _fill_animals(template: str, rng: random.Random) -> str:
    """Fill {wet}/{Wet} style slots. Same pool pick reused within one line."""
    wet, Wet = _pick_animal(rng, _WET)
    smug, Smug = _pick_animal(rng, _SMUG)
    boss, Boss = _pick_animal(rng, _BOSS)
    hot, Hot = _pick_animal(rng, _HOT)
    fog, Fog = _pick_animal(rng, _FOG)
    cold, Cold = _pick_animal(rng, _COLD)
    puddle, Puddle = _pick_animal(rng, _PUDDLE)
    return template.format(
        wet=wet,
        Wet=Wet,
        smug=smug,
        Smug=Smug,
        boss=boss,
        Boss=Boss,
        hot=hot,
        Hot=Hot,
        fog=fog,
        Fog=Fog,
        cold=cold,
        Cold=Cold,
        puddle=puddle,
        Puddle=Puddle,
    )


def _line_seed(day: date, hour: int) -> str:
    """Stable seed for the active slot; overnight does not reshuffle at midnight."""
    if int(hour) >= OVERNIGHT_FLIP_HOUR:
        return f"{day.isoformat()}-overnight"
    if int(hour) < DAY_START_HOUR:
        return f"{(day - timedelta(days=1)).isoformat()}-overnight"
    return day.isoformat()


def pick_whimsy_line(weather: WeatherData, day: date, hour: int = 0) -> str:
    """Pick a whimsical line for the remainder of the active slot.

    Until 8pm the line describes the waking day through 9pm; from 8pm it
    describes overnight until 8am. The RNG is seeded on the slot (overnight
    keeps last evening's date), so half-hourly refreshes do not reshuffle
    the sentence while the weather bucket stays the same. ``hour`` limits
    the look to hours still ahead.
    """
    bucket = sky_bucket(weather, hour)
    rng = random.Random(_line_seed(day, hour))

    # Running joke: rare UK antelope on calm/clear/mild days only.
    if bucket in ("clear", "mild", "cloudy") and rng.randrange(20) == 0:
        return _strip_final_stop(rng.choice(_ANTELOPE))

    if bucket == "storm":
        indoor = rng.choice(_INDOOR_BITS)
        wait = rng.choice(_STORM_WAIT)
        return _strip_final_stop(f"Stay inside, {indoor}. {wait}")

    lines = _LINES.get(bucket) or _LINES["mild"]
    return _strip_final_stop(_fill_animals(rng.choice(lines), rng))
