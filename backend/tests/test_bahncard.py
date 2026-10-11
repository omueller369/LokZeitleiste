import unittest
import test_accounts


class BahnCardTest(unittest.TestCase):
    setUp = test_accounts.AccountsTest.setUp
    tearDown = test_accounts.AccountsTest.tearDown
    active_staff = test_accounts.AccountsTest.active_staff
    create_staff = test_accounts.AccountsTest.create_staff
    payload = test_accounts.AccountsTest.payload
    staff_login = test_accounts.AccountsTest.staff_login
    change = test_accounts.AccountsTest.change

    def profile(self):
        return next(row for row in self.client.get('/api/v1/admin/tf').json() if row['id'] == self.tf)

    def test_dates_updates_legacy_clients_and_no_card(self):
        base = f'/api/v1/admin/tf/{self.tf}'
        profile = self.profile()
        self.assertIsNone(profile['bahncard_valid_until'])
        profile['bahncard_valid_until'] = '2027-12-31'
        self.assertEqual(self.client.put(base, json=profile).status_code, 200)
        self.assertEqual(self.profile()['bahncard_valid_until'], '2027-12-31')
        legacy = self.profile(); legacy.pop('bahncard_valid_until'); legacy['first_name'] = 'Neu'
        self.assertEqual(self.client.put(base, json=legacy).status_code, 200)
        self.assertEqual(self.profile()['bahncard_valid_until'], '2027-12-31')
        legacy['bahncard'] = 100
        self.assertEqual(self.client.put(base, json=legacy).status_code, 200)
        self.assertIsNone(self.profile()['bahncard_valid_until'])
        profile = self.profile(); profile['bahncard_valid_until'] = '2028-02-29'
        self.assertEqual(self.client.put(base, json=profile).status_code, 200)
        self.assertEqual(self.profile()['bahncard_valid_until'], '2028-02-29')
        profile['bahncard_valid_until'] = '2027-02-29'
        self.assertEqual(self.client.put(base, json=profile).status_code, 422)
        self.assertEqual(self.profile()['bahncard_valid_until'], '2028-02-29')
        profile['bahncard'] = 0; profile['bahncard_valid_until'] = '2028-02-29'
        self.assertEqual(self.client.put(base, json=profile).status_code, 200)
        self.assertEqual(self.profile()['bahncard'], 0)
        self.assertIsNone(self.profile()['bahncard_valid_until'])
        profile['bahncard'] = 25
        self.assertEqual(self.client.put(base, json=profile).status_code, 422)

    def test_creation_and_permissions(self):
        profile = self.profile()
        for card in (0, 50, 100):
            data = dict(profile, username=f'card-{card}', personnel_number=f'CARD-{card}',
                        password='initial-secret-12345', bahncard=card, bahncard_valid_until='2027-10-01')
            result = self.client.post('/api/v1/admin/tf', json=data)
            self.assertEqual(result.status_code, 201, result.text)
            saved = next(row for row in self.client.get('/api/v1/admin/tf').json() if row['id'] == result.json()['id'])
            self.assertEqual(saved['bahncard'], card)
            self.assertEqual(saved['bahncard_valid_until'], '2027-10-01' if card else None)
        _, reader = self.active_staff({'employees': 1}, 'card-reader')
        self.assertEqual(reader.put(f'/api/v1/admin/tf/{self.tf}', json=profile).status_code, 403)
        _, planner = self.active_staff({'planning': 1}, 'card-planner')
        self.assertNotIn('bahncard_valid_until', planner.get('/api/v1/admin/tf').json()[0])
