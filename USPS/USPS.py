from urllib2 import Request, urlopen, URLError, quote
import xml.etree.ElementTree as etree

def indent(elem, level=0):
    """Indents an etree element so printing that element is actually human-readable"""
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def debug_print(elem):
    indent(elem)
    etree.dump(elem)

class Credentials(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2='', phone=''):
        self.name = name
        self.address1 = address
        self.address2 = address2
        self.city = city
        self.state = state
        self.zip = str(zip)
        self.country = country
        self.phone = phone

class Package(object):
    FirstClassService='FIRST CLASS'
    PriorityService='PRIORITY'
    PriorityCommericialService='PRIORITY COMMERCIAL'
    ExpressService='EXPRESS'
    ExpressCommercialService='EXPRESS COMMERCIAL'
    ExpressSHService='EXPRESS SH'
    ExpressSHCommercialService='EXPRESS SH COMMERCIAL'
    ExpressHFPService='EXPRESS HFP'
    ExpressHFPCommercialService='EXPRESS HFP COMMERCIAL'
    BPMService='BPM'
    ParcelService='PARCEL'
    MediaService='MEDIA'
    LibraryService='LIBRARY'
    AllService='ALL'
    OnlineService='ONLINE'
    
    LetterMailType = 'LETTER'
    FlatMailType = 'FLAT'
    ParcelMailType = 'PARCEL'
    
    RegularSize = 'REGULAR'
    LargeSize = 'LARGE'
    OversizeSize = 'OVERSIZE'

    def __init__(self, shipper, recipient, weight_lbs, weight_ozs, length, width, height):
        self.service_type = self.AllService
        self.shipper = shipper
        self.recipient = recipient
        self.weight = (weight_lbs, weight_ozs)
        self.dimensions = (length, width, height)
        self.size = self.RegularSize
        self.postages = dict()
        
    def __repr__(self):
        text = self.ID()
        for (mail_type, rate) in self.postages.items():
            text += '\n\t%s: %s' % (mail_type, rate)
        return text
        
    def ID(self):
        id = '%s To %s Package' % (self.shipper.name, self.recipient.name)
        return id.replace(' ', '')
        
    def SetFirstClass(self, mail_type):
        self.service_type = self.FirstClassService
        self.first_class_mail_type = mail_type
    
    def AddPostage(self, mail_type, rate):
        self.postages[mail_type] = rate
        
class Error(object):
    def __init__(self, number, description, source):
        self.number = number
        self.description = description
        self.source = source
        
    def __repr__(self):
        return "Error in '%s': %s" % (self.source, self.description)

