import re


def extract_singlenumber(string_var):
    """ Fast way to extract single number  from string """
    try:
        return re.sub('\D', '', string_var)
    except TypeError:
        return None


def extract_list_of_numbers(string_var):
    """ Fast way to extract list of numbers from string"""
    try:
        return re.findall(r'\d+', string_var)
    except TypeError:
        return None
