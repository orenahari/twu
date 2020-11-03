"""
This module deals with all the webpage aspects of the reporting.
Login, filling in the correct boxes, saving, etc.
"""
import abc
import datetime as dt
import enum
import random
import urllib

import requests
from bs4 import BeautifulSoup

import exceptions
from parameters import Parameters
import twlog
import work

logger = twlog.TimeWatchLogger()
params = Parameters()


class Excuse(enum.Enum):
    #TODO: add excuses to setup template
    sick = params.excuse_numbers['sick']
    vacation = params.excuse_numbers['vacation']
    holiday_eve = params.excuse_numbers['holiday_eve']
    home = params.excuse_numbers['home']
    holiday = params.excuse_numbers['holiday']
    office = params.excuse_numbers['office']


class Timewatch:

    def __init__(self, start_date: dt.datetime, end_date: dt.datetime,
                 overwrite: bool,
                 vacation_list: list,
                 sick_list: list):
        self.session = None
        self.start_date = start_date
        self.end_date = end_date
        self.company = None
        self.overwrite = overwrite
        self.timewatch_base_url = 'https://checkin.timewatch.co.il/punch'
        self.vacation_list = vacation_list
        self.sick_list = sick_list

    def login(self, user, company, password, proxies=None):
        self.company = company
        self.session = requests.Session()
        if proxies:
            self.session.proxies.update(proxies)
            response = self.session.post(url='{base}/punch2.php'.format(base=self.timewatch_base_url),
                                         data={'comp': company, 'name': user, 'pw': password},
                                         proxies=proxies)
        else:
            response = self.session.post(url='{base}/punch2.php'.format(base=self.timewatch_base_url),
                                         data={'comp': company, 'name': user, 'pw': password})
        self._determine_login_success(response=response)
        self._set_employee_auth()

    def _determine_login_success(self, response):
        url_parts = urllib.parse.urlparse(response.url, scheme='', allow_fragments=True)
        if 'e=' in url_parts.query:
            raise exceptions.LoginFailure('error: %s', url_parts.query)
        else:
            setattr(self.session, 'login_response', response)
            logger.info('Successfully logged in')

    def _set_employee_auth(self):
        soup = BeautifulSoup(self.session.login_response.text, features='html.parser')
        selected_href = soup.select('a[href*="/punch/editwh.php"]')
        for res in selected_href:
            try:
                href = res.attrs['href']
                query = urllib.parse.urlparse(href, scheme='', allow_fragments=True).query
                parameters = urllib.parse.parse_qs(query)
                setattr(self.session, 'employee_auth_number', parameters['ee'][0])
                setattr(self.session, 'company', self.company)
            except (TypeError, KeyError, AttributeError, IndexError):
                continue

    def fill(self):
        for d in self.date_list:
            try:
                logger.info('Working on date %s', d.strftime('%d-%m-%Y'))
                tw = TimewatchSingleDate(session=self.session, date=d)
                tw.query()
                if d.weekday() in [4, 5]:
                    logger.debug('%s is a weekend', d.strftime('%d/%m/%Y'))
                elif d in self.sick_list:
                    tw.set_values(begin=None, end=None, excuse=Excuse.sick, overwrite=self.overwrite)
                elif d in self.vacation_list:
                    tw.set_values(begin=None, end=None, excuse=Excuse.vacation, overwrite=self.overwrite)
                elif tw.is_holiday():
                    tw.set_values(begin=None, end=None, excuse=Excuse.vacation, overwrite=self.overwrite)
                elif tw.is_holiday_eve():
                    tw.set_values(begin=None, end=None, excuse=Excuse.vacation_eve, overwrite=self.overwrite)
                elif tw.is_at_work():
                    work_hours = tw.get_hours(mode='work')
                    tw.set_values(begin=work_hours['begin'], end=work_hours['end'], excuse=Excuse.office,
                                  overwrite=self.overwrite)
                else:
                    work_hours = tw.get_hours(mode='spoof')
                    tw.set_values(begin=work_hours['begin'], end=work_hours['end'], excuse=Excuse.home,
                                  overwrite=self.overwrite)
            except exceptions.CannotProceedWithDate as e:
                logger.debug('Cannot proceed with date %s (%s)', d.strftime('%d-%m-%Y'), str(e))

    @property
    def date_list(self):
        """
        generator of dates in sequence between two given dates.\n
        yields dates in the sequence for iteration only if they are work days.

        :yields: each yield is a consecutive date in the range start to end dates
        """
        delta = self.end_date - self.start_date
        for d in range(delta.days + 1):
            tmp_date = self.start_date + dt.timedelta(days=d)
            yield tmp_date


