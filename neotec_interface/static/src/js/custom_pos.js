odoo.define('neotec_interface.custom_pos', function (require) {
    "use strict";

    var chrome = require('point_of_sale.chrome');
    var screens = require('point_of_sale.screens');
    var gui = require('point_of_sale.gui');
    var PopupWidget = require('point_of_sale.popups');
    var posModels = require('point_of_sale.models');
    var Model = require('web.DataModel');
    var core = require('web.core');
    var _t = core._t;
    var isChargingLegalTip = null;

    chrome.Chrome.include({

        loading_hide: function(){
            this._super();
            var FiscalPrinter = new Model("neotec_interface.fiscal_printer");
            var fiscalPrinterId = this.pos.config.fiscal_printer_id[0];
            FiscalPrinter.query(['charge_legal_tip']).filter([['id','=',fiscalPrinterId]]).first().then(function(fiscalPrinter){
                isChargingLegalTip = fiscalPrinter.charge_legal_tip;
            });

            $('#credit_note_option').click(doCreditNote);
            $('#delivery_option').click(doDelivery);
        }

    });

    screens.ClientListScreenWidget.include({
        display_client_details: function (visibility,partner,clickpos) {
            var self = this;
            this._super(visibility,partner,clickpos);

            if(visibility === "edit")
            {
                var NcfType = new Model("neotec_interface.ncf_type");
                var ResPartner = new Model("res.partner");
                var client = this.new_client;

                var clientEditContainer = $('section.edit');
                var vatField = clientEditContainer.find('.vat.client-name'); //Rnc
                var nameField = clientEditContainer.find("input[name='name']");
                var ncfTypeSelect = clientEditContainer.find(".client-ncf-type");

                if(client != null)
                {
                    ResPartner.query(['ncf_type_id']).filter([['id','=',client.id]]).limit(1).all().then(function(partners){

                        var ncf_type = partners[0].ncf_type_id; //0: Id, 1: Name

                        NcfType.query().all().then(function (result) {

                            _.each(result, function(ncf){
                                if(ncf.id != 5) //Omitir Nota Credito
                                {
                                    var ncfTypeOption = $("<option>");
                                    ncfTypeOption.val(ncf.id);
                                    ncfTypeOption.text(ncf.display_name);

                                    ncfTypeSelect.append(ncfTypeOption);
                                }
                            });

                            ncfTypeSelect.val(ncf_type[0]);

                        });


                    });
                }
                else
                {
                    NcfType.query().all().then(function (result) {
                        _.each(result, function(ncf){
                            if(ncf.id != 5) // Omitir Nota Credito
                            {

                                var ncfTypeOption = $("<option>");
                                ncfTypeOption.val(ncf.id);
                                ncfTypeOption.text(ncf.display_name);
                                ncfTypeSelect.append(ncfTypeOption);

                            }
                        });
                    });

                    var countriesSelect = clientEditContainer.find('select.client-address-country');
                    countriesSelect.val(62); //Seleccionar RD por defecto.

                }


                vatField.keyup(function(){

                    var rnc = vatField.val();
                    var company = null;

                    if(rnc.length == 9 || rnc.length == 11)
                    {
                        $.get('/find/company?rnc='+rnc).success(function(data){

                            company = JSON.parse(data);

                            if(Object.keys(company).length != 0) // Check if empty
                            {
                                if(company.comercial_name.length != 1)
                                {
                                    nameField.val(company.comercial_name);
                                }
                                else
                                {
                                    nameField.val(company.name);
                                }
                            }

                        });
                    }

                });

            }

        }
    });

    screens.OrderWidget.include({

        renderElement: function(scrollbottom) {
            var self = this;
            this._super(scrollbottom);

            if(isChargingLegalTip != null)
            {
                if(!isChargingLegalTip)
                {
                    $('#legalTip').hide();
                }
            }
        },

        update_summary: function() {
            var self = this;

            if(isChargingLegalTip)
            {
                var order = this.pos.get_order();
                if (!order.get_orderlines().length) {
                    return;
                }

                var total = order ? order.get_total_with_tax() : 0;
                var taxes = order ? order.get_total_tax() : 0; // fixed to get only the tax
                var total_without_tax = order ? order.get_total_without_tax() : 0;
                var legalTip = total_without_tax * 0.10;

                this.el.querySelector('.summary .total > .value').textContent = this.format_currency(total);
                this.el.querySelector('.summary .total .subentry .value').textContent = this.format_currency(taxes);
                this.el.querySelector('#legalTip > span').textContent = this.format_currency(legalTip);
            }
            else
            {
                this._super();
            }

        }
    });

    screens.ReceiptScreenWidget.include({

        show: function(){
            this._super();

            // disables next button until order is send to the server
            $('.receipt-screen .top-content .button').attr('disabled','disabled');
        }

    });

    // Change Order get_total_with_tax return if legal tip is enabled
    posModels.Order.prototype.get_total_with_tax = function() {

        if(isChargingLegalTip)
        {
            var subtotal = this.get_total_without_tax();
            var legalTip = neotec_interface_models.roundTo2(subtotal * 0.10);
            var total_with_tax = subtotal + this.get_total_tax();
            var total = total_with_tax + legalTip;

            return total;
        }

        return this.get_total_without_tax() + this.get_total_tax();
    };

    posModels.PosModel.prototype._save_to_server = function (orders, options) {
        if (!orders || !orders.length) {
            var result = $.Deferred();
            result.resolve([]);
            return result;
        }

        options = options || {};

        var self = this;
        var timeout = typeof options.timeout === 'number' ? options.timeout : 7500 * orders.length;

        // we try to send the order. shadow prevents a spinner if it takes too long. (unless we are sending an invoice,
        // then we want to notify the user that we are waiting on something )
        var posOrderModel = new Model('pos.order');
        return posOrderModel.call('create_from_ui',
            [_.map(orders, function (order) {
                order.to_invoice = options.to_invoice || false;
                return order;
            })],
            undefined,
            {
                shadow: !options.to_invoice,
                timeout: timeout
            }
        ).then(function (server_ids) {

            _.each(orders, function (order) {
                self.db.remove_order(order.id);
            });
            self.set('failed',false);

            validateFiscalInvoice(server_ids[0]);

            return server_ids;
        }).fail(function (error, event){
            if(error.code === 200 ){    // Business Logic Erreor, not a connection problem
                //if warning do not need to display traceback!!
                if (error.data.exception_type == 'warning') {
                    delete error.data.debug;
                }

                // Hide error if already shown before ...
                if ((!self.get('failed') || options.show_error) && !options.to_invoice) {
                    self.gui.show_popup('error-traceback',{
                        'title': error.data.message,
                        'body':  error.data.debug
                    });
                }
                self.set('failed',error)
            }
            // prevent an error popup creation by the rpc failure
            // we want the failure to be silent as we send the orders in the background
            event.preventDefault();
            console.error('Failed to send orders:', orders);
        });
    };

    var validateFiscalInvoice = function (orderId) {

        var pos = window.posmodel;

        var NcfType = new Model("neotec_interface.ncf_type");
        var ResPartner = new Model("res.partner");
        var FiscalPrinter = new Model("neotec_interface.fiscal_printer");

        var client = pos.get_client();
        var currentOrder = pos.get_order();

        var fiscalPrinterId = pos.config.fiscal_printer_id[0];
        var currentOrderItems = currentOrder.get_orderlines();

        FiscalPrinter.query(['invoice_directory','copy_quantity','bd','ep','ia','charge_legal_tip']).filter([['id','=',fiscalPrinterId]]).first().then(function(fiscalPrinter){

            var invoice = new neotec_interface_models.Invoice();
            var ncf = new neotec_interface_models.NCF();

            invoice.fiscalPrinterId = fiscalPrinterId;
            invoice.copyQty = fiscalPrinter.copy_quantity;
            invoice.directory = fiscalPrinter.invoice_directory;
            if(pos.config.receipt_footer)
            {
                invoice.comments = pos.config.receipt_footer.padRight(40, ' ');
            }

            invoice.orderId = orderId;
            invoice.legalTenPercent = (fiscalPrinter.charge_legal_tip) ? '1' : '0';
            invoice.deliveryAddress = currentOrder.delivery_address || null;
            ncf.office = fiscalPrinter.ep;
            ncf.box = fiscalPrinter.ia;
            ncf.bd = fiscalPrinter.bd;

            _.each(currentOrderItems, function(item) {
                var itemType = 1;

                if(item.product.display_name == "Recargo")
                {
                    itemType = 4;
                    itemType = 4;
                }
                else if(item.product.display_name == "Propina")
                {
                    invoice.tip = item.price;
                    return;
                }

                var fiscalItem = new neotec_interface_models.Item(itemType ,item.product.display_name, item.price, item.quantity, item.product.taxes_id[0]);

                invoice.items.push(fiscalItem);


                if(item.discount > 0) // push other item with the original price and set the discuented amount as price to the current item
                {
                    var discountItem = _.clone(fiscalItem);

                    discountItem.type = 3;
                    discountItem.price = neotec_interface_models.roundTo2((discountItem.price * item.quantity) * (item.discount / 100));
                    invoice.items.push(discountItem); // add discount item
                }

            });

            currentOrder.paymentlines.forEach(function(paymentLine){
                invoice.payments.push(new neotec_interface_models.Payment(paymentLine.cashregister.journal.id, paymentLine.amount));
            });

            if(client != null)
            {
                ResPartner.query(['ncf_type_id']).filter([['id','=',client.id]]).first().then(function(partner){
                    var ncfType = partner.ncf_type_id; //0: Id, 1: Name

                    invoice.client = new neotec_interface_models.Client(client.name, client.vat, client.phone);
                    ncf.ncfTypeId = ncfType[0];
                    invoice.ncf = ncf;

                    FiscalPrinter.call("register_invoice", [invoice]).then(function (res) {
                        // Eneables next button after order is send to the server
                        $('.receipt-screen .top-content .button').removeAttr("disabled");
                    });

                });
            }
            else
            {
                //Query Final Consumer NcfTypeId
                NcfType.query(['id']).filter([['ttr','=','2']]).first().then(function(ncfType){

                    ncf.ncfTypeId = ncfType.id;
                    invoice.ncf = ncf;

                    FiscalPrinter.call("register_invoice", [invoice]).then(function (res) {
                        // Eneables next button after order is send to the server
                        $('.receipt-screen .top-content .button').removeAttr("disabled");
                    });

                });
            }

        });


    };


    var doCreditNote = function() {
        window.posmodel.gui.show_popup('creditnote',{
            'title': 'Realizar nota de credito',
            'confirm': function(value){

                if(value != '')
                {
                    window.posmodel.gui.show_popup('creditnotevalidate',{
                        'title': 'Realizar nota de credito',
                        'ncf': value,
                        'confirm': function(creditNote){

                            var FiscalPrinter = new Model("neotec_interface.fiscal_printer");
                            var NcfType = new Model("neotec_interface.ncf_type");
                            var fiscalPrinterId = window.posmodel.config.fiscal_printer_id[0];

                            FiscalPrinter.query(['invoice_directory','copy_quantity','bd','ep','ia','charge_legal_tip']).filter([['id','=',fiscalPrinterId]]).first().then(function(fiscalPrinter){

                                var ncf = new neotec_interface_models.NCF();

                                creditNote.fiscalPrinterId = fiscalPrinterId;
                                creditNote.copyQty = fiscalPrinter.copy_quantity;
                                creditNote.directory = fiscalPrinter.invoice_directory;
                                creditNote.legalTenPercent = (fiscalPrinter.charge_legal_tip) ? '1' : '0';
                                ncf.office = fiscalPrinter.ep;
                                ncf.box = fiscalPrinter.ia;
                                ncf.bd = fiscalPrinter.bd;

                                NcfType.query(['id']).filter([['ttr','=','4']]).first().then(function(ncfType){

                                    ncf.ncfTypeId = ncfType.id;
                                    creditNote.ncf = ncf;

                                    FiscalPrinter.call("register_invoice", [creditNote]).then(function (res) {
                                        //do nothing
                                    });

                                });

                            });


                         }
                    });
                }

             }
        });
    };

    var doDelivery = function(){

        var client = posmodel.get_client();
        var clientAddress = null;
        var order = posmodel.get_order();

        if(client)
        {
           clientAddress = client.street;
        }

        if (order != null)
        {
            if (order.delivery_address != undefined)
            {
                clientAddress = order.delivery_address;
            }

            window.posmodel.gui.show_popup('textarea',{
                'title': 'Dirección de Entrega',
                'value': clientAddress || '',
                'confirm': function(value){
                    order.delivery_address = value;
                }
            });
        }

    };

    var CreditNoteValidateWidget = PopupWidget.extend({
        template: 'CreditNoteValidatePopupWidget',

        this_events: {
            'click .credit-note-validate-body tr': 'give_back_selected_item',
            'change #checkAllItems': 'select_items'
        },

        init: function(parent, args) {
            this._super(parent, args);
            //events
            for(var prop in this.this_events)
            {
                this.events[prop] = this.this_events[prop];
            }
        },

        loadOrder: function(ncf, callback) {
            var self = this;
            var PosOrder = new Model("pos.order");
            var PosOrderLine = new Model("pos.order.line");

            PosOrder.query(['id','pos_reference','legal_tip']).filter([['ncf', '=', ncf]]).first().then(function(order){

                if (order != null)
                {

                    PosOrderLine.query(['id','product_id','price_unit','qty','price_subtotal_incl', 'price_with_tax', 'tax_ids']).filter([['order_id','=', order.id]]).all().then(function(orderLines){

                        var total = 0;

                        _.each(orderLines, function(orderLine){
                            orderLine.product = orderLine.product_id[1];
                            total += orderLine.price_unit * orderLine.qty;
                        });

                        order.orderLines = orderLines;

                        if(isChargingLegalTip)
                        {
                            self.legalTip  = total * 0.10;
                        }

                        if(callback)
                        {
                            callback(order);
                        }

                    });

                }

            });

        },

        select_items: function(e){

            if(e.target.checked)
            {
                this.$('tbody tr').addClass('selected-item');
            }
            else
            {
                this.$('tbody tr').removeClass('selected-item');
            }

            this.updateInfoShowers();
        },

        give_back_selected_item: function(e) {
            var $selectedRow = $(e.target.parentElement);
            $selectedRow.toggleClass('selected-item');

            this.updateInfoShowers();
        },

        updateInfoShowers: function() {

            var selectedItems = this.$('tbody tr.selected-item');
            var infoShowers = this.$('.info-shower');
            var totalSelectedItems = 0;

            _.each(selectedItems, function(e) {
                totalSelectedItems += Number.parseFloat($(e).children().eq(3).text());
            });

            infoShowers[0].textContent = selectedItems.length + '/' + this.totalItemsCount;
            infoShowers[1].textContent = this.format_currency(totalSelectedItems);
            infoShowers[2].textContent = this.format_currency(this.totalOrder);

            var total = totalSelectedItems + ((isChargingLegalTip) ? this.legalTip : 0);
            this.$('input').val(neotec_interface_models.roundTo2(total));
        },

        show: function(options){
            var self = this;
            options = options || {};
            this._super(options);

            this.renderElement();
            this.$('input').focus();
            var $tbody = this.$('tbody');

            this.loadOrder(options.ncf, function(order){

                var totalOrder = 0;

                _.each(order.orderLines, function(orderLine){

                    var row = $('<tr>')
                    .append($('<td>').text(orderLine.product))
                    .append($('<td>').text(orderLine.qty))
                    .append($('<td>').text(self.format_currency(orderLine.price_with_tax)).attr("price", orderLine.price_unit).attr('tax-id', orderLine.tax_ids[0]))
                    .append($('<td>').text(self.format_currency(orderLine.price_subtotal_incl))).attr('orderline-id', orderLine.id);

                    $tbody.append(row);

                    totalOrder += orderLine.price_subtotal_incl;
                });

                self.totalItemsCount = order.orderLines.length;
                self.totalOrder = totalOrder;

                self.$('#checkAllItems').prop('checked', true);
                self.$('tbody tr').addClass('selected-item');
                self.updateInfoShowers();

                if(isChargingLegalTip)
                {
                    self.$('.info-shower')[3].textContent =  self.format_currency(self.legalTip);
                }
            });

        },

        click_confirm: function(){

            var type = '';
            var referenceTtr = this.options.ncf.substr(9,2);

            if(referenceTtr == '02')
                type = '3';
            else if(referenceTtr == '15')
                type = '4';
            else if(referenceTtr == '14')
                type = '8';
            else if(referenceTtr == '01')
                type = '4';

            var creditNote = new neotec_interface_models.Invoice(type);
            creditNote.referenceNcf = this.options.ncf;

            var $selectedItems = this.$('tbody tr.selected-item');

            _.each($selectedItems, function($selectedItem){

                $selectedItem = $($selectedItem);

                var description = $selectedItem.children().eq(0).text();
                var qty = Number.parseFloat($selectedItem.children().eq(1).text());
                var price = Number.parseFloat($selectedItem.children().eq(2).attr('price').split(' ')[0]);
                var taxId = Number.parseInt($selectedItem.children().eq(2).attr('tax-id'));
                var orderLineId = Number.parseInt($selectedItem.attr('orderline-id'));

                var item = new neotec_interface_models.Item(1, description, price, qty, taxId, orderLineId);

                creditNote.items.push(item);
            });


            this.gui.close_popup();
            if( this.options.confirm ){
                this.options.confirm.call(this,creditNote);
            }
        }
    });

    gui.define_popup({name:'creditnotevalidate', widget: CreditNoteValidateWidget});

    var CreditNotePopupWidget = PopupWidget.extend({
        template: 'CreditNotePopupWidget',

        this_events: {
            'click .credit-note-body tr': 'get_ncf_from_seleted_order'
        },

        loadLastOrders: function(callback) {

            var PosOrder = new Model("pos.order");
            var PosOrderLine = new Model("pos.order.line");

            PosOrder.query(['id','pos_reference','ncf','date_order']).order_by(['-date_order']).limit(3).all().then(function(orders){

                self.orders = [];

                _.each(orders, function(order) {

                    PosOrderLine.query(['price_unit','qty']).filter([['order_id','=', order.id]]).all().then(function(orderLines){

                        var orderAmount = 0;

                        _.each(orderLines, function(orderLine){
                            orderAmount += orderLine.price_unit * orderLine.qty;
                        });

                        order.amount = orderAmount;

                        self.orders.push(order);

                        if(callback)
                        {
                            callback(order);
                        }
                    });

                });

            });

        },

        init: function(parent, args) {
            var self = this;
            this._super(parent, args);
            this.options = {};
            //events
            for(var prop in this.this_events)
            {
                this.events[prop] = this.this_events[prop];
            }

        },

        get_ncf_from_seleted_order: function(e) {
            var $selectedRow = $(e.target.parentElement);
            var select_ncf = $selectedRow.find('td:nth-child(2)').text();
            this.$('input').val(select_ncf);
        },

        show: function(options){
            var self = this;
            options = options || {};
            this._super(options);

            this.renderElement();
            this.$('input,textarea').focus();
            var $tbody = this.$('tbody');

            this.loadLastOrders(function(order){
                var row = $('<tr>')
                .append($('<td>').text(order.pos_reference))
                .append($('<td>').text(order.ncf))
                .append($('<td>').text(order.date_order))
                .append($('<td>').text(self.format_currency(order.amount)));
                $tbody.append(row);
            });

        },
        click_confirm: function(){
            var value = this.$('input,textarea').val();
            this.gui.close_popup();
            if( this.options.confirm ){
                this.options.confirm.call(this,value);
            }
        },
    });

    gui.define_popup({name:'creditnote', widget: CreditNotePopupWidget});

});