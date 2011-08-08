try:
    from test_config import UPSConfig, EndiciaConfig
    from test_config import FedexConfigDebug as FedexConfig
except:
    print 'HELLO THERE! test_config not found. If you want to run this test, you need to setup test_config.py with your account information.'
    raise

import os, tempfile
from shipping import Package, Address
import sys
sys.path.append('../')

import ups
import endicia
import fedex

shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')
bad_recipient = Address('Apple', "1 Park Place.", 'San Diego', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com', address2='#502')
recipient_intl = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'CA', phone='5122901212', email='ben@ordoro.com')
recipient_intl2 = Address('Bazaarvoice', 'One Lyric Square', 'London', '', 'W6 0NB', 'GB', phone='+44 (0)208 080', email='ben@ordoro.com')

def _show_file(extension, data):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
        temp_file.write(data)
        os.system('open %s' % temp_file.name)

class P(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def TestUPS():
    packages = [ Package(20.0 * 16, 12, 12, 12, value=1000, require_signature=3, reference='a12302b') ]

    intl_packages = [ Package(2.0 * 16, 12, 12, 12, value=100, reference='a12302b') ]
    products = [
        P(total=10, item_price=2, quantity=5, description='It\'s just a bunch of widgets'),
        P(total=90, item_price=1, quantity=90, description='It\'s another bunch of widgets')
    ]
    
    u = ups.UPS(UPSConfig, debug=True)

    for r in ( recipient_intl2, ):
        try:
            validate = True
            r.is_residence = True
            response = u.label(intl_packages, shipper, r, ups.SERVICES[9][0], ups.PACKAGES[5][0], validate, [ 'test@mytrashmail.com '], create_commercial_invoice=True, products=products)
            status = response['status']
            print 'Status: %s' % status,
            for info in response['shipments']:
                print 'tracking: %s, cost: %s' % (info['tracking_number'], info['cost'])
                # _show_file(extension='.gif', data=info['label'])
            # _show_file(extension='.pdf', data=response['international_document']['pdf'])
        except ups.UPSError as e:
            print e
    
    for r in ( recipient, shipper, bad_recipient, recipient_intl ):
        try:
            print u.validate(r)
        except ups.UPSError as e:
            print e
        
        try:
            validate = False
            r.is_residence = True
            response = u.label(packages, shipper, r, ups.SERVICES[2][0], ups.PACKAGES[7][0], validate, [ 'test@mytrashmail.com '])
            status = response['status']
            print 'Status: %s' % status,
            for info in response['shipments']:
                print 'tracking: %s, cost: %s' % (info['tracking_number'], info['cost'])
                # _show_file(extension='.gif', data=info['label'])
        except ups.UPSError as e:
            print e
    
        for package_type in ups.PACKAGES:
            package_code = package_type[0]
            try:
                response = u.rate(packages, package_code, shipper, r)
                print response
            except ups.UPSError as e:
                print e

def TestEndiciaLabel():
    package = endicia.Package(endicia.Package.shipment_types[0], 20, endicia.Package.shapes[1], 10, 10, 10)
    package_intl = endicia.Package(endicia.Package.international_shipment_types[0], 20, endicia.Package.shapes[3], 10, 10, 10)
    customs = [ endicia.Customs('hello', 1, 2, 100, 'Bermuda'), endicia.Customs('Thingy', 10, 16, 80, 'Bahamas') ]
    
    debug = True
    req0 = endicia.LabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package_intl, shipper, recipient_intl, contents_type='Merchandise', customs_info=customs, debug=debug)
    req1 = endicia.LabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, debug=debug)
    req2 = endicia.LabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, stealth=False, debug=debug)
    req3 = endicia.LabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, insurance='ENDICIA', insurance_amount=1.0, debug=debug)
    req4 = endicia.LabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, customs_form='Form2976A', customs_info=customs, contents_type='Merchandise', debug=debug)

    for request in [ req0, req1, req2, req3, req4 ]:
        response = request.send()
    
        print response
        if not isinstance(response, endicia.Error):
            _show_file(extension='.png', data=response.label)
    
    return response

def TestEndicia():
    debug = True
    
    # TestEndiciaLabel()

    # Rate
    packages = [ Package(20.0 * 16, 12, 12, 12, value=100) ]

    en = endicia.Endicia(EndiciaConfig)
    for shape in endicia.Package.shapes:
        try:
            response = en.rate(packages, shape, shipper, recipient)
            print response
        except endicia.EndiciaError as e:
            print e

    # # Account Status
    # request = endicia.AccountStatusRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, debug=debug)
    # response = request.send()
    # print response
    
    # # Recredit
    # request = endicia.RecreditRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 10.00, debug=debug)
    # response = request.send()
    # print response

    # Change Password
    # request = endicia.ChangePasswordRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 'ord7oro', debug=debug)
    # response = request.send()
    # print response

    # Refund
    # request = endicia.RefundRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, tracking_number, debug=debug)
    # response = request.send()
    # print response