class TimewatchSingleDate:

    def __init__(self, session, date):
        self.session = session
        self.date = date
        self.excuse = None
        self.placemarks = None
        self.at_work = None
        self.soup = None
        self.holiday = None

    def set_values(self, begin, end, excuse, overwrite):
        if overwrite:
            headers = {
                'Content-Type': "application/x-www-form-urlencoded",
                'Referer': self.get_url
            }

            data = {
                'e': self.session.employee_auth_number,
                'c': self.session.company,
                'tl': self.session.employee_auth_number,
                'd': self.date.strftime('%Y-%m-%d'),
                'jd': self.date.strftime('%Y-%m-%d')
            }

            # all 5 boxes start out as emtpy
            for prefix in ['e', 'x']:
                for idx in range(0, 5):
                    data.update({
                        '{p}hh{i}'.format(i=idx, p=prefix): '',
                        '{p}mm{i}'.format(i=idx, p=prefix): ''})

            try:
                # override the 0 index box
                logger.debug('Setting begin time to %s', begin.strftime('%H:%M'))
                data.update({'ehh0': begin.strftime('%H'), 'emm0': begin.strftime('%M')})
            except AttributeError:
                pass

            try:
                logger.debug('Setting end time to %s', end.strftime('%H:%M'))
                data.update({'xhh0': end.strftime('%H'), 'xmm0': end.strftime('%M')})
            except AttributeError:
                pass

            # overwrite excuse
            logger.debug('Setting excuse to %s', str(excuse))
            data.update({'excuse': str(excuse.value)})

            self.post(url=self.post_url, data=data, headers=headers)
        else:
            logger.debug('Setting begin time to %s', begin.strftime('%H:%M'))

    @property
    def work_coordinates(self):
        return {'lat': 32.166702, 'long': 34.812927}

    @property
    def distance_tolerance(self):
        return 3

    def is_at_work(self):
        try:
            with work.KMLFile(file_date=self.date) as f:
                self.placemarks = [work.PlacemarkWrapper(placemark=x,
                                                         tolerance=self.distance_tolerance) for x in f.placemarks]
            self.at_work = [x for x in self.placemarks if x.within_distance(work_coordinates=self.work_coordinates)]
            return len(self.at_work) > 0
        except exceptions.TodayKMLExcpetion as e:
            raise exceptions.CannotProceedWithDate(str(e))

    def is_holiday_eve(self):
        try:
            self._get_holiday()
            return self.holiday == 'eve'
        except exceptions.NoHolidayFound:
            return False

    def is_holiday(self):
        try:
            self._get_holiday()
            return self.holiday == 'day'
        except exceptions.NoHolidayFound:
            return False

    def get_hours(self, mode):
        if mode == 'work':
            return {
                'begin': min([x.timespan['begin'].astimezone() for x in self.at_work]),
                'end': max([x.timespan['end'].astimezone() for x in self.at_work])
            }
        elif mode == 'spoof':
            """
            Randomizes start and end times in the day.

            Randomize starting from the minimal start time with 0-2 hours.
            Randomize end such that work day won't be longer than max length day [hours] or shorter than nominal-1 [hours]
            or that is won't end past maximal end time, as provided in the parameters file.

            :return: dict with start datetime object and end datetime object representing the start/end of workday
            """
            begin = dt.datetime.strptime(params.work['work_day']['minimal_start_time'], '%H:%M')
            if params.work['work_day']['randomize']:
                return {'begin': begin.time(), 'end': self.delta(begin=begin).time()}
            else:
                return {'begin': params.work['work_day']['minimal_start_time'],
                        'end': params.work['work_day']['maximal_end_time']}

    def delta(self, begin):
        d = begin.replace(
            hour=begin.hour + params.work['work_day']['nominal_length'] + random.randint(-1, 1),
            minute=int(random.randint(0, 59))
        )
        if d < begin + dt.timedelta(hours=params.work['work_day']['max_length']) and d < dt.datetime.strptime(
                params.work['work_day']['maximal_end_time'], '%H:%M'):
            return d
        else:
            return self.delta(begin=begin)

    def _get_holiday(self):
        date_str = self.date.strftime('%d-%m-%Y')
        font_tags = [x for x in self.soup.find_all(name='font')]
        font_tags_filtered_by_date = [x for x in font_tags if date_str in x.parent.text and date_str not in x.text]
        if len(font_tags_filtered_by_date) == 1:
            tag = font_tags_filtered_by_date[0]
            obsereved_holiday_type = set([ord(x) for x in tag.text])
            if set([ord(x) for x in self.holiday_types['day']]) == obsereved_holiday_type:
                self.holiday = 'day'
            elif set([ord(x) for x in self.holiday_types['eve']]) == obsereved_holiday_type:
                self.holiday = 'eve'
            else:
                raise exceptions.NoHolidayFound
        else:
            ValueError('Too many labels for %s', self.date.strftime('%d-%m-%Y'))

    @property
    def holiday_types(self):
        return {'day': 'חג', 'eve': 'ערב חג'}

    def query(self):
        response = self.session.get(self.get_url)
        self.soup = BeautifulSoup(response.text, features='html.parser')

    @property
    def base_url(self):
        return r'https://checkin.timewatch.co.il'

    @property
    def get_url(self):
        template = '{base}/punch/editwh2.php?ie={company}&e={employee}&d={date}&jd={date}&tl={employee}'
        url = template.format(
            base=self.base_url,
            company=self.session.company,
            employee=self.session.employee_auth_number,
            date=self.date.strftime('%Y-%m-%d')
        )
        return url

    @property
    def post_url(self):
        return '{base}/punch/editwh3.php'.format(base=self.base_url)

    def post(self, url, data, headers):
        response = self.session.post(url=url,
                                     data=data,
                                     headers=headers,
                                     verify=True,
                                     allow_redirects=True,
                                     proxies=self.session.proxies)
        if not response.status_code == 200:
            raise exceptions.BadResponseCode('Got a response of %s', str(response.status_code))
        if 'reject' in response.text:
            raise exceptions.PostRequestRejected()


