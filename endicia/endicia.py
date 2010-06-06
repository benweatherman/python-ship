import re
from urllib2 import Request, urlopen, URLError, quote
import base64
import xml.etree.ElementTree as etree
        
class package(object):
    shipment_types = [
                'Priority',
                'Express',
                'First',
                'LibraryMail',
                'MediaMail',
                'ParcelPost',
                'ParcelSelect',
                'StandardMailClass',
                'ExpressMailInternational',
                'FirstClassMailInternational',
                'PriorityMailInternational',
            ]
    
    shapes = [
                'SmallFlatRateBox',
                'MediumFlatRateBox',
                'LargeFlatRateBox',
                'Parcel',
             ]

    def __init__(self, weight_oz, shape, length, width, height, description='', value=0):
        self.mail_class = self.shipment_types[0]
        self.weight_oz = str(weight_oz)
        self.shape = shape
        self.dimensions = ( str(length), str(width), str(height) )
        self.description = description
        self.value = str(value)

class request(object):
    def __init__(self, url, api):
        self.debug = True
        self.url = url
        self.api = api
        
    def Send(self):
        root = self._get_xml()
        request_text = etree.tostring(root)

        try:
            url_base = u'https://www.envmgr.com/LabelService/EwsLabelService.asmx' if self.debug else u'https://LabelServer.endicia.com'
            full_url = u'%s/%s' % (url_base, self.url)
            data = '%s=%s' % (self.api, quote(request_text))
            request = Request(full_url, data)
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
            response = error(status, root, namespace)
        else:
            response = self._parse_response_body(root, namespace)
        return response

class error(object):
    def __init__(self, status, root, namespace):
        self.status = status
        error_path = '{%s}ErrorMessage' % namespace
        self.message = root.findtext(error_path)
        
    def __repr__(self):
        return 'Endicia error %d: %s' % (self.status, self.message)
        
class label_request(request):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient):
        url = u'GetPostageLabelXML'
        api = u'labelRequestXML'
        super(label_request, self).__init__(url, api)
        
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        
        self.package = package
        self.shipper = shipper
        self.recipient = recipient
        
    def _parse_response_body(self, root, namespace):
        return label_response(root, namespace)
        
    def _get_xml(self):
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
        
        self.__add_address(self.shipper, 'From', root)
        self.__add_address(self.recipient, 'To', root)

        return root
        
    def __add_address(self, address, type, root):
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
            
class label_response(object):
    def __init__(self, root, namespace):
        self.root = root
        self.tracking = root.findtext('{%s}TrackingNumber' % namespace)
        self.postage = root.findtext('{%s}FinalPostage' % namespace)
        encoded_image = root.findtext('{%s}Base64LabelImage' % namespace)
        self.label = base64.b64decode(encoded_image)
        
    def __repr__(self):
        return 'Tracking: %s, cost: $%s' % (self.tracking, self.postage)
        
class recredit_request(request):
    def __init__(self, partner_id, account_id, passphrase, amount):
        self.debug = True
        url = u'BuyPostageXML'
        api = u'recreditRequestXML'
        super(recredit_request, self).__init__(url, api)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        
        self.amount = str(amount)

    def _parse_response_body(self, root, namespace):
        return recredit_response(root, namespace)

    def _get_xml(self):
        root = etree.Element('RecreditRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'Recredit %s for %s' % (self.partner_id, self.amount)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase
        
        etree.SubElement(root, u'RecreditAmount').text = self.amount

        return root

class recredit_response(object):
    def __init__(self, root, namespace):
        self.root = root
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)
        
class change_password_request(request):
    def __init__(self, partner_id, account_id, passphrase, new_passphrase):
        self.debug = True
        url = u'ChangePassPhraseXML'
        api = u'changePassPhraseRequestXML'
        super(change_password_request, self).__init__(url, api)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

        self.new_passphrase = new_passphrase

    def _parse_response_body(self, root, namespace):
        return change_password_response(root, namespace)

    def _get_xml(self):
        root = etree.Element('ChangePassPhraseRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'ChangePassPhrase %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase

        etree.SubElement(root, u'NewPassPhrase').text = self.new_passphrase

        return root

class change_password_response(object):
    def __init__(self, root, namespace):
        self.root = root
        self.status = root.findtext('{%s}Status' % namespace)

    def __repr__(self):
        return 'Password Change: %s' % ('OK' if int(self.status) == 0 else 'Error')
        
class rate_request(request):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient):
        self.debug = True
        url = u'CalculatePostageRateXML'
        api = u'postageRateRequestXML'
        super(rate_request, self).__init__(url, api)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

        self.package = package
        self.shipper = shipper
        self.recipient = recipient

    def _parse_response_body(self, root, namespace):
        return rate_response(root, namespace)

    def _get_xml(self):
        root = etree.Element('PostageRateRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase
        
        etree.SubElement(root, u'MailClass').text = self.package.mail_class
        #etree.SubElement(root, u'DateAdvance').text = 
        etree.SubElement(root, u'WeightOz').text = self.package.weight_oz
        etree.SubElement(root, u'MailpieceShape').text = self.package.shape
        etree.SubElement(root, u'Value').text = self.package.value
        
        etree.SubElement(root, u'FromPostalCode').text = self.shipper.zip
        etree.SubElement(root, u'ToPostalCode').text = self.recipient.zip
        
        etree.SubElement(root, u'ResponseOptions').set('PostagePrice', 'TRUE')

        return root

        return root

class rate_response(object):
    def __init__(self, root, namespace):
        self.root = root
        self.postage_price = root.find('{%s}PostagePrice' % namespace).get('TotalAmount')

    def __repr__(self):
        return 'Estimated Cost: $%s' % self.postage_price
        
class account_status_request(request):
    def __init__(self, partner_id, account_id, passphrase):
        self.debug = True
        url = u'GetAccountStatusXML'
        api = u'accountStatusRequestXML'
        super(account_status_request, self).__init__(url, api)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

    def _parse_response_body(self, root, namespace):
        return account_status_response(root, namespace)

    def _get_xml(self):
        root = etree.Element('AccountStatusRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'AccountStatusRequest %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase

        return root

class account_status_response(object):
    def __init__(self, root, namespace):
        self.root = root
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)