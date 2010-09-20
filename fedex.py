import os
from datetime import datetime
import binascii
import suds
from suds.client import Client
from suds.sax.element import Element
import urlparse

import logging

from shipping import Address

SERVICES = [
    'FEDEX_GROUND',
    'GROUND_HOME_DELIVERY',
    'FEDEX_EXPRESS_SAVER',
    'FEDEX_2_DAY',
    'STANDARD_OVERNIGHT',
    'PRIORITY_OVERNIGHT',
    'FIRST_OVERNIGHT',
    'FEDEX_1_DAY_FREIGHT',
]

PACKAGES = [
    'FEDEX_BOX',
    'FEDEX_PAK',
    'FEDEX_TUBE',
    'YOUR_PACKAGING',
]

class FedexError(Exception):
    pass

class FedexWebError(FedexError):
    def __init__(self, fault, document):
        self.fault = fault
        self.document = document
        
        fault = self.document.childAtPath('/Envelope/Body/Fault/detail/fault')
        code = fault.childAtPath('/errorCode').getText()
        reason = fault.childAtPath('/reason').getText()
        messages = fault.childrenAtPath('/details/ValidationFailureDetail/message')
        words = [ x.getText() for x in messages ]
        error_lines = '\n'.join(words)
        
        error_text = 'FedEx error %s: %s Details:\n%s ' % (code, reason, error_lines)
        super(FedexError, self).__init__(error_text)

class FedexShipError(FedexError):
    def __init__(self, reply):
        self.reply = reply
        
        messages = [ 'FedEx error %s: %s' % (x.Code, x.LocalizedMessage if hasattr(x, 'LocalizedMessage') else x.Message) for x in reply.Notifications ]
        error_text = '\n'.join(messages)
        super(FedexError, self).__init__(error_text)

class Package(object):
    def __init__(self, weight_in_ozs, length, width, height, value=0, require_signature=False):
        self.weight = weight_in_ozs / 16
        self.length = length
        self.width = width
        self.height = height
        self.value = value
        self.require_signature = require_signature

