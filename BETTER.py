from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
from selenium import webdriver

from geopy.geocoders import Nominatim
from geopy import distance

from functools import partial
from p_tqdm import p_map
from tqdm import tqdm
from time import time
import numpy as np

from tools import webwait, webwait_all


def get_distance(home_coords: tuple[float, float], centre_address: str) -> float:
    geolocator = Nominatim(user_agent="aaaa")
    centre_address = centre_address.replace('\n', ', ')
    try:
        centre_location = geolocator.geocode(centre_address)
        if centre_location is not None:
            centre_coords = (centre_location.latitude, centre_location.longitude)
            distance_ = np.round(distance.geodesic(home_coords, centre_coords).km, 3)
        else:
            distance_ = np.nan

    except:
        distance_ = np.nan

    return distance_


def get_activity_names(driver: WebDriver, timeout: int, retries: int=5) -> list[str]:
    """return a list of activity names in the sports hall"""
    retry_count = 0
    while True:
        try:
            return [x.text.lower() for x in
                    webwait_all(driver, "CSS_SELECTOR",
                                "[class^='SubActivityComponent__ActivityName-sc-1mw63if-2']", timeout)]

        except:
            retry_count += 1
            print(f'Retrying link (A) {driver.current_url}, attempt {retry_count}')
            driver.refresh()

        if retry_count > retries:
            return []


