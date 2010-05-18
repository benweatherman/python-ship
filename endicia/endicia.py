import re
from urllib2 import Request, urlopen, URLError, quote
import base64
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
    ExpressClass = 'Express'
    FirstClass = 'First'
    LibraryMailClass = 'LibraryMail'
    MediaMailClass = 'MediaMail'
    ParcelPostClass = 'ParcelPost'
    ParcelSelectClass = 'ParcelSelect'
    PriorityClass = 'Priority'
    StandardMailClass = 'StandardMailClass'
    ExpressMailInternationalClass = 'ExpressMailInternational'
    FirstClassMailInternationalClass = 'FirstClassMailInternational'
    PriorityMailInternationalClass = 'PriorityMailInternational'
    
    MediumFlatRateBoxShape = 'MediumFlatRateBox'
    """
    Card Letter Flat Parcel
    LargeParcel IrregularParcel OversizedParcel
    FlatRateEnvelope FlatRatePaddedEnvelope
    SmallFlatRateBox MediumFlatRateBox LargeFlatRateBox
    """

    def __init__(self, weight_oz, shape, length, width, height, description='', value=0):
        self.mail_class = self.PriorityClass
        self.weight_oz = str(weight_oz)
        self.shape = shape
        self.dimensions = ( str(length), str(width), str(height) )
        self.description = description
        self.value = str(value)

class EndiciaRequest(object):
    def __init__(self, url, api):
        self.url = url
        self.api = api
        
    def Send(self):
        root = self._GetXML()
        request_text = etree.tostring(root)

        try:
            data = '%s=%s' % (self.api, quote(request_text))
            request = Request(self.url, data)
            response_text = urlopen(request).read()
            response = self.__ParseResponse(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                print 'Could not reach the server, reason: %s' % e.reason
            elif hasattr(e, 'code'):
                print 'Could not fulfill the request, code: %d' % e.code
            raise

        return response
        
    def __ParseResponse(self, response_text):
        """Parses the text from an Endicia web service call"""
        root = etree.fromstring(response_text)
        namespace = re.search('{(.*)}', root.tag).group(1)
        status_path = '{%s}Status' % namespace
        status = int(root.findtext(status_path))
        response = None
        if status != 0:
            response = Error(status, root, namespace)
        else:
            response = self._ParseResponseBody(root, namespace)
        return response

class Error(object):
    def __init__(self, status, root, namespace):
        self.status = status
        error_path = '{%s}ErrorMessage' % namespace
        self.message = root.findtext(error_path)
        
    def __repr__(self):
        return 'Endicia error %d: %s' % (self.status, self.message)
        
class EndiciaLabelRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient):
        self.debug = True
        url = u'https://www.envmgr.com/LabelService/EwsLabelService.asmx/GetPostageLabelXML' if self.debug else u'https://LabelServer.endicia.com/GetPostageLabelXML'
        api = u'labelRequestXML'
        super(EndiciaLabelRequest, self).__init__(url, api)
        
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        
        self.package = package
        self.shipper = shipper
        self.recipient = recipient
        
    def _ParseResponseBody(self, root, namespace):
        return EndiciaLabelResponse(root, namespace)
        
    def _GetXML(self):
        root = etree.Element('LabelRequest')
        root.set('LabelType', 'Default')
        root.set('LabelSize', '4X6')
        root.set('ImageFormat', 'PNG')
        if self.debug:
            root.set('Test', 'YES')
            
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        
        etree.SubElement(root, u'MailClass').text = self.package.mail_class
        #etree.SubElement(root, u'DateAdvance').text = 
        etree.SubElement(root, u'WeightOz').text = self.package.weight_oz
        etree.SubElement(root, u'MailpieceShape').text = self.package.shape
        etree.SubElement(root, u'Stealth').text = 'FALSE'
        etree.SubElement(root, u'Value').text = self.package.value
        etree.SubElement(root, u'Description').text = self.package.description
        
        etree.SubElement(root, u'PartnerCustomerID').text = 'SomeCustomerID'
        etree.SubElement(root, u'PartnerTransactionID').text = 'SomeTransactionID'
        
        etree.SubElement(root, u'ResponseOptions').set('PostagePrice', 'TRUE')
        
        self.__AddAddress(self.shipper, 'From', root)
        self.__AddAddress(self.recipient, 'To', root)

        return root
        
    def __AddAddress(self, address, type, root):
        info = dict()
        info['Name'] = address.name
        info['Address1'] = address.address1
        info['City'] = address.city
        info['State'] = address.state
        info['PostalCode'] = address.zip
        
        for key, value in info.items():
            # Endicia expects ReturnAddressX instead of FromAddressX
            if type == 'From' and 'Address' in key:
                element_key = 'Return%s' % key
            else:
                element_key = '%s%s' % (type, key)
            etree.SubElement(root, element_key).text = value
            
class EndiciaLabelResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.tracking = root.findtext('{%s}TrackingNumber' % namespace)
        self.postage = root.findtext('{%s}FinalPostage' % namespace)
        encoded_image = root.findtext('{%s}Base64LabelImage' % namespace)
        self.label = base64.b64decode(encoded_image)
        
    def __repr__(self):
        return 'Tracking: %s, cost: $%s' % (self.tracking, self.postage)