class Fedex(object):
    def __init__(self, credentials, debug=True):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.wsdl_dir = os.path.join(this_dir, 'wsdl', 'fedex')
        self.credentials = credentials
        self.debug = debug

        logging.basicConfig(level=logging.INFO)
        #logging.getLogger('suds.client').setLevel(logging.DEBUG)
        #logging.getLogger('suds.transport').setLevel(logging.DEBUG)

    def _normalized_country_code(self, country):
        country_lookup = {
            'usa': 'US',
            'united states': 'US',
        }
        return country_lookup.get(country.lower(), country)

    def label(self, packages, packaging_type, service_type, shipper, recipient, email_alert, evening=False, payment=None):
        wsdl_file_path = os.path.join(self.wsdl_dir, 'ShipService_v9.wsdl')
        wsdl_url = urlparse.urljoin('file://', wsdl_file_path)

        client = Client(wsdl_url)
        
        if self.debug:
            # For UPS, we have to do some fancy stuff to use the test environment
            # e.g. client.set_options(location='https://onlinetools.ups.com/webservices/Ship')
            # FedEx is nice and uses the test server automagically when you supply test
            # account information. Yay!
            pass
        else:
            client.set_options(location='https://gateway.fedex.com:443/web-services')

        auth = client.factory.create('WebAuthenticationDetail')
        auth.UserCredential.Key = self.credentials['key']
        auth.UserCredential.Password = self.credentials['password']
        
        client_detail = client.factory.create('ClientDetail')
        client_detail.AccountNumber = self.credentials['account_number']
        client_detail.MeterNumber = self.credentials['meter_number']
        
        trans = client.factory.create('TransactionDetail')
        
        version = client.factory.create('VersionId')
        version.ServiceId = 'ship'
        version.Major = '9'
        version.Intermediate = '0'
        version.Minor = '0'
        
        shipment = client.factory.create('RequestedShipment')

        shipment.CustomerSelectedActualRateType = 'PAYOR_ACCOUNT_SHIPMENT'
        
        if not payment:
            payment = { 'type': 'SENDER', 'account': self.credentials['account_number'] }
        shipment.ShippingChargesPayment.PaymentType = payment['type']
        shipment.ShippingChargesPayment.Payor.AccountNumber = payment['account']

        shipment.RateRequestTypes = 'ACCOUNT'
        
        shipment.EdtRequestType = 'ALL'
        shipment.ShipTimestamp = datetime.now()
        
        shipment.DropoffType = 'REGULAR_PICKUP'
        shipment.ServiceType = service_type
        
        shipment.PackagingType = packaging_type
        shipment.PackageDetail = 'INDIVIDUAL_PACKAGES'
        
        shipment.Shipper.Contact.PersonName = shipper.name
        shipment.Shipper.Contact.PhoneNumber = shipper.phone
        shipment.Shipper.Contact.EMailAddress = shipper.email
        shipment.Shipper.Address.StreetLines = [ shipper.address1, shipper.address2 ]
        shipment.Shipper.Address.City = shipper.city
        shipment.Shipper.Address.StateOrProvinceCode = shipper.state
        shipment.Shipper.Address.PostalCode = shipper.zip
        shipment.Shipper.Address.CountryCode = self._normalized_country_code(shipper.country)
        shipment.Shipper.Address.Residential = shipper.is_residence
        
        shipment.Recipient.Contact.PersonName = recipient.name
        shipment.Recipient.Contact.PhoneNumber = recipient.phone
        shipment.Recipient.Contact.EMailAddress = recipient.email
        shipment.Recipient.Address.StreetLines = [ recipient.address1, recipient.address2 ]
        shipment.Recipient.Address.City = recipient.city
        shipment.Recipient.Address.StateOrProvinceCode = recipient.state
        shipment.Recipient.Address.PostalCode = recipient.zip
        shipment.Recipient.Address.CountryCode = self._normalized_country_code(recipient.country)
        shipment.Recipient.Address.Residential = recipient.is_residence
        
        if email_alert:
            shipment.SpecialServicesRequested.SpecialServiceTypes.append('EMAIL_NOTIFICATION')
            shipment.SpecialServicesRequested.EMailNotificationDetail.AggregationType = 'PER_PACKAGE'
            for type, email in [ ('SHIPPER', shipper.email), ('RECIPIENT', recipient.email) ]:
                info = client.factory.create('EMailNotificationRecipient')
                info.EMailNotificationRecipientType = type
                info.EMailAddress = email
                info.Format = 'HTML'
                info.NotifyOnShipment = True
                info.Localization.LanguageCode = 'EN'
            
                shipment.SpecialServicesRequested.EMailNotificationDetail.Recipients.append(info)
        
        if evening:
            shipment.SpecialServicesRequested.SpecialServiceTypes.append('HOME_DELIVERY_PREMIUM')
            shipment.SpecialServicesRequested.HomeDeliveryPremiumDetail.HomeDeliveryPremiumType = 'EVENING'
        
        shipment.LabelSpecification.LabelFormatType = 'COMMON2D'
        shipment.LabelSpecification.ImageType = 'PNG'
        shipment.LabelSpecification.LabelStockType = 'PAPER_4X6'
        shipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
        shipment.ErrorLabelBehavior = 'STANDARD'
        
        shipment.PackageCount = 0
        shipment.TotalWeight.Value = 0
        shipment.TotalWeight.Units = 'LB'
        for p in packages:
            package = client.factory.create('RequestedPackageLineItem')
            package.PhysicalPackaging = 'BOX'
            package.InsuredValue.Amount = p.value
            package.InsuredValue.Currency = 'USD'
            
            package.Weight.Units = 'LB'
            package.Weight.Value = p.weight
            
            package.Dimensions.Units = 'IN'
            package.Dimensions.Length = p.length
            package.Dimensions.Width = p.width
            package.Dimensions.Height = p.height
            
            if p.require_signature:
                package.SpecialServicesRequested.SpecialServiceTypes.append('SIGNATURE_OPTION')
                package.SpecialServicesRequested.SignatureOptionDetail.OptionType = 'ADULT'

            shipment.RequestedPackageLineItems.append(package)
            shipment.PackageCount += 1
            shipment.TotalWeight.Value += p.weight
        
        try:
            self.reply = client.service.processShipment(auth, client_detail, trans, version, shipment)

            if self.reply.HighestSeverity == 'ERROR':
                raise FedexShipError(self.reply)
            elif self.reply.HighestSeverity == 'WARNING':
                pass
                #print self.reply
                
            response = { 'status': self.reply.HighestSeverity, 'info': list() }
            for i in range(len(packages)):
                label = self.reply.CompletedShipmentDetail.CompletedPackageDetails[i].Label.Parts[0].Image
                info = {
                    'tracking_number': self.reply.CompletedShipmentDetail.CompletedPackageDetails[i].TrackingIds[0].TrackingNumber,
                    'cost': self.reply.CompletedShipmentDetail.CompletedPackageDetails[i].PackageRating.PackageRateDetails[0].NetCharge.Amount,
                    'label': binascii.a2b_base64(label),
                }
                response['info'].append(info)
            return response
            
        except suds.WebFault as e:
            raise FedexWebError(e.fault, e.document)