from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
import selenium.common.exceptions
from selenium import webdriver

from geopy.geocoders import Nominatim, GoogleV3
from geopy import distance

from functools import partial
from p_tqdm import p_map
from tqdm import tqdm
from time import time
import numpy as np
import math

from tools import webwait, webwait_all, latlon2metres


def Places_Leisure_loop(link, centre_name, centre_distance, Act, timeout):
    Places_dict = {}
    driver = webdriver.Chrome()

    retry_count = 0
    driver.get(link)
    while True:
        try:
            activities = webwait(driver, 'CLASS_NAME', "activity-locations__list", timeout)
            break

        except:
            retry_count += 1
            print(f'Retrying link {link}, attempt {retry_count}')
            driver.refresh()

    activities_items = webwait_all(
        activities, 'CLASS_NAME', "activity-locations__list-item", timeout)

    activities_names = [x.text.lower() for x in webwait_all(
        activities, 'CLASS_NAME', "activity-locations__link", timeout)]

    if 'sports' in activities_names:
        sports_item = activities_items[activities_names.index('sports')]

    else:
        return None

    while True:
        try:
            cookie_reject = webwait(driver, 'ID', "cookiescript_reject", timeout)
            cookie_reject.click()
            break

        except:
            break

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sports_item)
    sports_item.click()

    activity_days = webwait_all(driver, 'CLASS_NAME', "activity-days__list-item", timeout)
    activities_days_date_text = [x.text for x in webwait_all(driver, 'CLASS_NAME', "activity-days__date", timeout)]
    index_1 = [x for x in range(len(activities_days_date_text)) if activities_days_date_text[x].strip() != ''][0]

    activity_days = activity_days[index_1:]

    dates_dict = {}

    for i, activity_day in enumerate(activity_days):

        while True:
            activities_days_date_text = [x.text for x in
                                         webwait_all(driver, 'CLASS_NAME', "activity-days__date", timeout)]
            if activities_days_date_text[i + index_1].strip() == '':
                webwait(driver, 'CLASS_NAME', "slick-next.slick-arrow", timeout).click()

            else:
                break

        activity_groups = webwait_all(activity_day, 'CLASS_NAME', "activities-group", timeout)
        activity_groups.extend(webwait_all(activity_day, 'CLASS_NAME', "activities-group.is-open", timeout))

        for activity_group in activity_groups:
            try:
                if activity_group.get_attribute('class').strip() == "activities-group":
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", activity_group)
                    activity_group.click()

            except:
                pass

        sessions = webwait_all(activity_day, 'CLASS_NAME', "activities-group__sessions", timeout)
        session_date = sessions[0].get_attribute('data-date')

        times, prices, spaces_avail = [], [], []

        for session in sessions:

            cards = np.array(webwait_all(session, 'CLASS_NAME', "timetable-card", timeout))
            info_btns = np.array(
                webwait_all(
                    session, 'CLASS_NAME',
                    "timetable-card__btn.c-btn.c-btn--primary.c-btn--medium.c-btn-hover", timeout))

            titles = np.array([x.text.lower() for x in
                               webwait_all(session, 'CLASS_NAME', "timetable-card__title", timeout)])
            valid_indices = np.where(np.char.find(titles, Act.lower()) >= 0)[0]
            cards = cards[valid_indices]
            info_btns = info_btns[valid_indices]
            for card, info_btn in zip(cards, info_btns):
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                card.click()
                info_btn.click()

                court_options = webwait(driver, 'CLASS_NAME', "session-info__sublocationgroups", timeout)
                courts = webwait_all(court_options, 'NAME', "sublocationgroup", timeout)
                if not courts:
                    webwait(driver, 'CLASS_NAME', "modal__close", timeout).click()
                    continue

                time_ = webwait(driver, 'CLASS_NAME', "session-info__time", timeout).text
                price = webwait(driver, 'CLASS_NAME', "session-info__price2", timeout).text.split('&')[]

                times.append(time_)
                prices.append(price)
                spaces_avail.append(len(courts))

                webwait(driver, 'CLASS_NAME', "modal__close", timeout).click()

        dates_dict[session_date] = {'Times': np.array(times.copy()),
                                    'Prices': np.array(prices.copy()),
                                    'Spaces': np.array(spaces_avail.copy())}

    centre_address = centre_address.replace('\n', ', ')
    Places_dict[centre_name] = {'Address': centre_address, 'Activity': {},
                                'Distance': centre_distance / 1000, 'Company': 'BETTER'}

    valid_activities_names = np.array(activities_names)[valid_activities_indexes]
    valid_links = [link + '/' + z.lower().replace(' ', '-') for z in valid_activities_names]

    for activity_link in valid_links:
        driver.get(activity_link)
        activity = activity_link.split('/')[-1]
        retry_count = 0
        while True:
            try:
                dates_tab = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "DateRibbonComponent__DatesWrapper-sc-p1q1bx-1.iDJlaR")
                    )
                )
                break
            except:
                retry_count += 1
                print(f'Retrying link {activity_link}, attempt {retry_count}')
                driver.refresh()

        all_dates_links = [x.get_attribute('href') for x in WebDriverWait(dates_tab, timeout).until(
            EC.presence_of_all_elements_located(
                (By.TAG_NAME, "a")
            )
        ) if 'undefined' not in x.get_attribute('href')]
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
                             driver.find_elements(By.CLASS_NAME,
                                                  "ClassCardComponent__ClassTime-sc-1v7d176-3.jaVGAY")]
                    if not times:
                        raise Exception("")
                    found = True
                    break
                except:
                    pass

                try:
                    driver.find_element(By.CLASS_NAME,
                                        "ByTimeListComponent__Wrapper-sc-39liwv-1."
                                        "ByTimeListComponent__NoContentWrapper-sc-39liwv-2.SqNmL.cUXVSN"
                                        )
                    found = False
                    break
                except:
                    pass
                end_time = time()
                if end_time - start_time > timeout:
                    start_time = time()
                    retry_count += 1
                    print(f'Retrying link {activity_link}, attempt {retry_count}')
                    driver.refresh()

            if not found:
                continue

            prices = [x.text.lower() for x in WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "ClassCardComponent__Price-sc-1v7d176-14.cUTjXm")
                )
            )]
            spaces_avail = [x.text.lower().split(' ')[0] for x in WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "ContextualComponent__BookWrap-sc-eu3gk6-1.fiQwml")
                )
            )]

            valid_indexes = np.array([x for x in range(len(spaces_avail)) if spaces_avail[x] != '0'])
            if valid_indexes.size == 0:
                continue

            dates_dict[date] = {'Times': np.array(times.copy())[valid_indexes],
                                'Prices': np.array(prices.copy())[valid_indexes],
                                'Spaces': np.array(spaces_avail.copy())[valid_indexes]}

        Places_dict[centre_name]['Activity'][activity] = dates_dict.copy()

    driver.close()
    return Places_dict


