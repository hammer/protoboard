import ConfigParser
import datetime
import os

import tornado.httpserver
import tornado.ioloop
import tornado.web

# API Clients
import googleanalytics as ga
import bitly_api
from pyslideshare import pyslideshare
import twython.core as twython
import satisfaction

# Modules needed for hand-crafted Zendesk client
from tornado import httpclient
import pycurl
import simplejson

# Modules needed for hand-crafted JIRA client
from suds.client import Client

config = ConfigParser.ConfigParser()
config.readfp(open(os.path.expanduser('~/.protoboard')))

# Google Analytics
TABLE_ID = config.get('Google Analytics', 'table_id')
try:
  GA_ACCOUNT = ga.Connection().get_account(TABLE_ID)
  GA_EXISTS = True
except:
  GA_EXISTS = False

# Bit.ly
BITLY_LOGIN = config.get('Bit.ly', 'login')
BITLY_API_KEY = config.get('Bit.ly', 'api_key')
try:
  BITLY_CONN = bitly_api.Connection(BITLY_LOGIN, BITLY_API_KEY)
  BITLY_EXISTS = True
except:
  BITLY_EXISTS = False

# Slideshare
SS_API_KEY = config.get('Slideshare', 'api_key')
SS_SECRET_KEY = config.get('Slideshare', 'secret_key')
SS_USERNAME = config.get('Slideshare', 'username')
SS_PASSWORD = config.get('Slideshare', 'password')
SS_PARAMS = {'api_key': SS_API_KEY,
             'secret_key': SS_SECRET_KEY,
             'username': SS_USERNAME,
             'password': SS_PASSWORD}
try:
  SS_CONN = pyslideshare.pyslideshare(SS_PARAMS, verbose=False)
  SS_EXISTS = True
except:
  SS_EXISTS = False

# Twitter
TWITTER_USERNAME = config.get('Twitter', 'username')
TWITTER_PASSWORD = config.get('Twitter', 'password')
try:
  TWITTER_CONN = twython.setup(username=TWITTER_USERNAME, password=TWITTER_PASSWORD)
  TWITTER_EXISTS = True
except:
  TWITTER_EXISTS = False

# Zendesk
ZD_USERNAME = config.get('Zendesk', 'username')
ZD_PASSWORD = config.get('Zendesk', 'password')
ZD_FORUMS_URL = 'http://cloudera.zendesk.com/forums.json'
ZD_ENTRIES_URL = 'http://cloudera.zendesk.com/forums/%(id)s/entries.json?page=%(page)s'
ZD_ENTRY_URL = 'http://cloudera.zendesk.com/entries/%(id)s'

# JIRA
JIRA_USERNAME = config.get('JIRA', 'username')
JIRA_PASSWORD = config.get('JIRA', 'password')
JIRA_WSDL = 'http://issues.cloudera.org/rpc/soap/jirasoapservice-v2?wsdl'
JQL_LAST_MODIFIED = 'project = %(project)s AND status not in (Closed, Resolved) \
                     ORDER BY updated DESC, key DESC'
JIRA_CLIENT = Client(JIRA_WSDL)
try:
  JIRA_AUTH_TOKEN = JIRA_CLIENT.service.login(JIRA_USERNAME, JIRA_PASSWORD)
  JIRA_EXISTS = True
except:
  JIRA_EXISTS = False

GS_COMPANY = config.get('Get Satisfaction', 'company')
try:
  GS_CONN = satisfaction.Company('cloudera')
  GS_EXISTS = True
except:
  GS_EXISTS = False

