"""
This module provides helpers in order to manage fiscal invoices
"""


def format_invoice(invoice):
    """
    :return formatted string representation of the invoice according to Neotec Invoice Format
    :param invoice.
    """

    # invoice body
    formatted_invoice = invoice['type'] + '||' + invoice['copyQty'] + '||' + invoice['logo'] + '||' + invoice[
        'density'] + '||' + invoice['ncf']['office'] + '||' + invoice['ncf']['box'] + '||' + invoice[
                            'ncfString'] + '||' + invoice['client']['name'] + '||' + invoice['client']['rnc'] + '||' + \
                        invoice['referenceNcf'] + '||' + invoice['discount'] + '||' + invoice['charge'] + '||' + \
                        invoice['tip'] + '||' + invoice['comments'] + '||' + invoice['legalTenPercent'] + '||' + \
                        invoice['effectivePayment'] + '||' + invoice['checkPayment'] + '||' + invoice[
                            'creditCardPayment'] + '||' + invoice['debitCardPayment'] + '||' + invoice[
                            'ownCardPayment'] + '||' + invoice['voucherPayment'] + '||' + invoice[
                            'other1Payment'] + '||' + invoice['other2Payment'] + '||' + invoice[
                            'other3Payment'] + '||' + invoice['other4Payment'] + '||' + invoice['creditNotePayment']

    formatted_invoice += '\n'

    # items
    for item in invoice['items']:
        formatted_invoice += item['type'] + '||' + item['quantity'] + '||' + item['description'] + '||' + item['price'] + '||' + item['tax'] + '\n'

    return formatted_invoice
