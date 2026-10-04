"""Run: python -m unittest discover -s tests -v"""
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from werkzeug.datastructures import FileStorage

from app import create_app
from analytics import summarize
from db import connect
from services import add_product, import_csv, money, record_sale, restock


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'test.db'
        self.app = create_app(self.path, demo=False)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.token = session['csrf']
        with connect(self.path) as db:
            add_product(db, dict(sku='TEST', name='Test mug', category='Home',
                                 price='10.25', cost='4.10', stock='10', reorder_level='3'))

    def tearDown(self):
        self.folder.cleanup()

    def sale(self, **changes):
        data = dict(reference='S-1', sku='TEST', sold_on=date.today().isoformat(), quantity='2')
        data.update(changes)
        return data

    def state(self):
        with connect(self.path) as db:
            return (db.execute('SELECT stock FROM products WHERE sku="TEST"').fetchone()[0],
                    db.execute('SELECT COUNT(*) FROM sales').fetchone()[0])

    def test_all_pages_and_local_chart_asset(self):
        for path in ['/', '/inventory', '/sales', '/imports', '/assets/plotly.js',
                     '/examples/products', '/examples/sales']:
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)

    def test_sale_decrements_stock_and_calculates_gross_profit(self):
        response = self.client.post('/actions/sale', data={**self.sale(), 'csrf':self.token}, follow_redirects=True)
        self.assertIn(b'Sale recorded and stock updated', response.data)
        self.assertEqual(self.state(), (8, 1))
        with connect(self.path) as db:
            metrics, _, top, _ = summarize(db, date.today().isoformat(), date.today().isoformat())
        self.assertEqual(metrics['revenue'], 2050)
        self.assertEqual(metrics['profit'], 1230)
        self.assertEqual(metrics['margin'], 60.0)
        self.assertEqual(top[0]['quantity'], 2)

    def test_historical_cost_does_not_change(self):
        with connect(self.path) as db:
            record_sale(db, self.sale())
            db.execute('UPDATE products SET cost_cents=900, price_cents=1500 WHERE sku="TEST"')
        with connect(self.path) as db:
            row = db.execute('SELECT * FROM sales').fetchone()
            self.assertEqual((row['cost_cents'], row['price_cents']), (410, 1025))

    def test_overselling_rejected(self):
        response = self.client.post('/actions/sale', data={**self.sale(quantity='11'), 'csrf':self.token}, follow_redirects=True)
        self.assertIn(b'Not enough stock', response.data)
        self.assertEqual(self.state(), (10, 0))

    def test_duplicate_sale_rejected(self):
        with connect(self.path) as db:
            record_sale(db, self.sale())
        with self.assertRaisesRegex(ValueError, 'already exists'):
            with connect(self.path) as db:
                record_sale(db, self.sale())
        self.assertEqual(self.state(), (8, 1))

    def test_future_date_and_fractional_quantity_rejected(self):
        for changes in [dict(sold_on=(date.today()+timedelta(days=1)).isoformat()), dict(quantity='1.5'),
                        dict(quantity='0'), dict(unit_price='nan'), dict(sold_on='bad')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                with connect(self.path) as db:
                    record_sale(db, self.sale(**changes))
        self.assertEqual(self.state(), (10, 0))

    def test_csv_failure_rolls_back_all_sales_and_stock(self):
        contents = ('reference,sku,sold_on,quantity,unit_price,unit_cost\n'
                    f'A,TEST,{date.today()},2,10,4\nB,TEST,{date.today()},99,10,4\n')
        response = self.client.post('/actions/import', data={
            'csrf':self.token, 'kind':'sales', 'file':(io.BytesIO(contents.encode()), 'sales.csv')}, follow_redirects=True)
        self.assertIn(b'CSV row 3', response.data)
        self.assertEqual(self.state(), (10, 0))

    def test_csv_success_and_duplicates(self):
        contents = ('reference,sku,sold_on,quantity,unit_price,unit_cost\n'
                    f'A,TEST,{date.today()},2,10,4\nB,TEST,{date.today()},3,,\n')
        with connect(self.path) as db:
            self.assertEqual(import_csv(db, FileStorage(stream=io.BytesIO(contents.encode()),filename='sales.csv'), 'sales'), 2)
        self.assertEqual(self.state(), (5, 2))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            with connect(self.path) as db:
                import_csv(db, FileStorage(stream=io.BytesIO(contents.encode()),filename='sales.csv'), 'sales')
        self.assertEqual(self.state(), (5, 2))

    def test_product_import_is_atomic(self):
        contents = 'sku,name,category,price,cost,stock,reorder_level\nNEW,Tea,Food,5,2,10,2\nTEST,Duplicate,Home,5,2,10,2\n'
        with self.assertRaises(ValueError):
            with connect(self.path) as db:
                import_csv(db, FileStorage(stream=io.BytesIO(contents.encode()),filename='products.csv'), 'products')
        with connect(self.path) as db:
            self.assertIsNone(db.execute('SELECT * FROM products WHERE sku="NEW"').fetchone())

    def test_restock_persists_and_is_audited(self):
        response = self.client.post('/actions/restock',data={'csrf':self.token,'sku':'TEST','quantity':'4'},follow_redirects=True)
        self.assertIn(b'Stock added successfully', response.data)
        self.assertEqual(self.state(), (14, 0))
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT quantity FROM restocks').fetchone()[0], 4)

    def test_filters_empty_range_invalid_range_and_search(self):
        with connect(self.path) as db:
            record_sale(db, self.sale())
            metrics, _, top, sales = summarize(db, '2020-01-01', '2020-01-02')
        self.assertEqual(metrics['revenue'], 0)
        self.assertEqual(top, [])
        self.assertEqual(sales, [])
        self.assertIn(b'Choose a valid date range', self.client.get('/?start=bad',follow_redirects=True).data)
        self.assertIn(b'No products found', self.client.get('/inventory?q=missing').data)

    def test_export_has_two_decimal_money_and_protects_formulas(self):
        with connect(self.path) as db:
            db.execute('UPDATE products SET name=? WHERE sku="TEST"', ('=1+1',))
            record_sale(db, self.sale())
        products = self.client.get('/export/products')
        self.assertIn(b"'=1+1", products.data)
        self.assertIn(b'10.25,4.10', products.data)
        self.assertIn('attachment', products.headers['Content-Disposition'])
        self.assertIn(b'10.25,4.10', self.client.get('/export/sales').data)

    def test_csrf_required(self):
        response = self.client.post('/actions/sale',data=self.sale())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.state(), (10, 0))

    def test_money_validation(self):
        self.assertEqual(money('0.29'), 29)
        for value in ['NaN', 'Infinity', '-1', '0.001', '', '1000001']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_persistence_and_no_reseeding(self):
        with connect(self.path) as db:
            record_sale(db, self.sale())
        create_app(self.path, demo=True)
        self.assertEqual(self.state(), (8, 1))
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)

    def test_demo_shop_renders(self):
        demo = create_app(Path(self.folder.name) / 'demo.db', demo=True).test_client()
        self.assertIn(b'Everyday ceramic mug', demo.get('/').data)
        self.assertEqual(demo.get('/sales').status_code, 200)


if __name__ == '__main__':
    unittest.main()
