#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

try:
    from .config import UPSTestConfig
except ImportError:
    logging.error("Could not find UPSTestConfig in tests.config module.")
    exit(1)

import unittest
from shipping import Package, Address, Product
import sys
sys.path.append('../')

import ups

# TODO: Split this up further. Should be one assert per function, and domestic
# and international tests should probably be two different TestCase classes.

class TestUPS(unittest.TestCase):
    def setUp(self):
        self.api = ups.UPS(UPSTestConfig, debug=True)
        self.shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
        self.test_email = 'test@mytrashmail.com'

    def TestIntl(self):
        recipients = [
            Address('Bazaarvoice', 'One Lyric Square', 'London', '', 'W6 0NB', 'GB', phone='+44 (0)208 080', email='ben@ordoro.com'),
            Address('Some Recipient', '24 Tennant st', 'EDINBURGH', 'Midlothian', 'EH6 5ND', 'GB', phone='+44 (0)208 080', email='ben@ordoro.com')
        ]
        packages = [
            Package(2.0 * 16, 12, 12, 12, value=100, require_signature=2, reference='a12302b')
        ]
        products = [
            Product(total=10, value=2, quantity=5, description='It\'s just a bunch of widgets', country = 'CA'),
            Product(total=10, value=2, quantity=5, description='It\'s just a bunch of widgets', country = 'CA')
        ]
        
        for recipient in recipients:
            validate = True
            recipient.is_residence = True
            response = self.api.label(intl_packages, self.shipper, recipient, ups.SERVICES[9][0], ups.PACKAGES[5][0], validate, [ self.test_email ], create_commercial_invoice=True, customs_info=products)
            self.assertIn("status", response)
            self.assertIn("shipments", response)

            for info in response['shipments']:
                self.assertIn("tracking_number", info)
                self.assertIn("cost", info)
 
    def TestDomestic(self):
        # Test 'validate' function.
        recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')
        self.assertTrue(self.api.validate(recipient)["valid"], msg = "UPS thinks Apple's HQ address isn't valid.")
        
        bad_recipient = Address('Apple', "1 Park Place.", 'San Diego', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com', address2='#502')
        self.assertFalse(self.api.validate(bad_recipient)["valid"], msg = "UPS thinks our invalid address is valid.")
    
        # Test 'label' function.
        validate = False
        recipient.is_residence = True
        package = Package(20.0 * 16, 12, 12, 12, value=1000, require_signature=3, reference='a12302b')
        response = self.api.label([package], self.shipper, recipient, ups.SERVICES[2][0], ups.PACKAGES[7][0], validate, [ self.test_email ])
        status = response['status']
        self.assertIn("shipments", response)

        for shipment in response['shipments']:
            self.assertIn("tracking_number", shipment)
            self.assertIn("cost", shipment)
   
        # Test 'rate' function. 
        for package_type in ups.PACKAGES:
            package_code = package_type[0]
            response = self.api.rate(packages, package_code, shipper, r)
