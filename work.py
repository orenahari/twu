"""
This module
"""
import abc
import datetime as dt
import os
import platform
import subprocess
import time
from math import isclose
from random import randint

from bs4 import BeautifulSoup
from fastkml import kml

import exceptions
from parameters import Parameters
import twlog
import web

logger = twlog.TimeWatchLogger()
params = Parameters()


class StrategySelector:

    def __init__(self, date, session, overwrite, vacation):
        self.date = date
        self.session = session
        self.overwrite = overwrite
        self.distance_tolerance = 3
        self.work_coordinates = {'lat': 32.166702, 'long': 34.812927}
        self.vacation = vacation

    def select(self):

        # tw = web.TimewatchSingleDate(session=self.session, date=self.date, overwrite=False)
        # date_soup = tw.query()
        #
        # # try weekend
        # if self.date.weekday() in [4, 5]:
        #     return Weekend(date=self.date, session=self.session, overwrite=self.overwrite)
        #
        # # try holiday
        # pattern = '^(?!.*{date}).*$'.format(date=self.date.strftime('%d-%m-%Y'))
        # font_tags = date_soup.find_all(name='font', text=re.compile(pattern))
        # font_tags_filtered = [x for x in font_tags if self.date.strftime('%d-%m-%Y') in x.parent.text]
        # if len(font_tags_filtered) == 1:
        #     return Holiday(holiday_type=font_tags_filtered[0].text)
        #
        # # try office
        # with KMLFile(file_date=self.date) as f:
        #     placemarks = [PlacemarkWrapper(placemark=x, tolerance=self.distance_tolerance) for x in f.placemarks]
        # at_work = [x for x in placemarks if x.within_distance(work_coordinates=self.work_coordinates)]
        # if len(at_work) > 0:
        #     return WorkFromOffice

        # try
        # holiday_type =
        # holiday =
        # return [x for x in soup.find_all(name='font') if self._has_date_string(tag=x)]
        # return {
        #     'excuse': soup.find('select').find('option', selected=True),
        #     'begin': dt.time(hour=int(soup.find(name='input', id='ehh0').attrs['value']),
        #                      minute=int(soup.find(name='input', id='emm0').attrs['value'])),
        #     'end': dt.time(hour=int(soup.find(name='input', id='xhh0').attrs['value']),
        #                    minute=int(soup.find(name='input', id='xmm0').attrs['value']))
        #     'holiday':
        # }
        #
        #     return [x for x in soup.find_all(name='font') if self._has_date_string(tag=x)]
        # if
        #
        #     current_values = tw.query()

        # tw = web.TimewatchSingleDate(session=self.session, date=self.date, overwrite=False)
        # current_values = tw.query_date()
        #
        # if self.date.weekday() in [4, 5]:
        #     return Weekend(date=self.date, session=self.session, overwrite=self.overwrite)

        logger.info('Starting for date %s', self.date.strftime('%d/%m/%Y'))
        try:
            return Weekend(date=self.date, session=self.session, overwrite=self.overwrite)
        except exceptions.NotAValidStrategy:
            try:
                return Vacation(date=self.date, session=self.session, overwrite=self.overwrite)
            except exceptions.NotAValidStrategy:
                try:
                    return Holiday(date=self.date, session=self.session, overwrite=self.overwrite)
                except exceptions.NotAValidStrategy:
                    try:
                        return WorkFromOffice(date=self.date, session=self.session, overwrite=self.overwrite)
                    except exceptions.NotAValidStrategy:
                        return WorkFromHome(date=self.date, session=self.session, overwrite=self.overwrite)


class WorkDay(abc.ABC):

    def __init__(self, date: dt.datetime, session, overwrite: bool):
        self.date = date
        self.session = session
        self.timewatch_base_url = 'https://checkin.timewatch.co.il/punch'
        self.overwrite = overwrite
        if not self.is_valid():
            raise exceptions.NotAValidStrategy('%s is not a valid for %s', str(type(self)),
                                               self.date.strftime('%d-%m-%Y'))

    @abc.abstractmethod
    def fill(self):
        pass

    @abc.abstractmethod
    def is_valid(self):
        pass

    @property
    def logger_date(self):
        return self.date.strftime('%d/%m/%Y')

    def get_current_excuse(self):
        date_url_template = '{base}/editwh2.php?ie={company}&e={employee}&d={date}&jd={date}&tl={employee}'
        response = self.session.get(url=date_url_template.format(
            employee=self.session.employee_auth_number,
            base=self.timewatch_base_url,
            company=self.session.company,
            date=self.date.strftime('%Y-%m-%d')
        ))
        soup = BeautifulSoup(response.text, features='html.parser')
        return soup.find('select').find('option', selected=True)


