from os import environ as ENV
from functools import partial
from io import StringIO
import datetime
import json
import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium import webdriver

from geopy import distance

from p_tqdm import p_map
import pandas as pd


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


def find_master_table(driver: WebDriver, timeout: int = 10) -> WebElement | None | bool:
    """Check if master table is present. Return None if there are no slots are avail,
    return False if the booking is not of table type"""

    start = time.time()
    while (time.time() - start) <= timeout:
        try:
            availability_grid = driver.find_element(
                By.CLASS_NAME, "masterTable ")

            return availability_grid

        except NoSuchElementException:
            pass

        try:
            no_slots_msg = driver.find_element(
                By.CLASS_NAME, "alert.alert-warning").text
            if no_slots_msg.lower().startswith("no "):
                return None

        except NoSuchElementException:
            pass

        try:
            driver.find_element(
                By.CLASS_NAME, "btn.btn-success ")
            return False

        except NoSuchElementException:
            pass

    return False


def read_master_table(driver: WebDriver, timeout: int) -> tuple[list[int] | None,
                                                                list[str] | None,
                                                                list[str] | None]:
    """Read table of available bookings"""

    availability_grid = find_master_table(driver, timeout)

    if availability_grid == False:
        return None, None, None

    if availability_grid is None:
        return [], [], []

    rows = webwait_all(availability_grid, 'TAG_NAME', "tr", timeout)[1:]

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


def search_parameters(driver: WebDriver, adv_search_panel: WebElement, centre_name: str, timeout: int) -> tuple[Select, list[str]]:
    """Fill in the search page with appropriate parameters"""

    start = time.time()
    while (time.time() - start) <= timeout:
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

    return None, None


def filter_activity_options(activity: str, options: list[str]) -> list[str]:
    """return valid activity options that match the specified activity"""

    return [x for x in options if activity.lower() in x.lower()]


def setup_search_page(driver: WebDriver, booking_link: str, centre_name: str, login: bool = True, timeout: int = 10) -> Select:
    """Setup EA search page with correct parameters and return scroll object for activity selection"""

    driver.get(booking_link)

    if login:
        ea_login(driver, timeout)

    webwait(driver, 'ID', "bookingFrame", timeout)
    driver.switch_to.frame('bookingFrame')

    adv_search_panel = find_search_panel(driver, timeout)
    scroll_into_view(driver, adv_search_panel)

    return search_parameters(driver, adv_search_panel, centre_name, timeout)


def check_for_no_results(driver: WebDriver) -> bool:
    """Check if booking page shows up with no results"""

    try:
        alert_text = driver.find_element(By.CLASS_NAME,
                                         'alert.alert-warning').text
        if 'no results' in alert_text.lower():
            return True

        return False

    except:
        return False


def find_avail_button(driver: WebDriver) -> tuple[WebElement, str, str] | tuple[None, str, str]:
    """Find and check string in availability button"""

    for block in ['col-sm-12.btn-group.btn-block', 'btn-group.btn-block']:

        try:
            activity_btn = driver.find_element(By.CLASS_NAME, block)
        except NoSuchElementException:
            continue

        for btn in ['btn.btn-success-wait.availabilitybutton ', 'btn.btn-danger-wait.availabilitybutton ']:
            try:
                avail_text_btn = activity_btn.find_element(By.CLASS_NAME, btn)
                activity_name = activity_btn.find_element(By.CLASS_NAME,
                                                          'BookingLinkButton.btn.btn-primary ').text.strip()
            except NoSuchElementException:
                continue

            if avail_text_btn.text.lower() in ['space', 'full']:
                return avail_text_btn, avail_text_btn.text, activity_name

    return None, '', ''


def read_bookings(driver: WebDriver, timeout: int = 10) -> tuple[list[int], list[str], list[str]]:
    """Read table data spanning over 2 weeks"""

    table_data1, index1, columns1 = read_master_table(driver, timeout)

    if table_data1 is None:
        return [], [], []

    date_window_text = webwait(driver, 'ID',
                               "ctl00_MainContent_startDate",
                               timeout).text

    webwait(driver, 'ID',
            "ctl00_MainContent_dateForward1", timeout).click()

    date_window_text2 = date_window_text

    while date_window_text2 == date_window_text or date_window_text2 == '':
        try:
            date_window_text2 = webwait(
                driver, 'ID', "ctl00_MainContent_startDate", timeout).text
        except:
            continue

    table_data2, index2, columns2 = read_master_table(driver, timeout)

    if not table_data1 and not table_data2:
        return [], [], []

    if table_data1 and not table_data2:
        return table_data1, index1, columns1

    if table_data2 and not table_data1:
        return table_data2, index2, columns2

    columns = [*columns1, *columns2]
    table_data = table_data1.copy()
    for i, row in enumerate(table_data):
        row.extend(table_data2[i])

    return table_data, index1, columns


