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

from openerp import models, fields, api, SUPERUSER_ID
from openerp.osv import osv, fields as oldFields
from openerp.exceptions import UserError
from openerp.tools.translate import _
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
                if tax_amount == 0:  # no tax applicable for this item
                    tax_amount = 1000

                final_price = item['price'] + (item['price'] * (tax_amount / 100))

                item['tax'] = str(tax_amount).replace('.', '') + '0'
                item['quantity'] = '{:.3f}'.format(item['quantity']).replace('.', '').replace(',','')
                item['price'] = '{:.2f}'.format(final_price).replace('.', '').replace(',','')
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

            invoice['ncfString'] = ncf

            if 'orderId' in invoice:
                current_order = self.env['pos.order'].search([('id', '=', invoice['orderId'])],
                                                             limit=1)
                fiscal_printer = self.env['neotec_interface.fiscal_printer'].browse(invoice['fiscalPrinterId'])

                current_order.ncf = ncf
                current_order.using_legal_tip = fiscal_printer.charge_legal_tip

                if not invoice['client'] is None:

                    if invoice['deliveryAddress']:
                        current_order.is_delivery_order = True
                        current_order.delivery_address = invoice['de    liveryAddress']

                        for c in neoutil.split2len('ENTREGA: ' + invoice['deliveryAddress'], 40):
                            invoice['comments'] += c.ljust(40)

                        if invoice['client']['phone'] != '':
                            for c in neoutil.split2len('TELEFONO: ' + invoice['client']['phone'], 40):
                                invoice['comments'] += c.ljust(40)

            if invoice['referenceNcf'] != '':

                for item in invoice['items']:
                    order_line = self.env['pos.order.line'].browse(item['orderLineId'])
                    order_line.price_unit = 0

            file_name = str(ncf)

            if not os.path.exists(invoice['directory']+'/factura'):
                os.makedirs(invoice['directory']+'/factura')

            f = open(invoice['directory'] + '/factura/' + file_name + '.txt', 'w')
            formatted_invoice = neoutil.format_invoice(invoice)
            f.write(formatted_invoice)
            f.close()

            fiscal_printer = self.env['neotec_interface.fiscal_printer'].browse(invoice['fiscalPrinterId'])

            ftp_conf = {'ftp_user': fiscal_printer.ftp_user, 'ftp_pwd': fiscal_printer.ftp_pwd,
                        'ftp_ip': fiscal_printer.ftp_ip}

            path_parts = fiscal_printer.invoice_directory.split('/')
            last_dir = path_parts[len(path_parts) - 1]
            remote_path_conf = {'path': last_dir, 'file_name': ncf}

            try:
                neoutil.send_invoice_to_terminal(formatted_invoice, ftp_conf, remote_path_conf)
            except SSHException:
                raise ValidationError("No se pudo conectar con la terminar de impresión")

    @api.one
    def do_z_close(self):

        if not os.path.exists(self.invoice_directory):
            os.makedirs(self.invoice_directory)

        file_name = 'cierrez'

        f = open(self.invoice_directory + '/' + file_name + '.txt', 'w')
        f.write('1')
        f.close()

        ftp_conf = {'ftp_user': self.ftp_user, 'ftp_pwd': self.ftp_pwd,
                    'ftp_ip': self.ftp_ip}

        path_parts = self.invoice_directory.split('/')
        last_dir = path_parts[len(path_parts) - 1]
        remote_path_conf = {'path': last_dir, 'file_name': file_name}

        try:
            neoutil.send_invoice_to_terminal('1', ftp_conf, remote_path_conf, is_operation=True)
        except SSHException:
            raise ValidationError("No se pudo conectar con la terminar de impresión")

    @api.one
    def do_x_close(self):
        if not os.path.exists(self.invoice_directory):
            os.makedirs(self.invoice_directory)

        file_name = 'cierrex'

        f = open(self.invoice_directory + '/' + file_name + '.txt', 'w')
        f.write('2')
        f.close()

        ftp_conf = {'ftp_user': self.ftp_user, 'ftp_pwd': self.ftp_pwd,
                    'ftp_ip': self.ftp_ip}

        path_parts = self.invoice_directory.split('/')
        last_dir = path_parts[len(path_parts) - 1]
        remote_path_conf = {'path': last_dir, 'file_name': file_name}

        try:
            neoutil.send_invoice_to_terminal('2', ftp_conf, remote_path_conf, is_operation=True)
        except SSHException:
            raise ValidationError("No se pudo conectar con la terminar de impresión")


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
    _inherit = 'pos.order'

    ncf = fields.Char(string="NCF", readonly=True)
    is_delivery_order = fields.Boolean(string="Orden Domicilio")
    delivery_address = fields.Char(string=u"Dirección")
    using_legal_tip = fields.Boolean(string='Incluir Propina Legal', readonly=True)
    legal_tip = fields.Float(string="Propina legal (10%)", compute='_calculate_legal_tip')

    @api.one
    @api.model
    def _calculate_legal_tip(self):

        total = 0

        if self.using_legal_tip:
            order_lines = self.env['pos.order.line'].search([('order_id', '=', self.ids[0])])
            for order_line in order_lines:
                total += order_line.price_subtotal

        legal_tip = total * 0.10;
        self.amount_total += legal_tip
        self.legal_tip = neoutil.round_to_2(legal_tip)

    @api.v8
    def test_paid(self):
        """A Point of Sale is paid when the sum
        @return: True
        """
        if self.lines and not self.amount_total:
            return True
        amount_untaxed = 0
        for line in self.lines:
            amount_untaxed += line.price_subtotal

        legal_tip = self.amount_paid - self.amount_total

        if (not self.lines) or (not self.statement_ids) or \
                (abs(self.amount_total - (self.amount_paid - legal_tip)) > 0.00001):
            return False

        return True


