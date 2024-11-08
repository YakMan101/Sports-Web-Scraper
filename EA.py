from os import environ as ENV
from functools import partial
from io import StringIO
import datetime
import json
import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium import webdriver

from geopy import distance

from p_tqdm import p_map
import pandas as pd
import numpy as np


from tools import webwait, webwait_all, similar, get_coordinates, scroll_into_view, return_similar_strings


def ea_login(driver, timeout):
    """Login to ea account if prompted"""

    try:
        webwait(driver, 'ID', "CybotCookiebotDialogBodyButtonDecline",
                timeout).click()
    except:
        pass

    webwait(driver, 'ID', "emailAddress", timeout).send_keys(ENV['EMAIL'])
    webwait(driver, 'ID', "password", timeout).send_keys(ENV['EA_PASS'])
    webwait(driver, 'CSS_SELECTOR', 'button[type="submit"]', timeout).click()


def read_master_table(driver, timeout):
    """Read table of available bookings"""

    try:
        availabilty_grid = webwait(
            driver, 'CLASS_NAME', "masterTable ", timeout)
    except:
        return None, None, None

    rows = webwait_all(availabilty_grid, 'TAG_NAME', "tr", timeout)[1:]

    table = driver.find_element(By.CLASS_NAME, 'masterTable ')
    table_html = table.get_attribute('outerHTML')
    df = pd.read_html(StringIO(table_html))[0]
    df.set_index('-', inplace=True)
    index = df.index
    columns = df.columns

    table_data = [
        [1 if 'itemavailable' in cell.get_attribute('class') else 0
         for cell in row.find_elements(By.TAG_NAME, 'td')[1:]]
        for row in rows]

    return table_data, index, columns


def clean_centre_name(centre_name: str) -> str:
    """Remove certain words from centre name and make all lower case"""

    items_to_remove = ['leisure centre', 'the', 'l c', 'lc']
    cleaned_centre_name = centre_name.lower()
    for item in items_to_remove:
        cleaned_centre_name = cleaned_centre_name.replace(item, '')

    return cleaned_centre_name.strip()


def find_search_panel(driver: WebDriver, timeout: int) -> WebElement:
    """Return the search panel object"""

    panels = webwait_all(driver, 'CLASS_NAME', "panel.panel-default", timeout)
    panel_names = [x.text.lower() for x in panels]
    return panels[panel_names.index('advanced search')]


