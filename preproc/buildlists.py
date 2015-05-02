#!/usr/bin/python
# -*- coding: utf-8 -*-
# Other possible sources of tech evang bugs:
# http://code.google.com/p/chromium/issues/csv?can=2&q=label%3ANeeds-Evangelism&colspec=ID%20Pri%20M%20Iteration%20ReleaseBlock%20Cr%20Status%20Owner%20Summary%20OS%20Modified
# https://bugs.webkit.org/buglist.cgi?bug_file_loc=&bug_file_loc_type=allwordssubstr&bug_id=&bug_status=UNCONFIRMED&bug_status=NEW&bug_status=ASSIGNED&bug_status=REOPENED&bugidtype=include&chfieldfrom=&chfieldto=Now&chfieldvalue=&component=Evangelism&email1=&email2=&emailassigned_to1=1&emailassigned_to2=1&emailcc2=1&emailreporter2=1&emailtype1=substring&emailtype2=substring&field-1-0-0=component&field-1-1-0=bug_status&field0-0-0=noop&keywords=&keywords_type=allwords&long_desc=&long_desc_type=substring&query_format=advanced&remaction=&short_desc=&short_desc_type=allwordssubstr&type-1-0-0=anyexact&type-1-1-0=anyexact&type0-0-0=noop&value-1-0-0=Evangelism&value-1-1-0=UNCONFIRMED%2CNEW%2CASSIGNED%2CREOPENED&value0-0-0=&ctype=csv
# https://bazaar.launchpad.net/~phablet-team/webbrowser-app/trunk/view/head:/src/Ubuntu/Components/Extras/Browser/ua-overrides.js
# Browser.js for Opera (from Github)
# https://github.com/operasoftware/browserjs/blob/master/OPRdesktop/
# https://github.com/operasoftware/browserjs/blob/master/desktop/spoofs.xml (old!)
# IE's compatview lists

#TODO Static pages :

# show misc test data?
# "maybe" issues? "site x had different redirects for different UAs, no bug is reported (yet)"
# hook screenshot review into /sites/example.com pages?


import json, glob, urllib, os, urllib2,csv,StringIO,re, sys, time
from pprint import pprint
from urlparse import urlparse
import socket
socket.setdefaulttimeout(240) # Seconds. Loading Bugzilla searches can be slow
import tldextract
import cgi
import pdb
from datetime import datetime
from webcompat_data_exporter import get_webcompat_data

stackato_fs_path = os.environ.get('STACKATO_FILESYSTEM') # path to files or None

os.chdir(os.path.dirname(os.path.abspath(__file__))) # For CRON usage..
# We generally want to handle the main domains (i.e. google.com for www.google.com) instead of the full host names
# however, for some major sites with lots of distinct properties we loose too much useful information if we classify it just by domain name..
# conf['weWantSubdomainsFor'] is a list of hostnames that should not be reduced to domain names. For these, we'll strip any *www.* prefix, but
# no other subdomains. (Another option is to only strip www - might work too)
conf = { 'weWantSubdomainsFor': r'(\.google\.com|\.live\.com|\.yahoo\.com|go\.com|\.js$)',  # the latter is not, strictly speaking, a subdomain..
'load_remote_bz_data': True, 'load_webcompat_bugs': True }


# http://stackoverflow.com/questions/8230315/python-sets-are-not-json-serializable :-(
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
       if isinstance(obj, set):
          return list(obj)
       return json.JSONEncoder.default(self, obj)

f = open('data/aliases.json')
aliases = json.load(f)
f.close()

masterBugTable = {'hostIndex':{}, 'bugs':{}, 'lists':{}}

def prep_action_links(action_links):
	if len(action_links) == 0:
		return ''
	return '<br>How you can help: %s' % ' | '.join(action_links)

def sanitize(dirty_html):
	dirty_html = dirty_html.replace('&', '&amp;')
	dirty_html = dirty_html.replace('<', '&lt;')
	dirty_html = dirty_html.replace('>', '&gt;')
	dirty_html = dirty_html.replace('"', '&quot;')
	return dirty_html

