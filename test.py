try:
    from test_config import UPSUsername, UPSPassword, UPSAccessLicenseNumber, UPSShipperNumber
    from test_config import USPSUsername
    from test_config import EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase
except:
    print 'HELLO THERE! test_config not found. If you want to run this test, you need to setup test_config.py with your account information.'
    raise

import os, tempfile
from shipping import Address
import UPS
import USPS
import endicia

def TestUPS():
    shipper   = UPS.ShipperAddress('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', UPSShipperNumber)
    recipient = UPS.Address('Adobe', '345 Park Ave.', 'San Jose', 'CA', 95110, 'US')
    request = UPS.ShipConfirmRequest(UPSUsername, UPSPassword, UPSAccessLicenseNumber, shipper, recipient)
    response = request.Send()
    if isinstance(response, UPS.ShipConfirmResponse):
        print 'ShipConfirmResponse: %s' % response

        request = UPS.ShipAcceptRequest(UPSUsername, UPSPassword, UPSAccessLicenseNumber, response.digest)
        response = request.Send()
        print 'ShipAcceptResponse %s' % response
        with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as temp_file:
            temp_file.write(response.label)
            os.system('open %s' % temp_file.name)
    else:
        print response

def TestUSPSRate():
    shipper   = USPS.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 10022, 'US')
    recipient = USPS.Address('Joe Customer', '6060 Primacy Pkwy', 'Memphis', 'TN', 20008, 'US')
    
    # Package: (shipper, recipient, weight_lbs, weight_ozs, length, width, height)
    package1 = USPS.Package(shipper, recipient, 10, 5, 20, 16, 20)
    package2 = USPS.Package(shipper, recipient, 10, 5, 20, 16, 20)
    packages  = [ package1, package2 ]
    
    request = USPS.RateRequest(USPSUsername, packages)
    print "RateRequest: %s" % request
    response = request.Send()
    print "RateResponse: %s" % response
    
def TestUSPSDeliveryConfirmation():
    shipper   = USPS.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    recipient = USPS.Address('Joe Customer', '6060 Primacy Pkwy', 'Memphis', 'TN', '', 'US', address2='STE 201')
    
    weight_in_ounces = 2
    request = USPS.DeliveryConfirmationRequest(USPSUsername, shipper, recipient, weight_in_ounces)
    print request
    response = request.Send()
    print response
    
def TestUSPSExpressMail():
    shipper   = USPS.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    recipient = USPS.Address('Joe Customer', '6060 Primacy Pkwy', 'Memphis', 'TN', '', 'US', address2='STE 201')
    
    weight_in_ounces = 2
    request = USPS.ExpressMailRequest(USPSUsername, shipper, recipient, weight_in_ounces)
    print request
    response = request.Send()
    print response

def TestUSPS():
    TestUSPSRate()
    TestUSPSDeliveryConfirmation()
    TestUSPSExpressMail()

def TestEndiciaLabel():
    package = endicia.Package(endicia.Package.shipment_types[0], 20, endicia.Package.shapes[1], 10, 10, 10)
    package_intl = endicia.Package(endicia.Package.international_shipment_types[0], 20, endicia.Package.shapes[3], 10, 10, 10)
    shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5123943636')
    recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US')
    recipient_intl = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'Canada')
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
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_file.write(response.label)
            os.system('open %s' % temp_file.name)
    
    return response

def TestEndiciaRate():
    shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US')
    recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US')
    for shape in endicia.Package.shapes:
        package = endicia.Package(15, shape, 12, 12, 12)
        request = endicia.RateRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient, debug)
        response = request.send()
    
def TestAccountStatus():
    request = endicia.AccountStatusRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase)
    response = request.send()
    
    print response

def TestEndiciaRecredit():
    request = endicia.RecreditRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 10.00)
    response = request.send()
    
    print response
    
def TestEndiciaChangePassword():
    request = endicia.ChangePasswordRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 'ord7oro')
    response = request.send()
    
    print response

def TestRefundRequest(tracking_number):
    request = endicia.RefundRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, tracking_number)
    response = request.send()
    
    print response

def TestEndicia():
    TestEndiciaLabel()
    #response = TestEndiciaLabel()
    #TestRefundRequest(response.tracking)
    #TestEndiciaRate()
    #TestAccountStatus()
    #TestEndiciaRecredit()
    #TestEndiciaChangePassword()

if __name__ == '__main__':
    #TestUPS()
    #TestUSPS()
    TestEndicia()