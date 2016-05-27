odoo.define('neotec_interface.custom_pos', function (require) {
    "use strict";

    var chrome = require('point_of_sale.chrome');
    var screens = require('point_of_sale.screens');
    var Model = require('web.DataModel');
    var core = require('web.core');
    var _t = core._t;

    chrome.Chrome.include({

        loading_hide: function(){
            this._super();
            console.log(_t("Trabajando Fiscal!"));
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

            var NcfType = new Model("neotec_interface.ncf_type");
            var ResPartner = new Model("res.partner");
            var FiscalPrinter = new Model("neotec_interface.fiscal_printer");

            var client = this.pos.get_client();
            var currentOrder = this.pos.get_order();
            var fiscalPrinterId = this.pos.config.fiscal_printer_id[0];
            var currentOrderItems = currentOrder.get_orderlines();


            FiscalPrinter.query(['invoice_directory','copy_quantity','bd','ep','ia']).filter([['id','=',fiscalPrinterId]]).first().then(function(fiscalPrinter){


                if(client != null)
                {
                    ResPartner.query(['ncf_type_id']).filter([['id','=',client.id]]).first().then(function(partners){
                        var ncf_type = partners[0].ncf_type_id; //0: Id, 1: Name

                        var invoice = {clientName: client.name, ncfTypeId: ncf_type[0]};

                    });
                }
                else
                {
                    var invoice = new neotec_interface_models.Invoice();
                    invoice.office = fiscalPrinter.ep;
                    invoice.box = fiscalPrinter.ia;
                    invoice.copyQty = fiscalPrinter.copy_quantity;
                    invoice.directory = fiscalPrinter.invoice_directory;

//                     TODO Machear metodos de pagos en Odoo POS con metodos pago Impresora

//                    invoice.subTotal = currentOrder.get_total_without_tax();
//                    invoice.total = currentOrder.get_total_with_tax();
//                    invoice.paidTotal = currentOrder.get_total_paid();

                    _.each(currentOrderItems, function(item) {

                        invoice.push(new neotec_interface_models.Item(item ,item.product.display_name, item.price, item.quantity, item.discount));

                    });

                    FiscalPrinter.call("register_invoice", [invoice]).then(function (res) {

                    });



                    console.log(currentOrder);
                    console.log(neotec_interface_models.Invoice);



                    console.log(currentOrderItems);
                }

            });




        }


    });

});