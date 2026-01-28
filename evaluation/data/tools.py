def get_capital_city(country):
    country_lower = country.lower()
    """Get the capital city of a given country."""
    if country_lower == "france":
        return "Paris"
    elif country_lower == "japan":
        return "Tokyo"
    elif country_lower == "brazil":
        return "Brasília"
    elif country_lower == "australia":
        return "Canberra"
    else:
        return "Unknown"


def get_weather(city):
    """Get the current weather for a given city."""
    city_lower = city.lower()
    if city_lower == "paris":
        return "Sunny, 25°C"
    elif city_lower == "tokyo":
        return "Cloudy, 22°C"
    elif city_lower == "brasília":
        return "Rainy, 28°C"
    elif city_lower == "canberra":
        return "Windy, 20°C"
    else:
        return "Data not available"


def get_largest_city(country):
    """Get the largest city in a given country."""
    country_lower = country.lower()
    if country_lower == "france":
        return "Paris"
    elif country_lower == "japan":
        return "Tokyo"
    elif country_lower == "brazil":
        return "São Paulo"
    elif country_lower == "australia":
        return "Sydney"
    else:
        return "Unknown"


def get_largest_city_by_ranking(country, ranking):
    """Returns the city name at the given population rank within a country.
       country: string (e.g., "Australia"), ranking: integer only (1 = largest, 2 = second largest, etc.)
    """
    country_lower = country.lower()
    ranking = int(ranking)
    if country_lower == "france":
        cities = ["Paris", "Marseille", "Lyon"]
    elif country_lower == "japan":
        cities = ["Tokyo", "Yokohama", "Osaka"]
    elif country_lower == "brazil":
        cities = ["São Paulo", "Rio de Janeiro", "Salvador"]
    elif country_lower == "australia":
        cities = ["Sydney", "Melbourne", "Brisbane"]
    else:
        return "Unknown"

    if 1 <= ranking <= len(cities):
        return cities[ranking - 1]
    else:
        return "Ranking out of range"


def get_city_population(city):
    """Get the population of a given city."""
    city_lower = city.lower()
    if city_lower == "paris":
        return 2148000
    elif city_lower == "tokyo":
        return 13960000
    elif city_lower == "são paulo":
        return 12330000
    elif city_lower == "sydney":
        return 5312000
    elif city_lower == "brisbane":
        return 2514000
    elif city_lower == "melbourne":
        return 5078000
    else:
        return "Data not available"


def get_country_population(country):
    """Get the population of a given country."""
    country_lower = country.lower()
    if country_lower == "france":
        return 67000000
    elif country_lower == "japan":
        return 125800000
    elif country_lower == "brazil":
        return 211000000
    elif country_lower == "australia":
        return 25690000
    else:
        return "Data not available"


def get_exchange_rate(from_currency, to_currency):
    """Get the exchange rate between two currencies."""
    from_currency_upper = from_currency.upper()
    to_currency_upper = to_currency.upper()
    if from_currency_upper == "USD" and to_currency_upper == "EUR":
        return 0.85
    elif from_currency_upper == "USD" and to_currency_upper == "JPY":
        return 110.0
    elif from_currency_upper == "USD" and to_currency_upper == "BRL":
        return 5.2
    elif from_currency_upper == "USD" and to_currency_upper == "AUD":
        return 1.4
    else:
        return "Exchange rate not available"


def get_country_currency(country):
    """Get the currency used in a given country."""
    country_lower = country.lower()
    if country_lower == "france":
        return "EUR"
    elif country_lower == "japan":
        return "JPY"
    elif country_lower == "brazil":
        return "BRL"
    elif country_lower == "australia":
        return "AUD"
    else:
        return "Unknown"


def get_top_producer(product):
    """Get the top producer of a given product."""
    product_lower = product.lower()
    if product_lower == "coffee":
        return "Brazil"
    elif product_lower == "cars":
        return "China"
    elif product_lower == "electronics":
        return "USA"
    elif product_lower == "wheat":
        return "Russia"
    else:
        return "Unknown"


def get_annual_rainfall(city):
    """Get the list of rainfall measurements covering the past year for a given city."""
    city_lower = city.lower()
    if city_lower == "brasília":
        return [1.2, 1.5, 1.3, 1.4, 1.6, 1.5, 1.3, 1.4, 1.5, 1.6, 1.4, 1.5]
    elif city_lower == "tokyo":
        return [0.8, 0.9, 1.0, 0.7, 0.6, 0.8, 0.9, 1.0, 0.7, 0.6, 0.8, 0.9]
    elif city_lower == "paris":
        return [0.5, 0.6, 0.7, 0.5, 0.4, 0.6, 0.7, 0.5, 0.4, 0.6, 0.7, 0.5]
    elif city_lower == "sydney":
        return [0.9, 1.0, 1.1, 0.9, 0.8, 1.0, 1.1, 0.9, 0.8, 1.0, 1.1, 0.9]
    elif city_lower == "melbourne":
        return [0.7, 0.8, 0.9, 0.7, 0.6, 0.8, 0.9, 0.7, 0.6, 0.8, 0.9, 0.7]
    elif city_lower == "brisbane":
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
    animal_lower = animal.lower()
    if animal_lower == "kangaroo":
        return "Australia"
    else:
        return "Unknown"


def get_gdp(country):
    """Get the GDP of a given country."""
    country_lower = country.lower()
    if country_lower == "france":
        return 2715.52  # in billion USD
    elif country_lower == "japan":
        return 5154.48  # in billion USD
    elif country_lower == "brazil":
        return 1839.76  # in billion USD
    elif country_lower == "australia":
        return 1392.68  # in billion USD
    else:
        return "Data not available"


def calculate_per_capita(total, population):
    """Calculate the per capita value given total and population."""
    total = float(total)
    population = float(population)

    if population == 0:
        return 0
    return round((total * 1000000000) / population, 2)


def count_books(author):
    """Count the number of books written by a given author."""
    author_lower = author.lower()
    if author_lower == "george orwell":
        return 9
    else:
        return 0


def get_author(book_title):
    """Get the author of a given book title."""
    booktitle_lower = book_title.lower()
    if booktitle_lower == "1984":
        return "George Orwell"
    elif booktitle_lower == "brave new world":
        return "Aldous Huxley"
    elif booktitle_lower == "fahrenheit 451":
        return "Ray Bradbury"
    else:
        return "Unknown"


def greater_than(value, threshold):
    """Check if a value is greater than a given threshold."""
    value = float(value)
    threshold = float(threshold)
    return value > threshold


def less_than(value, threshold):
    """Check if a value is less than a given threshold."""
    value = float(value)
    threshold = float(threshold)
    return value < threshold


def get_all_cities_in_country(country):
    """Get all cities in a given country."""
    country_lower = country.lower()
    if country_lower == "france":
        return ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"]
    elif country_lower == "japan":
        return ["Tokyo", "Yokohama", "Osaka", "Nagoya", "Sapporo"]
    elif country_lower == "brazil":
        return ["São Paulo", "Rio de Janeiro", "Salvador", "Brasília", "Fortaleza"]
    elif country_lower == "australia":
        return ["Sydney", "Melbourne", "Brisbane"]
    else:
        return []


def add(x, y):
    """Add two numbers."""
    return float(x) + float(y)


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
    less_than,
    get_all_cities_in_country,
]

# __all__ = [tool.__name__ for tool in tools]
