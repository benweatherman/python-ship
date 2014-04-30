import logging
logger = logging.getLogger(__name__)

import re
from urllib2 import Request, urlopen, URLError, quote
import base64
import xml.etree.ElementTree as etree

import suds
from suds.client import Client
from suds.sax.element import Element
from decimal import Decimal
from iso_country_codes import lookup_code, lookup_country

class EndiciaError(Exception):
    pass

class EndiciaWebError(EndiciaError):
    def __init__(self, fault, document):
        self.fault = fault
        self.document = document
        
        error_text = 'Endicia error {}: {}'.format(fault.faultcode, fault.faultstring)
        super(EndiciaWebError, self).__init__(error_text)

class Customs(object):
    def __init__(self, description, quantity, weight, value, country):
        self._description = description
        self._quantity = quantity
        self._weight = weight
        self._value = value
        self._country = country
    
    @property
    def description(self):
        return self._description
    
    @property
    def quantity(self):
        return self._quantity
    
    @property
    def weight(self):
        return self._weight
    
    @property
    def value(self):
        return self._value
    
    @property
    def country(self):
        return lookup_country(self._country)
       
    @property
    def country_code(self):
        return lookup_code(self._country)

class Package(object):
    domestic_shipment_types = [
        'Priority',
        'Express',
        'First',
        'LibraryMail',
        'MediaMail',
        'ParcelPost',
        'ParcelSelect',
        'StandardMailClass',
    ]
    
    international_shipment_types = [
        'ExpressMailInternational',
        'FirstClassMailInternational',
        'PriorityMailInternational',
    ]
    
    shipment_types = domestic_shipment_types + international_shipment_types
    
    shapes = [
        'SmallFlatRateBox',
        'MediumFlatRateBox',
        'LargeFlatRateBox',
        'Parcel',
        'Card',
        'Letter',
        'Flat',
        'LargeParcel',
        'IrregularParcel',
        'OversizedParcel',
        'FlatRateEnvelope',
        'FlatRatePaddedEnvelope',
     ]

    def __init__(self, mail_class, weight_oz, shape, length, width, height, description='', value=0):
        self.mail_class = mail_class
        self.weight_oz = str(weight_oz)
        self.shape = shape
        self.length = length
        self.width = width
        self.height = height
        self.description = description
        self.value = str(value)

    @property
    def weight_in_ozs(self):
        return self.weight_oz

    @property
    def dimensions(self):
        return (self.length, self.width, self.height)


class Endicia(object):
    def __init__(self, credentials, debug=True):
        self.wsdl_url = 'https://www.envmgr.com/LabelService/EwsLabelService.asmx?WSDL' if debug else 'https://LabelServer.Endicia.com/LabelService/EwsLabelService.asmx?WSDL'
        self.credentials = credentials
        self.debug = debug
        self.client = Client(self.wsdl_url)

    def rate(self, package, shipper, recipient, insurance='OFF', insurance_amount=0, delivery_confirmation=False, signature_confirmation=False):
        # Play nice with the other function signatures, which expect to take lists of packages.
        if not isinstance(package, Package):

            # But not too nice.
            if len(package) > 1:
                raise Exception("Can only take one Package at a time!")

            package = package[0]
        
        to_country_code = lookup_code(recipient.country)

        request = self.client.factory.create('PostageRatesRequest')
        request.RequesterID = self.credentials['partner_id']
        request.CertifiedIntermediary.AccountID = self.credentials['account_id']
        request.CertifiedIntermediary.PassPhrase = self.credentials['passphrase']

        request.MailClass = 'Domestic' if to_country_code.upper() == 'US' else 'International'
        request.WeightOz = package.weight_in_ozs
        request.MailpieceShape = package.shape
        request.MailpieceDimensions.Length = package.length
        request.MailpieceDimensions.Width = package.width
        request.MailpieceDimensions.Height = package.height

        request.FromPostalCode = shipper.zip
        request.ToPostalCode = recipient.zip
        request.ToCountryCode = to_country_code

        request.CODAmount = 0
        request.InsuredValue = insurance_amount
        request.RegisteredMailValue = package.value

        request.Services._InsuredMail = insurance
        if delivery_confirmation:
            request.Services._DeliveryConfirmation = 'ON'
        if signature_confirmation:
            request.Services._SignatureConfirmation = 'ON'

        try:
            reply = self.client.service.CalculatePostageRates(request)
            if reply.Status != 0:
                raise EndiciaError(reply.ErrorMessage)
            logger.debug(reply)

            response = { 'status': reply.Status, 'info': list() }

            for details in reply.PostagePrice:
                response['info'].append({
                    'service': details.Postage.MailService,
                    'package': details.MailClass,
                    'delivery_day': '',
                    'cost': details._TotalAmount
                })
            return response
        except suds.WebFault as e:
            raise EndiciaWebError(e.fault, e.document)

    def label(self, package, shipper, recipient, **kwargs):
        if "debug" not in kwargs:
            kwargs["debug"] = self.debug

        return LabelRequest(self.credentials['partner_id'],
            self.credentials['account_id'], self.credentials['passphrase'],
            package, shipper, recipient, **kwargs
        ).send()

    def cancel(self, tracking_no, shipper, **kwargs):
        if "debug" not in kwargs:
            kwargs["debug"] = self.debug

        return CarrierPickupCancelRequest(
            self.credentials['account_id'], self.credentials['passphrase'],
            tracking_no, shipper, **kwargs
        ).send()

