import xml.etree.ElementTree as etree
import re

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

class Package(object):
    def __init__(self, weight_in_ozs, length, width, height, value=0, require_signature=False):
        self.weight = weight_in_ozs / 16
        self.length = length
        self.width = width
        self.height = height
        self.value = value
        self.require_signature = require_signature

class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2='', phone='', email='', is_residence=True, company_name=''):
        self.company_name = company_name or ''
        self.name = name or ''
        self.address1 = address or ''
        self.address2 = address2 or ''
        self.city = city or ''
        self.state = state or ''
        self.zip = str(zip).split('-')[0] if zip else ''
        self.country = country or ''
        self.phone = re.sub('[^0-9]*', '', str(phone)) if phone else ''
        self.email = email or ''
        self.is_residence = is_residence or False
    
    def __eq__(self, other):
        return vars(self) == vars(other)
    
    def __repr__(self):
        street = self.address1
        if self.address2:
            street += '\n' + self.address2
        return '%s\n%s\n%s, %s %s %s' % (self.name, street, self.city, self.state, self.zip, self.country)