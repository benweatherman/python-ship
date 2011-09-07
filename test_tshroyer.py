from shipping import Address

white_house = Address('Mr. President', '1600 Pennsylvania Avenue NW', 'Washington', 'DC', '20500', 'US', company_name='White House')
powells = Address('Manager', '1005 W Burnside', 'Portland', 'OR', '97209', 'US', is_residence = False, company_name='Powell\'s City of Books')

from wholesale import config
ups_config = config.getConfig('ups')

from ups import UPS
ups = UPS(ups_config, debug=True)
print(white_house)
print(ups.validate(white_house))

print(powells)
print(ups.validate(powells))

