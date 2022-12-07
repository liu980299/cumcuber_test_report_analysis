import json
import jenkins
import argparse, os, urllib.parse, pymsteams

parser = argparse.ArgumentParser()
parser.add_argument("--username",help="username",required=True)
parser.add_argument("--passwords",help="passowrd",required=True)
parser.add_argument("--servers",help="Jenkins Server",required=True)
parser.add_argument("--jobs", help="job name list and delimiter ','",required=True)
parser.add_argument("--input", help="Test Result folder", required=True, default="c:/cucumber-result/")
parser.add_argument("--teams", help="teams webhook connectors", required=True)
args = parser.parse_args()


if __name__ == "__main__":
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    server_dict = dict(zip(servers,passwords))
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
    for team_str in args.teams.split(","):
        (env, webhook) = team_str.split("|", 1)
        teams[env] = pymsteams.connectorcard(webhook)
    res = {}
    for file_name in files:
        if file_name.endswith(".json"):
            file_path = args.input + "/" + file_name
            job_name = file_name.split(".")[0]
            section = pymsteams.cardsection()
            section.title(job_name)
            job_info = json.load(open(file_path, "r"))
            if job_name in lastbuilds:
                lastBuild = lastbuilds[job_name]
                if str(lastBuild) in job_info:
                    build_res = job_info[str(lastBuild)]
                    if "PORTAL URL" in build_res :
                        if build_res["PORTAL URL"] not in res:
                            res[build_res["PORTAL URL"]] = {}
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
                                if scenario["feature"] not in features_res:
                                    features_res[scenario["feature"]] = {"failed":0}
                                feature_res = features_res[scenario["feature"]]
                                feature_res["failed"] += 1
                                if "url" not in feature_res:
                                    feature_res["url"] = scenario["feature_url"]

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
