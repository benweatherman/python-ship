#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

try:
    from .config import EndiciaTestConfig
except:
    logging.error("Could not find EndiciaTestConfig in tests.config module.")
    raise

import os, tempfile
from shipping import Package, Address
import sys
sys.path.append('../')

import endicia

shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')
recipient_intl = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'CA', phone='5122901212', email='ben@ordoro.com')

def _show_file(extension, data):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
        temp_file.write(data)
        os.system('open %s' % temp_file.name)

class P(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

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

    en = endicia.Endicia(EndiciaTestConfig)
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

if __name__ == '__main__':
    TestEndicia()
