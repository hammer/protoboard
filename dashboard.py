import datetime
import os

import tornado.httpserver
import tornado.ioloop
import tornado.web

import googleanalytics as ga

TABLE_ID = '' # without the 'ga:' prefix
GA_ACCOUNT = ga.Connection().get_account(TABLE_ID)

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
        end_date = datetime.date.today()
        data = GA_ACCOUNT.get_data(start_date, end_date, metrics=['pageviews'], dimensions=['date'])
        self.render("index.html", data=str([item[1][0] for item in data.list]))

def main():
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()

