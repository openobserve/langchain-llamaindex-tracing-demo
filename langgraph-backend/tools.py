"""Mocked trip-planning tools.

Deliberately dependent on each other's output (you need an airport code before
you can look up weather or flight price for it) so a real question forces the
agent to go through more than one agent -> tools loop instead of resolving
everything in a single turn.
"""

from langchain_core.tools import tool

_AIRPORTS = {
    "new york": "JFK",
    "tokyo": "HND",
    "paris": "CDG",
    "san francisco": "SFO",
    "london": "LHR",
}

_WEATHER = {
    "JFK": "62F, light rain",
    "HND": "78F, humid, clear skies",
    "CDG": "58F, overcast",
    "SFO": "64F, foggy mornings",
    "LHR": "55F, drizzle",
}

_FLIGHT_PRICES_USD = {
    ("JFK", "HND"): 890,
    ("HND", "JFK"): 910,
    ("JFK", "CDG"): 540,
    ("CDG", "JFK"): 560,
    ("SFO", "HND"): 720,
    ("HND", "SFO"): 700,
}

_FX_RATES_FROM_USD = {
    "JPY": 149.5,
    "EUR": 0.92,
    "GBP": 0.79,
    "USD": 1.0,
}


@tool
def lookup_airport_code(city: str) -> str:
    """Look up the 3-letter airport code for a city. Call this first for any
    city you don't already have a code for."""
    code = _AIRPORTS.get(city.strip().lower())
    if not code:
        return f"No airport code found for '{city}'. Known cities: {', '.join(_AIRPORTS)}."
    return code


@tool
def get_weather(airport_code: str) -> str:
    """Get current weather for an airport code (use lookup_airport_code first)."""
    return _WEATHER.get(airport_code.strip().upper(), f"No weather data for '{airport_code}'.")


@tool
def get_flight_price(origin_code: str, destination_code: str) -> str:
    """Get an estimated round-trip flight price in USD between two airport codes."""
    key = (origin_code.strip().upper(), destination_code.strip().upper())
    price = _FLIGHT_PRICES_USD.get(key)
    if price is None:
        return f"No price data for {key[0]} -> {key[1]}."
    return f"${price} USD"


@tool
def convert_currency(amount: float, to_currency: str) -> str:
    """Convert a USD amount to another currency (JPY, EUR, GBP, USD)."""
    rate = _FX_RATES_FROM_USD.get(to_currency.strip().upper())
    if rate is None:
        return f"No exchange rate for '{to_currency}'. Known: {', '.join(_FX_RATES_FROM_USD)}."
    converted = round(amount * rate, 2)
    return f"{converted} {to_currency.strip().upper()}"


ALL_TOOLS = [lookup_airport_code, get_weather, get_flight_price, convert_currency]
