#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

try:
    from .config import EndiciaTestConfig
except ImportError:
    logging.error("Could not find EndiciaTestConfig in tests.config module.")
    exit(1)

from . import _show_file
import unittest
from shipping import Package, Address
import sys
sys.path.append('../')

import endicia

class TestEndicia(unittest.TestCase):
    def setUp(self):
        self.api = endicia.Endicia(EndiciaTestConfig, debug=True)
        self.shipper = Address(
            'Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US',
            phone='5122901212', email='ben@ordoro.com'
        )
        self.recipient = Address(
            'Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US',
            phone='5122901212', email='ben@ordoro.com'
        )
        self.intl_recipient = Address(
            'Apple Canada', "7495 Birchmount Road", 'Markham', 'ON', "L3R 5G2", 'CA',
            phone='9055135800', email='ben@ordoro.com'
        )
        self.package = endicia.Package(
            endicia.Package.shipment_types[0], 3,
            endicia.Package.shapes[1], 10, 10, 10
        )

    def testIntlLabel(self):
        package_intl = endicia.Package(
            endicia.Package.international_shipment_types[0], 20,
            endicia.Package.shapes[3], 10, 10, 10
        )
        customs = [
            endicia.Customs('Thing 1', 1, 2, 100, 'United States'),
            endicia.Customs('Thing 2', 10, 16, 80, 'Canada')
        ]
        label = self.api.label(package_intl, self.shipper, self.intl_recipient,
            contents_type='Merchandise', customs_info=customs,
            image_format="GIF" # Only GIF is valid for international labels.
        )
        self.assertFalse(isinstance(label, endicia.Error), msg=label.message)


    def testLabel(self):
        label = self.api.label(self.package, self.shipper, self.recipient)
        self.assertFalse(isinstance(label, endicia.Error), msg=getattr(label, 'message', None))

    def testUnstealthyLabel(self):
        label = self.api.label(self.package, self.shipper, self.recipient, stealth=False)
        self.assertFalse(isinstance(label, endicia.Error), msg=getattr(label, 'message', None))

    def testInsuredLabel(self):
        label = self.api.label(self.package, self.shipper, self.recipient, insurance='ENDICIA', insurance_amount=1.0)
        self.assertFalse(isinstance(label, endicia.Error), msg=getattr(label, 'message', None))

    def testRate(self):
        packages = [ self.package ]

        for shape in endicia.Package.shapes:
            rate = self.api.rate(packages, self.shipper, self.recipient)
            self.assertEqual(rate["status"], 0)
            self.assertIn("info", rate)

            for item in rate["info"]:
                self.assertIn("cost", item)

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

if __name__ == '__main__':
    TestEndicia()
