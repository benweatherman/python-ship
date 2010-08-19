import xml.etree.ElementTree as etree

def indent(elem, level=0):
    """Indents an etree element so printing that element is actually human-readable"""
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def debug_print_tree(elem):
    indent(elem)
    etree.dump(elem)

class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2='', phone=''):
        self.name = name
        self.address1 = address
        self.address2 = address2
        self.city = city
        self.state = state
        self.zip = str(zip)
        self.country = country
        self.phone = phone