def expand_adv_search_panel(adv_search_panel: WebElement) -> None:
    """Expand advanced search panel so the scroll element can be retrieved"""

    adv_search_panel_expanded = adv_search_panel.find_element(
        By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')

    if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
        adv_search_panel.click()


def get_centre_scroll_element(driver: WebDriver, timeout: int) -> WebElement:
    """Return scroll object to select centres"""

    return Select(webwait(driver, 'ID',
                          "ctl00_MainContent__advanceSearchUserControl_SitesAdvanced", timeout))


def get_centre_options(driver: WebDriver, adv_search_panel: WebElement, timeout: int) -> tuple[list[str], WebElement]:
    """Return list of centres obtained from centre scroller"""

    while True:
        expand_adv_search_panel(adv_search_panel)
        centre_scroll = get_centre_scroll_element(driver, timeout)

        centre_options = [clean_centre_name(x.text.lower())
                          for x in centre_scroll.options]

        if '' not in centre_options:
            return centre_scroll, centre_options


def select_end_date(driver: WebDriver, timeout: int) -> None:
    """Select 2 weeks from now on the date range selector"""

    end_date_selector = webwait(
        driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_endDate", timeout)
    end_date = (datetime.date.today() +
                datetime.timedelta(days=14)).strftime("%d/%m/%Y")
    end_date_selector.clear()
    end_date_selector.send_keys(end_date)


def get_activity_options(driver: WebDriver, timeout: int) -> tuple[Select, list[str]]:
    """Return list of activities available at centre"""

    act_scroll = Select(
        webwait(driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_Activities", timeout))

    return act_scroll, [x.text for x in act_scroll.options]


def search_parameters(driver: webdriver, adv_search_panel: WebElement, centre_name: str, timeout: int) -> tuple[Select, list[str]]:
    start = time.time()
    while True:
        if (time.time() - start) >= timeout:
            return None, None

        try:
            centre_scroll, centre_options = get_centre_options(driver, adv_search_panel,
                                                               timeout)
            cleaned_centre_name = clean_centre_name(centre_name)
            matching_centres = return_similar_strings(cleaned_centre_name, centre_options,
                                                      0.6)
            centre_index = centre_options.index(matching_centres[0][0])

            centre_scroll.select_by_index(centre_index)
            select_end_date(driver, timeout)

            act_scroll, act_options = get_activity_options(driver, timeout)

            return act_scroll, act_options

        except (IndexError, StaleElementReferenceException):
            continue


def filter_activity_options(activity: str, options: list[str]) -> list[str]:
    """return valid activity options that match the specified activity"""

    return [x for x in options if activity.lower() in x.lower()]


def ea_gym_loop(centre_name, centre_address, centre_distance, activity, timeout):
    EA_dict = {}
    booking_link = 'https://profile.everyoneactive.com/booking'

    driver = webdriver.Chrome()
    driver.get(booking_link)

    ea_login(driver, timeout)

    webwait(driver, 'ID', "bookingFrame", timeout)
    driver.switch_to.frame('bookingFrame')

    adv_search_panel = find_search_panel(driver, timeout)
    scroll_into_view(driver, adv_search_panel)

    act_scroll, act_options = search_parameters(
        driver, adv_search_panel, centre_name, timeout)

    if act_scroll is None:
        print(f'{centre_name} cannot be found')
        driver.close()
        return None

    valid_act_options = filter_activity_options(activity, act_options)

    if not valid_act_options:
        print(f'{activity} is not available at: {centre_name}')
        driver.close()
        return None

    EA_dict[centre_name] = {'Address': centre_address.replace('\n', ', '), 'Activity': {},
                            'Distance': centre_distance, 'Company': 'Everyone Active'}

    print(centre_address)
    for i, option in enumerate(valid_act_options):
        # Needed to remind the scroll object that it has options for some reason.
        act_scroll.options
        act_scroll.select_by_visible_text(option)

        webwait(driver, 'ID',
                "ctl00_MainContent__advanceSearchUserControl__searchBtn", timeout).click()

        avail_text = ''
        no_results = False
        start = time.time()
        while True:
            if (time.time() - start) >= timeout + 2:
                if not i + 1 == len(valid_act_options):
                    driver.get(booking_link)
                    webwait(driver, 'ID', "bookingFrame", timeout)
                    driver.switch_to.frame('bookingFrame')

                    panels = webwait_all(
                        driver, 'CLASS_NAME', "panel.panel-default", timeout)
                    panel_names = [x.text.lower() for x in panels]
                    adv_search_panel = panels[panel_names.index(
                        'advanced search')]
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", adv_search_panel)
                    adv_search_panel_expanded = adv_search_panel.find_element(
                        By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
                    if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
                        adv_search_panel.click()

                    act_scroll, act_options = search_parameters(
                        driver, adv_search_panel, centre_name, timeout)
                break

            try:
                try:
                    alert_text = driver.find_element(
                        By.CLASS_NAME, 'alert.alert-warning').text
                    if 'No results' in alert_text:
                        no_results = True
                        break
                except:
                    pass
                activity_btn = driver.find_element(
                    By.CLASS_NAME, 'col-sm-12.btn-group.btn-block')
                avail_text = activity_btn.find_element(
                    By.CLASS_NAME, 'btn.btn-success-wait.availabilitybutton ')
                if not avail_text.text == '':
                    break

                activity_btn = driver.find_element(
                    By.CLASS_NAME, 'btn-group.btn-block')
                avail_text = activity_btn.find_element(
                    By.CLASS_NAME, 'btn.btn-success-wait.availabilitybutton ')
                if not avail_text.text == '':
                    break

            except:
                continue

        if no_results or avail_text == '' or not avail_text.text == 'Space':
            continue

        avail_text.click()

        try:
            table_data1, index, columns1 = read_master_table(driver, timeout)

            date_window_text = webwait(
                driver, 'ID', "ctl00_MainContent_startDate", timeout).text

            webwait(driver, 'ID', "ctl00_MainContent_dateForward1",
                    timeout).click()

            date_window_text2 = date_window_text

            while date_window_text2 == date_window_text or date_window_text2 == '':
                try:
                    date_window_text2 = webwait(
                        driver, 'ID', "ctl00_MainContent_startDate", timeout).text
                except:
                    continue

            table_data2, index, columns2 = read_master_table(driver, timeout)

            columns = [*columns1, *columns2]
            table_data = np.hstack(
                (np.array(table_data1), np.array(table_data2)))
            del columns1, columns2, table_data1, table_data2

            df = pd.DataFrame(table_data, index=index, columns=columns)

            dates_dict = {}
            for date in columns:
                times = [index[x]
                         for x in range(len(df[date])) if df[date].iloc[x] == 1]
                if not times:
                    continue
                prices = ['NaN'] * len(times)
                spaces_avail = ['NaN'] * len(times)
                dates_dict[date] = {'Times': np.array(times.copy()),
                                    'Prices': np.array(prices.copy()),
                                    'Spaces': np.array(spaces_avail.copy())}

            EA_dict[centre_name]['Activity'][options_name] = dates_dict.copy()
        except:
            pass

        if not i + 1 == len(valid_act_options):
            driver.get(booking_link)
            webwait(driver, 'ID', "bookingFrame", timeout)
            driver.switch_to.frame('bookingFrame')

            panels = webwait_all(driver, 'CLASS_NAME',
                                 "panel.panel-default", timeout)
            panel_names = [x.text.lower() for x in panels]
            adv_search_panel = panels[panel_names.index('advanced search')]
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", adv_search_panel)
            adv_search_panel_expanded = adv_search_panel.find_element(
                By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
            if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
                adv_search_panel.click()

            act_scroll, act_options = search_parameters(
                driver, adv_search_panel, centre_name, timeout)

    if EA_dict[centre_name]['Activity'] == {}:
        return None
    driver.close()
    return EA_dict


def extract_coords_from_link(link: str) -> str:
    """Get coordinates in the form of '[lat, lon]' embedded in website link"""

    return link.split("/")[-1].replace(",", ", ")


def reject_cookies(driver: WebDriver, timeout: int = 5):
    """Try to reject cookies if popup appears"""

    try:
        webwait(driver, 'ID',
                'CybotCookiebotDialogBodyButtonDecline', timeout=timeout).click()

    except TimeoutException:
        print('Cookies popup not found')


def get_all_centre_info(postcode: str, max_centres: int = 10, timeout: int = 10) -> tuple[list, list, list]:
    """Get name, address and distance of all EA centres and order 
    in terms of distance and only return closest 'max_centres' centres"""

    home_coords = get_coordinates(postcode)

    with webdriver.Chrome() as driver:

        centres_page = "https://www.everyoneactive.com/centre/"
        driver.get(centres_page)

        reject_cookies(driver)

        centres = webwait_all(driver, 'CLASS_NAME',
                              "centre-finder__results-item-name", timeout)
        centre_names = [x.find_element(By.TAG_NAME, "a").text
                        for x in centres]

        centre_addresses = [x.text for x in driver.find_elements(By.CLASS_NAME,
                                                                 'centre-finder__results-details-address')]
        centre_coords = [f'[{extract_coords_from_link(x.get_attribute("href"))}]'
                         for x in driver.find_elements(By.CLASS_NAME,
                                                       'centre-finder__results-details-link.link--external')]

    valid_indexes = [centre_coords.index(x)
                     for x in centre_coords if x != '[, ]']
    centre_names = [centre_names[x] for x in valid_indexes]
    centre_addresses = [centre_addresses[x] for x in valid_indexes]

    centre_coords = [centre_coords[x] for x in valid_indexes]
    centre_coords = [json.loads(x) for x in centre_coords]
    centre_distances = [round(distance.geodesic(home_coords, x).km, 3)
                        for x in centre_coords]

    ordered_indexes = [x[0] for x in sorted(enumerate(centre_distances),
                                            key=lambda x: x[1])]

    centre_names = [centre_names[x]
                    for x in ordered_indexes][:max_centres]
    centre_addresses = [centre_addresses[x] for x in ordered_indexes]
    centre_distances = [centre_distances[x] for x in ordered_indexes]

    return centre_names, centre_addresses, centre_distances


def scrape_ea_website(postcode, activity, max_centres=20, cpu_cores=4, timeout=10):
    """Perform web scraping of EA websites"""

    all_centre_names, all_centre_addresses, all_centre_distances = get_all_centre_info(
        postcode, max_centres, timeout)

    EA_dict = {}

    func = partial(ea_gym_loop, activity=activity, timeout=timeout)
    results = p_map(func, all_centre_names, all_centre_addresses,
                    all_centre_distances, num_cpus=cpu_cores)

    for result in results:
        if result is None:
            continue
        EA_dict.update(result)

    if not EA_dict:
        return {}

    return EA_dict
