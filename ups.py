import os
import suds
from suds.client import Client
from suds.sax.element import Element
import urlparse
import base64
from datetime import date
import logging

from shipping import Address

SERVICES = [
    ('03', 'UPS Ground'),
    ('11', 'UPS Standard'),
    ('01', 'UPS Next Day'),
    ('14', 'UPS Next Day AM'),
    ('13', 'UPS Next Day Air Saver'),
    ('02', 'UPS 2nd Day'),
    ('59', 'UPS 2nd Day AM'),
    ('12', 'UPS 3-day Select'),
    ('65', 'UPS Saver'),
    ('07', 'UPS Worldwide Express'),
    ('08', 'UPS Worldwide Expedited'),
    ('54', 'UPS Worldwide Express Plus'),
]

PACKAGES = [
    ('02', 'Custom Packaging'),
    ('01', 'UPS Letter'),
    ('03', 'Tube'),
    ('04', 'PAK'),
    ('21', 'UPS Express Box'),
    ('2a', 'Small Express Box'),
    ('2b', 'Medium Express Box'),
    ('2c', 'Large Express Box'),
]

class UPSError(Exception):
    def __init__(self, fault, document):
        self.fault = fault
        self.document = document

        code = self.document.childAtPath('/detail/Errors/ErrorDetail/PrimaryErrorCode/Code').getText()
        text = self.document.childAtPath('/detail/Errors/ErrorDetail/PrimaryErrorCode/Description').getText()
        error_text = 'UPS Error %s: %s' % (code, text)

        super(UPSError, self).__init__(error_text)

from suds.plugin import MessagePlugin
class FixRequestNamespacePlug(MessagePlugin):
    def sending(self, context):
        context.envelope = context.envelope.replace('ns1:Request>', 'ns0:Request>').replace('ns2:Request>', 'ns1:Request>')

