try:
    from test_config import UPSConfig
    from test_config import USPSUsername
    from test_config import EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase
    from test_config import FedexConfig
except:
    print 'HELLO THERE! test_config not found. If you want to run this test, you need to setup test_config.py with your account information.'
    raise

import os, tempfile
from shipping import Address
import ups
import endicia
import fedex

shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')
recipient_intl = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'Canada', phone='5122901212', email='ben@ordoro.com')

def _show_file(extension, data):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
        temp_file.write(data)
        #os.system('open %s' % temp_file.name)

def TestUPS():
    package = [ None ]
    
    u = ups.UPS(UPSConfig)
    
    try:
        u.label(package, shipper, recipient, ups.SERVICES[0])
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

def TestEndiciaRate():
    debug = True
    for shape in endicia.Package.shapes:
        package = endicia.Package(endicia.Package.shipment_types[0], 15, shape, 12, 12, 12)
        request = endicia.RateRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, debug)
        response = request.send()

def TestEndiciaRecredit():
    debug = True
    request = endicia.RecreditRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 10.00, debug=debug)
    response = request.send()
    
    print response
    
def TestEndiciaChangePassword():
    debug = True
    request = endicia.ChangePasswordRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 'ord7oro', debug=debug)
    response = request.send()
    
    print response

def TestRefundRequest(tracking_number):
    debug = True
    request = endicia.RefundRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, tracking_number, debug=debug)
    response = request.send()
    
    print response

def TestEndicia():
    debug = True
    
    TestEndiciaLabel()

    # Rate
    for shape in endicia.Package.shapes:
        package = endicia.Package(endicia.Package.shipment_types[0], 15, shape, 12, 12, 12)
        request = endicia.RateRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, debug)
        response = request.send()
        print response

    # Account Status
    request = endicia.AccountStatusRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, debug=debug)
    response = request.send()
    print response
    
    # Recredit
    request = endicia.RecreditRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 10.00, debug=debug)
    response = request.send()
    print response

    # Change Password
    # request = endicia.ChangePasswordRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 'ord7oro', debug=debug)
    # response = request.send()
    # print response

    # Refund
    # request = endicia.RefundRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, tracking_number, debug=debug)
    # response = request.send()
    # print response

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
                    _show_file(extension='.png', data=info['label'])
            except fedex.FedexError as e:
                print e

if __name__ == '__main__':
    #TestUPS()
    #TestUSPS()
    #TestEndicia()
    TestFedex()