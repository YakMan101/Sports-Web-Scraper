import math

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By

from geopy.geocoders import Nominatim
from difflib import SequenceMatcher


def webwait_all(driver: WebDriver, type_: str, name: str, timeout: int) -> list[WebElement]:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located(
            (By.__getattribute__(By, type_), name))
    )


def webwait(driver: WebDriver, type_: str, name: str, timeout: int) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.__getattribute__(By, type_), name))
    )


def wait_until_element_seen(driver: WebDriver, element: WebElement, timeout: int = 5) -> None:
    """Wait until element is in view"""

    WebDriverWait(driver, timeout).until(EC.visibility_of(element))


def scroll_into_view(driver: WebDriver, element: WebElement) -> None:
    """Bring specific element into view"""

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", element)

    wait_until_element_seen(driver, element)


def get_coordinates(postcode: str) -> tuple[int, int]:
    """Return longitude and latitude of a given postcode"""

    geolocator = Nominatim(user_agent="aaaa")
    home = geolocator.geocode(postcode)

    return home.latitude, home.longitude


def get_distance_between_coords(lat_lon1: tuple[float, float], lat_lon2: tuple[float, float]) -> float:
    lat1, lon1 = lat_lon1
    lat2, lon2 = lat_lon2

    R = 6371e3  # metres
    psi1 = lat1 * math.pi / 180  # psi, lambda in radians
    psi2 = lat2 * math.pi / 180
    delta_psi = (lat2 - lat1) * math.pi / 180
    delta_lambda = (lon2 - lon1) * math.pi / 180

    a = (math.sin(delta_psi / 2) * math.sin(delta_psi / 2) +
         math.cos(psi1) * math.cos(psi2) *
         math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2))

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c  # in metres
    return d


def similar(a: str, b: str) -> float:
    """Check how similar two strings are"""

    return SequenceMatcher(None, a, b).ratio()


def return_similar_strings(case: str, string_list: list[str], threshold: float) -> list[tuple[str, float]]:
    """Return a list of strings that meet minimum similarity ratio 
    to the case in order of most to least similar"""

    similar_strings = []
    for string in string_list:
        similarity_score = similar(case, string)
        if similarity_score >= threshold:
            similar_strings.append((string, similarity_score))

    return sorted(similar_strings, key=lambda x: similar(x, case), reverse=True)
