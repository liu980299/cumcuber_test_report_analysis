from bs4 import BeautifulSoup
from atlassian import Confluence
import datetime,requests
import argparse,json,re
import pymsteams
import jenkins
import copy
from jira import JIRA

parser = argparse.ArgumentParser()
parser.add_argument("--confluence",help="conflence source and confidential")
parser.add_argument("--task", help="task build number", required=True)
parser.add_argument("--jira", help="jira configure", required=True)
parser.add_argument("--teams", help="team web hooker", required=True)
parser.add_argument("--domain", help="teams domain", required=True)
parser.add_argument("--jenkins", help="job url", required=True)
args = parser.parse_args()
status_macro = """<ac:structured-macro ac:name="status" ac:schema-version="1"><ac:parameter ac:name="colour">Red</ac:parameter><ac:parameter ac:name="title">FAIL</ac:parameter></ac:structured-macro>"""
jira_macro = """<ac:structured-macro ac:name="jira" ac:schema-version="1" ><ac:parameter ac:name="server">JIRA</ac:parameter><ac:parameter ac:name="serverId">{server}</ac:parameter><ac:parameter ac:name="key">{id}</ac:parameter></ac:structured-macro>"""
expand_macro = """<ac:structured-macro ac:name="expand" ac:schema-version="1">
    <ac:parameter ac:name="title">{error_str}</ac:parameter>
    <ac:rich-text-body>
        {content}
    </ac:rich-text-body>
</ac:structured-macro>"""
message_payload={
    "type": "message",
    "attachments": [
        {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "type": "AdaptiveCard",
            "body": [

            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.0",
            "msteams": {
                "entities": [

                ]
            }
        }
    }
]
}
if __name__ == "__main__":
    confluence = args.confluence
    server_url,job_name,username,password,message_job = args.jenkins.split("|")
    server = jenkins.Jenkins(server_url,username,password)
    job_info = server.get_job_info(job_name)
    last_successful_task = job_info["lastSuccessfulBuild"]["url"] + "tasks/tasks.json"
    response = server.jenkins_request(requests.Request('GET',last_successful_task))
    last_task = json.loads(response.text)
    monitor_scenarios = {}
    if "monitor_scenarios" in last_task:
        monitor_scenarios = last_task["monitor_scenarios"]

    jira_server,jira_auth = args.jira.split("|")
    domain = args.domain
    jira = JIRA(server=jira_server, token_auth=jira_auth)
    # raw_data = args.data
    data_file = open("data.json","r")
    data = json.load(data_file)
    data_file.close()
    teams = {}
    for team_str in args.teams.split(","):
        (env, webhook) = team_str.split("|", 1)
        teams[env] = pymsteams.connectorcard(webhook)
        teams[env].payload = copy.deepcopy(message_payload)

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
    team_contacts = {}
    print(user_key)
    page = confluence.get_page_by_id(page_id, expand="body.storage")
    properties = confluence.get_page_properties(page_id)
    content = page["body"]["storage"]["value"]
    soup = BeautifulSoup(content, "html.parser")
    owner_dict = {}
    test_file = open("test.in","w")
    test_file.write(content)
    test_file.close()
    all_jiras = []
    tables = soup.find_all("table")
    macros = {}
    for table in tables:
        ths = table.find_all("th")
        headers = []
        for th in ths:
            headers.append(th.text)
        if "QA" in headers:
            trs = table.find_all("tr")
            owner_list = {}
            for tr in trs:
                tds = tr.find_all("td")
                row = []
                index = 0
                owner = {}
                for td in tds:
                    row.append(str(td))
                    text = str(td)
                    if (text.find("userkey") >= 0):
                        matches = re.findall("userkey=\"([^\"]+)\"", text)
                        userkey = matches[len(matches) - 1]
                        owner[headers[index]] = userkey
                    else:
                        if text.find(".feature") > 0 and index == 0:
                            index += 1
                        owner[headers[index]] = td.text
                    index += 1
                if len(owner) > 1 and "QA" in owner:
                    ldap_user = owner["LDAP User"].lower()
                    if ldap_user not in owner_list:
                        owner_dict[owner["QA"]] = ldap_user
                        print(owner)
                        user = confluence.get_user_details_by_userkey(owner["QA"])
                        owner_list[ldap_user] = {}
                        owner_list[ldap_user]["user"] = user["displayName"]
                        if user["displayName"] not in team_contacts:
                            team_contacts[user["displayName"]] = ldap_user + "@" +domain
                        owner_list[ldap_user]["email"] = user["username"]
                        owner_list[ldap_user]["key"] = owner["QA"]
                        owner_list[ldap_user]["features"] = [owner["Feature File"].lower()]
                    else:
                        if "QA" in owner:
                            owner_list[ldap_user]["features"].append(owner["Feature File"].lower())

        if "Release" in headers:
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
                                if (len(a_jira["scenarios"]) == 0):
                                    tr.decompose()
                                else:
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
                                            new_tr += new_content
                                        else:
                                            new_tr += contents[header]
                                    new_tr += "</tr>"
                                    tr_new = BeautifulSoup(new_tr, "html.parser").find("tr")
                                    tr.replace_with(tr_new)
                                    a_jira["scenario_text"] = scenario_text
                                issue=jira.issue(a_jira["id"])
                                a_jira["summary"] = issue.get_field("summary")
                                a_jira["creator"] = str(issue.get_field("creator"))
                                a_jira["updated"] = True
                                in_updates = True
                                all_jira_ids = [ ticket["id"] for ticket in all_jiras]
                                if not a_jira["id"] in all_jira_ids:
                                    all_jiras.append(a_jira)
                                break
                        if not in_updates:
                            for jira_id in jira_list:
                                new_jira = {}
                                new_jira["id"] = jira_id
                                issue = jira.issue(jira_id)
                                new_jira["summary"] = issue.get_field("summary")
                                new_jira["creator"] = str(issue.get_field("creator"))
                                new_jira["scenarios"] = record["scenarios"]
                                new_jira["version"] = record["Release"]
                                new_jira["scenario_text"] = record["Test"]
                                all_jira_ids = [ ticket["id"] for ticket in all_jiras]
                                if not new_jira["id"] in all_jira_ids:
                                    all_jiras.append(new_jira)

            for a_jira in jiras:
                version = ".".join(a_jira["version"].split(".")[:2])
                if "updated" not in a_jira:
                    if "is_new" in a_jira and a_jira["is_new"]:
                        issue = jira.create_issue(project=a_jira["project"], summary=a_jira["summary"],
                                                      description=a_jira["description"], issuetype={'name': 'Bug'}, labels=['foundByAutomation'],
                                                             fixVersions=[{"name":"Triage"}],customfield_12257=a_jira["steps"],
                                                             reporter={"name": user_data["username"]},assignee={"name":user_data["username"]})
                        print(issue)
                        a_jira["original_id"] = a_jira["id"]
                        a_jira["id"] = issue.id
                    else:
                        issue = jira.issue(a_jira["id"])
                    a_jira["summary"] = issue.get_field("summary")
                    a_jira["creator"] = str(issue.get_field("creator"))
                    all_jira_ids = [ticket["id"] for ticket in all_jiras]
                    if not a_jira["id"] in all_jira_ids:
                        all_jiras.append(a_jira)
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
    res["jiras"] = all_jiras
    for env in data["tasks"]:
        tasks = data["tasks"][env]
        for task in tasks:
            jiras = task["jiras"]
            new_jiras = []
            teams_message ={"type":"TextBlock","text":"# **<at>"+task["owner"]+"</at> new tasks:**\n\n","wrap":True}
            for jira in jiras:
                if jira not in new_jiras:
                    new_jiras.append(jira)
            for scenario in task["scenarios"]:
                scenario_item = task["scenarios"][scenario]
                new_comment = {}
                if scenario_item["changed"]:
                    teams_message["text"] += "\n\n- [{0}]({1})".format(scenario,scenario_item["work_url"])

                if "new_comment" in scenario_item and scenario_item["new_comment"]:
                    teams_message["text"] += " --" + scenario_item["new_comment"]["content"]
                    new_comment = scenario_item["new_comment"]
                    if "comments" in scenario_item:
                        scenario_item["comments"].append(scenario_item["new_comment"])
                    else:
                        scenario_item["comments"] = [scenario_item["new_comment"]]
                    scenario_item["new_comment"] = None
                if scenario in monitor_scenarios:
                    if not new_comment["is_monitored"]:
                        scenario_item["is_monitored"] = False
                        if "history" in scenario_item:
                            scenario_item.pop("history")
                        monitor_scenarios.pop(scenario)
                    else:
                        history_item = {}
                        for key in scenario_item:
                            if not key == "history":
                                history_item[key] = scenario_item[key]
                        monitor_scenarios[scenario].append(history_item)
                        scenario_item["history"] = monitor_scenarios[scenario]
                        comments = []
                        for item in monitor_scenarios[scenario]:
                            for a_comment in item["comments"]:
                                comments.append(a_comment)
                        scenario_item["comments"] = comments
                        scenario_item["is_monitored"] = True
                else:
                    if "is_monitored" in new_comment and new_comment["is_monitored"]:
                        scenario_item["is_monitored"] = True
                        history_item = {}
                        for key in scenario_item:
                            if not key == "history":
                                history_item[key] = scenario_item[key]
                        monitor_scenarios[scenario] = [scenario_item]
                        scenario_item["history"] = history_item
            if "changed" in task and task["changed"]:
                mention = {
                        "type": "mention",
                        "text": "<at>" + task["owner"] + "</at>",
                        "mentioned": {
                            "id": team_contacts[task["owner"]],
                            "name": task["owner"]
                        }
                    }
                teams[task["env"]].payload["attachments"][0]["content"]["body"].append(teams_message)
                teams[task["env"]].payload["attachments"][0]["content"]["msteams"]["entities"].append(mention)
            task["jiras"] = new_jiras
    res["tasks"] = data["tasks"]
    res["monitor_scenarios"] = monitor_scenarios
    new_content = str(soup)
    response = confluence.update_page(page_id,page["title"],new_content)
    task_json = open("tasks.json","w")
    json.dump(res,task_json,indent=4)
    task_json.close()
    messages_json = {}
    for env in teams:
        if len(teams[env].payload["attachments"][0]["content"]["body"]) > 0:
            messages_json[env] = teams[env].payload
    json_file = open("messages.json","w")
    json.dump(messages_json,json_file,indent=4)
    json_file.close()
    server.build_job(message_job,parameters={"test":"test"},token=message_job + "_token")

