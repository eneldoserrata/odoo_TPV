"""
This module provides helpers in order to manage fiscal invoices
"""


class Invoice:
    """
    Represents a fiscal invoice
    """

    pass


def format_invoice(invoice):
    """
    :return formatted string representation of the invoice according to Neotec Invoice Format
    :param invoice.
    """

    formatted_invoice = invoice['type'] + '||' + invoice['copyQty'] + '||' + invoice['logo'] + '||' + invoice['density'] + '||' + invoice['ncf']['office'] + '||' + invoice['ncf']['box'] + '||' + invoice['ncfString']

    return formatted_invoice