# TODO(hammer): Move to async HTTP client
# TODO(hammer): Add API call to HTTP client to ignore bad certs
# TODO(hammer): Make Zendesk Python client
def get_zendesk_data():
  blocking_http_client = httpclient.HTTPClient()
  blocking_http_client._curl.setopt(pycurl.SSL_VERIFYPEER, 0)

  # Get the list of forums
  response = blocking_http_client.fetch(ZD_FORUMS_URL,
                                        auth_username=ZD_USERNAME,
                                        auth_password=ZD_PASSWORD)
  forums = simplejson.loads(response.buffer.read())
  
  # Get each entry in each forum
  all_entries = []
  for forum in forums:
    # Zendesk paginates forum entries; need to fetch all pages
    page = 1
    while True:
      response = blocking_http_client.fetch(ZD_ENTRIES_URL % {'id': forum['id'], 'page': page},
                                            auth_username=ZD_USERNAME,
                                            auth_password=ZD_PASSWORD)
      new_entries = simplejson.loads(response.buffer.read())
      if not new_entries: break
      for new_entry in new_entries:
        all_entries.append({'forum': forum['name'],
                            'title': new_entry['title'],
                            'hits': str(new_entry['hits']),
                            'url': ZD_ENTRY_URL % new_entry})
      page += 1
  all_entries.sort(lambda x, y: int(x['hits']) > int(y['hits']) and -1 or 1)

  # only returning top 20, for now
  return all_entries[:20]

def get_url_from_gs_topic(topic):
  links = topic.entry.links
  for link in links:
    if link['rel'] == u'topic_at_sfn':
      return link['href']

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
    if GA_EXISTS:
      start_date = datetime.date(2010, 07, 01)
      end_date = datetime.date.today() - datetime.timedelta(1)
      ga_data = [item[1][0]
                 for item in GA_ACCOUNT.get_data(start_date, end_date, metrics=['pageviews'], dimensions=['date']).list]
    else:
      ga_data = []

    # Bit.ly
    if BITLY_EXISTS:
      bitly_data = [{'link': item['url'], 'clicks': str(BITLY_CONN.clicks(shortUrl=item['short_url'])[0]['global_clicks'])}
                    for item in BITLY_CONN.history()]
      bitly_data.sort(lambda x, y: int(x['clicks']) > int(y['clicks']) and -1 or 1)
      bitly_data = bitly_data[:5]
    else:
      bitly_data = []

    # Slideshare
    if SS_EXISTS:
      ss_data = [{'title': show.Title, 'views': show.Views}
                 for show in SS_CONN.get_slideshow_by_user(username_for='cloudera').User.Slideshow]
      ss_data.sort(lambda x, y: int(x['views']) > int(y['views']) and -1 or 1)
      ss_data = ss_data[:10]
    else:
      ss_data = []

    # Twitter
    if TWITTER_EXISTS:
      twitter_data = [{'username': mention['user']['screen_name'], 'tweet': mention['text']}
                      for mention in TWITTER_CONN.getUserMentions(count="10")]
    else:
      twitter_data = []

    # Zendesk
    zd_data = get_zendesk_data()
    zd_data = zd_data[:10]

    # JIRA
    # TODO(hammer): client.service.logout(JIRA_AUTH_TOKEN) needed?
    if JIRA_EXISTS:
      jql_params = {'project': 'Flume'}
      jira_data = [{'key': issue.key, 'summary': issue.summary}
                   for issue in JIRA_CLIENT.service.getIssuesFromJqlSearch(JIRA_AUTH_TOKEN, JQL_LAST_MODIFIED % jql_params, 10)]
    else:
      jira_data = []

    # Get Satisfaction
    if GS_EXISTS:
      gs_data = [{'title': topic.title, 'url': get_url_from_gs_topic(topic)}
                 for i, topic in enumerate(GS_CONN.topics)
                 if i < 10]
    else:
      gs_data = []

    self.render("index.html",
                ga_data=ga_data,
                bitly_data=bitly_data,
                ss_data=ss_data,
                twitter_data=twitter_data,
                zd_data=zd_data,
                jira_data=jira_data,
                gs_data=gs_data)

def main():
  http_server = tornado.httpserver.HTTPServer(Application())
  http_server.listen(8888)
  tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
  main()

