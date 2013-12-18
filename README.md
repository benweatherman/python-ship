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


USPS Domestic Shipping Rate Example
===================================

The USPS module uses Endicia to calculate shipping rates and generate labels. For this example, we'll need to import the Package and Endicia classes from the `endicia` module and the Address class from the `shipping` module:

    from endicia import Package, Endicia
    from shipping import Address

To calculate shipping or generate a label, you have to first create a Package object:

    # Separate variables for the sake of clarity.
    mail_class = Package.shipment_types[0] # "Priority"
    weight_in_oz = 20
    packaging_shape = Package.shapes[1] # "MediumFlatRateBox"
    length = 10 # inches
    width = 10 # inches
    height = 10 # inches

    package = Package(mail_class, weight_in_oz, packaging_shape, length, width, height)

You also need to create Address objects to represent the address you are shipping from and the address you are shipping to:

    shipper = Address('Microsoft', "1 157th Ave NE", 'Redmond', 'WA', 98052, 'US')
    recipient = Address("Apple", "1 Infinite Loop", 'Cupertino', 'CA', 95014, 'US')

And finally, you need to create an Endicia object and pass your authentication info, package, and addresses to it:

    api = Endicia({
        "partner_id": "<your partner ID goes here>",
        "account_id": "000000", # Your account ID. Has to be a six-digit value.
        "passphrase": "<your passphrase goes here>"
    })

Then you are free to call whatever API functions on the Endicia object you like. In this example, we want the `rate` function:

    shipping_rate = api.rate([package], package.shape, shipper, recipient, debug=True) 

Which should put something like this in `shipping_rate`:

    {
        'status': 0,
        'info': [
            {
                'delivery_day': '', 
                'cost': 11.3, 
                'service': Priority Mail Medium Flat Rate Box,
                'package': Priority
            },
            {
                'delivery_day': '',
                'cost': 39.95,
                'service': Priority Mail Express Flat Rate Box,
                'package': Express
            }
        ]
    }
