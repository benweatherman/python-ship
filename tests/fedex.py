#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

try:
    from .config import FedexTestConfig
except ImportError:
    logging.error("Could not find FedexTestConfig in tests.config module.")
    exit(1)

from . import _show_file
import unittest
from shipping import Package, Address
import sys
sys.path.append('../')

import fedex

shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')

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
    
    f = fedex.Fedex(FedexTestConfig)
    
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

    f = fedex.Fedex(FedexTestConfig)

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
    f = fedex.Fedex(FedexTestConfig)
    
    packages = [
        fedex.Package(100, 12, 12, 12, 100.0, dry_ice_weight_in_ozs=54.27),
    ]
    
    for service in fedex.SERVICES:
        for package_type in fedex.PACKAGES:
            try:
                print service, package_type,
                response = f.label(packages, package_type, service, shipper, recipient, True)
                status = response['status']
                print 'Status: %s' % status,
                for shipment_info in response['shipments']:
                    print 'tracking: %s, cost: %s' % (shipment_info['tracking_number'], shipment_info['cost'])
            except fedex.FedexError as e:
                print e
    
    for package_type in fedex.PACKAGES:
        try:
            response = f.rate(packages, package_type, shipper, recipient)
            print response
        except fedex.FedexError as e:
            print e

if __name__ == '__main__':
    TestFedex()
    TestFedexGroundCertification()
    TestFedexExpressCertification()
    TestFedexProd()
