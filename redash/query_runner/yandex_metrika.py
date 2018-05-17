import json
import logging
from redash.query_runner import *
from redash.utils import JSONEncoder
import requests
from urlparse import parse_qs, urlparse
logger = logging.getLogger(__name__)

COLUMN_TYPES = {
    'date': (
        'firstVisitDate', 'firstVisitStartOfYear', 'firstVisitStartOfQuarter',
        'firstVisitStartOfMonth', 'firstVisitStartOfWeek',
    ),
    'datetime': (
        'firstVisitStartOfHour', 'firstVisitStartOfDekaminute', 'firstVisitStartOfMinute',
        'firstVisitDateTime', 'firstVisitHour', 'firstVisitHourMinute'

    ),
    'int': (
        'pageViewsInterval', 'pageViews', 'firstVisitYear', 'firstVisitMonth',
        'firstVisitDayOfMonth', 'firstVisitDayOfWeek', 'firstVisitMinute',
        'firstVisitDekaminute',
    )
}

for type_, elements in COLUMN_TYPES.items():
    for el in elements:
        if 'first' in el:
            el = el.replace('first', 'last')
            COLUMN_TYPES[type_] += (el, )


def parse_ym_response(response):
    columns = []
    dimensions_len = len(response['query']['dimensions'])
   
    for h in response['query']['dimensions'] + response['query']['metrics']:
        friendly_name = h.split(':')[-1]
        if friendly_name in COLUMN_TYPES['date']:
            data_type = TYPE_DATE
        elif friendly_name in COLUMN_TYPES['datetime']:
            data_type = TYPE_DATETIME
        else:
            data_type = TYPE_STRING
        columns.append({'name': h, 'friendly_name': friendly_name, 'type': data_type})

    rows = []
    for num, row in enumerate(response['data']):
        res = {}
        for i, d in enumerate(row['dimensions']):
            res[columns[i]['name']] = d['name']
        for i, d in enumerate(row['metrics']):
            res[columns[dimensions_len + i]['name']] = d
            if num == 0 and isinstance(d, float):
                columns[dimensions_len + i]['type'] = TYPE_FLOAT
        rows.append(res)

    return {'columns': columns, 'rows': rows}


class YandexMetrika(BaseSQLQueryRunner):
    @classmethod
    def annotate_query(cls):
        return False

    @classmethod
    def type(cls):
        return "yandex_metrika"

    @classmethod
    def name(cls):
        return "Yandex Metrika"

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "token": {
                    "type": "string",
                    "title": "OAuth Token"
                }
            },
            "required": ["token"],
        }

    def __init__(self, configuration):
        super(YandexMetrika, self).__init__(configuration)
        self.syntax = 'json'
        self.host = 'https://api-metrika.yandex.ru'
        self.list_path = 'counters'

    def _get_tables(self, schema):

        counters = self._send_query('management/v1/{0}'.format(self.list_path))

        for row in counters[self.list_path]:
            owner = row.get('owner_login')
            counter = '{0} | {1}'.format(
                row.get('name', 'Unknown').encode('utf-8'), row.get('id', 'Unknown')
            )
            if owner not in schema:
                schema[owner] = {'name': owner, 'columns': []}

            schema[owner]['columns'].append(counter)

        return schema.values()

    def test_connection(self):
        self._send_query('management/v1/{0}'.format(self.list_path))

    def _send_query(self, path='stat/v1/data', **kwargs):
        token = kwargs.pop('oauth_token', self.configuration['token'])
        r = requests.get('{0}/{1}'.format(self.host, path), params=dict(oauth_token=token, **kwargs))
        if r.status_code != 200:
            raise Exception(r.text)
        return r.json()

    def run_query(self, query, user):
        logger.debug("Metrika is about to execute query: %s", query)
        data = None
        if query == "":
            error = "Query is empty"
            return data, error
        try:
            params = json.loads(query)
        except ValueError:
            params = parse_qs(urlparse(query).query, keep_blank_values=True)

        try:
            data = json.dumps(parse_ym_response(self._send_query(**params)), cls=JSONEncoder)
            error = None
        except Exception as e:
            logging.exception(e)
            error = unicode(e)
        return data, error


class YandexAppMetrika(YandexMetrika):
    @classmethod
    def type(cls):
        return "yandex_appmetrika"

    @classmethod
    def name(cls):
        return "Yandex AppMetrika"

    def __init__(self, configuration):
        super(YandexAppMetrika, self).__init__(configuration)
        self.host = 'https://api.appmetrica.yandex.ru'
        self.list_path = 'applications'


register(YandexMetrika)
register(YandexAppMetrika)
