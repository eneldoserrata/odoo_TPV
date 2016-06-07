# -*- coding: utf-8 -*-
import json
import os
import urllib2
try:
    from paramiko import SSHException
except ImportError:
    pass
from openerp.exceptions import ValidationError
from ..neoutil import neoutil

from openerp import models, fields, api
from pprint import pprint


class FiscalPrinter(models.Model):
    _name = 'neotec_interface.fiscal_printer'

    name = fields.Char(string="Nombre", required=True)
    invoice_directory = fields.Char(string="Directorio Facturas", required=True)
    copy_quantity = fields.Integer(string="Cantidad Copias", default=0)
    description = fields.Text(string=u"Descripción")
    bd = fields.Integer(string=u"División de Negocios", required=True)
    ep = fields.Integer(string="Sucursal", required=True)  # Punto de Emisión
    ia = fields.Integer(string="Caja", required=True)  # Area de Impresión
    charge_legal_tip = fields.Boolean(string="Cargar Propina Legal", default=False,
                                      help="Carga 10% de propina legal a la cuenta del cliente en el modulo de restaurantes")

    ftp_user = fields.Char(string="Usuario")
    ftp_pwd = fields.Char(string=u"Contraseña")
    ftp_ip = fields.Char(string=u"Dirección Terminar Impresión")

    ncf_range_ids = fields.One2many("neotec_interface.ncf_range", "fiscal_printer_id", "Secuencias de NCF")

    def create(self, cr, uid, vals, context=None):
        invoice_dir = vals.get("invoice_directory", False)

        if not os.path.exists(invoice_dir):
            os.makedirs(invoice_dir)

        return super(FiscalPrinter, self).create(cr, uid, vals, context=context)

    @api.model
    def register_invoice(self, invoice):

        if invoice:

            invoice['density'] = ''
            invoice['logo'] = ''
            invoice['ncf']['bd'] = str(invoice['ncf']['bd']).zfill(2)
            invoice['ncf']['office'] = str(invoice['ncf']['office']).zfill(3)
            invoice['ncf']['box'] = str(invoice['ncf']['box']).zfill(3)
            invoice['copyQty'] = str(invoice['copyQty'])
            invoice['tip'] = str(invoice['tip'])

            if invoice['client'] is None:
                invoice['client'] = {'name': '', 'rnc': ''}

            for item in invoice['items']:
                tax = self.env['account.tax'].browse(item['taxId'])
                # if item doesnt have tax, 18% is default
                tax_amount = 18.0
                if tax:
                    tax_amount = tax.amount
                if tax_amount == 0: # no tax applicable for this item
                    tax_amount = 1000
                item['tax'] = str(tax_amount).replace('.', '') + '0'
                item['price'] = str(item['price'])
                item['quantity'] = item['quantity'].replace('.', '')
                item['type'] = str(item['type'])

            for payment in invoice['payments']:
                payment_type = self.env['neotec_interface.payment_type'].search(
                    [['account_journal_id', '=', payment['id']]])

                payment['amount'] = '{:.2f}'.format(payment['amount']).replace('.', '')

                if payment_type.code == 0:
                    invoice['effectivePayment'] = payment['amount']
                elif payment_type.code == 1:
                    invoice['checkPayment'] = payment['amount']
                elif payment_type.code == 2:
                    invoice['creditCardPayment'] = payment['amount']
                elif payment_type.code == 3:
                    invoice['debitCardPayment'] = payment['amount']
                elif payment_type.code == 4:
                    invoice['ownCardPayment'] = payment['amount']
                elif payment_type.code == 5:
                    invoice['voucherPayment'] = payment['amount']
                elif payment_type.code == 6:
                    invoice['other1Payment'] = payment['amount']
                elif payment_type.code == 7:
                    invoice['other2Payment'] = payment['amount']
                elif payment_type.code == 8:
                    invoice['other3Payment'] = payment['amount']
                elif payment_type.code == 9:
                    invoice['other4Payment'] = payment['amount']
                elif payment_type.code == 10:
                    invoice['creditNotePayment'] = payment['amount']

            ncf_type = self.env['neotec_interface.ncf_type'].browse(invoice['ncf']['ncfTypeId'])

            if ncf_type.ttr == 1:  # Fiscal Credit
                invoice['type'] = '2'
            elif ncf_type.ttr == 15:  # Governmental
                invoice['type'] = '2'
            elif ncf_type.ttr == 14:  # Special Regime
                invoice['type'] = '6'
            elif ncf_type.ttr == 4:  # TODO In case of Credit Note the 'type' will be sent from the frontend
                pass
            else:  # Final Consumer ttr = 2
                invoice['type'] = '1'

            sequence = ''

            ncf_range = self.env['neotec_interface.ncf_range'].search(
                [('fiscal_printer_id', '=', invoice['fiscalPrinterId']),
                 ('ncf_type_id', '=', invoice['ncf']['ncfTypeId'])])

            if ncf_range.remaining_quantity <= 0:
                raise ValidationError("No le quedan NCFs \"" + ncf_type.name + "\", realize su solicitud")

            next_range = ncf_range.used_quantity + 1
            ncf_range.used_quantity = next_range
            sequence = str(next_range).zfill(8)

            ncf = ncf_type.serie + invoice['ncf']['bd'] + invoice['ncf']['office'] + invoice['ncf']['box'] + str(
                ncf_type.ttr).zfill(2) + sequence

            pprint(invoice['orderReference'])
            current_order = self.env['pos.order'].search([('pos_reference', '=', invoice['orderReference'])], limit=1)
            current_order.ncf = ncf

            invoice['ncfString'] = ncf

            file_name = str(ncf)

            if not os.path.exists(invoice['directory']):
                os.mkdir(invoice['directory'])

            f = open(invoice['directory'] + '/' + file_name, 'w')
            formatted_invoice = neoutil.format_invoice(invoice)
            f.write(formatted_invoice)
            f.close()

            fiscal_printer = self.env['neotec_interface.fiscal_printer'].browse(invoice['fiscalPrinterId'])

            ftp_conf = {'ftp_user': fiscal_printer.ftp_user, 'ftp_pwd': fiscal_printer.ftp_pwd,
                        'ftp_ip': fiscal_printer.ftp_ip}

            path_parts = fiscal_printer.invoice_directory.split('/')
            last_dir = path_parts[len(path_parts) - 1]
            remote_path_conf = {'path': last_dir, 'file_name': ncf}

            # try:
            # neoutil.send_invoice_to_terminal(formatted_invoice, ftp_conf, remote_path_conf)
            # except SSHException:
            #     raise ValidationError("No se pudo conectar con la terminar de impresión")