# Function for BETTER gyms/centres
def Places_Leisure(Loc, Act, max_centres=20, cpu_cores=4, timeout=10):
    """
    :param Loc: Location which to search from. Postcodes work best.
    :param Act: Activity e.g: 'Badminton', 'Basketball'
    :param max_centres: Take closest 'n' centres from Loc
    :param cpu_cores: Number of parallel tabs to be open. Each tab is a different centre
    :param timeout: Maximum wait time for website to load. If slow internet, increase this.
    :return: dictionary of centres and corresponding info in the following example structure:
    """

    Places_dict = {}

    geolocator = Nominatim(user_agent="aaaa")
    home = geolocator.geocode(Loc)
    home_coords = (home.latitude, home.longitude)

    FindCentre_url = "https://www.placesleisure.org/find-centre/"

    driver = webdriver.Chrome()
    driver.get(FindCentre_url)
    centre_elements = np.array(WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, 'our-centres__item'))))
    centre_names = np.array([x.get_attribute('data-name') for x in centre_elements])
    centre_lat_lon = [(float(x.get_attribute('data-lat')), float(x.get_attribute('data-long'))) for x in
                      centre_elements]
    centre_distances = np.array([latlon2metres((x[0], x[1]), home_coords) for x in centre_lat_lon])
    sorted_indices = np.argsort(centre_distances)

    centre_elements = centre_elements[sorted_indices][:max_centres]
    centre_names = centre_names[sorted_indices][:max_centres]
    centre_distances = centre_distances[sorted_indices][:max_centres]

    centre_links = [(WebDriverWait(x, timeout).until(
        EC.presence_of_element_located(
            (By.CLASS_NAME, 'c-btn.c-btn--primary.b-centre-card__link')
        )).get_attribute('href')) for x in centre_elements]

    # centre_adresses = [(WebDriverWait(x, timeout).until(
    #     EC.presence_of_element_located(
    #         (By.XPATH, 'b-centre-card__address')
    #     ))).text for x in centre_elements]

    driver.close()

    func = partial(Places_Leisure_loop, Act=Act, timeout=timeout)
    results = p_map(func, centre_links, centre_names, centre_distances, num_cpus=cpu_cores)
    for result in results:
        if result is None:
            continue
        Places_dict.update(result)

    if not Places_dict:
        return None

    return Places_dict
