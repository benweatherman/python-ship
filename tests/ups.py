#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

try:
    from .config import UPSTestConfig
except:
    logging.error("Could not find UPSTestConfig in tests.config module.")
    exit(1)

import os, tempfile
from shipping import Package, Address, Product
import sys
sys.path.append('../')

import ups

shipper = Address('Adobe', "345 Park Avenue", 'San Jose', 'CA', 95110, 'US', phone='5122901212', email='ben@ordoro.com')
recipient = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com')
bad_recipient = Address('Apple', "1 Park Place.", 'San Diego', 'CA', 95014, 'US', phone='5122901212', email='ben@ordoro.com', address2='#502')
recipient_intl = Address('Apple', "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'CA', phone='5122901212', email='ben@ordoro.com')
recipient_intl2 = Address('Bazaarvoice', 'One Lyric Square', 'London', '', 'W6 0NB', 'GB', phone='+44 (0)208 080', email='ben@ordoro.com')
recipient_intl4 = Address('Some Recipient', '24 Tennant st', 'EDINBURGH', 'Midlothian', 'EH6 5ND', 'GB', phone='+44 (0)208 080', email='ben@ordoro.com')

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

    intl_packages = [ Package(2.0 * 16, 12, 12, 12, value=100, require_signature=2, reference='a12302b') ]
    products = [
        Product(total=10, value=2, quantity=5, description='It\'s just a bunch of widgets', country = 'CA'),
        Product(total=10, value=2, quantity=5, description='It\'s just a bunch of widgets', country = 'CA')
    ]
    
    u = ups.UPS(UPSConfig, debug=True)

    for r in ( recipient_intl2, recipient_intl4, ):
        try:
            validate = True
            r.is_residence = True
            response = u.label(intl_packages, shipper, r, ups.SERVICES[9][0], ups.PACKAGES[5][0], validate, [ 'test@mytrashmail.com '], create_commercial_invoice=True, customs_info=products)
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
        
        return
    
        for package_type in ups.PACKAGES:
            package_code = package_type[0]
            try:
                response = u.rate(packages, package_code, shipper, r)
                print response
            except ups.UPSError as e:
                print e

if __name__ == '__main__':
    TestUPS()
