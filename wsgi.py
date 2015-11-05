# TODO: linkify bug numbers in task descriptions


import os, json, re, glob
import sys
from wsgiref.simple_server import make_server
import mimetypes
from cgi import parse_qs, escape
from siteinfo import load_data, find_screenshot, get_test_steps_as_strings

def head_html(title):
  return str("""<!DOCTYPE html">
  <html>
  <head>

  <!--<script type="text/javascript" src="data/masterbugtable.js"></script>-->
  <script src="//www.mozilla.org/tabzilla/media/js/tabzilla.js"></script>
  <link href="//www.mozilla.org/tabzilla/media/css/tabzilla.css" rel="stylesheet" />
  <link rel="StyleSheet" lang="text/css" href="/css/main.css">
  <title>Are We Compatible Yet? - %s</title>
  </head>
  <div id="wrapper">
  <a href="http://www.mozilla.org/" id="tabzilla">mozilla</a>
  <h1>%s</h1>

  """ % (title,title))

serve_path_directly = [ '/timeline.html', '/screenshots/index.htm' ]
for fn in glob.glob( './data/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './data/testing/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './js/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './screenshots/js/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './screenshots/css/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './css/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './images/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './extensions/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))
for fn in glob.glob( './lists/*.*'):
  serve_path_directly.append(fn[1:].replace('\\', '/'))

def get_mime_type(f):
  m_type = mimetypes.guess_type(f)[0]
  if m_type is None:
    if '.json' in f:
      m_type = 'application/json'
    elif '.xpi' in f:
      m_type = 'application/x-xpinstall'
    elif '.ttf' in f:
      m_type = 'application/x-font-ttf'
    else:
      m_type = ''
  return m_type

# import - ish..
f = open('screenshots/headers.py', 'r')
exec(f)
f.close()

def buglist_to_table(title, list, the_data, output):
  if len(list) == 0:
    return
  output.append(str('<h2>%s</h2>\n<table>' % title))
  for bug in list:
    bug_data = the_data['masterbugtable']['bugs'].get(str(bug))
    steps = get_test_steps_as_strings(the_data['tests_parsed'], bug)
    test_result = the_data['test_results'].get(str(bug))
    output.append(str('<tr class="bug"><td><a href="%s">%s</a></td><td><a href="%s">%s</a></td><td>%s</td><td>%s</td></tr>' % (bug_data['link'], bug_data['id'], bug_data['link'], bug_data['summary'], bug_data['status'], bug_data.get('resolution', ''))))
    if test_result:
      if test_result['test_state'] == 'false':
        test_result['test_state'] = 'Failed'
      elif test_result['test_state'] == 'true':
        test_result['test_state'] = 'Passed'
      output.append(str('<tr><th style="text-align:left">Tested: </th><td colspan="3">%s, Result: <b>%s</b></td></tr>' % (test_result['test_date'], test_result['test_state'])))
    if steps:
      output.append(str('<tr><th style="text-align:left">Test code: </th><td colspan="3"><pre>%s</pre></td></tr>' % str('\n'.join(steps))))
  output.append('</table>')
