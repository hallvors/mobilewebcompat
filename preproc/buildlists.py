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
# test results
# todo-lists (including "recontact" sitewait that hasn't been touched for a while)
# include webcompat.com issues
# screenshots?
# misc test data?
# "maybe" issues?
# /sites/example.com.html with further details?
# hook screenshot review into /sites/example.com system?

import json, glob, urllib, os, urllib2,csv,StringIO,re, sys, time
from pprint import pprint
from urlparse import urlparse
import socket
socket.setdefaulttimeout(240) # Seconds. Loading Bugzilla searches can be slow
import tldextract
import cgi
import pdb

stackato_fs_path = os.environ.get('STACKATO_FILESYSTEM') # path to files or None

os.chdir(os.path.dirname(os.path.abspath(__file__))) # For CRON usage..
# We generally want to handle the main domains (i.e. google.com for www.google.com) instead of the full host names
# however, for some major sites with lots of distinct properties we loose too much useful information if we classify it just by domain name..
# conf['weWantSubdomainsFor'] is a list of hostnames that should not be reduced to domain names. For these, we'll strip any *www.* prefix, but
# no other subdomains. (Another option is to only strip www - might work too)
conf = { 'weWantSubdomainsFor': r'(\.google\.com|\.live\.com|\.yahoo\.com|go\.com|\.js$)',  # the latter is not, strictly speaking, a subdomain..
'load_remote_bz_data': False }

f = open('../data/toplists.js', 'r')
tmp = f.read()
f.close()
list_details = json.loads(tmp[tmp.index('['):])

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

def main():
	if conf['load_remote_bz_data']:
		urltemplate = 'https://bugzilla.mozilla.org/bzapi/bug?component=Mobile&product=Tech%20Evangelism&component=Desktop&include_fields=id,summary,creation_time,last_change_time,status,resolution,depends_on,whiteboard,cf_last_resolved,url,priority' # removed ",flags" to work around bugzilla bug..
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

	# reading our lists of regionally important sites
	for fn in glob.glob('..' + os.sep +'data' + os.sep + '*.json'):
		f = open(fn)
		data = json.load(f)
		f.close()
		listname = os.path.splitext(os.path.basename(fn))[0]

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
		masterBugTable['bugs'][bug['id']] = bug;
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

			if bug['status'] in ['RESOLVED', 'CLOSED', 'VERIFIED'] :
				masterBugTable['hostIndex'][host]['resolved'].append(bug['id'])
			else:
				masterBugTable['hostIndex'][host]['open'].append(bug['id'])
				metrics['allOpenBugsForAllLists'].add(bug['id'])
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
		write_list_html(the_list, masterBugTable, find_list_details(the_list, list_details))
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

