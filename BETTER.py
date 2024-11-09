"""Functions to retrieve available sports hall boookings from BETTER leisure centre websites"""

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
from selenium import webdriver

from geopy.geocoders import Nominatim
from geopy import distance

from functools import partial
from p_tqdm import p_map
from time import time

from tools import webwait, webwait_all, get_coordinates


def get_distance(home_coords: tuple[float, float], centre_address: str) -> float:
    """Return distance between centre and home"""
    geolocator = Nominatim(user_agent="aaaa")
    centre_address = centre_address.replace('\n', ', ')
    try:
        centre_location = geolocator.geocode(centre_address)
        if centre_location is not None:
            centre_coords = (centre_location.latitude,
                             centre_location.longitude)
            distance_ = round(distance.geodesic(home_coords,
                                                centre_coords).km, 3)
        else:
            distance_ = None

    except:
        distance_ = None

    return distance_


def get_activities(driver: WebDriver, timeout: int, retries: int = 5) -> list[dict]:
    """return a list of activity names in the sports hall"""
    retry_count = 0
    while True:
        try:
            activity_names = [x.text.lower() for x in
                              webwait_all(driver, "CSS_SELECTOR",
                                          "[class^='SubActivityComponent__ActivityName-sc-1mw63if-2']", timeout)]
            activity_links = [x.get_attribute('href') for x in
                              webwait_all(driver, "CSS_SELECTOR",
                                          "[class^='SubActivityComponent__StyledLink-sc-1mw63if-1 bYfPqu']", timeout)]

            return [{'name': name, 'link': link} for name, link in zip(activity_names, activity_links)]

        except (TimeoutError, TimeoutException):
            retry_count += 1
            print(
                f'Retrying link (A) {driver.current_url}, attempt {retry_count}')
            driver.refresh()

        if retry_count > retries:
            return []


def get_dates_tab(driver: WebDriver, timeout: int, retries: int = 5) -> WebElement | None:
    """Return the dates tab web page element for a given activity"""

    retry_count = 0
    while True:
        try:
            return webwait(driver, "CSS_SELECTOR",
                           "[class^='DateRibbonComponent__DatesWrapper-sc-p1q1bx-1']", timeout)
        except (TimeoutError, TimeoutException):
            retry_count += 1
            print(
                f'Retrying link (B) {driver.current_url}, attempt {retry_count}')
            driver.refresh()

        if retry_count > retries:
            return None


def get_bookings_for_date(driver: WebDriver, timeout: int, retries: int = 5) -> list[str]:
    """Return a list of booking times available for a given date"""

    found = None
    start_time = time()
    retry_count = 0
    while found is None:
        times = [x.text.lower() for x in
                 driver.find_elements(By.CSS_SELECTOR,
                                      "[class^='ClassCardComponent__ClassTime-sc-1v7d176-3']")]

        if not times:
            try:
                driver.find_element(By.CSS_SELECTOR,
                                    "[class^='ByTimeListComponent__Wrapper-sc-39liwv-1 ByTimeListComponent__NoContentWrapper-sc-39liwv-2']")
                return []
            except NoSuchElementException:
                pass

        else:
            return times

        end_time = time()
        if end_time - start_time > timeout:
            start_time = time()
            retry_count += 1
            print(
                f'Retrying link (C) {driver.current_url}, attempt {retry_count}')
            driver.refresh()

        if retry_count > retries:
            return []


def get_prices_for_date(driver: WebDriver, timeout: int) -> list[str]:
    """Return a list of prices for a given date"""

    return [x.text.lower()[1:] for x in
            webwait_all(driver, "CSS_SELECTOR",
                        "[class^='ClassCardComponent__Price-sc-1v7d176-14 jumCLU']", timeout)]


def get_slots_for_date(driver: WebDriver, timeout: int) -> list[str]:
    """Return a list ofavailable slots available for a given date"""

    return [x.get_attribute('spaces') for x in
            webwait_all(driver, "CSS_SELECTOR",
                        "[class^='ContextualComponent__BookWrap-sc-eu3gk6-1 buJCkX']", timeout)]


def initialize_better_dict(centre_name: str, centre_address: str, home_coords: tuple[float, float]) -> dict:
    """Initialize the dictionary to store centre info."""

    distance = get_distance(home_coords, centre_address)
    centre_address = centre_address.replace('\n', ', ')
    return {centre_name: {'Address': centre_address, 'Activity': {},
                          'Distance': distance, 'Company': 'BETTER'}}


def get_valid_activity_links(activities: list[dict], activity: str) -> list[str]:
    """Return valid activity links that match the user's activity."""

    return [x['link'] for x in activities if activity.lower() in x['name'].lower()]


