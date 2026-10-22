from test_backend_start import BackendStartTest
from unittest import TestCase

class MenuPreferenceTest(TestCase):
    setUp=BackendStartTest.setUp
    tearDown=BackendStartTest.tearDown
    payload=BackendStartTest.payload
    create_staff=BackendStartTest.create_staff
    staff_login=BackendStartTest.staff_login
    change=BackendStartTest.change
    active_staff=BackendStartTest.active_staff
    def test_personal_choice_and_revision(self):
        _,staff=self.active_staff({},'menu-one')
        _,other=self.active_staff({},'menu-two')
        path='/api/v1/admin/menu-preference'
        self.assertEqual(staff.get(path).json()['variant'],'sidebar')
        revision=0
        for variant in ['compact','sections','sidebar']:
            response=staff.put(path,json={'variant':variant,'expected_revision':revision})
            self.assertEqual(response.status_code,200,response.text)
            revision+=1
            self.assertEqual(response.json()['revision'],revision)
            self.assertEqual(staff.get(path).json()['variant'],variant)
            self.assertEqual(other.get(path).json()['revision'],0)
        self.assertEqual(staff.put(path,json={'variant':'compact','expected_revision':0}).status_code,409)
        self.assertEqual(staff.put(path,json={'variant':'bad','expected_revision':revision}).status_code,422)
        self.assertEqual(staff.put(path,json={'variant':'compact','expected_revision':revision,'user_id':1}).status_code,422)
