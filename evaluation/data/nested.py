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
    """Get the annual rainfall for a given city."""
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

questions = [
    "What's the weather like in the capital of France?",
    "How many books has the author of '1984' written?",
    "What's the population of the largest city in Canada?",
    "What's the current exchange rate from USD to the currency used in Japan?",
    "What's the GDP per capita of the country whose national animal is the kangaroo?",
    "If the GDP of Canada is negative, give me its GDP per capita otherwise return its GDP.",
    "What's the average annual rainfall in the capital city of the country that produces the most coffee in the world?",
    "What are the populations of the three largest cities in Australia?",
    "What are the cities in Australia with rainfall greater than 1000mm?",
    "What is the total population of all cities in Australia?",
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
        "calculate_per_capita_1": {
            "get_gdp_1": {"get_country_by_national_animal_1": {"animal": ["kangaroo"]}},
            "get_country_population_1": {
                "get_country_by_national_animal_2": {"animal": ["kangaroo"]}
            },
        }
    },
    {
        "conditional_1": {
            "greater_than_1": {
                "get_gdp_1": {"country": ["Canada"]},
                "threshold": ["0"],
            },
            "get_gdp_2": {"country": ["Canada"]},
            "calculate_per_capita_1": {
                "get_gdp_3": {"country": ["Canada"]},
                "get_country_population_1": {"country": ["Canada"]},
            },
        }
    },
    {
        "average_1": {
            "get_annual_rainfall_1": {
                "get_capital_city_1": {"get_top_producer_1": {"product": ["coffee"]}}
            }
        }
    },
    {
        "map_1": {
            "lambda_1": {
                "get_city_population_1": {
                    "get_largest_city_by_ranking_1": {
                        "country": ["Australia"],
                        "ranking": [0],
                    }
                }
            },
            "rankings": [["1", "2", "3"]],
        }
    },
    {
        "filter_1": {
            "lambda_1": {
                "greater_than_1": {
                    "get_annual_rainfall_1": {"city": [0]},
                    "threshold": [1000],
                }
            },
            "get_all_cities_in_country_1": {"country": ["Australia"]},
        }
    },
    {
        "reduce_1": {
            "lambda_1": {"add_1": {"x": [0], "get_city_population_1": {"city": [""]}}},
            "get_all_cities_in_country_1": {"country": ["Australia"]},
        }
    },
]
