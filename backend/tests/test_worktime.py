import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

import test_api
from lokzeitleiste.models import WorkTimeChange
from lokzeitleiste.worktime.service import process_change
from lokzeitleiste.reports import worker


class WorkTimeTest(unittest.TestCase):
    create_tf = test_api.ApiFlowTest.create_tf

    def setUp(self):
        test_api.ApiFlowTest.setUp(self)
        self.change_engine = patch('lokzeitleiste.worktime.service.engine', return_value=self.engine)
        self.change_send = patch('lokzeitleiste.worktime.service.send_time_change')
        self.change_engine.start()
        self.mail = self.change_send.start()
        self.client.post('/api/v1/admin/login', json={'username':'admin','password':'admin-secret-12345'})
        self.tf = self.create_tf('tf-edit', 'P-EDIT').json()['id']
        token = self.client.post('/api/v1/tf/login', json={'username':'tf-edit','password':'tf-secret-12345'}).json()['access_token']
        self.headers = {'Authorization':'Bearer ' + token}
        self.base = f'/api/v1/admin/tf/{self.tf}/worktime'

    def tearDown(self):
        self.change_send.stop()
        self.change_engine.stop()
        test_api.ApiFlowTest.tearDown(self)

    def upload(self, day='2026-09-21', start='08:00', end='16:00', pause=0, guest=0, kind='Zugfahrt'):
        item = dict(client_id=str(uuid4()),kind=kind,date=day,start=start,end=end,pause=pause,guest=guest)
        year, month = map(int, day.split('-')[:2])
        result = self.client.post(f'/api/v1/me/months/{year}/{month}/entries', json={'entries':[item]}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        return item

    def overview(self, year=2026, month=9):
        result = self.client.get(f'{self.base}/months/{year}/{month}')
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def edit(self, entry, start, end, reason='Zeit laut Dienstnachweis korrigiert'):
        return self.client.patch(f"{self.base}/entries/{entry['id']}", json=dict(
            start=start,end=end,expected_updated_at=entry['updated_at'],reason=reason))

    def test_edit_recalculates_day_week_month_and_notifies_once(self):
        item = self.upload(pause=30,guest=60)
        old = self.overview()['entries'][0]
        result = self.edit(old, '07:00', '17:00')
        self.assertEqual(result.status_code, 200, result.text)
        data = self.overview()
        self.assertEqual(data['days'][0]['work'], 570)
        self.assertEqual(data['days'][0]['credited'], 570)
        self.assertEqual(data['weeks'][3]['totals']['work'], 570)
        self.assertEqual(data['month']['totals']['credited'], 570)
        self.assertEqual(self.mail.call_count, 1)
        sent = self.mail.call_args.kwargs
        self.assertEqual(sent['recipient'], 'tf-edit@example.com')
        self.assertIn('Arbeitsbeginn: 08:00 → 07:00', sent['body'])
        self.assertIn('Arbeitsende: 16:00 → 17:00', sent['body'])
        self.assertIn('Arbeitszeit 7:30 h → 9:30 h', sent['body'])
        self.assertIn('KW 39/2026', sent['body'])
        self.assertEqual(self.edit(old,'06:00','17:00').status_code, 409)
        current = data['entries'][0]
        self.assertFalse(self.edit(current,'07:00','17:00').json()['changed'])
        self.assertEqual(self.mail.call_count, 1)
        # Ein alter Offline-Upload darf weder die Korrektur noch andere Paketzeilen überschreiben.
        self.assertEqual(self.client.post('/api/v1/me/months/2026/9/entries',json={'entries':[item]},headers=self.headers).status_code,409)
        self.assertEqual(self.overview()['entries'][0]['start'], '07:00')
        current_item = dict(item,start='07:00',end='17:00')
        self.assertEqual(self.client.post('/api/v1/me/months/2026/9/entries',json={'entries':[current_item]},headers=self.headers).status_code,200)
        history = self.client.get(self.base + '/changes/history').json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['email_status'], 'sent')

    def test_midnight_recalculates_adjacent_month_and_full_week(self):
        self.upload(day='2026-09-30',start='22:00',end='06:00')
        old = self.overview()['entries'][0]
        self.assertEqual(self.edit(old,'21:00','07:00').status_code,200)
        self.assertEqual(self.overview()['days'][0]['work'],180)
        october = self.overview(month=10)
        self.assertEqual(october['days'][0]['work'],420)
        self.assertEqual(october['weeks'][0]['totals']['work'],600)
        self.assertEqual(october['month']['totals']['work_without_guest'],420)
        self.assertIn('Monat 10/2026 · Arbeitszeit: 6:00 h → 7:00 h',self.mail.call_args.kwargs['body'])

    def test_week_and_year_boundary(self):
        self.upload(day='2026-12-31',start='22:00',end='06:00')
        old=self.overview(month=12)['entries'][0]
        self.assertEqual(self.edit(old,'21:00','07:00').status_code,200)
        january=self.overview(year=2027,month=1)
        self.assertEqual(january['weeks'][0]['iso_year'],2026)
        self.assertEqual(january['weeks'][0]['week'],53)
        self.assertEqual(january['weeks'][0]['totals']['work'],600)
        self.assertEqual(january['days'][0]['work'],420)

    def test_sunday_shift_recalculates_both_calendar_weeks(self):
        self.upload(day='2026-09-27',start='22:00',end='06:00')
        old=self.overview()['entries'][0]
        self.assertEqual(self.edit(old,'21:00','07:00').status_code,200)
        weeks={w['week']:w['totals']['work'] for w in self.overview()['weeks']}
        self.assertEqual(weeks[39],180)
        self.assertEqual(weeks[40],420)
        self.assertIn('KW 39/2026',self.mail.call_args.kwargs['body'])
        self.assertIn('KW 40/2026',self.mail.call_args.kwargs['body'])

    def test_validation_authorization_and_overlap_preserve_original(self):
        self.upload(pause=60,guest=120)
        old=self.overview()['entries'][0]
        for start,end in [('08:00:01','16:00'),('08:00','09:00')]:
            self.assertEqual(self.edit(old,start,end).status_code,422)
        self.assertEqual(self.edit(old,'07:00','16:00','   ').status_code,422)
        with patch('lokzeitleiste.main.PUBLIC_ORIGIN','https://testserver'):
            self.assertEqual(self.edit(old,'07:00','16:00').status_code,403)
        other=self.create_tf('tf-other','P-OTHER').json()['id']
        self.assertEqual(self.client.patch(f'/api/v1/admin/tf/{other}/worktime/entries/{old["id"]}',
            json=dict(start='07:00',end='16:00',expected_updated_at=old['updated_at'],reason='Grund')).status_code,404)
        self.upload(start='17:00',end='19:00')
        self.assertEqual(self.edit(old,'08:00','18:00').status_code,409)
        self.assertEqual(self.overview()['entries'][0]['start'],'08:00')
        self.assertEqual(self.mail.call_count,0)
        self.client.post('/api/v1/admin/logout')
        self.assertEqual(self.edit(old,'07:00','16:00').status_code,401)

    def test_missing_smtp_and_failed_delivery_retry(self):
        self.upload()
        old=self.overview()['entries'][0]
        with patch.dict('os.environ',{'SMTP_HOST':''}):
            self.assertEqual(self.edit(old,'07:00','17:00').status_code,503)
        self.assertEqual(self.overview()['entries'][0]['start'],'08:00')
        self.mail.side_effect=OSError('SMTP nicht erreichbar')
        result=self.edit(old,'07:00','17:00')
        self.assertEqual(result.status_code,200,result.text)
        change_id=result.json()['change_id']
        self.assertEqual(self.overview()['entries'][0]['start'],'07:00')
        with Session(self.engine) as db:
            record=db.get(WorkTimeChange,change_id)
            self.assertEqual(record.status,'failed')
            snapshot=record.email_body
        self.mail.side_effect=None
        with patch('lokzeitleiste.reports.worker.engine',return_value=self.engine):
            worker.poll_once()
        self.assertEqual(self.mail.call_args.kwargs['body'],snapshot)
        process_change(change_id)
        self.assertEqual(self.mail.call_count,2)
        history=self.client.get(self.base+'/changes/history').json()
        self.assertEqual(history[0]['email_status'],'sent')
        self.assertEqual(history[0]['attempts'],2)

    def test_manual_retry_keeps_original_notification(self):
        self.upload()
        old=self.overview()['entries'][0]
        self.mail.side_effect=OSError('SMTP nicht erreichbar')
        change_id=self.edit(old,'07:00','17:00').json()['change_id']
        with Session(self.engine) as db:
            record=db.get(WorkTimeChange,change_id)
            record.attempts=5
            snapshot=record.email_body
            db.commit()
        process_change(change_id)
        self.assertEqual(self.mail.call_count,1)
        self.mail.side_effect=None
        result=self.client.post(f'{self.base}/changes/{change_id}/retry')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.mail.call_args.kwargs['body'],snapshot)
        self.assertEqual(self.client.post(f'{self.base}/changes/{change_id}/retry').status_code,409)

    def test_email_transport_contains_previous_and_new_values(self):
        from lokzeitleiste.reports.mailer import send_time_change
        with patch.dict('os.environ',{'SMTP_SECURITY':'ssl'}), patch('smtplib.SMTP_SSL') as smtp:
            send_time_change(recipient='tf-edit@example.com',body='Arbeitsbeginn: 08:00 → 07:00\nArbeitsende: 16:00 → 17:00')
            email=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(email['To'],'tf-edit@example.com')
            self.assertIn('08:00 → 07:00',email.get_content())
            self.assertIn('16:00 → 17:00',email.get_content())


if __name__ == '__main__':
    unittest.main()