def link_bug(text, link):
	match = re.search('\d+$', link)
	if match:
		bugnr = match.group(0)
		text = text.replace(bugnr, '<a href="%s">%s</a>' % (link, bugnr))
	return text

def main():
	if conf['load_remote_bz_data']:
		urltemplate = 'https://bugzilla.mozilla.org/bzapi/bug?component=Mobile&product=Tech%20Evangelism&component=Desktop&include_fields=id,summary,creation_time,last_change_time,status,resolution,depends_on,whiteboard,cf_last_resolved,url,priority,op_sys' # removed ",flags" to work around bugzilla bug..
		bzdata = get_remote_file(urltemplate, True)
		try:
			f = open('data/bz-cache.json', 'w')
			f.write(bzdata)
			f.close()
		except:
			pass
		bzdataobj = json.loads(bzdata)
	else:
		print('Warning: using cached bzdata')
		f = open('data/bz-cache.json', 'r')
		bzdataobj = json.load(f)
		f.close()
	# Make sure we record that these bugs are from Bugzilla..
	for bug in bzdataobj['bugs']:
		bug['link'] = 'https://bugzilla.mozilla.org/show_bug.cgi?id=%s' % bug['id']
		bug['test_id'] = '%s' % bug['id'] # Bugzilla issues are referenced by bug number in sitedata.js
		if '[sitewait]' in bug['whiteboard']:
			bug['last_contacted'] = find_last_contacted_date(bug['id'])
	if conf['load_webcompat_bugs']:
		# merge in webcompat.com data
		webcompat_data = get_webcompat_data()[1]
		try:
			f = open('data/wc-cache.json', 'w')
			f.write(json.dumps(webcompat_data).encode('utf_8'))
			f.close()
		except:
			print('wot?')
	else:
		print('Warning: using cached webcompat data')
		f = open('data/wc-cache.json', 'r')
		webcompat_data = json.load(f)
		f.close()

	for bug in webcompat_data['bugs']:
		if 'firefox' not in bug['whiteboard']:
			continue
		bug['link'] = 'https://webcompat.com/issues/%s' % bug['id']
		bug['test_id'] = 'wc%s' % bug['id'] # webcompat.com issues are referenced by wc plus bug number in sitedata.js
		bzdataobj['bugs'].append(bug)

	# Read list names (toplists.js)
	f = open('../data/toplists.js', 'r')
	tmp = f.read()
	f.close()
	list_details = json.loads(tmp[tmp.index('['):])
	# find and process latest test data
	f = open('../data/testing/index.json', 'r')
	tmp = f.read()
	f.close()
	test_file_index = json.loads(tmp)
	f = open('../data/testing/%s' % test_file_index[-1], 'r')
	test_data = {}
	test_reader = csv.reader(f)
	for line in test_reader:
		test_data[line[0]] = {"bug":line[0], "test_date":line[1], "ua":line[2], "test_state":line[3]}
	f.close()
	# reading our lists of regionally important sites
	for fn in glob.glob('..' + os.sep +'data' + os.sep + '*.json'):
		f = open(fn)
		data = json.load(f)
		f.close()
		listname = os.path.splitext(os.path.basename(fn))[0]
		# get the pretty name for this list too
		tmp = find_list_details(listname, list_details)
		data['fancyname'] = tmp['name']
		if listname:
			masterBugTable['lists'][listname] = data
			masterBugTable['lists'][listname]['metrics']={'numOpenBugs':0, 'numClosedBugs':0, 'numHostsWithOpenBugs': 0}
		f.close()
	metrics={'allOpenBugsForAllLists':set(), 'hostsWithOpenBugs':set(), 'totalUniqueHosts':set()}

	# The U.S. dominates the internet for sure - but local lists become much less interesting
	# with all the Google and Facebook issues repeated everywhere. Let's pretend U.S. 50 aren't
	# dominant in local markets..
	for domain in masterBugTable['lists']['us50']['data']:
		for listname in masterBugTable['lists']:
			# if listname != 'us50' and listname != '1000':
			if 'ccTLD' in masterBugTable['lists'][listname]:
				try:
					masterBugTable['lists'][listname]['data'].remove(domain)
				except:
					pass

	for bug in bzdataobj['bugs']:
		if re.search(r'\[meta\]', bug['summary'], re.I) : # We don't care about [meta] stuff. Why? Well, we're post-post-modern, that's why.
			continue
		masterBugTable['bugs'][bug['test_id']] = bug;
		# extract host names:
		hostnames = set()
		if 'url' in bug:
			hostnames = hostsFromText(bug['url']) # extract host name from URL field
		if 'summary' in bug:
			hostnames = hostnames.union(hostsFromText(bug['summary'])) # ...and extract host name(s) from summary
		#
		for host in hostnames:
			if not host in masterBugTable['hostIndex']:
				masterBugTable['hostIndex'][host] = {'open':[], 'resolved':[]}
				metrics['totalUniqueHosts'].add(host)

			if bug['status'] in ['RESOLVED', 'CLOSED', 'VERIFIED']:
				masterBugTable['hostIndex'][host]['resolved'].append(bug['test_id'])
			else:
				masterBugTable['hostIndex'][host]['open'].append(bug['test_id'])
				metrics['allOpenBugsForAllLists'].add(bug['test_id'])
				metrics['hostsWithOpenBugs'].add(host)
			# Done looking at bug status, updating structures and calculating metrics
		# Done processing each host mentioned for this bug
	# Done processing all bugs in the data dump, one at a time
	#get_ie_data()
	# Calculate metrics
	# total metrics - all lists
	masterBugTable['metrics'] = {"numOpenBugs":len(metrics['allOpenBugsForAllLists']), "numHosts":len(metrics['totalUniqueHosts']), "numHostsWithOpenBugs":len(metrics['hostsWithOpenBugs'])}
        masterBugTable['timestamp'] = time.time()
	# local metrics..
	for the_list in masterBugTable['lists']:
		the_list_data = masterBugTable['lists'][the_list]
		for domain in the_list_data['data']:
			if str(domain) in masterBugTable['hostIndex']:
				the_list_data['metrics']['numOpenBugs'] += len(masterBugTable['hostIndex'][domain]['open'])
				the_list_data['metrics']['numClosedBugs'] += len(masterBugTable['hostIndex'][domain]['resolved'])
				if len(masterBugTable['hostIndex'][domain]['open']) > 0:
					the_list_data['metrics']['numHostsWithOpenBugs'] += 1
		# Generate static HTML file for the list
		write_list_html(the_list, masterBugTable, find_list_details(the_list, list_details), test_data)
	# Write a JS(ON) file
	print 'Writing masterbugtable.js'
	f = open('../data/masterbugtable.js', 'w')
	f.write('/* This file is generated by preproc/buildlists.py - do not edit */\nvar masterBugTable = '+json.dumps(masterBugTable, indent=2, cls=SetEncoder))
	f.close()
	if stackato_fs_path:
		history_file = stackato_fs_path + '/history.json'
		print("Will write history data to %s " % history_file)
		# we want to store some statistics for posterity
		historical_data = None
		if os.path.exists(history_file) and (time.time() - os.path.getmtime(history_file)) / (60*60*24*7) >= 1:
			# If the file already exists, we only update it if it's older than a week.
			print("History file is older than one week per timestamp")
			f = open( history_file, 'r')
			historical_data = json.load(f)
			f.close()
		elif not os.path.exists(history_file):
			# There is no file yet, history starts here
			print("history starts here..")
			historical_data = []

		if historical_data != None:
			# If historical_data is still None at this point, there is a file and it's less than a week old
			# ..so we don't bother doing anything
			# Let's save [ { timestamp, numOpenBugs, numHosts, numHostsWithOpenBugs } ]
			history_now = {"timestamp": str(time.time()), "numOpenBugs": masterBugTable['metrics']['numOpenBugs'], "numHosts": masterBugTable['metrics']['numHosts'], "numHostsWithOpenBugs": masterBugTable['metrics']['numHostsWithOpenBugs'] }
			historical_data.append(history_now)
			print('Now we\'re rewriting history, baby!')
			f = open(history_file, 'w')
			f.write(json.dumps(historical_data))
			f.close()
	return;

