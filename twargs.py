import argparse
import datetime as dt
import re


class TWArgs:

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='Build and import projects')
        self.parser.add_argument('--proxy', dest='proxy', action='store', default=None,
                                 help='http/https proxy (the same) to be used with/without authentication')

        regular_mode = self.parser.add_argument_group()
        regular_mode.add_argument('--start-date', dest='start_date', action=VerifyDateFormatAction,
                                  help='enter start date (included) in DD-MM-YYYY format')
        regular_mode.add_argument('--end-date', dest='end_date', action=VerifyDateFormatAction,
                                  help='enter end date (included) in DD-MM-YYYY format')
        regular_mode.add_argument('--overwrite', dest='overwrite', action='store_true', default=False,
                                  help='If true will overwrite all values, default is False')
        regular_mode.add_argument('--vacation', nargs='*', dest='vacation', default=[],
                                  help='vacation dates as space separated dates (dd/mm/YYYY), or range as: start..end')
        regular_mode.add_argument('--sick', nargs='*', dest='sick', default=[],
                                  help='sick dates as space separated dates (dd/mm/YYYY),or range as: start..end')

    def parse_args(self, argv):
        args_output = self.parser.parse_args(args=argv[1::])

        if args_output.start_date and args_output.end_date:
            if args_output.start_date > args_output.end_date:
                raise ValueError('start date is after end date')

        if args_output.proxy:
            args_output.proxy = {
                'http': args_output.proxy,
                'https': args_output.proxy
            }

        vacation_list = []
        for d in args_output.vacation:
            match = re.search(pattern=r'(?P<start>[\d\-]*)\.\.(?P<end>[\d\-]*)', string=d)
            if match:
                start_date = dt.datetime.strptime(match.group('start'), '%d-%m-%Y')
                end_date = dt.datetime.strptime(match.group('end'), '%d-%m-%Y')
                delta = end_date - start_date
                vacation_list.extend([start_date + dt.timedelta(days=x) for x in range(delta.days + 1)])
            else:
                vacation_list.extend([dt.datetime.strptime(d, '%d-%m-%Y')])

        args_output.vacation = vacation_list

        sick_list = []
        for d in args_output.sick:
            match = re.search(pattern=r'(?P<start>[\d\-]*)\.\.(?P<end>[\d\-]*)', string=d)
            if match:
                start_date = dt.datetime.strptime(match.group('start'), '%d-%m-%Y')
                end_date = dt.datetime.strptime(match.group('end'), '%d-%m-%Y')
                delta = end_date - start_date
                sick_list.extend([start_date + dt.timedelta(days=x) for x in range(delta.days + 1)])
            else:
                vacation_list.extend([dt.datetime.strptime(d, '%d-%m-%Y')])

        args_output.sick = sick_list
        return args_output


class VerifyDateFormatAction(argparse.Action):
    """
    Action subclass to verfiy that dates provided by cli are in the correct format.
    This class is callable.
    """
    DATE_FORMAT_LIST = ['d', 'm', 'Y']
    DATE_FORMAT_DIGIT_NUMS = [2, 2, 4]

    def __call__(self, parser, namespace, values, option_string=None):
        """
        Call function when this class is called.
        Checks that the format of the input 'values' (str) is correct - based on the class attributes:
        DATE_FORMAT_LIST - list of chars that comprise the format
        DATE_FORMAT_DIGIT_NUMS - number of repetitions of each char in DATE_FROMAT_LIST.

        If 'values' is provided in the correct format, A datetime object is created from 'values' string
        and passed into namespace. This datetime object will be passed subsequently in the 'args' tuple
        at the output of the argument parser function.

        :param parser: (parser object) that calls this callable
        :param namespace: (namespace object) into which args are provided
        :param values: (str) arguments provided by cli
        :param option_string: (str) not used in the instance
        :return: Nothing
        """
        try:
            tmp = dt.datetime.strptime(values, '%' + '-%'.join(self.DATE_FORMAT_LIST))
            setattr(namespace, self.dest, tmp)
        except ValueError:
            msg = '{} is not a a valid date. please use format: {}'.format(
                values, '-'.join(
                    [x * y for x, y in zip(self.DATE_FORMAT_LIST, self.DATE_FORMAT_DIGIT_NUMS)]))
            raise argparse.ArgumentTypeError(msg)