def write_list_html(listname, masterBugTable, list_data):
	# TODO: test data!
	print(listname)
	listname = str(listname) # some names are numeric but this code requires strings..
	list_data['name'] = str(list_data['name'])
	html = """<!DOCTYPE html><head><meta charset="utf-8">
	<title>arewecompatibleyet.com: important sites: %s</title>
	<script src="https://mozorg.cdn.mozilla.net/en-US/tabzilla/tabzilla.js"></script>
	<link rel="stylesheet" href="https://www.mozilla.org/en-US/tabzilla/media/css/tabzilla.css"></link>
	<link lang="text/css" href="../css/main.css" rel="stylesheet"></link>
</head>
	<body><h1>%s</h1>
	""" % (list_data['name'],list_data['name'])
	bug_template = """<tr class="{state}"><td><a href="https://bugzilla.mozilla.org/show_bug.cgi?id={bug_id}">{bug_id}</a></td><td class="summary"><a title="{bug_summary}" href="https://bugzilla.mozilla.org/show_bug.cgi?id={bug_id}">{bug_summary}</a></td><td>{step}</td><td><span class="testres {test_state}">{test_age} <strong>▪ {test_state}</strong></span></td></tr>""".decode('utf_8')
	site_template = """
	<tr><td><a class="sitelink" title="{hostname}" href="http://{hostname}" target="_blank">→ </a>{hostname}</td><td><table class="nested-bug-table">
		{bugdata}
	</table></td></tr>
	""".decode('utf_8')
	site_html = []
	bug_html = []
	resolved = []
	contacted = {}
	contactready = {}
	open_bugs = {}
	for hostname in masterBugTable['lists'][listname]['data']:
		if hostname in masterBugTable['hostIndex']:
			# We have a host with known open or closed bugs..
			for bug in masterBugTable['hostIndex'][hostname]['open']:
				bug_data = masterBugTable['bugs'][bug]
				if 'whiteboard' in bug_data:
					if '[contactready]' in bug_data['whiteboard']:
						contactready[str(bug)] = bug_data
						bug_html.append(bug_template.format(**{"state":"open", "step": "contactready", "bug_id":bug, "bug_summary":cgi.escape(bug_data["summary"]), "test_state":"", "test_age":""}))
					elif '[sitewait]' in bug_data['whiteboard']:
						contacted[str(bug)] = bug_data
						bug_html.append(bug_template.format(**{"state":"open", "step": "sitewait", "bug_id":bug, "bug_summary":cgi.escape(bug_data["summary"]), "test_state":"", "test_age":""}))
					else: # not analysed yet?
						open_bugs[str(bug)] = bug_data
						bug_html.append(bug_template.format(**{"state":"open", "step": "needsanalysis", "bug_id":bug, "bug_summary":cgi.escape(bug_data["summary"]), "test_state":"", "test_age":""}))
			if len(masterBugTable['hostIndex'][hostname]['open']):
				site_html.append(site_template.format(**{"hostname": str(hostname), "bugdata": "\n".join(bug_html)}))
			resolved.extend(masterBugTable['hostIndex'][hostname]['resolved'])
		bug_html = []
	perc_resolved = int((len(resolved) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] + masterBugTable['lists'][listname]['metrics']['numClosedBugs']))
	perc_contacted = int((len(contacted) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] + masterBugTable['lists'][listname]['metrics']['numClosedBugs']))
	perc_contactready = int((len(contactready) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] + masterBugTable['lists'][listname]['metrics']['numClosedBugs']))
	perc_open_bugs = int((len(open_bugs) * 100) / (masterBugTable['lists'][listname]['metrics']['numOpenBugs'] + masterBugTable['lists'][listname]['metrics']['numClosedBugs']))

	numOpenBugs = len(open_bugs) + len(contacted) + len(contactready)
	perc_hosts_w_open_bugs = round(float(masterBugTable['lists'][listname]['metrics']['numHostsWithOpenBugs']*100) / len(masterBugTable['lists'][listname]['data']),2)
	metrics = """<div id="metrics">%d sites, %.1f%% have open bugs. <br>The %d open bugs affect %d unique hostnames.</div>""" % (len(masterBugTable['lists'][listname]['data']), perc_hosts_w_open_bugs, numOpenBugs, masterBugTable['lists'][listname]['metrics']['numHostsWithOpenBugs'])

	table = """<table class="list-master-table" border="1">
		<tr><td colspan="3"><div class="list-status-graph">
			<a class="resolved" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d resolved</a>
			<a class="contacted" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d contacted</a>
			<a class="contactready" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d contactready</a>
			<a class="open" href="https://bugzilla.mozilla.org/buglist.cgi?bug_id=%s" style="width:%d%%">%d open</a>
		</div></td></tr>
	""" % (','.join(map(str,resolved)), perc_resolved, len(resolved), ','.join(contacted.keys()), perc_contacted, len(contacted), ','.join(contactready.keys()), perc_contactready, len(contactready), ','.join(open_bugs.keys()), perc_open_bugs, len(open_bugs))

	f = open('../lists/%s.html' % listname, 'w')
	f.write(html.encode('utf_8'))
	f.write('\n')
	f.write(metrics.encode('utf_8'))
	f.write('\n')
	f.write(table.encode('utf_8'))
	f.write('\n')
	f.write('\n'.join(site_html).encode('utf_8'))
	f.write('</table></body></html>')
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

def get_ie_data():
	# IE site patching lists:
	iecvlist = 'https://iecvlist.microsoft.com/ie10/201206/iecompatviewlist.xml'
	import xml.etree.ElementTree as ET
	xmltree = ET.fromstring(get_remote_file(iecvlist))
	#iedata = {'hostIndex':{}, 'bugs':{}, 'lists':{'iecvlist':[]}}
	masterBugTable['lists']['iecvlist'] = {"data":[], "metrics":{"numOpenBugs": 0,"numClosedBugs": 0}}
	i=1
	for child in xmltree:
		if child.tag == 'domain':
			host = child.text.strip()
			masterBugTable['lists']['iecvlist']['data'].append(host)
			bug_id = 'IE-%i'%i
			mode = '['+child.attrib['docMode']+']' if 'docMode' in child.attrib else ''
			if len(child.attrib.keys()) == 0:
				mode = '[renders in IE7-standard-mode or IE5-quirks-mode, depends on doctype]'
			feat = '['+child.attrib['featureSwitch']+']' if 'featureSwitch' in child.attrib else ''
			uaString = '['+child.attrib['uaString']+']' if 'uaString' in child.attrib else ''
			masterBugTable['bugs'][bug_id] = {
				"status":"NEW",
			      "whiteboard": "%s %s %s" % (mode, feat, uaString),
			      "url": "http://%s" % host,
			      "depends_on": "",
			      "last_change_time": "",
			      "creation_time": "",
			      "summary": "%s is on Internet Explorer compatibility view list %s %s %s" % (host, mode, feat, uaString),
			      "priority": "--",
			      "id": bug_id,
			      "resolution": "",
			      "cf_last_resolved": "",
			      "bug_link": iecvlist
			}
			if not host in masterBugTable['hostIndex']:
				masterBugTable['hostIndex'][host] = {"open":[], "resolved":[]}
			masterBugTable['hostIndex'][host]["open"].append(bug_id)
			i+=1

if __name__ == "__main__":
    main()
