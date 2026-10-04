"""Run with: python app.py. Open http://127.0.0.1:5000."""
import csv
import io
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for, Response, send_file
from plotly.offline import get_plotlyjs

from db import connect, initialize
from services import add_product, record_sale, restock, import_csv
from analytics import summarize

ROOT = Path(__file__).resolve().parent


def create_app(database=None, demo=True):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
                      DATABASE=str(database or ROOT / 'instance' / 'shop.db'),
                      MAX_CONTENT_LENGTH=2 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    initialize(app.config['DATABASE'], demo)

    @app.template_filter('money')
    def format_money(cents):
        return f'${cents / 100:,.2f}'

    @app.before_request
    def csrf_protection():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        if request.method == 'POST' and not secrets.compare_digest(
                request.form.get('csrf', ''), session['csrf']):
            abort(400, 'Your form expired. Reload the page and try again.')

    @app.context_processor
    def shared():
        return dict(today=date.today().isoformat(), csrf=session.get('csrf'),
                    suggested_reference=f'SALE-{secrets.token_hex(4).upper()}')

    @app.get('/')
    def dashboard():
        try:
            start = date.fromisoformat(request.args.get('start') or (date.today()-timedelta(days=29)).isoformat())
            end = date.fromisoformat(request.args.get('end') or date.today().isoformat())
            if start > end or (end-start).days > 366:
                raise ValueError
        except ValueError:
            flash('Choose a valid date range of up to 367 days, with the start before the end.', 'error')
            return redirect(url_for('dashboard'))
        with connect(app.config['DATABASE']) as db:
            metrics, chart, top, sales = summarize(db, start.isoformat(), end.isoformat())
            products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        low = [p for p in products if p['stock'] <= p['reorder_level']]
        stock_value = sum(p['stock'] * p['cost_cents'] for p in products)
        return render_template('dashboard.html', metrics=metrics, chart=chart, top=top,
                               sales=sales[:8], low=low, product_count=len(products),
                               stock_value=stock_value, start=start, end=end, page='dashboard')

    @app.get('/inventory')
    def inventory():
        query = request.args.get('q', '').strip()
        with connect(app.config['DATABASE']) as db:
            products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        if query:
            products = [p for p in products if query.casefold() in
                        f'{p["sku"]} {p["name"]} {p["category"]}'.casefold()]
        return render_template('inventory.html', products=products, query=query, page='inventory')

    @app.get('/sales')
    def sales_page():
        with connect(app.config['DATABASE']) as db:
            products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
            sales = db.execute('''SELECT s.*, p.name, quantity*s.price_cents AS revenue,
                quantity*(s.price_cents-s.cost_cents) AS profit FROM sales s
                JOIN products p ON p.sku=s.sku ORDER BY sold_on DESC, id DESC LIMIT 200''').fetchall()
        return render_template('sales.html', products=products, sales=sales, page='sales')

    @app.get('/imports')
    def imports_page():
        return render_template('imports.html', page='imports')

    @app.post('/actions/<action>')
    def action(action):
        actions = {'product': (add_product, 'inventory'), 'sale': (record_sale, 'sales_page'),
                   'restock': (restock, 'inventory')}
        if action not in actions and action != 'import':
            abort(404)
        target = 'imports_page' if action == 'import' else actions[action][1]
        try:
            # A failed row rolls back the ENTIRE transaction, including stock changes.
            with connect(app.config['DATABASE']) as db:
                if action == 'import':
                    count = import_csv(db, request.files.get('file'), request.form.get('kind'))
                    message = f'Imported {count} rows successfully.'
                else:
                    actions[action][0](db, request.form)
                    message = {'product':'Product added.', 'sale':'Sale recorded and stock updated.',
                               'restock':'Stock added successfully.'}[action]
            flash(message, 'success')
        except (ValueError, csv.Error) as error:
            flash(f'{error} No changes were saved.', 'error')
        return redirect(url_for(target))

    @app.get('/export/<kind>')
    def export(kind):
        queries = {
            'products': '''SELECT sku, name, category, price_cents, cost_cents, stock, reorder_level FROM products ORDER BY name''',
            'sales': '''SELECT reference, sku, sold_on, quantity, price_cents, cost_cents FROM sales ORDER BY sold_on DESC, id DESC'''}
        headers = {'products':['sku','name','category','price','cost','stock','reorder_level'],
                   'sales':['reference','sku','sold_on','quantity','unit_price','unit_cost']}
        if kind not in queries:
            abort(404)
        with connect(app.config['DATABASE']) as db:
            rows = db.execute(queries[kind]).fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers[kind])
        for row in rows:
            values = []
            for key in row.keys():
                value = row[key]
                if key.endswith('_cents'):
                    value = f'{value / 100:.2f}'
                elif isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                    value = "'" + value  # Keep spreadsheet programs from treating text as a formula.
                values.append(value)
            writer.writerow(values)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': f'attachment; filename={kind}.csv'})

    @app.get('/examples/<kind>')
    def example(kind):
        if kind not in ('products', 'sales'):
            abort(404)
        return send_file(ROOT / 'sample_data' / f'{kind}.csv', as_attachment=True)

    @app.get('/assets/plotly.js')
    def plotly_script():
        return Response(get_plotlyjs(), mimetype='application/javascript',
                        headers={'Cache-Control': 'public, max-age=86400'})

    @app.errorhandler(413)
    def too_large(error):
        return render_template('error.html', message='The upload is too large. Use a CSV smaller than 2 MB.', page='imports'), 413

    return app


if __name__ == '__main__':
    create_app(demo=os.environ.get('SHOP_DEMO', '1') != '0').run(
        host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
