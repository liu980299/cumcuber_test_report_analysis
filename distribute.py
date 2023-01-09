import datetime
import json
import re

import jenkins
import argparse, os, urllib.parse, pymsteams

import requests

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
parser.add_argument("--skips", help="skipped java file, if failuare in skip java file, the previous step would be checked ", required=True)

args = parser.parse_args()

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

def analysis_scenario(scenario,log_contents,mins=3):
    res = {}
    res["url"] = scenario["scenario_url"]
    if "console_log" in scenario:
        res["console_log"] = scenario["console_log"].split("\n\u001b[m\u001b[37m")
    if "Ended on" in scenario:
        lag = datetime.timedelta(minutes=mins)
        res["end_time"] = scenario["Ended on"]
        log_time = datetime.datetime.strptime(res["end_time"],"%Y-%m-%d %H:%M:%S")
        timestamp = (log_time - lag).strftime("%Y-%m-%dT%H:%M:%S")
        res["logs"]={}
        for log_tag in log_contents:
            res["logs"][log_tag] = []
            for log_item in log_contents[log_tag]:
                if log_item["log_time"] >= timestamp and log_item["log_time"] <= res["end_time"].replace(" ","T"):
                    res["logs"][log_tag].append(log_item)
    res["steps"] = []
    for step in scenario["steps"]:
        if step["result"] == "passed":
            res["steps"].append(step["name"])
        if step["result"] == "failed":
            res["failed_step"] = step["name"]
            if "error_message" in step:
                res["error_message"] = step["error_message"]
            if "img" in step:
                res["img"] = step["img"]
    return res




if __name__ == "__main__":
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    server_dict = dict(zip(servers,passwords))
    ssh_log = ServerLog(args.log_server,args.username,args.private_key)
    input_dir = args.input
    skips = args.skips.split(",")
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
    steps_dict={}
    java_analysis={}
    if "result.json" in files:
        steps_dict = json.load(open(input_dir + "/result.json","r"))
    for file_name in files:
        if file_name.endswith(".json") and not file_name == 'result.json':
            file_path = args.input + "/" + file_name
            job_name = file_name.split(".")[0]
            section = pymsteams.cardsection()
            section.title(job_name)
            job_info = json.load(open(file_path, "r"))
            if job_name in lastbuilds:
                java_analysis[job_name] = {}
                lastBuild = lastbuilds[job_name]
                log_contents = {}
                if str(lastBuild) in job_info:
                    build_res = job_info[str(lastBuild)]
                    if "PORTAL URL" in build_res :
                        for env in log_maps:
                            if build_res["PORTAL URL"].find(env) >0:
                                log_map = log_maps[env]
                                start_time = build_res["Started on"].replace(" ","T").split(":")[0]
                                end_time = build_res["Ended on"].replace(" ", "T").split(":")[0]
                                ssh_log.set_duration(start_time,end_time)
                                for log_blob in log_map:
                                    log_data=log_blob.replace("<job>",job_name)
                                    log_name, log_pattern, keyword = log_data.split(":",2)
                                    ssh_log.extract_log(log_name,log_pattern,keyword)
                                    log_content = []
                                    for line in open(log_name+".log","r").readlines():
                                        if line.find(ssh_log.test_date) > 0:
                                            start = line.find(ssh_log.test_date)
                                            log_time = line[start:start+19]
                                            log_content.append({"log_time":log_time,"content":line[start+19:],"prefix":line[:start]})
                                    log_content.sort(key=lambda x:x["log_time"])
                                    log_tag = log_name.rsplit("_",1)[1]
                                    log_contents[log_tag] = log_content

                        if build_res["PORTAL URL"] not in res:
                            res[build_res["PORTAL URL"]] = {}
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
                            res[build_res["PORTAL URL"]]["jobs"][job_name]={}
                        env_res = res[build_res["PORTAL URL"]]
                        env_res["version"] = build_res["PORTAL VERSION"]
                        env_res["build"] = lastBuild
                        env_res["Total"] += int(build_res["Scenarios"])
                        env_res["failed"] += int(build_res["failed"])
                        env_res["passed"] += int(build_res["passed"])
                        env_res["skipped"] += int(build_res["skipped"])
                        if job_name not in env_res["jobs"]:
                            env_res["jobs"][job_name] = {}
                        features_res = env_res["jobs"][job_name]
                        for scenario in build_res["scenarioes"]:
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
                                scenario_res[scenario["scenario"]] = analysis_scenario(scenario,log_contents)
                                if "url" not in feature_res:
                                    feature_res["url"] = scenario["feature_url"]
    if len(steps_dict) > 0:
        json.dump(java_analysis,open("results.json","w"),indent=4)
    for env in teams:
        for portal_url in res:
            if portal_url.find(env) >= 0:
                env_res = res[portal_url]
                teams[env].title("Failed Scenarios Against Feature Distribution")
                team_text = "**Total : " + str(env_res["Total"]) + " <strong style='color:red;'>Failed : " + str(env_res["failed"]) + "</strong>** Version : " +  env_res[
                                        "version"] + " Portal : " + portal_url
                teams[env].text(team_text)
                jobs = [key for key in res[portal_url]["jobs"]]
                jobs.sort()
                for job in jobs:
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
                            section_text += "<li><a href='" + features[feature]["url"] + "'>" + feature+ " (" + str(features[feature]["failed"]) + ")</a></li>"
                    else:
                        section_text += "<strong style='color:green;'>  Congratulation! No feature failed in this job! </strong>"
                    section_text +="</ul>"
                    section.text(section_text)
                    teams[env].addSection(section)
                teams[env].color(mcolor="red")
        teams[env].send()
    if len(res) > 0:
        json.dump(res,open("analysis.json","w"),indent=4)

