import unittest2
from neotec_interface.neoutil import neoutil


class TestInvoiceFormat(unittest2.TestCase):

    ncf = {'office': '1', 'box': '1'}
    invoice = {'type': '1', 'copyQty': '0', 'logo': '', 'density': '', 'ncf': ncf, 'ncfString': 'A010010010100000001'}

    def test_pipes_count(self):
        self.assertEqual(neoutil.format_invoice(self.invoice).count('|'), 50)