def TestFedexGroundCertification():
    test_cases = [
        (
            Address('TC #4', '20 FedEx Parkway', 'Kansas City', 'MO', 64112, 'US', address2='2nd Floor Suite 2001', phone=5152961616, is_residence=False),
            fedex.Package(20.0 * 16, 12, 12, 12),
            fedex.SERVICES[0],
            fedex.PACKAGES[-1],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #20', '456 Roswell Rd', 'Atlanta', 'GA', 30328, 'US', phone=5152961616),
            fedex.Package(20.0 * 16, 5, 5, 108),
            fedex.SERVICES[1],
            fedex.PACKAGES[-1],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #21', '987 Main St', 'Boston', 'MA', '02129', 'US', phone=5152961616),
            fedex.Package(20.0 * 16, 5, 5, 108, require_signature=True),
            fedex.SERVICES[1],
            fedex.PACKAGES[-1],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #23', '321 Jay St', 'New York', 'NY', '11201', 'US', phone=5152961616),
            fedex.Package(20.0 * 16, 5, 5, 108, require_signature=True),
            fedex.SERVICES[1],
            fedex.PACKAGES[-1],
            False, # Email alert
            True,  # Evening
        ),
        (
            Address('TC #24', '456 Roswell Rd', 'Atlanta', 'GA', 30328, 'US', phone=5152961616),
            fedex.Package(20.0 * 16, 5, 5, 108, require_signature=True),
            fedex.SERVICES[1],
            fedex.PACKAGES[-1],
            False, # Email alert
            True,  # Evening
        ),
    ]
    
    f = fedex.Fedex(FedexConfig)
    
    for case in test_cases:
        try:
            print case
            recipient, package, service, package_type, email, evening = case
            packages = [ package ]
            response = f.label(packages, package_type, service, shipper, recipient, email, evening=evening)
            
            for info in response['info']:
                _show_file(extension='.png', data=info['label'])
        except fedex.FedexError as e:
            print e

def TestFedexExpressCertification():
    test_cases = [
        (
            Address('TC #1', '123 Bishop Rd', 'Honolulu', 'HI', 96819, 'US', phone=5152961616),
            fedex.Package(1.0 * 16, 12, 12, 12),
            fedex.SERVICES[5],
            fedex.PACKAGES[0],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #4', '789 Davies', 'Englewood', 'CO', 80112, 'US', phone=5152961616),
            fedex.Package(1.0 * 16, 12, 12, 12),
            fedex.SERVICES[4],
            fedex.PACKAGES[0],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #7', '6050 Rockwell Ave', 'Anchorage', 'AK', 99501, 'US', phone=5152961616),
            fedex.Package(5.0 * 16, 12, 12, 12),
            fedex.SERVICES[3],
            fedex.PACKAGES[1],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #8', '44 Binney St', 'Boston', 'MA', 02115, 'US', phone=5152961616),
            fedex.Package(1.0 * 16, 12, 12, 12),
            fedex.SERVICES[6],
            fedex.PACKAGES[0],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #9', '16 Court St', 'New York', 'NY', 10211, 'US', phone=5152961616),
            fedex.Package(8.0 * 16, 7, 10, 15),
            fedex.SERVICES[6],
            fedex.PACKAGES[3],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #10', 'SW 129th St', 'Miami', 'FL', 33156, 'US', phone=5152961616),
            fedex.Package(1.0 * 16, 12, 12, 12),
            fedex.SERVICES[2],
            fedex.PACKAGES[0],
            False, # Email alert
            False, # Evening
        ),
        (
            Address('TC #11', '36 Charles Lane', 'Baltimore', 'MD', 21201, 'US', phone=5152961616),
            fedex.Package(150 * 16, 10, 10, 15),
            fedex.SERVICES[2],
            fedex.PACKAGES[3],
            False, # Email alert
            False, # Evening
        ),
    ]

    f = fedex.Fedex(FedexConfig)

    for case in test_cases:
        try:
            print case
            recipient, package, service, package_type, email, evening = case
            packages = [ package ]
            response = f.label(packages, package_type, service, shipper, recipient, email, evening=evening)

            for info in response['info']:
                _show_file(extension='.png', data=info['label'])
        except fedex.FedexError as e:
            print e

def TestFedexProd():
    test_cases = [
        (
            Address('TC #4', '20 FedEx Parkway', 'Kansas City', 'MO', 64112, 'US', address2='2nd Floor Suite 2001', phone=5152961616, is_residence=False),
            fedex.Package(20.0 * 16, 12, 12, 12),
            fedex.SERVICES[0],
            fedex.PACKAGES[-1],
            False, # Email alert
            False, # Evening
        ),
    ]
    
    from test_config import FedexConfigProd
    
    f = fedex.Fedex(FedexConfigProd, debug=False)
    
    for case in test_cases:
        try:
            print case
            recipient, package, service, package_type, email, evening = case
            packages = [ package ]
            response = f.label(packages, package_type, service, shipper, recipient, email, evening=evening)
            
            for info in response['info']:
                _show_file(extension='.png', data=info['label'])
        except fedex.FedexError as e:
            print e

def TestFedex():
    f = fedex.Fedex(FedexConfig)
    
    packages = [
        fedex.Package(100, 12, 12, 12, 100.0),
    ]
    
    for service in fedex.SERVICES:
        for package_type in fedex.PACKAGES:
            try:
                print service, package_type,
                response = f.label(packages, package_type, service, shipper, recipient, True)
                status = response['status']
                print 'Status: %s' % status,
                for info in response['info']:
                    print 'tracking: %s, cost: %s' % (info['tracking_number'], info['cost'])
                #     _show_file(extension='.png', data=info['label'])
            except fedex.FedexError as e:
                print e
    
    for package_type in fedex.PACKAGES:
        try:
            response = f.rate(packages, package_type, shipper, recipient)
            print response
        except fedex.FedexError as e:
            print e

if __name__ == '__main__':
    TestUPS()
    #TestUSPS()
    # TestEndicia()
    #TestFedex()
    #TestFedexGroundCertification()
    #TestFedexExpressCertification()
    #TestFedexProd()