# The first argument passed to the function
# is a dictionary containing CGI-style envrironment variables and the
# second variable is the callable object (see PEP 333).
def arewecompatibleyet(environ, start_response):
  parameters = parse_qs(environ.get('QUERY_STRING', ''))
  output=[]
  print( environ['PATH_INFO'])
  sys.stdout.flush()
  if environ['PATH_INFO'] is '/':
    f = open('timeline.html', 'r')
    contents = f.read()
    f.close()
    headers = [('Content-type', 'text/html;charset=utf-8'), ('X-served-with', 'wsgi.py')]
    start_response('200 OK', headers)
    return [contents]

  if environ['PATH_INFO'] in serve_path_directly:
    # sigh.. we tried --static-map configuration, but it seems we have to serve this "manually" anyway
    m_type = get_mime_type(environ['PATH_INFO'])
    if 'text/' in m_type:
      m_type += ';charset=utf-8'
    headers = [('Content-type', m_type), ('X-served-with', 'wsgi.py')]
    start_response('200 OK', headers)
    f = open('.'+environ['PATH_INFO'], 'r')
    contents = f.read()
    f.close()
    return [contents]

  status = '200 OK' # HTTP Status
  headers = [('Content-type', 'text/html;charset=utf-8')] # HTTP Headers
  start_response(status, headers)
  f = open('data/masterbugtable.js', 'r')
  f.seek(89)
  data = json.loads(f.read())
  f.close()
  if environ['PATH_INFO'] == '/newsite':
    f = open('data/toplists.js', 'r')
    f.seek(61)
    #return f.read()
    lists = json.loads(f.read())
    f.close()
    output = [head_html('Site lists')]
    output.append('<ul>')
    for lst in lists:
      num_sites = len(data['lists'][lst['id']]['data'])
      output.append(str('<li><a href="lists/%s.html">%s</a>'%(str(lst['id']), str(lst['name']))))

    output.append('</ul>')
  elif '/taskdetails/' in environ['PATH_INFO']:
    # task types: check, writetest, contact, recontact, analyze, regcheck
    the_type = sanitize(parameters['type'][0])
    the_bug = sanitize(parameters['bug'][0])
    the_link = sanitize(parameters['link'][0])
    the_desc = sanitize(parameters['desc'][0])
    the_host = sanitize(parameters['host'][0])
    output.append(head_html(the_desc))
    output.append('<p>Thank you and welcome! We need your help. This is a small guide to how to complete your task - if you already know what to do, simply <a href="%s">jump right in</a>!</p>' % the_link)
    #output.append('<h2>%s</h2>' % the_desc)
    if 'webcompat.com' in the_link or 'github.com' in the_link or the_type == 'writetest':
      output.append('<p><b>Before you start</b>: for this task you need a <a href="https://github.com">GitHub</a> account. If you don\'t have one, please register before you continue.</p>')
    elif 'bugzilla.mozilla.org' in the_link:
      output.append('<p><b>Before you start</b>: for this task you need a <a href="https://bugzilla.mozilla.org">Bugzilla</a> account. If you don\'t have one, please register before you continue.</p>')
    if the_type == 'check' or the_type == 'regcheck':
      output.append('<h3>Howto</h3>')
      output.append('<ol>\n<li>Load <a href="%s">the bug report</a>, check the description\n<li>Visit the website and see if you can find the problem \n<li>Leave a comment in the bug report explaining if you found it or not' % the_link)
      if the_type == 'regcheck':
        output.append('<li>The bug report is likely closed. If you find the problem, re-open it.\n<li>If you don\'t see a way to reopen the bug, make sure to say so in the comment and somebody will help you.')
        output.append('<li>If you <b>don\'t</b> see any problem, we need to fix the test. Comment in the bug that the test needs fixing.')
      output.append('</ol>')
    elif the_type == 'findcontact':
      output.append('<h3>Howto</h3>')
      output.append('<p><a href="%s">The bug report</a> should explain what the site needs to know. Your task is to reach out and try to find a contact that can help us fix the website.</p>' % the_link)
      output.append('<ol>')
      if the_host in data['hostIndex']:
        if len(data['hostIndex'][the_host]['resolved']) > 0:
            output.append('<li><b>Pro tip:</b> Look at old, resolved bugs <a href="/site/%s">listed here</a> - if we contacted them already, closed bugs may have useful contact details' % the_host)
            # the below loop does not actually work, and I have absolutely no idea why..
        for bug_number in data['hostIndex'][the_host]['resolved']:
            output.append('<li>..indeed, we may already have contacted this site about <a href="%s">bug %s</a>. Check if that bug has contact details!' % (bug_number, data['bugs'][str(bug_number)]['link']))
      output.append('<li>You can look for "Contact us" forms or E-mail addresses on the site..')
      output.append('<li>..you can try to find developers for the site on GitHub or LinkedIn..')
      output.append('<li>..you can look for the site\'s accounts on Twitter or Facebook..')
      output.append('<li>Once you\'ve found a promising way to contact the site, add a comment to the bug with this information.')
      if 'webcompat.com' in the_link or 'github.com' in the_link:
        output.append('<li>Please also remove the <b>needscontact</b> label and add a <b>contactready</b> label')
      elif 'bugzilla.mozilla.org' in the_link:
        output.append('<li>Please also remove [needscontact] and add [contactready] to the Whiteboard field if Bugzilla lets you do so. (If not just comment and someone will help)')
      output.append('</ol>')
    elif the_type == 'contact' or the_type == 'recontact':
      output.append('<h3>Howto</h3>')
      output.append('<p><a href="%s">The bug report</a> should explain what the site needs to know. Your task is to reach out to get them to fix the website.</p>' % the_link)
      output.append('<p>The bug should already have some information about how to contact the site. Now try to write a polite letter..</p>')
      output.append('<ol>')
      if the_type == 'recontact':
        output.append('<li>(We already tried to contact the site, but the problem seems to still be there.. Maybe find another contact?)')
        output.append('<li>(It\'s probably a good idea to first check if they fixed the problem already without telling us. It happens..)</li>')
      output.append('<li>You may find <a href="https://wiki.mozilla.org/Compatibility/StdLetters">our letter templates</a> useful')
      output.append('<li>Say who you are, that you volunteer for Firefox, and that you\'re trying to reach a web developer')
      if 'webcompat.com' in the_link or 'github.com' in the_link:
        output.append('<li>Make sure you include the bug report link, <b>%s</b> '%the_link)
        output.append('<li>Having sent a request to the site, please comment on the bug and add a <b>sitewait</b> label')
      elif 'bugzilla.mozilla.org' in the_link:
        output.append('<li>Please include this link: <b>https://webcompat.com/simplebug/index.html#mozilla/%s</b>' % the_bug)
        output.append('<li>Having sent a request to the site, please comment on the bug and add [sitewait] to the Whiteboard field if Bugzilla lets you do so. (If not just comment and someone will help)')
      output.append('</ol>')
    elif the_type == 'writetest':
      output.append('<p>Hey, cool! You want to write a test? A test is a small JavaScript that will return false if the problem exists, true if it is fixed.</p>')
      output.append('<ol><li>Have a look at <a href="https://github.com/hallvors/sitecomptester-extension/blob/master/README.md#writing-tests">the documentation</a>')
      output.append('<li>Start by cloning the <a href="https://github.com/hallvors/sitecomptester-extension/">sitecomptester-extension</a> repository on GitHub')
      output.append('<li>Study the <a href="%s">bug report</a> and make sure you understand the problem' % the_link)
      output.append('<li>Use two instances of Firefox, one of which is spoofing as the browser affected by the bug, and one spoofing as a browser that gets the content we want')
      output.append('<li>See if you can come up with a script that says "true" when ran in the console of the "right content" browser but "false" in the other one')
      output.append('<li>Add that script with the required meta data at the top of <a href="https://github.com/hallvors/sitecomptester-extension/blob/master/data/sitedata.js">sitedata.js</a> and create a pull request')
      output.append('</ol>')
    elif the_type == 'analyze':
      output.append('<p>You rock! Plenty of sites need some help figuring out why they are broken.</p>')
      output.append('<ol>')
      output.append('<li>If possible, load the site in two browsers, one where it works and one where it fails')
      output.append('<li>Study the <a href="%s">bug report</a> and make sure you understand the problem' % the_link)
      output.append('<li>Use the developer tools to investigate. Good luck!')
      output.append('<li>Comment in the bug when you found the cause. If you\'re confident you\'ve found it.. ')
      if 'webcompat.com' in the_link or 'github.com' in the_link:
        output.append(' add a <b>contactready</b> label')
      elif 'bugzilla.mozilla.org' in the_link:
        output.append(' add [contactready] to the Whiteboard field if Bugzilla lets you do so. (If not just comment and someone will help)')
      output.append('</ol>')
  elif '/site/' in environ['PATH_INFO']:
    site = environ['PATH_INFO'][6:].strip()
    output.append(head_html(site))
    the_data = load_data()
    ss = find_screenshot(the_data['masterbugtable'], site)
    if ss:
      output.append(str('<p><img src="%s" alt="Comparison screenshots of %s"></p>' % (ss, site)))
    if site in the_data['masterbugtable']['hostIndex']:
      buglist_to_table('Open bugs', the_data['masterbugtable']['hostIndex'][site]['open'], the_data, output)
      buglist_to_table('Closed bugs', the_data['masterbugtable']['hostIndex'][site]['resolved'], the_data, output)
    else:
      output.append('<p>No information known about this site.</p>')
#    data = data['lists'][site]
#    output.append('<ul>')
#    for domain in data['data']:
#      output.append('<li><a href="/sites/%s">%s</a>' % (domain, domain))
#    output.append('<pre>')
#    output.append(json.dumps(data, indent=4))
  elif 'screenshots/headers.py' in environ['PATH_INFO']:
    url = parameters['url'][0]
    if not '://' in url:
      url = 'http://%s'%url
    return check_url(url)

  return output

def sanitize(dirty_html):
  dirty_html = dirty_html.replace('&', '&amp;')
  dirty_html = dirty_html.replace('<', '&lt;')
  dirty_html = dirty_html.replace('>', '&gt;')
  dirty_html = dirty_html.replace('"', '&quot;')
  return dirty_html


application = arewecompatibleyet


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    srv = make_server('localhost', port, application)
    srv.serve_forever()