class CustomLegacyPosOrder(osv.osv):
    """
        Made for overriding the odoo 8 pos.order _amount_all method, so that legal tip is included in total
    """
    _name = 'pos.order'
    _inherit = 'pos.order'

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = super(CustomLegacyPosOrder, self)._amount_all(cr, uid, ids, name, args, context)
        cur_obj = self.pool.get('res.currency')

        for order in self.browse(cr, uid, ids, context=context):
            amount_untaxed = 0
            cur = order.pricelist_id.currency_id

            for line in order.lines:
                amount_untaxed += line.price_subtotal

            cr.execute('SELECT using_legal_tip FROM pos_order WHERE id = ' + str(order.id))
            using_legal_tip = cr.fetchone()[0]

            if using_legal_tip:
                res[order.id]['amount_total'] += cur_obj.round(cr, uid, cur, amount_untaxed * 0.10)

        return res

    def _create_account_move_line(self, cr, uid, ids, session=None, move_id=None, context=None):
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        account_move_obj = self.pool.get('account.move')
        account_tax_obj = self.pool.get('account.tax')
        property_obj = self.pool.get('ir.property')
        cur_obj = self.pool.get('res.currency')

        # session_ids = set(order.session_id for order in self.browse(cr, uid, ids, context=context))

        if session and not all(
                        session.id == order.session_id.id for order in self.browse(cr, uid, ids, context=context)):
            raise UserError(_('Selected orders do not have the same session!'))

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False

        for order in self.browse(cr, uid, ids, context=context):
            if order.account_move:
                continue
            if order.state != 'paid':
                continue

            current_company = order.sale_journal.company_id

            group_tax = {}
            account_def = property_obj.get(cr, uid, 'property_account_receivable_id', 'res.partner', context=context)

            order_account = order.partner_id and \
                            order.partner_id.property_account_receivable_id and \
                            order.partner_id.property_account_receivable_id.id or \
                            account_def and account_def.id

            if move_id is None:
                # Create an entry for the sale
                move_id = self._create_account_move(cr, uid, order.session_id.start_at, order.name,
                                                    order.sale_journal.id, order.company_id.id, context=context)

            move = account_move_obj.browse(cr, SUPERUSER_ID, move_id, context=context)

            def insert_data(data_type, values):
                # if have_to_group_by:

                sale_journal_id = order.sale_journal.id

                # 'quantity': line.qty,
                # 'product_id': line.product_id.id,
                values.update({
                    'ref': order.name,
                    'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(
                        order.partner_id).id or False,
                    'journal_id': sale_journal_id,
                    'date': oldFields.date.context_today(self, cr, uid, context=context),
                    'move_id': move_id,
                })

                if data_type == 'product':
                    key = ('product', values['partner_id'], (values['product_id'], values['name']),
                           values['analytic_account_id'], values['debit'] > 0)
                elif data_type == 'tax':
                    key = ('tax', values['partner_id'], values['tax_line_id'], values['debit'] > 0)
                elif data_type == 'counter_part':
                    key = ('counter_part', values['partner_id'], values['account_id'], values['debit'] > 0)
                elif data_type == 'legal_tip':
                    key = ('legal_tip', values['partner_id'], values['account_id'], values['debit'] > 0)
                else:
                    return

                grouped_data.setdefault(key, [])

                # if not have_to_group_by or (not grouped_data[key]):
                #     grouped_data[key].append(values)
                # else:
                #     pass

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        for line in grouped_data[key]:
                            if line.get('tax_code_id') == values.get('tax_code_id'):
                                current_value = line
                                current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity',
                                                                                                            0.0)
                                current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                                current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                                break
                        else:
                            grouped_data[key].append(values)
                else:
                    grouped_data[key].append(values)

            # because of the weird way the pos order is written, we need to make sure there is at least one line,
            # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            # are set inside the for loop)
            # TOFIX: a deep refactoring of this method (and class!) is needed in order to get rid of this stupid hack
            assert order.lines, _('The POS order must have lines when calling this method')
            # Create an move for each order line

            cur = order.pricelist_id.currency_id
            for line in order.lines:
                amount = line.price_subtotal

                # Search for the income account
                if line.product_id.property_account_income_id.id:
                    income_account = line.product_id.property_account_income_id.id
                elif line.product_id.categ_id.property_account_income_categ_id.id:
                    income_account = line.product_id.categ_id.property_account_income_categ_id.id
                else:
                    raise UserError(_('Please define income ' \
                                      'account for this product: "%s" (id:%d).') \
                                    % (line.product_id.name, line.product_id.id))

                name = line.product_id.name
                if line.notice:
                    # add discount reason in move
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                insert_data('product', {
                    'name': name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(cr, uid, line, context=context),
                    'credit': ((amount > 0) and amount) or 0.0,
                    'debit': ((amount < 0) and -amount) or 0.0,
                    'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(
                        order.partner_id).id or False
                })

                # Create the tax lines
                taxes = []
                for t in line.tax_ids_after_fiscal_position:
                    if t.company_id.id == current_company.id:
                        taxes.append(t.id)
                if not taxes:
                    continue
                for tax in account_tax_obj.browse(cr, uid, taxes, context=context).compute_all(
                                        line.price_unit * (100.0 - line.discount) / 100.0, cur, line.qty)['taxes']:
                    insert_data('tax', {
                        'name': _('Tax') + ' ' + tax['name'],
                        'product_id': line.product_id.id,
                        'quantity': line.qty,
                        'account_id': tax['account_id'] or income_account,
                        'credit': ((tax['amount'] > 0) and tax['amount'] ) or 0.0,
                        'debit': ((tax['amount'] < 0) and -tax['amount']) or 0.0,
                        'tax_line_id': tax['id'],
                        'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(
                            order.partner_id).id or False
                    })

            # counterpart
            insert_data('counter_part', {
                'name': _("Trade Receivables"),  # order.name,
                'account_id': order_account,
                'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
                'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
                'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(
                    order.partner_id).id or False
            })

            # legal_tip if exists, ..... I am pro, I am Diego
            insert_data('legal_tip', {
                'name': _("Propina Legal"),  # order.name,
                'account_id': order_account,
                'credit': (order.using_legal_tip and order.legal_tip) or 0.0,
                'debit': 0.0,
                'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(
                    order.partner_id).id or False
            })

            order.write({'state': 'done', 'account_move': move_id})

        all_lines = []
        for group_key, group_data in grouped_data.iteritems():
            for value in group_data:
                all_lines.append((0, 0, value), )

        if move_id:  # In case no order was changed
            self.pool.get("account.move").write(cr, SUPERUSER_ID, [move_id], {'line_ids': all_lines}, context=context)
            self.pool.get("account.move").post(cr, SUPERUSER_ID, [move_id], context=context)

        return True

    _columns = {
        'amount_tax': oldFields.function(_amount_all, string='Taxes', digits=0, multi='all'),
        'amount_total': oldFields.function(_amount_all, string='Total', digits=0, multi='all'),
        'amount_paid': oldFields.function(_amount_all, string='Paid', states={'draft': [('readonly', False)]},
                                       readonly=True, digits=0, multi='all'),
        'amount_return': oldFields.function(_amount_all, string='Returned', digits=0, multi='all'),
    }


class CustomPosOrderLine(models.Model):
    _name = 'pos.order.line'
    _inherit = 'pos.order.line'

    price_with_tax = fields.Float(string="Precio con Impuestos", compute="_calculate_price_with_tax")

    @api.one
    def _calculate_price_with_tax(self):
        tax_amount = 0
        if (self.tax_ids):
            tax_amount = self.tax_ids.amount

        t = self.price_unit * (tax_amount / 100)
        self.price_with_tax = neoutil.round_to_2(self.price_unit + t)
