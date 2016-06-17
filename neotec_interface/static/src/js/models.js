// Util prototypes
String.prototype.padRight = function(l,c) {return this+Array(l-this.length+1).join(c||" ")};

neotec_interface_models = (function(){

    var roundTo2 = function(n) {
        return Math.round(n * 100) / 100;
    };

    var Payment = function(id, amount) {
        this.id = id || '';
        this.amount = amount || '';
    };

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

    var Item = function(type, description, price, quantity, taxId, orderLineId) {
        this.type = type || '';
        this.quantity = quantity || '';
        this.description = description || '';
        this.price = price || '';
        this.tax = '';
        this.taxId = taxId || '';
        this.orderLineId = orderLineId || '';
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

        this.items = [];
        this.payments = [];
        this.directory = '';
        this.fiscalPrinterId = '';
    };

    var exports = {
        Client: Client,
        Item: Item,
        Invoice: Invoice,
        NCF: NCF,
        Payment: Payment,
        roundTo2: roundTo2
    };

    return exports;

})();