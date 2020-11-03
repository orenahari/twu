"""
This module houses an implementation of a Singleton :class:`TimeWatchParametersSingleton`
for parameters access.
Also a subclass :class:`TimeWatchParameters` that is used for the access.
"""

import json
import os


class Parameters(object):
    """
    Singleton & Context manager implementation for parameters access.
    Instantiation is emtpy.
    parameters are added later via a call to `with` statement:
    """
    _instance = None
    file_path = None
    params = dict()

    def __new__(cls, *args, **kwargs):
        if isinstance(cls._instance, Parameters):
            with open(os.path.join(os.path.dirname(__file__), 'params', 'params.json')) as f:
                cls._instance.params.update(json.loads(f.read()))
        else:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __getattr__(self, name):
        try:
            return self.params[name]
        except KeyError:
            return getattr(self, name)

    def is_params_valid(self):
        lst = flatten_dict(self.params)
        return not any(['xxx' == x for x in lst])

    def generate_params(self):
        if not self.is_params_valid() and input('Do you wish to interactively update parameters? (yes/no)') == 'yes':
            self._instance.user['worker'] = str(input('What is the username?\n'))
            self._instance.user['company'] = str(input('What is the company number?\n'))
            self._instance.user['password'] = str(input('What is the password?\n'))
            self._instance.work['location'] = {
                'lat': input('What is work lat (float)?'),
                'long': input('What is work long (float)?')
            }
            self._instance.work['work_day'] = {
                'max_length': int(input('What is the max number (int) of hours allowed in work day?')),
                'nominal_length': int(input('What is the nominal number (int) of hours per work day?')),
                'minimal_start_time': input('What is minimal start of work day (HH:MM)?'),
                'maximal_end_time': input('What is maximal end of work day (HH:MM)?')
            }
            if input('Do you wish to randomize (yes/no)?') == 'yes':
                self._instance.work['work_day'].update({'randomize': True})
            else:
                self._instance.work['work_day'].update({'randomize': False})
            self._instance.params.excuse = {
                'holiday': input('What is the phrase excuse used for `holiday DAY`?'),
                'holiday_eve': input('What is the phrase excuse used for `holiday EVE`?'),
                'home': input('What is the pharse used for `work from home`?')
            }
            self.write_to_file()

    def write_to_file(self):
        params = dict()
        params.update({'user': self._instance.user})
        params.update({'work': self._instance.work})
        with open(self._instance.file_path, 'w+') as f:
            f.write(json.dumps(params))


def flatten_dict(d):
    lst = []
    for k, v in d.items():
        if isinstance(v, dict):
            lst.extend(flatten_dict(v))
        else:
            lst.append(v)
    return lst
