def get_capital_city(country):
    """Get the capital city of a given country."""
    pass


def get_weather(city):
    """Get the current weather for a given city."""
    pass


def get_largest_city(country):
    """Get the largest city in a given country."""
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
    """Get the annual rainfall for a given city."""
    pass


def calculate_average(rainfall_data):
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


tools = [
    get_top_producer,
    get_capital_city,
    get_weather,
    get_largest_city,
    get_city_population,
    get_country_population,
    get_exchange_rate,
    get_country_currency,
    get_annual_rainfall,
    calculate_average,
    get_country_by_national_animal,
    get_gdp,
    calculate_per_capita,
    count_books,
    get_author,
]

questions = [
    "What's the weather like in the capital of France?",
    "How many books has the author of '1984' written?",
    "What's the population of the largest city in Canada?",
    "What's the current exchange rate from USD to the currency used in Japan?",
    "What's the average annual rainfall in the capital city of the country that produces the most coffee in the world?",
    "What's the GDP per capita of the country whose national animal is the kangaroo?",
]


answers = [
    {
        "get_weather_1": {
            "get_capital_city_1": {"country": ["France"]},
        }
    },
    {"count_books_1": {"get_author_1": {"book_title": ["1984"]}}},
    {"get_city_population_1": {"get_largest_city_1": {"country": ["Canada"]}}},
    {
        "get_exchange_rate_1": {
            "from_currency": ["USD"],
            "get_country_currency_1": {"country": ["Japan"]},
        }
    },
    {
        "calculate_average_1": {
            "get_annual_rainfall_1": {
                "get_capital_city_1": {"get_top_producer_1": {"product": ["coffee"]}}
            }
        }
    },
    {
        "calculate_per_capita_1": {
            "get_gdp_1": {"get_country_by_national_animal_1": {"animal": ["kangaroo"]}},
            "get_country_population_1": {
                "get_country_by_national_animal_2": {"animal": ["kangaroo"]}
            },
        }
    },
]
