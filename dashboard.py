import datetime
import os

import tornado.httpserver
import tornado.ioloop
import tornado.web

import googleanalytics as ga
import bitly_api

# TODO(hammer): Load API Auth information from a configuration file

# Google Analytics API
TABLE_ID = '' # without the 'ga:' prefix
GA_ACCOUNT = ga.Connection().get_account(TABLE_ID)

# Bit.ly API
BITLY_LOGIN = ''
BITLY_API_KEY = '' # retrieve from http://bit.ly/a/your_api_key
BITLY_CONN = bitly_api.Connection(BITLY_LOGIN, BITLY_API_KEY)

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
        start_date = datetime.date(2010, 07, 01)
        end_date = datetime.date(2010, 07, 20)
        ga_data = GA_ACCOUNT.get_data(start_date, end_date, metrics=['pageviews'], dimensions=['date'])
        bitly_data = [(item['url'], str(BITLY_CONN.clicks(shortUrl=item['short_url'])[0]['global_clicks'])) for item in BITLY_CONN.history()]
        self.render("index.html",
                    ga_data=str([item[1][0] for item in ga_data.list]),
                    bitly_data=bitly_data)

def main():
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()

