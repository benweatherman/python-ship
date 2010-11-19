import os
import suds
from suds.client import Client
from suds.sax.element import Element
import urlparse
import base64

import logging

from shipping import Address

SERVICES = [
    ('03', 'UPS Ground'),
    ('11', 'UPS Standard'),
    ('01', 'UPS Next Day'),
    ('14', 'UPS Next Day AM'),
    ('02', 'UPS 2nd Day'),
    ('59', 'UPS 2nd Day AM'),
    ('12', 'UPS 3-day Select'),
    ('65', 'UPS Saver'),
    ('07', 'UPS Worldwide Express'),
    ('08', 'UPS Worldwide Expedited'),
    ('54', 'UPS Worldwide Express Plus'),
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
        context.envelope = context.envelope.replace('ns1:Request', 'ns0:Request')

class UPS(object):
    def __init__(self, credentials, debug=True):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.wsdl_dir = os.path.join(this_dir, 'wsdl', 'ups')
        self.credentials = credentials
        self.debug = debug
        
        logging.basicConfig(level=logging.ERROR)
        #logging.getLogger('suds.client').setLevel(logging.DEBUG)
        #logging.getLogger('suds.transport').setLevel(logging.DEBUG)
    
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
    
    def validate(self, recipient):
        client = self._get_client('XAV.wsdl')
        self._add_security_header(client)
        
        request = client.factory.create('ns0:RequestType')
        request.RequestOption = 1 # Address Validation
        
        address = client.factory.create('ns2:AddressKeyFormatType')
        address.ConsigneeName = recipient.name
        address.AddressLine = [ recipient.address1, recipient.address2 ]
        address.PoliticalDivision2 = recipient.city
        address.PoliticalDivision1 = recipient.state
        address.PostcodePrimaryLow = recipient.zip
        address.CountryCode = recipient.country
        
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
    
    def label(self, packages, shipper_address, recipient_address, service, validate_address):
        client = self._get_client('Ship.wsdl')
        self._add_security_header(client)
        if not self.debug:
            client.set_options(location='https://onlinetools.ups.com/webservices/Ship')

        request = client.factory.create('ns0:RequestType')

        request.RequestOption = 'validate' if validate_address else 'nonvalidate'
        
        shipment = client.factory.create('ns3:ShipmentType')
        shipment.Description = 'Shipment from %s to %s' % (shipper_address.name, recipient_address.name)
        shipment.Description = shipment.Description[:50]
        
        charge = client.factory.create('ns3:ShipmentChargeType')
        charge.Type = '01'
        charge.BillShipper.AccountNumber = self.credentials['shipper_number']
        shipment.PaymentInformation.ShipmentCharge = charge
        
        shipment.Service.Code = service
        
        for i, p in enumerate(packages):
            package = client.factory.create('ns3:PackageType')
            package.Description = 'Package %d' % i
            package.Packaging.Code = '02'
            
            package.Dimensions.UnitOfMeasurement.Code = 'IN'
            package.Dimensions.Length = p.length
            package.Dimensions.Width = p.width
            package.Dimensions.Height = p.height
            
            package.PackageWeight.UnitOfMeasurement.Code = 'LBS'
            package.PackageWeight.Weight = p.weight
            shipment.Package.append(package)
        
        shipment.Shipper.Name = shipper_address.name
        shipment.Shipper.Phone.Number = shipper_address.phone
        shipment.Shipper.EMailAddress = shipper_address.email
        shipment.Shipper.Address.AddressLine = [ shipper_address.address1, shipper_address.address2 ]
        shipment.Shipper.Address.City = shipper_address.city
        shipment.Shipper.Address.StateProvinceCode = shipper_address.state
        shipment.Shipper.Address.PostalCode = shipper_address.zip
        shipment.Shipper.Address.CountryCode = self._normalized_country_code(shipper_address.country)
        shipment.Shipper.ShipperNumber = self.credentials['shipper_number']
        
        shipment.ShipTo.Name = recipient_address.name
        shipment.ShipTo.Phone.Number = recipient_address.phone
        shipment.ShipTo.EMailAddress = recipient_address.email
        shipment.ShipTo.Address.AddressLine = [ recipient_address.address1, recipient_address.address2 ]
        shipment.ShipTo.Address.City = recipient_address.city
        shipment.ShipTo.Address.StateProvinceCode = recipient_address.state
        shipment.ShipTo.Address.PostalCode = recipient_address.zip
        shipment.ShipTo.Address.CountryCode = self._normalized_country_code(recipient_address.country)
        
        label = client.factory.create('ns3:LabelSpecificationType')
        label.LabelImageFormat.Code = 'GIF'
        label.HTTPUserAgent = 'Mozilla/4.5'

        try:
            self.reply = client.service.ProcessShipment(request, shipment, label)
            
            results = self.reply.ShipmentResults
            info = list()
            for p in results.PackageResults:
                info.append({
                    'tracking_number': p.TrackingNumber,
                    'cost': results.ShipmentCharges.TotalCharges.MonetaryValue,
                    'label': base64.b64decode(p.ShippingLabel.GraphicImage)
                })

            response = { 'status': self.reply.Response.ResponseStatus.Description, 'info': info }
            return response
        except suds.WebFault as e:
            raise UPSError(e.fault, e.document)
        
class UPSShipRequest(object):
    def __init__(self, credentials):
        self.credentials = credentials
        self.use_production_url = False

    def Send(self):
        url = 'https://onlinetools.ups.com/webservices/Ship' if self.use_production_url else 'https://wwwcie.ups.com/webservices/Ship'
        root = self._get_xml()
        #debug_print_tree(root)
        request_text = etree.tostring(root)

        try:
            kHeaders = { 'SOAPAction': 'http://onlinetools.ups.com/webservices/ShipBinding/v1.1' }
            request = Request(url, request_text, kHeaders)
            response_text = urlopen(request).read()
            response = self._ParseResponse(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                print 'Could not reach the server, reason: %s' % e.reason
            elif hasattr(e, 'code'):
                print 'Could not fulfill the request, code: %d' % e.code
            raise

        return response

    def _ParseResponse(self, response_text):
        """Parses the text from a UPS web service call"""
        root = etree.fromstring(response_text)
        assert len(root.getchildren()) == 2, "Wrong number of document elements in the response: %d (we're expecting 2 elements)" % len(root.getchildren())

        body = root.getchildren()[1]

        fault = body.find(QNames.SoapTagString('Fault'))
        response = None
        if fault != None:
            response = self.__ProcessFault(fault)
        else:
            response = self._ProcessBody(body)

        return response

    def _get_xml(self):
        root = etree.Element(QNames.SoapTag(u'Envelope'))

        header = etree.SubElement(root, QNames.SoapTag(u'Header'))
        header.append(self.credentials.GetTree())

        body = etree.SubElement(root, QNames.SoapTag(u'Body'))
        body.append(self._GetBody())

        return root

    def __ProcessFault(self, fault):
        """When an error occurs, this gets out all the good information to report an error"""
        faultcode = fault.findtext('faultcode')
        faultstring = fault.findtext('faultstring')
        shipmentError = ShipError(faultcode, faultstring)

        # The error namespace seems to change depending on the type of error you get
        # and the ElementTree parser really wants you to search with the namespace as
        # part of the node tag. So we need to find the Errors tag and figure out what
        # namespace it's in.
        # TODO: We should catch any exeptions in here and just dump out the fault
        errorsTag = fault.find('detail').getchildren()[0].tag
        errorNamespace = re.search('{(.*)}', errorsTag).group(1)

        errors = fault.findall('detail/{%s}Errors' % errorNamespace)
        severityPath = string.Template('{$uri}ErrorDetail/{$uri}Severity').substitute(uri=errorNamespace)
        descriptionPath = string.Template('{$uri}ErrorDetail/{$uri}PrimaryErrorCode/{$uri}Description').substitute(uri=errorNamespace)
        digestPath = string.Template('{$uri}ErrorDetail/{$uri}PrimaryErrorCode/{$uri}Digest').substitute(uri=errorNamespace)
        locationPath = string.Template('{$uri}ErrorDetail/{$uri}Location').substitute(uri=errorNamespace)
        subDescriptionPath = string.Template('{$uri}ErrorDetail/{$uri}SubErrorCode/{$uri}Description').substitute(uri=errorNamespace)

        for error in errors:
            severity = error.findtext(severityPath)
            description = error.findtext(descriptionPath)
            digest = error.findtext(digestPath)
            subDescription = error.findtext(subDescriptionPath)
            location = error.find(locationPath)
            locationInfo = None
            if location is not None:
                locationInfo = [ (child.tag, child.text) for child in location ]

            shipmentError.AddErrorInfo(severity, description, digest, subDescription, locationInfo)

        return shipmentError
        
class ShipConfirmRequest(UPSShipRequest):
    def __init__(self, username, password, token, shipper, recipient):
        credentials = Credentials(username, password, token)
        super(ShipConfirmRequest, self).__init__(credentials)
        self.shipper = shipper
        self.recipient = recipient

    def _GetBody(self):
        """Creates the SOAP Body for a ShipConfirmRequest. A ShipConfirmRequest is the first part in
           a 2-stage process for sending a shipment. We send UPS a bunch of information in this request.
           We get back a ShipConfirmResponse and once we like all the data in that response, we send out
           a ShipAcceptRequest to actually make the deal."""
        root = etree.Element(QNames.ShipTag(u'ShipConfirmRequest'))

        requestInfo = etree.SubElement(root, QNames.CommonTag(u'Request'))
        etree.SubElement(requestInfo, QNames.CommonTag(u'RequestOption')).text = u'validate'

        shipment = etree.SubElement(root, QNames.ShipTag(u'Shipment'))
        etree.SubElement(shipment, QNames.ShipTag(u'Description')).text = "Shipment description"

        shipper = etree.SubElement(shipment, QNames.ShipTag(u'Shipper'))
        self.shipper.AddElementsToTree(shipper)

        shipTo = etree.SubElement(shipment, QNames.ShipTag(u'ShipTo'))
        self.recipient.AddElementsToTree(shipTo)

        ship_from = etree.SubElement(shipment, QNames.ShipTag(u'ShipFrom'))
        self.shipper.AddElementsToTree(ship_from)

        paymentInfo = etree.SubElement(shipment, QNames.ShipTag(u'PaymentInformation'))
        shipCharge = etree.SubElement(paymentInfo, QNames.ShipTag(u'ShipmentCharge'))
        etree.SubElement(shipCharge, QNames.ShipTag(u'Type')).text = '01'
        billshipper = etree.SubElement(shipCharge, QNames.ShipTag(u'BillShipper'))
        etree.SubElement(billshipper, QNames.ShipTag(u'AccountNumber')).text = self.shipper.shipper_number

        # TODO: What types of Codes go here for service?
        service = etree.SubElement(shipment, QNames.ShipTag(u'Service'))
        etree.SubElement(service, QNames.ShipTag(u'Code')).text = '02'

        package = etree.SubElement(shipment, QNames.ShipTag(u'Package'))
        etree.SubElement(package, QNames.ShipTag(u'Description')).text = 'Package description'
        packaging = etree.SubElement(package, QNames.ShipTag(u'Packaging'))
        # TODO: Need different codes here for package types
        etree.SubElement(packaging, QNames.ShipTag(u'Code')).text = '02'
        #--
        dimensions = etree.SubElement(package, QNames.ShipTag(u'Dimensions'))
        units = etree.SubElement(dimensions, QNames.ShipTag(u'UnitOfMeasurement'))
        etree.SubElement(units, QNames.ShipTag(u'Code')).text = 'IN'
        etree.SubElement(dimensions, QNames.ShipTag(u'Length')).text = '13'
        etree.SubElement(dimensions, QNames.ShipTag(u'Width')).text = '11'
        etree.SubElement(dimensions, QNames.ShipTag(u'Height')).text = '2'
        #--
        weight = etree.SubElement(package, QNames.ShipTag(u'PackageWeight'))
        units = etree.SubElement(weight, QNames.ShipTag(u'UnitOfMeasurement'))
        etree.SubElement(units, QNames.ShipTag(u'Code')).text = 'LBS'
        etree.SubElement(weight, QNames.ShipTag(u'Weight')).text = '2.0'

        label = etree.SubElement(root, QNames.ShipTag(u'LabelSpecification'))
        imageformat = etree.SubElement(label, QNames.ShipTag(u'LabelImageFormat'))
        etree.SubElement(imageformat, QNames.ShipTag(u'Code')).text = u'GIF'
        etree.SubElement(label, QNames.ShipTag(u'HTTPUserAgent')).text = u'Mozilla/4.5'

        return root

    def _ProcessBody(self, body):
        """Parses the text from a UPS web service call"""
        shipConfirmResponse = body.find(QNames.ShipTagString('ShipConfirmResponse'))
        assert shipConfirmResponse != None

        results = shipConfirmResponse.find(QNames.ShipTagString('ShipmentResults'))
        totalCharges = results.find(QNames.ShipTagString('ShipmentCharges')).find(QNames.ShipTagString('TotalCharges'))
        cost = totalCharges.findtext(QNames.ShipTagString('MonetaryValue'))
        id = results.findtext(QNames.ShipTagString('ShipmentIdentificationNumber'))
        digest = results.findtext(QNames.ShipTagString('ShipmentDigest'))

        return ShipConfirmResponse(id, cost, digest)

class ShipAcceptRequest(UPSShipRequest):
    def __init__(self, username, password, token, digest):
        credentials = Credentials(username, password, token)
        super(ShipAcceptRequest, self).__init__(credentials)
        self.digest = digest

    def _GetBody(self):
        root = etree.Element(QNames.ShipTag(u'ShipAcceptRequest'))
        etree.SubElement(root, QNames.ShipTag(u'ShipmentDigest')).text = self.digest
        return root

    def _ProcessBody(self, body):
        basePath = string.Template('{$uri}ShipAcceptResponse/{$uri}ShipmentResults/{$uri}PackageResults').substitute(uri=QNames.ShipURI())
        trackingPath = string.Template('$base/{$uri}TrackingNumber').substitute(base=basePath, uri=QNames.ShipURI())
        trackingNumber = body.findtext(trackingPath)

        labelPath = string.Template('$base/{$uri}ShippingLabel/{$uri}GraphicImage').substitute(base=basePath, uri=QNames.ShipURI())
        label = body.findtext(labelPath)
        label = base64.b64decode(label)

        return ShipAcceptResponse(trackingNumber, label)
        
class ShipConfirmResponse(object):
    def __init__(self, id, cost, digest):
        self.id = id
        self.cost = cost
        self.digest = digest

    def __repr__(self):
        return 'ShipmentID: %s, cost: %s' % (self.id, self.cost)

class ShipAcceptResponse(object):
    def __init__(self, trackingNumber, label):
        self.trackingNumber = trackingNumber
        self.label = label

    def __repr__(self):
        return 'Tracking number: %s' % self.trackingNumber

class ShipError(object):
    def __init__(self, code, faultstring):
        self.code = code
        self.faultstring = faultstring
        self.errorInfos = list()

    def AddErrorInfo(self, severity, description, digest, subDescription, location):
        info = (severity, description, digest, subDescription, location)
        self.errorInfos.append(info)

    def __repr__(self):
        info = '%s error: %s' % (self.code, self.faultstring)
        for error in self.errorInfos:
            info += '\r\n'
            info += 'Severity: %s, Description: %s' % (error[0], error[1])
            digest = error[2]
            if digest is not None:
                info += '\r\nOther info: %s' % digest

            subDescription = error[3]    
            if subDescription is not None:
                info += '\r\nOther Info: %s' % subDescription

            locationInfo = error[4]
            if locationInfo is not None:
                info += '\r\nLocation:'
                for location in locationInfo:
                    info += '\r\n%s: %s' % (location[0], location[1])
        return info