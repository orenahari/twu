import work
import datetime as dt


def test_kml_file_url_is_correct():
    k_general = work.KMLFile(file_date=dt.datetime(year=2020, month=7, day=16))
    assert k_general.timeline_url == 'https://www.google.com/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i2020!2i6!3i16!2m3!1i2020!2i6!3i16'

    k_end_of_year = work.KMLFile(file_date=dt.datetime(year=2020, month=12, day=31))
    assert k_end_of_year.timeline_url == 'https://www.google.com/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i2020!2i11!3i31!2m3!1i2020!2i11!3i31'

    k_start_of_year = work.KMLFile(file_date=dt.datetime(year=2021, month=1, day=3))
    assert k_start_of_year.timeline_url == 'https://www.google.com/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i2021!2i0!3i3!2m3!1i2021!2i0!3i3'