class UPS(object):
    def __init__(self, credentials, debug=True):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.wsdl_dir = os.path.join(this_dir, 'wsdl', 'ups')
        self.credentials = credentials
        self.debug = debug
        
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger('suds').setLevel(logging.ERROR)
    
    def _add_security_header(self, client):
        security_ns = ('security', 'http://www.ups.com/XMLSchema/XOLTWS/UPSS/v1.0')
        security = Element('UPSSecurity', ns=security_ns)

        username_token = Element('UsernameToken', ns=security_ns)
        username = Element('Username', ns=security_ns).setText(self.credentials['username'])
        password = Element('Password', ns=security_ns).setText(self.credentials['password'])
        username_token.append(username)
        username_token.append(password)

        service_token = Element('ServiceAccessToken', ns=security_ns)
        license = Element('AccessLicenseNumber', ns=security_ns).setText(self.credentials['access_license'])
        service_token.append(license)

        security.append(username_token)
        security.append(service_token)

        client.set_options(soapheaders=security)
    
    def _normalized_country_code(self, country):
        country_lookup = {
            'usa': 'US',
            'united states': 'US',
        }
        return country_lookup.get(country.lower(), country)
    
    def _get_client(self, wsdl):
        wsdl_file_path = os.path.join(self.wsdl_dir, wsdl)
        wsdl_url = urlparse.urljoin('file://', wsdl_file_path)

        plugin = FixRequestNamespacePlug()
        return Client(wsdl_url, plugins=[plugin])

    def _create_shipment(self, client, packages, shipper_address, recipient_address, box_shape, namespace='ns3', create_reference_number=True):
        shipment = client.factory.create('{}:ShipmentType'.format(namespace))

        for i, p in enumerate(packages):
            package = client.factory.create('{}:PackageType'.format(namespace))

            if hasattr(package, 'Packaging'):
                package.Packaging.Code = box_shape
            elif hasattr(package, 'PackagingType'):
                package.PackagingType.Code = box_shape
            
            package.Dimensions.UnitOfMeasurement.Code = 'IN'
            package.Dimensions.Length = p.length
            package.Dimensions.Width = p.width
            package.Dimensions.Height = p.height
            
            package.PackageWeight.UnitOfMeasurement.Code = 'LBS'
            package.PackageWeight.Weight = p.weight

            if p.require_signature:
                package.PackageServiceOptions.DeliveryConfirmation.DCISType = str(p.require_signature)
            
            if p.value:
                package.PackageServiceOptions.DeclaredValue.CurrencyCode = 'USD'
                package.PackageServiceOptions.DeclaredValue.MonetaryValue = p.value
            
            if create_reference_number and p.reference:
                try:
                    reference_number = client.factory.create('{}:ReferenceNumberType'.format(namespace))
                    reference_number.Value = p.reference
                    package.ReferenceNumber.append(reference_number)
                except suds.TypeNotFound as e:
                    pass

            shipment.Package.append(package)

        shipfrom_name = shipper_address.name[:35]
        shipfrom_company = shipper_address.company_name[:35]
        shipment.Shipper.Name = shipfrom_company or shipfrom_name
        shipment.Shipper.Address.AddressLine = [ shipper_address.address1, shipper_address.address2 ]
        shipment.Shipper.Address.City = shipper_address.city
        shipment.Shipper.Address.StateProvinceCode = shipper_address.state
        shipment.Shipper.Address.PostalCode = shipper_address.zip
        shipment.Shipper.Address.CountryCode = self._normalized_country_code(shipper_address.country)
        shipment.Shipper.ShipperNumber = self.credentials['shipper_number']
        
        shipto_name = recipient_address.name[:35]
        shipto_company = recipient_address.company_name[:35]
        shipment.ShipTo.Name = shipto_company or shipto_name
        shipment.ShipTo.Address.AddressLine = [ recipient_address.address1, recipient_address.address2 ]
        shipment.ShipTo.Address.City = recipient_address.city
        shipment.ShipTo.Address.StateProvinceCode = recipient_address.state
        shipment.ShipTo.Address.PostalCode = recipient_address.zip
        shipment.ShipTo.Address.CountryCode = self._normalized_country_code(recipient_address.country)
        if recipient_address.is_residence:
            shipment.ShipTo.Address.ResidentialAddressIndicator = ''
        
        return shipment

    def rate(self, packages, packaging_type, shipper, recipient):
        client = self._get_client('RateWS.wsdl')
        self._add_security_header(client)
        if not self.debug:
            client.set_options(location='https://onlinetools.ups.com/webservices/Rate')

        request = client.factory.create('ns0:RequestType')
        request.RequestOption = 'Shop'

        classification = client.factory.create('ns2:CodeDescriptionType')
        classification.Code = '00' # Get rates for the shipper account

        shipment = self._create_shipment(client, packages, shipper, recipient, packaging_type, namespace='ns2')

        try:
            self.reply = client.service.ProcessRate(request, CustomerClassification=classification, Shipment=shipment)
            logging.debug(self.reply)
            
            service_lookup = dict(SERVICES)

            info = list()
            for r in self.reply.RatedShipment:
                unknown_service = 'Unknown Service: {}'.format(r.Service.Code)
                info.append({
                    'service': service_lookup.get(r.Service.Code, unknown_service),
                    'package': '',
                    'delivery_day': '',
                    'cost': r.TotalCharges.MonetaryValue,
                })

            response = { 'status': self.reply.Response.ResponseStatus.Description, 'info': info }
            return response
        except suds.WebFault as e:
            raise UPSError(e.fault, e.document)
    
    def validate(self, recipient):
        client = self._get_client('XAV.wsdl')
        self._add_security_header(client)
        if not self.debug:
            client.set_options(location='https://onlinetools.ups.com/webservices/XAV')
        
        request = client.factory.create('ns0:RequestType')
        request.RequestOption = 1 # Address Validation
        
        address = client.factory.create('ns2:AddressKeyFormatType')
        address.ConsigneeName = recipient.name
        address.AddressLine = [ recipient.address1, recipient.address2 ]
        address.PoliticalDivision2 = recipient.city
        address.PoliticalDivision1 = recipient.state
        address.PostcodePrimaryLow = recipient.zip
        address.CountryCode = self._normalized_country_code(recipient.country)
        
        try:
            reply = client.service.ProcessXAV(request, AddressKeyFormat=address)
            
            candidates = list()
            if hasattr(reply, 'Candidate'):
                for c in reply.Candidate:
                    name = c.AddressKeyFormat.ConsigneeName if hasattr(c.AddressKeyFormat, 'ConsigneeName') else ''
                    a = Address(
                        name,
                        c.AddressKeyFormat.AddressLine[0],
                        c.AddressKeyFormat.PoliticalDivision2,
                        c.AddressKeyFormat.PoliticalDivision1,
                        c.AddressKeyFormat.PostcodePrimaryLow,
                        c.AddressKeyFormat.CountryCode)
                    if len(c.AddressKeyFormat.AddressLine) > 1:
                        a.address2 = c.AddressKeyFormat.AddressLine[1]

                    if a not in candidates:
                        candidates.append(a)
            
            valid = hasattr(reply, 'ValidAddressIndicator')
            ambiguous =  hasattr(reply, 'AmbiguousAddressIndicator')
            return { 'candidates': candidates, 'valid': valid, 'ambiguous': ambiguous }
        except suds.WebFault as e:
            raise UPSError(e.fault, e.document)
    
    def label(self, packages, shipper_address, recipient_address, service, box_shape, validate_address, email_notifications=list(), create_commercial_invoice=False, products=[]):
        client = self._get_client('Ship.wsdl')
        self._add_security_header(client)
        if not self.debug:
            client.set_options(location='https://onlinetools.ups.com/webservices/Ship')

        request = client.factory.create('ns0:RequestType')
        request.RequestOption = 'validate' if validate_address else 'nonvalidate'
        
        create_reference_number = recipient_address.country in ( 'US', 'CA', 'PR' ) and shipper_address.country == recipient_address.country
        shipment = self._create_shipment(client, packages, shipper_address, recipient_address, box_shape, create_reference_number=create_reference_number)
        if not create_reference_number:
            reference_number = client.factory.create('ns3:ReferenceNumberType')
            reference_number.Value = packages[0].reference
            shipment.ReferenceNumber.append(reference_number)

        charge = client.factory.create('ns3:ShipmentChargeType')
        charge.Type = '01'
        charge.BillShipper.AccountNumber = self.credentials['shipper_number']
        shipment.PaymentInformation.ShipmentCharge = charge

        shipment.Description = 'Shipment from %s to %s' % (shipper_address.name, recipient_address.name)
        shipment.Description = shipment.Description[:50]
        shipment.Service.Code = service

        shipment.Shipper.AttentionName = shipper_address.name[:35] or shipper_address.company_name[:35]
        shipment.Shipper.Phone.Number = shipper_address.phone
        shipment.Shipper.EMailAddress = shipper_address.email
        shipment.ShipTo.AttentionName = recipient_address.name[:35] or recipient_address.company_name[:35] or ''
        shipment.ShipTo.Phone.Number = recipient_address.phone
        shipment.ShipTo.EMailAddress = recipient_address.email

        if shipment.Shipper.Address.CountryCode == 'US' and shipment.ShipTo.Address.CountryCode in ( 'PR', 'CA' ):
            shipment.InvoiceLineTotal.CurrencyCode = 'USD'
            shipment.InvoiceLineTotal.MonetaryValue = sum([ p.value or 0 for p in packages]) or 1

        for i, p in enumerate(shipment.Package):
            p.Description = 'Package %d' % i

        if email_notifications:
            notification = client.factory.create('ns3:NotificationType')
            notification.NotificationCode = 6 # Ship Notification
            notification.EMail.EMailAddress = email_notifications
            shipment.ShipmentServiceOptions.Notification.append(notification)

        if create_commercial_invoice:
            shipment.ShipmentServiceOptions.InternationalForms.FormType = '01'
            shipment.ShipmentServiceOptions.InternationalForms.InvoiceNumber = packages[0].reference
            shipment.ShipmentServiceOptions.InternationalForms.InvoiceDate = date.today().strftime('%Y%m%d')
            shipment.ShipmentServiceOptions.InternationalForms.ReasonForExport = 'SALE'
            shipment.ShipmentServiceOptions.InternationalForms.CurrencyCode = 'USD'

            shipto_name = recipient_address.name[:35]
            shipto_company = recipient_address.company_name[:35]
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Name = shipto_company or shipto_name
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.AttentionName = shipto_name or shipto_company
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Address.AddressLine = [ recipient_address.address1, recipient_address.address2 ]
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Address.City = recipient_address.city
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Address.StateProvinceCode = recipient_address.state
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Address.PostalCode = recipient_address.zip
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Address.CountryCode = self._normalized_country_code(recipient_address.country)
            shipment.ShipmentServiceOptions.InternationalForms.Contacts.SoldTo.Phone.Number = recipient_address.phone

            for p in products:
                product = client.factory.create('ns2:ProductType')
                product.Unit.UnitOfMeasurement.Code = 'PCS'
                product.Unit.Value = p.item_price
                product.Unit.Number = p.quantity
                product.Description = p.description[:35]
                product.OriginCountryCode = self._normalized_country_code(shipper_address.country)
                shipment.ShipmentServiceOptions.InternationalForms.Product.append(product)

        label = client.factory.create('ns3:LabelSpecificationType')
        label.LabelImageFormat.Code = 'GIF'
        label.HTTPUserAgent = 'Mozilla/4.5'

        try:
            self.reply = client.service.ProcessShipment(request, shipment, label)
            
            results = self.reply.ShipmentResults

            response = {
                'status': self.reply.Response.ResponseStatus.Description,
                'shipments': list(),
                'international_document': {
                    'description': None,
                    'pdf': None
                }
            }

            shipments = list()
            for p in results.PackageResults:
                response['shipments'].append({
                    'tracking_number': p.TrackingNumber,
                    'cost': results.ShipmentCharges.TotalCharges.MonetaryValue,
                    'label': base64.b64decode(p.ShippingLabel.GraphicImage),
                })
            
            try:
                response['international_document']['description'] = results.Form.Description
                response['international_document']['pdf'] = base64.b64decode(results.Form.Image.GraphicImage)
            except AttributeError as e:
                pass

            return response
        except suds.WebFault as e:
            print client.last_sent()
            raise UPSError(e.fault, e.document)