class Weekend(WorkDay):

    def fill(self):
        logger.debug('%s is a weekend day', self.logger_date)

    def is_valid(self):
        return self.is_weekend()

    def is_weekend(self):
        """
        Check if date is weekend based on weekday definition:
        https://docs.python.org/3/library/datetime.html#datetime.date.weekday
        :return: bool. True if current date a weekend day
        """
        return self.date.weekday() in [4, 5]


class WorkFromOffice(WorkDay):

    def __init__(self, date: dt.datetime, session, overwrite: bool):
        self._placemarks = None
        self._at_work = None
        super().__init__(date=date, session=session, overwrite=overwrite)

    def fill(self):
        logger.debug('%s is an office workday', self.logger_date)
        tw = web.TimewatchSingleDate(session=self.session, date=self.date, overwrite=self.overwrite)
        t = self.get_work_times()
        tw.update(begin=t['begin'], end=t['end'], excuse=self.excuse)

    def is_valid(self):
        return len(self.at_work) > 0

    @property
    def work_coordinates(self):
        return {'lat': 32.166702, 'long': 34.812927}

    @property
    def distance_tolerance(self):
        return 3

    @property
    def placemarks(self):
        if self._placemarks:
            pass
        else:
            with KMLFile(file_date=self.date) as f:
                self._placemarks = [PlacemarkWrapper(placemark=x,
                                                     tolerance=self.distance_tolerance) for x in f.placemarks]
        return self._placemarks

    def get_work_times(self):
        return {
            'begin': min([x.timespan['begin'].astimezone() for x in self.at_work]),
            'end': max([x.timespan['end'].astimezone() for x in self.at_work])
        }

    @property
    def at_work(self):
        if self._at_work:
            pass
        else:
            self._at_work = [x for x in self.placemarks if x.within_distance(work_coordinates=self.work_coordinates)]
        return self._at_work

    @property
    def excuse(self):
        return str(0)


class WorkFromHome(WorkDay):

    def fill(self):
        logger.debug('%s is a home workday', self.logger_date)
        tw = web.TimewatchSingleDate(date=self.date, session=self.session, overwrite=self.overwrite)
        t = self.spoof_times()
        tw.update(begin=t['begin'], end=t['end'], excuse=self.excuse)

    def is_valid(self):
        return True

    @property
    def excuse(self):
        return str(74)

    @property
    def defaults(self):
        return {
            'minimal_start_time': dt.datetime.strptime(
                date_string=params.work['work_day']['minimal_start_time'],
                format='%H:%M'),
            'maximal_end_time': dt.datetime.strptime(
                date_string=params.work['work_day']['maximal_end_time'],
                format='%H:%M'),
            'max_length': int(params.work['work_day']['max_length']),
            'nominal_length': int(params.work['work_day']['nominal_length'])
        }

    def spoof_times(self):
        if params.work['work_day']['randomize']:
            strategy = RandomizedTime()
        else:
            strategy = FixedTime()
        return strategy.spoof()
    # def spoof_times(self) -> dict:
    #     """
    #     Randomizes start and end times in the day.
    #
    #     Randomize starting from the minimal start time with 0-2 hours.
    #     Randomize end such that work day won't be longer than max length day [hours] or shorter than nominal-1 [hours]
    #     or that is won't end past maximal end time, as provided in the parameters file.
    #
    #     :return: dict with start datetime object and end datetime object representing the start/end of workday
    #     """
    #     begin = dt.datetime(
    #         year=self.date.year, month=self.date.month, day=self.date.day,
    #         hour=int(self.defaults['minimal_start_time'].hour),
    #         minute=int(randint(0, 59)))
    #
    #     return {'begin': begin, 'end': self.delta(begin=begin)}
    #
    # def delta(self, begin):
    #     d = begin.replace(
    #         hour=begin.hour + self.defaults['nominal_length'] + randint(-1, 1),
    #         minute=int(randint(0, 59))
    #     )
    #     if d < self.max_time(begin=begin):
    #         return d
    #     else:
    #         return self.delta(begin=begin)
    #
    # def max_time(self, begin):
    #     return begin.replace(minute=0, hour=self.defaults['minimal_start_time'].hour + self.defaults['max_length'])


class Vacation(WorkDay):

    def fill(self):
        logger.debug('%s was already filled out as a vacation - doing nothing', self.logger_date)

    def is_valid(self):
        excuse = self.get_current_excuse()
        return excuse.attrs['value'] == str(1)