def BETTER_gym_loop(booking_link: str, centre_name: str, centre_address: str, activity: str, home_coords: tuple[float, float], timeout: int) -> dict | None:
    """Main loop"""
    BETTER_dict = {}
    driver = webdriver.Chrome()

    driver.get(booking_link)

    activities_names = get_activity_names(driver, timeout)

    valid_activities_indexes = np.array([activities_names.index(x) for x in activities_names if activity.lower() in x])

    if valid_activities_indexes.size == 0:
        return None

    valid_activities_names = np.array(activities_names)[valid_activities_indexes]
    valid_links = [booking_link + '/' + z.lower().replace(' ', '-') for z in valid_activities_names]

    distance_ = get_distance(home_coords, centre_address)
    centre_address = centre_address.replace('\n', ', ')
    BETTER_dict[centre_name] = {'Address': centre_address, 'Activity': {}, 'Distance': distance_, 'Company': 'BETTER'}

    for activity_link in valid_links:
        driver.get(activity_link)
        activity = activity_link.split('/')[-1]
        retry_count = 0
        while True:
            try:
                dates_tab = webwait(driver, "CSS_SELECTOR",
                                    "[class^='DateRibbonComponent__DatesWrapper-sc-p1q1bx-1']", timeout)
                break
            except:
                retry_count += 1
                print(f'Retrying link (B) {activity_link}, attempt {retry_count}')
                driver.refresh()

            if retry_count > 5:
                break

        all_dates_links = [x.get_attribute('href') for x in
                           webwait_all(dates_tab, "TAG_NAME", "a", timeout)
                           if 'undefined' not in x.get_attribute('href')]
        dates_dict = {}

        for date_link in tqdm(all_dates_links, total=len(all_dates_links),
                              desc=f'Searching: {centre_name} - {activity}', disable=True):

            driver.get(date_link)
            date = date_link.split('/')[-2]
            found = None
            start_time = time()
            retry_count = 0
            while found is None:
                try:
                    times = [x.text.lower() for x in
                             driver.find_elements(By.CSS_SELECTOR,
                                                  "[class^='ClassCardComponent__ClassTime-sc-1v7d176-3']")]
                    if not times:
                        raise Exception("")
                    found = True
                    break
                except:
                    pass

                try:
                    driver.find_element(By.CSS_SELECTOR,
                                        "[class^='ByTimeListComponent__Wrapper-sc-39liwv-1 ByTimeListComponent__NoContentWrapper-sc-39liwv-2']")
                    found = False
                    break
                except:
                    pass
                end_time = time()
                if end_time - start_time > timeout:
                    start_time = time()
                    retry_count += 1
                    print(f'Retrying link (C) {activity_link}, attempt {retry_count}')
                    driver.refresh()

                if retry_count > 5:
                    break

            if not found:
                continue

            prices = [x.text.lower() for x in
                      webwait_all(driver, "CSS_SELECTOR",
                                  "[class^='ClassCardComponent__Price-sc-1v7d176-14']", timeout)]
            spaces_avail = [x.text.lower().split(' ')[0] for x in
                            webwait_all(driver, "CSS_SELECTOR",
                                        "[class^='ContextualComponent__BookWrap-sc-eu3gk6-1']", timeout)]

            valid_indexes = np.array([x for x in range(len(spaces_avail)) if spaces_avail[x] != '0'])
            if valid_indexes.size == 0:
                continue

            dates_dict[date] = {'Times': np.array(times.copy())[valid_indexes],
                                'Prices': np.array(prices.copy())[valid_indexes],
                                'Spaces': np.array(spaces_avail.copy())[valid_indexes]}

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
    'Tadworth Leisure and Community Centre':
        {
        'Address': 'Preston Manor Road, Tadworth, Surrey, KT20 5FB',
        'Activity': {
            'badminton-60min': {
                '2023-08-29': {
                    'Times': ['07:00 - 08:00', '14:00 - 15:00'],
                    'Prices': ['£11.30', '£11.30'],
                    'Spaces': ['4', '1']
                    },
                '2023-08-30': {
                    'Times': ['07:00 - 08:00', '08:00 - 09:00'],
                    'Prices': ['£11.30', '£11.30'],
                    'Spaces': ['4', '2']
                    },
                }
            'badminton-40min': {
                '2023-08-30': {
                    'Times': ['19:20 - 20:00'],
                    'Prices': ['£11.90'],
                    'Spaces': ['1']
                    },
                }
            },
        'Distance': '0.122km'
        },
    'Rainbow Leisure Centre, Epsom': {
        'Address': 'East Street, Epsom, Surrey, KT17 1BN',
        'Activity': {
            'badminton-60min': {
                '2023-09-02': {
                    'Times': ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00'],
                    'Prices': ['£14.00', '£14.00', '£14.00', '£14.00', '£14.00', '£14.00', '£14.00', '£14.00'],
                    'Spaces': ['3', '7', '7', '7', '7', '7', '8', '3']
                    }
                }
            }
        'Distance': '4.402km'
        }
    }
    """

    geolocator = Nominatim(user_agent="aaaa")
    home = geolocator.geocode(Loc)
    home_coords = (home.latitude, home.longitude)

    FindCentre_url = "https://www.better.org.uk/centre-locator"

    driver = webdriver.Chrome()
    driver.get(FindCentre_url)
    webwait(driver, "NAME", 'venue_search[searchterm]', timeout).send_keys(Loc)
    Select(driver.find_elements(By.NAME, 'venue_search[business_sector_id]')[1]).select_by_value('2')
    driver.find_element(By.XPATH, "/html[1]/body[1]/main[1]/div[2]/div[1]/form[1]/div[4]/button[1]").click()


    centre_names = [x.text for x in webwait_all(driver, "CSS_SELECTOR", "[class^='venue-result-panel__link']", timeout)][:max_centres]
    centre_addresses = [x.text for x in webwait_all(driver, "CSS_SELECTOR", "[class^='venue-result-panel__address']", timeout)][:max_centres]
    centre_booking_items = webwait_all(driver, "CSS_SELECTOR", "[class^='call-to-action call-to-action--primary venue-result-panel__btn']", timeout)
    centre_booking_links = [x.get_attribute('href') for x in centre_booking_items if 'bookings.better' in x.get_attribute('href')][:max_centres]

    print(centre_booking_links, centre_names, centre_addresses)
    if max_centres is None or max_centres > len(centre_booking_links):
        max_centres = len(centre_booking_links)

    driver.close()

    BETTER_gym_dict = p_map(partial(BETTER_gym_loop, activity=activity, home_coords=home_coords, timeout=timeout),
                             centre_booking_links, centre_names, centre_addresses, num_cpus=cpu_cores)

    BETTER_gym_dict = {k: v for d in BETTER_gym_dict if d is not None for k, v in d.items()}

    return BETTER_gym_dict
