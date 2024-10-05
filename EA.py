from os import environ as ENV
from difflib import SequenceMatcher
from functools import partial
from io import StringIO
import datetime
import json
import time

from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium import webdriver

from geopy.geocoders import Nominatim
from geopy import distance

from p_tqdm import p_map
import pandas as pd
import numpy as np


from tools import webwait, webwait_all

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def EA_login(driver, timeout):
    try:
        webwait(driver, 'ID', "CybotCookiebotDialogBodyButtonDecline", timeout).click()
    except:
        pass

    webwait(driver, 'ID', "emailAddress", timeout).send_keys(ENV['EMAIL'])
    webwait(driver, 'ID', "password", timeout).send_keys(ENV['EA_PASS'])
    webwait(driver, 'CSS_SELECTOR', 'button[type="submit"]', timeout).click()


def read_master_table(driver, timeout):
    try:
        availabilty_grid = webwait(driver, 'CLASS_NAME', "masterTable ", timeout)
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


def search_paramters(driver, timeout, adv_search_panel, centre_name, centre_options):
    start = time.time()
    while True:
        if (time.time() - start) >= timeout + 2:
            return None, None

        try:
            adv_search_panel_expanded = adv_search_panel.find_element(
                By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
            if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
                adv_search_panel.click()

            centre_scroll = Select(webwait(
                driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_SitesAdvanced", timeout))

            matching_centres = [x for x in centre_options if similar(centre_name, x) >= 0.6]

            matching_centres = sorted(matching_centres, key=lambda x: similar(x, centre_name), reverse=True)
            centre_index = centre_options.index(matching_centres[0])
            centre_scroll.select_by_index(centre_index)

            end_date_selecter = webwait(driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_endDate", timeout)
            end_date = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%d/%m/%Y")
            end_date_selecter.clear()
            end_date_selecter.send_keys(end_date)

            act_scroll = Select(
                webwait(driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_Activities", timeout))
            act_options = [x.text for x in act_scroll.options]

            return act_scroll, act_options

        except:
            continue


def EA_gym_loop(centre_name, centre_address, centre_distance, Act, timeout):
    EA_dict = {}
    booking_link = 'https://profile.everyoneactive.com/booking'

    driver = webdriver.Chrome()
    driver.get(booking_link)

    EA_login(driver, timeout)

    webwait(driver, 'ID', "bookingFrame", timeout)
    driver.switch_to.frame('bookingFrame')

    panels = webwait_all(driver, 'CLASS_NAME', "panel.panel-default", timeout)
    panel_names = [x.text.lower() for x in panels]
    adv_search_panel = panels[panel_names.index('advanced search')]
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", adv_search_panel)

    centre_name_original = centre_name
    centre_name = centre_name.lower().replace('leisure centre', '').strip()
    centre_name = centre_name.replace('the', '').strip()
    centre_name = centre_name.replace('l c', '').strip()
    centre_name = centre_name.replace('lc', '').strip()

    while True:
        adv_search_panel_expanded = adv_search_panel.find_element(
            By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
        if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
            adv_search_panel.click()

        centre_scroll = Select(
            webwait(driver, 'ID', "ctl00_MainContent__advanceSearchUserControl_SitesAdvanced", timeout))

        centre_options = [x.text.lower() for x in centre_scroll.options]
        centre_options = [x.replace('leisure centre', '').strip() for x in centre_options]
        centre_options = [x.replace('the', '').strip() for x in centre_options]
        centre_options = [x.replace('l c', '').strip() for x in centre_options]
        centre_options = [x.replace('lc', '').strip() for x in centre_options]

        if '' not in centre_options:
            break

    act_scroll, act_options = search_paramters(driver, timeout, adv_search_panel, centre_name, centre_options)
    if act_scroll is None:
        print(f'{centre_name_original} cannot be found')
        driver.close()
        return None

    act_options_lower_case = [x.lower() for x in act_options]
    valid_act_options_names = [act_options[x] for x in range(len(act_options_lower_case))
                               if Act.lower() in act_options_lower_case[x]]

    valid_act_options_names = [x for x in valid_act_options_names if 'mixed' not in x.lower()]

    if not valid_act_options_names:
        print(f'{Act} is not available at: {centre_name_original}')
        driver.close()
        return None

    centre_address = centre_address.replace('\n', ', ')
    EA_dict[centre_name_original] = {'Address': centre_address, 'Activity': {}, 'Distance': centre_distance,
                                     'Company': 'Everyone Active'}

    for i, options_name in enumerate(valid_act_options_names):
        act_scroll.select_by_visible_text(options_name)
        webwait(driver, 'ID', "ctl00_MainContent__advanceSearchUserControl__searchBtn", timeout).click()

        avail_text = ''
        no_results = False
        start = time.time()
        while True:
            if (time.time() - start) >= timeout + 2:
                if not i + 1 == len(valid_act_options_names):
                    driver.get(booking_link)
                    webwait(driver, 'ID', "bookingFrame", timeout)
                    driver.switch_to.frame('bookingFrame')

                    panels = webwait_all(driver, 'CLASS_NAME', "panel.panel-default", timeout)
                    panel_names = [x.text.lower() for x in panels]
                    adv_search_panel = panels[panel_names.index('advanced search')]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", adv_search_panel)
                    adv_search_panel_expanded = adv_search_panel.find_element(
                        By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
                    if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
                        adv_search_panel.click()

                    act_scroll, act_options = search_paramters(driver, timeout, adv_search_panel, centre_name,
                                                               centre_options)
                break

            try:
                try:
                    alert_text = driver.find_element(By.CLASS_NAME, 'alert.alert-warning').text
                    if 'No results' in alert_text:
                        no_results = True
                        break
                except:
                    pass
                activity_btn = driver.find_element(By.CLASS_NAME, 'col-sm-12.btn-group.btn-block')
                avail_text = activity_btn.find_element(
                    By.CLASS_NAME, 'btn.btn-success-wait.availabilitybutton ')
                if not avail_text.text == '':
                    break

                activity_btn = driver.find_element(By.CLASS_NAME, 'btn-group.btn-block')
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

            date_window_text = webwait(driver, 'ID', "ctl00_MainContent_startDate", timeout).text

            webwait(driver, 'ID', "ctl00_MainContent_dateForward1", timeout).click()

            date_window_text2 = date_window_text

            while date_window_text2 == date_window_text or date_window_text2 == '':
                try:
                    date_window_text2 = webwait(driver, 'ID', "ctl00_MainContent_startDate", timeout).text
                except:
                    continue

            table_data2, index, columns2 = read_master_table(driver, timeout)

            columns = [*columns1, *columns2]
            table_data = np.hstack((np.array(table_data1), np.array(table_data2)))
            del columns1, columns2, table_data1, table_data2

            df = pd.DataFrame(table_data, index=index, columns=columns)

            dates_dict = {}
            for date in columns:
                times = [index[x] for x in range(len(df[date])) if df[date].iloc[x] == 1]
                if not times:
                    continue
                prices = ['NaN'] * len(times)
                spaces_avail = ['NaN'] * len(times)
                dates_dict[date] = {'Times': np.array(times.copy()),
                                    'Prices': np.array(prices.copy()),
                                    'Spaces': np.array(spaces_avail.copy())}

            EA_dict[centre_name_original]['Activity'][options_name] = dates_dict.copy()
        except:
            pass

        if not i + 1 == len(valid_act_options_names):
            driver.get(booking_link)
            webwait(driver, 'ID', "bookingFrame", timeout)
            driver.switch_to.frame('bookingFrame')

            panels = webwait_all(driver, 'CLASS_NAME', "panel.panel-default", timeout)
            panel_names = [x.text.lower() for x in panels]
            adv_search_panel = panels[panel_names.index('advanced search')]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", adv_search_panel)
            adv_search_panel_expanded = adv_search_panel.find_element(
                By.CLASS_NAME, 'panel-heading').get_attribute('aria-expanded')
            if adv_search_panel_expanded == 'false' or adv_search_panel_expanded is None:
                adv_search_panel.click()

            act_scroll, act_options = search_paramters(driver, timeout, adv_search_panel, centre_name, centre_options)

    if EA_dict[centre_name_original]['Activity'] == {}:
        return None
    driver.close()
    return EA_dict


# Function for Everyone Active gyms/centres
def EA_gym(Loc, Act, max_centres=20, cpu_cores=4, timeout=10):
    """
    :param Loc: Location which to search from. Postcodes work best.
    :param Act: Activity e.g: 'Badminton', 'Basketball'
    :param max_centres: Take closest 'n' centres from Loc
    :param cpu_cores: Number of parallel tabs to be open. Each tab is a different centre
    :param timeout: Maximum wait time for website to load. If slow internet, increase this.
    :return: dictionary of centres and corresponding info in the same structure as seen in BETTER_gym:
    """

    geolocator = Nominatim(user_agent="aaaa")
    home = geolocator.geocode(Loc)
    home_coords = (home.latitude, home.longitude)
    driver = webdriver.Chrome()

    # EA_login_link = "https://account.everyoneactive.com/login/?redirect=/"
    # driver.get(EA_login_link)
    # EA_login(driver, timeout)

    centres_page = "https://www.everyoneactive.com/centre/"
    driver.get(centres_page)

    all_centres = webwait_all(driver, 'CLASS_NAME', "centre-finder__results-item-name", timeout)
    all_centre_names = [x.find_element(By.TAG_NAME, "a").text for x in all_centres]
    all_centre_links = [x.find_element(By.TAG_NAME, "a").get_attribute("href") for x in all_centres]
    all_centre_adresses = [x.find_element(By.TAG_NAME, "a").text for x in all_centres]
    all_centre_coords = [f'[{x.get_attribute("href").split("/")[-1].replace(",", ", ")}]' for x in
                         driver.find_elements(By.CLASS_NAME, 'centre-finder__results-details-link.link--external')
                         ]

    valid_indexes = np.array([all_centre_coords.index(x) for x in all_centre_coords if x != '[, ]'])
    all_centre_names = np.array(all_centre_names)[valid_indexes]
    all_centre_adresses = np.array(all_centre_adresses)[valid_indexes]
    all_centre_coords = np.array(all_centre_coords)[valid_indexes]
    all_centre_links = np.array(all_centre_links)[valid_indexes]

    all_centre_coords = np.array([json.loads(x) for x in all_centre_coords])
    all_centre_distances = np.array(
        [np.round(distance.geodesic(home_coords, x).km, 3) for x in all_centre_coords])

    ordered_indexes = np.argsort(all_centre_distances)[:max_centres]
    all_centre_names = list(all_centre_names[ordered_indexes])
    all_centre_adresses = list(all_centre_adresses[ordered_indexes])
    all_centre_distances = list(all_centre_distances[ordered_indexes])
    # all_centre_links = list(all_centre_links[ordered_indexes])

    EA_dict = {}

    driver.close()

    func = partial(EA_gym_loop, Act=Act, timeout=timeout)
    results = p_map(func, all_centre_names, all_centre_adresses, all_centre_distances, num_cpus=cpu_cores)

    for result in results:
        if result is None:
            continue
        EA_dict.update(result)

    if not EA_dict:
        return None

    return EA_dict