class Holiday(WorkDay):

    def __init__(self, date: dt.datetime, session, overwrite: bool):
        self._holiday_type = None
        super().__init__(date=date, session=session, overwrite=overwrite)

    @property
    def holiday_type(self):
        return self._holiday_type

    @holiday_type.setter
    def holiday_type(self, value):
        self._holiday_type = value

    def fill(self):
        logger.debug('%s is a holiday %s', self.logger_date, self.holiday_type)
        tw = web.TimewatchSingleDate(date=self.date, session=self.session, overwrite=self.overwrite)
        tw.update(excuse=self.excuse)

    def is_valid(self):
        labels = self.get_date_labels()
        if len(labels) == 1:
            tag = labels[0]
            try:
                self.holiday_type = self.find_holiday_type(tag=tag)
                return True
            except exceptions.NoHolidayFound:
                return False
        else:
            ValueError('Too many labels for %s', self.date.strftime('%d-%m-%Y'))

    @property
    def excuse(self):
        if self.holiday_type == 'day':
            return str(1)
        elif self.holiday_type == 'eve':
            return str(2250)
        else:
            raise ValueError('%s is not a valid holiday type', self.holiday_type)

    def find_holiday_type(self, tag):
        obsereved_holiday_type = set([ord(x) for x in tag.text])
        for k, v in self.holiday_types.items():
            if set([ord(x) for x in v]) == obsereved_holiday_type:
                return k
        raise exceptions.NoHolidayFound()

    @property
    def holiday_types(self):
        return {'day': 'חג', 'eve': 'ערב חג'}

    def get_date_labels(self):
        date_url_template = '{base}/editwh2.php?ie={company}&e={employee}&d={date}&jd={date}&tl={employee}'
        response = self.session.get(url=date_url_template.format(
            employee=self.session.employee_auth_number,
            base=self.timewatch_base_url,
            company=self.session.company,
            date=self.date.strftime('%Y-%m-%d')
        ))
        soup = BeautifulSoup(response.text, features='html.parser')
        return [x for x in soup.find_all(name='font') if self._has_date_string(tag=x)]

    def _has_date_string(self, tag):
        return self.date.strftime('%d-%m-%Y') in tag.parent.text and self.date.strftime('%d-%m-%Y') not in tag.text


class KMLFile:
    """
    Represents the KML file itself.
    Encapsulate file operations on KML file
    """

    def __init__(self, file_date):
        self.file_date = file_date
        self._download_process = None
        self.raw_data = None
        self._placemarks = None

    def __enter__(self):
        if self.file_date.date() == dt.datetime.today().date():
            raise exceptions.TodayKMLExcpetion('Cannot download today\'s kml file - process will hang')
        else:
            self._download_file()
            return self

    def __exit__(self, *exception):
        try:
            os.remove(self.file_path)
            logger.debug('file %s was removed', self.file_name)
        except PermissionError:
            logger.debug('unable to remove file %s', self.file_name)
        logger.debug('attempt to close download file browser window')
        self._download_process.kill()

    def read(self):
        """
        read kml data from the saved file into a raw string
        :return:
        """
        with open(file=self.file_path, mode='rb') as f:
            return f.read()

    @property
    def placemarks(self):
        if self._placemarks:
            return self._placemarks
        else:
            kml_data = kml.KML()
            kml_data.from_string(self.read())

            # assume kml_data is document level
            # TODO: deal with the case where it is not document > placemarks
            self._placemarks = []
            for document in kml_data.features():
                if isinstance(document, kml.Document):
                    self._placemarks.extend([x for x in document.features()])
                else:
                    continue

            return self._placemarks

    @property
    def file_name(self):
        return 'history-{date}.kml'.format(date=dt.datetime.strftime(self.file_date, '%Y-%m-%d'))

    @property
    def downloads_dir(self):
        return os.path.join(os.path.expanduser('~'), 'Downloads')

    @property
    def file_path(self):
        return os.path.join(self.downloads_dir, self.file_name)

    @property
    def no_zero_padding(self):
        if platform.system() == 'linux':
            return '-'
        else:
            return '#'

    @property
    def timeline_url(self):
        """
        Generates url to download kml file from google based on required date.

        :return str: kml download link for class instance date
        """

        # This is dif, months (and only months) are zero based
        # (https://stackoverflow.com/questions/32332904/current-url-to-download-kml-data-from-google-location-history)

        'https://www.google.com/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i2020!2i6!3i16!2m3!1i2020!2i6!3i16'
        month = '!2i{month}'.format(month=self.file_date.month - 1)

        year = '!1i{year}'.format(year=self.file_date.strftime('%{zp}Y'.format(zp=self.no_zero_padding)))
        day = '!3i{day}'.format(day=self.file_date.strftime('%{zp}d'.format(zp=self.no_zero_padding)))

        pb = '!1m8!1m3{year}{month}{day}!2m3{year}{month}{day}'.format(year=year, month=month, day=day)
        url = '{base_url}/kml?authuser={user}&pb={pb}'.format(
            base_url=r'https://www.google.com/maps/timeline',
            user=0,
            pb=pb
        )
        return url

    def _download_file(self):
        logger.debug('Start download of kml file')
        if platform.system() == 'Linux':
            chrome_path = 'google-chrome'
        elif platform.system() == 'Windows':
            chrome_path = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        else:
            raise ValueError('{} is not a supported os'.format(platform.system()))

        self._download_process = subprocess.Popen(args=(chrome_path, self.timeline_url),
                                                  stdout=subprocess.PIPE,
                                                  stdin=subprocess.PIPE,
                                                  stderr=subprocess.PIPE)
        counter = 0
        max_cycles = 200
        sleep_time = 0.5  # seconds
        while (not os.path.exists(self.file_path)) and (counter < max_cycles):
            time.sleep(sleep_time)
            counter += 1
        if counter >= max_cycles:
            raise RuntimeError(
                'more that {} seconds waiting for file to be downloaded - stopping'.format(
                    str(sleep_time * max_cycles)))
        else:
            logger.debug('Finished kml file download: %s', self.file_name)