def get_booking_details_for_date(driver: WebDriver, timeout: int) -> tuple[list[str], list[str], list[str]]:
    """Extract booking times, prices, and available slots for a given date."""

    times = get_bookings_for_date(driver, timeout)
    if not times:
        return [], [], []

    prices = get_prices_for_date(driver, timeout)
    spaces_avail = get_slots_for_date(driver, timeout)

    return times, prices, spaces_avail


def process_dates(driver: WebDriver, timeout: int) -> dict:
    """Process available dates and return booking details for each date."""

    dates_tab = get_dates_tab(driver, timeout)
    if dates_tab is None:
        return {}

    all_dates_links = [x.get_attribute('href') for x in
                       webwait_all(dates_tab, "TAG_NAME", "a", timeout)
                       if 'undefined' not in x.get_attribute('href')]

    dates_dict = {}
    for date_link in all_dates_links:
        driver.get(date_link)
        date = date_link.split('/')[-2]
        times, prices, spaces_avail = get_booking_details_for_date(driver,
                                                                   timeout)

        if times:
            valid_indexes = [x for x in range(len(spaces_avail))
                             if spaces_avail[x] != '0']
            if len(valid_indexes) != 0:
                dates_dict[date] = {'Times': [times[i] for i in valid_indexes],
                                    'Prices': [prices[i] for i in valid_indexes],
                                    'Spaces': [spaces_avail[i] for i in valid_indexes]}
    return dates_dict


def BETTER_gym_loop(booking_link: str, centre_name: str,
                    centre_address: str, activity: str,
                    home_coords: tuple[float, float], timeout: int) -> dict | None:
    """Returns all available bookings for a given leisure centre booking link"""

    driver = webdriver.Chrome()
    BETTER_dict = initialize_better_dict(
        centre_name, centre_address, home_coords)

    driver.get(f"{booking_link}/sports-hall-activities")

    activities = get_activities(driver, timeout)
    valid_activity_links = get_valid_activity_links(activities, activity)
    if not valid_activity_links:
        driver.close()
        return None

    for activity_link in valid_activity_links:
        driver.get(activity_link)
        dates_dict = process_dates(driver, timeout)

        if dates_dict:
            BETTER_dict[centre_name]['Activity'][activity] = dates_dict.copy()

    driver.close()

    return BETTER_dict


def extract_centre_info(driver: WebDriver, timeout: int, max_centres: int) -> tuple[list[str], list[str], list[str]]:
    """Extract centre names, addresses, and booking links after a search."""

    centre_names = [x.text for x in webwait_all(
        driver, "CSS_SELECTOR", "[class^='venue-result-panel__link']", timeout)][:max_centres]
    centre_addresses = [x.text for x in webwait_all(
        driver, "CSS_SELECTOR", "[class^='venue-result-panel__address']", timeout)][:max_centres]
    centre_booking_items = webwait_all(
        driver, "CSS_SELECTOR", "[class^='call-to-action call-to-action--primary venue-result-panel__btn']", timeout)
    centre_booking_links = [x.get_attribute(
        'href') for x in centre_booking_items if 'bookings.better' in x.get_attribute('href')][:max_centres]

    return centre_names, centre_addresses, centre_booking_links


def search_centres(driver: WebDriver, postcode: str, timeout: int, max_centres: int) -> tuple[list[str], list[str], list[str]]:
    """Search and return centre names, addresses, and booking links."""

    FindCentre_url = "https://www.better.org.uk/centre-locator"
    driver.get(FindCentre_url)

    webwait(driver, "NAME", 'venue_search[searchterm]', timeout).send_keys(
        postcode)
    Select(driver.find_elements(By.NAME, 'venue_search[business_sector_id]')[
           1]).select_by_value('2')
    driver.find_element(
        By.XPATH, "/html[1]/body[1]/main[1]/div[2]/div[1]/form[1]/div[4]/button[1]").click()

    return extract_centre_info(driver, timeout, max_centres)


def process_centre_bookings(centre_names: list[str], centre_addresses: list[str], centre_booking_links: list[str],
                            activity: str, home_coords: tuple[float, float], timeout: int, cpu_cores: int) -> dict:
    """Start threads for booking search for each centre and return available bookings."""

    BETTER_gym_dict = p_map(partial(BETTER_gym_loop, activity=activity, home_coords=home_coords, timeout=timeout),
                            centre_booking_links, centre_names, centre_addresses, num_cpus=cpu_cores)

    return {k: v for d in BETTER_gym_dict if d is not None for k, v in d.items()}


def scrape_better_website(postcode: str, activity: str, max_centres: int = 20, cpu_cores: int = 4, timeout: int = 10) -> dict | None:
    """Main function to collect nearest centres and return available bookings."""

    home_coords = get_coordinates(postcode)
    driver = webdriver.Chrome()

    centre_names, centre_addresses, centre_booking_links = search_centres(driver, postcode,
                                                                          timeout, max_centres)
    driver.close()

    return process_centre_bookings(centre_names, centre_addresses, centre_booking_links,
                                   activity, home_coords, timeout, cpu_cores)
