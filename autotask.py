from bs4 import BeautifulSoup
from atlassian import Confluence
import datetime,html
import argparse,json,re

from jira import JIRA

parser = argparse.ArgumentParser()
parser.add_argument("--confluence",help="conflence source and confidential")
parser.add_argument("--data",help="data for update", required=True)
parser.add_argument("--task", help="task build number", required=True)
parser.add_argument("--jira", help="jira configure", required=True)
args = parser.parse_args()
status_macro = """<ac:structured-macro ac:name="status" ac:schema-version="1"><ac:parameter ac:name="colour">Red</ac:parameter><ac:parameter ac:name="title">FAIL</ac:parameter></ac:structured-macro>"""
jira_macro = """<ac:structured-macro ac:name="jira" ac:schema-version="1" ><ac:parameter ac:name="server">JIRA</ac:parameter><ac:parameter ac:name="serverId">{server}</ac:parameter><ac:parameter ac:name="key">{id}</ac:parameter></ac:structured-macro>"""
expand_macro = """<ac:structured-macro ac:name="expand" ac:schema-version="1">
    <ac:parameter ac:name="title">{error_str}</ac:parameter>
    <ac:rich-text-body>
        {content}
    </ac:rich-text-body>
</ac:structured-macro>"""
if __name__ == "__main__":
    confluence = args.confluence
    jira_server,jira_auth = args.jira.split("|")
    jira = JIRA(server=jira_server, token_auth=jira_auth)
    raw_data = args.data
    data = json.loads(raw_data)
    user_data = data["user"]
    user = user_data["email"]
    res = {}
    res["build"] = data["build"]
    res["task_build"] = int(args.task)
    res["jiras"] = []
    jiras = []
    if "jiras" in data:
        jiras = data["jiras"]
    server_url, page_id, username, token,server_id = confluence.split("|")
    templates = json.load(open("template.json","r"))
    confluence = Confluence(server_url, username, token=token, verify_ssl=False)
    response = confluence.get(f'/rest/api/user?username={user}')
    user_key = response["userKey"]
    print(user_key)
    page = confluence.get_page_by_id(page_id, expand="body.storage")
    properties = confluence.get_page_properties(page_id)
    content = page["body"]["storage"]["value"]
    soup = BeautifulSoup(content, "html.parser")
    test_file = open("test.in","w")
    test_file.write(content)
    test_file.close()
    tables = soup.find_all("table")
    macros = {}
    for table in tables:
        ths = table.find_all("th")
        headers = []
        for th in ths:
            headers.append(th.text)

        if "Release" in headers:
            jira_list = []
            trs = table.find_all("tr")
            last_tr = trs[0]
            for tr in trs:
                if len(tr.text.strip()) > 0:
                    last_tr = tr
                tds = tr.find_all("td")
                row = []
                index = 0
                contents = {}
                tags = {}
                for td in tds:
                    row.append(td.text)
                    contents[headers[index]] = str(td)
                    tags[headers[index]] = td
                    index += 1
                if len(row) > 0:
                    record = dict(zip(headers,row))
                    if record["StatusGreenPassRedFail"].lower() == "redfail" and record['Reason'].find('JIRA') >= 0:
                        in_updates = False
                        if "Release" in record:
                            m = re.search("(\d+\.\d+)", record["Release"])
                            if m:
                                record["Release"] = m.group(1)
                        jira_list = []
                        if 'Reason' in tags:
                            macros = tags['Reason'].find_all('ac:structured-macro')
                            for macro in macros:
                                parameters = macro.find_all('ac:parameter')
                                for parameter in parameters:
                                    if parameter.get("ac:name") == 'key':
                                        jira_list.append(parameter.text.strip())
                        jira_str = ",".join(jira_list)
                        if 'Test' in tags:
                            links = tags['Test'].find_all('a')
                            record['scenarios'] = []
                            for link in links:
                                link_url = link.get("url")
                                record['scenarios'].append({"url":link.get('href'),"name":link.text})
                        for a_jira in jiras:
                            if jira_str.lower().find(a_jira["id"].lower()) >= 0:
                                new_tr = "<tr>"
                                scenario_text = ""
                                for header in headers:
                                    if header == "Test":
                                        new_content = "<td>"
                                        test_content = ""
                                        for scenario in a_jira["scenarios"]:
                                            test_content += "<a target=\"_blank\" href=\"" + scenario["url"] + "\">" + \
                                                           scenario["name"] + "</a><br/>"
                                            scenario_text += scenario["name"] + "\n"

                                        if len(a_jira["scenarios"]) > 5:
                                            error_num = len(a_jira["scenarios"])
                                            error_str = "Failed " + str(error_num) + " scenarios"
                                            test_content = expand_macro.format(error_str=error_str,content=test_content)

                                        new_content += test_content + "</td>"
                                    else:
                                        new_tr += contents[header]
                                new_tr += "<td>"
                                tr_new = BeautifulSoup(new_tr, "html.parser").find("tr")
                                tr.replace_with(tr_new)
                                issue=jira.issue(a_jira["id"])
                                a_jira["summary"] = issue.get_field("summary")
                                a_jira["creator"] = issue.get_field("creator")
                                a_jira["updated"] = True
                                a_jira["scenario_text"] = scenario_text
                                in_updates = True
                                break
                        if not in_updates:
                            for jira_id in jira_list:
                                new_jira = {}
                                new_jira["id"] = jira_id
                                issue = jira.issue(jira_id)
                                new_jira["summary"] = issue.get_field("summary")
                                new_jira["creator"] = issue.get_field("creator")
                                new_jira["scenario"] = record["scenarios"]
                                new_jira["scenario_text"] = record["Test"]
            for a_jira in jiras:
                version = ".".join(a_jira["version"].split(".")[:2])
                if "updated" not in a_jira:
                    new_tr = "<tr>"
                    for header in headers:
                        if header == "Since":
                            new_tr += "<td>" + templates[header].format(datetime.datetime.now().strftime("%Y-%m-%d")) + "</td>"
                        elif header == "Reason":
                            new_tr += "<td>" + jira_macro.format(server=server_id, id=a_jira["id"].upper()) + "</td>"
                        elif header == "Owner":
                            new_tr += "<td>" + templates[header].format(user_key) + "</td>"
                        elif header == "Release":
                            new_tr += "<td>" + templates[header].format(version) + "</td>"
                        elif header == "Test":
                            new_tr += "<td>"
                            for scenario in a_jira["scenarios"]:
                                new_tr += "<a target=\"_blank\" href=\"" + scenario["url"] + "\">" + scenario[
                                    "name"] + "</a><br/>"
                            new_tr += "</td>"
                        elif header == "Fixed":
                            new_tr += "<td></br></td>"
                        elif header =="Feature File":
                            new_tr += "<td>"
                            feature_list = []
                            for scenario in a_jira["scenarios"]:
                                if scenario["feature"] not in feature_list:
                                    feature_list.append(scenario["feature"])
                            new_tr += "<br/>".join(feature_list)
                        else:
                            new_tr += "<td>" + status_macro + "</td>"
                    new_tr += "</tr>"
                    tr_new = BeautifulSoup(new_tr, "html.parser").find("tr")
                    last_tr.insert_after(tr_new)
    # new_content = soup.prettify()
    # test_file = open("test.out","w")
    # test_file.write(new_content)
    # test_file.close()
    # print(new_content)
    res["jiras"] = jiras
    for env in data["tasks"]:
        tasks = data["tasks"][env]
        for task in tasks:
            for scenario in task["scenarios"]:
                if "new_comment" in scenario and scenario["new_comment"]:
                    if "comments" in scenario:
                        scenario["comments"].append(scenario["new_comment"])
                    else:
                        scenario["comments"] = [scenario["new_comment"]]
                    scenario["new_comment"] = None
    res["tasks"] = data["tasks"]
    new_content = str(soup)
    response = confluence.update_page(page_id,page["title"],new_content)
    task_json = open("tasks.json","w")
    json.dump(res,task_json,indent=4)
    task_json.close()