class PlacemarkWrapper:

    def __init__(self, placemark, tolerance):
        self.placemark = placemark
        self.tolerance = tolerance

    @property
    def placemark(self):
        return self._placemark

    @placemark.setter
    def placemark(self, value):
        self._placemark = value

    @property
    def coordinates(self):
        coords = self.placemark.geometry.coords[0]
        return {
            'lat': coords[1], 'long': coords[0], 'alt': coords[2]
        }

    @property
    def timespan(self):
        return {
            'begin': self.placemark.begin,
            'end': self.placemark.end
        }

    def within_distance(self, work_coordinates):
        """
        Checks if coordinates provided are within a tolerance of the work location.

        :param dict work_coordinates: lat and long of work location
        :return: True if provided coordinates are within tolerance of work coordinates
        """

        # round to 3 decimal places - gives a ~100 meters precision
        # assumes to be neighborhood or street
        # https://en.wikipedia.org/wiki/Decimal_degrees
        precision = pow(10, -3)

        is_close_long = isclose(self.coordinates['long'], round(float(work_coordinates['long']), 5),
                                abs_tol=self.tolerance * precision)
        is_close_lat = isclose(self.coordinates['lat'], round(float(work_coordinates['lat']), 5),
                               abs_tol=self.tolerance * precision)

        return is_close_lat and is_close_long


class TimeSpoof(abc.ABC):

    def __init__(self):
        pass

    @abc.abstractmethod
    def spoof(self):
        pass

    @property
    def defaults(self):
        return {
            'minimal_start_time': dt.datetime.strptime(
                date_string=params.work['work_day']['minimal_start_time'],
                format='%H:%M'),
            'maximal_end_time': dt.datetime.strptime(
                date_string=params.work['work_day']['maximal_end_time'],
                format='%H:%M'),
            'max_length': int(params.work['work_day']['max_length']),
            'nominal_length': int(params.work['work_day']['nominal_length'])
        }


class FixedTime(TimeSpoof):

    def spoof(self):
        return {
            'begin': dt.datetime.strptime(
                date_string=params.work['work_day']['minimal_start_time'],
                format='%H:%M').time(),
            'end': dt.datetime.strptime(
                date_string=params.work['work_day']['maximal_end_time'],
                format='%H:%M')
        }


class RandomizedTime(TimeSpoof):

    def spoof(self):
        """
        Randomizes start and end times in the day.

        Randomize starting from the minimal start time with 0-2 hours.
        Randomize end such that work day won't be longer than max length day [hours] or shorter than nominal-1 [hours]
        or that is won't end past maximal end time, as provided in the parameters file.

        :return: dict with start datetime object and end datetime object representing the start/end of workday
        """
        begin = dt.datetime.strptime(params.work['work_day']['minimal_start_time'], '%H:%M')

        return {'begin': begin.time(), 'end': self.delta(begin=begin).time()}

    def delta(self, begin):
        d = begin.replace(
            hour=begin.hour + params.work['work_day']['nominal_length'] + randint(-1, 1),
            minute=int(randint(0, 59))
        )
        if d < begin + dt.timedelta(hours=params.work['work_day']['max_length']) and d < dt.datetime.strptime(
                params.work['work_day']['maximal_end_time'], '%H:%M'):
            return d
        else:
            return self.delta(begin=begin)
