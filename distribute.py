import datetime
import json
import re
from bs4 import BeautifulSoup
import django
import jenkins
import argparse, os, urllib.parse, pymsteams
from atlassian import Confluence
from jira import JIRA

import requests
from django.conf import settings
from django.template import Template, Context

from getserverlog import ServerLog

parser = argparse.ArgumentParser()
parser.add_argument("--username",help="username",required=True)
parser.add_argument("--passwords",help="passowrd",required=True)
parser.add_argument("--servers",help="Jenkins Server",required=True)
parser.add_argument("--log_server",help="log server name",required=True)
parser.add_argument("--jobs", help="job name list and delimiter ','",required=True)
parser.add_argument("--input", help="Test Result folder", required=True, default="c:/cucumber-result/")
parser.add_argument("--log_map", help="server,logfile pattern,grep keyword group, delimiter as |",required=True)
parser.add_argument("--private_key", help="private_key location",required=True)
parser.add_argument("--teams", help="teams webhook connectors", required=True)
parser.add_argument("--report_url",help="report url for jenkins to retrieve resources", required=True)
parser.add_argument("--performance",help="performance check argument <QA-CASEID>:<STEP>:<DURATION>", required=False)
parser.add_argument("--context",help="context analysis argument <start flag>:<end flag>:<context flag>", required=False)
parser.add_argument("--skips", help="skipped java file, if failuare in skip java file, the previous step would be checked ", required=True)
parser.add_argument("--confluence",help="conflence source and confidential",required=False)


args = parser.parse_args()

Templates = [
    {
        'BACKEND':'django.template.backends.django.DjangoTemplates'
    }
]

settings.configure(TEMPLATES=Templates)

django.setup()

def analysis_performance(performances,job_info,performance_result, lastBuild):
    qa_case = performances["case_id"]
    step = performances["step"]
    duration = performances["duration"]
    if len(performance_result) == 0:
        performance_result = {"scenarios":{},"_type":"report","data":"duration"}
    for buildNum in job_info:
        build_res = job_info[buildNum]

        for scenario in build_res["scenarioes"]:
            if scenario["scenario"].find(qa_case) >= 0:
                if scenario["scenario"] not in performance_result["scenarios"]:
                    performance_result["scenarios"][scenario["scenario"]] = []
                scenario_res = performance_result["scenarios"][scenario["scenario"]]
                scenario_item = {"build": buildNum}
                scenario_item["version"] = build_res["PORTAL VERSION"]
                steps = scenario["steps"]
                for step_info in steps:
                    if step_info["name"].find(step) >= 0:
                        for key in step_info:
                            if key == "duration":
                                step_duration = step_info[key]
                                m = re.search('(\d+)m\s*(\d+)s\s*(\d+)ms', step_duration)
                                if m:
                                    scenario_item["duration"] = float(m.group(1)) * 60 + float(m.group(2)) + float(
                                        m.group(3)) / 1000
                                    if buildNum == lastBuild:
                                        if "duration" not in performance_result:
                                            performance_result["duration"] = {}
                                        performance_result["duration"][scenario["scenario"]] = scenario_item["duration"]
                                        if "result" not in performance_result:
                                            performance_result["result"] = {}
                                        if scenario_item["build"] == lastBuild and scenario_item["duration"] > duration:
                                            performance_result["result"][scenario["scenario"]] = "failed"
                                        else:
                                            performance_result["result"][scenario["scenario"]] = "pass"
                            else:
                                scenario_item[key] = step_info[key]
                        break
                if scenario_item["result"] == "failed":
                    scenario_item["color"] = "red"
                else:
                    scenario_item["color"] = "green"
                if not scenario_item["result"] == "skipped":
                    scenario_res.append(scenario_item)
    return performance_result


