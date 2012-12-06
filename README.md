This is my extremely early version of providing a shipment API in Python.

UPS: Ground shipping almost complete
USPS: Rate query complete, delivery confirmation almost complete
FedEx: Not implemented


ups_config and fedex_config dictionaries:

      fedex_config = {
        'meter_number': 'FedEx Meter Number', 
        'password': 'FedEx API password', 
        'account_number': 'FedEx Account Number', 
        'key': 'FedEx API Key'
      }
         
      ups_config = {
        'username': 'UPS Online Username',
        'password': 'UPS Online Password', 
        'shipper_number': 'UPS Shipper Number',
        'access_license': 'UPS API License'
      }