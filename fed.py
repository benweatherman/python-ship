#!/usr/bin/env python
"""
This example shows how to create shipments. The variables populated below
represents the minimum required values. You will need to fill all of these, or
risk seeing a SchemaValidationError exception thrown.

Near the bottom of the module, you'll see some different ways to handle the
label data that is returned with the reply.
"""

import logging
import binascii
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest
import fedex.base_service

# Set this to the INFO level to see the response from Fedex printed in stdout.
#logging.basicConfig(level=logging.INFO)

Services = [
    'FEDEX_GROUND',
    'FEDEX_EXPRESS_SAVER',
    'GROUND_HOME_DELIVERY',
    'STANDARD_OVERNIGHT',
    'PRIORITY_OVERNIGHT',
]

Packages = [
    'FEDEX_BOX',
    'FEDEX_PAK',
    'FEDEX_TUBE',
    'YOUR_PACKAGING',
]

class FedexError(fedex.base_service.FedexBaseServiceException):
    pass

class Package(object):
    def __init__(self, weight_in_ozs, length, width, height):
        self.weight = weight_in_ozs / 16
        self.length = length
        self.width = width
        self.height = height

class Fedex(object):
    def __init__(self, config):
        self.config_object = FedexConfig(key=config['key'], password=config['password'], account_number=config['account_number'], meter_number=config['meter_number'], use_test_server=True)

    def label(self, packages, packaging_type, service_type, shipper, recipient):
        # This is the object that will be handling our tracking request.
        # We're using the FedexConfig object from example_config.py in this dir.
        shipment = FedexProcessShipmentRequest(self.config_object)

        # This is very generalized, top-level information.
        # REGULAR_PICKUP, REQUEST_COURIER, DROP_BOX, BUSINESS_SERVICE_CENTER or STATION
        shipment.RequestedShipment.DropoffType = 'REGULAR_PICKUP'

        # See page 355 in WS_ShipService.pdf for a full list. Here are the common ones:
        # STANDARD_OVERNIGHT, PRIORITY_OVERNIGHT, FEDEX_GROUND, FEDEX_EXPRESS_SAVER
        shipment.RequestedShipment.ServiceType = service_type

        # What kind of package this will be shipped in.
        # FEDEX_BOX, FEDEX_PAK, FEDEX_TUBE, YOUR_PACKAGING
        shipment.RequestedShipment.PackagingType = packaging_type

        # No idea what this is.
        # INDIVIDUAL_PACKAGES, PACKAGE_GROUPS, PACKAGE_SUMMARY 
        shipment.RequestedShipment.PackageDetail = 'INDIVIDUAL_PACKAGES'

        # Shipper contact info.
        shipment.RequestedShipment.Shipper.Contact.PersonName = shipper.name
        shipment.RequestedShipment.Shipper.Contact.PhoneNumber = shipper.phone

        # Shipper address.
        shipment.RequestedShipment.Shipper.Address.StreetLines = [ shipper.address1, shipper.address2 ]
        shipment.RequestedShipment.Shipper.Address.City = shipper.city
        shipment.RequestedShipment.Shipper.Address.StateOrProvinceCode = shipper.state
        shipment.RequestedShipment.Shipper.Address.PostalCode = shipper.zip
        shipment.RequestedShipment.Shipper.Address.CountryCode = shipper.country
        shipment.RequestedShipment.Shipper.Address.Residential = shipper.is_residence

        # Recipient contact info.
        shipment.RequestedShipment.Recipient.Contact.PersonName = recipient.name
        shipment.RequestedShipment.Recipient.Contact.PhoneNumber = recipient.phone

        # Recipient address
        shipment.RequestedShipment.Recipient.Address.StreetLines = [ recipient.address1, recipient.address2 ]
        shipment.RequestedShipment.Recipient.Address.City = recipient.city
        shipment.RequestedShipment.Recipient.Address.StateOrProvinceCode = recipient.state
        shipment.RequestedShipment.Recipient.Address.PostalCode = recipient.zip
        shipment.RequestedShipment.Recipient.Address.CountryCode = recipient.country
        # This is needed to ensure an accurate rate quote with the response.
        shipment.RequestedShipment.Recipient.Address.Residential = recipient.is_residence

        # Who pays for the shipment?
        # RECIPIENT, SENDER or THIRD_PARTY
        shipment.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER' 

        # Specifies the label type to be returned.
        # LABEL_DATA_ONLY or COMMON2D
        shipment.RequestedShipment.LabelSpecification.LabelFormatType = 'COMMON2D'

        # Specifies which format the label file will be sent to you in.
        # DPL, EPL2, PDF, PNG, ZPLII
        shipment.RequestedShipment.LabelSpecification.ImageType = 'PNG'

        # To use doctab stocks, you must change ImageType above to one of the
        # label printer formats (ZPLII, EPL2, DPL).
        # See documentation for paper types, there quite a few.
        shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_4X6'

        # This indicates if the top or bottom of the label comes out of the 
        # printer first.
        # BOTTOM_EDGE_OF_TEXT_FIRST or TOP_EDGE_OF_TEXT_FIRST
        shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'

        for p in packages:
            weight = shipment.create_wsdl_object_of_type('Weight')
            weight.Value = p.weight
            weight.Units = 'LB'
            
            dimensions = shipment.create_wsdl_object_of_type('Dimensions')
            dimensions.Length = p.length
            dimensions.Width = p.width
            dimensions.Height = p.height
            dimensions.Units = 'IN'

            package = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
            package.Weight = weight

            shipment.add_package(package)
            
            # Un-comment this to see the other variables you may set on a package.
            #print package

        # If you'd like to see some documentation on the ship service WSDL, un-comment
        # this line. (Spammy).
        #print shipment.client

        # Un-comment this to see your complete, ready-to-send request as it stands
        # before it is actually sent. This is useful for seeing what values you can
        # change.
        #print shipment.RequestedShipment

        # If you want to make sure that all of your entered details are valid, you
        # can call this and parse it just like you would via send_request(). If
        # shipment.response.HighestSeverity == "SUCCESS", your shipment is valid.
        #shipment.send_validation_request()

        # Fires off the request, sets the 'response' attribute on the object.
        try:
            shipment.send_request()

            # This will show the reply to your shipment being sent. You can access the
            # attributes through the response attribute on the request object. This is
            # good to un-comment to see the variables returned by the Fedex reply.
            #print shipment.response
        
            response = { 'status': shipment.response.HighestSeverity, 'info': list() }
            for i in range(len(packages)):
                label = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[i].Label.Parts[0].Image
                info = {
                    'tracking_number': shipment.response.CompletedShipmentDetail.CompletedPackageDetails[i].TrackingIds[0].TrackingNumber,
                    'cost': shipment.response.CompletedShipmentDetail.CompletedPackageDetails[i].PackageRating.PackageRateDetails[0].NetCharge.Amount,
                    'label': binascii.a2b_base64(label),
                }
                response['info'].append(info)
            
            return response
        except fedex.base_service.FedexBaseServiceException as e:
            raise FedexError(e.error_code, e.value)