def merge_summary(res):
    for url in res:
        env_res = res[url]
        cursor = {}
        top = {}
        for job_name in env_res["job_summary"]:
            cursor[job_name] = 0
            for summary in env_res["job_summary"][job_name]:
                if job_name not in top or ("Scenarios" in summary and top[job_name] < summary["Scenarios"]):
                    top[job_name] = summary["Scenarios"]
        start_time = ""
        while(True):
            tag = True
            oversize = False

            for job_name in cursor:
                summary_list = env_res["job_summary"][job_name]
                if cursor[job_name] >= len(summary_list) - 1:
                    oversize = True
                    break
            if oversize:
                break
            for job_name in cursor:
                summary_list = env_res["job_summary"][job_name]
                if start_time == "" and "Scenarios" in summary_list[cursor[job_name]] \
                    and "Started on" in summary_list[cursor[job_name]]:
                    start_time = summary_list[cursor[job_name]]["Started on"][:13]
                    break


            for job_name in cursor:
                summary_list = env_res["job_summary"][job_name]
                while ("Started on" not in summary_list[cursor[job_name]] or summary_list[cursor[job_name]]["Started on"][:13] > start_time):
                    cursor[job_name] += 1
                    if cursor[job_name] >= len(summary_list) -1:
                        tag = False
                        break
                else:
                    if not tag:
                        break
                    if (summary_list[cursor[job_name]]["Started on"][:13] < start_time):
                        start_time = summary_list[cursor[job_name]]["Started on"][:13]
                        tag = False
            if tag:
                summary_item = {}
                for key in ["Scenarios","passed","failed","skipped"]:
                    summary_item[key] = 0
                for job_name in cursor:
                    job_summary = env_res["job_summary"][job_name][cursor[job_name]]
                    for key in ["Scenarios", "passed", "failed", "skipped"]:
                        summary_item[key] += int(job_summary[key])
                    for key in ["PORTAL VERSION","PORTAL URL"]:
                        summary_item[key] = job_summary[key]
                    if "Started on" not in summary_item or summary_item["Started on"] > job_summary["Started on"]:
                        summary_item["Started on"] =  job_summary["Started on"]
                    if "Ended on" not in summary_item or summary_item["Ended on"] > job_summary["Ended on"]:
                        summary_item["Ended on"] =  job_summary["Ended on"]
                    cursor[job_name] += 1
                start_time = ""
                env_res["summary"].append(summary_item)


def analysis_context(context_res,context_flags,scenario,scenario_res,conflence_res):
    scenario_res = {"name": scenario["scenario"], "data": scenario_res}
    contexts=[]
    start_list = context_flags["start_list"]
    end_dict = context_flags["end"]
    page_levels = context_flags["page_levels"]
    steps = scenario["steps"]
    for step in steps:
        if step["result"] == "failed":
            find_result = False
            for start_flag in start_list:
                patterns = start_flag[1]
                for pattern in patterns:
                    if step["name"].find(pattern) >= 0:
                        start_context = context_res
                        for name in start_flag[0]:
                            if name not in start_context:
                                start_context[name] = {}
                            start_context = start_context[name]
                        if "scenarios" not in start_context:
                            start_context["scenarios"] = []
                        start_context["scenarios"].append(scenario_res)
                        find_result = True
                        break
                if find_result:
                    break
            if not find_result:
                for end_flag in end_dict:
                    if step["name"].find(end_dict[end_flag]) >=0:
                        if end_flag not in context_res:
                            context_res[end_flag] = {}
                            context_res[end_flag]["scenarios"] = []
                        context_res[end_flag]["scenarios"].append(scenario_res)
                        find_result = True
                        break
            if not find_result:
                level = 0
                for page_level in page_levels:
                    for pattern in page_level:
                        m = re.search(pattern["pattern"], step["name"])
                        if m:
                            page = m.group(1).strip()
                            if "pages" in pattern and (len(contexts) == 0 or contexts[level - 1] not in pattern["pagas"]):
                                continue
                            if ("include" in pattern and page in pattern["include"]) or \
                                    ("exclude" in pattern and page not in pattern["exclude"]) or ("include" not in pattern and "exclude" not in pattern):
                                contexts = contexts[:level]
                                contexts.append(page)
                                break
                    level += 1
                    if find_result:
                        break
            if not find_result:
                context_levels = context_res
                if len(contexts) == 0:
                    contexts = ["Others"]
                for context_name in contexts:
                    if context_name not in context_levels:
                        context_levels[context_name] = {}
                    context_levels = context_levels[context_name]
                if "scenarios" not in context_levels:
                    context_levels["scenarios"] = []
                context_levels["scenarios"].append(scenario_res)
            break
        else:
            for start_flag in start_list:
                patterns = start_flag[1]
                for pattern in patterns:
                    if step["name"].find(pattern) >= 0:
                        contexts = start_flag[2]
                        break
            for end_flag in end_dict:
                if step["name"].find(end_dict[end_flag]) >=0:
                    contexts = []
                    break
            level = 0
            for page_level in page_levels:
                for pattern in page_level:
                    m = re.search(pattern["pattern"],step["name"])
                    if m:
                        page = m.group(1).strip()
                        if ("include" in pattern and page in pattern["include"]) or \
                                ("exclude" in pattern and page not in pattern["exclude"]) or len(pattern) == 1:
                            contexts = contexts[:level]
                            contexts.append(page)
                            break
                level += 1
    scenario_res["data"]["contexts"] = contexts
    if len(contexts) > 0:
        page = contexts[-1].lower()
        for test in confluence_res["tests"]:
            if "conditions" in test and scenario_res["data"]["version"] >= test["Release"]:
                for condition in test["conditions"]:
                    if "pages" in condition and page in condition["pages"]:
                        if "steps" in condition:
                            for step in condition["steps"]:
                                if step.endswith("+"):
                                    new_step = step.strip("+")
                                    previous_step = scenario_res["data"]["previous_step"]
                                    if new_step.find("{}") >= 0:
                                        previous_step = formailise_str(previous_step)
                                    if previous_step.lower().find(new_step.lower()) >= 0:
                                        scenario_res["data"]["JIRA"] = test["JIRA"]
                                        break
                                else:
                                    failed_step = scenario_res["data"]["failed_step"]
                                    if step.find("{}") >= 0:
                                        failed_step= formailise_str(failed_step)
                                    if failed_step.lower().find(step.lower()) >=0:
                                        scenario_res["data"]["JIRA"] = test["JIRA"]
                                        break
                        else:
                            scenario_res["data"]["JIRA"] = test["JIRA"]
                    elif "steps" in condition and "pages" not in condition:
                        for step in condition["steps"]:
                            if step.endswith("+"):
                                new_step = step.strip("+")
                                previous_step = scenario_res["data"]["previous_step"]
                                if new_step.find("{}") >= 0:
                                    previous_step = formailise_str(previous_step)
                                if previous_step.lower().find(new_step.lower()) >= 0:
                                    scenario_res["data"]["JIRA"] = test["JIRA"]
                                    break
                            else:
                                failed_step = scenario_res["data"]["failed_step"]
                                if step.find("{}") >= 0:
                                    failed_step = formailise_str(failed_step)
                                if failed_step.lower().find(step.lower()) >= 0:
                                    scenario_res["data"]["JIRA"] = test["JIRA"]
                                    break
    else:
        print("###" + scenario_res["name"])

