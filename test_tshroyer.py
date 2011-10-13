from shipping import Address
from shipping import Package
from ups import PACKAGES
import logging
logging.basicConfig(level=logging.ERROR)
from shipping import setLoggingLevel
setLoggingLevel(logging.ERROR)
logging.getLogger('%s.ups' % __name__).setLevel(logging.DEBUG)


white_house = Address('Mr. President', '1600 Pennsylvania Avenue NW', 'Washington', 'DC', '20500', 'US', company_name='White House')
powells = Address('Manager', '1005 W Burnside', 'Portland', 'OR', '97209', 'US', is_residence = False, company_name='Powell\'s City of Books')
our_place = Address('Wholesale Imports Guy', '4957 Summer Ave', 'Memphis', 'TN', '38122', 'US', company_name='WholesaleImport.com')

from wholesale import config
ups_config = config.getConfig('ups')

from ups import UPS
ups = UPS(ups_config, debug=False)
print(white_house)
print(ups.validate(white_house))

print(powells)
print(ups.validate(powells))

ten_pound_box = Package(10.0 * 16, 12, 12, 12, value=100, require_signature=3, reference='a12302b')
our_packaging =  PACKAGES[0][0]

# Send some books to powells because they need some more
print(ups.rate([ten_pound_box], our_packaging, our_place, powells))
