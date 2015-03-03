# get site info
# data sources:
# data/masterbugtable.js - connects site (if known) to bugs
# data/testing/index.json - gives fn of most recent CSV
# data/testing/results-*.csv - results from the last test
# data/sitedata.js - actual test code

# to come: file system / ccTLD /comp/idx.js - obj['list'] - array hostname, name (of file), fullurl

from slimit import ast
from slimit.parser import Parser
from slimit.visitors import nodevisitor
import os, json, csv, re

stackato_fs_path = os.environ.get('STACKATO_FILESYSTEM') # path to files or None
#stackato_fs_path = 'c:\\mozilla\\testing'
#print('warning: hard-coded fs path')

def main():
    pass

def load_data():
    # Read list names (toplists.js)
    f = open('./data/masterbugtable.js', 'r')
    tmp = f.read()
    f.close()
    masterbugtable = json.loads(tmp[tmp.index('{'):])
    # find and process latest test data
    f = open('./data/testing/index.json', 'r')
    tmp = f.read()
    f.close()
    test_file_index = json.loads(tmp)
    f = open('./data/testing/%s' % test_file_index[-1], 'r')
    test_data = {}
    test_reader = csv.reader(f)
    for line in test_reader:
        test_data[str(line[0])] = {"bug":line[0], "test_date":line[1], "ua":line[2], "test_state":line[3]}
    f.close()
    f = open('./data/sitedata.js', 'r')
    parser = Parser()
    tree = parser.parse(f.read())
    f.close()
    return {'masterbugtable': masterbugtable, 'test_result_files': test_file_index, 'test_results': test_data, 'tests_parsed': tree}

def find_screenshot(masterbugtable, site):
    # look through lists to find one with the site
    for the_list in masterbugtable['lists']:
        if site in masterbugtable['lists'][str(the_list)]['data']:
           # FOUND!..now what?
           # ccTLD = All non-numeric chars, if any
           tmp = re.search('[a-z]*', the_list)
           if tmp:
                cctld = tmp.group(0)
                the_path = stackato_fs_path + os.path.sep + cctld + os.path.sep + 'comp' + os.path.sep
                if os.path.isfile(the_path + 'idx.js'):
                    # if we have stackato_fs_path / ccTLD / comp / idx.js
                    f = open(the_path + 'idx.js')
                    ss_data = json.loads(f.read())
                    # loop through 'list' and check the hostname, return directory + os.path.sep + file name if match
                    for filedata in ss_data:
                        if filedata['hostname'] == site:
                            return the_path + filedata['name']
    return None

def get_test_steps_as_strings(tree, bug):
    the_node = None
    output = []
    for node in nodevisitor.visit(tree):
        if isinstance(node, ast.Assign):
            if str(bug) in getattr(node.left, 'value', ''):
                the_node = node
                break
    if the_node:
        for node in nodevisitor.visit(the_node):
            if isinstance(node, ast.FuncExpr):
                output.append(node.to_ecma())
    return output

if __name__ == "__main__":
    main()

