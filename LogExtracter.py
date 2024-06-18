import os,re
from time import sleep

import SSHLibrary
import argparse,hashlib
import datetime,requests
import zipfile,jenkins,json,gzip,shutil
from LogParser import LogParser
import pymsteams


class ServerLog:
    def __init__(self, server, username, private_key):
        self.sshclient = SSHLibrary.SSHLibrary()
        self.sshclient.open_connection(server)
        self.login_output = self.sshclient.login_with_public_key(username,private_key)

    def set_duration(self, start_time,end_time):
        self.test_date= start_time.split("T")[0]
        self.start_time = start_time.rsplit(":",1)[0]
        self.end_time = (datetime.datetime.strptime(end_time,"%Y-%m-%dT%H:%M:%S") + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M")
        # end_hour = end_time.split("T")[1]
        # self.match_str = self.test_date + "T("
        # for hour in range(int(start_hour), int(end_hour) + 1):
        #     self.match_str += str(hour).zfill(2) + ":[0-5][0-9]:[0-5][0-9]|"
        # self.match_str = self.match_str.strip("|")
        # self.match_str += ")"

    def extract_log(self, log_name,log_files):
        log_name = log_name.replace("<date>",self.test_date)
        self.log_file = log_name + ".log"
        print("Extracting " + self.log_file +"...")
        self.zip_file = log_name + ".gz"

        if (os.path.exists(self.zip_file)):
            os.remove(self.zip_file)

        test_date = (datetime.datetime.strptime(self.test_date,"%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d") + "*,"+self.test_date
        log_files = log_files.replace("<date>",test_date)

        # if exclude:
        #     command = "zstdgrep -E \"" + self.match_str + "\" " + log_files + "|grep -i " + keyword + "|grep -iv "+ exclude + ">" + log_name + ".log"
        # else:
        #     command = "zstdgrep -E \"" + self.match_str + "\" " + log_files + "|grep -i " + keyword + ">" + log_name + ".log"
        command = "rm " + self.zip_file + ";rm " + self.log_file + ";for logfile in " + log_files + ";do "
        command += "export end=`zstdgrep -n -m 1  \"" + self.end_time + "\" $logfile|cut -d ':' -f 1`;export start=`zstdgrep -n -m 1 \"" + self.start_time + "\" "
        command += "$logfile |cut -d ':' -f 1`;if [ ! -z $start ] || [ ! -z $end ];then [ -z $start ]&& export start=1;[ -z $end ]&& export end=`zstdcat $logfile|wc -l`;"
        command += "zstdcat $logfile|sed -n \"${start},${end}p\" >>" + self.log_file + ";fi;done"

        ret = self.sshclient.execute_command(command)

        if len(ret) == 3 and not ret[2] == 0:
            print(ret)
        else:
            try:
                zipCommand = "gzip -c " + self.log_file + " >" +self.zip_file
                self.sshclient.execute_command(zipCommand)
                self.sshclient.get_file( self.zip_file)
                with gzip.open(self.zip_file, 'rb') as f_in:
                    with open(self.log_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        f_in.close()
                        f_out.close()
                # zipfile.ZipFile(self.zip_file, "r").extract(self.log_file)
                setattr(self,self.log_file,True)
                return True
            except Exception as e:
                print("Not found "+ self.log_file)
                setattr(self, self.log_file, False)
                return False

    def __del__(self):
        self.sshclient.close_connection()

def setStepWorker(step, worker, log_cfg):
    if "workers" not in step:
        # step["worker"] = []
        step["workers"] = {}
    # step["worker"].append(worker)
    if "error" in worker and "level" in worker["error"]:
        if "errors" not in step:
            step["errors"] = []
        step["errors"].append(worker["error"])
    if "name" not in worker:
        print ("*** name not in worker **")
        print(worker)
    else:
        worker_item = {"session":worker["session"],"id":worker["id"],"start_time":worker["start_time"]}
        if worker["name"] not in step["workers"]:
            step["workers"][worker["name"]] = [worker_item]
        else:
            step["workers"][worker["name"]].append(worker_item)
            if worker["name"] not in log_cfg["ignores"]:
                if "duplicated" not in step:
                    step["duplicated"] = []
                if worker["name"] not in step["duplicated"]:
                    step["duplicated"].append(worker["name"])

def setScenario(logparser, scenario, log_cfg, users):
    session_list = []
    scenario["log_file"] = logparser.name
    for user in scenario["test_users"]:
        session_user = user.lower()
        if session_user in logparser.sessions:
            user_sessions = logparser.sessions[session_user]
            if type(scenario["test_users"][user]) == dict:
                current_user_time = scenario["test_users"][user]
                session = matchUserTime(logparser, session_user,current_user_time,scenario,log_cfg)
                if not session:
                    print("*** not finding session for user :" + user)
                    # logparser.dumpSession(session)
                else:
                    session_list.append(session)
            else:
                for item in scenario["test_users"][user]:
                    session = matchUserTime(logparser, session_user,item,scenario,log_cfg)
                    if not session:
                        print("*** not finding session for user :" + user)
                    else:
                        session_list.append(session)

    if scenario["result"].lower() == "failed" or "duplicated" in scenario:
        for session in session_list:
            logparser.dumpSession(session)


def matchUserTime(logparser, username, user_time,scenario, log_cfg):
    user_sessions = logparser.sessions[username]
    for start_time in user_sessions:
        if not start_time == "index":
            startTime = start_time.replace("T", " ")
            if user_time["start_time"] < startTime and user_time["end_time"] > startTime:
                user_sessions[start_time]["scenario"] = scenario["name"]
                if "session_ids" not in scenario:
                    scenario["session_ids"] = []
                session = user_sessions[start_time]
                scenario["session_ids"].append(session["id"])
                if "worker" in session:
                    index = 0
                    steps = scenario["steps"]
                    work_index = 0
                    split_session = False
                    for worker in session["worker"]:
                        startTime = worker["start_time"].replace("T", " ")
                        worker_dict = {"log_file":logparser.name}
                        for key in ["id","name","start_time","end_time","error","session"]:
                            if key in worker:
                                worker_dict[key] = worker[key]
                        while index <= len(steps) - 1:
                            if steps[index]["start_time"] > startTime:
                                break
                            index += 1
                        if startTime > user_time["end_time"]:
                            split_session = True
                            break
                            # if "errors" not in scenario:
                            #     scenario["errors"] = []
                            # scenario["errors"].append(worker_dict)
                        else:
                            setStepWorker(steps[index - 1], worker_dict ,log_cfg)
                            if "duplicated" in steps[index - 1]:
                                if "duplicated" not in scenario:
                                    scenario["duplicated"] = []
                                if steps[index - 1]["name"] not in scenario["duplicated"]:
                                    scenario["duplicated"].append(steps[index - 1]["name"])
                        work_index += 1

                    if split_session:
                        new_session = {"type":"session"}
                        new_session[logparser.key] = session[logparser.key]
                        new_session["worker"] = session["worker"][work_index:]
                        new_session["start_time"] = session["worker"][work_index]["start_time"]
                        if "end_time" in session:
                            new_session["end_time"] = session["end_time"]
                        session["end_time"] = user_time["end_time"]
                        session["worker"] = session["worker"][:work_index]
                        logparser.injectByTime(user_sessions,new_session)
                        logParser.session_list.append(new_session)
                        new_session["id"] = len(logparser.session_list)
                        for worker in new_session["worker"]:
                            worker["session"] = new_session["id"]
                            worker["id"] = worker["id"] - work_index
                            if "error" in worker and "level" in worker["error"]:
                                error = worker["error"]
                                error["worker"] = worker["id"]
                                error["session"] = new_session["id"]
                                if error["id"] in session["errors"][logparser.name]:
                                    session["errors"][logparser.name].pop(error["id"])
                                if "errors" not in new_session:
                                    new_session["errors"] = {logparser.name: {}}
                                    new_session["errors"][logparser.name][error["id"]] = error

                if "errors" in session:
                    for log_error in session["errors"]:
                        for error_id in session["errors"][log_error]:
                            session["errors"][log_error][error_id]["scenario"] = scenario["name"]
                    if "errors" not in scenario:
                        scenario["errors"] = []
                    scenario["errors"].append(session["errors"])
                return user_sessions[start_time]

def parseContainer(res,container_data, log_data):
    scenarios = container_data["scenarios"]
    users = log_data["users"]
    for scenario in scenarios:
        res[scenario["name"]] = scenario
        test_users = {}
        if "test_users" in scenario:
            log_data["matchable"] +=1
            for test_user in scenario["test_users"]:
                test_user_name = test_user.lower()
                if not test_user == "assigned":
                    if test_user not in users:
                        users[test_user_name] = {}
                test_user_data = scenario["test_users"][test_user]
                if type(test_user_data) == dict:
                    test_users[test_user_data["start_time"]] = test_user
                    users[test_user_name][test_user_data["start_time"]] = {"scenario":scenario["name"],"end_time":test_user_data["end_time"]}
                elif type(test_user_data) == list:
                    for item in test_user_data:
                        test_users[item["start_time"]] = test_user
                        users[test_user_name][item["start_time"]] = {"scenario":scenario["name"],"end_time":item["end_time"]}
                elif not test_user == "assigned":
                    print("***unexpceted data in test usrs : " + str(test_user_data))
        if "test_data_users" in scenario:
            for test_user in scenario["test_data_users"]:
                if test_user not in scenario["test_users"]:
                    if test_user not in users:
                        users[test_user] = {}
                    if scenario["start_time"] not in users[test_user]:
                        users[test_user][scenario["start_time"]] = {"scenario":scenario["name"],"end_time":scenario["end_time"]}
        start_times = [key for key in test_users.keys()]
        start_times.sort()
        index = 0
        contexts = scenario.pop("contexts")
        for context in contexts:
            for step in context["steps"]:
                start_time, name = step.split("|",1)
                step_data = {"start_time": start_time, "name": name}
                scenario["steps"].append(step_data)
                if index <= len(start_times) - 1:
                    if start_time >= start_times[index]:
                        if index < len(start_times) - 1:
                            if start_time < start_times[index + 1]:
                                step_data["user"] = test_users[start_times[index]]
                            else:
                                index += 1
                                if start_time >= start_times[index]:
                                    step_data["user"] = test_users[start_times[index]]

                    step_data["user"] = test_users[start_times[index]]


def parseTests(server,env,data_url,timelines, log_data):
    res = {}
    if data_url == "":
        for container in timelines:
            container_file = open(env + "/" + container +".json","r",encoding="utf-8")
            container_data = json.load(container_file)
            parseContainer(res,container_data, users)
    else:
        workspace = data_url.rsplit("/",1)[0]
        for container in timelines:
            get_data = False
            while (not get_data):
                try:
                    response = server.jenkins_request(requests.Request('GET', workspace + "/" + env+ "/" + container + ".json"))
                    get_data = True
                except Exception as e:
                    print("Connection error ...")
                    sleep(5)
            container_data = json.loads(response.text)
            parseContainer(res,container_data, log_data)
    return res



def mergeTests(envData, logpaser,users,log_cfg):
    for user in logpaser.sessions:
        if user in users:
            sessions = logpaser.sessions[user]
            session_times = [start_time for start_time in sessions if not start_time == "index"]
            for start_time in session_times:
                session = sessions[start_time]
                new_session = matchSession(envData,logpaser,session,users[user],log_cfg)
                while new_session:
                    new_session = matchSession(envData,logpaser,new_session,users[user],log_cfg)

    # for scenario in tests:
    #     setScenario(logpaser,tests[scenario], log_cfg)

def matchSession(envData,logparser,session,users,log_cfg):
    tests = envData["tests"]
    start_time = session["start_time"].replace("T", " ")
    user_sessions = logparser.sessions[session[logparser.key]]
    for user_start in users:
        if user_start < start_time and users[user_start]["end_time"] > start_time:
            user_time = users[user_start]
            scenario_name = users[user_start]["scenario"]
            scenario = tests[scenario_name]
            if "has_logs" not in scenario:
                scenario["has_logs"] = True
                envData["matched"] += 1
                if scenario["result"] == "failed":
                    envData["match_failed"] += 1
            session["scenario"] = scenario["name"]
            if "session_ids" not in scenario:
                scenario["session_ids"] = []
            scenario["session_ids"].append(session["id"])
            new_session = None
            if "worker" in session:
                index = 0
                steps = scenario["steps"]
                work_index = 0
                split_session = False
                for worker in session["worker"]:
                    startTime = worker["start_time"].replace("T", " ")
                    worker_dict = {"log_file": logparser.name}
                    for key in ["id", "name", "start_time", "end_time", "error", "session"]:
                        if key in worker:
                            worker_dict[key] = worker[key]
                    while index <= len(steps) - 1:
                        if steps[index]["start_time"] > startTime:
                            break
                        index += 1
                    if startTime > user_time["end_time"]:
                        split_session = True
                        break
                        # if "errors" not in scenario:
                        #     scenario["errors"] = []
                        # scenario["errors"].append(worker_dict)
                    else:
                        setStepWorker(steps[index - 1], worker_dict, log_cfg)
                        if "duplicated" in steps[index - 1]:
                            if "duplicated" not in scenario:
                                scenario["duplicated"] = []
                            if steps[index - 1]["name"] not in scenario["duplicated"]:
                                scenario["duplicated"].append(steps[index - 1]["name"])
                    work_index += 1



                if split_session:
                    new_session = {"type": "session"}
                    new_session[logparser.key] = session[logparser.key]
                    new_session["worker"] = session["worker"][work_index:]
                    new_session["start_time"] = session["worker"][work_index]["start_time"]
                    if "end_time" in session and session["end_time"] > new_session["start_time"]:
                        new_session["end_time"] = session["end_time"]
                    session["end_time"] = user_time["end_time"]
                    session["worker"] = session["worker"][:work_index]
                    logparser.injectByTime(user_sessions, new_session)
                    logParser.session_list.append(new_session)
                    new_session["id"] = len(logparser.session_list)
                    for worker in new_session["worker"]:
                        worker["session"] = new_session["id"]
                        if not "end_time" in new_session:
                            new_session["end_time"] = worker["end_time"]
                        if "end_time" in worker and worker["end_time"] > new_session["end_time"]:
                            new_session["end_time"] = worker["end_time"]
                        worker["id"] = worker["id"] - work_index
                        if "error" in worker and "level" in worker["error"]:
                            error = worker["error"]
                            error["worker"] = worker["id"]
                            error["session"] = new_session["id"]
                            if error["id"] in session["errors"][logparser.name]:
                                session["errors"][logparser.name].pop(error["id"])
                            if "errors" not in new_session:
                                new_session["errors"] = {logparser.name: {}}
                            new_session["errors"][logparser.name][error["id"]] = error
            if "unknown" in session:
                for unknown in session["unknown"]:
                    index = 0
                    steps = scenario["steps"]
                    startTime = unknown["start_time"].replace("T", " ")
                    unknown_dict = {"log_file": logparser.name}
                    for key in ["id", "thread", "start_time", "end_time", "error", "session"]:
                        if key in unknown:
                            unknown_dict[key] = unknown[key]
                    while index <= len(steps) - 1:
                        if steps[index]["start_time"] > startTime:
                            break
                        index += 1
                    step = steps[index-1]
                    if "unknown" not in step:
                        step["unknown"] = []
                    step["unknown"].append(unknown_dict)
                    if "error" in unknown and "level" in unknown["error"] and unknown["error"]["level"] == "ERROR":
                        if "errors" not in step:
                            step["errors"] = []
                        step["errors"].append(unknown["error"])


            if "errors" in session:
                    for log_error in session["errors"]:
                        for error_id in session["errors"][log_error]:
                            session["errors"][log_error][error_id]["scenario"] = scenario["name"]
                    if "errors" not in scenario:
                        scenario["errors"] = []
                    scenario["errors"].append(session["errors"])
            if "error" in session:
                if "errors" not in scenario:
                    scenario["errors"] = []
                session["error"]["scenario"] = scenario_name
                scenario["errors"].append(session["error"])

            if scenario["result"].lower() == "failed" or "duplicated" in scenario:
                logparser.dumpSession(session)

            return new_session


def mergeSession(session, scenario):
    steps = scenario["steps"]
    if session["log_file"] not in scenario:
        scenario[session["log_file"]] = []
    start_time = session["start_time"].replace("T", " ")
    for i in range(len(scenario["steps"])):
        step = steps[i]
        if "id" not in step:
            step["id"] = i

        if steps[i]["start_time"] > start_time:
            index = 0
            if i > 0:
                index = i - 1
            step = steps[index]
            if not "sessions" in step:
                step["sessions"] = []

            item = {"name":session["log_file"],"start_time":session["start_time"],"session":session["id"],"log_file":session["log_file"],"type":"session"}
            if "stacks" in session["error"]:
                item["stacks"] = error["stacks"]
            item["error"] = session["error"]["name"]
            step["sessions"].append(item)
            scenario[session["log_file"]].append(index)
            return index


def addSession(logParser,scenario_name, tests,error):
    if scenario_name in tests:
        scenario = tests[scenario_name]
        log_session = logParser.session_list[error["session"] - 1]
        start_time = log_session["start_time"].replace("T", " ")
        if start_time < scenario["end_time"]:
            error["scenario"] = scenario_name
            log_session["log_file"] = logParser.name
            log_session["scenario"] = scenario_name
            step = mergeSession(log_session, scenario)
            if step:
                error["step"] = step


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--jenkins", help="jenkins args", required=False)
    parser.add_argument("--data_url", help="analysis data url", required=False)
    parser.add_argument("--server",help="log server name",required=True)
    parser.add_argument("--username",help="username log in server",required=True)
    parser.add_argument("--private_key", help="private_key location",required=True)
    parser.add_argument("--start_time", help="start time date and hours, format is YYYY-MM-DDTHH ",required=False)
    parser.add_argument("--end_time",help="end time date and hours, format is YYYY-MM-DDTHH",required=False)
    parser.add_argument("--log_map", help="server,logfile pattern,grep keyword group, delimiter as |",required=True)
    parser.add_argument("--confluence", help="confluence server, delimiter as |", required=True)
    parser.add_argument("--teams", help="teams webhook connectors", required=True)

    args = parser.parse_args()
    log_envs = []
    log_json_file = open("logs.json","r")
    log_json = json.load(log_json_file)
    log_json_file.close()
    if args.jenkins and args.data_url:
        server_url, job_name, username, password = args.jenkins.split("|")
        data_url = args.data_url


        server = jenkins.Jenkins(server_url, username, password)
        job = server.get_job_info(job_name)
        analysis_json_url = job["lastSuccessfulBuild"]["url"] + data_url
        # for build in job["builds"]:
        #     if build["number"] == 794:
        #         analysis_json_url = build["url"] + data_url
        response = server.jenkins_request(requests.Request('GET', analysis_json_url))
        data = json.loads(response.text)
        # server = None
        # analysis_file = open("analysis.json","r",encoding="utf-8")
        # data = json.load(analysis_file)
        # analysis_file.close()
        # analysis_json_url = ""

        for env in data:
            if "Env" in data[env]:
                log_data = {}
                log_data["env"] = data[env]["Env"]
                log_data["start_time"] = data[env]["start_time"]
                log_data["end_time"] = data[env]["end_time"]
                log_data["test_date"] = log_data["end_time"].split("T")[0]
                log_data["fatal"] = {}
                log_data["errors"] = {}
                log_data["users"] = {}
                log_data["matched"] = 0
                log_data["matchable"] = 0
                log_data["match_failed"] = 0
                log_data["total"] = data[env]["Total"]
                log_data["tests"] = parseTests(server,data[env]["Env"],analysis_json_url,data[env]["timeline"],log_data)
                log_data["logs"] = []
                log_data["log_files"] = []
                log_envs.append(log_data)

    server = args.server
    private_key = args.private_key

    username = args.username
    log_maps=args.log_map.split("|")

    log_dict={}

    server_log = ServerLog(server,username,private_key)
    if args.jenkins and args.data_url:
        for log_env in log_envs:
            server_log.set_duration(log_env["start_time"],log_env["end_time"])
            if log_env["env"] not in log_dict:
                log_dict[log_env["env"]] = {}

            log_env_res = log_dict[log_env["env"]]

            for log_map in log_maps:
                log_name, log_pattern= log_map.split(":")
                log_name=log_name.replace("<env>",log_env["env"])
                log_pattern = log_pattern.replace("<env>",log_env["env"])
                log_env_res[log_name] = server_log.extract_log(log_name,log_pattern)
    else:
        server_log.set_duration(args.start_time,args.end_time)
        for log_map in log_maps:
            log_name, log_pattern = log_map.split(":")
            server_log.extract_log(log_name, log_pattern)

    teams = {}
    for team_str in args.teams.split(","):
        (env, webhook) = team_str.split("|", 1)
        teams[env] = pymsteams.connectorcard(webhook)

    for log_env in log_envs:
        # if log_env["env"].find("qa1") < 0:
        #     continue
        test_date = log_env["test_date"]
        env_name = log_env["env"]
        for log_item in log_json:
            jsonCfg = open(log_item["name"] + ".json", "r", encoding="utf-8")
            log_cfg = json.load(jsonCfg, strict=False)
            log_file_name = log_item["file"].replace("<env>",env_name)
            log_env["log_files"].append(log_file_name)
            if hasattr(server_log,log_file_name) and getattr(server_log,log_file_name):
                print("Processing " + log_file_name + "...")
                logParser = LogParser(log_file_name,test_date,log_cfg)
                if "map_keys" in log_item:
                    map_file_name = log_item["map_keys"].replace("<env>",env_name)
                    if os.path.exists("./" + map_file_name):
                        maps_file = open(map_file_name, "r", encoding="utf-8")
                        maps = json.load(maps_file)
                        logParser.setKeysMap(maps)

                logParser.parseLog()

                if not "main" in log_item or not log_item["main"]:
                    log_env["logs"].append(logParser)
                else:
                    log_env["main"] = logParser
                    log_env["main_log"] = logParser.name
                    mergeTests(log_env, logParser, log_env["users"],log_item)
                    # mergeTests(log_env["tests"], logParser, log_item)

                if "fatal" in logParser.categories:
                    log_env["fatal"][log_item["name"]] = logParser.categories["fatal"]
            elif hasattr(server_log,log_file_name) and not getattr(server_log,log_file_name):
                team_text = "<H2 style='color:red;'> No " + log_file_name + " log found from " + log_env["start_time"] \
                            + " to " + log_env["end_time"] + "! </H2>"
                print(team_text)
                teams[env].text(team_text)
                teams[env].send()
                teams[env].payload.clear()

        if "main" in log_env:
            mainLog = log_env.pop("main")

            log_env_logs = log_env.pop("logs")

            log_env["duplicated"] = {}
            for scenario in log_env["tests"]:
                scenario_data = log_env["tests"][scenario]
                if "duplicated" in scenario_data:
                    log_env["duplicated"][scenario] = scenario_data
            for logParser in log_env_logs:
                log_env["errors"][logParser.name] = logParser.categories
                for error in logParser.error_list:
                    error["log_file"] = logParser.name
                    if mainLog.key in error:
                        session = None
                        if error[mainLog.key] in mainLog.sessions:
                            key_sessions = mainLog.sessions[error[mainLog.key]]
                            mainSession = mainLog.getSession(error[mainLog.key],error["log_time"])
                            if mainSession and "end_time" in mainSession and mainSession["end_time"] > error["log_time"]:
                                session = mainSession
                        if session:
                            if "errors" not in session:
                                session["errors"] = {}
                            if logParser.name not in session["errors"]:
                                session["errors"][logParser.name] = {}
                            session["errors"][logParser.name][error["id"]] = error
                            if "scenario" in session:
                                scenario_name = session["scenario"]
                                addSession(logParser, scenario_name, log_env["tests"],error)
                        elif error[mainLog.key] in log_env["users"]:
                            user = error[mainLog.key]
                            users = log_env["users"][error[mainLog.key]]
                            for start_time in users:
                                log_time = error["log_time"].replace("T", " ")
                                if log_time > start_time and log_time < users[start_time]["end_time"]:
                                    scenario_name = users[start_time]["scenario"]
                                    addSession(logParser, scenario_name, log_env["tests"],error)

                logParser.dumpSessions()
        #     error_file = open(logParser.name + "/categories.json","r",encoding="utf-8")
        #     log_env["errors"][logParser.name] = json.load(error_file)
        #     error_file.close()

        # main_error = open(mainLog.name + "/categories.json", "r",encoding="utf-8")
        # log_env["errors"][mainLog.name] = json.load(main_error)
        # main_error.close()

            log_env["errors"][mainLog.name] = mainLog.categories
            mainLog.dumpSessions()


    messages = {}
    for env in teams:
        send_flag = True
        for log_env in log_envs:
            if log_env["env"].find(env) >= 0:
                errors = log_env["errors"]

                total_error = 0
                total_exception = 0
                msg_texts = {}
                log_files = ",".join(log_env["errors"])
                for log_file in log_env["errors"]:
                    teams[env].title(log_file + " Log Error Checking Result For Auto Test")
                    log_file_erros = log_env["errors"][log_file]
                    log_error_num = 0
                    log_exception_num= 0
                    log_scenario_num = 0
                    log_error_texts = {}
                    error_lines ={}
                    total_lines =  0
                    for category in log_file_erros:

                        category_errors = log_file_erros[category]
                        category_error_num = 0
                        category_exception_num = 0
                        category_scenarios_num =  0
                        error_texts = {}
                        for error_type  in category_errors:
                            error_list = category_errors[error_type]
                            error_list_num = len(error_list)
                            category_error_num += error_list_num
                            exception_num = 0
                            scenario_num = 0
                            for error in error_list:
                                if "stacks" in error:
                                    exception_num += 1
                                if "scenario" in error:
                                    scenario_num +=  1
                            category_exception_num += exception_num
                            category_scenarios_num += scenario_num
                            if error_list_num > 0:
                                error_texts[error_type + "(" + str(scenario_num) + "/" + str(error_list_num) +")"] = error_list_num
                                if (error_list_num) not in error_lines:
                                    error_lines[error_list_num] = 1
                                else:
                                    error_lines[error_list_num] += 1
                        total_lines += len(error_texts)
                        if category_error_num > 0:
                            log_error_texts[category + "(" + str(category_scenarios_num) + "/" + str(category_error_num) +")"] = error_texts
                        log_error_num += category_error_num
                        log_scenario_num += category_scenarios_num
                        log_exception_num += category_exception_num

                    total_error += log_error_num
                    total_exception += log_exception_num
                    # msg_texts[log_file + "(" + str(log_exception_num) + "/" + str(log_error_num) + ")"] = log_error_texts
                    msg_texts = log_error_texts
                    log_file_name = log_file + ".log"
                    if hasattr(server_log, log_file_name) and not getattr(server_log, log_file_name):
                        team_text = "<H2 style='color:red;'> No " + log_file + " log found from " + log_env["start_time"] \
                                    + " to " + log_env["end_time"] +"! </H2>"
                        print(team_text)
                        teams[env].text(team_text)
                    else:
                        team_text = "<H2>Total : " + str(log_error_num) + " errors and total : " + str(
                            log_exception_num) + " exceptions found from " + log_env["start_time"] \
                                    + " to " + log_env["end_time"]

                        if log_file.find("portal") >=0:
                            team_text += " and detected "+ str(log_env["matched"]) +" of matchable " + str(log_env["matchable"]) + " from total " + str(log_env["total"]) +" scenarios, among them matched failed scenarios " + str(log_env["match_failed"])
                        team_text += "</H2>"
                        times = 10
                        if total_lines > 70:
                            line_times  = [lines for lines in error_lines]
                            line_times.sort()
                            lines_total = total_lines
                            for lines_num in line_times:
                                lines_total -= error_lines[lines_num]
                                if lines_total <= 70:
                                    times = lines_num
                                    break
                            team_text += "\n\n total error message is too big. Only the errors happened more than " + str(times) + " times would be listed"
                        team_text += "<hr/>\n\n"
                        teams[env].text(team_text)
                        for category_text in log_error_texts:
                            section = pymsteams.cardsection()
                            # section.title("## Log : " + log_text)
                            section_text = "<ul>"
                            # for category_text in msg_texts[log_text]:
                            if len(log_error_texts) > 1:
                                section_text += "<h3>" + category_text + "</h3>"
                            #     section_text += "\n\n<ul>"
                            for err_text in msg_texts[category_text]:
                                if total_lines <= 70:
                                    section_text += "<li>" + err_text + "</li>"
                                elif msg_texts[category_text][err_text] > times:
                                    section_text += "<li>" + err_text + "</li>"
                            section_text += "</ul>"
                            # section_text += "</ul>"
                            section.text(section_text)
                            teams[env].addSection(section)
                    try:
                        teams[env].send()
                        teams[env].payload.clear()
                    except Exception as e:
                        print(e)
                        messages[env] = teams[env].payload


    log_result = open("log_analysis.json","w",encoding="utf-8")
    json.dump(log_envs,log_result,indent=4)
    log_result.close()

    zipfile.ZipFile("log_analysis.zip","w",zipfile.ZIP_DEFLATED,compresslevel=9).write("log_analysis.json")

    os.remove("log_analysis.json")