import redis
import re
import json
import time
import string
import random
import requests
import urbdict
from slackclient import SlackClient

r = redis.StrictRedis(host='localhost', port=6379, db=0)

common_words = ['the', 'be', 'to', 'of', 'and', 'a', 'in',
                'that', 'have', 'I', 'it', 'for', 'not',
                'on', 'with', 'he', 'as', 'you', 'do', 'at',
                'this', 'but', 'his', 'by', 'from', 'they',
                'we', 'say', 'her', 'she', 'or', 'an', 'will',
                'my', 'one', 'all', 'would', 'there', 'their',
                'what', 'so', 'up', 'out', 'if', 'about',
                'who', 'get', 'which', 'go', 'me', 'when',
                'make', 'can', 'like', 'time', 'no', 'just',
                'him', 'know', 'take', 'person', 'into', 'year',
                'your', 'good', 'some', 'could', 'them', 'see',
                'other', 'than', 'then', 'now', 'look', 'only',
                'come', 'its', 'over', 'think', 'also', 'back',
                'after', 'use', 'two', 'how', 'our', 'work',
                'first', 'well', 'way', 'even', 'new', 'want',
                'because', 'any', 'these', 'give', 'day', 'most',
                'us', 'are' 'aren\'t', 'haven\'t', 'you\'ve',
                'is', 'got']

common_words = set([i.upper() for i in common_words])
print "common words = " + str(common_words)
class LoudHailer(object):
  uppercase   = frozenset(string.uppercase)
  all_caps    = re.compile('^[A-Z\d\s\!\@\#\$\%\^\&\*'+
                         '\(\)\_\+\-\=\[\]\{\}\|\;\''+
                         '\:\"\,\.\/\<\>\?]*$')
  hey_user    = re.compile('^\<\@[A-Z0-9]*\>\: ')

  def num_uppercase(self, loud):
    return sum(1 for c in message if c in self.uppercase)
  
  def get_loud(self, domain, channel):
    response = r.srandmember('louds')
    r.hset('loudlast', 
           domain+'/'+channel, 
           response)
    return response
    
  def do_commands(self, command, user, domain, channel):
    def do_help(user, domain, channel, args):
      return "```" + \
             "!help          - This help message.\n" + \
             "!define <term> - Look it up in your Funk & Wagnall's.\n" + \
             "!reward        - Give a point to the last loud.\n" + \
             "!punish        - Take a point from last loud.\n" + \
             "!hitme         - Returns a random loud.\n" + \
             "!whosay       - Who said the last loud returned by 2louder.\n" + \
             "!gifit         - Get a giphy gif from the last loud.\n" + \
             "```" 
    
    def do_definition(user, domain, channel, args):
      return urbdict.define(args) 

    def do_reward(user, domain, channel, args):
      key = r.hget('loudlast', domain+'/'+channel)
      if key:
        points = r.hget('loudpoints', key)
        if not points:
          points = 1
        else:
          points = int(points) + 1
        r.hset('loudpoints', key, points)
    
    def do_punish(user, domain, channel, args):
      key = r.hget('loudlast', domain+'/'+channel)
      if key:
        points = r.hget('loudpoints', key)
        if not points:
          points = -1
        else:
          points = int(points) - 1
        r.hset('loudpoints', key, points)
         
    def do_hitme(user, domain, channel, args):
      return self.get_loud(domain, channel)

    def do_whosay(user, domain, channel, args):
      print domain+'/'+channel
      key = r.hget('loudlast', domain+'/'+channel)
      if key:
        info   = r.hget('loudinfo', key)
        points = r.hget('loudpoints',key)

        if not points:
          points = 0
        else:
          points = int(points)

        if info:
          info    = json.loads(info)
          user    = info[0].upper()
          domain  = info[1].upper()
          channel = info[2].upper()
          return "brother %s said that in %s-%s (scoring %d points)" % (user,    domain,
                                                                        channel, points) 
    
    def do_loud_gif(user, domain, channel, args):
      loud = r.hget('loudlast', domain+'/'+channel)
      if not loud:
        return None
      else:
        words  = set(loud.split(" "))
        sample = list(words.difference(common_words))[0:5]
        print "sample = " + str(sample)

      url ='http://api.giphy.com/v1/gifs/search?'

      if loud:
        payload = {'q': "+".join(sample), 'api_key': 'dc6zaTOxFJmzC'}
      else:
        return "Papa broke the redis!"

      try:
        req = requests.get(url, params=payload)
      except:
        return "Had trouble getting that sweet gif!"

      try:
        json_response = req.json()
        json_response_sample = random.choice(json_response['data'])
        return json_response_sample['images']['downsized_medium']['url']
      except:
        return "Whoa bud, that gif json didn't parse!"

    args     = command.split(' ')
    command  = args[0].strip().lower()
    args     = ' '.join(args[1:])
    
    commands = { '!help':    do_help,
                 '!define':  do_definition,
                 '!reward':  do_reward,
                 '!punish':  do_punish,
                 '!hitme':   do_hitme,
                 '!whosay': do_whosay,
                 '!gifit':   do_loud_gif, }

    if command in commands:
      return commands[command](user,domain, channel, args)
    else:
      return None

  def add(self, loud, user, domain, channel):
    if re.match(self.hey_user, loud):
      return None
    if self.num_uppercase(loud) <= 4:
      return None
    if re.match(self.all_caps, loud):
      response = self.get_loud(domain, channel)

      if not r.sismember('louds',loud):
        r.sadd('louds',loud)
        r.hset('loudinfo', 
               loud, 
               json.dumps([user, domain, channel]))

      return response
    else:
      return None



def convert_to_dict(items_list):
  return {i.id : i for i in items_list}

def get_dict_item(cur_dict, item, search_list):
  if item not in cur_dict:
    cur_dict = convert_to_dict(search_list)
  if item not in cur_dict:
    return "unknown"
  else:
    return cur_dict[item]

with open('sekrit','r') as sekrit_file:
  token = sekrit_file.readline().strip()

print token

louds     = LoudHailer()

sc = SlackClient(token)

if sc.rtm_connect():
  for i in xrange(0,10):
    time.sleep(1)

  users = convert_to_dict(sc.server.users)
  channels = convert_to_dict(sc.server.channels)

  while True:
    for response in sc.rtm_read():
      if 'type' in response and response['type'] == 'message':
        try:
          message = response['text']
          user    = get_dict_item(users, 
                                  response['user'], 
                                  sc.server.users).name
          channel = get_dict_item(channels, 
                                  response['channel'], 
                                  sc.server.channels).name
          domain  = get_dict_item(channels, 
                                  response['channel'], 
                                  sc.server.channels).server.domain
        except:
          continue 
        print "%s (%s/%s) -- %s" % (user, domain, channel, message)

        loud_response = louds.add(message, user, domain, channel)

        if loud_response:
          sc.rtm_send_message(response['channel'], loud_response)
          print "           -- %s" % loud_response
          

        command_response = louds.do_commands(message,user,domain,channel)
        if command_response:
          sc.rtm_send_message(response['channel'], command_response)
          print "           -- %s" % command_response

        
    time.sleep(1)
else:
  print "Can't connect to  Slack?!?"
