neotec_interface_models = (function(){

    var Client = function(name, rnc, address) {
        this.name = name || ''; // Buyer Social Reason
        this.rnc = rnc || ''; // Buyer RNC
    };

    var NCF = function() {
        this.serie = '';
        this.bd = ''; // Business Division
        this.office = '';
        this.box = '';
        this.ncfTypeId = '';// Ncf type
    };

    var Item = function(type, description, price, quantity, discount) {
        this.type = type || '';
        this.description = description || '';
        this.price = price || '';
        this.quantity = quantity || '';
        this.discount = discount || ''
    };

    var Invoice = function(type, client) { // TODO In case of Credit Note the 'type' will be sent from the frontend
        this.type = type || '';
        this.copyQty = '';
        this.logo = ''
        this.density = ''
        this.ncf = null,
        this.client = client || null;
        this.referenceNcf = ''
        this.discount = '';
        this.charge = '';
        this.tip = '';
        this.comments = '';
        this.legalTenPercent = '';
        this.effectivePayment = '';
        this.checkPayment = '';
        this.creditCardPayment = '';
        this.debitCardPayment = '';
        this.ownCardPayment = '';
        this.voucherPayment = '';
        this.other1Payment = '';
        this.other2Payment = '';
        this.other3Payment = '';
        this.other4Payment = '';
        this.creditNotePayment = '';

        this.items = []
        this.directory = '';
        this.fiscalPrinterId = '';
    };

    var exports = {
        Client: Client,
        Item: Item,
        Invoice: Invoice,
        NCF: NCF
    };

    return exports;

})();