class USPSRequest(object):
    def __init__(self, credentials, url):
        self.credentials = credentials
        self.url = url
        
    def Send(self):
        root = self._GetXML()
        request_text = etree.tostring(root)

        try:
            full_url = '%s%s' % (self.url, quote(request_text))
            request = Request(full_url)
            response_text = urlopen(request).read()
            response = self._ParseResponse(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                print 'Could not reach the server, reason: %s' % e.reason
            elif hasattr(e, 'code'):
                print 'Could not fulfill the request, code: %d' % e.code
            raise

        return response
        
    def _GetXML(self):
        return self._GetBody()
        
    def _ParseResponse(self, response_text):
        """Parses the text from a USPS web service call"""
        root = etree.fromstring(response_text)
        response = None
        if root.tag == 'Error':
            response = self._ParseError(root)
        else:
            response = self._ParseResponseBody(root)
        return response
        
    def _ParseError(self, error_root):
        number = error_root.findtext('Number')
        description = error_root.findtext('Description')
        source = error_root.findtext('Source')
        return Error(number, description, source)

class RateRequest(USPSRequest):
    def __init__(self, username, packages):
        self.debug = True
        url = 'http://testing.shippingapis.com/ShippingAPITest.dll?API=RateV2&XML=' if self.debug else 'http://production.shippingapis.com/ShippingAPI.dll?API=RateV3&XML='
        
        credentials = Credentials(username, '')
        super(RateRequest, self).__init__(credentials, url)
        self.packages = packages

    def __repr__(self):
        body = self._GetBody()
        indent(body)
        return etree.tostring(body)
        
    def _GetBody(self):
        root_id = u'RateV2Request' if self.debug else u'RateV3Request'
        root = etree.Element(root_id)
        root.set('USERID', self.credentials.username)
        
        for i, package in enumerate(self.packages):
            package_token = etree.SubElement(root, u'Package')
            package_id = '%s%d' % (package.ID(), i)
            package_token.set('ID', package_id)

            etree.SubElement(package_token, u'Service').text = package.service_type
            if package.service_type == Package.FirstClassService:
                etree.SubElement(package_token, u'FirstClassMailType').text = package.first_class_mail_type

            etree.SubElement(package_token, u'ZipOrigination').text = package.shipper.zip
            etree.SubElement(package_token, u'ZipDestination').text = package.recipient.zip

            etree.SubElement(package_token, u'Pounds').text = str(package.weight[0])
            etree.SubElement(package_token, u'Ounces').text = str(package.weight[1])

            etree.SubElement(package_token, u'Container')

            """
            May be left blank in situations that do not require a Size. Defined as follows: REGULAR: package length plus girth is 84 inches or less; LARGE: package length plus girth measure more than 84 inches but not more than 108 inches; OVERSIZE: package length plus girth is more than 108 but not more than 130 inches. 
            """
            length = max(package.dimensions)
            etree.SubElement(package_token, u'Size').text = Package.LargeSize

            etree.SubElement(package_token, u'Machinable').text = 'true'

        return root
        
    def _ParseResponseBody(self, root):
        return RateResponse(root, self.packages)

class RateResponse(object):
    def __init__(self, root, packages):
        self.packages = packages
        
        package_roots = root.findall('Package')
        assert len(package_roots) == len(self.packages)
        for i, package in enumerate(self.packages):
            postage_roots = package_roots[i].findall('Postage')
            for postage_root in postage_roots:
                mail_service = postage_root.findtext('MailService')
                rate = postage_root.findtext('Rate')
                package.AddPostage(mail_service, rate)
        
    def __repr__(self):
        import pprint
        return pprint.pformat(self.packages)
        
class DeliveryConfirmationRequest(USPSRequest):
    def __init__(self, username, sender, recipient, weight_in_ounces):
        self.debug = True
        url = 'https://secure.shippingapis.com/ShippingAPITest.dll?API=DelivConfirmCertifyV3&XML=' if self.debug else 'https://production.shippingapis.com/ShippingAPI.dll?API=DeliveryConfirmationV3&XML='
        
        credentials = Credentials(username, '')
        super(DeliveryConfirmationRequest, self).__init__(credentials, url)
        
        self.sender = sender
        self.recipient = recipient
        self.weight_in_ounces = str(weight_in_ounces)
        
    def __repr__(self):
        body = self._GetBody()
        indent(body)
        return etree.tostring(body)
        
    def _GetBody(self):
        root_id = u'DelivConfirmCertifyV3.0Request' if self.debug else u'DeliveryConfirmationV3.0Request'
        root = etree.Element(root_id)
        root.set('USERID', self.credentials.username)
        
        etree.SubElement(root, u'Option').text = '1'
        etree.SubElement(root, u'ImageParameters')
        
        etree.SubElement(root, u'FromName').text = self.sender.name[0:31]
        etree.SubElement(root, u'FromFirm')
        etree.SubElement(root, u'FromAddress1').text = self.sender.address2[0:31]
        etree.SubElement(root, u'FromAddress2').text = self.sender.address1[0:31]
        etree.SubElement(root, u'FromCity').text = self.sender.city[0:31]
        etree.SubElement(root, u'FromState').text = self.sender.state
        etree.SubElement(root, u'FromZip5').text = self.sender.zip
        etree.SubElement(root, u'FromZip4')
        
        etree.SubElement(root, u'ToName').text = self.recipient.name[0:31]
        etree.SubElement(root, u'ToFirm')
        etree.SubElement(root, u'ToAddress1').text = self.recipient.address2[0:31]
        etree.SubElement(root, u'ToAddress2').text = self.recipient.address1[0:31]
        etree.SubElement(root, u'ToCity').text = self.recipient.city[0:31]
        etree.SubElement(root, u'ToState').text = self.recipient.state
        etree.SubElement(root, u'ToZip5').text = self.recipient.zip
        etree.SubElement(root, u'ToZip4')
        
        etree.SubElement(root, u'WeightInOunces').text = self.weight_in_ounces
        etree.SubElement(root, u'ServiceType').text = 'Priority'
        etree.SubElement(root, u'POZipCode')
        
        etree.SubElement(root, u'ImageType').text = 'TIF'
        #etree.SubElement(root, u'AddressServiceRequest').text = 'TRUE'
        etree.SubElement(root, u'LabelDate')

        return root
    
    def _ParseResponseBody(self, root):
        return DeliveryConfirmationResponse(root)
        
class DeliveryConfirmationResponse(object):
    def __init__(self, root):
        self.root = root
    
    def __repr__(self):
        indent(self.root)
        return etree.tostring(self.root)