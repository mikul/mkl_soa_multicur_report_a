from odoo import models, fields, api
from datetime import datetime

class MulticurCustomerStatementWizard(models.TransientModel):
    _name = 'multicur.customer.statement.wizard'
    _description = 'Multiple Currency Customer Statement of Account Wizard'

    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    def _get_soa_a_report_base_filename(self):
        """Generates a filename in the format 'Lastname_Fullname_soa_YYYY-MM-DD'."""
        self.ensure_one()
        today_date = datetime.today().strftime('%Y-%m-%d')
        full_name = self.partner_id.name or ''
        filename = f"{full_name}_SOA_{today_date}"
        return filename

    def print_customer_statement(self):

        #currency
        currency_objs = self.env['res.currency'].search([
            ('active', '=', True)
        ])

        opening_bal_dict_list = []
        ending_bal_dict_list = []

        for currency in currency_objs:
            opening_bal_dict_list.append({
                    'opening_balance': 0,
                    'currency_id':currency.id,
                    'currency':currency.name,
                }
            )
            ending_bal_dict_list.append({
                    'ending_balance': 0,
                    'currency_id':currency.id,
                    'currency':currency.name,
                }
            )

        # Initialize the list for payment details
        sales_details = [] 
        opening_details = []

        #invoice
        inv_objs = self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'posted'),
            ('invoice_date', '<', self.date_from),  # Invoices before the start date
            ('move_type', '=', 'out_invoice'),
        ])


        # Initialize the list for payment details
        sales_details = [] 

        # Initialize opening balance variables
        opening_balance_invoices = 0.0
        opening_balance_payments = 0.0

        # Calculate opening balance using invoices before start_date
        for inv in inv_objs:
            for balance in opening_bal_dict_list:
                if balance['currency_id'] == inv.currency_id.id:
                    balance['opening_balance'] += inv.amount_total

        for balance in opening_bal_dict_list:
            if balance['opening_balance'] > 0 or self.env.company[0].currency_id.name == balance['currency']:
                data = {
                        'id': 0,
                        'date': self.date_from.strftime('%m/%d/%Y'),  
                        'transaction': '***Opening Balance***',
                        'name': '',
                        'details': '',
                        'amount': 0.0,
                        'balance': balance['opening_balance'],
                        'currency': balance['currency'],
                    }  
                opening_details.append(data)

        #Transaction Summary
        inv_objs = self.env['account.move'].search([
            ('partner_id','=',self.partner_id.id),
            ('state','=','posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('move_type', '=', 'out_invoice')])

        for inv in inv_objs:
            sale_order_name = ''
            if hasattr(self.env['account.move.line'], 'sale_line_ids'):
                sale_lines = inv.invoice_line_ids.mapped('sale_line_ids')
                if sale_lines:
                    sale_orders = sale_lines.mapped('order_id')
                    if sale_orders:
                        # If multiple sale orders are found, concatenate their names
                        sale_order_name = ', '.join(sale_orders.mapped('name'))

                details = f'{inv.name}: Invoice for {inv.ref}' if inv.ref  else (f'{inv.name}: Invoice for {sale_order_name}' if sale_order_name else inv.name)
            else:
                details = f'{inv.name}: {inv.ref}' if inv.ref  else f'{inv.name}'
            data = {
                'id': inv.id,
                'date': inv.invoice_date.strftime('%m/%d/%Y') if inv.invoice_date else '',  
                'transaction': 'Invoice',
                'name': inv.name,         
                'details': details,             # Sales details
                'amount': inv.amount_total,                
                'balance': inv.amount_residual,             
                'currency': inv.currency_id.name,
            }
            sales_details.append(data)

        # Output the list of dictionaries
        transactions = sales_details
        transactions = sorted(
            transactions,
            key=lambda x: (datetime.strptime(x['date'], '%m/%d/%Y'),x['transaction'], x['id'])
        )

        total_balances = []

        all_transaction = sales_details + opening_details

        for trans in all_transaction:
            for balance in ending_bal_dict_list:
                if balance['currency'] == trans['currency']:
                    balance['ending_balance'] += trans['balance']

        ending_bal_dict_list = list(filter(lambda balance: balance['ending_balance'] != 0, ending_bal_dict_list))


        running_balance = 0.0
        total_amount = 0.0
        total_payment = 0.0
        opening_bal = 0.0
         

         
        # Prepare data for the report
        data = {
            'form': {
                'partner_id': self.partner_id,
                'start_date': self.date_from.strftime('%m/%d/%Y'),  # Example value
                'end_date': self.date_to.strftime('%m/%d/%Y'),  # Example value
                'opening_balance': opening_bal,  # Example value
                'invoiced_amount': total_amount,  # Example value
                'amount_paid': total_payment,  # Example value
                'balance_due': total_amount - total_payment,  # Example value
                'opening_details': opening_details,
                'transactions': transactions,
                'total_balances': ending_bal_dict_list,
            }
        }
        # Pass data in the context
        return self.env.ref('mkl_soa_multicur_report_a.action_variable_month_multicur_customer_statement_report').with_context(data=data).report_action(self)
