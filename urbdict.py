import urllib
import json
import random
import math
from   operator import itemgetter

url = 'http://api.urbandictionary.com/v0/define?term=%s'

output = """
*%s:*


_definition_\n%s """

example = "\n\n_example_\n%s"
def define(term):
  try:
    r = json.loads(urllib.urlopen(url % term).read())

    scores = [ [i, float((r['list'][i]['thumbs_up'])/float(r['list'][i]['thumbs_down']))*\
                   float((r['list'][i]['thumbs_up'])/float(r['list'][i]['thumbs_down'])) ] for i in xrange(len(r['list'])) ]
    scores = sorted(scores, key=itemgetter(0), reverse=True)

    if len(scores) >= 1:
      pick = int(math.floor(random.betavariate(3,1)*len(scores)))
      r = r[u'list'][scores[pick][0]]
      out = output % (term, r['definition'])    
      if 'example' in r:
        out += example % r['example'] 
      return out
  except:
    return "Shit's Broken!"

