def get_capital_city(country):
    """Get the capital city of a given country."""
    pass


def get_weather(city):
    """Get the current weather for a given city."""
    pass


def get_largest_city(country):
    """Get the largest city in a given country."""
    pass


def get_largest_city_by_ranking(country, ranking):
    """Get the largest city in a given country by ranking."""
    pass


def get_city_population(city):
    """Get the population of a given city."""
    pass


def get_country_population(country):
    """Get the population of a given country."""
    pass


def get_exchange_rate(from_currency, to_currency):
    """Get the exchange rate between two currencies."""
    pass


def get_country_currency(country):
    """Get the currency used in a given country."""
    pass


def get_top_producer(product):
    """Get the top producer of a given product."""
    pass


def get_annual_rainfall(city):
    """Get the list of rainfall measurements covering the past year for a given city."""
    pass


def average(rainfall_data):
    """Calculate the average from a list of rainfall data."""
    pass


def get_country_by_national_animal(animal):
    """Get the country associated with a given national animal."""
    pass


def get_gdp(country):
    """Get the GDP of a given country."""
    pass


def calculate_per_capita(total, population):
    """Calculate the per capita value given total and population."""
    pass


def count_books(author):
    """Count the number of books written by a given author."""
    pass


def get_author(book_title):
    """Get the author of a given book title."""
    pass


def greater_than(value, threshold):
    """Check if a value is greater than a given threshold."""
    pass


def get_all_cities_in_country(country):
    """Get all cities in a given country."""
    pass


def add(x, y):
    """Add two numbers."""
    pass


tools = [
    get_top_producer,
    get_capital_city,
    get_weather,
    get_largest_city,
    get_largest_city_by_ranking,
    get_city_population,
    get_country_population,
    get_exchange_rate,
    get_country_currency,
    get_annual_rainfall,
    average,
    get_country_by_national_animal,
    get_gdp,
    calculate_per_capita,
    count_books,
    get_author,
    add,
    greater_than,
    get_all_cities_in_country,
]

# __all__ = [tool.__name__ for tool in tools]
