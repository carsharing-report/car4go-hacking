#token refresh curl 'https://www.car2go.com/auth/realms/c2gcustomer/protocol/openid-connect/token' -H 'User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:64.0) Gecko/20100101 Firefox/64.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.5' --compressed -H 'Referer: https://www.car2go.com/spa/?fragment=rentals' -H 'Content-type: application/x-www-form-urlencoded' -H 'DNT: 1' -H 'Connection: keep-alive' -H 'Cookie: AUTH_SESSION_ID=<jsid>.keycloak-prod00docker18; KEYCLOAK_IDENTITY=????; KEYCLOAK_SESSION=c2gcustomer/<uuid>/<uuid>; JSESSIONID="<jsid>:-1.keycloak-prod00docker12"; car2go.cookie.allowed=true; JSESSIONID=<jsid>' -H 'Pragma: no-cache' -H 'Cache-Control: no-cache' --data 'grant_type=refresh_token&refresh_token=<bearer token?>&client_id=portal-client'

import json
import sys
from calendar import monthrange
from urllib.parse import urlparse, parse_qs
import logging
import requests
import datetime as dt
import csv

logger = logging.getLogger(__name__)


def month_iterator(start_month, end_month):
    while start_month <= end_month:
        yield start_month
        start_month = start_month + dt.timedelta(days=monthrange(start_month.year,
                                                                 start_month.month)[1])


class Car2Go:
    baseurl = 'https://www.car2go.com/caba/customer/v2/responsive/'

    def __init__(self, headers=None, **kwargs):
        self.headers = headers or {}
        self.args = kwargs

    def get_ride_info(self, uuid):
        r = requests.get(self.baseurl + 'rentals/' + uuid, headers=self.headers)
        r.raise_for_status()
        '''
        {
          "uuid": "ride uuid",
          "currency": "EUR",
          "driverName": "Actualname Lastname",
          "locationId": 12,
          "start": {
            "address": "somestraße 1 10117 Berlin",
            "latitude": 52.11111111,
            "longitude": 13.11111111,
            "time": "2019-12-24T22:18:31+0100"
          },
          "end": {
            "address": "somestraße 1, 10245 Berlin",
            "latitude": 52.11111111,
            "longitude": 13.11111111,
            "time": "2019-012-24T22:34:45+0100"
          },
          "buildSeries": "W246",
          "numberPlate": "HH-GO1111,
          "paymentProfileName": "Lastname, Actualname",
          "invoiceUrl": "https://www.car2go.com/documentstore/v1/customer/document/statement/XXXXXXX",
          "price": {
            "packagesUsed": false,
            "creditsUsed": false,
            "containsTaxItem": false,
            "totalAmount": 6.63,
            "priceItems": [
              {
                "uuid": "uuid",
                "amount": 6.63000,
                "type": "DRIVE",
                "count": 17,
                "description": "Fahrzeit: 17 min x 0,39 €/min"
              }
            ],
            "paymentsUsed": [
              {
                "paymentType": "MASTERCARD",
                "amount": 6.63,
                "profileType": "PRIVATE",
                "name": "XXXXXXXXXXXX1111"
              }
            ]
          }
        }'''

        return r.json()

    def get_month_rides(self, date: dt.date):
        month = '{}-{}'.format(date.year, date.month)
        url = self.baseurl + 'rentals/all'
        r = requests.get(url, params=dict(month=month, **self.args),
                         headers=self.headers)

        r.raise_for_status()
        rides = r.json().get('rentals', [])
        for r in rides:
            logger.info('processing %s', json.dumps(r))
            del r['driverName']  # this is anonymized as Maram Witwit

            if r['creditsUsed']:
                info = self.get_ride_info(r['uuid'])
                logger.info('processing %s', json.dumps(info))

                r['totalAmount'] = info['price']['totalAmount']
            else:
                r['totalAmount'] = r['chargedAmount']

        return rides

    def get_rides(self, starts_at: dt.date, ends_at: dt.date = None) -> dict:
        ends_at = ends_at or dt.date.today()
        for m in month_iterator(starts_at, ends_at):
            yield from self.get_month_rides(m)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    start_date = dt.date(2018, 1, 1)
    end_date = dt.date(2018, 12, 1)

    headers = {}
    params = {}
    for x in range(len(sys.argv)):
        if sys.argv[x] == '-H':
            p, v = sys.argv[x + 1].split(':', maxsplit=1)
            headers[p] = v.strip()
        if sys.argv[x].startswith('https://'):
            q = parse_qs(urlparse(sys.argv[x]).query)
            for p, vl in q.items():
                params[p] = vl[0]

    del params['month']

    c2g = Car2Go(headers, **params)

    with open('some.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'uuid',
            'creditsUsed',
            'chargedAmount',
            'currency',
            'ownRental',
            'name',
            'time'
        ])
        for ride in c2g.get_rides(start_date):
            print(ride)
            # uuid	0816a46c-9999-4d44-952a-b3b2170ccd7f
            # creditsUsed	false
            # chargedAmount	6.63
            # currency	EUR
            # driverName	Maram Witwit
            # ownRental	true
            # name	somestraße 78, 10117 Berlin
            # time	2019-12-24T22:18:31+0100
            writer.writerow(ride.values())
