import ConfigParser
import datetime
import os

import tornado.httpserver
import tornado.ioloop
import tornado.web

import googleanalytics as ga
import bitly_api
from pyslideshare import pyslideshare

config = ConfigParser.ConfigParser()
config.readfp(open(os.path.expanduser('~/.protoboard')))

# Google Analytics API
TABLE_ID = config.get('Google Analytics', 'table_id')
GA_ACCOUNT = ga.Connection().get_account(TABLE_ID)

# Bit.ly API
BITLY_LOGIN = config.get('Bit.ly', 'login')
BITLY_API_KEY = config.get('Bit.ly', 'api_key')
BITLY_CONN = bitly_api.Connection(BITLY_LOGIN, BITLY_API_KEY)

# Slideshare API
SS_API_KEY = config.get('Slideshare', 'api_key')
SS_SECRET_KEY = config.get('Slideshare', 'secret_key')
SS_USERNAME = config.get('Slideshare', 'username')
SS_PASSWORD = config.get('Slideshare', 'password')
SS_PARAMS = {'api_key': SS_API_KEY,
             'secret_key': SS_SECRET_KEY,
             'username': SS_USERNAME,
             'password': SS_PASSWORD}
SS_CONN = pyslideshare.pyslideshare(SS_PARAMS, verbose=False)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        # Google Analytics
        start_date = datetime.date(2010, 07, 01)
        end_date = datetime.date.today() - datetime.timedelta(1)
        ga_data = str([item[1][0] for item in GA_ACCOUNT.get_data(start_date, end_date, metrics=['pageviews'], dimensions=['date']).list])

        # Bit.ly
        bitly_data = [{'link': item['url'], 'clicks': str(BITLY_CONN.clicks(shortUrl=item['short_url'])[0]['global_clicks'])} for item in BITLY_CONN.history()]
        bitly_data.sort(lambda x, y: int(x['clicks']) > int(y['clicks']) and -1 or 1)        

        # Slideshare
        ss_data = [{'title': show.Title, 'views': show.Views} for show in SS_CONN.get_slideshow_by_user(username_for='cloudera').User.Slideshow]
        ss_data.sort(lambda x, y: int(x['views']) > int(y['views']) and -1 or 1)

        self.render("index.html",
                    ga_data=ga_data,
                    bitly_data=bitly_data,
                    ss_data=ss_data)

def main():
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()