class EndiciaRequest(object):
    def __init__(self, url, api, debug=False):
        self.debug = debug
        self.url = url
        self.api = api
        
    def send(self):
        root = self._get_xml()
        request_text = etree.tostring(root)

        try:
            url_base = u'https://www.envmgr.com/LabelService/EwsLabelService.asmx' if self.debug else u'https://LabelServer.Endicia.com/LabelService/EwsLabelService.asmx'
            full_url = u'%s/%s' % (url_base, self.url)
            data = '%s=%s' % (self.api, quote(request_text))
            request = Request(full_url, data)
            response_text = urlopen(request).read()
            response = self.__parse_response(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                print 'Could not reach the server, reason: %s' % e.reason
            elif hasattr(e, 'code'):
                print 'Could not fulfill the request, code: %d' % e.code
            raise

        return response
        
    def __parse_response(self, response_text):
        """Parses the text from an Endicia web service call"""
        root = etree.fromstring(response_text)
        namespace = re.search('{(.*)}', root.tag).group(1)
        status_path = '{%s}Status' % namespace
        status = int(root.findtext(status_path))
        response = None
        if status != 0:
            response = Error(status, root, namespace)
        else:
            response = self._parse_response_body(root, namespace)
        return response

class Error(object):
    def __init__(self, status, root, namespace):
        self.status = status
        error_path = '{%s}ErrorMessage' % namespace
        self.message = root.findtext(error_path).encode('UTF-8')
        
    def __repr__(self):
        return 'Endicia error %d: %s' % (self.status, self.message)
        
class LabelRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient,
                       stealth=True, value=0, insurance='OFF', insurance_amount=0,
                       customs_form='None', customs_info=list(),
                       contents_type='', contents_explanation='', nondelivery='Return',
                       date_advance=0,
                       delivery_confirmation=False, signature_confirmation=False,
                       customs_signer=None,
                       return_services=False,
                       label_type=None,
                       label_size="4X6",
                       image_format="PNG",
                       debug=False):
        url = u'GetPostageLabelXML'
        api = u'labelRequestXML'
        super(LabelRequest, self).__init__(url, api, debug)
        
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        
        self.package = package
        self.shipper = shipper
        self.recipient = recipient
        self.stealth = 'TRUE' if stealth else 'FALSE'
        self.value = value
        self.insurance = insurance
        self.insurance_amount = insurance_amount
        self.customs_form = customs_form
        self.customs_info = customs_info
        self.contents_type = contents_type
        self.contents_explanation = contents_explanation
        self.nondelivery = nondelivery
        self.date_advance = date_advance
        self.delivery_confirmation = u'ON' if delivery_confirmation else u'OFF'
        self.signature_confirmation = u'ON' if signature_confirmation else u'OFF'
        self.customs_signer = customs_signer
        self.return_services = return_services
        self.label_size = label_size
        self.image_format = image_format

        if not label_type:
            self.label_type = 'International' if package.mail_class in Package.international_shipment_types else 'Default'
        else:
            self.label_type = label_type
            
        
    def _parse_response_body(self, root, namespace):
        return LabelResponse(root, namespace)
        
    def _get_xml(self):
        root = etree.Element('LabelRequest')
        root.set('LabelType', 'Default')
        root.set('LabelSize', self.label_size)
        root.set('ImageFormat', self.image_format)
        if self.debug:
            root.set('Test', 'YES')
        
        etree.SubElement(root, u'LabelType').text = self.label_type
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        
        etree.SubElement(root, u'MailClass').text = self.package.mail_class
        etree.SubElement(root, u'WeightOz').text = self.package.weight_oz
        etree.SubElement(root, u'MailpieceShape').text = self.package.shape
        etree.SubElement(root, u'Stealth').text = self.stealth
        etree.SubElement(root, u'Value').text = self.package.value
        etree.SubElement(root, u'Description').text = self.package.description
        
        etree.SubElement(root, u'PartnerCustomerID').text = 'SomeCustomerID'
        etree.SubElement(root, u'PartnerTransactionID').text = 'SomeTransactionID'
        
        etree.SubElement(root, u'ResponseOptions').set('PostagePrice', 'TRUE')
        
        self.__add_address(self.shipper, 'From', root)
        self.__add_address(self.recipient, 'To', root)
        
        etree.SubElement(root, u'Stealth').text = self.stealth
        etree.SubElement(root, u'Value').text = str(self.value)
        etree.SubElement(root, u'InsuredValue').text = str(self.insurance_amount)
        
        etree.SubElement(root, u'CustomsFormType').text = self.customs_form
        etree.SubElement(root, u'ContentsType').text = self.contents_type
        etree.SubElement(root, u'ContentsExplanation').text = self.contents_explanation
        etree.SubElement(root, u'NonDeliveryOption').text = self.nondelivery
        etree.SubElement(root, u'DateAdvance').text = str(self.date_advance)
        
        services = etree.SubElement(root, u'Services')
        services.set(u'DeliveryConfirmation', self.delivery_confirmation)
        services.set(u'SignatureConfirmation', self.signature_confirmation)
        services.set(u'InsuredMail', self.insurance)

        package_lbs = Decimal(self.package.weight_oz) / 16

        if self.label_type == "International" and package_lbs >= 1:
            etree.SubElement(root, u'LabelSubtype').text = "Integrated"
            
            if package_lbs < 4:
                etree.SubElement(root, u'IntegratedFormType').text = 'Form2976'
            else:
                etree.SubElement(root, u'IntegratedFormType').text = 'Form2976A'

        if self.label_type == "Domestic" or package_lbs < 1:
            etree.SubElement(root, u'LabelSubtype').text = "None"

        if self.return_services:
            services.set(u'ReturnReceipt', "YES")
       
        dimensions = etree.SubElement(root, u'MailpieceDimensions')
        etree.SubElement(dimensions, u'Length').text = str(self.package.length)
        etree.SubElement(dimensions, u'Width').text = str(self.package.width)
        etree.SubElement(dimensions, u'Height').text = str(self.package.height)
 
        for i, info in enumerate(self.customs_info):
            i += 1
            if info.description:
                etree.SubElement(root, u'CustomsDescription%d' % i).text = info.description
            if info.quantity:
                etree.SubElement(root, u'CustomsQuantity%d' % i).text = str(info.quantity)
            if info.weight:
                etree.SubElement(root, u'CustomsWeight%d' % i).text = str(info.weight)
            if info.value:
                etree.SubElement(root, u'CustomsValue%d' % i).text = str(info.value)
            if info.country:
                etree.SubElement(root, u'CustomsCountry%d' % i).text = lookup_code(info.country)
        
        if len(self.customs_info) and self.customs_signer:
            etree.SubElement(root, u'CustomsCertify').text = 'TRUE'
            etree.SubElement(root, u'CustomsSigner').text = self.customs_signer
        
        return root
        
    def __add_address(self, address, type, root):
        info = dict()
        info['Company'] = address.company_name
        info['Name'] = address.name
        info['Address1'] = address.address1
        info['City'] = address.city
        info['State'] = address.state
        info['PostalCode'] = address.zip
        info['CountryCode'] = lookup_code(address.country)
        if address.phone:
            info['Phone'] = address.phone
        if address.address2:
            info['Address2'] = address.address2
        
        for key, value in info.items():
            # Endicia expects ReturnAddressX instead of FromAddressX
            if type == 'From' and 'Address' in key:
                element_key = 'Return%s' % key
            else:
                element_key = '%s%s' % (type, key)
            etree.SubElement(root, element_key).text = value
            
class LabelResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.tracking = root.findtext('{%s}TrackingNumber' % namespace)
        self.postage = root.findtext('{%s}FinalPostage' % namespace)
        encoded_image = root.findtext('{%s}Base64LabelImage' % namespace)
        self.label = base64.b64decode(encoded_image)
        
    def __repr__(self):
        return 'Tracking: %s, cost: $%s' % (self.tracking, self.postage)
        
class RecreditRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, amount, debug=False):
        url = u'BuyPostageXML'
        api = u'recreditRequestXML'
        super(RecreditRequest, self).__init__(url, api, debug)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        
        self.amount = str(amount)

    def _parse_response_body(self, root, namespace):
        return RecreditResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('RecreditRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'Recredit %s for %s' % (self.partner_id, self.amount)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase
        
        etree.SubElement(root, u'RecreditAmount').text = self.amount

        return root

class RecreditResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)
        
class ChangePasswordRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, new_passphrase, debug=False):
        url = u'ChangePassPhraseXML'
        api = u'changePassPhraseRequestXML'
        super(ChangePasswordRequest, self).__init__(url, api, debug)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

        self.new_passphrase = new_passphrase

    def _parse_response_body(self, root, namespace):
        return ChangePasswordResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('ChangePassPhraseRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'ChangePassPhrase %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase

        etree.SubElement(root, u'NewPassPhrase').text = self.new_passphrase

        return root

class ChangePasswordResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.status = root.findtext('{%s}Status' % namespace)

    def __repr__(self):
        return 'Password Change: %s' % ('OK' if int(self.status) == 0 else 'Error')
        
class RateRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient, debug=False):
        url = u'CalculatePostageRateXML'
        api = u'postageRateRequestXML'
        super(RateRequest, self).__init__(url, api, debug)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

        self.package = package
        self.shipper = shipper
        self.recipient = recipient

    def _parse_response_body(self, root, namespace):
        return RateResponse(root, namespace)

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

class RateResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.postage_price = root.find('{%s}PostagePrice' % namespace).get('TotalAmount')

    def __repr__(self):
        return 'Estimated Cost: $%s' % self.postage_price
        
class AccountStatusRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, debug=False):
        url = u'GetAccountStatusXML'
        api = u'accountStatusRequestXML'
        super(AccountStatusRequest, self).__init__(url, api, debug)

        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

    def _parse_response_body(self, root, namespace):
        return AccountStatusResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('AccountStatusRequest')

        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'AccountStatusRequest %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase

        return root

class AccountStatusResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)

class RefundRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, tracking_number, debug=False):
        url = u'RefundRequestXML'
        api = u'refundRequestXML'
        super(RefundRequest, self).__init__(url, api, debug)
        
        self.account_id = account_id
        self.passphrase = passphrase
        self.tracking_number = tracking_number
    
    def send(self):
        root = self._get_xml()
        request_text = etree.tostring(root)

        try:
            url_base = u'https://www.envmgr.com/LabelService/EwsLabelService.asmx' if self.debug else u'https://LabelServer.Endicia.com/LabelService/EwsLabelService.asmx'
            full_url = u'%s?method=RefundRequest' % url_base
            data = 'XMLInput=%s' % quote(request_text)
            request = Request(full_url, data)
            response_text = urlopen(request).read()
            response = self.__parse_response(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                print 'Could not reach the server, reason: %s' % e.reason
            elif hasattr(e, 'code'):
                print 'Could not fulfill the request, code: %d' % e.code
            raise

        return response
    
    def _parse_response_body(self, root, namespace):
        return RefundResponse(root, namespace)
    
    def _get_xml(self):
        root = etree.Element('RefundRequest')

        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        refund_list = etree.SubElement(root, u'RefundList')
        etree.SubElement(refund_list, u'PICNumber').text = self.tracking_number

        return root

class RefundResponse(object):
    def __init__(self, root, namespace):
        self.root = root
    
    def __repr__(self):
        from shipping import debug_print_tree
        debug_print_tree(self.root)

class CarrierPickupCancelRequest(EndiciaRequest):
    def __init__(self, account_id, passphrase, tracking_no, shipper=None, debug=False):
        url = u'CalculatePostageRateXML'
        api = u'postageRateRequestXML'
        super(CarrierPickupCancelRequest, self).__init__(url, api, debug)

        self.account_id = account_id
        self.passphrase = passphrase

        self.tracking_no = tracking_no
        self.shipper = shipper

    def _parse_response_body(self, root, namespace):
        return CarrierPickupCancelResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element(u'CarrierPickupCancel')

        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        etree.SubElement(root, u'ConfirmationNumber').text = "abc"#self.tracking_no
        etree.SubElement(root, u'Test').text = "Y" if self.debug else "N"

        if self.shipper:
            etree.SubElement(root, u'UseAddressOnFile').text = "N"
            etree.SubElement(root, u'CompanyName').text = self.shipper.company_name or self.shipper.name
            etree.SubElement(root, u'Address').text = self.shipper.address1
            etree.SubElement(root, u'City').text = self.shipper.city
            etree.SubElement(root, u'State').text = self.shipper.state
            etree.SubElement(root, u'ZIP5').text = self.shipper.zip

            if self.shipper.address2:
                etree.SubElement(root, u'SuiteOrApt').text = self.shipper.address2

        else:
            etree.SubElement(root, u'UseAddressOnFile').text = "Y"

        #from shipping import debug_print_tree
        #debug_print_tree(root)
        
        return root

class CarrierPickupCancelResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.response = root.findtext('{%s}Response' % namespace)
        self.error = root.findtext('{%s}Response/{%s}Error' % (namespace, namespace))
        self.status = root.findtext('{%s}Response/{%s}Status' % (namespace, namespace))
        self.confirmation_number = root.findtext('{%s}Response/{%s}ConfirmationNumber' % (namespace, namespace))

    def __repr__(self):
        from shipping import debug_print_tree
        debug_print_tree(self.root)
