"""
This module provides helpers in order to manage fiscal invoices
"""
import os
import socket
import traceback
try:
    import paramiko
except ImportError:
    pass


def send_invoice_to_terminal(formatted_invoice, ftp_conf, remote_path_conf, is_no_sale=False):

    # Paramiko client configuration
    use_gss_api = False  # enable GSS-API / SSPI authentication
    dog_ss_api_key_exchange = False
    port = 22
    username = ftp_conf['ftp_user']
    password = ftp_conf['ftp_pwd']
    host_name = ftp_conf['ftp_ip']

    # get host key, if we know one
    host_key_type = None
    host_key = None

    try:
        host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    except IOError:
        try:
            # try ~/ssh/ too, because windows can't have a folder named ~/.ssh/
            host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
        except IOError:
            print('*** Unable to open host keys file')
            host_keys = {}

    if host_name in host_keys:
        host_key_type = host_keys[host_name].keys()[0]
        host_key = host_keys[host_name][host_key_type]
        print('Using host key of type %s' % host_key_type)


    try:
        t = paramiko.Transport((host_name, port))
        t.connect(host_key, username, password, gss_host=socket.getfqdn(host_name),
                  gss_auth=use_gss_api, gss_kex=dog_ss_api_key_exchange)
        sftp = paramiko.SFTPClient.from_transport(t)

        office_dir = remote_path_conf['path']
        office_invoice_dir = office_dir+'/factura'
        office_no_sale_dir = office_dir+'/noventa'

        try:
            sftp.mkdir(office_dir)
            sftp.mkdir(office_invoice_dir)
            sftp.mkdir(office_no_sale_dir)
        except IOError:
            print(remote_path_conf['path'] + ' already exists')

        if is_no_sale:
            with sftp.open(office_no_sale_dir+'/' + remote_path_conf['file_name']+'.txt', 'w') as f:
                f.write(formatted_invoice)
                print 'No Sale: \"' + remote_path_conf['file_name'] + '\" sent to ftp server'
        else:
            with sftp.open(office_invoice_dir + '/' + remote_path_conf['file_name']+'.txt', 'w') as f:
                f.write(formatted_invoice)
                print 'Invoice: \"' + remote_path_conf['file_name'] + '\" sent to ftp server'

        t.close()
    except Exception as e:
        print('*** Caught exception: %s: %s' % (e.__class__, e))
        traceback.print_exc()
        try:
            t.close()
        except:
            pass


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


def round_to_2(amount):
    return round(amount * 100) / 100