def write_list_html(listname, masterBugTable, list_data, test_data):
	listname = str(listname) # some names are numeric but this code requires strings..
	list_data['name'] = str(list_data['name'])
	html = """<!DOCTYPE html><head><meta charset="utf-8">
	<title>arewecompatibleyet.com: important sites: %s</title>
	<script src="https://mozorg.cdn.mozilla.net/en-US/tabzilla/tabzilla.js"></script>
	<link rel="stylesheet" href="https://www.mozilla.org/en-US/tabzilla/media/css/tabzilla.css"></link>
	<link lang="text/css" href="../css/main.css" rel="stylesheet"></link>
</head>
	<body><div id="wrapper">
<a href="http://www.mozilla.org/" id="tabzilla">mozilla</a>
<h1>%s</h1>
	""" % (list_data['name'],list_data['name'])
	bug_template = """<tr class="{state} {step}"><td><a href="{bug_link}">{bug_id}</a></td><td><a title="{bug_summary}" href="{bug_link}">{bug_summary}</a>{action_links}</td><td>{step}</td><td><span class="testres {test_classname}">{test_age} <strong>▪ {test_state}</strong></span></td></tr>""".decode('utf_8')
	site_template = """
	<tr><td rowspan="{rowspan}">
		<a class="sitelink" title="More information about {hostname}" href="/site/{hostname}">🔎 </a>
		<a class="sitelink" title="{hostname}" href="http://{hostname}" target="_blank">→ </a>
		{hostname}</td><td></tr>
		{bugdata}
	""".decode('utf_8')
	task_template = """<li>[{difficulty}] {desc_html} - <a href="/taskdetails/?bug={bug}&type={type}&link={link}&desc={desc}">Accept task!</a></li>""".decode('utf_8')
	task_link_template = """<a href="/taskdetails/?bug={bug}&type={type}&link={link}&desc={desc}">{linktext}</a>""".decode('utf_8')
	tasks = {"easy":[],"medium":[],"hard":[]}
	site_html = []
	bug_html = []
	task_html = []
	resolved = []
	contacted = {}
	contactready = {}
	needscontact = {}
	open_bugs = {}
	all_green = []
	long_tail = []
	for hostname in masterBugTable['lists'][listname]['data']:
		if hostname in masterBugTable['hostIndex']:
			# We have a host with known open or closed bugs..
			for bug in masterBugTable['hostIndex'][hostname]['open']:
				bug_data = masterBugTable['bugs'][bug]
				bug_step = ''
				test_state = '[test missing]'
				test_classname = ''
				test_age = ''
				action_links = []
				creation_time = datetime.strptime(bug_data['creation_time'], '%Y-%m-%dT%H:%M:%SZ')
				last_change_time = datetime.strptime(bug_data['last_change_time'], '%Y-%m-%dT%H:%M:%SZ')
				diff_creation_change = last_change_time - creation_time
				age_since_change = datetime.utcnow() - last_change_time
				if str(bug_data['test_id']) not in test_data:
					action_links.append(task_link_template.format(**{'bug':bug_data['id'],'type':'writetest','link': sanitize(bug_data['link']),'linktext':'add test','desc':'Add test for bug %s'%bug_data['id']}))
					tasks['hard'].append({'desc':'Write a new test for bug %s' % bug_data['id'], 'bug':bug_data['id'], 'type':'writetest', 'link':bug_data['link'], 'difficulty':'hard'})
				else:
					this_test_data = test_data[str(bug_data['test_id'])]
					if this_test_data['test_state'] == 'true':
						test_state = 'Might be fixed!'
						test_classname = 'pass'
						action_links.append(task_link_template.format(**{'desc':'Check if %s is fixed - a test is passing, we should have a look' % bug_data['id'], 'bug':bug_data['id'], 'type':'check', 'link': bug_data['link'], 'difficulty':'easy', 'linktext':'re-test'}))
						tasks['easy'].append({'desc':'Check if %s is fixed - a test is passing, we should have a look' % bug_data['id'], 'bug':bug_data['id'], 'type':'check', 'link': bug_data['link'], 'difficulty':'easy'})
					elif this_test_data['test_state'] == 'false':
						test_state = 'fail'
						test_classname = 'fail'
					else:
						test_state = this_test_data['test_state']
						test_classname = 'fail'
					test_age = 'Tested %s, ' % timesince(datetime.strptime(this_test_data['test_date'], '%Y-%m-%d %H:%M:%S'))
				if 'whiteboard' in bug_data:
					if '[contactready]' in bug_data['whiteboard']:
						contactready[str(bug)] = bug_data
						bug_step = 'contactready'
						action_links.insert(0, task_link_template.format(**{'desc':'Contact %s about bug %s' % (hostname, bug), 'bug':bug_data['id'], 'type':'contact', 'link':bug_data['link'], 'difficulty':'medium', 'linktext': 'contact'}))
						tasks['medium'].append({'desc':'Contact %s about bug %s' % (hostname, bug_data['id']), 'bug':bug_data['id'], 'type':'contact', 'link':bug_data['link'], 'difficulty':'medium'})
					if '[needscontact]' in bug_data['whiteboard']:
						needscontact[str(bug)] = bug_data
						bug_step = 'needscontact'
						action_links.insert(0, task_link_template.format(**{'desc':'Find contact person for %s about bug %s' % (hostname, bug), 'bug':bug_data['id'], 'type':'findcontact', 'link':bug_data['link'], 'difficulty':'medium', 'linktext': 'contact'}))
						tasks['medium'].append({'desc':'Find contact person for %s about bug %s' % (hostname, bug_data['id']), 'bug':bug_data['id'], 'type':'findcontact', 'link':bug_data['link'], 'difficulty':'medium'})
					elif '[sitewait]' in bug_data['whiteboard']:
						contacted[str(bug)] = bug_data
						bug_step = 'sitewait'
						# encourage visitors to re-contact bugs that have been in sitewait for a while
						if age_since_change.days > 60:
							action_links.insert(0, task_link_template.format(**{'desc': 'Try to contact %s once more about %s - it\'s been more than two months..' % (hostname, bug_data['id']), 'bug':bug_data['id'], 'type':'recontact', 'link':bug_data['link'], 'difficulty':'medium', 'linktext': 'contact again!'}))
							tasks['medium'].append({'desc': 'Try to contact %s once more about %s - it\'s been more than two months..' % (hostname, bug_data['id']), 'bug':bug_data['id'], 'type':'recontact', 'link':bug_data['link'], 'difficulty':'medium'})
					elif bug_data['status'] != 'ASSIGNED': # not analysed yet?
						open_bugs[str(bug)] = bug_data
						bug_step = 'needsanalysis'
						# If bug was last changed more than 60 days ago, or was a hit-n-run report, not changed since filed,
						# let's ask for help simply checking if the problem is there
						if age_since_change.days > 60 or diff_creation_change.seconds < 60*60:
							action_links.insert(0, task_link_template.format(**{'desc':'Check if bug %s happens for you' % bug_data['id'], 'bug':bug_data['id'], 'type':'check', 'link':bug_data['link'], 'difficulty':'easy', 'linktext': 'look for problem'}))
							tasks['easy'].append({'desc':'Check if bug %s happens for you' % bug_data['id'], 'bug':bug_data['id'], 'type':'check', 'link':bug_data['link'], 'difficulty':'easy'})

						action_links.append(task_link_template.format(**{'desc':'Analyze bug %s to figure out why it fails' % bug_data['id'], 'bug':bug_data['id'], 'type':'analyze', 'link':bug_data['link'], 'difficulty':'hard', 'linktext':'analyze'}))
						tasks['hard'].append({'desc':'Analyze bug %s to figure out why it fails' % bug_data['id'], 'bug':bug_data['id'], 'type':'analyze', 'link':bug_data['link'], 'difficulty':'hard'})
					else:
						bug_step = 'needsanalysis'

				bug_html.append(bug_template.format(**{"bug_id":bug, "state":"open", "step": bug_step, "bug_link":bug_data['link'], "bug_summary":sanitize(bug_data["summary"]), "test_state":test_state, "test_classname": test_classname, "test_age":test_age, "action_links":prep_action_links(action_links)}))

			if len(masterBugTable['hostIndex'][hostname]['open']) > 0:
				rowspan = len(masterBugTable['hostIndex'][hostname]['open']) + 1
				site_html.append(site_template.format(**{"hostname": str(hostname), "bugdata": "\n".join(bug_html), "rowspan":rowspan}))
			elif len(masterBugTable['hostIndex'][hostname]['resolved']) > 0:
				all_green.append(hostname)
			resolved.extend(masterBugTable['hostIndex'][hostname]['resolved'])
			# We also go through the resolved ones to see if any of them has a failing test
			for bug in masterBugTable['hostIndex'][hostname]['resolved']:
				bug_data = masterBugTable['bugs'][bug]
				if str(bug_data['test_id']) in test_data:
					this_test_data = test_data[str(bug_data['test_id'])]
					if this_test_data['test_state'] != 'true' and bug_data['resolution'] in ['FIXED', 'WORKSFORME', 'CLOSED']:
						tasks['easy'].append({'desc':'Check if bug %s regressed. It\'s supposedly fixed, but the test fails.' % bug_data['id'], 'bug':bug_data['id'], 'type':'regcheck', 'link':bug_data['link'], 'difficulty':'easy'})

		# the long tail? Sites we don't know much about..
		else:
			long_tail.append(hostname)
		bug_html = []
	perc_resolved = int((len(resolved) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] + masterBugTable['lists'][listname]['metrics']['numClosedBugs']))
	perc_contacted = int((len(contacted) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] ))
	perc_contactready = int((len(contactready) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] ))
	perc_open_bugs = int((len(open_bugs) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] ))
	numOpenBugs = len(open_bugs) + len(contacted) + len(contactready)
	perc_hosts_w_open_bugs = round(float(masterBugTable['lists'][listname]['metrics']['numHostsWithOpenBugs']*100) / len(masterBugTable['lists'][listname]['data']),2)
	metrics = """<div id="metrics">%d sites, %.1f%% have open bugs. <br>The %d open bugs affect %d unique hostnames.</div>""" % (len(masterBugTable['lists'][listname]['data']), perc_hosts_w_open_bugs, numOpenBugs, masterBugTable['lists'][listname]['metrics']['numHostsWithOpenBugs'])

	table = """<table class="list-master-table" border="1">
		<tr><td colspan="5"><div class="list-status-graph">
			<!-- TODO: how to link to both webcompat.com and bugzilla bugs here??? -->
			<!--span class="resolved" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d resolved</span-->
			<span class="open" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d open</span>
			<span class="contactready" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d contactready</span>
			<span class="contacted" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d contacted</span>
		</div></td></tr>
	""" % (','.join(map(str,resolved)), perc_resolved, len(resolved),','.join(open_bugs.keys()), perc_open_bugs, len(open_bugs), ','.join(contactready.keys()), perc_contactready, len(contactready), ','.join(contacted.keys()), perc_contacted, len(contacted) )
	for task in tasks['easy']:
		task['desc_html'] = link_bug(task['desc'], task['link'])
		task_html.append(task_template.format(**task))
	for task in tasks['medium']:
		task['desc_html'] = link_bug(task['desc'], task['link'])
		task_html.append(task_template.format(**task))
	for task in tasks['hard']:
		task['desc_html'] = link_bug(task['desc'], task['link'])
		task_html.append(task_template.format(**task))
	if False:
		# Sites with only resolved bugs
		site_html.append('<tr><th colspan="5">Sites with only closed bugs</th></tr>')
		for hostname in all_green:
			site_html.append('<tr><td rowspan="%d">%s</td><td colspan="4"></td></tr>'%(len(masterBugTable['hostIndex'][hostname]['resolved'])+1, hostname ))
			if hostname in masterBugTable['hostIndex']:
				# We might as well list those closed bugs..
				for bug in masterBugTable['hostIndex'][hostname]['resolved']:
					bug_data = masterBugTable['bugs'][bug]
					test_state = ''
					test_classname = ''
					if str(bug_data['test_id']) in test_data:
						this_test_data = test_data[str(bug_data['test_id'])]
						test_state = this_test_data['test_state']
						if this_test_data['test_state'] != 'true' and bug_data['resolution'] in ['FIXED', 'WORKSFORME', 'CLOSED']:
							tasks['easy'].append({'desc':'Check if bug %s regressed. It\'s supposedly fixed, but the test fails.' % bug_data['id'], 'bug':bug_data['id'], 'type':'regcheck', 'link':bug_data['link'], 'difficulty':'easy'})

					site_html.append(bug_template.format(**{"bug_id":bug, "state":bug_data['status'], "step": "", "bug_link":bug_data['link'], "bug_summary":sanitize(bug_data["summary"]), "test_state":test_state, "test_classname": test_classname, "test_age":test_age, "action_links":""}))
		# Sites with no known bugs at all..
		site_html.append('<tr><th colspan="5">Sites with no known bugs</th></tr>')
		for hostname in long_tail:
			site_html.append('<tr><td>%s</td><td colspan="4">..no issues reported about %s ever..</td></tr>'%(hostname,hostname))
	f = open('../lists/%s.html' % listname, 'w')
	f.write(html.encode('utf_8'))
	f.write('\n')
	f.write(metrics.encode('utf_8'))
	f.write('\n')
	f.write(table.encode('utf_8'))
	f.write('\n')
	f.write('\n'.join(site_html).encode('utf_8'))
	f.write('</table>')
	f.write('\n<h2>Tasks</h2>\n<p>Below are all the tasks from the above table ordered by difficulty.</p>\n<p>Please note: data from Bugzilla is updated once an hour. If you complete one of these tasks it will not disappear from the list immediately, but should within one hour during the next data update. :) <br>TODO: make this true also for tasks like "write a test" (only disappears after next test run)..</p>')
	if len(task_html) == 0:
		f.write('\n<p><b>Congratulations!</b> Nothing to do here at the moment - check back later or help out in some other region :)</p>')
	else:
		f.write('\n<ul>')
		f.write('\n'.join(task_html).encode('utf_8'))
		f.write('\n</ul>')
	f.write('</div></body></html>')
	f.write('\n')
	f.close()