class UpdateStrategy(abc.ABC):

    def __init__(self, date, session, begin, end, excuse):
        self.begin = begin
        self.end = end
        self.excuse = excuse
        self.session = session
        self.date = date
        self.existing_values = dict()

    @abc.abstractmethod
    def update(self):
        pass

    @property
    def logger_date(self):
        return self.date.strftime('%d/%m/%Y')

    def post(self, url, data, headers):
        response = self.session.post(url=url,
                                     data=data,
                                     headers=headers,
                                     verify=True,
                                     allow_redirects=True,
                                     proxies=self.session.proxies)
        if not response.status_code == 200:
            raise exceptions.BadResponseCode('Got a response of %s', str(response.status_code))
        if 'reject' in response.text:
            raise exceptions.PostRequestRejected()

    @property
    def post_url(self):
        return '{base}/punch/editwh3.php'.format(base=self.base_url)

    @property
    def base_url(self):
        return r'https://checkin.timewatch.co.il'

    @property
    def get_url(self):
        template = '{base}/punch/editwh2.php?ie={company}&e={employee}&d={date}&jd={date}&tl={employee}'
        url = template.format(
            base=self.base_url,
            company=self.session.company,
            employee=self.session.employee_auth_number,
            date=self.date.strftime('%Y-%m-%d')
        )
        return url

    @staticmethod
    def select(date, session, excuse, begin, end, overwrite):
        if overwrite:
            return Overwrite(date=date, session=session, excuse=excuse, begin=begin, end=end)
        else:
            if any([excuse.attrs['value'] == x for x in ['1']]):
                return Preserve(date=date, session=session, excuse=excuse, begin=None, end=None)
            else:
                return Preserve(date=date, session=session, excuse=excuse, begin=begin, end=end)


