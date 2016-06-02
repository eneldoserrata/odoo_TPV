# -*- coding: utf-8 -*-
import json
import os
import urllib2
from datetime import datetime

from openerp.exceptions import ValidationError
from ..neoutil import neoutil
from pprint import pprint
import pytz

from openerp import models, fields, api


class FiscalPrinter(models.Model):
    _name = 'neotec_interface.fiscal_printer'

    name = fields.Char(string="Nombre", required=True)
    invoice_directory = fields.Char(string="Directorio Facturas", required=True)
    copy_quantity = fields.Integer(string="Cantidad Copias", default=0)
    description = fields.Text(string=u"Descripción")
    bd = fields.Integer(string=u"División de Negocios", required=True)
    ep = fields.Integer(string="Sucursal", required=True) #Punto de Emisión
    ia = fields.Integer(string="Caja", required=True) #Area de Impresión
    charge_legal_tip = fields.Boolean(string="Cargar Propina Legal", default=False, help="Carga 10% de propina legal a la cuenta del cliente en el modulo de restaurantes")

    ncf_range_ids = fields.One2many("neotec_interface.ncf_range","fiscal_printer_id","Secuencias de NCF")

    def create(self,cr,uid, vals, context=None):
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
                item['tax'] = str(tax_amount).replace('.', '') + '0'
                item['price'] = str(item['price'])
                item['quantity'] = str(item['quantity'])
                item['type'] = str(item['type'])

            ncf_type = self.env['neotec_interface.ncf_type'].browse(invoice['ncf']['ncfTypeId'])

            if ncf_type.ttr == 1: # Fiscal Credit
                invoice['type'] = '2'
            elif ncf_type.ttr == 15: # Governmental
                invoice['type'] = '2'
            elif ncf_type.ttr == 14: # Special Regime
                invoice['type'] = '6'
            elif ncf_type.ttr == 4: #TODO In case of Credit Note the 'type' will be sent from the frontend
                pass
            else: # Final Consumer ttr = 2
                invoice['type'] = '1'

            sequence = ''

            ncf_range = self.env['neotec_interface.ncf_range'].search([('fiscal_printer_id', '=', invoice['fiscalPrinterId']),
                                                           ('ncf_type_id', '=', invoice['ncf']['ncfTypeId'])])

            if ncf_range.remaining_quantity <= 0:
                raise ValidationError("No le quedan NCFs \""+ncf_type.name+"\", realize su solicitud")

            next_range = ncf_range.used_quantity + 1
            ncf_range.used_quantity = next_range
            sequence = str(next_range).zfill(8)

            ncf = ncf_type.serie + invoice['ncf']['bd'] + invoice['ncf']['office'] + invoice['ncf']['box'] + invoice['type'].zfill(2) + sequence

            invoice['ncfString'] = ncf

            pprint(invoice)

            now = datetime.now() # TODO Fix timezone .astimezone(pytz.timezone('America/Santo_Domingo'))
            file_name = str(now)
            file_name = file_name[:file_name.index('.')]

            if not os.path.exists(invoice['directory']):
                os.mkdir(invoice['directory'])

            f = open(invoice['directory'] +'/'+file_name, 'w')
            formatted_invoice = neoutil.format_invoice(invoice)
            f.write(formatted_invoice)
            f.close()


class NCFRange(models.Model):
    _name = 'neotec_interface.ncf_range'

    total_quantity = fields.Integer(string="Cantidad", required=True)
    used_quantity = fields.Integer(string="Usados", required=True)
    remaining_quantity = fields.Integer(compute="_compute_remaining", string="Restantes")
    ncf_type_id = fields.Many2one("neotec_interface.ncf_type",string="Tipo NCF", required=True)
    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer", string="Impresora")

    @api.one
    @api.depends('used_quantity', 'total_quantity')
    def _compute_remaining(self):
        self.remaining_quantity = self.total_quantity - self.used_quantity


class NCF(models.Model):
    _name = 'neotec_interface.ncf'

    name = fields.Char(string="Sequencia")
    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer",string="Impresora")
    ncf_type_id = fields.Many2one("neotec_interface.ncf_type")


class NCFType(models.Model):
    _name = 'neotec_interface.ncf_type'
    name = fields.Char(string="Nombre")
    serie = fields.Char(string="Serie")
    ttr = fields.Integer(string="Tipo de Comprobante Fiscal")


class POSConfigWithFiscalPrinter(models.Model):
    _name = 'pos.config'
    _inherit = 'pos.config'

    fiscal_printer_id = fields.Many2one("neotec_interface.fiscal_printer","Impresora Fiscal")


class CustomPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    ncf_type_id = fields.Many2one('neotec_interface.ncf_type', 'Tipo Comprobante')

    @api.onchange('vat')
    def get_rnc(self):
        try:
            if(self.vat):
                res = urllib2.urlopen('http://api.marcos.do/rnc/'+self.vat)
                if res.code == 200:
					company = json.load(res)
					if 'comercial_name' in company:
						if(len(company['comercial_name']) != 1):
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
    account_journal_id  = fields.Many2one("account.journal",string="Tipo de Pago")
    code = fields.Integer(string=u"Código", readonly=True)