def find_list_details(listname, list_data):
	for the_list in list_data:
		if the_list['id'] == listname:
			return the_list

def hostsFromText(text):
	#  We need to extract any hosts names mentioned in
	#    a) URL field
	#    b) Summary
	#    c) Alias words from aliases.json (i.e. "Hotmail" in summary -> file under live.com)
	#  Also, we want domain names without subdomains (no www. or m. prefixes, for example)
	#  This is a generic method to extract one or more domain names from a text string - the argument can be a URL or some text with a host name mentioned
	text = text.strip().lower()
	hosts = []
	text = re.split('\s', text)

	for word in text:
		word = word.strip('.()!?,[]') # make sure we don't assume a random 'foo.' is a domain due to a sentence-delimiting dot in summary.. Also removing some other characters that might be adjacent..
		if '.' in word and not '][' in word: # now go on to assume the first white-space separated string that contains at least one internal period is a domain name
		# above if excludes words that contain ][ to avoid grabbing parts of the [foo][e.me] labels used in bugzilla
			hosts.append(word)
		else : #
			for hostname in aliases:
				if aliases[hostname] in word:
					#print ('alias match '+hostname+' in '+word+' '+' '.join(text))
					hosts.append(hostname)
	# now we've listed any words/character sequences that contain internal dots.
	# However, we do not want www. or m. or similar prefixes, so we'll run through the list and use
	# tldextract to remove those
	uniquehosts = set()

	for hostname in hosts:
		parts = tldextract.extract(hostname)
		if parts.domain == '' or parts.domain == 'www':
			hostname = parts.suffix # Hello blogspot.com and friends..
		else:
			if re.search(conf['weWantSubdomainsFor'], hostname, re.I) and not re.search('^www', parts[0]):
				hostname = '.'.join(parts[0:3])
			else:
				hostname = '.'.join(parts[1:3])

		uniquehosts.add(hostname)

	# That's it! (We hope..)
	return uniquehosts

