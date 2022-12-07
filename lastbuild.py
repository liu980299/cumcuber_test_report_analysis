import datetime
import json
import os
import sys
from time import sleep
import jenkins
import requests
from template import *
from bs4 import BeautifulSoup
from atlassian import Confluence
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--username", help="username", required=True)
parser.add_argument("--passwords", help="passowrd", required=True)
parser.add_argument("--confluence",help="conflence source and confidential")
parser.add_argument("--servers", help="Jenkins Server", required=True)
parser.add_argument("--skips", help="folder would be skipped", required=True)
parser.add_argument("--targets", help="target job names", required=True)
parser.add_argument("--source", help="qa environment version source", required=True)

args = parser.parse_args()
def get_confluence(confluence):
    server_url,page_id,username,token=confluence.split("|")
    confluence = Confluence(server_url,username,token=token,verify_ssl=False)
    page = confluence.get_page_by_id(page_id,expand="body.storage")
    content = page["body"]["storage"]["value"]
    soup = BeautifulSoup(content, "html.parser")
    tr_lines = soup.find_all("tr")
    res = {"components":["Environment"],"data":{}}
    components = res["components"]
    for tr in tr_lines:
        tds = tr.find_all("td")
        tds_list = [td for td in tds]
        if len(tds_list) > 0:
            component = tds_list[0].text
            components.append(component)
            res["data"][component] = tds_list[-1].text
    return res

def get_versions(source,username,server_dict):
    res = []
    for server_url in server_dict:
        if source.find(server_url) >= 0:
            password = server_dict[server_url]
            server = jenkins.Jenkins(server_url,username,password)
            response = server.jenkins_request(requests.Request('GET',source))
            html = response.text.replace("table/>","table>")
            soup = BeautifulSoup(html,"html.parser")
            envirs = [envir.text for envir in soup.find_all("b") if not envir.text == ""]
            versions = [version for version in soup.find_all("table")]
            index=0
            for version in versions:
                item = {}
                item["Environment"]=envirs[index]
                tr_lines = version.find_all("tr")
                for tr_line in tr_lines:
                    tds = [ td for td in tr_line.find_all("td")]
                    if len(tds) > 0:
                        component = tds[0].text
                        value = tds[-1].text
                        item[component] = value
                res.append(item)
                index += 1
    return res


if __name__ == "__main__":
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    server_dict = dict(zip(servers, passwords))
    skips = args.skips.split(",")
    confluence = args.confluence
    source = args.source

    jobs_dict = get_confluence(confluence)
    versions= get_versions(source,args.username,server_dict)
    print(json.dumps(jobs_dict,indent=4))
    targets = args.targets.split(",")
    res ={}
    components = jobs_dict["components"]

    for component in jobs_dict["data"]:
        password = None
        for server_url in server_dict:
            if jobs_dict["data"][component].find(server_url) >= 0:
                password = server_dict[server_url]
                break
        server = jenkins.Jenkins(jobs_dict["data"][component], args.username, password=password)
        all_jobs = server.get_jobs()
        jobs ={}
        for job in all_jobs:
            jobs[job["name"]] = job
        for target in targets:
            job_name = None
            for job in jobs:
                if job.find(target) >= 0:
                    job_name = job
                    break
            if job_name:
                job_info = server.get_job_info(job_name)
                if job_info:
                    if job_info["lastSuccessfulBuild"]:
                        lastBuild = job_info["lastSuccessfulBuild"]["number"]
                        build_info = server.get_build_info(job_name, lastBuild)
                        res[component] = build_info
                    else:
                        print(component + ": No Successful Build")
                break
    last_build = {"Environment":"Last Build"}
    for component in res:
        if "displayName" in res[component]:
            last_build[component] = res[component]["displayName"].split(":")[-1]
        else:
            last_build[component] = "No Successful Build Available"

    versions.insert(0,last_build)
    context={}
    context["components"] = components
    context["versions"] = versions
    context["updatetime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    template = open("versions.template","r").read()
    html = Template(template).render(Context(context))
    open("versions.html","w").write(html)

    for component in res:
        if "displayName" in res[component]:
            print(component + ":" + res[component]["displayName"])
        else:
            print(component + ":" + json.dumps(res[component]))