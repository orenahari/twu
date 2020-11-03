import twlog
import twargs

import web
import parameters
import sys
import time

t = time.time()
logger = twlog.TimeWatchLogger()
logger.info('Start')

a = twargs.TWArgs()
args = a.parse_args(sys.argv)
params = parameters.Parameters()
time_watch = web.Timewatch(start_date=args.start_date, end_date=args.end_date,
                           overwrite=args.overwrite,
                           vacation_list=args.vacation,
                           sick_list=args.sick)

time_watch.login(
    user=params.user['worker'],
    company=params.user['company'],
    password=params.user['password'],
    proxies=args.proxy)
time_watch.fill()

logger.info('Finished in {:.2f} seconds'.format(time.time() - t))
