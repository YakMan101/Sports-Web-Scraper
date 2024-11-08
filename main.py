"""Script to run search for all bookings (BETTER and Everyone Active leisure centres) available for specific sports hall activity"""

from os import environ as ENV
from multiprocessing import cpu_count

from dotenv import load_dotenv

from BETTER import scrape_better_website
from EA import scrape_ea_website


def write_save_avail(data, home, act):
    """Save all booking information to text file"""
    if data is None:
        print('dict is empty')
        return

    with open(f"Available {act} slots.txt", "w+") as f:
        f.write(f"Home Address: {home}\n")
        f.write(f"Activity: {act}\n")
        for centre_name, centre_info in data:
            f.write(
                "\n=============================================================\n")
            f.write("\n\n" + centre_name + ":\n")
            f.write("---------------------------\n")
            f.write(f"Company: {centre_info['Company']}\n")
            f.write(f"Address: {centre_info['Address']}\n")
            if centre_info['Distance'] is None:
                f.write(f"Distance: Not Found")
            else:
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
                        f.write("£" + price + " " * int(spaces) + "| ")

                    f.write("\n       " + "Spaces: ")
                    for courts in centre_info['Activity'][activity][date]['Spaces']:
                        str_len_space = len(courts)
                        spaces = str_len_time - str_len_space
                        f.write(courts + " " * int(spaces) + "| ")


if __name__ == '__main__':

    load_dotenv()

    postcode = ENV['POSTCODE']
    activity = ENV['ACTIVITY']

    """
    If you have slower internet or computer please either reduce 'cpu_cores' or increase 'timeout'
    
    --> max_centres - Search upto this many closest centres.
    --> cpu_cores - Number of parallel browsers that can be open at the same time
    --> timeout - maximum time script waits for html elements to load.
    """
    better_dict, ea_dict = {}, {}
    better_dict = scrape_better_website(postcode, activity, max_centres=5,
                                        cpu_cores=cpu_count(), timeout=10)
    ea_dict = scrape_ea_website(postcode, activity, max_centres=5,
                                cpu_cores=cpu_count(), timeout=10)

    all_dict = {}
    for i in [better_dict, ea_dict]:
        all_dict = all_dict | i

    dict_list = [x for x in all_dict.items()]
    dict_list_sorted = sorted(dict_list,
                              key=lambda x: x[1]['Distance']
                              if x[1]['Distance']
                              is not None else 99999)

    write_save_avail(dict_list_sorted, postcode, activity)
