from urllib2 import Request, urlopen, URLError
import string, re, base64
import xml.etree.ElementTree as etree
from misc import indent, debug_print

class QNames:
    @classmethod
    def SoapTagString(cls, tag):
        return u'{http://schemas.xmlsoap.org/soap/envelope/}%s' % tag
    
    @classmethod
    def SoapTag(cls, tag):
        return etree.QName(QNames.SoapTagString(tag))
        
    @classmethod
    def SecurityTag(cls, tag):
        return etree.QName(u'http://www.ups.com/XMLSchema/XOLTWS/UPSS/v1.0', tag)
        
    @classmethod
    def CommonTag(cls, tag):
        return etree.QName(u'http://www.ups.com/XMLSchema/XOLTWS/Common/v1.0', tag)
    
    @classmethod
    def ShipURI(cls):
        return u'http://www.ups.com/XMLSchema/XOLTWS/Ship/v1.0'
        
    @classmethod
    def ShipTagString(cls, tag):
        return u'{%s}%s' % (QNames.ShipURI(), tag)

    @classmethod
    def ShipTag(cls, tag):
        return etree.QName(u'http://www.ups.com/XMLSchema/XOLTWS/Ship/v1.0', tag)
        
class Credentials(object):
    def __init__(self, username, password, token):
        self.username = username
        self.password = password
        self.token = token

    def GetTree(self):
        root = etree.Element(QNames.SecurityTag(u'UPSSecurity'))

        usernameToken = etree.SubElement(root, QNames.SecurityTag(u'UsernameToken'))
        etree.SubElement(usernameToken, QNames.SecurityTag(u'Username')).text = self.username
        etree.SubElement(usernameToken, QNames.SecurityTag(u'Password')).text = self.password

        serviceAccessToken = etree.SubElement(root, QNames.SecurityTag(u'ServiceAccessToken'))
        etree.SubElement(serviceAccessToken, QNames.SecurityTag(u'AccessLicenseNumber')).text = self.token

        return root

    def __repr__(self):
        root = self.getETreeElement()
        indent(root)
        return etree.tostring(root)
        
class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2=None, phone=None):
        self.name = name
        self.address1 = address
        self.address2 = address2
        self.city = city
        self.state = state
        self.zip = zip
        self.country = country
        self.phone = phone

    def AddElementsToTree(self, root):
        etree.SubElement(root, QNames.ShipTag(u'Name')).text = self.name
        address = etree.SubElement(root, QNames.ShipTag(u'Address'))
        etree.SubElement(address, QNames.ShipTag(u'AddressLine')).text = self.address1
        etree.SubElement(address, QNames.ShipTag(u'AddressLine')).text = self.address2
        etree.SubElement(address, QNames.ShipTag(u'City')).text = self.city
        etree.SubElement(address, QNames.ShipTag(u'StateProvinceCode')).text = self.state
        etree.SubElement(address, QNames.ShipTag(u'PostalCode')).text = str(self.zip)
        etree.SubElement(address, QNames.ShipTag(u'CountryCode')).text = self.country
        if self.phone:
            phone = etree.SubElement(root, QNames.ShipTag(u'Phone'))
            etree.SubElement(phone, QNames.ShipTag(u'Number')).text = self.phone

class ShipperAddress(Address):
    def __init__(self, name, address, city, state, zip, country, shipper_number, address2=None, phone=None):
        super(ShipperAddress, self).__init__(name, address, city, state, zip, country, address2, phone)
        self.shipper_number = shipper_number

    def AddElementsToTree(self, root):
        super(ShipperAddress, self).AddElementsToTree(root)
        etree.SubElement(root, QNames.ShipTag(u'ShipperNumber')).text = self.shipper_number
        
class UPSShipRequest(object):
    def __init__(self, credentials):
        self.credentials = credentials
        self.use_production_url = False

    def Send(self):
        url = 'https://onlinetools.ups.com/webservices/Ship' if self.use_production_url else 'https://wwwcie.ups.com/webservices/Ship'
        root = self._get_xml()
        #debug_print(root)
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