from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By


def webwait_all(driver, type_, name, timeout):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.__getattribute__(By, type_), name)))


def webwait(driver, type_, name, timeout):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.__getattribute__(By, type_), name)))


def latlon2metres(lat_lon1, lat_lon2):
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
