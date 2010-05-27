try:
    from test_config import UPSUsername, UPSPassword, UPSAccessLicenseNumber, UPSShipperNumber
    from test_config import USPSUsername
    from test_config import EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase
except:
    print 'HELLO THERE! test_config not found. If you want to run this test, you need to setup test_config.py with your account information.'
    raise

import os, tempfile
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
    shape = endicia.Package.MediumFlatRateBoxShape
    package = endicia.Package(15, shape, 10, 10, 10)
    shipper = endicia.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    recipient = endicia.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    request = endicia.EndiciaLabelRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient)
    response = request.Send()
    
    print response
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        temp_file.write(response.label)
        os.system('open %s' % temp_file.name)

def TestEndiciaRate():
    shape = endicia.Package.MediumFlatRateBoxShape
    package = endicia.Package(15, shape, 10, 10, 10)
    shipper = endicia.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    recipient = endicia.Address('John Smith', "475 L'Enfant Plaza, SW", 'Washington', 'DC', 20260, 'US')
    request = endicia.EndiciaRateRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, package, shipper, recipient)
    response = request.Send()
    
    print response
    
def TestAccountStatus():
    request = endicia.EndiciaAccountStatusRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase)
    response = request.Send()
    
    print response

def TestEndiciaRecredit():
    request = endicia.EndiciaRecreditRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 200)
    response = request.Send()
    
    print response
    
def TestEndiciaChangePassword():
    request = endicia.EndiciaChangePasswordRequest(EndiciaPartnerID, EndiciaAccountID, EndiciaPassphrase, 'NewPassword')
    response = request.Send()
    
    print response

def TestEndicia():
    TestEndiciaLabel()
    TestEndiciaRate()
    TestAccountStatus()
    TestEndiciaRecredit()
    TestEndiciaChangePassword()

if __name__ == '__main__':
    #TestUPS()
    #TestUSPS()
    TestEndicia()