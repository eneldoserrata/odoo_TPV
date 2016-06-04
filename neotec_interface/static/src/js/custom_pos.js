odoo.define('neotec_interface.custom_pos', function (require) {
    "use strict";

    var chrome = require('point_of_sale.chrome');
    var screens = require('point_of_sale.screens');
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
                                if(!(ncf.id == 1 || ncf.id == 5)) // Omitir Consumidor Final, Nota Credito
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
                            if(!(ncf.id == 1 || ncf.id == 5)) // Omitir Consumidor Final, Nota Credito
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

    screens.PaymentScreenWidget.include({

        validate_order: function(force_validation){
            var self = this;
            this._super(force_validation);

            var order = this.pos.get_order();

            if(!order.is_paid())
            {
                return;
            }

            var NcfType = new Model("neotec_interface.ncf_type");
            var ResPartner = new Model("res.partner");
            var FiscalPrinter = new Model("neotec_interface.fiscal_printer");

            var client = this.pos.get_client();
            var currentOrder = this.pos.get_order();
            var fiscalPrinterId = this.pos.config.fiscal_printer_id[0];
            var currentOrderItems = currentOrder.get_orderlines();


            FiscalPrinter.query(['invoice_directory','copy_quantity','bd','ep','ia','charge_legal_tip']).filter([['id','=',fiscalPrinterId]]).first().then(function(fiscalPrinter){

                var invoice = new neotec_interface_models.Invoice();
                var ncf = new neotec_interface_models.NCF();

                invoice.fiscalPrinterId = fiscalPrinterId;
                invoice.copyQty = fiscalPrinter.copy_quantity;
                invoice.directory = fiscalPrinter.invoice_directory;
                invoice.comments = self.pos.config.receipt_footer;
                invoice.legalTenPercent = (fiscalPrinter.charge_legal_tip) ? '1' : '0';
                ncf.office = fiscalPrinter.ep;
                ncf.box = fiscalPrinter.ia;
                ncf.bd = fiscalPrinter.bd;


                _.each(currentOrderItems, function(item) {
                    var itemType = 1;

                    if(item.product.display_name == "Recargo")
                    {
                        itemType = 4;
                    }
                    else if(item.product.display_name == "Propina")
                    {
                        invoice.tip = item.price;
                        return;
                    }

                    var fiscalItem = new neotec_interface_models.Item(itemType ,item.product.display_name, item.price, item.quantityStr, item.product.taxes_id[0]);

                    invoice.items.push(fiscalItem);


                    if(item.discount > 0) // push other item with the original price and set the discuented amount as price to the current item
                    {
                        var discountItem = _.clone(fiscalItem);

                        discountItem.type = 3;
                        discountItem.price = neotec_interface_models.roundTo2(discountItem.price * item.discount / 100);
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

                        invoice.client = new neotec_interface_models.Client(client.name, client.vat);
                        ncf.ncfTypeId = ncfType[0];
                        invoice.ncf = ncf;

                        FiscalPrinter.call("register_invoice", [invoice]).then(function (res) {
                            //do nothing
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
                            //do nothing
                        });

                    });
                }

            });

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

});