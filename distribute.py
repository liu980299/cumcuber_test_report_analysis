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
            res = {}
            job_info = server.get_job_info(job["name"])
            lastbuilds[job["name"]] = job_info["lastBuild"]["number"]

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
                            res[build_res["PORTAL URL"]]["features"] = {}
                        env_res = res[build_res["PORTAL URL"]]
                        env_res["version"] = build_res["PORTAL VERSION"]
                        env_res["build"] = lastBuild
                        env_res["Total"] += int(build_res["Scenarios"])
                        env_res["failed"] += int(build_res["failed"])
                        env_res["passed"] += int(build_res["passed"])
                        env_res["skipped"] += int(build_res["skipped"])
                        features_res = env_res["features"]
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
                team_text = "**Total : " + str(env_res["Total"]) + " Failed : " + str(env_res["failed"]) + "** Version : " +  env_res[
                                        "version"] + " Portal : " + portal_url
                team_text += "\n\n**Features:**\n\n"
                features = env_res["features"]
                feature_list = [feature for feature in features.keys()]
                feature_list.sort()
                team_text += "\n\n"
                for feature in feature_list:
                    team_text += "\n\n  [" + feature+ " (" + str(features[feature]["failed"]) + ")]("+ features[feature]["url"] +")"
                teams[env].text(team_text)
                teams[env].color(mcolor="red")
        teams[env].send()