def formailise_str(step_str):
    res_str = re.sub("\s+\"[^\"]+\"\s+", " {} ", step_str)
    res_str = re.sub("\s+\"[^\"]+\"", " {}", res_str)
    return res_str

def get_failed_java(scenario,steps_dict,skips):
    steps = scenario["steps"]
    index = 0
    for step in steps:
        if step["result"] == "failed":
            break
        index += 1
    java_file = None
    orignial = None
    while java_file == None:
        keyword = steps[index]["name"]
        items = keyword.split("\"")
        new_items =[]
        for i in range(0,len(items)):
            if i % 2 == 0:
                new_items.append(items[i])
        new_keyword = "{}".join(new_items)
        new_keyword = re.sub(r"(Then|Given|When|But|And)\s*","",new_keyword)
        new_keyword = re.sub(r"\s+", " ", new_keyword)
        new_keyword = re.sub(r" \d+ "," {} ",new_keyword)
        if not orignial:
            orignial = new_keyword


        if new_keyword in steps_dict:
            if steps_dict[new_keyword] in skips:
                index -= 1
            else:
                failed_step = scenario["feature"] + ">>" + scenario["scenario"] + ">>" + orignial
                return steps_dict[new_keyword], failed_step
        else:
            failed_step = scenario["feature"] + ">>" + scenario["scenario"] + ">>" + orignial
            print("*** " + new_keyword + " Not Found")
            return None, failed_step

def analysis_scenario(tag_id, scenario,log_contents,mins=5):
    res = {}
    res["url"] = scenario["scenario_url"]
    if "console_log" in scenario:
        res["console_log"] = scenario["console_log"].split("\n\u001b[m\u001b[37m")
        for log_line in res["console_log"]:
            m = re.search("([^ ]+@threatmetrix\.com)",log_line)
            if m:
                res["user_id"] = m.group(1)
    if "Ended on" in scenario:
        # lag = datetime.timedelta(minutes=mins)
        res["end_time"] = scenario["Ended on"]
        # log_time = datetime.datetime.strptime(res["end_time"],"%Y-%m-%d %H:%M:%S")
        timestamp = scenario["Started on"].replace(" ","T")
        res["logs"]={}
        for log_tag in log_contents:
            res["logs"][log_tag] = []
            for log_item in log_contents[log_tag]:
                if log_item["log_time"] >= timestamp and log_item["log_time"] <= res["end_time"].replace(" ","T"):
                    res["logs"][log_tag].append(log_item)
    res["steps"] = []
    find_failed = False
    for step in scenario["steps"]:
        if step["result"] == "failed":
            res["failed_step"] = step["name"]
            if "error_message" in step:
                res["error_message"] = step["error_message"]
            if "img" in step:
                res["img"] = step["img"]
            find_failed = True
        elif step["name"].lower().find("wait") < 0 and step["name"].lower().find("if exists") < 0 and not find_failed:
            res["previous_step"] = step["name"]
        res["steps"].append(step)
    data_path = scenario["job_name"]+"/"+tag_id+".json"
    json.dump(res,open(data_path,"w"),indent=4)
    previous_step = ""
    if "previous_step" in res:
        previous_step = res["previous_step"]
    return {"url":data_path,"failed_step":res["failed_step"],"previous_step":previous_step}

