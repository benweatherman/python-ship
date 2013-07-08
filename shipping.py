import re

def debug_print_tree(elem):   
   import xml.etree.ElementTree as etree
   from xml.dom.minidom import parseString
   node = parseString(etree.tostring(elem).replace('\n', ''))
   print(node.toprettyxml(indent="   "))
   
import logging
def setLoggingLevel(level = logging.ERROR):
   """ Convenience function to set all the logging in one place """
   logging.getLogger('%s.ups' % __name__).setLevel(level)
   logging.getLogger('%s.fedex' % __name__).setLevel(level)
   logging.getLogger('%s.endicia' % __name__).setLevel(level)
   logging.getLogger('suds.client').setLevel(level)
   logging.getLogger('suds.transport').setLevel(level)
   logging.getLogger('suds.xsd.schema').setLevel(level)
   logging.getLogger('suds.wsdl').setLevel(level)

class Package(object):
    def __init__(self, weight_in_ozs, length='', width='', height='', value=0, require_signature=False, reference=u''):
        self.weight = weight_in_ozs / 16
        self.length = length
        self.width = width
        self.height = height
        self.value = value
        self.require_signature = require_signature
        self.reference = reference
    
    @property
    def weight_in_ozs(self):
        return self.weight * 16

    @property
    def weight_in_lbs(self):
        return self.weight
        
class Product(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        

class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2='', phone='', email='', is_residence=True, company_name=''):
        self.company_name = company_name or ''
        self.name = name or ''
        self.address1 = address or ''
        self.address2 = address2 or ''
        self.city = city or ''
        self.state = state or ''
        self.zip = re.sub('[^\w]', '', unicode(zip).split('-')[0]) if zip else ''
        self.country = country or ''
        self.phone = re.sub('[^0-9]*', '', unicode(phone)) if phone else ''
        self.email = email or ''
        self.is_residence = is_residence or False
    
    def __eq__(self, other):
        return vars(self) == vars(other)
    
    def __repr__(self):
        street = self.address1
        if self.address2:
            street += '\n' + self.address2
        return '%s\n%s\n%s, %s %s %s' % (self.name, street, self.city, self.state, self.zip, self.country)

def get_country_code(country):
    lookup = {
        'us': 'US',
        'usa': 'US',
        'united states': 'US',
    }

    return lookup.get(country.lower(), country)