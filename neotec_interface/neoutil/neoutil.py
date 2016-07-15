"""
This module provides helpers in order to manage fiscal invoices
"""
import ftplib
import traceback
from ftplib import FTP
from io import BytesIO

def send_invoice_to_terminal(formatted_invoice, ftp_conf, remote_path_conf, is_no_sale=False, is_operation=False):

    username = ftp_conf['ftp_user']
    password = ftp_conf['ftp_pwd']
    host_name = ftp_conf['ftp_ip']

    try:

        try:
            ftp = FTP(host_name)
            ftp.login(user=username, passwd = password)
        except AttributeError:
            return

        office_dir = remote_path_conf['path']
        office_invoice_dir = office_dir + '/factura'
        office_no_sale_dir = office_dir + '/noventa'

        try:
            ftp.mkd(office_dir)
            ftp.mkd(office_invoice_dir)
            ftp.mkd(office_no_sale_dir)
        except ftplib.error_perm:
            print(remote_path_conf['path'] + ' already exists')

        formatted_invoice = formatted_invoice.encode('utf-8')

        if is_no_sale:
            with BytesIO(formatted_invoice) as f:
                ftp.storbinary('STOR '+office_no_sale_dir + '/' + remote_path_conf['file_name'] + '.txt', f)
                print 'No Sale: \"' + remote_path_conf['file_name'] + '\" sent to ftp server'
        elif is_operation:
            with BytesIO(formatted_invoice) as f:
                ftp.storbinary('STOR ' + office_dir + '/' + remote_path_conf['file_name'] + '.txt', f)
                print 'No Sale: \"' + remote_path_conf['file_name'] + '\" sent to ftp server'
        else:
            with BytesIO(formatted_invoice) as f:
                ftp.storbinary('STOR ' + office_invoice_dir + '/' + remote_path_conf['file_name'] + '.txt', f)
                print 'Invoice: \"' + remote_path_conf['file_name'] + '\" sent to ftp server'

    except Exception as e:
        print('*** Caught exception: %s: %s' % (e.__class__, e))
        traceback.print_exc()


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
        formatted_invoice += item['type'] + '||' + item['quantity'] + '||' + item['description'] + '||' + item[
            'price'] + '||' + item['tax'] + '\n'

    return formatted_invoice


def round_to_2(amount):
    return round(amount * 100) / 100


def split2len(s, n):
    """
    This function splits a String in chunks of N characters
    :param s: String to be splited
    :param n: The frecuency number of characters to be splited
    :return: Array containing chunks of the N splited string
    """
    def _f(s, n):
        while s:
            yield s[:n]
            s = s[n:]
    return list(_f(s, n))