class Overwrite(UpdateStrategy):

    def update(self):
        logger.debug('Using `overwrite` strategy - all values will be overwritten')
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'Referer': self.get_url
        }

        data = {
            'e': self.session.employee_auth_number,
            'c': self.session.company,
            'tl': self.session.employee_auth_number,
            'd': self.date.strftime('%Y-%m-%d'),
            'jd': self.date.strftime('%Y-%m-%d')
        }

        # all 5 boxes start out as emtpy
        for prefix in ['e', 'x']:
            for idx in range(0, 5):
                data.update({
                    '{p}hh{i}'.format(i=idx, p=prefix): '',
                    '{p}mm{i}'.format(i=idx, p=prefix): ''})

        # overwrite excuse
        logger.debug('Setting excuse to %s', self.excuse)
        data.update({'excuse': self.excuse})
        # override the 0 index box
        logger.debug('Setting begin time to %s', self.begin.strftime('%H:%M'))
        data.update({'ehh0': self.begin.strftime('%H'), 'emm0': self.begin.strftime('%M')})

        logger.debug('Setting end time to %s', self.end.strftime('%H:%M'))
        data.update({'xhh0': self.end.strftime('%H'), 'xmm0': self.end.strftime('%M')})

        self.post(url=self.post_url, data=data, headers=headers)


class Preserve(UpdateStrategy):

    def update(self):
        self._get_date_values()
        logger.debug('Using `preserve` strategy - values will be preserved where appropriate')
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'Referer': self.get_url
        }

        data = {
            'e': self.session.employee_auth_number,
            'c': self.session.company,
            'tl': self.session.employee_auth_number,
            'd': self.date.strftime('%Y-%m-%d'),
            'jd': self.date.strftime('%Y-%m-%d'),
        }

        # clear 4 last rows
        for prefix in ['e', 'x']:
            for idx in range(1, 5):
                data.update({
                    '{p}hh{i}'.format(i=idx, p=prefix): '',
                    '{p}mm{i}'.format(i=idx, p=prefix): ''})

        if self.has_excuse():
            logger.debug('Excuse is already set to %s. Not changing excuse', self.existing_values['excuse'].text)
            data.update({'excuse': self.existing_values['excuse'].attrs['value']})
        else:
            logger.debug('Excuse is not set - setting to %s', self.excuse)
            data.update({'excuse': self.excuse})

        if self.need_to_update_begin():
            logger.debug('Setting begin time to %s', self.begin.strftime('%H:%M'))
        else:
            logger.debug('Setting begin time to %s', self.begin.strftime('%H:%M'))
            logger.debug('Begin time already set - doing nothing')
            self.begin = self.existing_values['begin']

        data.update({'ehh0': self.begin.strftime('%H'), 'emm0': self.begin.strftime('%M')})

        if self.need_to_update_end():
            logger.debug('Setting end time to %s', self.end.strftime('%H:%M'))
        else:
            logger.debug('End time already set - doing nothing')
            self.end = self.existing_values['end']

        data.update({'xhh0': self.end.strftime('%H'), 'xmm0': self.end.strftime('%M')})

        self.post(url=self.post_url, data=data, headers=headers)

    def has_excuse(self):
        return not self.existing_values['excuse'].attrs['value'] == '0'

    def need_to_update_begin(self):
        # need to update the value only if there is no actual value
        # AND a value was provided
        # AND the current excuse does not prohibit times (like vacation)
        return self.existing_values['begin'] == '' and (not self.begin == '') and self.is_excuse_prohibit_times()

    def need_to_update_end(self):
        return not self.existing_values['end'] == '' and (not self.end == '') and self.is_excuse_prohibit_times()

    def is_excuse_prohibit_times(self):
        return self.existing_values['excuse'].attrs['value'] in [str(x) for x in [1, 2250]]

    def _get_date_values(self):
        response = self.session.get(self.get_url)
        soup = BeautifulSoup(response.text, features='html.parser')
        self.existing_values.update({'excuse': soup.find('select').find('option', selected=True)})

        try:
            self.existing_values.update({
                'begin': dt.time(hour=int(soup.find(name='input', id='ehh0').attrs['value']),
                                 minute=int(soup.find(name='input', id='emm0').attrs['value']))})
        except ValueError:
            self.existing_values.update({'begin': ''})

        try:
            self.existing_values.update({
                'end': dt.time(hour=int(soup.find(name='input', id='xhh0').attrs['value']),
                               minute=int(soup.find(name='input', id='xmm0').attrs['value']))})
        except ValueError:
            self.existing_values.update({'end': ''})