def get_dailyresult(confluence):
    server_url, page_id, username, token,jira_url,jira_auth = confluence.split("|")
    confluence = Confluence(server_url, username, token=token, verify_ssl=False)
    if jira_url.find("https") < 0:
        jira_server = jira_url.rsplit("/")[0]
        jira_server = "https://" + jira_server
    else:
        jira_server = "https://" + jira_url[8:].split("/")[0]
    jira = JIRA(server=jira_server, token_auth=jira_auth)
    page = confluence.get_page_by_id(page_id, expand="body.storage")
    content = page["body"]["storage"]["value"]
    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")
    res = {"tests":[],"jiras":{}}
    for table in tables:
        ths = table.find_all("th")
        headers = []
        for th in ths:
            headers.append(th.text)
        if "Release" in headers:
            trs = table.find_all("tr")
            for tr in trs:
                tds = tr.find_all("td")
                row = []
                for td in tds:
                    row.append(td.text)
                if len(row) > 0:
                    record = dict(zip(headers,row))
                    if record["StatusGreenPassRedFail"].lower() == "redfail" and record['Reason'].find('JIRA') >=0:
                        if "Release" in record:
                            m = re.search("(\d+\.\d+)", record["Release"])
                            if m:
                                record["Release"] = m.group(1)
                        m = re.search("([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",record['Reason'])
                        if m:
                            uuid = m.group(1)
                            jira_start = record['Reason'].find(uuid)
                            jira_str = record['Reason'][jira_start+36:]
                        record["Scenario"] = record['Test']
                        m = re.search("<([^>]+)>",record["Test"])
                        if m:
                            condition_str = m.group(1)
                            conditions = condition_str.split("|")
                            condition_list = []
                            for condition in conditions:
                                condition_dict = {}
                                if condition.find("&&") > 0:
                                    condition_items = condition.split("&&",1)
                                else:
                                    condition_items = [condition]
                                for condition_item in condition_items:
                                    if condition_item.lower().find("page:") >= 0:
                                        condition_dict["pages"] = [page.strip().lower() for page in condition_item.split(":")[1].split(",")]
                                    elif condition_item.lower().find("step:") >= 0:
                                        condition_dict["steps"] = [step.strip().lower() for step in condition_item.split(":")[1].split(",")]
                                condition_list.append(condition_dict)
                            record["conditions"] = condition_list
                        record["JIRA"] = ""
                        while jira_str.find('JIRA')>=0:
                            jira_start =jira_str.find('JIRA')
                            if record["JIRA"] == "":
                                record["JIRA"] = jira_str[:jira_start]
                            else:
                                record["JIRA"] += "," + jira_str[:jira_start]
                            m = re.search("([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                                          jira_str)
                            if m:
                                uuid=m.group(1)
                                jira_start = jira_str.find(uuid)
                                jira_str = jira_str[jira_start + 36:]
                            else:
                                jira_str = jira_str['Reason'][jira_start + 40:]
                        if record["JIRA"] == "":
                            record["JIRA"] = jira_str.split(" ")[0]
                        else:
                            record["JIRA"]  += "," + jira_str.split(" ")[0]
                        for jira_id in record["JIRA"].split(","):
                            issue = jira.issue(jira_id)
                            res["jiras"][jira_id]={"version":record["Release"],"summary":issue.get_field("summary"),"id":jira_id}
                        res["tests"].append(record)
    res["jira_url"] = jira_url
    return res

def getContext(step,context_flags,previous_context):
    start_list = context_flags["start_list"]
    end_dict = context_flags["end"]
    page_levels = context_flags["page_levels"]
    contexts = previous_context.split(">")
    if step["result"] == "failed":
        for start_flag in start_list:
            patterns = start_flag[1]
            for pattern in patterns:
                if step["name"].find(pattern) >= 0:
                    for name in start_flag[0]:
                        return name
            for end_flag in end_dict:
                if step["name"].find(end_dict[end_flag]) >= 0:
                    if end_flag not in context_res:
                        return end_flag
            level = 0
            for page_level in page_levels:
                for pattern in page_level:
                    m = re.search(pattern["pattern"], step["name"])
                    if m:
                        page = m.group(1).strip()
                        if "pages" in pattern and (
                                len(contexts) == 0 or contexts[level - 1] not in pattern["pagas"]):
                            continue
                        if ("include" in pattern and page in pattern["include"]) or \
                                ("exclude" in pattern and page not in pattern["exclude"]) or (
                                "include" not in pattern and "exclude" not in pattern):
                            contexts = contexts[:level]
                            contexts.append(page)
                            return ">".join(contexts)
                level += 1
    else:
        for start_flag in start_list:
            patterns = start_flag[1]
            for pattern in patterns:
                if step["name"].find(pattern) >= 0:
                    contexts = ">".join(start_flag[2])
        for end_flag in end_dict:
            if step["name"].find(end_dict[end_flag]) >= 0:
                return previous_context
        level = 0
        for page_level in page_levels:
            for pattern in page_level:
                m = re.search(pattern["pattern"], step["name"])
                if m:
                    page = m.group(1).strip()
                    if ("include" in pattern and page in pattern["include"]) or \
                            ("exclude" in pattern and page not in pattern["exclude"]) or len(pattern) == 1:
                        contexts = contexts[:level]
                        contexts.append(page)
                        return ">".join(contexts)
            level += 1
    return previous_context

def timeline_analysis(scenario,timeline_res,context_flags):

    if "tags" not in scenario:
        print("*** no tags in " + scenario["scenario"])
    else:
        container = scenario["tags"][0].strip()[1:]
        pattern = re.compile("(\d+)m (\d+)s (\d+)ms")
        if container not in timeline_res:
            timeline_res[container] = {"start_time":scenario["Started on"],"end_time":scenario["Ended on"],"scenarios":[]}
        scenario_res={"start_time":scenario["Started on"],"end_time":scenario["Ended on"],"steps":[],"result":scenario["result"],"contexts":[]}
        scenario_res["name"] = scenario["scenario"]
        scenario_res["url"] = scenario["scenario_url"]
        step_starttime = datetime.datetime.strptime(scenario["start_time"],"%Y-%m-%dT%H:%M:%S.%fZ")
        context_steps=[]
        context_res={"name":"Login","start_time":scenario_res["start_time"],"steps":[]}
        previous_context = "Login"
        for step in scenario["steps"]:
            step_starttime_str = step_starttime.strftime("%Y-%m-%d %H:%M:%S")
            step_str = step_starttime.strftime("%Y-%m-%d %H:%M:%S") + "|" + step["name"]
            step_context = getContext(step,context_flags,previous_context)
            if not step_context == previous_context:
                context_res["end_time"] = step_starttime_str
                if len(context_res["steps"]) > 0:
                    scenario_res["contexts"].append(context_res)
                context_res = {"name": step_context, "start_time":step_starttime_str , "steps": []}
                previous_context = step_context
            context_res["steps"].append(step_str)
            if "duration" not in step:
                if len(scenario["steps"]) == 1:
                    step["duration"] = scenario["Test Runtime"]
                else:
                    print(step)

            m = pattern.search(step["duration"])
            if m:
                step_starttime += datetime.timedelta(minutes=int(m.group(1)),seconds=int(m.group(2)),milliseconds=int(m.group(3)))
            # scenario_res["steps"].append(step_str)
            if step["result"] == "failed":
                break
        if len(context_res["steps"]) > 0:
            context_res["end_time"] = scenario_res["end_time"]
            scenario_res["contexts"].append(context_res)
        container_res = timeline_res[container]
        if "Ended on" not in scenario:
            print(scenario)
        if scenario["Started on"] < container_res["start_time"]:
            container_res["start_time"] = scenario["Started on"]
            container_res["scenarios"].insert(0,scenario_res)
        elif scenario["Ended on"] > container_res["end_time"] or len(container_res["scenarios"]) == 0:
            container_res["end_time"] = scenario["Ended on"]
            container_res["scenarios"].append(scenario_res)
        else:
            index = 1
            for scenario_item in container_res["scenarios"][1:]:
                if scenario_res["start_time"] < scenario_item["start_time"]:
                    break
                index += 1
            container_res["scenarios"].insert(index,scenario_res)

def parse_context(context_str):
    context_flags = context_str.split(":")
    start_flags = context_flags[0].split("#")
    res ={}
    start_list = []
    for start_flag in start_flags:
        name,patterns,default_page = start_flag.split("|")
        start_list.append([name.split(","),patterns.split(","),default_page.split(",")])
    end_flags = context_flags[1].split(",")
    end_dict = {}
    for end_flag in end_flags:
        name,pattern = end_flag.split("|")
        end_dict[name] = pattern

    page_flags= context_flags[2].split("|")
    page_levels = []
    for page_flag in page_flags:
        page_items =[]
        for page_item_flag in page_flag.replace("{}","\"([^\"]+)\"").split(","):
            page_item = {}
            locked_pages = None
            if page_item_flag.find("@") > 0:
                page_item_flag,locked_pages=page_item_flag.split("@")
                locked_pages = [locked_page.lower() for locked_page in locked_pages.split("#")]
                locked_pages = [locked_page.lower() for locked_page in locked_pages.split("#")]
            if page_item_flag.find("++") > 0:
                pattern,include=page_item_flag.split("++")
                page_item["pattern"] = pattern
                page_item["include"] = include.split("#")
            elif page_item_flag.find("--") > 0:
                pattern,exclude = page_item_flag.split("--")
                page_item["pattern"] = pattern
                page_item["exclude"] = exclude.split("#")
            else:
                page_item["pattern"] = page_item_flag
            if locked_pages:
                page_item["pages"] = locked_pages
            page_items.append(page_item)
        page_levels.append(page_items)
    res["start_list"] = start_list
    res["end"] = end_dict
    res["page_levels"] = page_levels
    return res

if __name__ == "__main__":
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    confluence_res = None
    jira_url = ""
    if args.confluence:
        confluence_res = get_dailyresult(args.confluence)
        jira_url = confluence_res["jira_url"]
    if args.context:
        context_flags = parse_context(args.context)
    else:
        context_flags = None
    server_dict = dict(zip(servers,passwords))
    performances = {}
    if args.performance:
        performance = args.performance.split(":")
        performances["case_id"] = performance[0]
        performances["step"] = performance[1]
        performances["duration"] = int(performance[2])
    ssh_log = ServerLog(args.log_server,args.username,args.private_key)
    input_dir = args.input
    skips = args.skips.split(",")
    report_url = args.report_url
    log_list = args.log_map.split("|")
    lastbuilds = {}
    urls={}
    for server_url in server_dict:
        server= jenkins.Jenkins(server_url, args.username, password=server_dict[server_url])
        all_jobs = server.get_jobs()
        jobs=[]
        job_names = args.jobs.split(",")
        for job in all_jobs:
            for job_name in job_names:
                if job["name"].find(job_name) == 0:
                    jobs.append(job)
        for job in jobs:
            job_info = server.get_job_info(job["name"])
            lastbuilds[job["name"]] = job_info["lastBuild"]["number"]
            urls[job["name"]] = job_info["lastBuild"]["url"]


    files = os.listdir(args.input)
    teams = {}
    log_maps = {}
    for team_str in args.teams.split(","):
        (env, webhook) = team_str.split("|", 1)
        teams[env] = pymsteams.connectorcard(webhook)
        log_maps[env] = [log_bolb.replace("<env>",env) for log_bolb in log_list]
    res = {}
    performance_res={}
    steps_dict={}
    java_analysis={}
    if "result.json" in files:
        steps_dict = json.load(open(input_dir + "/result.json","r"))
    for file_name in files:
        if file_name.endswith(".json") and not file_name == 'result.json' and file_name.lower().find("temp") < 0:
            file_path = args.input + "/" + file_name
            job_name = file_name.split(".")[0]
            section = pymsteams.cardsection()
            section.title(job_name)
            job_info = json.load(open(file_path, "r"))
            job_summary = []
            for build in job_info:
                build_info = job_info[build]
                build_summary = {}
                for key in build_info:
                    if not key == "scenarioes":
                        build_summary[key] = build_info[key]
                job_summary.append(build_summary)
            scenario_id = 0
            if job_name in lastbuilds:
                performance_result = None
                java_analysis[job_name] = {}
                lastBuild = lastbuilds[job_name]
                latestBuild = ""
                for build in job_info:
                    if build > latestBuild:
                        latestBuild = build
                log_contents = {}
                build_res = job_info[latestBuild]
                if "PORTAL URL" in build_res :
                    for env in log_maps:
                        if build_res["PORTAL URL"].find(env) >0:
                            log_map = log_maps[env]
                            start_time = build_res["Started on"].replace(" ","T").split(":")[0]
                            end_time = build_res["Ended on"].replace(" ", "T").split(":")[0]
                            ssh_log.set_duration(start_time,end_time)
                            for log_blob in log_map:
                                log_data=log_blob.replace("<job>",job_name)
                                if len(log_data.split(":")) == 3:
                                    log_name, log_pattern, keyword = log_data.split(":",2)
                                    ssh_log.extract_log(log_name,log_pattern,keyword)
                                else:
                                    log_name, log_pattern, keyword,exclude = log_data.split(":",3)
                                    ssh_log.extract_log(log_name,log_pattern,keyword,exclude=exclude)

                                log_content = []
                                for line in open(log_name+".log","r",encoding="utf8").readlines():
                                    if line.find(ssh_log.test_date + 'T') > 0:
                                        start = line.find(ssh_log.test_date + 'T')
                                        log_time = line[start:start+19]
                                        log_content.append({"log_time":log_time,"content":line[start+19:],"prefix":line[:start]})
                                log_content.sort(key=lambda x:x["log_time"])
                                log_tag = log_name.rsplit("_",1)[1]
                                log_contents[log_tag] = log_content

                    if build_res["PORTAL URL"] not in res:
                        res[build_res["PORTAL URL"]] = {}
                        res[build_res["PORTAL URL"]]["builds"]={}
                        res[build_res["PORTAL URL"]]["PORTAL URL"] =build_res["PORTAL URL"]
                        for env in teams:
                            if build_res["PORTAL URL"].find(env) > 0:
                                res[build_res["PORTAL URL"]]["Env"] = env
                                break
                        res[build_res["PORTAL URL"]]["Total"] = 0
                        res[build_res["PORTAL URL"]]["failed"] = 0
                        res[build_res["PORTAL URL"]]["passed"] = 0
                        res[build_res["PORTAL URL"]]["skipped"] = 0
                        res[build_res["PORTAL URL"]]["jobs"] = {}
                        res[build_res["PORTAL URL"]]["summary"] = []
                        res[build_res["PORTAL URL"]]["job_summary"] = {}
                        res[build_res["PORTAL URL"]]["context"] = {}
                        res[build_res["PORTAL URL"]]["timeline"] = {}
                        res[build_res["PORTAL URL"]]["jobs"][job_name]={}
                    env_res = res[build_res["PORTAL URL"]]
                    context_res= env_res["context"]
                    timeline_res = env_res["timeline"]
                    env_res["version"] = build_res["PORTAL VERSION"]
                    if "jiras" not in env_res and confluence_res:
                        env_res["jiras"] = []
                        for jira_issue in confluence_res["jiras"]:
                            ticket = confluence_res["jiras"][jira_issue]
                            if ticket["version"] <= env_res["version"]:
                                env_res["jiras"].append(ticket)
                    env_res["builds"][job_name] = {"workable":latestBuild,"latest":str(lastBuild)}
                    env_res["build"] = lastBuild
                    env_res["Total"] += int(build_res["Scenarios"])
                    env_res["failed"] += int(build_res["failed"])
                    env_res["passed"] += int(build_res["passed"])
                    env_res["skipped"] += int(build_res["skipped"])
                    res[build_res["PORTAL URL"]]["job_summary"][job_name] = job_summary
                    if job_name not in env_res["jobs"]:
                        env_res["jobs"][job_name] = {}
                    features_res = env_res["jobs"][job_name]
                    for scenario in build_res["scenarioes"]:
                        scenario["job_name"] = job_name
                        timeline_analysis(scenario,timeline_res,context_flags)
                        if scenario["result"] == "failed":
                            if len(steps_dict) > 0:
                                java_file, failed_step = get_failed_java(scenario,steps_dict,skips)
                                if java_file:
                                    if java_file not in java_analysis[job_name]:
                                        java_analysis[job_name][java_file] ={}
                                    java_analysis[job_name][java_file][failed_step] = scenario["scenario_url"]
                            if scenario["feature"] not in features_res:
                                features_res[scenario["feature"]] = {"failed":0,"scenarios":{}}
                            feature_res = features_res[scenario["feature"]]
                            feature_res["failed"] += 1
                            scenario_res = feature_res["scenarios"]
                            scenario_id += 1
                            tag_id = job_name + "_" + str(scenario_id)
                            scenario_item = analysis_scenario(tag_id, scenario,log_contents)
                            scenario_item["version"] = env_res["version"]
                            if confluence_res:
                                scenario_tag = scenario["scenario"][:20]
                                for test in confluence_res["tests"]:
                                    if test["Scenario"].lower().find(scenario_tag.lower()) >= 0 and env_res["version"] >= test["Release"].strip():
                                        scenario_item["JIRA"] = test["JIRA"]
                                        break
                            if scenario["scenario"] not in scenario_res:
                                scenario_res[scenario["scenario"]] = scenario_item
                            else:
                                index = 0
                                for i in range (1,20):
                                    index += 1
                                    scenario_name = scenario["scenario"] + "-" + str(index)
                                    if scenario_name not in scenario_res:
                                        scenario_res[scenario_name] = scenario_item
                                        break

                            if context_flags:
                                analysis_context(context_res,context_flags,scenario,scenario_res[scenario["scenario"]],confluence_res)
                            if "url" not in feature_res:
                                feature_res["url"] = scenario["feature_url"]
                if len(performances) > 0:
                    latest_build_info = job_info[latestBuild]
                    if latest_build_info["PORTAL URL"] not in performance_res:
                        performance_res[latest_build_info["PORTAL URL"]] = {}
                    performance_res[latest_build_info["PORTAL URL"]] = analysis_performance(performances, job_info,performance_res[latest_build_info["PORTAL URL"]], str(lastBuild))
    for build_url in performance_res:
        if build_url not in res:
            res[build_url] = {"jobs":{}}
        if "Performance Test" not in res[build_url]["jobs"] :
            res[build_url]["jobs"]["Performance Test"] = performance_res[build_url]


    if len(steps_dict) > 0:
        json.dump(java_analysis,open("results.json","w"),indent=4)

    if len(res) > 0:
        merge_summary(res)
        json.dump(res,open("analysis.json","w"),indent=4)

    for env in teams:
        send_flag = True
        for portal_url in res:
            if portal_url.find(env) >= 0:
                env_res = res[portal_url]
                for job in env_res["builds"]:
                    job_builds = env_res["builds"][job]
                    if not job_builds["workable"] == job_builds["latest"] :
                        send_flag = True
                        break
                teams[env].title("Failed Scenarios Against Feature Distribution")
                team_text = "**Total : " + str(env_res["Total"]) + " <strong style='color:red;'>Failed : " + str(env_res["failed"]) + "</strong>** Version : " +  env_res[
                                        "version"] + " Portal : " + portal_url + "\n\n<H2>Please check auto test results on Workspace:" +report_url +"</H2>"
                teams[env].text(team_text)

                jobs = [key for key in res[portal_url]["jobs"]]
                jobs.sort()
                for job in jobs:
                    job_data = res[portal_url]["jobs"][job]
                    if "_type" in job_data and job_data["_type"] == "report" and "data" in job_data:
                        data_type = job_data["data"]
                        if data_type in job_data and len(job_data[data_type]) > 0:
                            section = pymsteams.cardsection()
                            section.title("# **" + job + "**")
                            section.linkButton("Workspace",report_url)
                            section_text = "\n\n<ul>"

                            for item in job_data[data_type]:
                                section_text +="<li>" + item + " : " + str(job_data[data_type][item]) + "s </li>"
                            section_text += "</ul>"
                            section.text(section_text)
                            teams[env].addSection(section)

                for job in jobs:
                    job_data = res[portal_url]["jobs"][job]
                    if "_type" not in job_data or not job_data["_type"] == "report":
                        section = pymsteams.cardsection()
                        if job in urls:
                            section.title("# **JOB : [" + job +"]("+urls[job] +"Cluecumber_20Test_20Report/)**")
                        else:
                            section.title("# **JOB : " + job +"**")
                        section_text = "\n\n<ul>"
                        # section_text += "\n\n**Features:**"
                        features = env_res["jobs"][job]
                        feature_list = [feature for feature in features.keys()]
                        feature_list.sort()
                        if len(feature_list) > 0:
                            for feature in feature_list:
                                checked_num = 0
                                scenario_list = features[feature]["scenarios"]
                                for scenario_name in scenario_list:
                                    if "JIRA" in scenario_list[scenario_name]:
                                        checked_num +=1
                                section_text += "<li><a href='" + features[feature]["url"] + "'>" + feature+ " (" + str(checked_num) + "/" +  str(features[feature]["failed"]) + ")</a></li>"
                        else:
                            section_text += "<strong style='color:green;'>  Congratulation! No feature failed in this job! </strong>"
                        section_text +="</ul>"
                        section.text(section_text)
                        teams[env].addSection(section)
                teams[env].color(mcolor="red")
        if send_flag:
            try:
                # teams[env].printme()
                teams[env].send()
            except Exception as e:
                print(e)
                print("*** Could not send message to Teams")
                pass
    context = {"report_url":report_url,"jira_url":jira_url}
    template = open("index.template","r").read()
    html = Template(template).render(Context(context))
    open("index.html","w").write(html)