class NCFRange(models.Model):
    _name = 'neotec_interface.ncf_range'

    total_quantity = fields.Integer(string="Cantidad", required=True)
    used_quantity = fields.Integer(string="Usados", required=True)
    remaining_quantity = fields.Integer(compute="_compute_remaining", string="Restantes")
    ncf_type_id = fields.Many2one("neotec_interface.ncf_type", string="Tipo NCF", required=True)
    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer", string="Impresora")

    @api.one
    @api.depends('used_quantity', 'total_quantity')
    def _compute_remaining(self):
        self.remaining_quantity = self.total_quantity - self.used_quantity


class NCF(models.Model):
    _name = 'neotec_interface.ncf'

    name = fields.Char(string="Sequencia")
    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer", string="Impresora")
    ncf_type_id = fields.Many2one("neotec_interface.ncf_type")


class NCFType(models.Model):
    _name = 'neotec_interface.ncf_type'
    name = fields.Char(string="Nombre")
    serie = fields.Char(string="Serie")
    ttr = fields.Integer(string="Tipo de Comprobante Fiscal")


class POSConfigWithFiscalPrinter(models.Model):
    _name = 'pos.config'
    _inherit = 'pos.config'

    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer", "Impresora Fiscal")


class CustomPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    ncf_type_id = fields.Many2one('neotec_interface.ncf_type', 'Tipo Comprobante')

    @api.onchange('vat')
    def get_rnc(self):
        try:
            if (self.vat):
                res = urllib2.urlopen('http://api.marcos.do/rnc/' + self.vat)
                if res.code == 200:
                    company = json.load(res)
                    if 'comercial_name' in company:
                        if (len(company['comercial_name']) != 1):
                            self.name = company['comercial_name']
                        else:
                            self.name = company['name']
        except urllib2.URLError as e:
            if hasattr(e, 'reason'):
                print 'We failed to reach a server.'
                print 'Reason: ', e.reason
            elif hasattr(e, 'code'):
                print 'The server couldn\'t fulfill the request.'
                print 'Error code: ', e.code
            return " "


class PaymentType(models.Model):
    _name = 'neotec_interface.payment_type'
    name = fields.Char(string=u"Título", required=True)
    account_journal_id = fields.Many2one("account.journal", string="Tipo de Pago")
    code = fields.Integer(string=u"Código", readonly=True)


class CustomPosOrder(models.Model):
    _name = 'pos.order'
    _inherit = 'pos.order'

    legal_tip = fields.Monetary(string="Propina legal (10%)"),
    ncf = fields.Char(string="NCF")