def get_remote_file(url, req_json=False):
	pprint('Getting '+url)
	req = urllib2.Request(url)
	if req_json:
		req.add_header('Accept', 'application/json')
#	req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:27.0) Gecko/20100101 Firefox/27.0')
	bzresponse = urllib2.urlopen(req, timeout=240)
	return bzresponse.read()

# Next method is from http://flask.pocoo.org/snippets/33/
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    now = datetime.utcnow()
    diff = now - dt

    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:

        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default
#
#def get_ie_data():
#	# IE site patching lists:
#	iecvlist = 'https://iecvlist.microsoft.com/ie10/201206/iecompatviewlist.xml'
#	import xml.etree.ElementTree as ET
#	xmltree = ET.fromstring(get_remote_file(iecvlist))
#	#iedata = {'hostIndex':{}, 'bugs':{}, 'lists':{'iecvlist':[]}}
#	masterBugTable['lists']['iecvlist'] = {"data":[], "metrics":{"numOpenBugs": 0,"numClosedBugs": 0}}
#	i=1
#	for child in xmltree:
#		if child.tag == 'domain':
#			host = child.text.strip()
#			masterBugTable['lists']['iecvlist']['data'].append(host)
#			bug_id = 'IE-%i'%i
#			mode = '['+child.attrib['docMode']+']' if 'docMode' in child.attrib else ''
#			if len(child.attrib.keys()) == 0:
#				mode = '[renders in IE7-standard-mode or IE5-quirks-mode, depends on doctype]'
#			feat = '['+child.attrib['featureSwitch']+']' if 'featureSwitch' in child.attrib else ''
#			uaString = '['+child.attrib['uaString']+']' if 'uaString' in child.attrib else ''
#			masterBugTable['bugs'][bug_id] = {
#				"status":"NEW",
#			      "whiteboard": "%s %s %s" % (mode, feat, uaString),
#			      "url": "http://%s" % host,
#			      "depends_on": "",
#			      "last_change_time": "",
#			      "creation_time": "",
#			      "summary": "%s is on Internet Explorer compatibility view list %s %s %s" % (host, mode, feat, uaString),
#			      "priority": "--",
#			      "id": bug_id,
#			      "resolution": "",
#			      "cf_last_resolved": "",
#			      "bug_link": iecvlist
#			}
#			if not host in masterBugTable['hostIndex']:
#				masterBugTable['hostIndex'][host] = {"open":[], "resolved":[]}
#			masterBugTable['hostIndex'][host]["open"].append(bug_id)
#			i+=1

def find_last_contacted_date(bug):
	# https://bugzilla.mozilla.org/rest/bug/679025/comment
	contacted_date = None
	comment_str = get_remote_file('https://bugzilla.mozilla.org/rest/bug/%s/comment' % bug, True)
	comments = json.loads(comment_str)
	for i in range(len(comments['bugs'][str(bug)]['comments'])-1,0,-1):
		comment = comments['bugs'][str(bug)]['comments'][i]
		if 'contact' in comment['tags']:
			contacted_date = comment['time']
			break
	# https://bugzilla.mozilla.org/rest/bug/679025/history
	if not contacted_date:
		history_str = get_remote_file('https://bugzilla.mozilla.org/rest/bug/%s/history' % bug, True)
		history = json.loads(history_str)['bugs'][0]['history']
		for i in range(len(history)-1,0,-1):
			for change in history[i]['changes']:
				if change['field_name'] != 'whiteboard':
					continue
				if '[sitewait]' in change['added'] and '[sitewait]' not in change['removed']:
					contacted_date = history[i]['when']
					break

	return contacted_date

if __name__ == "__main__":
    main()
