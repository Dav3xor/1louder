import redis
import re
import json
import time
import string
import random
import requests
from slackclient import SlackClient

r = redis.StrictRedis(host='localhost', port=6379, db=0)


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
    def do_help(user, domain, channel):
      return "```" + \
             "!help      - This help message.\n" + \
             "!reward    - Give a point to the last loud.\n" + \
             "!punish    - Take a point from last loud.\n" + \
             "!hitme     - Returns a random loud.\n" + \
             "!saywhat   - Who said the last loud returned by 2louder.\n" + \
             "!gifit     - Get a giphy gif from the last loud.\n" + \
             "```" 

    def do_reward(user, domain, channel):
      key = r.hget('loudlast', domain+'/'+channel)
      if key:
        points = r.hget('loudpoints', key)
        if not points:
          points = 1
        else:
          points = int(points) + 1
        r.hset('loudpoints', key, points)
    
    def do_punish(user, domain, channel):
      key = r.hget('loudlast', domain+'/'+channel)
      if key:
        points = r.hget('loudpoints', key)
        if not points:
          points = -1
        else:
          points = int(points) - 1
        r.hset('loudpoints', key, points)
         
    def do_hitme(user, domain, channel):
      return self.get_loud(domain, channel)

    def do_saywhat(user, domain, channel):
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
    
    def do_loud_gif(user, domain, channel):
      loud = r.hget('loudlast', domain+'/'+channel)
      if loud:
        sample = loud.split(" ")[0:5]

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

    command  = command.strip().lower()
    commands = { '!help':    do_help,
                 '!reward':  do_reward,
                 '!punish':  do_punish,
                 '!hitme':   do_hitme,
                 '!saywhat': do_saywhat,
                 '!gifit':   do_loud_gif, }

    if command in commands:
      return commands[command](user,domain, channel)
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

        if loud_response and user != '2louder' and user != 'eletest':
          sc.rtm_send_message(response['channel'], loud_response)
          print "           -- %s" % loud_response
          

        command_response = louds.do_commands(message,user,domain,channel)
        if command_response:
          sc.rtm_send_message(response['channel'], command_response)
          print "           -- %s" % command_response

        
    time.sleep(1)
else:
  print "Can't connect to  Slack?!?"
