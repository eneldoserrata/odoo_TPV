# -*- coding: utf-8 -*-
from openerp import http
from urllib2 import urlopen

class NeotecInterface(http.Controller):

    @http.route('/find/company', auth='public')
    def index(self, **kw):
        rnc = kw.get("rnc")
        response = urlopen('http://api.marcos.do/rnc/'+rnc)
        return response.read()
