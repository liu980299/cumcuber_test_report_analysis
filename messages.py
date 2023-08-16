import time

import jenkins
import pymsteams
import requests
import argparse,json,re

parser = argparse.ArgumentParser()
parser.add_argument("--jenkins",help="jenkins args",required=True)
parser.add_argument("--jobs",help="job names",required=True)
parser.add_argument("--teams",help="teams web hooks",required=True)

args = parser.parse_args()

def teams_send(webhook):
    try:
        webhook.send()
    except requests.exceptions.ConnectTimeout as e:
        print("Teams connection failed. sleep 10s and reconnect ...")
        time.sleep(10)
        teams_send(webhook)


if __name__ == "__main__":
    server_url, job_name, username, password = args.jenkins.split("|")
    server = jenkins.Jenkins(server_url, username, password)
    job_info = server.get_job_info(job_name)
    job_args = args.jobs.split("|")
    teams = {}
    for team_str in args.teams.split(","):
        (env, webhook) = team_str.split("|", 1)
        teams[env] = pymsteams.connectorcard(webhook)

    bookmarks = [job.split(":")[0].strip("#") for job in job_args if job.find("#") >= 0 ]
    jobs = [job.split(":")[0].strip("#") for job in job_args]
    reports = [job.split(":")[1] for job in job_args]
    job_reports = dict(zip(jobs,reports))
    jobs_build ={}
    if "lastSuccessfulBuild" in job_info and job_info["lastSuccessfulBuild"]:
        last_successful_task = job_info["lastSuccessfulBuild"]["url"] + "/messages/messages.json"
        response = server.jenkins_request(requests.Request('GET',last_successful_task))
        jobs_build = json.loads(response.text)
    res = {}
    for job_name in jobs:
        job_info = server.get_job_info(job_name)
        if job_name in jobs_build:
            build = jobs_build[job_name]
            max_build = build
            if job_name in bookmarks:
                builds = job_info["builds"]
                for build_info in builds:
                    if build_info["number"] > int(build):
                        message_json_url = build_info["url"] + "/" + job_reports[job_name] + "/messages.json"
                        response = server.jenkins_request(requests.Request('GET',message_json_url))
                        if response.status_code == "200":
                            if build_info["number"] > max_build:
                                max_build = build_info["number"]
                            messages_json = json.loads(response.text)
                            for env in messages_json:
                                if env in teams:
                                    teams[env].payload = messages_json[env]
                                    teams[env].send()
            else:
                last_build = job_info["lastSuccessfulBuild"]["number"]
                if last_build > int(build):
                    message_json_url = job_info["lastSuccessfulBuild"]["url"] + "/" + job_reports[job_name] + "/messages.json"
                    response = server.jenkins_request(requests.Request('GET', message_json_url))
                    if response.status_code == 200:
                        if build_info["number"] > max_build:
                            max_build = build_info["number"]
                        messages_json = json.loads(response.text)
                        for env in messages_json:
                            if env in teams:
                                teams[env].payload = messages_json[env]
                                teams_send(teams[env])
            res[job_name] = max_build
        else:
            last_build = job_info["lastSuccessfulBuild"]["number"]
            res[job_name] = last_build
            message_json_url = job_info["lastSuccessfulBuild"]["url"] + "/" + job_reports[job_name] + "/messages.json"
            try:
                response = server.jenkins_request(requests.Request('GET', message_json_url))
                if response.status_code == 200:
                    messages_json = json.loads(response.text)
                    for env in messages_json:
                        if env in teams:
                            teams[env].payload = messages_json[env]
                            teams_send(teams[env])

            except requests.exceptions.HTTPError as e:
                print("no messages found for " + job_name)
                pass
            except jenkins.NotFoundException as e:
                pass

    message_json = open("messages.json","w")
    json.dump(res,message_json,indent=4)
    message_json.close()




