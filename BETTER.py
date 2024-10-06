from selenium.common.exceptions import NoSuchElementException
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
import numpy as np

from tools import webwait, webwait_all


def get_distance(home_coords: tuple[float, float], centre_address: str) -> float:
    geolocator = Nominatim(user_agent="aaaa")
    centre_address = centre_address.replace('\n', ', ')
    try:
        centre_location = geolocator.geocode(centre_address)
        if centre_location is not None:
            centre_coords = (centre_location.latitude,
                             centre_location.longitude)
            distance_ = np.round(distance.geodesic(
                home_coords, centre_coords).km, 3)
        else:
            distance_ = np.nan

    except:
        distance_ = np.nan

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

        except:
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
        except TimeoutError:
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


def BETTER_gym_loop(booking_link: str, centre_name: str,
                    centre_address: str, activity: str,
                    home_coords: tuple[float, float], timeout: int) -> dict | None:
    """Main loop"""
    BETTER_dict = {}
    driver = webdriver.Chrome()

    driver.get(f"{booking_link}/sports-hall-activities")

    activities = get_activities(driver, timeout)
    valid_activity_links = [x['link'] for x in activities
                            if activity.lower() in x['name'].lower()]
    if len(valid_activity_links) == 0:
        return None

    distance = get_distance(home_coords, centre_address)
    centre_address = centre_address.replace('\n', ', ')
    BETTER_dict[centre_name] = {'Address': centre_address, 'Activity': {},
                                'Distance': distance, 'Company': 'BETTER'}

    for activity_link in valid_activity_links:
        driver.get(activity_link)
        dates_tab = get_dates_tab(driver, timeout)
        if dates_tab is None:
            continue

        all_dates_links = [x.get_attribute('href') for x in
                           webwait_all(dates_tab, "TAG_NAME", "a", timeout)
                           if 'undefined' not in x.get_attribute('href')]
        dates_dict = {}

        for date_link in all_dates_links:
            driver.get(date_link)
            times = get_bookings_for_date(driver, timeout)

            if not times:
                continue

            prices = get_prices_for_date(driver, timeout)
            spaces_avail = get_slots_for_date(driver, timeout)

            valid_indexes = np.array(
                [x for x in range(len(spaces_avail)) if spaces_avail[x] != '0'])
            if valid_indexes.size == 0:
                continue

            date = date_link.split('/')[-2]
            dates_dict[date] = {
                'Times': [times[i] for i in valid_indexes],
                'Prices': [prices[i] for i in valid_indexes],
                'Spaces': [spaces_avail[i] for i in valid_indexes]
            }

        BETTER_dict[centre_name]['Activity'][activity] = dates_dict.copy()

    driver.close()
    return BETTER_dict


# Function for BETTER gyms/centres
def BETTER_gym(Loc: str, activity: str, max_centres: int | None = 20, cpu_cores: int = 4, timeout: int = 10) -> dict | None:
    """
    :param Loc: Location which to search from. Postcodes work best.
    :param Act: Activity e.g: 'Badminton', 'Basketball'
    :param max_centres: Take closest 'n' centres from Loc
    :param cpu_cores: Number of parallel tabs to be open. Each tab is a different centre
    :param timeout: Maximum wait time for website to load. If slow internet, increase this.
    :return: dictionary of centres and corresponding info in the following example structure:
    {
        'CentreName1': {
            'Address': 'CentreAddress1',
            'Activity': {
                'ActivityType1': {
                    'Date1': {
                        'Times': ['T1', 'T2'], 
                        'Prices': ['P1', 'P2'], 
                        'Spaces': ['S1', 'S2']}}},
            'Distance': 'Distance1'
    }
    """

    geolocator = Nominatim(user_agent="aaaa")
    home = geolocator.geocode(Loc)
    home_coords = (home.latitude, home.longitude)

    FindCentre_url = "https://www.better.org.uk/centre-locator"

    driver = webdriver.Chrome()
    driver.get(FindCentre_url)
    webwait(driver, "NAME", 'venue_search[searchterm]', timeout).send_keys(Loc)
    Select(driver.find_elements(By.NAME, 'venue_search[business_sector_id]')[
           1]).select_by_value('2')
    driver.find_element(
        By.XPATH, "/html[1]/body[1]/main[1]/div[2]/div[1]/form[1]/div[4]/button[1]").click()

    centre_names = [x.text for x in webwait_all(
        driver, "CSS_SELECTOR", "[class^='venue-result-panel__link']", timeout)][:max_centres]
    centre_addresses = [x.text for x in webwait_all(
        driver, "CSS_SELECTOR", "[class^='venue-result-panel__address']", timeout)][:max_centres]
    centre_booking_items = webwait_all(
        driver, "CSS_SELECTOR", "[class^='call-to-action call-to-action--primary venue-result-panel__btn']", timeout)
    centre_booking_links = [x.get_attribute(
        'href') for x in centre_booking_items if 'bookings.better' in x.get_attribute('href')][:max_centres]

    if max_centres is None or max_centres > len(centre_booking_links):
        max_centres = len(centre_booking_links)

    driver.close()

    BETTER_gym_dict = p_map(partial(BETTER_gym_loop, activity=activity, home_coords=home_coords, timeout=timeout),
                            centre_booking_links, centre_names, centre_addresses, num_cpus=cpu_cores)

    BETTER_gym_dict = {
        k: v for d in BETTER_gym_dict if d is not None for k, v in d.items()}

    return BETTER_gym_dict
