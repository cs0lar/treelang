def get_capital_city(country):
    """Get the capital city of a given country."""
    if country == "France":
        return "Paris"
    elif country == "Japan":
        return "Tokyo"
    elif country == "Brazil":
        return "Brasília"
    elif country == "Australia":
        return "Canberra"
    else:
        return "Unknown"


def get_weather(city):
    """Get the current weather for a given city."""
    if city == "Paris":
        return "Sunny, 25°C"
    elif city == "Tokyo":
        return "Cloudy, 22°C"
    elif city == "Brasília":
        return "Rainy, 28°C"
    elif city == "Canberra":
        return "Windy, 20°C"
    else:
        return "Data not available"


def get_largest_city(country):
    """Get the largest city in a given country."""
    if country == "France":
        return "Paris"
    elif country == "Japan":
        return "Tokyo"
    elif country == "Brazil":
        return "São Paulo"
    elif country == "Australia":
        return "Sydney"
    else:
        return "Unknown"


def get_largest_city_by_ranking(country, ranking):
    """Get the largest city in a given country by ranking."""
    if country == "France":
        cities = ["Paris", "Marseille", "Lyon"]
    elif country == "Japan":
        cities = ["Tokyo", "Yokohama", "Osaka"]
    elif country == "Brazil":
        cities = ["São Paulo", "Rio de Janeiro", "Salvador"]
    elif country == "Australia":
        cities = ["Sydney", "Melbourne", "Brisbane"]
    else:
        return "Unknown"

    if 1 <= ranking <= len(cities):
        return cities[ranking - 1]
    else:
        return "Ranking out of range"


def get_city_population(city):
    """Get the population of a given city."""
    if city == "Paris":
        return 2148000
    elif city == "Tokyo":
        return 13960000
    elif city == "São Paulo":
        return 12330000
    elif city == "Sydney":
        return 5312000
    elif city == "Brisbane":
        return 2514000
    elif city == "Melbourne":
        return 5078000
    else:
        return "Data not available"


def get_country_population(country):
    """Get the population of a given country."""
    if country == "France":
        return 67000000
    elif country == "Japan":
        return 125800000
    elif country == "Brazil":
        return 211000000
    elif country == "Australia":
        return 25690000
    else:
        return "Data not available"


def get_exchange_rate(from_currency, to_currency):
    """Get the exchange rate between two currencies."""
    if from_currency == "USD" and to_currency == "EUR":
        return 0.85
    elif from_currency == "USD" and to_currency == "JPY":
        return 110.0
    elif from_currency == "USD" and to_currency == "BRL":
        return 5.2
    elif from_currency == "USD" and to_currency == "AUD":
        return 1.4
    else:
        return "Exchange rate not available"


def get_country_currency(country):
    """Get the currency used in a given country."""
    if country == "France":
        return "EUR"
    elif country == "Japan":
        return "JPY"
    elif country == "Brazil":
        return "BRL"
    elif country == "Australia":
        return "AUD"
    else:
        return "Unknown"


def get_top_producer(product):
    """Get the top producer of a given product."""
    if product == "coffee":
        return "Brazil"
    elif product == "cars":
        return "China"
    elif product == "electronics":
        return "USA"
    elif product == "wheat":
        return "Russia"
    else:
        return "Unknown"


def get_annual_rainfall(city):
    """Get the list of rainfall measurements covering the past year for a given city."""
    if city == "Brasilia":
        return [1.2, 1.5, 1.3, 1.4, 1.6, 1.5, 1.3, 1.4, 1.5, 1.6, 1.4, 1.5]
    elif city == "Tokyo":
        return [0.8, 0.9, 1.0, 0.7, 0.6, 0.8, 0.9, 1.0, 0.7, 0.6, 0.8, 0.9]
    elif city == "Paris":
        return [0.5, 0.6, 0.7, 0.5, 0.4, 0.6, 0.7, 0.5, 0.4, 0.6, 0.7, 0.5]
    elif city == "Sydney":
        return [0.9, 1.0, 1.1, 0.9, 0.8, 1.0, 1.1, 0.9, 0.8, 1.0, 1.1, 0.9]
    elif city == "Melbourne":
        return [0.7, 0.8, 0.9, 0.7, 0.6, 0.8, 0.9, 0.7, 0.6, 0.8, 0.9, 0.7]
    elif city == "Brisbane":
        return [1.0, 1.1, 1.2, 1.0, 0.9, 1.1, 1.2, 1.0, 0.9, 1.1, 1.2, 1.0]
    else:
        return []


def average(rainfall_data):
    """Calculate the average from a list of rainfall data."""
    if not rainfall_data:
        return 0
    return round(sum(rainfall_data) / len(rainfall_data), 2)


def get_country_by_national_animal(animal):
    """Get the country associated with a given national animal."""
    if animal == "Kangaroo":
        return "Australia"
    else:
        return "Unknown"


def get_gdp(country):
    """Get the GDP of a given country."""
    if country == "France":
        return 2715.52  # in billion USD
    elif country == "Japan":
        return 5154.48  # in billion USD
    elif country == "Brazil":
        return 1839.76  # in billion USD
    elif country == "Australia":
        return 1392.68  # in billion USD
    else:
        return "Data not available"


def calculate_per_capita(total, population):
    """Calculate the per capita value given total and population."""
    if population == 0:
        return 0
    return round((total * 1000000000) / population, 2)


def count_books(author):
    """Count the number of books written by a given author."""
    if author == "George Orwell":
        return 9
    else:
        return 0


def get_author(book_title):
    """Get the author of a given book title."""
    if book_title == "1984":
        return "George Orwell"
    elif book_title == "Brave New World":
        return "Aldous Huxley"
    elif book_title == "Fahrenheit 451":
        return "Ray Bradbury"
    else:
        return "Unknown"


def greater_than(value, threshold):
    """Check if a value is greater than a given threshold."""
    return value > threshold


def get_all_cities_in_country(country):
    """Get all cities in a given country."""
    if country == "France":
        return ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"]
    elif country == "Japan":
        return ["Tokyo", "Yokohama", "Osaka", "Nagoya", "Sapporo"]
    elif country == "Brazil":
        return ["São Paulo", "Rio de Janeiro", "Salvador", "Brasília", "Fortaleza"]
    elif country == "Australia":
        return ["Sydney", "Melbourne", "Brisbane"]
    else:
        return []


def add(x, y):
    """Add two numbers."""
    return x + y


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
