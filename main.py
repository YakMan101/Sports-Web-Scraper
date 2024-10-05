from os import environ as ENV

from dotenv import load_dotenv
import numpy as np

from BETTER import BETTER_gym
from EA import EA_gym


def write_save_avail(data, home, act):
    if data is None:
        print('dict is empty')
        return

    with open(f"Available {act} slots.txt", "w+") as f:
        f.write(f"Home Address: {home}\n")
        f.write(f"Activity: {act}\n")
        for centre_name, centre_info in data:
            f.write("\n=============================================================\n")
            f.write("\n\n" + centre_name + ":\n")
            f.write("---------------------------\n")
            f.write(f"Company: {centre_info['Company']}\n")
            f.write(f"Address: {centre_info['Address']}\n")
            f.write(f"Distance: {centre_info['Distance']}km\n")
            for activity in list(centre_info['Activity'].keys()):
                f.write("\n\n-->" + activity + ":")
                for date in list(centre_info['Activity'][activity].keys()):
                    f.write("\n   " + date + ":")

                    f.write("\n       " + "Times:  ")
                    for time in centre_info['Activity'][activity][date]['Times']:
                        str_len_time = len(time) + 1
                        f.write(time + " | ")

                    f.write("\n       " + "Prices: ")
                    for price in centre_info['Activity'][activity][date]['Prices']:
                        str_len_price = len(price)
                        spaces = str_len_time - str_len_price
                        f.write(price + " " * int(spaces) + "| ")

                    f.write("\n       " + "Spaces: ")
                    for courts in centre_info['Activity'][activity][date]['Spaces']:
                        str_len_space = len(courts)
                        spaces = str_len_time - str_len_space
                        f.write(courts + " " * int(spaces) + "| ")


if __name__ == '__main__':

    load_dotenv()

    Home = ENV['POSTCODE']
    Activity = ENV['ACTIVITY']

    """
    If you have slower internet or computer please either reduce 'cpu_cores' or increase 'timeout'
    
    --> max_centres - Search upto this many closest centres.
    --> cpu_cores - Number of parallel browsers that can be open at the same time
    --> timeout - maximum time script waits for html elements to load.
    """

    better_dict = BETTER_gym(Home, Activity, max_centres=8, cpu_cores=8, timeout=5)
    ea_dict = EA_gym(Home, Activity, max_centres=8, cpu_cores=8, timeout=5)
    # Search through everyone Places centres
    # places_dict = Places_Leisure(Home, Activity, max_centres=10, cpu_cores=1, timeout=5)

    all_dict = {}
    for i in [better_dict, ea_dict]:
        if i is not None:
            all_dict = all_dict | i

    dict_list = [x for x in all_dict.items()]
    dict_list_distances = [x[1]['Distance'] for x in dict_list]
    dict_list_sorted = np.array(dict_list)[np.argsort(dict_list_distances)]

    write_save_avail(dict_list_sorted, Home, Activity)