def compile_table_data_into_dict(table_data: list[list[int]], index: list[str], columns: list[str]) -> dict:
    """Convert the nested table data into a easier to use dict object"""

    dates_dict = {}
    for col_idx, date in enumerate(columns):
        times = []
        prices = []
        spaces_avail = []

        for row_idx, value in enumerate(table_data):
            if value[col_idx] == 1:
                times.append(index[row_idx])
                prices.append('NaN')
                spaces_avail.append('NaN')

        if times:
            dates_dict[date] = {
                'Times': times,
                'Prices': prices,
                'Spaces': spaces_avail
            }

    return dates_dict


def click_and_wait_search(driver: WebDriver, timeout: int = 10) -> None:
    """Click search button and wait untill it is finished"""

    start = time.time()
    while (time.time() - start) <= timeout:
        try:
            webwait(driver, 'ID',
                    "ctl00_MainContent__advanceSearchUserControl__searchBtn",
                    timeout).click()
            break

        except ElementClickInterceptedException:
            pass

    start = time.time()
    while (time.time() - start) <= timeout:
        try:
            search_btn = driver.find_element(
                By.ID, "ctl00_MainContent__advanceSearchUserControl__searchBtn")
            if search_btn.get_attribute("disabled") is None:
                break

        except StaleElementReferenceException:
            pass


def wait_for_slots_table_to_load(driver: WebDriver, timeout: int = 10) -> None:
    """Wait for table with booking slots to load"""

    start = time.time()
    while (time.time() - start) <= timeout:
        try:
            driver.find_element(By.ID, 'slotsGrid')
            break

        except NoSuchElementException:
            pass


def loop_through_activities(driver: WebDriver, act_scroll: Select, activity_options: list[str],
                            centre_name: str, booking_link: str, timeout: int = 10) -> dict[str:str]:
    """Loop through and scrape info of each activity for a given centre"""

    activity_dict = {}

    for i, option in enumerate(activity_options):

        while True:
            try:
                act_scroll.select_by_visible_text(option)
                break

            except NoSuchElementException:
                pass

        click_and_wait_search(driver, timeout)

        no_results = False
        start = time.time()
        while (time.time() - start) <= timeout:

            if check_for_no_results(driver):
                no_results = True
                break

            avail_text_btn, avail_text, activity_text = find_avail_button(
                driver)
            if activity_text == option:
                break

        if no_results or not avail_text.lower() == 'space' or activity_text != option:
            continue

        avail_text_btn.click()
        wait_for_slots_table_to_load(driver, timeout)

        table_data, index, columns = read_bookings(driver, timeout)
        if table_data:
            dates_dict = compile_table_data_into_dict(
                table_data, index, columns)
            activity_dict[option] = dates_dict.copy()

        if not i + 1 == len(activity_options):
            act_scroll, _ = setup_search_page(driver, booking_link,
                                              centre_name, False, timeout)

    return activity_dict


def ea_gym_loop(centre_name, centre_distance, activity, timeout):
    """Scrape info from a certain centre"""

    booking_link = 'https://profile.everyoneactive.com/booking'

    with webdriver.Chrome() as driver:
        act_scroll, act_options = setup_search_page(driver, booking_link,
                                                    centre_name, True, timeout)

        if act_scroll is None:
            print(f'{centre_name} cannot be found')
            driver.close()
            return None

        valid_act_options = filter_activity_options(activity, act_options)

        if not valid_act_options:
            print(f'{activity} is not available at: {centre_name}')
            driver.close()
            return None

        activity_dict = loop_through_activities(driver, act_scroll,
                                                valid_act_options, centre_name,
                                                booking_link, timeout)

    if activity_dict == {}:
        return None

    return {centre_name: {'Address': 'N/A', 'Activity': activity_dict,
                          'Distance': centre_distance,
                          'Company': 'Everyone Active'}}


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
        centre_coords = [f'[{extract_coords_from_link(x.get_attribute("href"))}]'
                         for x in driver.find_elements(By.CLASS_NAME,
                                                       'centre-finder__results-details-link.link--external')]

    valid_indexes = [centre_coords.index(x)
                     for x in centre_coords if x != '[, ]']
    centre_names = [centre_names[x] for x in valid_indexes]

    centre_coords = [centre_coords[x] for x in valid_indexes]
    centre_coords = [json.loads(x) for x in centre_coords]
    centre_distances = [round(distance.geodesic(home_coords, x).km, 3)
                        for x in centre_coords]

    ordered_indexes = [x[0] for x in sorted(enumerate(centre_distances),
                                            key=lambda x: x[1])]

    centre_names = [centre_names[x]
                    for x in ordered_indexes][:max_centres]
    centre_distances = [centre_distances[x] for x in ordered_indexes]

    return centre_names, centre_distances


def scrape_ea_website(postcode, activity, max_centres=20, cpu_cores=4, timeout=10):
    """Perform web scraping of EA websites"""

    all_centre_names, all_centre_distances = get_all_centre_info(postcode,
                                                                 max_centres, timeout)

    EA_dict = {}

    func = partial(ea_gym_loop, activity=activity, timeout=timeout)
    results = p_map(func, all_centre_names, all_centre_distances,
                    num_cpus=cpu_cores)

    for result in results:
        if result is None:
            continue
        EA_dict.update(result)

    if not EA_dict:
        return {}

    return EA_dict
